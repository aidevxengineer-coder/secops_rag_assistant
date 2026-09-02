"""Projects, chats, messages — permanent storage in Postgres, replaces the
in-memory session dict entirely. Same raw-SQL-via-SQLAlchemy pattern as
ingestion/table_store.py and auth/db.py, same shared engine."""
from sqlalchemy import text
from ingestion.table_store import get_engine


def ensure_chat_tables():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS projects (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chats (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
                title TEXT NOT NULL DEFAULT 'New Chat',
                history_summary TEXT NOT NULL DEFAULT '',
                summarized_through INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        # for chats table created before this column existed:
        conn.execute(text("ALTER TABLE chats ADD COLUMN IF NOT EXISTS summarized_through INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                route TEXT,
                sources_json JSONB,
                sql_text TEXT,
                report_url TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id)"))


# --- projects ---
def create_project(user_id: str, name: str) -> dict:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO projects (user_id, name) VALUES (:user_id, :name) RETURNING *
        """), {"user_id": user_id, "name": name}).mappings().first()
    return dict(row)


def list_projects(user_id: str) -> list[dict]:
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT * FROM projects WHERE user_id = :user_id ORDER BY created_at DESC
        """), {"user_id": user_id}).mappings().all()
    return [dict(r) for r in rows]


def delete_project(user_id: str, project_id: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM projects WHERE id = :id AND user_id = :user_id
        """), {"id": project_id, "user_id": user_id})


# --- chats ---
def create_chat(user_id: str, project_id: str | None = None, title: str = "New Chat") -> dict:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO chats (user_id, project_id, title)
            VALUES (:user_id, :project_id, :title) RETURNING *
        """), {"user_id": user_id, "project_id": project_id, "title": title}).mappings().first()
    return dict(row)


def list_chats(user_id: str, project_id: str | None = None) -> list[dict]:
    engine = get_engine()
    query = "SELECT * FROM chats WHERE user_id = :user_id"
    params = {"user_id": user_id}
    if project_id:
        query += " AND project_id = :project_id"
        params["project_id"] = project_id
    query += " ORDER BY updated_at DESC"
    with engine.begin() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return [dict(r) for r in rows]


def get_chat(user_id: str, chat_id: str) -> dict | None:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT * FROM chats WHERE id = :id AND user_id = :user_id
        """), {"id": chat_id, "user_id": user_id}).mappings().first()
    return dict(row) if row else None


def rename_chat(user_id: str, chat_id: str, title: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE chats SET title = :title, updated_at = now()
            WHERE id = :id AND user_id = :user_id
        """), {"title": title, "id": chat_id, "user_id": user_id})


def delete_chat(user_id: str, chat_id: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM chats WHERE id = :id AND user_id = :user_id
        """), {"id": chat_id, "user_id": user_id})


def get_message_count(chat_id: str) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT COUNT(*) AS c FROM messages WHERE chat_id = :chat_id"
        ), {"chat_id": chat_id}).mappings().first()
    return row["c"]


def touch_chat(chat_id: str, history_summary: str = None, summarized_through: int = None):
    engine = get_engine()
    sets = ["updated_at = now()"]
    params = {"id": chat_id}
    if history_summary is not None:
        sets.append("history_summary = :summary")
        params["summary"] = history_summary
    if summarized_through is not None:
        sets.append("summarized_through = :through")
        params["through"] = summarized_through
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE chats SET {', '.join(sets)} WHERE id = :id"), params)


# --- messages ---
def add_message(chat_id: str, role: str, content: str, route: str = None,
                 sources_json: str = None, sql_text: str = None, report_url: str = None):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO messages (chat_id, role, content, route, sources_json, sql_text, report_url)
            VALUES (:chat_id, :role, :content, :route, :sources_json, :sql_text, :report_url)
        """), {
            "chat_id": chat_id, "role": role, "content": content, "route": route,
            "sources_json": sources_json, "sql_text": sql_text, "report_url": report_url,
        })


def get_messages(chat_id: str, limit: int = None) -> list[dict]:
    engine = get_engine()
    query = "SELECT * FROM messages WHERE chat_id = :chat_id ORDER BY created_at ASC"
    if limit:
        query = f"SELECT * FROM ({query}) sub ORDER BY created_at DESC LIMIT {limit}"
    with engine.begin() as conn:
        rows = conn.execute(text(query), {"chat_id": chat_id}).mappings().all()
    result = [dict(r) for r in rows]
    return list(reversed(result)) if limit else result  # keep chronological order either way

def get_daily_activity(days: int = 14):
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(f"""
            SELECT DATE(created_at) AS day, COUNT(*) AS message_count
            FROM messages
            WHERE created_at > now() - interval '{days} days'
            GROUP BY DATE(created_at) ORDER BY day
        """)).mappings().all()
    return [dict(r) for r in rows]