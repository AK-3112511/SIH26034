"use client";
/**
 * Digital Repository — compliance history grouped by manufacturer.
 *
 * Scans are grouped by the manufacturer named on the label, which is the
 * identity the extraction pipeline actually records. The search box now also
 * matches the brand name captured with a scan, so looking up the name printed
 * largest on the packet finds the company that packed it. There is still no
 * barcode: nothing in the pipeline reads one, and inventing the field would
 * mean a search that silently returns nothing.
 */
import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
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
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import { Pagination } from "@/app/components/ui/Pagination";
import { TableState } from "@/app/components/ui/TableState";
import { productsApi, type ProductSearchResult } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { shortId, timeAgo } from "@/lib/format";

const TREND_CONFIG: Record<
  ProductSearchResult["trend"],
  { icon: typeof TrendingUp; label: string; className: string }
> = {
  IMPROVING: {
    icon: TrendingUp,
    label: "Improving",
    className: "text-verdict-pass bg-verdict-pass/10 border-verdict-pass/20",
  },
  WORSENING: {
    icon: TrendingDown,
    label: "Worsening",
    className: "text-verdict-fail bg-verdict-fail/10 border-verdict-fail/20",
  },
  STABLE: {
    icon: Minus,
    label: "Stable",
    className: "text-ink-600 bg-ink-900/5 border-ink-900/10",
  },
  INSUFFICIENT_DATA: {
    icon: Minus,
    label: "Too few scans",
    className: "text-ink-600/60 bg-ink-900/5 border-ink-900/10",
  },
};

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 350;

function TrendBadge({ trend }: { trend: ProductSearchResult["trend"] }) {
  const cfg = TREND_CONFIG[trend];
  const Icon = cfg.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-xs font-semibold ${cfg.className}`}
    >
      <Icon size={12} aria-hidden />
      {cfg.label}
    </span>
  );
}

export default function RepositoryPage() {
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProductSearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    const id = setTimeout(() => {
      setQuery(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchInput]);

  const fetchResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await productsApi.search({
        q: query || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setResults(data.results);
      setTotal(data.total);
    } catch (err) {
      setError(apiErrorMessage(err, "The repository could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [query, page]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  return (
    <AppShell>
      <div className="mb-2">
        <h1 className="font-display text-2xl font-bold text-ink-900">Repository</h1>
        <p className="mt-1 font-body text-sm text-ink-600">
          Every scan of every product, grouped by the manufacturer named on the label.
        </p>
      </div>

      <CalibrationRuler className="mb-6" />

      <div className="card-surface mb-2">
        <label htmlFor="repository-search" className="sr-only">
          Search by manufacturer or brand
        </label>
        <div className="relative">
          <Search
            size={15}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-600/60"
            aria-hidden
          />
          <input
            id="repository-search"
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by manufacturer or brand"
            className="form-input min-h-[40px] w-full py-1.5 pl-9 pr-3 text-sm"
          />
        </div>
      </div>
      <p className="mb-6 px-1 font-body text-xs text-ink-600/70">
        Barcode search is not available: no barcode is read from the package.
      </p>

      <ErrorBanner className="mb-6" message={error} onRetry={fetchResults} />

      <div className="card-surface overflow-x-auto p-0 shadow-sm">
        <table className="data-table w-full">
          <caption className="sr-only">Compliance history by manufacturer</caption>
          <thead>
            <tr>
              <th scope="col" className="w-8 py-3 pl-4">
                <span className="sr-only">Expand</span>
              </th>
              <th scope="col" className="py-3">
                Manufacturer
              </th>
              <th scope="col" className="py-3 text-center">
                Scans
              </th>
              <th scope="col" className="py-3 text-center">
                Passed
              </th>
              <th scope="col" className="py-3 text-center">
                Failed
              </th>
              <th scope="col" className="py-3 text-center">
                Pending
              </th>
              <th scope="col" className="py-3">
                Trend
              </th>
              <th scope="col" className="py-3 pr-4">
                Last scan
              </th>
            </tr>
          </thead>
          <tbody>
            <TableState
              colSpan={8}
              loading={loading}
              isEmpty={results.length === 0}
              loadingLabel="Searching…"
              emptyTitle="No manufacturers found"
              emptyHint={
                query
                  ? "No manufacturer or brand matches that search."
                  : "No scan has a manufacturer name on it yet."
              }
            />

            {!loading &&
              results.map((product) => {
                const isExpanded = expanded === product.manufacturer_name;
                return (
                  <Fragment key={product.manufacturer_name}>
                    <tr>
                      <td className="py-3 pl-4 align-middle">
                        <button
                          type="button"
                          onClick={() =>
                            setExpanded(isExpanded ? null : product.manufacturer_name)
                          }
                          aria-label={`${isExpanded ? "Hide" : "Show"} scans for ${product.manufacturer_name}`}
                          aria-expanded={isExpanded}
                          className="rounded text-ink-600 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500"
                        >
                          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                      </td>
                      <td className="py-3 align-middle">
                        <span className="block font-body text-sm font-semibold text-ink-900">
                          {product.manufacturer_name}
                        </span>
                        {product.product_names.length > 0 && (
                          <span className="mt-0.5 block font-body text-xs text-ink-600">
                            {product.product_names.slice(0, 3).join(", ")}
                            {product.product_names.length > 3 &&
                              ` and ${product.product_names.length - 3} more`}
                          </span>
                        )}
                      </td>
                      <td className="py-3 text-center align-middle font-mono text-xs text-ink-900">
                        {product.total_scans}
                      </td>
                      <td className="py-3 text-center align-middle font-mono text-xs text-verdict-pass">
                        {product.passed_count}
                      </td>
                      <td className="py-3 text-center align-middle font-mono text-xs text-verdict-fail">
                        {product.failed_count}
                      </td>
                      <td className="py-3 text-center align-middle font-mono text-xs text-verdict-pending">
                        {product.pending_review_count}
                      </td>
                      <td className="py-3 align-middle">
                        <TrendBadge trend={product.trend} />
                      </td>
                      <td className="py-3 pr-4 align-middle font-mono text-xs text-ink-600">
                        {timeAgo(product.last_scan_at)}
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr>
                        <td colSpan={8} className="bg-paper-100 px-4 py-3">
                          <p className="mb-2 font-body text-xs font-semibold uppercase tracking-wider text-ink-600">
                            Showing {product.scans.length} of {product.total_scans} scans
                          </p>
                          <div className="flex flex-col gap-1.5">
                            {product.scans.map((scan) => (
                              <Link
                                key={scan.scan_id}
                                href={`/queue/${scan.scan_id}`}
                                className="flex items-center gap-3 rounded px-2 py-1.5 transition-colors hover:bg-paper-000 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass-500"
                              >
                                <SealBadge verdict={scan.status as VerdictStatus} size={24} />
                                <span className="w-20 font-mono text-xs text-ink-600">
                                  {timeAgo(scan.captured_at_utc ?? scan.created_at)}
                                </span>
                                <span className="flex-1 font-body text-xs text-ink-900">
                                  {scan.district_label ?? "Location not recorded"}
                                </span>
                                <span className="flex items-center gap-1 font-mono text-[10px] text-ink-600/60">
                                  <Package size={11} aria-hidden />
                                  {shortId(scan.scan_id)}
                                </span>
                              </Link>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
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
        busy={loading}
        itemLabel="manufacturers"
      />
    </AppShell>
  );
}
