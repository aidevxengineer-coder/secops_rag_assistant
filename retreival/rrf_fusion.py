def reciprocal_rank_fusion(ranked_lists: list[list], k: int = 60, top_n: int = 10):
    """RRF: score = sum(1 / (k + rank)) across all ranked lists a doc appears in."""
    scores, doc_lookup = {}, {}
    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list):
            cid = doc.metadata["chunk_id"]
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
            doc_lookup[cid] = doc

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [doc_lookup[cid] for cid, _ in fused]
