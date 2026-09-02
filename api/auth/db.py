"""Users + password reset tables. Same raw-SQL-via-SQLAlchemy pattern as
ingestion/table_store.py, using the same shared engine."""
from sqlalchemy import text
from ingestion.table_store import get_engine


def ensure_auth_tables():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_verified BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ
            )
        """))
        # add to ensure_auth_tables() in auth/db.py
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true"))
        # gen_random_uuid() needs the pgcrypto extension
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))


def get_user_by_email(email: str) -> dict | None:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM users WHERE email = :email"), {"email": email}
        ).mappings().first()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM users WHERE id = :id"), {"id": user_id}
        ).mappings().first()
    return dict(row) if row else None


def create_user(email: str, password_hash: str, role: str = "user") -> dict:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO users (email, password_hash, role)
            VALUES (:email, :password_hash, :role)
            RETURNING *
        """), {"email": email, "password_hash": password_hash, "role": role}).mappings().first()
    return dict(row)


def store_reset_token(user_id: str, token_hash: str, expires_at):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO password_resets (user_id, token_hash, expires_at)
            VALUES (:user_id, :token_hash, :expires_at)
        """), {"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at})


def get_valid_reset(token_hash: str) -> dict | None:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT * FROM password_resets
            WHERE token_hash = :token_hash AND used_at IS NULL AND expires_at > now()
            ORDER BY id DESC LIMIT 1
        """), {"token_hash": token_hash}).mappings().first()
    return dict(row) if row else None


def mark_reset_used(reset_id: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE password_resets SET used_at = now() WHERE id = :id"), {"id": reset_id})


def update_password(user_id: str, new_hash: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET password_hash = :h WHERE id = :id"), {"h": new_hash, "id": user_id})

def list_all_users() -> list[dict]:
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT id, email, role, is_verified, is_active, created_at FROM users ORDER BY created_at DESC
        """)).mappings().all()
    return [dict(r) for r in rows]


def set_user_active(user_id: str, is_active: bool):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = :active WHERE id = :id"),
                     {"active": is_active, "id": user_id})


def set_user_role(user_id: str, role: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET role = :role WHERE id = :id"),
                     {"role": role, "id": user_id})


def admin_reset_user_password(user_id: str, new_hash: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET password_hash = :h WHERE id = :id"),
                     {"h": new_hash, "id": user_id})


def delete_user(user_id: str):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})