"""
Every node from your flowchart, implemented as a function of GraphState.
Each LLM-calling node is wrapped in timed_stage so latency shows up in the
same logs/latency.jsonl as ingestion — one unified timing story end to end.
"""

import json
import uuid

from uvicorn import Config
from .llm_client import generate_text
from .state import GraphState
from .table_agent import query_tables
from ingestion.latency_logger import timed_stage
from retreival.hybrid_retriever import hybrid_retrieve
from ingestion.vector_store import list_sources
from ingestion.table_store import get_registry_summary
from .tracing import trace_node
from ingestion.trace_store import save_trace_event
from .llm_client import generate_text, generate_text_stream
from ingestion.config import Config
from ingestion.table_store import search_relevant_tables
from .mcp_client import call_tavily, call_pdf_report

HISTORY_LIMIT = 10  # messages, not turns — 10 = 5 user+assistant exchanges

NO_FILE_DISCLAIMER_RULE = """
IMPORTANT: If the user asks for a PDF, downloadable file, or "report," do NOT say
you cannot generate files, do NOT suggest they copy this into Word/Google Docs, and
do NOT add any disclaimer about file generation. A separate part of the system
handles PDF creation automatically when needed — just answer the question normally.
Never mention PDFs, downloads, or file formats in your answer at all.
"""


def _format_history(history: list[dict], summary: str = "") -> str:
    parts = []
    if summary:
        parts.append(f"[Earlier conversation summary]\n{summary}")
    if history:
        parts.append(
            "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
        )
    return "\n\n".join(parts) if parts else "(no prior conversation)"


def _format_docs(docs: list) -> str:
    if not docs:
        return "(no documents retrieved)"
    parts = []
    for i, doc in enumerate(docs):
        src = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        block_type = doc.metadata.get("block_type", "text")
        parts.append(
            f"[Doc {i+1} | source={src} page={page} type={block_type}]\n{doc.page_content}"
        )
    return "\n\n".join(parts)


def _safe_json_parse(raw: str, fallback: dict) -> dict:
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[warn] failed to parse LLM JSON, using fallback. Raw was: {raw[:200]}")
        return fallback


# LLM CALL 1
@trace_node("summarizer")
def summarizer_node(state: GraphState) -> dict:
    history = state.get("conversation_history", [])
    if len(history) <= HISTORY_LIMIT:
        return {}  # no-op, nothing to summarize yet

    old_messages = history[:-HISTORY_LIMIT]
    recent_messages = history[-HISTORY_LIMIT:]
    existing_summary = state.get("history_summary", "")

    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in old_messages)
    prompt = f"""Summarize this conversation concisely, preserving key facts, decisions,
and any specific values/IDs mentioned. Merge with the previous summary if present.

Previous summary: {existing_summary or "(none)"}

Conversation to fold in:
{history_text}

Return ONLY the updated summary text."""

    new_summary = generate_text(
        prompt,
        trace_id=state.get("trace_id"),
        node_name="summarizer",
        model_name=Config.GENERATION_MODEL_2,
    )
    return {"history_summary": new_summary, "conversation_history": recent_messages}


