from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from ingestion.vector_store import get_vector_store
from ingestion.latency_logger import timed_stage


def keyword_search(
    query: str, collection_name: str, doc_id: str = "query", k: int = 10
):
    store = get_vector_store(collection_name)
    with timed_stage("keyword_search", doc_id, meta={"k": k}):
        raw = store.get(include=["documents", "metadatas"])
        tokenized = [d.lower().split() for d in raw["documents"]]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(query.lower().split())

        ranked = sorted(
            zip(raw["ids"], raw["documents"], raw["metadatas"], scores),
            key=lambda x: x[3],
            reverse=True,
        )[:k]

    results = []
    for _id, content, meta, score in ranked:
        m = dict(meta)
        m["bm25_score"] = round(float(score), 4)
        results.append(Document(page_content=content, metadata=m))
    return results
