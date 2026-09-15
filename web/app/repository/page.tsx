"use client";
/**
 * §3 Screen 6 — Digital Repository / Product Search (Phase 6.2)
 * Search by brand/barcode, timeline of past scans nationally, trend indicator.
 *
 * Data-model honesty note: the extraction pipeline (Phase 3.2) never defined
 * a dedicated barcode/GTIN field, and "brand" (e.g. "Parle-G") is a
 * different concept from "manufacturer" (e.g. "Parle Products Pvt Ltd") —
 * the only field actually extracted. Search matches manufacturer name, the
 * closest field that's real. See backend/app/services/catalog/product_search.py
 * for the full explanation and /audit/progress.md Log Entry #022 for the
 * flagged follow-up (adding a real barcode/brand field to the schema).
 */
import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Minus,
  Package,
  Search,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { SealBadge, type VerdictStatus } from "@/app/components/SealBadge";
import { productsApi, type ProductSearchResult } from "@/lib/api";

const TREND_CONFIG: Record<
  ProductSearchResult["trend"],
  { icon: typeof TrendingUp; label: string; className: string }
> = {
  IMPROVING: { icon: TrendingUp, label: "Improving", className: "text-verdict-pass bg-verdict-pass/10 border-verdict-pass/20" },
  WORSENING: { icon: TrendingDown, label: "Worsening", className: "text-verdict-fail bg-verdict-fail/10 border-verdict-fail/20" },
  STABLE: { icon: Minus, label: "Stable", className: "text-ink-600 bg-ink-900/5 border-ink-900/10" },
  INSUFFICIENT_DATA: { icon: Minus, label: "Insufficient data", className: "text-ink-600/60 bg-ink-900/5 border-ink-900/10" },
};

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const m = Math.floor(diff / 60000);
  const h = Math.floor(diff / 3600000);
  if (m < 60) return `${Math.max(1, m)}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function TrendBadge({ trend }: { trend: ProductSearchResult["trend"] }) {
  const cfg = TREND_CONFIG[trend];
  const Icon = cfg.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-semibold border ${cfg.className}`}
    >
      <Icon size={12} aria-hidden />
      {cfg.label}
    </span>
  );
}

