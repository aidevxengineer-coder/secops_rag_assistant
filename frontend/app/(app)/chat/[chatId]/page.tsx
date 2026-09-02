"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { ShieldHalf, Loader2 } from "lucide-react";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import EvidencePanel from "@/components/EvidencePanel";
import TraceViewer from "@/components/TraceViewer";
import { sendMessage, getChatMessages } from "@/lib/api";
import { onSocketMessage, subscribeToTrace } from "@/lib/websocket";
import { useTraceStore, useStreamedAnswer, useCurrentStep } from "@/lib/traceStore";
import type { ChatMessage as ChatMessageType, Source } from "@/lib/types";

function makeId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

type RightPanel = { type: "evidence"; sources: Source[]; sql?: string } | { type: "trace" } | null;

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>();
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loading, setLoading] = useState(false);
  const [rightPanel, setRightPanel] = useState<RightPanel>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const streamedAnswer = useStreamedAnswer();
  const currentStep = useCurrentStep();
  const pendingHandledRef = useRef<string | null>(null);

const handleSend = useCallback(async (text: string) => {
  setError(null);
  const userMsg: ChatMessageType = {
    id: makeId(),
    role: "user",
    content: text,
    timestamp: Date.now(),
  };
  setMessages((prev) => [...prev, userMsg]);
  setLoading(true);

  const traceId = crypto.randomUUID();
  useTraceStore.getState().reset();
  subscribeToTrace(traceId);

  try {
    const result = await sendMessage(text, chatId, traceId);
    const report = useTraceStore.getState().reportReady;
    const assistantMsg: ChatMessageType = {
      id: makeId(),
      role: "assistant",
      content: result.response,
      route: result.route,
      sources: result.sources,
      sql: result.sql,
      timestamp: Date.now(),
      reportUrl: report?.url,
      reportFilename: report?.filename,
    };
    setMessages((prev) => [...prev, assistantMsg]);
  } catch (e) {
    setError(e instanceof Error ? e.message : "Something went wrong reaching the backend.");
  } finally {
    setLoading(false);
  }
}, [chatId]);

// Single source of truth for "load history OR send pending message" — no
// second effect, no race, guarded so it only ever sends once per chatId
// even under React Strict Mode's double-invoke in dev.
useEffect(() => {
  let cancelled = false;
  const pendingKey = `pending_msg_${chatId}`;
  const pending = sessionStorage.getItem(pendingKey);

  if (pending) {
    setMessages([]);
    setLoadingHistory(false);
    if (pendingHandledRef.current !== chatId) {
      pendingHandledRef.current = chatId;
      sessionStorage.removeItem(pendingKey);
      handleSend(pending);
    }
    return;
  }

  setLoadingHistory(true);
  setMessages([]);
  getChatMessages(chatId)
    .then((history) => {
      if (cancelled) return;
      setMessages(
        history.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          route: m.route,
          sql: m.sql_text,
          reportUrl: m.report_url,
          timestamp: new Date(m.created_at).getTime(),
        }))
      );
    })
    .catch(() => setError("Couldn't load this chat's history."))
    .finally(() => !cancelled && setLoadingHistory(false));

  return () => {
    cancelled = true;
  };
}, [chatId, handleSend]);

    useEffect(() => {
        useTraceStore.getState().reset();
    }, [chatId]);

  const openEvidence = (sources: Source[], sql?: string) => {
    setRightPanel({ type: "evidence", sources, sql });
  };

  const toggleTracePanel = () => {
    setRightPanel((prev) => (prev?.type === "trace" ? null : { type: "trace" }));
  };

  const closeChatView = () => {
    setRightPanel(null);
  };

  return (
    <div className="flex h-screen bg-base">
      <div className="flex flex-1 flex-col">
        <header className="flex items-center gap-2.5 border-b border-hairline px-5 py-3.5">
          <ShieldHalf size={20} className="text-accent" strokeWidth={2} />
          <div>
            <h1 className="font-mono text-sm font-semibold tracking-wide">SecOps Copilot</h1>
            <p className="text-xs text-text-muted">
              Grounded over NIST, CISA, MITRE ATT&CK, FIPS references
            </p>
          </div>

          <div className="ml-auto flex gap-2">
            <button
              onClick={closeChatView}
              className={`rounded border px-3 py-1 text-xs font-mono transition-colors ${
                rightPanel === null ? "border-accent text-accent" : "border-hairline text-text-muted hover:border-accent"
              }`}
            >
              Chat
            </button>
            <button
              onClick={toggleTracePanel}
              className={`rounded border px-3 py-1 text-xs font-mono transition-colors ${
                rightPanel?.type === "trace" ? "border-accent text-accent" : "border-hairline text-text-muted hover:border-accent"
              }`}
            >
              Live Trace
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-6">
          {loadingHistory ? (
            <div className="flex items-center justify-center pt-24 text-text-muted">
              <Loader2 size={16} className="animate-spin" />
            </div>
          ) : (
            <>
              {messages.length === 0 && !loading && (
                <div className="mx-auto mt-24 max-w-md text-center">
                  <p className="text-sm text-text-muted">
                    Ask about incident response procedures, ATT&CK technique mappings,
                    cryptographic key sizes, control IDs, or anything in the knowledge base.
                  </p>
                </div>
              )}

              <div className="mx-auto flex max-w-3xl flex-col gap-5">
                {messages.map((m) => (
                  <ChatMessage key={m.id} message={m} onShowEvidence={() => openEvidence(m.sources || [], m.sql)} />
                ))}

                {loading && (
                  <div className="flex justify-start">
                    <div className="max-w-[75%] rounded-lg border border-hairline bg-surface px-4 py-3 text-sm leading-relaxed text-text-primary">
                      {streamedAnswer ? (
                        <p className="whitespace-pre-wrap">{streamedAnswer}</p>
                      ) : (
                        <div className="flex items-center gap-2 text-text-muted">
                          <Loader2 size={14} className="animate-spin" />
                          {currentStep || "Thinking..."}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {error && (
                  <div className="rounded border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-300">{error}</div>
                )}
              </div>
              <div ref={scrollRef} />
            </>
          )}
        </div>

        <div className="mx-auto w-full max-w-3xl">
          <ChatInput onSend={handleSend} disabled={loading || loadingHistory} />
        </div>
      </div>

      {rightPanel?.type === "evidence" && (
        <EvidencePanel sources={rightPanel.sources} sql={rightPanel.sql} onClose={() => setRightPanel(null)} />
      )}
      {rightPanel?.type === "trace" && <TraceViewer onClose={() => setRightPanel(null)} />}
    </div>
  );
}