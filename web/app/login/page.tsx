"use client";
/**
 * §3 Screen 1 — Login
 * Wires to POST /api/v1/auth/login.
 * senior_lmo/admin → dashboard (/).
 * field_lmo → rejected with explicit message (not a generic 403).
 */
import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { apiErrorMessage } from "@/lib/errors";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { ShieldCheck } from "lucide-react";

function LoginForm() {
  const { login, user, isDashboardRole } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const rejected = params.get("rejected") === "1";
  const expired = params.get("expired") === "1";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    rejected
      ? "Dashboard access requires Senior LMO or Admin role. Field LMO accounts are mobile-only."
      : expired
      ? "Your session has ended. Sign in again to continue."
      : null
  );
  const [loading, setLoading] = useState(false);

  // Already authenticated → redirect
  useEffect(() => {
    if (user && isDashboardRole) router.replace("/");
  }, [user, isDashboardRole, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      router.push("/");
    } catch (err: unknown) {
      if (err instanceof Error && err.message === "FIELD_LMO_REJECTED") {
        setError(
          "Dashboard access requires Senior LMO or Admin role. " +
          "Field LMO accounts are mobile-only — use the MetrologyAI mobile app."
        );
      } else {
        setError(apiErrorMessage(err, "Sign-in failed. Check your username and password."));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper-100 flex flex-col items-center justify-center px-4">
      {/* Header block */}
      <div className="w-full max-w-md mb-8 text-center">
        <div className="flex justify-center mb-4">
          <ShieldCheck size={40} strokeWidth={1.5} className="text-brass-500" aria-hidden />
        </div>
        <h1 className="font-display text-2xl font-bold text-ink-900 mb-1">
          MetrologyAI
        </h1>
        <p className="font-body text-sm text-ink-600">
          Legal Metrology Enforcement Dashboard
        </p>
        <p className="font-body text-xs text-ink-600 mt-1 opacity-70">
          Ministry of Consumer Affairs, Food & Public Distribution
        </p>
      </div>

      {/* Login card */}
      <div className="w-full max-w-md">
        <div className="card-surface">
          <CalibrationRuler className="mb-6 -mx-4 -mt-4" />

          <h2 className="font-display text-lg font-bold text-ink-900 mb-6 px-0">
            Sign in to Dashboard
          </h2>

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            <div>
              <label htmlFor="username" className="form-label">
                LMO ID / Username / Email
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={`form-input ${error && !loading ? "form-input-error" : ""}`}
                placeholder="Enter your LMO credential"
                aria-describedby={error ? "login-error" : undefined}
              />
            </div>

            <div>
              <label htmlFor="password" className="form-label">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`form-input ${error && !loading ? "form-input-error" : ""}`}
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div
                id="login-error"
                role="alert"
                className="rounded-[4px] p-3 text-sm font-body"
                style={{
                  backgroundColor: "rgba(179,38,30,0.08)",
                  border: "1px solid rgba(179,38,30,0.3)",
                  color: "#B3261E",
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="btn-primary w-full"
            >
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>

          <CalibrationRuler className="mt-6 -mx-4 -mb-4" />
        </div>

        <p className="mt-4 text-center font-body text-xs text-ink-600">
          Field LMO? Use the{" "}
          <span className="text-brass-500 font-semibold">MetrologyAI Mobile App</span>
          {" "}for field captures.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-paper-100 flex items-center justify-center">
          <span className="font-mono text-sm text-ink-600">Preparing secure login...</span>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
