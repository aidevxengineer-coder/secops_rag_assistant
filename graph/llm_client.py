"""
Shared Gemini text-generation client. Two entry points:
  generate_text()        - blocking, used for rewriter/orchestrator/evaluator/SQL-gen
  generate_text_stream() - streams tokens live, used ONLY for the final answer
                            nodes (main_llm_rag / main_llm_table / main_llm_no_rag)
                            so the user sees the answer build up in real time.
Both log every call attempt (success AND failure) to Postgres (llm_calls table)
via ONE shared helper — _record(), below — AND push a summary event to the
llm_calls Redis stream. Trace events (node timing/routing) go through a
SEPARATE stream (trace_tracing.py), kept apart from token/latency data on purpose.
"""

import time
from google import genai
from google.genai import types
from graph.gen_ai_errors import (
    _classify_error,
    LLMContextLimitError,
    LLMOverloadError,
    LLMRateLimitError,
)
from ingestion.config import Config
from ingestion.trace_store import save_llm_call
from ingestion.live_events import publish_trace_event, publish_llm_call_event

_client = None

MAX_RETRIES_PER_MODEL = 2
BASE_BACKOFF_SECONDS = 1.5


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        Config.validate()
        _client = genai.Client(api_key=Config.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=120_000))
    return _client


def _record(
    trace_id: str | None,
    node_name: str,
    model: str,
    latency_ms: float,
    prompt: str = "",
    response_text: str = "",
    usage=None,
) -> None:
    """
    Single logging call site for every LLM attempt — success or failure.
    Pass `usage=None` for any failed/aborted attempt (overload, rate limit,
    context limit, etc.) — this naturally logs 0/0/0 tokens, which is exactly
    what marks a failed attempt in the analytics queries (total_tokens = 0).
    `response_text` on a failure should be a short human-readable reason
    string (e.g. "<overload, retrying>") — it's what shows up in the admin
    trace viewer for that failed attempt.
    """
    if not trace_id:
        return

    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
    total_tokens = getattr(usage, "total_token_count", 0) or 0

    save_llm_call(
        trace_id, node_name, model,
        prompt[:5000], response_text[:5000],
        prompt_tokens, completion_tokens, total_tokens, latency_ms,
    )

    publish_llm_call_event(trace_id, {
        "event": "llm_call",
        "node": node_name,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": round(latency_ms, 1),
    })


def _fallback_models(model_name: str) -> list[str]:
    if model_name == Config.GENERATION_MODEL:
        return [Config.GENERATION_MODEL, Config.GENERATION_MODEL_2, Config.GENERATION_MODEL_3]
    return [Config.GENERATION_MODEL_2, Config.GENERATION_MODEL, Config.GENERATION_MODEL_3]


def generate_text(
    prompt: str,
    system: str | None = None,
    json_mode: bool = False,
    trace_id: str | None = None,
    node_name: str = "unknown",
    model_name: str = Config.GENERATION_MODEL,
) -> str:
    """Blocking call — used where you need the full response before deciding
    what to do next (routing decisions, SQL text, relevance judgments).

    Retries transient failures (503 overload, timeouts) with backoff, then
    falls through to progressively lighter models if the primary stays down.
    """
    client = _get_client()
    config_kwargs = {}
    if system:
        config_kwargs["system_instruction"] = system
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"
    config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    fallbacks = _fallback_models(model_name)
    models_to_try = [model_name] + [m for m in fallbacks if m != model_name]
    last_error: Exception | None = None

    for attempt_model in models_to_try:
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            start = time.perf_counter()
            try:
                response = client.models.generate_content(
                    model=attempt_model, contents=prompt, config=config,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                text_out = response.text.strip()

                _record(
                    trace_id, node_name, attempt_model, latency_ms,
                    prompt=prompt, response_text=text_out,
                    usage=getattr(response, "usage_metadata", None),
                )
                return text_out

            except Exception as e:
                err = _classify_error(e)
                last_error = err
                latency_ms = (time.perf_counter() - start) * 1000
                is_last_attempt_for_model = attempt == MAX_RETRIES_PER_MODEL

                if isinstance(err, LLMContextLimitError):
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="Token limit exceeded, no more retries now displaying message to user")
                    break

                elif isinstance(err, LLMRateLimitError):
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="Rate limit hit, no more retries now displaying message to user")
                    break

                elif isinstance(err, LLMOverloadError) and not is_last_attempt_for_model:
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="<overload, retrying>")
                    time.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue

                elif isinstance(err, LLMOverloadError):
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="2nd attempt also failed (overload), no more retries now displaying message to user")
                    break

                else:
                    # Non-overload error (bad request, auth, etc.) — don't
                    # burn retries/fallbacks on something retrying won't fix
                    raise err

    raise RuntimeError(
        f"All models failed for node={node_name}, trace={trace_id}: {last_error}"
    ) from last_error


def generate_text_stream(
    prompt: str,
    trace_id: str,
    node_name: str,
    model_name: str = Config.GENERATION_MODEL,
) -> str:
    """
    Streams tokens live to the trace Redis stream as 'answer_token' events
    (same stream as node/routing events — true chronological order), while
    building and returning the full text at the end for the graph state.

    Retries/falls back across models only while no tokens have been sent yet.
    Once the stream has started emitting tokens to the client, a failure is
    published as 'answer_error' and re-raised rather than silently retried —
    switching models mid-stream would duplicate or corrupt what the user
    already sees.
    """
    client = _get_client()
    fallbacks = _fallback_models(model_name)
    models_to_try = [model_name] + [m for m in fallbacks if m != model_name]
    last_error: Exception | None = None

    for attempt_model in models_to_try:
        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            start = time.perf_counter()
            full_text = ""
            last_chunk = None
            started_emitting = False

            try:
                for chunk in client.models.generate_content_stream(model=attempt_model, contents=prompt):
                    if chunk.text:
                        started_emitting = True
                        full_text += chunk.text
                        publish_trace_event(trace_id, {"event": "answer_token", "text": chunk.text})
                    last_chunk = chunk

                latency_ms = (time.perf_counter() - start) * 1000
                usage = getattr(last_chunk, "usage_metadata", None) if last_chunk else None
                _record(trace_id, node_name, attempt_model, latency_ms,
                        prompt=prompt, response_text=full_text, usage=usage)
                return full_text.strip()

            except Exception as e:
                err = _classify_error(e)
                last_error = err
                latency_ms = (time.perf_counter() - start) * 1000
                is_last_attempt_for_model = attempt == MAX_RETRIES_PER_MODEL

                if started_emitting and not isinstance(err, LLMContextLimitError):
                    publish_trace_event(trace_id, {"event": "answer_error", "text": str(e)})
                    raise

                elif isinstance(err, LLMContextLimitError):
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="Token limit exceeded, no more retries now displaying message to user")
                    break

                elif isinstance(err, LLMRateLimitError):
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="Rate limit hit, no more retries now displaying message to user")
                    break

                elif isinstance(err, LLMOverloadError) and not is_last_attempt_for_model:
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="<overload, retrying>")
                    time.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue

                elif isinstance(err, LLMOverloadError):
                    _record(trace_id, node_name, attempt_model, latency_ms,
                            prompt=prompt[:40], response_text="2nd attempt also failed (overload), no more retries now displaying message to user")
                    break

                else:
                    raise err

    publish_trace_event(trace_id, {"event": "answer_error", "text": str(last_error)})
    raise RuntimeError(
        f"All models failed for node={node_name}, trace={trace_id}: {last_error} because user has exceeded token limits for today"
    ) from last_error