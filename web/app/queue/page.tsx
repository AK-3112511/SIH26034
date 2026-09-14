"use client";
/**
 * §3 Screen 3 — Review Queue
 * Reads real PENDING_REVIEW scans from the backend.
 * Layout and filter controls strictly per §4.2's layout sketch:
 *   Filter: [District ▾] [Confidence ▾] [Age ▾]     [Search]
 *   🖼  Parle-G 100g        Chennai, TN     2h ago   [Review]
 * One-at-a-time selection only — no bulk actions, per the doc's explicit reasoning.
 */
import { useCallback, useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  Search,
  SlidersHorizontal,
  Package,
  AlertCircle,
  Clock,
  ArrowRight,
  ShieldAlert,
} from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { SealBadge, type VerdictStatus } from "@/app/components/SealBadge";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { scansApi, type ScanListItem } from "@/lib/api";

type SortField = "created_at" | "confidence_gap" | "age";
type SortDir = "asc" | "desc";

const DISTRICT_OPTIONS = [
  { value: "", label: "All Districts" },
  { value: "Chennai", label: "Chennai, TN" },
  { value: "Coimbatore", label: "Coimbatore, TN" },
  { value: "Madurai", label: "Madurai, TN" },
  { value: "Salem", label: "Salem, TN" },
];

const CONFIDENCE_OPTIONS = [
  { value: "all", label: "All Confidence" },
  { value: "gap_desc", label: "Largest Gap First" },
  { value: "gap_asc", label: "Smallest Gap First" },
  { value: "critical", label: "Critical Gap (>30%)" },
  { value: "moderate", label: "Moderate Gap (15–30%)" },
  { value: "low", label: "Low Gap (<15%)" },
];

