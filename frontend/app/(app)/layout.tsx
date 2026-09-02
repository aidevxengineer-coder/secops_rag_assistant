// app/(app)/layout.tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { registerTokenHandlers } from "@/lib/api-client";
import { initSocket, onSocketMessage } from "@/lib/websocket";
import { useTraceStore } from "@/lib/traceStore";
import Sidebar from "@/components/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, accessToken, loading, setAccessToken } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [loading, user, router]);

  useEffect(() => {
    registerTokenHandlers(() => accessToken, setAccessToken);
  }, [accessToken, setAccessToken]);

  useEffect(() => {
    if (!user) return;
    initSocket(user.id);
    const unsubscribe = onSocketMessage((data) => {
      if (data._channel === "llm_calls") {
        useTraceStore.getState().addLlmCall(data);
      } else if (data.event === "report_ready") {
        useTraceStore.getState().setReportReady({ url: data.url, filename: data.filename });
      } else {
        useTraceStore.getState().addEvent(data);
      }
    });
    return unsubscribe;
  }, [user]);

  if (loading) return <div className="flex min-h-screen items-center justify-center bg-base text-text-muted">Loading...</div>;
  if (!user) return null;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 overflow-hidden">{children}</div>
    </div>
  );
}