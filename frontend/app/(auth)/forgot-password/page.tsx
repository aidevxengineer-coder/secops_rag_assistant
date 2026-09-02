"use client";

import { useState } from "react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8088";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await fetch(`${API_BASE}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    setLoading(false);
    setSent(true); // always show success — backend never reveals if the email exists
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-base">
      <div className="w-full max-w-sm space-y-4 rounded-lg border border-hairline bg-surface p-6">
        <h1 className="font-mono text-lg text-text-primary">Reset password</h1>
        {sent ? (
          <p className="text-sm text-text-muted">If that email exists, a reset link has been sent. Check your inbox.</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="email" required placeholder="Email" value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-hairline bg-elevated px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
            />
            <button type="submit" disabled={loading} className="w-full rounded bg-accent py-2 text-sm font-medium text-base disabled:opacity-50">
              {loading ? "Sending..." : "Send reset link"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}