const AGE_OPTIONS = [
  { value: "newest", label: "Newest First" },
  { value: "oldest", label: "Oldest First (>24h)" },
  { value: "today", label: "Captured Today (<24h)" },
];

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const m = Math.floor(diff / 60000);
  const h = Math.floor(diff / 3600000);
  if (m < 60) return `${Math.max(1, m)}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function ReviewQueuePage() {
  const [items, setItems] = useState<ScanListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // §4.2 Filter Sketch Controls: [District ▾] [Confidence ▾] [Age ▾] [Search]
  const [districtFilter, setDistrictFilter] = useState("");
  const [confidenceOption, setConfidenceOption] = useState("all");
  const [ageOption, setAgeOption] = useState("newest");
  const [searchQuery, setSearchQuery] = useState("");

  // Column sort state
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const PAGE_SIZE = 20;

  // Map confidence & age options to API sort/filter params
  const computedSortParams = useMemo(() => {
    let apiSortBy: SortField = sortBy;
    let apiSortDir: SortDir = sortDir;

    if (confidenceOption === "gap_desc") {
      apiSortBy = "confidence_gap";
      apiSortDir = "desc";
    } else if (confidenceOption === "gap_asc") {
      apiSortBy = "confidence_gap";
      apiSortDir = "asc";
    } else if (ageOption === "newest") {
      apiSortBy = "created_at";
      apiSortDir = "desc";
    } else if (ageOption === "oldest") {
      apiSortBy = "created_at";
      apiSortDir = "asc";
    }

    return { sort_by: apiSortBy, sort_dir: apiSortDir };
  }, [confidenceOption, ageOption, sortBy, sortDir]);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const confidence_band =
        confidenceOption === "critical" || confidenceOption === "moderate" || confidenceOption === "low"
          ? confidenceOption
          : undefined;
      const age_band =
        ageOption === "today" ? "today" : ageOption === "oldest" ? "older" : undefined;

      const { data } = await scansApi.list({
        status: "PENDING_REVIEW", // Queue focuses on PENDING_REVIEW per §3
        district: districtFilter || undefined,
        q: searchQuery.trim() || undefined,
        confidence_band,
        age_band,
        sort_by: computedSortParams.sort_by,
        sort_dir: computedSortParams.sort_dir,
        page,
        page_size: PAGE_SIZE,
      });

      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load review queue from server. Please verify backend connection.");
    } finally {
      setLoading(false);
    }
  }, [districtFilter, confidenceOption, ageOption, searchQuery, computedSortParams, page]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleColumnSort = (field: SortField) => {
    if (field === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AppShell>
      {/* ── Page Header per §4.2 Layout Sketch ────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-2">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-2xl font-bold text-ink-900 tracking-tight">
              Review Queue
            </h1>
            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-brass-500/10 text-brass-500 border border-brass-500/20">
              PENDING REVIEW
            </span>
          </div>
          <p className="font-body text-sm text-ink-600 mt-1">
            {loading ? "Refreshing queue…" : `${total} scan${total !== 1 ? "s" : ""} requiring senior officer verification`}
          </p>
        </div>

        {/* Legal Invariant Tag (§3 & §4.2) */}
        <div className="flex items-center gap-2 px-3 py-2 rounded-[4px] bg-paper-000 border border-ink-900/[0.08] text-xs font-body text-ink-600 shadow-sm">
          <ShieldAlert size={14} className="text-brass-500 flex-shrink-0" aria-hidden />
          <span>
            <strong>Single Selection Only:</strong> Individual adjudication per Legal Metrology Act (no bulk actions).
          </span>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

      {/* ── Filter Bar per §4.2 Layout Sketch ─────────────────────────────── */}
      {/* Filter: [District ▾] [Confidence ▾] [Age ▾]     [Search] */}
      <div
        className="card-surface mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4"
        role="search"
        aria-label="Filter review queue"
      >
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-ink-600 uppercase tracking-wider mr-1">
            <SlidersHorizontal size={14} className="text-brass-500" aria-hidden />
            <span>Filter:</span>
          </div>

          {/* [District ▾] */}
          <div className="min-w-[150px]">
            <label htmlFor="filter-district" className="sr-only">
              Filter by District
            </label>
            <div className="relative">
              <select
                id="filter-district"
                value={districtFilter}
                onChange={(e) => {
                  setDistrictFilter(e.target.value);
                  setPage(1);
                }}
                className="form-input text-xs pr-8 py-1.5 min-h-[40px] appearance-none cursor-pointer"
              >
                {DISTRICT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-600/60 pointer-events-none"
                aria-hidden
              />
            </div>
          </div>

          {/* [Confidence ▾] */}
          <div className="min-w-[170px]">
            <label htmlFor="filter-confidence" className="sr-only">
              Sort/Filter by Confidence Gap
            </label>
            <div className="relative">
              <select
                id="filter-confidence"
                value={confidenceOption}
                onChange={(e) => {
                  setConfidenceOption(e.target.value);
                  setPage(1);
                }}
                className="form-input text-xs pr-8 py-1.5 min-h-[40px] appearance-none cursor-pointer"
              >
                {CONFIDENCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-600/60 pointer-events-none"
                aria-hidden
              />
            </div>
          </div>

          {/* [Age ▾] */}
          <div className="min-w-[160px]">
            <label htmlFor="filter-age" className="sr-only">
              Sort by Age
            </label>
            <div className="relative">
              <select
                id="filter-age"
                value={ageOption}
                onChange={(e) => {
                  setAgeOption(e.target.value);
                  setPage(1);
                }}
                className="form-input text-xs pr-8 py-1.5 min-h-[40px] appearance-none cursor-pointer"
              >
                {AGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-600/60 pointer-events-none"
                aria-hidden
              />
            </div>
          </div>
        </div>

        {/* [Search] */}
        <div className="w-full md:w-72">
          <label htmlFor="queue-search" className="sr-only">
            Search product or scan ID
          </label>
          <div className="relative">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-600/60 pointer-events-none"
              aria-hidden
            />
            <input
              id="queue-search"
              type="search"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Search product or ID…"
              className="form-input pl-9 pr-3 py-1.5 text-xs min-h-[40px]"
            />
          </div>
        </div>
      </div>

      {/* ── Error Banner ─────────────────────────────────────────────────── */}
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

      {/* ── Data Table per §4.2 Layout Sketch & §5.5 Design System ───────── */}
      <div className="card-surface p-0 overflow-x-auto shadow-sm">
        <table className="data-table w-full" aria-label="Scans pending review">
          <thead>
            <tr>
              <th className="w-12 pl-4 py-3">
                <span className="sr-only">Seal Verdict</span>
              </th>
              <th className="py-3 w-16 text-center">Preview</th>
              <th className="py-3 font-semibold">Product / Scan</th>
              <th className="py-3 font-semibold">District</th>
              <th className="py-3 font-semibold">
                <button
                  type="button"
                  onClick={() => handleColumnSort("confidence_gap")}
                  className="inline-flex items-center gap-1 font-body text-xs font-semibold uppercase tracking-wider text-ink-600 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500 rounded"
                >
                  Confidence Gap
                  {sortBy === "confidence_gap" ? (
                    sortDir === "desc" ? <ChevronDown size={13} className="text-brass-500" /> : <ChevronUp size={13} className="text-brass-500" />
                  ) : (
                    <ChevronsUpDown size={13} className="text-ink-600/40" />
                  )}
                </button>
              </th>
              <th className="py-3 font-semibold">
                <button
                  type="button"
                  onClick={() => handleColumnSort("created_at")}
                  className="inline-flex items-center gap-1 font-body text-xs font-semibold uppercase tracking-wider text-ink-600 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500 rounded"
                >
                  Age
                  {sortBy === "created_at" ? (
                    sortDir === "desc" ? <ChevronDown size={13} className="text-brass-500" /> : <ChevronUp size={13} className="text-brass-500" />
                  ) : (
                    <ChevronsUpDown size={13} className="text-ink-600/40" />
                  )}
                </button>
              </th>
              <th className="py-3 pr-4 text-right font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="py-16 text-center">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <span className="font-mono text-sm text-ink-600 animate-pulse">
                      Retrieving pending review scans…
                    </span>
                  </div>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-16 text-center">
                  <div className="max-w-md mx-auto">
                    <p className="font-display text-base font-semibold text-ink-900">
                      No scans awaiting review
                    </p>
                    <p className="font-body text-xs text-ink-600 mt-1">
                      {districtFilter || searchQuery
                        ? "No scans match the selected district or search term. Try resetting your filters."
                        : "All scans in your district have been adjudicated. New offline syncs will populate automatically."}
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const gapPercent = item.confidence_gap !== null ? (item.confidence_gap * 100).toFixed(1) : null;
                const isCriticalGap = (item.confidence_gap ?? 0) >= 0.30;

                return (
                  <tr key={item.scan_id} className="hover:bg-ink-900/[0.03] transition-colors">
                    {/* Seal badge (§5.1) */}
                    <td className="pl-4 py-3 align-middle">
                      <SealBadge verdict={item.status as VerdictStatus} size={24} />
                    </td>

                    {/* 🖼 Thumbnail preview per §4.2 */}
                    <td className="py-3 align-middle text-center">
                      <div className="w-11 h-11 rounded-[4px] overflow-hidden bg-paper-100 border border-ink-900/[0.08] flex items-center justify-center relative mx-auto">
                        {item.image_url ? (
                          <img
                            src={item.image_url}
                            alt={item.product_name ?? "Scan preview"}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              // Fallback if image path not available on static host
                              (e.currentTarget as HTMLElement).style.display = "none";
                            }}
                          />
                        ) : null}
                        <Package size={16} className="text-ink-600/40 absolute" aria-hidden />
                      </div>
                    </td>

                    {/* Product / Scan ID per §4.2 */}
                    <td className="py-3 align-middle">
                      <div>
                        <span className="font-body text-sm font-semibold text-ink-900 block leading-tight">
                          {item.product_name ?? "Unlabeled Package Capture"}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="font-mono text-xs text-ink-600">
                            ID: {item.scan_id.slice(0, 8)}…
                          </span>
                          <span className="font-mono text-[10px] uppercase px-1.5 py-0.2 rounded bg-ink-900/5 text-ink-600">
                            {item.source}
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* District location per §4.2 */}
                    <td className="py-3 align-middle font-body text-xs text-ink-600">
                      <span className="font-medium text-ink-900">
                        {item.district_label ?? (item.lat && item.lng ? `${item.lat.toFixed(2)}, ${item.lng.toFixed(2)}` : "—")}
                      </span>
                    </td>

                    {/* Confidence gap in IBM Plex Mono */}
                    <td className="py-3 align-middle">
                      {gapPercent !== null ? (
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`font-mono text-xs font-semibold px-2 py-0.5 rounded ${
                              isCriticalGap
                                ? "text-verdict-fail bg-verdict-fail/10 border border-verdict-fail/20"
                                : "text-ink-900 bg-ink-900/5"
                            }`}
                          >
                            Δ {gapPercent}%
                          </span>
                        </div>
                      ) : (
                        <span className="font-mono text-xs text-ink-600/60">—</span>
                      )}
                    </td>

                    {/* Age per §4.2 (e.g. 2h ago, 5h ago, 1d ago) */}
                    <td className="py-3 align-middle font-mono text-xs text-ink-600">
                      <div className="flex items-center gap-1">
                        <Clock size={12} className="text-ink-600/60" aria-hidden />
                        <span>{timeAgo(item.created_at)}</span>
                      </div>
                    </td>

                    {/* Action button [Review →] — Strictly one-at-a-time */}
                    <td className="pr-4 py-3 align-middle text-right">
                      <Link
                        href={`/queue/${item.scan_id}`}
                        className="
                          inline-flex items-center justify-center gap-1.5
                          bg-ink-900 text-white font-body text-xs font-semibold
                          px-3 py-1.5 rounded-[4px] min-h-[36px]
                          transition-colors hover:bg-ink-600
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500
                        "
                        aria-label={`Review ${item.product_name ?? 'scan'} ${item.scan_id.slice(0, 8)}`}
                      >
                        <span>Review</span>
                        <ArrowRight size={12} />
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ────────────────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="font-body text-xs text-ink-600">
            Page {page} of {totalPages} ({total} total queued)
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
