"use client";
/**
 * §3 Screen 10 — Audit Log (Phase 6.5)
 * Read-only trail of who reviewed/overrode what, when — separate from the
 * compliance data itself per §12. No edit/delete actions by design; the
 * backend exposes no write endpoint on this path at all.
 */
import { Fragment, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { AdminGuard } from "@/app/components/ui/AdminGuard";
import { adminAuditLogApi, type AuditLogEntry } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function AuditLogScreen() {
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const [targetTypeFilter, setTargetTypeFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");

  const PAGE_SIZE = 50;

  const fetchLog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await adminAuditLogApi.list({
        target_type: targetTypeFilter.trim() || undefined,
        action: actionFilter.trim() || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(apiErrorMessage(err, "The audit record could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [targetTypeFilter, actionFilter, page]);

  useEffect(() => {
    fetchLog();
  }, [fetchLog]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AppShell>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900">Audit Log</h1>
          <p className="font-body text-sm text-ink-600 mt-1">
            Read-only trail of who changed what, when. No edit or delete actions exist on this
            screen — the log itself is append-only.
          </p>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

      <div className="card-surface mb-6 flex flex-col md:flex-row gap-4">
        <div className="flex-1">
          <label htmlFor="filter-target-type" className="form-label">
            Target Type
          </label>
          <input
            id="filter-target-type"
            type="text"
            value={targetTypeFilter}
            onChange={(e) => {
              setTargetTypeFilter(e.target.value);
              setPage(1);
            }}
            placeholder="e.g. scan, user, ruleset"
            className="form-input text-xs py-1.5 min-h-[40px]"
          />
        </div>
        <div className="flex-1">
          <label htmlFor="filter-action" className="form-label">
            Action
          </label>
          <input
            id="filter-action"
            type="text"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(1);
            }}
            placeholder="e.g. USER_LOGIN_SUCCESS"
            className="form-input font-mono text-xs py-1.5 min-h-[40px]"
          />
        </div>
      </div>

      <ErrorBanner className="mb-6" message={error} />

      <div className="card-surface p-0 overflow-x-auto shadow-sm">
        <table className="data-table w-full" aria-label="Audit log entries">
          <thead>
            <tr>
              <th className="w-8 pl-4 py-3">
                <span className="sr-only">Expand</span>
              </th>
              <th className="py-3 font-semibold">Timestamp</th>
              <th className="py-3 font-semibold">Actor</th>
              <th className="py-3 font-semibold">Action</th>
              <th className="py-3 pr-4 font-semibold">Target</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="py-16 text-center">
                  <span className="font-mono text-sm text-ink-600 animate-pulse">
                    Loading audit trail…
                  </span>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-16 text-center">
                  <p className="font-display text-base font-semibold text-ink-900">
                    No matching entries
                  </p>
                </td>
              </tr>
            ) : (
              items.map((entry) => {
                const isExpanded = expanded === entry.id;
                const hasDetail = entry.detail && Object.keys(entry.detail).length > 0;
                return (
                  <Fragment key={entry.id}>
                    <tr
                      className={`hover:bg-ink-900/[0.03] transition-colors ${hasDetail ? "cursor-pointer" : ""}`}
                      onClick={() => hasDetail && setExpanded(isExpanded ? null : entry.id)}
                    >
                      <td className="pl-4 py-3 align-middle">
                        {hasDetail && (
                          <button
                            type="button"
                            aria-label={isExpanded ? "Collapse detail" : "Expand detail"}
                            aria-expanded={isExpanded}
                            className="text-ink-600 hover:text-ink-900"
                          >
                            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </button>
                        )}
                      </td>
                      <td className="py-3 align-middle font-mono text-xs text-ink-600 whitespace-nowrap">
                        {formatTimestamp(entry.timestamp)}
                      </td>
                      <td className="py-3 align-middle font-body text-xs text-ink-900">
                        {entry.actor_username ?? (
                          <span className="text-ink-600/60 italic">system</span>
                        )}
                      </td>
                      <td className="py-3 align-middle font-mono text-xs font-semibold text-ink-900">
                        {entry.action}
                      </td>
                      <td className="pr-4 py-3 align-middle font-mono text-xs text-ink-600">
                        {entry.target_type}
                        {entry.target_id && (
                          <span className="text-ink-600/60">
                            {" "}
                            #{entry.target_id.slice(0, 8)}
                          </span>
                        )}
                      </td>
                    </tr>
                    {isExpanded && hasDetail && (
                      <tr>
                        <td colSpan={5} className="bg-paper-100 px-4 py-3">
                          <pre className="font-mono text-xs text-ink-600 whitespace-pre-wrap break-all">
                            {JSON.stringify(entry.detail, null, 2)}
                          </pre>
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
            Page {page} of {totalPages} ({total} total entries)
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

export default function AdminAuditLogPage() {
  return (
    <AdminGuard>
      <AuditLogScreen />
    </AdminGuard>
  );
}
