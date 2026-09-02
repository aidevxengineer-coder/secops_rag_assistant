"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await register(email, password);
      router.push("/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-base">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 rounded-lg border border-hairline bg-surface p-6">
        <h1 className="font-mono text-lg text-text-primary">Create account</h1>
        {error && <p className="rounded border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">{error}</p>}
        <input
          type="email" required placeholder="Email" value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded border border-hairline bg-elevated px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
        />
        <input
          type="password" required placeholder="Password (min 8 characters)" value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded border border-hairline bg-elevated px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
        />
        <button type="submit" disabled={loading} className="w-full rounded bg-accent py-2 text-sm font-medium text-base disabled:opacity-50">
          {loading ? "Creating account..." : "Create account"}
        </button>
        <p className="text-center text-xs text-text-muted">
          Already have an account? <Link href="/login" className="hover:text-accent">Sign in</Link>
        </p>
      </form>
    </div>
  );
}