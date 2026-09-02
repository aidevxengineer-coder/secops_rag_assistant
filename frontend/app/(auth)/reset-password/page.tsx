"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const token = useSearchParams().get("token");
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8088";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError("Missing reset token — use the link from your email.");
      return;
    }
    setLoading(true);
    setError(null);
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: password }),
    });
    setLoading(false);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      setError(err.detail || "Reset failed — the link may have expired.");
      return;
    }
    router.push("/login");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-base">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 rounded-lg border border-hairline bg-surface p-6">
        <h1 className="font-mono text-lg text-text-primary">Set new password</h1>
        {error && <p className="rounded border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">{error}</p>}
        <input
          type="password" required placeholder="New password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border border-hairline bg-elevated px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
        />
        <button type="submit" disabled={loading} className="w-full rounded bg-accent py-2 text-sm font-medium text-base disabled:opacity-50">
          {loading ? "Updating..." : "Update password"}
        </button>
      </form>
    </div>
  );
}