# ---------------------------------------------------------------------------
# LLM Call 2: Query Rewriter
# ---------------------------------------------------------------------------
@trace_node("query_rewriter")
def query_rewriter_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    with timed_stage("query_rewriter", doc_id):
        prompt = f"""Rewrite the user's latest query into a standalone, fully-specified question.

FIRST, decide: is this new query a FOLLOW-UP to the previous conversation (uses pronouns
like "it"/"that"/"this", references something just discussed, or is clearly continuing
the same topic), or is it a NEW, UNRELATED topic/question?

- If it is a FOLLOW-UP: use the conversation history to fill in what's missing (resolve
  pronouns, carry over the specific subject being discussed) so the query stands alone.
- If it is a NEW topic: rewrite it using ONLY the query itself. Do NOT pull in framework
  names, control IDs, CVE numbers, standards, versions, or any other specific terms from
  earlier turns unless the current query actually mentions or clearly implies them.
  A general question must stay general — do not narrow it to a previous topic just
  because that topic appeared earlier in the conversation.

If evaluator feedback from a previous failed retrieval attempt is present, use it to
make the query more precise (more specific terms, different phrasing, narrower scope) —
this only applies to retrying the CURRENT query, never to reintroducing unrelated past topics.

{NO_FILE_DISCLAIMER_RULE}

Conversation history:
{_format_history(state.get("conversation_history", []), state.get("history_summary", ""))}

Original query: {state["original_query"]}
Evaluator feedback (if any): {state.get("evaluator_feedback", "none")}

Return ONLY the rewritten query text, nothing else — no preamble, no quotes."""

        rewritten = generate_text(
            prompt,
            trace_id=state.get("trace_id"),
            node_name="query_rewriter",
            model_name=Config.GENERATION_MODEL_2,
        )
    return {"rewritten_query": rewritten}


# ---------------------------------------------------------------------------
# LLM Call 3: Orchestrator — does this need vector RAG, a table lookup, or neither?
# ---------------------------------------------------------------------------
@trace_node("orchestrator")
def orchestrator_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]

    sources = list_sources(state["collection_name"])
    tables = search_relevant_tables(state["rewritten_query"], top_n=10)
    table_summary = "\n".join(f"- {t['table_name']} (columns: {t['columns']})" for t in tables) or "(none yet)"
    doc_summary = ", ".join(sources) or "(none yet)"

    with timed_stage("orchestrator", doc_id):
        prompt = f"""You have access to three knowledge sources:

VECTOR KNOWLEDGE BASE documents (conceptual/prose): {doc_summary}

STRUCTURED TABLES available (numeric lookups):
{table_summary}

LIVE WEB SEARCH (Tavily): ONLY for current/real-time CYBERSECURITY information not in
the static knowledge base — new CVEs, active exploits, breaking security advisories,
threat actor activity, or security-relevant "latest"/"this week"/"as of today" queries.
Never use this for non-security current events (sports, entertainment, general news,
weather, stock prices, etc.) even if the query asks for "latest" or "current" info.

This system is a CYBERSECURITY knowledge assistant grounded in NIST, CISA, MITRE ATT&CK,
and FIPS references. It does NOT have knowledge of, and should NOT attempt to answer,
anything outside security/compliance/cryptography — including sports, general
programming/debugging, entertainment, general trivia, or any other unrelated domain.

Classify this query into exactly one route:

- "table_query": specific numeric value, table lookup, comparing rows/columns
  from the STRUCTURED TABLES above.
- "vector_rag": needs conceptual/prose security knowledge that plausibly exists in the
  knowledge base above (NIST/CISA/MITRE/FIPS topics only).
- "web_search": needs current/real-time SECURITY info not in the static knowledge base
  (see restriction above — security topics only, never general current events).
- "none": general chit-chat, greetings, OR the query is outside this system's domain
  entirely (sports, general programming, entertainment, unrelated trivia, or any topic
  with no connection to cybersecurity/compliance/cryptography). This includes queries
  that ask for "latest"/"current" info on a NON-security topic — those still go here,
  NOT to web_search, since web_search is scoped to security freshness only.

Original user message: {state["original_query"]}
Rewritten query: {state["rewritten_query"]}

Respond with ONLY valid JSON, no markdown fences:
{{"route": "table_query" or "vector_rag" or "web_search" or "none",
  "reason": "brief reason",
  "wants_pdf_report": true or false}}"""

        raw = generate_text(
            prompt, json_mode=True, trace_id=state.get("trace_id"),
            node_name="orchestrator", model_name=Config.GENERATION_MODEL,
        )
        parsed = _safe_json_parse(
            raw, {"route": "none", "reason": "Failed to parse LLM response", "wants_pdf_report": False},
        )

    return {"route": parsed["route"], "wants_pdf_report": parsed.get("wants_pdf_report", False)}


