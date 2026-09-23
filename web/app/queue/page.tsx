"use client";
/**
 * Review Queue — the scans waiting for a senior officer.
 *
 * Three things made this list hard to work with and all of them are fixed
 * here. Every keystroke in the search box fired a request and replaced the
 * table with a spinner, so typing a product name flashed the page repeatedly.
 * The 15-second refresh reset its timer whenever any filter changed, and kept
 * polling in a background tab. And the district filter offered four
 * hard-coded names, so a scan from anywhere else could not be filtered to.
 *
 * New arrivals no longer reload the table underneath the officer either: an
 * unobtrusive count appears, and they choose when to take them.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ChevronDown,
  ChevronsUpDown,
  ChevronUp,
  Clock,
  Package,
  RefreshCw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
} from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { SealBadge, type VerdictStatus } from "@/app/components/SealBadge";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import { Pagination } from "@/app/components/ui/Pagination";
import { TableState } from "@/app/components/ui/TableState";
import { scansApi, eventsApi, type ScanListItem } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { shortId, timeAgo } from "@/lib/format";

type SortField = "created_at" | "confidence_gap";
type SortDir = "asc" | "desc";

const CONFIDENCE_OPTIONS = [
  { value: "all", label: "Any confidence" },
  { value: "gap_desc", label: "Largest gap first" },
  { value: "gap_asc", label: "Smallest gap first" },
  { value: "critical", label: "Critical gap (30% and over)" },
  { value: "moderate", label: "Moderate gap (15-30%)" },
  { value: "low", label: "Low gap (under 15%)" },
];

const AGE_OPTIONS = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "today", label: "Captured today" },
];

const PAGE_SIZE = 20;
const POLL_INTERVAL_MS = 15_000;
const SEARCH_DEBOUNCE_MS = 350;

export default function ReviewQueuePage() {
  const [items, setItems] = useState<ScanListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  /** First load only: a background refresh must not blank the table. */
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newCount, setNewCount] = useState(0);

  const [districtFilter, setDistrictFilter] = useState("");
  const [districts, setDistricts] = useState<string[]>([]);
  const [confidenceOption, setConfidenceOption] = useState("all");
  const [ageOption, setAgeOption] = useState("newest");

  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Debounce the search box: the officer is typing a product name, not asking
  // for a request per character.
  useEffect(() => {
    const id = setTimeout(() => {
      setSearchQuery(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  useEffect(() => {
    scansApi
      .districts()
      .then(({ data }) => setDistricts(data))
      .catch(() => setDistricts([]));
  }, []);

  const sortParams = useMemo(() => {
    if (confidenceOption === "gap_desc") return { sort_by: "confidence_gap", sort_dir: "desc" };
    if (confidenceOption === "gap_asc") return { sort_by: "confidence_gap", sort_dir: "asc" };
    if (ageOption === "oldest") return { sort_by: "created_at", sort_dir: "asc" };
    if (ageOption === "newest") return { sort_by: "created_at", sort_dir: "desc" };
    return { sort_by: sortBy, sort_dir: sortDir };
  }, [confidenceOption, ageOption, sortBy, sortDir]);

  const fetchQueue = useCallback(
    async (background = false) => {
      if (background) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const confidence_band =
          confidenceOption === "critical" ||
          confidenceOption === "moderate" ||
          confidenceOption === "low"
            ? confidenceOption
            : undefined;
        const age_band =
          ageOption === "today" ? "today" : ageOption === "oldest" ? "older" : undefined;

        const { data } = await scansApi.list({
          status: "PENDING_REVIEW",
          district: districtFilter || undefined,
          q: searchQuery || undefined,
          confidence_band,
          age_band,
          sort_by: sortParams.sort_by,
          sort_dir: sortParams.sort_dir,
          page,
          page_size: PAGE_SIZE,
        });

        setItems(data.items);
        setTotal(data.total);
        setNewCount(0);
      } catch (err) {
        setError(apiErrorMessage(err, "The review queue could not be loaded."));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [districtFilter, confidenceOption, ageOption, searchQuery, sortParams, page]
  );

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  // Poll for new arrivals. The interval is deliberately independent of the
  // filter state, so changing a filter does not restart the clock; the ref
  // keeps the latest fetch reachable without re-creating the timer.
  const fetchRef = useRef(fetchQueue);
  useEffect(() => {
    fetchRef.current = fetchQueue;
  }, [fetchQueue]);

  useEffect(() => {
    let since = new Date().toISOString();
    let cancelled = false;

    const tick = async () => {
      // A hidden tab does not need to poll; it will catch up on focus.
      if (document.visibilityState === "hidden") return;
      try {
        const { data } = await eventsApi.poll(since);
        if (cancelled) return;
        since = data.server_time || since;
        const arrivals = data.events.filter((e) => e.event_type === "scan.status_changed").length;
        if (arrivals > 0) setNewCount((n) => n + arrivals);
      } catch {
        // A failed poll is not worth an error banner; the next one may work.
      }
    };

    const id = setInterval(tick, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      cancelled = true;
      clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, []);

  const handleColumnSort = (field: SortField) => {
    if (field === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
    // A column sort is an explicit instruction: stop deferring to the presets.
    setConfidenceOption((c) => (c === "gap_desc" || c === "gap_asc" ? "all" : c));
    setAgeOption((a) => (a === "newest" || a === "oldest" ? "today" : a));
    setPage(1);
  };

  const hasFilters = Boolean(districtFilter || searchQuery || confidenceOption !== "all");

  const sortIcon = (field: SortField) =>
    sortBy === field ? (
      sortDir === "desc" ? (
        <ChevronDown size={13} className="text-brass-500" aria-hidden />
      ) : (
        <ChevronUp size={13} className="text-brass-500" aria-hidden />
      )
    ) : (
      <ChevronsUpDown size={13} className="text-ink-600/40" aria-hidden />
    );

  return (
    <AppShell>
      <div className="mb-2 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900">
              Review queue
            </h1>
            {refreshing && (
              <RefreshCw size={14} className="animate-spin text-ink-600" aria-label="Refreshing" />
            )}
          </div>
          <p className="mt-1 font-body text-sm text-ink-600">
            {loading
              ? "Loading…"
              : `${total} scan${total === 1 ? "" : "s"} awaiting a senior officer`}
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-card border border-ink-900/[0.08] bg-paper-000 px-3 py-2 font-body text-xs text-ink-600 shadow-sm">
          <ShieldAlert size={14} className="shrink-0 text-brass-500" aria-hidden />
          <span>
            <strong>One scan at a time.</strong> Each package is adjudicated individually.
          </span>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

      {newCount > 0 && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-card border border-brass-500/30 bg-brass-500/5 p-3">
          <p className="font-body text-xs text-ink-900">
            {newCount} scan{newCount === 1 ? " has" : "s have"} changed status since you opened
            this list.
          </p>
          <button
            type="button"
            onClick={() => fetchQueue(true)}
            className="btn-secondary min-h-[36px] px-3 py-1 text-xs"
          >
            Refresh
          </button>
        </div>
      )}

      <div
        className="card-surface mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-center"
        role="search"
        aria-label="Filter the review queue"
      >
        <div className="flex flex-wrap items-center gap-3">
          <div className="mr-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-600">
            <SlidersHorizontal size={14} className="text-brass-500" aria-hidden />
            <span>Filter</span>
          </div>

          <div className="min-w-[150px]">
            <label htmlFor="filter-district" className="sr-only">
              Filter by district
            </label>
            <select
              id="filter-district"
              value={districtFilter}
              onChange={(e) => {
                setDistrictFilter(e.target.value);
                setPage(1);
              }}
              className="form-input min-h-[40px] cursor-pointer py-1.5 text-xs"
            >
              <option value="">All districts</option>
              {districts.map((district) => (
                <option key={district} value={district}>
                  {district}
                </option>
              ))}
            </select>
          </div>

          <div className="min-w-[180px]">
            <label htmlFor="filter-confidence" className="sr-only">
              Filter by confidence gap
            </label>
            <select
              id="filter-confidence"
              value={confidenceOption}
              onChange={(e) => {
                setConfidenceOption(e.target.value);
                setPage(1);
              }}
              className="form-input min-h-[40px] cursor-pointer py-1.5 text-xs"
            >
              {CONFIDENCE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="min-w-[160px]">
            <label htmlFor="filter-age" className="sr-only">
              Filter by age
            </label>
            <select
              id="filter-age"
              value={ageOption}
              onChange={(e) => {
                setAgeOption(e.target.value);
                setPage(1);
              }}
              className="form-input min-h-[40px] cursor-pointer py-1.5 text-xs"
            >
              {AGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="w-full md:w-72">
          <label htmlFor="queue-search" className="sr-only">
            Search by product or scan id
          </label>
          <div className="relative">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-600/60"
              aria-hidden
            />
            <input
              id="queue-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search product or scan id"
              className="form-input min-h-[40px] py-1.5 pl-9 pr-3 text-xs"
            />
          </div>
        </div>
      </div>

      <ErrorBanner className="mb-6" message={error} onRetry={() => fetchQueue()} />

      <div className="card-surface overflow-x-auto p-0 shadow-sm">
        <table className="data-table w-full">
          <caption className="sr-only">Scans awaiting review</caption>
          <thead>
            <tr>
              <th scope="col" className="w-12 py-3 pl-4">
                <span className="sr-only">Verdict</span>
              </th>
              <th scope="col" className="w-16 py-3 text-center">
                Preview
              </th>
              <th scope="col" className="py-3">
                Product
              </th>
              <th scope="col" className="py-3">
                District
              </th>
              <th scope="col" className="py-3">
                <button
                  type="button"
                  onClick={() => handleColumnSort("confidence_gap")}
                  className="inline-flex items-center gap-1 rounded font-body text-xs font-semibold uppercase tracking-wider text-ink-600 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500"
                >
                  Confidence gap
                  {sortIcon("confidence_gap")}
                </button>
              </th>
              <th scope="col" className="py-3">
                <button
                  type="button"
                  onClick={() => handleColumnSort("created_at")}
                  className="inline-flex items-center gap-1 rounded font-body text-xs font-semibold uppercase tracking-wider text-ink-600 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500"
                >
                  Age
                  {sortIcon("created_at")}
                </button>
              </th>
              <th scope="col" className="py-3 pr-4 text-right">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            <TableState
              colSpan={7}
              loading={loading}
              isEmpty={items.length === 0}
              loadingLabel="Loading the queue…"
              emptyTitle="No scans awaiting review"
              emptyHint={
                hasFilters
                  ? "Nothing matches these filters. Try clearing the search or the district."
                  : "Every scan in your jurisdiction has been adjudicated. New captures will appear here as they sync."
              }
            />

            {!loading &&
              items.map((item) => {
                const gap = item.confidence_gap;
                const isCritical = (gap ?? 0) >= 0.3;

                return (
                  <tr key={item.scan_id}>
                    <td className="py-3 pl-4 align-middle">
                      <SealBadge verdict={item.status as VerdictStatus} size={24} />
                    </td>

                    <td className="py-3 text-center align-middle">
                      <div className="relative mx-auto flex h-11 w-11 items-center justify-center overflow-hidden rounded-card border border-ink-900/[0.08] bg-paper-100">
                        <Package size={16} className="absolute text-ink-600/40" aria-hidden />
                        {item.image_url && (
                          <img
                            src={item.image_url}
                            alt=""
                            className="relative h-full w-full object-cover"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        )}
                      </div>
                    </td>

                    <td className="py-3 align-middle">
                      <span className="block font-body text-sm font-semibold leading-tight text-ink-900">
                        {item.product_name ?? "Unnamed package"}
                      </span>
                      <span className="mt-0.5 flex items-center gap-2">
                        <span className="font-mono text-xs text-ink-600">
                          {shortId(item.scan_id)}
                        </span>
                        <span className="rounded bg-ink-900/5 px-1.5 py-0.5 font-mono text-[10px] uppercase text-ink-600">
                          {item.source === "ecommerce" ? "online" : "field"}
                        </span>
                      </span>
                    </td>

                    <td className="py-3 align-middle font-body text-xs text-ink-900">
                      {item.district_label ?? "—"}
                    </td>

                    <td className="py-3 align-middle">
                      {gap !== null ? (
                        <span
                          className={`rounded px-2 py-0.5 font-mono text-xs font-semibold ${
                            isCritical
                              ? "border border-verdict-fail/20 bg-verdict-fail/10 text-verdict-fail"
                              : "bg-ink-900/5 text-ink-900"
                          }`}
                        >
                          {(gap * 100).toFixed(1)}%
                        </span>
                      ) : (
                        <span className="font-mono text-xs text-ink-600/60">—</span>
                      )}
                    </td>

                    <td className="py-3 align-middle font-mono text-xs text-ink-600">
                      <span className="flex items-center gap-1">
                        <Clock size={12} className="text-ink-600/60" aria-hidden />
                        {timeAgo(item.created_at)}
                      </span>
                    </td>

                    <td className="py-3 pr-4 text-right align-middle">
                      <Link
                        href={`/queue/${item.scan_id}`}
                        className="inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-card bg-ink-900 px-3 py-1.5 font-body text-xs font-semibold text-white transition-colors hover:bg-ink-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500"
                        aria-label={`Review ${item.product_name ?? "scan"} ${shortId(item.scan_id)}`}
                      >
                        Review
                        <ArrowRight size={12} aria-hidden />
                      </Link>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        busy={loading || refreshing}
        itemLabel="scans"
      />
    </AppShell>
  );
}
