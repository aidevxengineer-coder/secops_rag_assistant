let socket: WebSocket | null = null;
let currentSessionId: string | null = null;
const listeners = new Set<(data: any) => void>();

export function initSocket(sessionId: string): WebSocket {
  // Reuse existing connection if it's for the same session and still alive
  if (
    socket &&
    currentSessionId === sessionId &&
    socket.readyState !== WebSocket.CLOSED &&
    socket.readyState !== WebSocket.CLOSING
  ) {
    return socket;
  }

  // Different session, or the old socket is dead — tear it down first
  if (socket) {
    socket.close();
  }

  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8088";
  const wsUrl = base.replace(/^https?/, "ws");

  socket = new WebSocket(`${wsUrl}/ws/${sessionId}`);
  currentSessionId = sessionId;

  socket.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data);
      listeners.forEach((cb) => cb(data));
    } catch {
      // ignore malformed frames
    }
  };

  socket.onclose = () => {
    if (currentSessionId === sessionId) {
      socket = null;
    }
  };

  return socket;
}

export function onSocketMessage(cb: (data: any) => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function subscribeToTrace(traceId: string) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "subscribe", trace_id: traceId }));
  }
}