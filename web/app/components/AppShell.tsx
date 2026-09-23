"use client";
/**
 * AppShell — authenticated layout wrapper.
 *
 * Guards the route (unauthenticated → /login, field officers → the handset)
 * and renders the navigation. Below 768px the nav links were simply hidden
 * with `hidden md:flex` and nothing replaced them, so on a phone the dashboard
 * had no way to reach any page but the one already open; there is now a
 * disclosure menu.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogOut, Menu, User, X } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { CalibrationRuler } from "./CalibrationRuler";

const NAV_ITEMS = [
  { label: "Overview",     href: "/",                roles: ["senior_lmo", "admin"] },
  { label: "Review Queue", href: "/queue",           roles: ["senior_lmo", "admin"] },
  { label: "Repository",   href: "/repository",      roles: ["senior_lmo", "admin"] },
  { label: "E-Commerce",   href: "/ecommerce",       roles: ["senior_lmo", "admin"] },
  { label: "Challans",     href: "/challans",        roles: ["senior_lmo", "admin"] },
  { label: "Rulesets",     href: "/admin/rulesets",  roles: ["admin"] },
  { label: "Users",        href: "/admin/users",     roles: ["admin"] },
  { label: "Audit Log",    href: "/admin/audit-log", roles: ["admin"] },
];

function isActivePath(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, isDashboardRole } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.push("/login");
      } else if (!isDashboardRole) {
        router.push("/login?rejected=1");
      }
    }
  }, [user, loading, isDashboardRole, router]);

  // A route change should never leave the menu covering the new page.
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  if (loading || !user || !isDashboardRole) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper-100">
        <span className="font-mono text-sm text-ink-600">Verifying credentials…</span>
      </div>
    );
  }

  const visibleNav = NAV_ITEMS.filter((item) => item.roles.includes(user.role));

  return (
    <div className="flex min-h-screen flex-col bg-paper-100">
      <header className="sticky top-0 z-50 bg-ink-900 text-white shadow-md">
        <div className="mx-auto max-w-desktop px-6">
          <div className="flex h-14 items-center justify-between gap-3">
            <div className="flex items-center gap-4">
              <span className="font-display text-lg font-bold tracking-tight text-white">
                MetrologyAI
              </span>
              <span className="hidden font-body text-xs uppercase tracking-widest text-brass-500 sm:block">
                Dashboard
              </span>
            </div>

            <nav className="hidden items-center gap-1 md:flex" aria-label="Main navigation">
              {visibleNav.map((item) => {
                const active = isActivePath(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`rounded px-3 py-1 font-body text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-900 ${
                      active ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-2 sm:flex">
                <User size={14} className="text-brass-500" aria-hidden />
                <span className="font-body text-xs text-white/80">{user.full_name}</span>
                <span className="font-mono text-xs uppercase text-brass-500">
                  {user.role.replace("_", " ")}
                </span>
              </div>
              <button
                type="button"
                onClick={() => logout()}
                aria-label="Sign out"
                className="rounded p-1.5 text-white/60 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500"
              >
                <LogOut size={16} />
              </button>
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-label={menuOpen ? "Close menu" : "Open menu"}
                aria-expanded={menuOpen}
                aria-controls="mobile-nav"
                className="rounded p-1.5 text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500 md:hidden"
              >
                {menuOpen ? <X size={18} /> : <Menu size={18} />}
              </button>
            </div>
          </div>
        </div>

        {menuOpen && (
          <nav
            id="mobile-nav"
            aria-label="Main navigation"
            className="border-t border-white/10 bg-ink-900 md:hidden"
          >
            <div className="mx-auto max-w-desktop px-4 py-2">
              <div className="border-b border-white/10 px-2 pb-2 font-body text-xs text-white/70">
                {user.full_name} · <span className="uppercase text-brass-500">{user.role.replace("_", " ")}</span>
              </div>
              <ul className="py-1">
                {visibleNav.map((item) => {
                  const active = isActivePath(pathname, item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={`block min-h-touch rounded px-3 py-3 font-body text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500 ${
                          active ? "bg-white/10 font-semibold text-white" : "text-white/75 hover:bg-white/5 hover:text-white"
                        }`}
                      >
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          </nav>
        )}

        <CalibrationRuler />
      </header>

      <main className="mx-auto w-full max-w-desktop flex-1 px-4 py-8 sm:px-6">{children}</main>

      <footer className="mt-auto border-t border-ink-900/10">
        <CalibrationRuler />
        <div className="mx-auto flex max-w-desktop flex-col gap-1 px-6 py-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="font-body text-xs text-ink-600">
            Legal Metrology (Packaged Commodities) Rules, 2011 — Enforcement Portal
          </span>
          <span className="font-mono text-xs text-ink-600">District: {user.district ?? "—"}</span>
        </div>
      </footer>
    </div>
  );
}
