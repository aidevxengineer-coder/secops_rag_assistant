from google.genai import errors as genai_errors


class LLMError(Exception):
    """Base class for all LLM call failures."""

    def __init__(
        self, message: str, status: str | None = None, code: int | None = None
    ):
        super().__init__(message)
        self.status = status
        self.code = code


class LLMContextLimitError(LLMError):
    """Prompt too large for the model's context window. Retrying the same
    model is pointless — only fallback to bigger-context model or truncation helps."""


class LLMRateLimitError(LLMError):
    """Quota/rate limit hit. Don't blind-retry; either back off per Retry-After
    or switch model/API key immediately."""


class LLMOverloadError(LLMError):
    """Transient server overload (503) or timeout (504). Retry with backoff."""


def _classify_error(e: Exception) -> LLMError:
    if isinstance(e, genai_errors.APIError):
        status = getattr(e, "status", None) or ""
        code = getattr(e, "code", None)
        message = str(e)

        if code == 400 and ("context" in message.lower() or "token" in message.lower()):
            return LLMContextLimitError(message, status, code)
        if code == 429 or status == "RESOURCE_EXHAUSTED":
            return LLMRateLimitError(message, status, code)
        if code in (503, 504) or status in ("UNAVAILABLE", "DEADLINE_EXCEEDED"):
            return LLMOverloadError(message, status, code)
        # Other 4xx/5xx we don't have a specific policy for
        return LLMError(message, status, code)

    # Not even a genai APIError — unknown, don't swallow silently
    return LLMError(str(e))
