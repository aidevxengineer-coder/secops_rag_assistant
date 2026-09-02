const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8088";

let currentAccessToken: string | null = null;
let onTokenRefreshed: ((token: string) => void) | null = null;

export function registerTokenHandlers(getToken: () => string | null, setToken: (t: string) => void) {
  currentAccessToken = getToken();
  onTokenRefreshed = setToken;
}

export function setCurrentAccessToken(token: string | null) {
  currentAccessToken = token;
}

async function refreshAccessToken(): Promise<string | null> {
  const res = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" });
  if (!res.ok) return null;
  const { access_token } = await res.json();
  currentAccessToken = access_token;
  onTokenRefreshed?.(access_token);
  return access_token;
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const doFetch = (token: string | null) =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.body && !(options.headers as any)?.["Content-Type"] ? { "Content-Type": "application/json" } : {}),
      },
    });

  let res = await doFetch(currentAccessToken);

  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (!newToken) {
      window.location.href = "/login";
      throw new Error("Session expired");
    }
    res = await doFetch(newToken);
  }

  return res;
}