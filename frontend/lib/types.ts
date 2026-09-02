export type Route = "vector_rag" | "table_query" | "web_search" | "none";

export interface Source {
  source: string;
  page: number;
  block_type: string;
  content: string;
  similarity_score?: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  route?: Route;
  sources?: Source[];
  sql?: string;
  timestamp: number;
  reportUrl?: string;    // NEW
  reportFilename?: string; // NEW
}

export interface ChatResponse {
  response: string;
  route: Route;
  sources: Source[];
  sql?: string;
  session_id: string;
  reportUrl?: string;
  reportFilename?: string;
  trace_id: string;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
}

export interface ChatSummary {
  id: string;
  project_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  role: "user" | "admin";
  is_verified: boolean;
  is_active: boolean;
  created_at: string;
}

export interface LatencyStat {
  node_name: string;
  call_count: number;
  p50: number;
  p95: number;
  avg_ms: number;
}

export interface FailureStat {
  node_name: string;
  failures: number;
  total_attempts: number;
  failure_pct: number;
}

export interface CostStat {
  model: string;
  total_input_tokens: number;
  total_output_tokens: number;
  successful_calls: number;
  estimated_cost_usd: number;
}

export interface ActivityStat {
  day: string;
  message_count: number;
}

export interface WallLatencyStat {
  node_name: string;
  call_count: number;
  p50: number;
  p95: number;
  avg_ms: number;
  max_ms: number;
}