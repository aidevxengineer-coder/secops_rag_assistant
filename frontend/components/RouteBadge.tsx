import { Database, Search, MessageCircle, Globe } from "lucide-react";
import type { Route } from "@/lib/types";

const ROUTE_CONFIG: Record<
  Route,
  { label: string; icon: typeof Search; color: string; bg: string; border: string }
> = {
  vector_rag: {
    label: "vector search",
    icon: Search,
    color: "text-accent",
    bg: "bg-accent/10",
    border: "border-accent/30",
  },
  table_query: {
    label: "table lookup",
    icon: Database,
    color: "text-verified",
    bg: "bg-verified/10",
    border: "border-verified/30",
  },
  web_search: {
    label: "web search",
    icon: Globe,
    color: "text-warning",       // pick whatever accent you use for "live/external" data
    bg: "bg-warning/10",
    border: "border-warning/30",
  },
  none: {
    label: "direct",
    icon: MessageCircle,
    color: "text-text-muted",
    bg: "bg-elevated",
    border: "border-hairline",
  },
};

export default function RouteBadge({ route }: { route: Route }) {
  const config = ROUTE_CONFIG[route];
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-mono uppercase tracking-wide ${config.color} ${config.bg} ${config.border}`}
    >
      <Icon size={11} strokeWidth={2.5} />
      {config.label}
    </span>
  );
}