# ---------------------------------------------------------------------------
# Retrieve Documents (hybrid vector + BM25 + RRF) — not an LLM call
# ---------------------------------------------------------------------------
@trace_node("retrieve")
def retrieve_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    docs = hybrid_retrieve(
        query=state["rewritten_query"],
        collection_name=state["collection_name"],
        doc_id=doc_id,
    )
    return {"retrieved_docs": docs}


# ---------------------------------------------------------------------------
# LLM Call 4: Document Relevance Evaluator
# ---------------------------------------------------------------------------
@trace_node("evaluator")
def evaluator_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    is_web = state.get("route") == "web_search"
    content = state.get("web_search_results", "(no results)") if is_web else _format_docs(state.get("retrieved_docs", []))
    source_label = "web search results" if is_web else "retrieved documents"

    trust_note = (
        """
IMPORTANT: These are LIVE web search results, which may describe events more recent
than your own training data. Do NOT reject them as "hallucinated" or "hasn't happened
yet" based on your own knowledge cutoff — trust the search content as current unless it
is internally inconsistent, contains an error message, or is clearly off-topic/spam.
""" if is_web else ""
    )

    with timed_stage("relevance_evaluator", doc_id):
        prompt = f"""Judge whether the {source_label} below are relevant and sufficient to
answer BOTH the original query and the rewritten query. Be strict about MISSING FACTS —
but judge ONLY the factual content, nothing else.

{NO_FILE_DISCLAIMER_RULE}

Do NOT consider whether a PDF, file, or any other output format can be produced — that
is a separate concern handled elsewhere in the system and is irrelevant to this judgment.
Only ask: "does this content contain the facts needed to answer the question?"
{trust_note}
Original query: {state["original_query"]}
Rewritten query: {state["rewritten_query"]}

{source_label.capitalize()}:
{content}

Respond with ONLY valid JSON, no markdown fences:
{{"is_relevant": true or false, "feedback": "if false, explain what's missing or what
search terms would help find the right content"}}"""

        raw = generate_text(
            prompt, json_mode=True, trace_id=state.get("trace_id"),
            node_name="evaluator", model_name=Config.GENERATION_MODEL_2,
        )
        parsed = _safe_json_parse(raw, {"is_relevant": False, "feedback": "Failed to parse LLM response"})
    return {"is_relevant": parsed["is_relevant"], "evaluator_feedback": parsed.get("feedback", "")}

# ---------------------------------------------------------------------------
# Retry Limit Check — application logic, not an LLM call
# ---------------------------------------------------------------------------
@trace_node("retry_check")
def retry_check_node(state: GraphState) -> dict:
    new_count = state.get("retry_count", 0) + 1
    save_trace_event(
        state.get("trace_id"),
        "retry",
        "retry_check",
        payload={"retry": new_count, "max_retries": state.get("max_retries", 2)},
    )
    return {"retry_count": new_count}


# ---------------------------------------------------------------------------
# Table Agent — LLM picks table(s) + writes SQL, executes against Postgres
# ---------------------------------------------------------------------------
@trace_node("table_agent")
def table_agent_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    with timed_stage("table_agent", doc_id):
        rows, sql_used = query_tables(
            state["rewritten_query"], trace_id=state.get("trace_id")
        )

    result = {"table_rows": rows, "table_sql": sql_used}
    if not rows:
        result["evaluator_feedback"] = (
            "No matching table/rows found for this query. Try rephrasing with "
            "more specific column names, document names, or numeric ranges."
        )
    return result

# ---------------------------------------------------------------------------
# LLM Call — Web Search via Tavily MCP (route: "web_search")
# ---------------------------------------------------------------------------
@trace_node("web_search")
def web_search_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    with timed_stage("web_search", doc_id):
        raw = call_tavily("tavily_search", {
            "query": state["rewritten_query"],
            "max_results": 5,
            "search_depth": "advanced",
        })
    return {"web_search_results": raw}