export default function RepositoryPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductSearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const PAGE_SIZE = 20;

  const fetchResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await productsApi.search({
        q: query.trim() || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setResults(data.results);
      setTotal(data.total);
    } catch {
      setError("Failed to load product repository. Check backend connection.");
    } finally {
      setLoading(false);
    }
  }, [query, page]);

  useEffect(() => {
    const t = setTimeout(fetchResults, 300); // debounce search-as-you-type
    return () => clearTimeout(t);
  }, [fetchResults]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AppShell>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900">
            Digital Repository
          </h1>
          <p className="font-body text-sm text-ink-600 mt-1">
            National compliance history by manufacturer — every scan of every product, nationwide.
          </p>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

      {/* Search bar */}
      <div className="card-surface mb-2">
        <label htmlFor="repository-search" className="sr-only">
          Search by manufacturer / brand name
        </label>
        <div className="relative">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-600/60 pointer-events-none"
            aria-hidden
          />
          <input
            id="repository-search"
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search by manufacturer / brand name (e.g. Parle Products)…"
            className="form-input pl-9 pr-3 py-1.5 text-sm min-h-[40px] w-full"
          />
        </div>
      </div>
      <p className="font-body text-xs text-ink-600/70 mb-6 px-1">
        Search matches manufacturer/brand name. Barcode search isn&apos;t available yet — no
        barcode is captured by the current extraction pipeline.
      </p>

      {error && (
        <div
          role="alert"
          className="mb-6 p-3 rounded-[4px] text-sm font-body flex items-center gap-2"
          style={{
            backgroundColor: "rgba(179,38,30,0.08)",
            border: "1px solid rgba(179,38,30,0.3)",
            color: "#B3261E",
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Data table — §9 compact 32px row density, same as Review Queue */}
      <div className="card-surface p-0 overflow-x-auto shadow-sm">
        <table className="data-table w-full" aria-label="Product compliance history">
          <thead>
            <tr>
              <th className="w-8 pl-4 py-3">
                <span className="sr-only">Expand</span>
              </th>
              <th className="py-3 font-semibold">Manufacturer / Brand</th>
              <th className="py-3 font-semibold text-center">Scans</th>
              <th className="py-3 font-semibold text-center">Passed</th>
              <th className="py-3 font-semibold text-center">Failed</th>
              <th className="py-3 font-semibold text-center">Pending</th>
              <th className="py-3 font-semibold">Trend</th>
              <th className="py-3 pr-4 font-semibold">Last Scan</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="py-16 text-center">
                  <span className="font-mono text-sm text-ink-600 animate-pulse">
                    Searching national repository…
                  </span>
                </td>
              </tr>
            ) : results.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-16 text-center">
                  <div className="max-w-md mx-auto">
                    <p className="font-display text-base font-semibold text-ink-900">
                      No products found
                    </p>
                    <p className="font-body text-xs text-ink-600 mt-1">
                      {query
                        ? "No manufacturer/brand names match your search."
                        : "No scans have a recognized manufacturer name yet."}
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              results.map((product) => {
                const isExpanded = expanded === product.manufacturer_name;
                return (
                  <Fragment key={product.manufacturer_name}>
                    <tr
                      className="hover:bg-ink-900/[0.03] transition-colors cursor-pointer"
                      onClick={() =>
                        setExpanded(isExpanded ? null : product.manufacturer_name)
                      }
                    >
                      <td className="pl-4 py-3 align-middle">
                        <button
                          type="button"
                          aria-label={isExpanded ? "Collapse timeline" : "Expand timeline"}
                          aria-expanded={isExpanded}
                          className="text-ink-600 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500 rounded"
                        >
                          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                      </td>
                      <td className="py-3 align-middle">
                        <span className="font-body text-sm font-semibold text-ink-900">
                          {product.manufacturer_name}
                        </span>
                      </td>
                      <td className="py-3 align-middle text-center font-mono text-xs text-ink-900">
                        {product.total_scans}
                      </td>
                      <td className="py-3 align-middle text-center font-mono text-xs text-verdict-pass">
                        {product.passed_count}
                      </td>
                      <td className="py-3 align-middle text-center font-mono text-xs text-verdict-fail">
                        {product.failed_count}
                      </td>
                      <td className="py-3 align-middle text-center font-mono text-xs text-verdict-pending">
                        {product.pending_review_count}
                      </td>
                      <td className="py-3 align-middle">
                        <TrendBadge trend={product.trend} />
                      </td>
                      <td className="pr-4 py-3 align-middle font-mono text-xs text-ink-600">
                        {timeAgo(product.last_scan_at)}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={8} className="bg-paper-100 px-4 py-3">
                          <p className="font-body text-xs font-semibold text-ink-600 uppercase tracking-wider mb-2">
                            Scan timeline ({product.scans.length} of {product.total_scans})
                          </p>
                          <div className="flex flex-col gap-1.5">
                            {product.scans.map((scan) => (
                              <Link
                                key={scan.scan_id}
                                href={`/queue/${scan.scan_id}`}
                                className="flex items-center gap-3 py-1.5 px-2 rounded hover:bg-paper-000 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500"
                              >
                                <SealBadge verdict={scan.status as VerdictStatus} size={24} />
                                <span className="font-mono text-xs text-ink-600 w-16">
                                  {timeAgo(scan.captured_at_utc ?? scan.created_at)}
                                </span>
                                <span className="font-body text-xs text-ink-900 flex-1">
                                  {scan.district_label ?? "Unknown location"}
                                </span>
                                <span className="font-mono text-[10px] text-ink-600/60 flex items-center gap-1">
                                  <Package size={11} aria-hidden />
                                  {scan.scan_id.slice(0, 8)}…
                                </span>
                              </Link>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="font-body text-xs text-ink-600">
            Page {page} of {totalPages} ({total} total products)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="btn-secondary text-xs px-3 py-1 min-h-[36px]"
            >
              ← Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="btn-secondary text-xs px-3 py-1 min-h-[36px]"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
