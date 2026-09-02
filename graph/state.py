"""
Shared state passed between every node in the graph. Maps directly to the
fields your flowchart's boxes read from / write to.
"""

from typing import TypedDict, Optional
from langchain_core.documents import Document


class GraphState(TypedDict, total=False):
    trace_id: str
    # --- query handling ---
    original_query: str
    rewritten_query: str
    conversation_history: list[dict]  # [{"role": "user"/"assistant", "content": "..."}]

    # --- orchestrator routing ---
    route: str  # "table_query" | "vector_rag" | "web_search" | "none"
    web_search_results: Optional[str] 

    # --- retrieval ---
    collection_name: str
    retrieved_docs: list[Document]

    # --- table agent ---
    table_rows: list[dict]
    table_sql: str

    # --- relevance evaluator + retry loop ---
    is_relevant: bool
    evaluator_feedback: str
    retry_count: int
    max_retries: int
    history_summary: str

    # --- pdf report generation ---
    wants_pdf_report: bool  # set by API layer, e.g. request body has format="pdf"
    report_path: Optional[str]
    report_url: Optional[str]

    # --- final output ---
    final_response: str
