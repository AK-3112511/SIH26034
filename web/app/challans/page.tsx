"use client";
/**
 * Section 39 notice archive — every statutory notice issued, newest first.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Clock, Download, FileText, ShieldAlert } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import { Pagination } from "@/app/components/ui/Pagination";
import { TableState } from "@/app/components/ui/TableState";
import { challansApi, type ChallanResponse } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { shortId, timeAgo } from "@/lib/format";

const PAGE_SIZE = 20;

export default function ChallansArchivePage() {
  const [items, setItems] = useState<ChallanResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchChallans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await challansApi.list({ page, page_size: PAGE_SIZE });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(apiErrorMessage(err, "The notice archive could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchChallans();
  }, [fetchChallans]);

  return (
    <AppShell>
      <div className="mb-2 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900">
            Section 39 notices
          </h1>
          <p className="mt-1 font-body text-sm text-ink-600">
            {loading ? "Loading…" : `${total} notice${total === 1 ? "" : "s"} issued`}
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-card border border-ink-900/[0.08] bg-paper-000 px-3 py-2 font-body text-xs text-ink-600 shadow-sm">
          <ShieldAlert size={14} className="shrink-0 text-brass-500" aria-hidden />
          <span>
            <strong>Fixed record.</strong> Each notice carries the hash of the PDF as issued.
          </span>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

      <ErrorBanner className="mb-6" message={error} onRetry={fetchChallans} />

      <div className="card-surface overflow-x-auto p-0 shadow-sm">
        <table className="data-table w-full">
          <caption className="sr-only">Section 39 notices issued</caption>
          <thead>
            <tr>
              <th scope="col" className="w-12 py-3 pl-4 text-center">
                <FileText size={16} className="inline text-ink-600" aria-label="Notice" />
              </th>
              <th scope="col" className="py-3">
                Notice / scan
              </th>
              <th scope="col" className="py-3">
                Issued by
              </th>
              <th scope="col" className="py-3">
                PDF hash
              </th>
              <th scope="col" className="py-3">
                Issued
              </th>
              <th scope="col" className="py-3 pr-4 text-right">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            <TableState
              colSpan={6}
              loading={loading}
              isEmpty={items.length === 0}
              loadingLabel="Loading the archive…"
              emptyTitle="No notices issued"
              emptyHint="A Section 39 notice appears here once one is issued from a non-compliant scan."
            />

            {!loading &&
              items.map((item) => (
                <tr key={item.challan_id}>
                  <td className="py-3 pl-4 text-center align-middle">
                    <FileText size={18} className="text-brass-500" aria-hidden />
                  </td>

                  <td className="py-3 align-middle">
                    <span className="block font-mono text-sm font-semibold leading-tight text-ink-900">
                      {shortId(item.challan_id)}
                    </span>
                    <span className="mt-0.5 block font-mono text-xs text-ink-600">
                      Scan {shortId(item.scan_id)}
                    </span>
                  </td>

                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    {shortId(item.lmo_id)}
                  </td>

                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    <span className="block max-w-[150px] truncate rounded border border-ink-900/10 bg-ink-900/5 px-2 py-0.5">
                      {item.pdf_hash ?? "not recorded"}
                    </span>
                  </td>

                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    <span className="flex items-center gap-1">
                      <Clock size={12} className="text-ink-600/60" aria-hidden />
                      {timeAgo(item.generated_at)}
                    </span>
                  </td>

                  <td className="space-x-2 py-3 pr-4 text-right align-middle">
                    <Link
                      href={`/queue/${item.scan_id}`}
                      className="inline-flex items-center justify-center gap-1.5 font-body text-xs font-semibold text-ink-600 transition-colors hover:text-ink-900"
                    >
                      Scan
                      <ArrowRight size={12} aria-hidden />
                    </Link>
                    {item.pdf_url && (
                      <a
                        href={item.pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-card bg-ink-900 px-3 py-1.5 font-body text-xs font-semibold text-white transition-colors hover:bg-ink-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500"
                        aria-label={`Open the notice ${shortId(item.challan_id)}`}
                      >
                        <Download size={14} aria-hidden />
                        PDF
                      </a>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <Pagination
        page={page}
        total={total}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        busy={loading}
        itemLabel="notices"
      />
    </AppShell>
  );
}
