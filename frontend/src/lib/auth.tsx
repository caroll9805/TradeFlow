import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, tokens } from "./api";
import type { User } from "./types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (body: Record<string, unknown>) => Promise<User>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  can: (perm: string) => boolean;
}

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(!!tokens.access);
  const qc = useQueryClient();

  const refreshMe = useCallback(async () => {
    if (!tokens.access) { setUser(null); setLoading(false); return; }
    try { setUser(await api.get<User>("/auth/me")); } catch { tokens.clear(); setUser(null); } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refreshMe(); }, [refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    const t = await api.post<{ access_token: string; refresh_token: string }>("/auth/login", { email, password });
    tokens.set(t.access_token, t.refresh_token);
    const me = await api.get<User>("/auth/me");
    setUser(me);
    qc.clear();
    return me;
  }, [qc]);

  const register = useCallback(async (body: Record<string, unknown>) => {
    const t = await api.post<{ access_token: string; refresh_token: string }>("/auth/register", body);
    tokens.set(t.access_token, t.refresh_token);
    const me = await api.get<User>("/auth/me");
    setUser(me);
    qc.clear();
    return me;
  }, [qc]);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* token may already be invalid */ }
    tokens.clear();
    setUser(null);
    qc.clear();
  }, [qc]);

  const value = useMemo<AuthCtx>(() => ({
    user, loading, login, register, logout, refreshMe,
    can: (p: string) => !!user?.permissions.includes(p),
  }), [user, loading, login, register, logout, refreshMe]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(AuthContext);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}
