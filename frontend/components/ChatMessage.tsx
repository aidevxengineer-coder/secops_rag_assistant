"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { FileSearch, ShieldHalf, User, Check, Copy, FileDown } from "lucide-react";
import RouteBadge from "./RouteBadge";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function ChatMessage({
  message,
  onShowEvidence,
}: {
  message: ChatMessageType;
  onShowEvidence: () => void;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const reportHref = message.reportUrl
    ? message.reportUrl.startsWith("http")
      ? message.reportUrl
      : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8088"}${message.reportUrl}`
    : null;

  return (
    <div className={clsx("group flex animate-rise-in items-start gap-2.5", isUser && "justify-end")}>
      {!isUser && (
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-hairline bg-surface">
          <ShieldHalf size={13} className="text-accent" strokeWidth={2} />
        </span>
      )}

      <div className={clsx("max-w-[75%] break-words overflow-hidden", isUser && "flex flex-col items-end")}>
        {!isUser && message.route && (
          <div className="mb-1.5">
            <RouteBadge route={message.route} />
          </div>
        )}

        <div
          className={clsx(
            "rounded-lg px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-accent text-base"
              : "border border-hairline bg-surface text-text-primary"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none break-words prose-p:my-2 prose-headings:mt-3 prose-headings:mb-1.5 prose-ul:my-2 prose-li:my-0.5 prose-pre:bg-elevated prose-pre:border prose-pre:border-hairline prose-code:text-accent prose-code:before:content-none prose-code:after:content-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children, ...props }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
                      {...props}
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        <div className="mt-1.5 flex items-center gap-3 px-1">
          <span className="font-mono text-[10px] text-text-muted opacity-0 transition-opacity group-hover:opacity-100">
            {formatTime(message.timestamp)}
          </span>

          {!isUser && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 font-mono text-[11px] text-text-muted opacity-0 transition-opacity hover:text-accent group-hover:opacity-100"
            >
              {copied ? <Check size={11} /> : <Copy size={11} />}
              {copied ? "copied" : "copy"}
            </button>
          )}

          {!isUser && message.sources && message.sources.length > 0 && (
            <button
              onClick={onShowEvidence}
              className="flex items-center gap-1.5 font-mono text-[11px] text-text-muted hover:text-accent"
            >
              <FileSearch size={12} />
              {message.sources.length} source{message.sources.length !== 1 ? "s" : ""}
            </button>
          )}

          {!isUser && reportHref && (
            <a
              href={reportHref}
              download
              className="flex items-center gap-1.5 font-mono text-[11px] text-verified hover:brightness-125"
            >
              <FileDown size={12} />
              report.pdf
            </a>
          )}
        </div>
      </div>

      {isUser && (
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-hairline bg-elevated">
          <User size={13} className="text-text-muted" strokeWidth={2} />
        </span>
      )}
    </div>
  );
}