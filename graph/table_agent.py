"""
Table agent: given a query, this asks the LLM to (1) pick the relevant
table(s) from the registry and (2) write a SELECT query against them,
then executes it against Postgres and returns the rows.

This is the piece that answers "how do we know a query is about a table" —
the orchestrator node classifies it, and this agent then does the actual
table selection + SQL generation as a second, more focused LLM call.
"""

from .llm_client import generate_text
from ingestion.table_store import (
    search_relevant_tables,
    run_sql,
)  # was: get_registry_summary, run_sql
from ingestion.trace_store import save_trace_event
from ingestion.config import Config


def _format_registry(registry: list[dict]) -> str:
    if not registry:
        return "(no tables registered yet)"
    parts = []
    for t in registry:
        parts.append(
            f"table_name: {t['table_name']}\n"
            f"  source: {t['source']} (page {t['page']})\n"
            f"  columns: {t['columns']}\n"
            f"  row_count: {t['row_count']}\n"
            f"  sample rows: {t['preview']}"
        )
    return "\n\n".join(parts)


def query_tables(
    user_query: str, trace_id: str | None = None
) -> tuple[list[dict], str]:
    """
    Returns (rows, sql_used). Rows is empty list if nothing matched or the
    generated SQL failed — caller should treat that as "not found", same
    as an empty vector retrieval result.
    """
    registry = search_relevant_tables(
        user_query, top_n=5
    )  # was: get_registry_summary()
    registry_text = _format_registry(registry)

    if trace_id:
        save_trace_event(
            trace_id,
            "sql_execution",
            "table_agent",
            payload={
                "candidate_tables": [t["table_name"] for t in registry],
            },
        )

    prompt = f"""You are a SQL agent for a Postgres database of tables extracted from
security/cryptography documents. Below is the registry of all available tables
with their columns and sample rows.

{registry_text}

User question: {user_query}

Write ONE SQL SELECT query that answers this question using the most relevant
table(s) above. Rules:
- Only SELECT statements — never modify data.
- Use exact table_name and column names as shown above (they're already
  lowercase/sanitized, don't guess different casing).
- If no table above seems relevant to the question, respond with exactly: NONE
- Return ONLY the SQL query text (or NONE), no markdown fences, no explanation."""

    sql = generate_text(
        prompt,
        trace_id=trace_id,
        node_name="table_agent_sql_gen",
        model_name=Config.GENERATION_MODEL,
    ).strip()

    if sql.upper() == "NONE" or not sql:
        return [], ""

    # Strip accidental markdown fences if the model added them anyway
    sql = sql.replace("```sql", "").replace("```", "").strip()

    try:
        rows = run_sql(sql)
        return rows, sql
    except Exception as e:
        print(f"[warn] table agent SQL failed: {e}\nSQL was: {sql}")
        return [], sql