# ---------------------------------------------------------------------------
# PDF Report Generator — runs after final_response is ready, on demand
# ---------------------------------------------------------------------------
@trace_node("report_generator")
def report_generator_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    filename = f"secops_report_{state.get('trace_id') or uuid.uuid4().hex}.pdf"

    with timed_stage("report_generator", doc_id):
        raw = call_pdf_report({
            "markdown": f"# SecOps Copilot Report\n\n**Query:** {state['original_query']}\n\n---\n\n{state['final_response']}",
            "outputFilename": filename,
            "showPageNumbers": True,
        })

    print("=" * 80)
    print("RAW MCP RETURN VALUE:")
    print(repr(raw))
    print("REPORTS_DIR:", Config.REPORTS_DIR.resolve())
    print("FILE EXISTS AT THAT PATH:", (Config.REPORTS_DIR / filename).exists())
    print("=" * 80)

    return {
        "report_path": filename,
        "report_url": f"{Config.PUBLIC_BASE_URL}/api/reports/{filename}",
    }

# ---------------------------------------------------------------------------
# Main LLM Call — grounded generation using SQL query results
# ---------------------------------------------------------------------------
@trace_node("main_llm_table")
def main_llm_table_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    rows = state.get("table_rows", [])

    with timed_stage("main_llm_table", doc_id):
        if not rows:
            # No matching rows — treat like the relevance evaluator failing,
            # so it can still go through the retry loop.
            return {
                "is_relevant": False,
                "evaluator_feedback": "No matching rows found in any table.",
            }

        prompt = f"""Answer the user's query using ONLY the SQL query results below.
Quote numeric values EXACTLY as they appear — never round, estimate, or paraphrase.

{NO_FILE_DISCLAIMER_RULE}

Original query: {state["original_query"]}
SQL used: {state.get("table_sql", "")}
Query results: {json.dumps(rows, default=str)}

Answer:"""
        response = generate_text_stream(
            prompt,
            trace_id=state.get("trace_id"),
            node_name="main_llm_table",
            model_name=Config.GENERATION_MODEL,
        )
    return {"final_response": response, "is_relevant": True}


# ---------------------------------------------------------------------------
# Main LLM Call — grounded generation using retrieved docs
# ---------------------------------------------------------------------------
@trace_node("main_llm_rag")
def main_llm_rag_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    with timed_stage("main_llm_rag", doc_id):
        prompt = f"""Answer the user's query using ONLY the retrieved documents below as
your source of truth. Follow these rules strictly:

1. If the documents contain a specific number, code, ID, or value, quote it EXACTLY
   as written — never round, estimate, average, or paraphrase a number.
2. If a table is present in the documents, read the correct row/column intersection
   carefully before answering — do not guess which cell corresponds to the value.
3. If the documents don't fully answer the query, say so explicitly rather than
   filling gaps with outside knowledge.
4. Cite which document/source the answer came from.

Conversation history:
{_format_history(state.get("conversation_history", []), state.get("history_summary", ""))}

{NO_FILE_DISCLAIMER_RULE}

Original query: {state["original_query"]}
Rewritten query: {state["rewritten_query"]}

Retrieved documents:
{_format_docs(state.get("retrieved_docs", []))}

Answer:"""

        response = generate_text_stream(
            prompt,
            trace_id=state.get("trace_id"),
            node_name="main_llm_rag",
            model_name=Config.GENERATION_MODEL,
        )
    return {"final_response": response}


