"use client";
import { ShieldAlert } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { useAuth } from "@/lib/auth-context";

/**
 * Renders its children only for administrators.
 *
 * The three admin pages each carried their own copy of this check. All three
 * redirected a senior officer to the overview with no explanation, which reads
 * as a broken link rather than as a permission boundary; the refusal is now
 * stated, inside the normal navigation so the officer can go elsewhere.
 */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper-100">
        <span className="font-mono text-sm text-ink-600">Verifying credentials…</span>
      </div>
    );
  }

  if (user?.role !== "admin") {
    return (
      <AppShell>
        <div className="card-surface flex items-start gap-3 border-verdict-pending/30 bg-verdict-pending/5">
          <ShieldAlert size={20} className="mt-0.5 shrink-0 text-verdict-pending" aria-hidden />
          <div>
            <p className="font-body text-sm font-semibold text-ink-900">
              Administrator access required
            </p>
            <p className="mt-0.5 font-body text-xs text-ink-600">
              This section manages rulesets, officer accounts and the audit record. Ask an
              administrator if you need access to it.
            </p>
          </div>
        </div>
      </AppShell>
    );
  }

  return <>{children}</>;
}
