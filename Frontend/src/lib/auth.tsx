import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { apiRequest, tokenStore } from "./api";
import type { AuthTokens, User } from "./types";

export type DisplayUser = User & { full_name: string };

interface AuthContextValue {
  user: DisplayUser | null;
  isAuthenticated: boolean;
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    full_name: string;
    company: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const USER_KEY = "hireai.user";

function withDisplayName(user: User): DisplayUser {
  const full_name =
    `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || user.username || user.email;
  return { ...user, full_name };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DisplayUser | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(USER_KEY);
    if (stored && tokenStore.access) {
      try {
        setUser(JSON.parse(stored) as DisplayUser);
      } catch {
              }
    }
    setIsReady(true);
  }, []);

  const persist = useCallback((next: User) => {
    const display = withDisplayName(next);
    window.localStorage.setItem(USER_KEY, JSON.stringify(display));
    setUser(display);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await apiRequest<AuthTokens & { user: User }>("/api/auth/login", {
        body: { email, password },
      });
      tokenStore.set(result);
      persist(result.user);
    },
    [persist],
  );

  const register = useCallback(
    async (input: { email: string; password: string; full_name: string; company: string }) => {
      const result = await apiRequest<AuthTokens & { user: User }>("/api/auth/register", {
        body: input,
      });
      tokenStore.set(result);
      persist(result.user);
    },
    [persist],
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    window.localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: !!user, isReady, login, register, logout }),
    [user, isReady, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
