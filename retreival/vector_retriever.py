from ingestion.vector_store import get_vector_store
from ingestion.latency_logger import timed_stage


def vector_search(
    query: str,
    collection_name: str,
    doc_id: str = "query",
    k: int = 10,
    similarity_threshold: float = 0.35,
):
    store = get_vector_store(collection_name)
    with timed_stage("vector_search", doc_id, meta={"k": k}):
        results = store.similarity_search_with_score(query, k=k)

    filtered = []
    for doc, distance in results:
        similarity = 1 - distance  # cosine space
        if similarity >= similarity_threshold:
            doc.metadata["similarity_score"] = round(similarity, 4)
            filtered.append(doc)
    return filtered
