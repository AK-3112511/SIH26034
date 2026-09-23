"use client";
/**
 * Auth context — the current officer, and the rules about when their session
 * stops being valid.
 *
 * Previously the session was whatever localStorage happened to contain. A
 * token that had expired hours earlier still rendered the full dashboard, and
 * the officer only discovered otherwise when an action failed — after they had
 * typed a reviewer note. Two things fix that: the token's own `exp` claim is
 * read on hydration and enforced with a timer, and the stored profile is
 * revalidated against `/auth/me` so a revoked or downgraded account cannot
 * keep working from cached JSON.
 */
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, type UserResponse } from "@/lib/api";

const TOKEN_KEY = "metrologyai_token";
const USER_KEY = "metrologyai_user";

interface AuthContextValue {
  user: UserResponse | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: (reason?: "expired") => void;
  /** true only for roles allowed on the dashboard */
  isDashboardRole: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Seconds-since-epoch expiry from a JWT, or null if the token is unreadable.
 *
 * This is a display/UX decision only — the backend is the authority on whether
 * a token is valid. We never trust the payload for anything but "should we
 * stop showing this officer a dashboard they can no longer use".
 */
export function readTokenExpiry(token: string): number | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof payload.exp === "number" && Number.isFinite(payload.exp) ? payload.exp : null;
  } catch {
    return null;
  }
}

/** True when the token carries an expiry that has already passed. */
export function isTokenExpired(token: string, nowMs: number = Date.now()): boolean {
  const exp = readTokenExpiry(token);
  if (exp === null) return false; // unreadable: let the server decide
  return exp * 1000 <= nowMs;
}

function clearStorage() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const expiryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const logout = useCallback(
    (reason?: "expired") => {
      clearStorage();
      setToken(null);
      setUser(null);
      router.push(reason === "expired" ? "/login?expired=1" : "/login");
    },
    [router]
  );

  // Hydrate from localStorage, then confirm with the server.
  useEffect(() => {
    let cancelled = false;

    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);

    if (!storedToken || !storedUser) {
      clearStorage();
      setLoading(false);
      return;
    }

    if (isTokenExpired(storedToken)) {
      clearStorage();
      setLoading(false);
      return;
    }

    let parsed: UserResponse;
    try {
      parsed = JSON.parse(storedUser) as UserResponse;
    } catch {
      clearStorage();
      setLoading(false);
      return;
    }

    // Field officers use the handset, not the dashboard.
    if (parsed.role === "field_lmo") {
      clearStorage();
      setLoading(false);
      return;
    }

    // Show the cached profile immediately so the shell does not flash, then
    // replace it with the server's copy — a role change or a deactivation made
    // on the Users screen must reach an already-open tab.
    setToken(storedToken);
    setUser(parsed);

    authApi
      .me()
      .then(({ data }) => {
        if (cancelled) return;
        if (data.role === "field_lmo" || !data.is_active) {
          clearStorage();
          setToken(null);
          setUser(null);
          return;
        }
        localStorage.setItem(USER_KEY, JSON.stringify(data));
        setUser(data);
      })
      .catch(() => {
        // A 401 is already handled by the axios interceptor. Anything else
        // (backend restarting, network blip) leaves the cached session in
        // place rather than throwing the officer out mid-review.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Sign out the moment the token expires, rather than on the next failed
  // request — the officer finds out before they have typed anything.
  useEffect(() => {
    if (expiryTimer.current) clearTimeout(expiryTimer.current);
    if (!token) return;

    const exp = readTokenExpiry(token);
    if (exp === null) return;

    const msRemaining = exp * 1000 - Date.now();
    if (msRemaining <= 0) {
      logout("expired");
      return;
    }

    // setTimeout saturates above ~24.8 days; sessions are far shorter, but
    // clamp so a malformed far-future exp cannot fire immediately.
    expiryTimer.current = setTimeout(() => logout("expired"), Math.min(msRemaining, 2_147_483_647));

    return () => {
      if (expiryTimer.current) clearTimeout(expiryTimer.current);
    };
  }, [token, logout]);

  const login = async (username: string, password: string) => {
    const { data } = await authApi.login(username, password);
    if (data.user.role === "field_lmo") {
      clearStorage();
      setToken(null);
      setUser(null);
      throw new Error("FIELD_LMO_REJECTED");
    }
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
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
