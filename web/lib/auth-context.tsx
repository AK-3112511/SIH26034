"use client";
/**
 * Auth context — provides current user + login/logout across the app.
 * Stored in localStorage; hydrated on mount.
 */
import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, type UserResponse } from "@/lib/api";

interface AuthContextValue {
  user: UserResponse | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** true only for roles allowed on the dashboard */
  isDashboardRole: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem("metrologyai_token");
    const storedUser = localStorage.getItem("metrologyai_user");
    if (storedToken && storedUser) {
      try {
        const parsed: UserResponse = JSON.parse(storedUser);
        if (parsed.role === "field_lmo") {
          // Reject field_lmo tokens from dashboard access
          localStorage.removeItem("metrologyai_token");
          localStorage.removeItem("metrologyai_user");
          setToken(null);
          setUser(null);
        } else {
          setToken(storedToken);
          setUser(parsed);
        }
      } catch {
        // corrupt — clear
        localStorage.removeItem("metrologyai_token");
        localStorage.removeItem("metrologyai_user");
      }
    }
    setLoading(false);
  }, []);

  const login = async (username: string, password: string) => {
    const { data } = await authApi.login(username, password);
    // Reject field_lmo role — dashboard is senior_lmo / admin only
    if (data.user.role === "field_lmo") {
      localStorage.removeItem("metrologyai_token");
      localStorage.removeItem("metrologyai_user");
      setToken(null);
      setUser(null);
      throw new Error("FIELD_LMO_REJECTED");
    }
    localStorage.setItem("metrologyai_token", data.access_token);
    localStorage.setItem("metrologyai_user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
  };

  const logout = () => {
    localStorage.removeItem("metrologyai_token");
    localStorage.removeItem("metrologyai_user");
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  const isDashboardRole = user?.role === "senior_lmo" || user?.role === "admin";

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, isDashboardRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
