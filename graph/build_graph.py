"""
Wires every node into the graph exactly per flowchart, plus the new
table-agent branch for structured/numeric queries.

Route after orchestrator:
    table_query -> table_agent -> (rows found?) -> main_llm_table -> save_memory
                                -> (no rows)     -> retry_check
    vector_rag  -> retrieve -> evaluator -> (relevant?) -> main_llm_rag -> save_memory
                                          -> (not relevant) -> retry_check
    none        -> main_llm_no_rag -> save_memory

retry_check -> (retries left?) -> query_rewriter (loop, with feedback)
                                -> safe_response -> save_memory
"""

from langgraph.graph import StateGraph, END
from .state import GraphState
from . import nodes
from ingestion.trace_store import ensure_trace_tables


def build_graph():
    ensure_trace_tables()
    graph = StateGraph(GraphState)

    graph.add_node("query_rewriter", nodes.query_rewriter_node)
    graph.add_node("orchestrator", nodes.orchestrator_node)
    graph.add_node("retrieve", nodes.retrieve_node)
    graph.add_node("evaluator", nodes.evaluator_node)
    graph.add_node("table_agent", nodes.table_agent_node)
    graph.add_node("web_search", nodes.web_search_node)          # NEW
    graph.add_node("retry_check", nodes.retry_check_node)
    graph.add_node("main_llm_rag", nodes.main_llm_rag_node)
    graph.add_node("main_llm_table", nodes.main_llm_table_node)
    graph.add_node("main_llm_no_rag", nodes.main_llm_no_rag_node)
    graph.add_node("main_llm_web", nodes.main_llm_web_node)       # NEW
    graph.add_node("safe_response", nodes.safe_response_node)
    graph.add_node("report_generator", nodes.report_generator_node)  # NEW
    graph.add_node("save_memory", nodes.save_memory_node)
    graph.add_node("summarizer", nodes.summarizer_node)

    graph.set_entry_point("query_rewriter")
    graph.add_edge("query_rewriter", "orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        nodes.route_after_orchestrator,
        {
            "table_agent": "table_agent",
            "retrieve": "retrieve",
            "web_search": "web_search",        # NEW
            "main_llm_no_rag": "main_llm_no_rag",
        },
    )

    graph.add_edge("retrieve", "evaluator")
    graph.add_edge("web_search", "evaluator")   # was: graph.add_edge("web_search", "main_llm_web")
    
    graph.add_conditional_edges(
        "evaluator",
        nodes.route_after_evaluator,
        {
            "main_llm_rag": "main_llm_rag",
            "main_llm_web": "main_llm_web",
            "retry_check": "retry_check",
        },
    )

    graph.add_conditional_edges(
        "table_agent",
        nodes.route_after_table_agent,
        {"main_llm_table": "main_llm_table", "retry_check": "retry_check"},
    )

    graph.add_conditional_edges(
        "retry_check",
        nodes.route_after_retry_check,
        {"query_rewriter": "query_rewriter", "safe_response": "safe_response"},
    )


    # every terminal answer node now funnels through this instead of a
    # direct edge to save_memory, so the PDF branch is checked once, in one place
    for node in ("main_llm_rag", "main_llm_table", "main_llm_no_rag", "main_llm_web", "safe_response"):
        graph.add_conditional_edges(
            node,
            nodes.route_after_final_response,
            {"report_generator": "report_generator", "save_memory": "save_memory"},
        )

    graph.add_edge("report_generator", "save_memory")

    graph.add_conditional_edges(
        "save_memory",
        nodes.route_after_save_memory,
        {"summarizer": "summarizer", "__end__": END},
    )

    graph.add_edge("summarizer", END)

    return graph.compile()