"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldHalf, Send, Loader2 } from "lucide-react";
import { createChat } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";


const SUGGESTIONS = [
  "What are the key requirements of FIPS 140-3?",
  "Explain the MITRE ATT&CK technique for lateral movement",
  "What's the recommended AES key size for top secret data?",
  "Walk me through incident response steps for a phishing attack",
];

export default function ChatIndexPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [creating, setCreating] = useState(false);

  const startChat = async (initialMessage: string) => {
    if (!initialMessage.trim() || creating) return;
    setCreating(true);
    const chat = await createChat(null, initialMessage.slice(0, 60));
    // stash the first message so the chat page can send it as soon as it mounts
    sessionStorage.setItem(`pending_msg_${chat.id}`, initialMessage);
    router.push(`/chat/${chat.id}`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    startChat(text);
  };

  const firstName = user?.email?.split("@")[0];

  return (
    <div className="flex h-screen flex-col items-center justify-center bg-base px-6">
      <div className="w-full max-w-2xl">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-hairline bg-surface">
            <ShieldHalf size={22} className="text-accent" strokeWidth={2} />
          </span>
          <h1 className="font-mono text-2xl font-semibold text-text-primary">
            {firstName ? `Welcome back, ${firstName}` : "Welcome to SecOps Copilot"}
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            Grounded over NIST, CISA, MITRE ATT&CK, and FIPS references — ask anything.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex items-center gap-2 rounded-xl border border-hairline bg-surface px-4 py-3 focus-within:border-accent">
          <input
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={creating}
            placeholder="Ask about controls, vulnerabilities, incident response procedures..."
            className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={creating || !text.trim()}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-base disabled:opacity-40"
          >
            {creating ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </form>

        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => startChat(s)}
              disabled={creating}
              className="rounded-lg border border-hairline bg-elevated px-3 py-2.5 text-left text-xs text-text-muted transition-colors hover:border-accent hover:text-text-primary disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}