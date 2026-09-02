"use client";

import { useRef, useState, KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";

export default function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resize = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-hairline bg-surface px-4 py-3">
      <div className="flex items-end gap-2 rounded-lg border border-hairline bg-elevated px-3 py-2 transition-shadow focus-within:border-accent focus-within:shadow-accent-glow">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            resize(e.target);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask about incident response, ATT&CK mappings, control IDs, key sizes..."
          rows={1}
          disabled={disabled}
          className="max-h-40 flex-1 resize-none bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent text-base transition-all hover:brightness-110 disabled:opacity-30 disabled:hover:brightness-100"
          aria-label="Send message"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
      <p className="mt-1.5 px-1 font-mono text-[10px] text-text-muted">
        Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