# ---------------------------------------------------------------------------
# Main LLM Call — direct generation, no RAG needed
# ---------------------------------------------------------------------------
@trace_node("main_llm_no_rag")
def main_llm_no_rag_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    with timed_stage("main_llm_no_rag", doc_id):
        prompt = f"""Respond naturally to the user using the conversation history for context.
This query doesn't need document search.

If the user's question is unrelated to cybersecurity, compliance, or cryptography
(e.g. sports, entertainment, general programming/debugging help, general trivia, or
any other unrelated topic), politely say this assistant is focused on security
knowledge (NIST, CISA, MITRE ATT&CK, FIPS) and isn't the right tool for that kind
of question — don't attempt to answer it anyway, even if you know the answer.

{NO_FILE_DISCLAIMER_RULE}

Conversation history:
{_format_history(state.get("conversation_history", []), state.get("history_summary", ""))}

User: {state["original_query"]}"""

        response = generate_text_stream(
            prompt,
            trace_id=state.get("trace_id"),
            node_name="main_llm_no_rag",
            model_name=Config.GENERATION_MODEL,
        )
    return {"final_response": response}

@trace_node("main_llm_web")
def main_llm_web_node(state: GraphState) -> dict:
    doc_id = state.get("original_query", "query")[:40]
    with timed_stage("main_llm_web", doc_id):
        prompt = f"""Answer using ONLY the web search results below. Cite the source URL
for every claim. If results are stale or conflicting on a CVE/advisory, flag that explicitly.

If the web search results are about a topic unrelated to cybersecurity, compliance, or
cryptography (e.g. sports scores, entertainment, general news), do NOT answer using
them — instead say this assistant is focused on security knowledge and isn't the
right tool for that kind of question.

{NO_FILE_DISCLAIMER_RULE}

Original query: {state["original_query"]}

Web search results:
{state.get("web_search_results", "(none)")}

Answer:"""
        response = generate_text_stream(
            prompt, trace_id=state.get("trace_id"),
            node_name="main_llm_web", model_name=Config.GENERATION_MODEL,
        )
    return {"final_response": response}

# ---------------------------------------------------------------------------
# Safe Response — retries exhausted, nothing relevant found
# ---------------------------------------------------------------------------
@trace_node("safe_response")
def safe_response_node(state: GraphState) -> dict:
    return {
        "final_response": (
            "I wasn't able to find enough relevant information in the knowledge base "
            "to answer this confidently. Could you rephrase the question, or provide "
            "more specific terms (document name, control ID, RFC number, etc.)?"
        )
    }


# ---------------------------------------------------------------------------
# Save Query and Response — conversation memory
# ---------------------------------------------------------------------------
@trace_node("save_memory")
def save_memory_node(state: GraphState) -> dict:
    history = list(state.get("conversation_history", []))
    history.append({"role": "user", "content": state["original_query"]})
    history.append({"role": "assistant", "content": state["final_response"]})
    return {"conversation_history": history}


# ---------------------------------------------------------------------------
# Routing functions for conditional edges
# ---------------------------------------------------------------------------
def route_after_orchestrator(state: GraphState) -> str:
    route = state.get("route", "none")
    save_trace_event(
        state.get("trace_id"),
        "routing_decision",
        "orchestrator",
        payload={"route": route},
    )
    if route == "table_query":
        return "table_agent"
    if route == "vector_rag":
        return "retrieve"
    if route == "web_search":
        return "web_search"
    return "main_llm_no_rag"

def route_after_final_response(state: GraphState) -> str:
    if not state.get("wants_pdf_report"):
        return "save_memory"
    if state.get("is_relevant") is False:  # bailed via safe_response
        return "save_memory"
    return "report_generator"


def route_after_evaluator(state: GraphState) -> str:
    if not state.get("is_relevant"):
        return "retry_check"
    return "main_llm_web" if state.get("route") == "web_search" else "main_llm_rag"


def route_after_table_agent(state: GraphState) -> str:
    return "main_llm_table" if state.get("table_rows") else "retry_check"


def route_after_retry_check(state: GraphState) -> str:
    if state.get("retry_count", 0) < state.get("max_retries", 2):
        return "query_rewriter"
    return "safe_response"


def route_after_save_memory(state: GraphState) -> str:
    return (
        "summarizer"
        if len(state.get("conversation_history", [])) > HISTORY_LIMIT
        else "__end__"
    )
