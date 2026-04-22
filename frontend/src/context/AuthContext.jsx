import { createContext, useContext, useState, useCallback } from "react";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("hireai_token"));
  const [user, setUser] = useState(() => {
    try {
      const u = localStorage.getItem("hireai_user");
      return u ? JSON.parse(u) : null;
    } catch {
      return null;
    }
  });

  const login = useCallback((accessToken, userData) => {
    setToken(accessToken);
    setUser(userData);
    localStorage.setItem("hireai_token", accessToken);
    localStorage.setItem("hireai_user", JSON.stringify(userData));
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("hireai_token");
    localStorage.removeItem("hireai_user");
  }, []);

  const updateUser = useCallback((userData) => {
    setUser(userData);
    localStorage.setItem("hireai_user", JSON.stringify(userData));
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
