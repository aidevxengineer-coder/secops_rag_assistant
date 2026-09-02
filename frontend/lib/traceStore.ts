import { create } from "zustand";

export interface TraceEvent {
  event: string;
  node?: string;
  duration_ms?: number;
  payload?: Record<string, unknown>;
  text?: string; // present on "answer_token" events
  url?: string; 
  filename?: string; 
}

export interface LlmCallEvent {
  event: "llm_call";
  node: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
}

interface TraceState {
  events: TraceEvent[];
  llmCalls: LlmCallEvent[];
  reportReady: { url: string; filename: string } | null;
  addEvent: (e: TraceEvent) => void;
  addLlmCall: (e: LlmCallEvent) => void;
  setReportReady: (r: { url: string; filename: string }) => void; // NEW
  reset: () => void;
}

export const useTraceStore = create<TraceState>((set) => ({
  events: [],
  llmCalls: [],
  reportReady: null,
  addEvent: (e) => set((state) => ({ events: [...state.events, e] })),
  addLlmCall: (e) => set((state) => ({ llmCalls: [...state.llmCalls, e] })),
  setReportReady: (r) => set({ reportReady: r }), 
  reset: () => set({ events: [], llmCalls: [], reportReady: null }),
}));

const STEP_LABELS: Record<string, string> = {
  query_rewriter: "Refining your question",
  orchestrator: "Deciding how to answer",
  retrieve: "Searching the knowledge base",
  evaluator: "Checking result relevance",
  table_agent: "Querying structured data",
  table_agent_sql_gen: "Writing SQL query",
  web_search: "Searching the web",
  main_llm_rag: "Drafting an answer",
  main_llm_table: "Drafting an answer",
  main_llm_web: "Drafting an answer",
  main_llm_no_rag: "Drafting an answer",
  retry_check: "Refining the search",
  summarizer: "Summarizing conversation history",
  report_generator: "Generating PDF report",
  safe_response: "Preparing response",
};


// Derived: joins all answer_token events into the live-streaming answer text
export function useStreamedAnswer(): string {
  return useTraceStore((s) =>
    s.events.filter((e) => e.event === "answer_token").map((e) => e.text).join("")
  );
}

// Derived: the most recent node event, translated into a user-facing label
export function useCurrentStep(): string | null {
  return useTraceStore((s) => {
    const withNode = s.events.filter((e) => e.node && e.event !== "answer_token");
    if (withNode.length === 0) return null;
    const last = withNode[withNode.length - 1];
    return STEP_LABELS[last.node as string] || (last.node as string).replace(/_/g, " ");
  });
}