"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  FileText,
  AlertCircle,
  Clock,
  ArrowRight,
  ShieldAlert,
  Download,
} from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { challansApi, type ChallanResponse } from "@/lib/api";

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const m = Math.floor(diff / 60000);
  const h = Math.floor(diff / 3600000);
  if (m < 60) return `${Math.max(1, m)}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function ChallansArchivePage() {
  const [items, setItems] = useState<ChallanResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const PAGE_SIZE = 20;

  const fetchChallans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await challansApi.list({
        page,
        page_size: PAGE_SIZE,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load challans archive. Please verify backend connection.");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchChallans();
  }, [fetchChallans]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AppShell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-2">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-2xl font-bold text-ink-900 tracking-tight">
              Section 39 Challan Archive
            </h1>
          </div>
          <p className="font-body text-sm text-ink-600 mt-1">
            {loading ? "Refreshing archive…" : `${total} legally generated challan${total !== 1 ? "s" : ""}`}
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-2 rounded-[4px] bg-paper-000 border border-ink-900/[0.08] text-xs font-body text-ink-600 shadow-sm">
          <ShieldAlert size={14} className="text-brass-500 flex-shrink-0" aria-hidden />
          <span>
            <strong>Immutable Record:</strong> All challans are secured with PDF hashing.
          </span>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

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

      <div className="card-surface p-0 overflow-x-auto shadow-sm">
        <table className="data-table w-full" aria-label="Generated Challans">
          <thead>
            <tr>
              <th className="pl-4 py-3 font-semibold w-12 text-center">
                <FileText size={16} className="text-ink-600 inline" />
              </th>
              <th className="py-3 font-semibold">Challan ID / Scan ID</th>
              <th className="py-3 font-semibold">Officer ID</th>
              <th className="py-3 font-semibold">PDF Hash</th>
              <th className="py-3 font-semibold">Age</th>
              <th className="py-3 pr-4 text-right font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="py-16 text-center">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <span className="font-mono text-sm text-ink-600 animate-pulse">
                      Retrieving challans archive…
                    </span>
                  </div>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-16 text-center">
                  <div className="max-w-md mx-auto">
                    <p className="font-display text-base font-semibold text-ink-900">
                      No challans found
                    </p>
                    <p className="font-body text-xs text-ink-600 mt-1">
                      No Section 39 challans have been generated yet.
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.challan_id} className="hover:bg-ink-900/[0.03] transition-colors">
                  <td className="pl-4 py-3 align-middle text-center">
                    <FileText size={18} className="text-brass-500" />
                  </td>

                  <td className="py-3 align-middle">
                    <div>
                      <span className="font-mono text-sm font-semibold text-ink-900 block leading-tight">
                        {item.challan_id.slice(0, 8)}…{item.challan_id.slice(-4)}
                      </span>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="font-mono text-xs text-ink-600">
                          Scan: {item.scan_id.slice(0, 8)}…
                        </span>
                      </div>
                    </div>
                  </td>

                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    {item.lmo_id ? `${item.lmo_id.slice(0, 8)}…` : "—"}
                  </td>

                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    <div className="flex items-center gap-1.5">
                      <span className="bg-ink-900/5 px-2 py-0.5 rounded border border-ink-900/10 truncate max-w-[150px]">
                        {item.pdf_hash ?? "N/A"}
                      </span>
                    </div>
                  </td>

                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    <div className="flex items-center gap-1">
                      <Clock size={12} className="text-ink-600/60" aria-hidden />
                      <span>{timeAgo(item.generated_at)}</span>
                    </div>
                  </td>

                  <td className="pr-4 py-3 align-middle text-right space-x-2">
                    <Link
                      href={`/queue/${item.scan_id}`}
                      className="inline-flex items-center justify-center gap-1.5 font-body text-xs font-semibold text-ink-600 hover:text-ink-900 transition-colors"
                      title="View original scan details"
                    >
                      <span>Scan Details</span>
                      <ArrowRight size={12} />
                    </Link>
                    {item.pdf_url && (
                      <a
                        href={item.pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="
                          inline-flex items-center justify-center gap-1.5
                          bg-ink-900 text-white font-body text-xs font-semibold
                          px-3 py-1.5 rounded-[4px] min-h-[36px]
                          transition-colors hover:bg-ink-600
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500
                        "
                        aria-label={`Download PDF for ${item.challan_id.slice(0, 8)}`}
                      >
                        <Download size={14} />
                        <span>PDF</span>
                      </a>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="font-body text-xs text-ink-600">
            Page {page} of {totalPages} ({total} total)
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
