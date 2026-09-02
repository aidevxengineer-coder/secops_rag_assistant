"""
Stores extracted Docling tables as real Postgres tables (one physical table
per extracted table, dynamic schema from the dataframe), plus a
`table_registry` catalog row per table so the LLM router/agent can look up
which physical table(s) are relevant to a query without scanning all of them.
"""

import re
import pandas as pd
from rank_bm25 import BM25Okapi
from sqlalchemy import create_engine, text
from .config import Config

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        if not Config.DATABASE_URL:
            raise EnvironmentError(
                "DATABASE_URL not set. Add it to .env, e.g. "
                "DATABASE_URL=postgresql://user:pass@localhost:5432/secops_tables"
            )
        _engine = create_engine(
            Config.DATABASE_URL,
            pool_pre_ping=True,  # checks connection is alive before using it, reconnects if dead
            pool_recycle=300,  # recycle connections every 5 min, before Supabase's pooler drops them
        )
        _ensure_registry_table()
    return _engine


def _ensure_registry_table():
    with _engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS table_registry (
                id SERIAL PRIMARY KEY,
                table_name TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                page INTEGER NOT NULL,
                columns TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                preview TEXT
            )
        """))


def _sanitize(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", str(name)).lower().strip("_")
    return name[:60] or "col"


def _build_preview(df: pd.DataFrame) -> str:
    """Head+tail for larger tables so the LLM sees both ends, not just the
    top — full table, no truncation, if it's small enough already."""
    if len(df) <= 6:
        preview_df = df
    else:
        preview_df = pd.concat([df.head(3), df.tail(2)])
    return "\n".join(str(r) for r in preview_df.to_dict(orient="records"))


def find_continuation_table(source: str, page: int, columns: tuple) -> str | None:
    """
    Checks if ANY earlier page (not just the immediately preceding one) for
    this source already has a table with an IDENTICAL column signature —
    handles tables that span 3+ pages, or that have a picture/unrelated
    content interrupting between two pages of the same table.
    """
    engine = get_engine()
    col_str = ", ".join(columns)
    with engine.begin() as conn:
        rows = (
            conn.execute(
                text("""
            SELECT table_name FROM table_registry
            WHERE source = :source AND page < :page AND columns = :columns
            ORDER BY page DESC
            LIMIT 1
        """),
                {"source": source, "page": page, "columns": col_str},
            )
            .mappings()
            .all()
        )

    return rows[0]["table_name"] if rows else None


def register_table(df: pd.DataFrame, source: str, page: int, table_idx: int) -> str:
    """
    Writes a dataframe as a real Postgres table (or appends to a detected
    continuation of an existing one) and updates the registry.
    """
    engine = get_engine()
    df = df.copy()
    df.columns = [_sanitize(c) for c in df.columns]

    # Empty-string cells (common in Docling table extraction — merged cells,
    # missing values) break pandas/SQLAlchemy's numeric type inference when
    # it tries int('') on a column it thinks is all-integer. Convert blanks
    # to real NULL so pandas treats the column correctly either way.
    df = df.replace(r"^\s*$", None, regex=True)
    df = df.map(lambda x: None if pd.isna(x) else str(x))

    continuation_table = find_continuation_table(source, page, tuple(df.columns))

    if continuation_table:
        table_name = continuation_table
        df.to_sql(table_name, engine, if_exists="append", index=False)

        # Preview should reflect the FULL merged table now, not just the new chunk
        full_df = pd.read_sql(f'SELECT * FROM "{table_name}"', engine)
        preview = _build_preview(full_df)

        with engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE table_registry
                SET row_count = :row_count, page = :page, preview = :preview
                WHERE table_name = :table_name
            """),
                {
                    "row_count": len(full_df),
                    "page": page,  # last page this table appeared on
                    "preview": preview,
                    "table_name": table_name,
                },
            )
        return table_name

    # No continuation found — create a new table as before
    table_name = _sanitize(f"tbl_{source}_p{page}_{table_idx}")
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    preview = _build_preview(df)

    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO table_registry (table_name, source, page, columns, row_count, preview)
            VALUES (:table_name, :source, :page, :columns, :row_count, :preview)
            ON CONFLICT (table_name) DO UPDATE SET
                columns = EXCLUDED.columns,
                row_count = EXCLUDED.row_count,
                preview = EXCLUDED.preview
        """),
            {
                "table_name": table_name,
                "source": source,
                "page": page,
                "columns": ", ".join(df.columns),
                "row_count": len(df),
                "preview": preview,
            },
        )
    return table_name


def get_registry_summary() -> list[dict]:
    """Returns every registered table's metadata."""
    engine = get_engine()
    with engine.begin() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT table_name, source, page, columns, row_count, preview FROM table_registry"
                )
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


def search_relevant_tables(query: str, top_n: int = 5) -> list[dict]:
    """
    BM25 pre-filter over table_name + columns + source, so the table agent
    only sends the LLM a short shortlist instead of the entire registry —
    matters once you're at dozens/hundreds of tables from 70+ docs.
    """
    registry = get_registry_summary()
    if not registry:
        return []
    if len(registry) <= top_n:
        return registry  # small enough, no need to filter

    corpus = [
        f"{r['table_name']} {r['columns']} {r['source']}".lower().split()
        for r in registry
    ]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(zip(registry, scores), key=lambda x: x[1], reverse=True)[:top_n]
    return [r for r, _score in ranked]


def run_sql(sql: str) -> list[dict]:
    """Executes a SELECT and returns rows as dicts. Only SELECT is allowed."""
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT statements are allowed from the SQL agent.")

    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(text(sql))
        return [dict(r) for r in result.mappings().all()]
    

