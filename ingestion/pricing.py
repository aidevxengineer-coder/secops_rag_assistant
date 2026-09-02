# ingestion/pricing.py
MODEL_PRICING = {
    # $ per 1M tokens — verified against Google's Gemini API pricing (July 2026)
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-2.5-flash":      {"input": 0.30, "output": 2.50},
}

def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model_name)
    if not pricing:
        return 0.0
    return (input_tokens / 1_000_000 * pricing["input"]) + (output_tokens / 1_000_000 * pricing["output"])