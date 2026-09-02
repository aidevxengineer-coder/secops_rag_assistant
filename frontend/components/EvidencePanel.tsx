"use client";

import { useState } from "react";
import { X, FileText, Table2, Copy, Check } from "lucide-react";
import type { Source } from "@/lib/types";

export default function EvidencePanel({
  sources,
  sql,
  onClose,
}: {
  sources: Source[];
  sql?: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopySql = async () => {
    if (!sql) return;
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <aside className="animate-slide-in-right flex h-full w-[360px] shrink-0 flex-col border-l border-hairline bg-surface shadow-panel">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <h2 className="font-mono text-xs uppercase tracking-wide text-text-muted">
          Evidence trail
        </h2>
        <button
          onClick={onClose}
          className="rounded p-1 text-text-muted transition-colors hover:bg-elevated hover:text-text-primary"
          aria-label="Close evidence panel"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {sql && (
          <div className="mb-4">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-wide text-text-muted">
                SQL executed
              </span>
              <button
                onClick={handleCopySql}
                className="flex items-center gap-1 font-mono text-[10px] text-text-muted hover:text-accent"
              >
                {copied ? <Check size={11} /> : <Copy size={11} />}
                {copied ? "copied" : "copy"}
              </button>
            </div>
            <pre className="overflow-x-auto rounded-lg border border-hairline bg-elevated p-3 font-mono text-xs text-accent">
              {sql}
            </pre>
          </div>
        )}

        {sources.length === 0 && !sql && (
          <p className="text-sm text-text-muted">No sources for this answer.</p>
        )}

        <div className="space-y-3">
          {sources.map((s, i) => (
            <div
              key={i}
              className="rounded-lg border border-hairline bg-elevated p-3 transition-colors hover:border-accent-dim"
            >
              <div className="mb-2 flex items-center gap-2 font-mono text-[11px] text-text-muted">
                {s.block_type === "table" ? <Table2 size={12} /> : <FileText size={12} />}
                <span className="truncate">{s.source}</span>
                <span className="ml-auto shrink-0">p.{s.page}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-primary/90">
                {s.content}
              </p>
              {s.similarity_score != null && (
              <div className="mt-2 flex items-center gap-1.5 font-mono text-[10px] text-text-muted">
                <span className="h-1 w-1 rounded-full bg-verified" />
                similarity: {s.similarity_score.toFixed(3)}
              </div>
)}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
