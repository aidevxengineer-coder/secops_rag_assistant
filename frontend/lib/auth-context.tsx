"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { setCurrentAccessToken } from "./api-client";

interface User {
  id: string;
  email: string;
  role: "user" | "admin";
}

interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setAccessToken: (token: string | null) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8088";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async (token: string) => {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("failed to fetch user");
    return res.json();
  }, []);

  // On mount: try silent refresh using the httpOnly cookie — this is what
  // keeps the user logged in across a page reload without storing the
  // access token anywhere persistent.
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" });
        if (res.ok) {
          const { access_token } = await res.json();
          setCurrentAccessToken(access_token);
          setAccessToken(access_token);
          const me = await fetchMe(access_token);
          setUser(me);
        }
      } catch {
        // no valid session — fine, user stays logged out
      } finally {
        setLoading(false);
      }
    })();
  }, [fetchMe]);

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include", // lets the browser store the httpOnly refresh cookie
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const { access_token } = await res.json();
    setCurrentAccessToken(access_token); // set it immediately, synchronously
    setAccessToken(access_token);
    setUser(await fetchMe(access_token));
  };

  const register = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed");
    }
    await login(email, password); // auto-login after successful registration
  };

  const logout = async () => {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
    setAccessToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, accessToken, loading, login, register, logout, setAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}