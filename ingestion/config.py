"""
Central config. All secrets/paths come from env vars — never hardcode keys.
"""

import os
from dotenv import load_dotenv
# ingestion/config.py
from pathlib import Path

load_dotenv()


class Config:
    MAX_RETRIES = 3
    MAX_HISTORY_MESSAGES = 10

    REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/api/generated_reports"))
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8088")

    # --- API keys (never hardcode, always env) ---
    GROQ_API_KEY_1 = os.getenv("GROQ_API_KEY_1")
    GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2")
    GROQ_API_KEY_3 = os.getenv("GROQ_API_KEY_3")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # user authentication / JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "SecOps Copilot")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # --- Generation model (Groq-hosted, for text generation) ---
    GENERATION_MODEL = os.getenv("GENERATION_MODEL", "gemini-3.5-flash-lite")
    GENERATION_MODEL_2 = os.getenv("GENERATION_MODEL_2", "gemini-3.1-flash-lite")
    GENERATION_MODEL_3 = os.getenv("GENERATION_MODEL_3", "gemini-2.5-flash")

    # --- Embeddings (local, free, no API cost) ---
    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # --- Chunking ---
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 120))
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://user:pass@localhost:5432/secops_tables"
    )
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # --- Storage paths ---
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    IMAGE_DIR = os.path.join(BASE_DIR, "data", "images")
    CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    LATENCY_LOG_PATH = os.path.join(LOG_DIR, "latency.jsonl")

    @classmethod
    def validate(cls):
        missing = []
        if not (cls.GROQ_API_KEY_1 or cls.GROQ_API_KEY_2 or cls.GROQ_API_KEY_3 or cls.GEMINI_API_KEY):
            missing.append("GROQ_API_KEY_1/2/3 or GEMINI_API_KEY")
        if not cls.TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY")
        if not cls.DATABASE_URL:
            missing.append("DATABASE_URL")
        if missing:
            raise EnvironmentError(
                f"Missing required env vars: {missing}. Copy .env.example to .env and fill in."
            )
