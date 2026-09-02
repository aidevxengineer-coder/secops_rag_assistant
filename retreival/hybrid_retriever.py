from .vector_retriever import vector_search
from .keyword_retriever import keyword_search
from .rrf_fusion import reciprocal_rank_fusion
from ingestion.latency_logger import timed_stage


def hybrid_retrieve(
    query: str,
    collection_name: str,
    doc_id: str = "query",
    k: int = 10,
    similarity_threshold: float = 0.35,
    top_n: int = 10,
):
    vector_results = vector_search(
        query, collection_name, doc_id, k=k, similarity_threshold=similarity_threshold
    )
    keyword_results = keyword_search(query, collection_name, doc_id, k=k)

    with timed_stage(
        "rrf_rerank",
        doc_id,
        meta={
            "vector_count": len(vector_results),
            "keyword_count": len(keyword_results),
        },
    ):
        fused = reciprocal_rank_fusion([vector_results, keyword_results], top_n=top_n)

    return fused
