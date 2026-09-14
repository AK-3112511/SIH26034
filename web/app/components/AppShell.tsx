"use client";
/**
 * AppShell — authenticated layout wrapper.
 * Renders the full nav header per §4.2's layout sketch and guards routes:
 *   - Unauthenticated → /login
 *   - field_lmo → /login?rejected=1
 * Nav items are role-aware (Admin-only items hidden for senior_lmo).
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { LogOut, User } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { CalibrationRuler } from "./CalibrationRuler";

const NAV_ITEMS = [
  { label: "Overview",     href: "/",              roles: ["senior_lmo", "admin"] },
  { label: "Review Queue", href: "/queue",          roles: ["senior_lmo", "admin"], star: true },
  { label: "Repository",   href: "/repository",     roles: ["senior_lmo", "admin"] },
  { label: "E-Commerce",   href: "/ecommerce",      roles: ["senior_lmo", "admin"] },
  { label: "Challans",     href: "/challans",        roles: ["senior_lmo", "admin"] },
  { label: "Admin",        href: "/admin/rulesets",  roles: ["admin"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, isDashboardRole } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.push("/login");
      } else if (!isDashboardRole) {
        router.push("/login?rejected=1");
      }
    }
  }, [user, loading, isDashboardRole, router]);

  if (loading || !user || !isDashboardRole) {
    return (
      <div className="min-h-screen bg-paper-100 flex items-center justify-center">
        <span className="font-mono text-sm text-ink-600">Verifying credentials…</span>
      </div>
    );
  }

  const visibleNav = NAV_ITEMS.filter((item) => item.roles.includes(user.role));

  return (
    <div className="min-h-screen bg-paper-100 flex flex-col">
      {/* ── Header nav ────────────────────────────────────────────────────── */}
      <header className="bg-ink-900 text-white sticky top-0 z-50 shadow-md">
        <div className="max-w-desktop mx-auto px-6 py-0">
          <div className="flex items-center justify-between h-14">
            {/* Brand */}
            <div className="flex items-center gap-4">
              <span className="font-display text-lg font-bold text-white tracking-tight">
                MetrologyAI
              </span>
              <span className="hidden sm:block font-body text-xs text-brass-500 uppercase tracking-widest">
                Dashboard
              </span>
            </div>

            {/* Nav links */}
            <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
              {visibleNav.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      relative px-3 py-1 font-body text-sm font-medium rounded transition-colors
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900
                      ${isActive
                        ? "text-white bg-white/10"
                        : "text-white/70 hover:text-white hover:bg-white/5"
                      }
                    `}
                  >
                    {item.label}
                    {item.star && (
                      <span className="text-brass-500 font-bold ml-0.5" aria-hidden>*</span>
                    )}
                    {item.href === "/queue" && isActive && (
                      <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-brass-500 rounded-full" />
                    )}
                  </Link>
                );
              })}
            </nav>

            {/* User pill + logout */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <User size={14} className="text-brass-500" aria-hidden />
                <span className="font-body text-xs text-white/80">
                  {user.full_name}
                </span>
                <span className="font-mono text-xs text-brass-500 uppercase">
                  {user.role.replace("_", " ")}
                </span>
              </div>
              <button
                onClick={logout}
                aria-label="Sign out"
                className="p-1.5 rounded text-white/60 hover:text-white hover:bg-white/10 transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500"
              >
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </div>
        {/* Calibration tick rule as header bottom border */}
        <CalibrationRuler />
      </header>

      {/* ── Page content ──────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-desktop mx-auto w-full px-6 py-8">
        {children}
      </main>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-ink-900/10 mt-auto">
        <CalibrationRuler />
        <div className="max-w-desktop mx-auto px-6 py-3 flex justify-between items-center">
          <span className="font-body text-xs text-ink-600">
            Legal Metrology (Packaged Commodities) Rules, 2011 — Enforcement Portal
          </span>
          <span className="font-mono text-xs text-ink-600">
            District: {user.district ?? "—"}
          </span>
        </div>
      </footer>
    </div>
  );
}
