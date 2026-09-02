"""
Chroma persistent vector store. Uses local sentence-transformers embeddings
(no API cost, no rate limits) — swap EMBEDDING_MODEL in config if you want
an API-based embedder later (OpenAI/Cohere).
"""

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from .config import Config

_embeddings = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=Config.EMBEDDING_MODEL)
    return _embeddings


def get_vector_store(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=Config.CHROMA_PERSIST_DIR,
        collection_metadata={"hnsw:space": "cosine"},
    )


def add_documents(chunks: list[Document], collection_name: str):
    store = get_vector_store(collection_name)
    ids = [c.metadata["chunk_id"] for c in chunks]
    store.add_documents(documents=chunks, ids=ids)
    return store


def list_sources(collection_name: str) -> list[str]:
    """Distinct document names available in the vector store — lets the
    orchestrator know what topics/documents actually exist."""
    store = get_vector_store(collection_name)
    raw = store.get(include=["metadatas"])
    return sorted({m["source"] for m in raw["metadatas"]}) if raw["metadatas"] else []
