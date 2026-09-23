"use client";
/**
 * Overview — what was inspected today, and where.
 *
 * The counts now render as skeletons on first load rather than as em-dashes,
 * which read as "nothing was scanned today" while the request was still in
 * flight.
 */
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowRight, RefreshCw } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { SealBadge } from "@/app/components/SealBadge";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import { scansApi, type DashboardStats } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

const Heatmap = dynamic(
  () => import("@/app/components/Heatmap").then((m) => m.Heatmap),
  {
    ssr: false,
    loading: () => (
      <div
        className="flex items-center justify-center"
        style={{ minHeight: 420 }}
      >
        <span className="font-mono text-sm text-ink-600">Loading map…</span>
      </div>
    ),
  }
);

function StatCard({
  label,
  value,
  verdict,
  href,
  loading = false,
}: {
  label: string;
  value: number | null;
  verdict: "PASSED" | "FAILED" | "PENDING_REVIEW" | "CALIBRATION_FAILED" | "QUEUED";
  href?: string;
  loading?: boolean;
}) {
  const inner = (
    <div className="card-surface flex flex-col gap-3 h-full transition-shadow hover:shadow-sm">
      <div className="flex items-center justify-between">
        <span className="font-body text-xs font-semibold text-ink-600 uppercase tracking-wider">
          {label}
        </span>
        <SealBadge verdict={verdict} size={24} />
      </div>
      {loading ? (
        <div
          className="h-10 w-20 animate-pulse rounded bg-ink-900/10"
          role="status"
          aria-label={`Loading ${label}`}
        />
      ) : (
        <p className="font-mono text-4xl font-bold tabular-nums text-ink-900">
          {value === null ? "—" : value.toLocaleString()}
        </p>
      )}
      {href && (
        <span className="flex items-center gap-1 font-body text-xs text-brass-500 font-semibold mt-auto">
          View queue <ArrowRight size={12} />
        </span>
      )}
    </div>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500 focus-visible:ring-offset-2 rounded-card"
      >
        {inner}
      </Link>
    );
  }
  return inner;
}

export default function OverviewPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await scansApi.stats();
      setStats(data);
      setLastRefresh(new Date());
    } catch (err) {
      setError(apiErrorMessage(err, "Today's counts could not be loaded."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return (
    <AppShell>
      {/* Page header */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink-900">
            Overview
          </h2>
          <p className="font-body text-sm text-ink-600 mt-1">
            Inspections recorded today under the Packaged Commodities Rules, 2011
          </p>
        </div>
        <button
          onClick={fetchStats}
          disabled={loading}
          aria-label="Refresh statistics"
          className="btn-secondary flex items-center gap-2 text-xs px-3 py-2 min-h-0 h-9"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      <CalibrationRuler className="mb-6" />

      <ErrorBanner className="mb-6" message={error} onRetry={fetchStats} />

      <section aria-label="Today's inspection counts">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Scanned today"
            value={stats?.scanned_today ?? null}
            verdict="QUEUED"
            loading={loading && !stats}
          />
          <StatCard
            label="Passed"
            value={stats?.passed_today ?? null}
            verdict="PASSED"
            loading={loading && !stats}
          />
          <StatCard
            label="Failed"
            value={stats?.failed_today ?? null}
            verdict="FAILED"
            loading={loading && !stats}
          />
          <StatCard
            label="Pending review"
            value={stats?.pending_review ?? null}
            verdict="PENDING_REVIEW"
            href="/queue"
            loading={loading && !stats}
          />
        </div>
      </section>

      <CalibrationRuler className="mb-6" />

      <section aria-label="National compliance heatmap">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display text-lg font-semibold text-ink-900">
            Where scans were taken
          </h3>
        </div>
        <div className="card-surface p-0 overflow-hidden">
          <Heatmap />
        </div>
      </section>

      <CalibrationRuler className="mt-8 mb-4" />

      {/* Secondary stats */}
      {stats && (
        <section aria-label="Additional statistics">
          <div className="flex items-center gap-6">
            <div>
              <span className="form-label">Calibration failed today</span>
              <p className="font-mono text-xl font-bold text-ink-900 tabular-nums">
                {stats.calibration_failed_today}
              </p>
            </div>
            <div className="h-8 w-px bg-ink-900/10" aria-hidden />
            <div>
              <span className="form-label">Last refreshed</span>
              <p className="font-mono text-sm text-ink-600">
                {lastRefresh.toLocaleTimeString("en-IN")}
              </p>
            </div>
          </div>
        </section>
      )}
    </AppShell>
  );
}
