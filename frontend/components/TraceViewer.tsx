import { useTraceStore } from "@/lib/traceStore";

export default function TraceViewer({ onClose }: { onClose: () => void }) {
  const events = useTraceStore((s) => s.events);
  const llmCalls = useTraceStore((s) => s.llmCalls);

  return (
    <aside className="flex h-full w-[380px] shrink-0 flex-col border-l border-hairline bg-surface">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <h2 className="font-mono text-xs uppercase tracking-wide text-text-muted">Live Trace</h2>
        <button onClick={onClose} className="text-text-muted hover:text-text-primary">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <h3 className="mb-2 font-mono text-[11px] uppercase text-text-muted">Events</h3>
        <div className="mb-6 space-y-2">
          {events.filter((e) => e.event !== "answer_token").map((e, i) => (
            <div key={i} className="rounded border border-hairline bg-elevated p-2 font-mono text-[11px]">
              <span className="text-accent">{e.node || e.event}</span>
              {e.duration_ms !== undefined && <span className="text-text-muted"> · {e.duration_ms}ms</span>}
              {e.payload && <pre className="mt-1 whitespace-pre-wrap text-text-muted">{JSON.stringify(e.payload)}</pre>}
            </div>
          ))}
        </div>

        <h3 className="mb-2 font-mono text-[11px] uppercase text-text-muted">LLM Calls</h3>
        <div className="space-y-2">
          {llmCalls.map((c, i) => (
            <div key={i} className="rounded border border-hairline bg-elevated p-2 font-mono text-[11px]">
              <div className="text-verified">{c.node}</div>
              <div className="text-text-muted">
                {c.prompt_tokens}+{c.completion_tokens}={c.total_tokens} tokens · {c.latency_ms}ms
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}