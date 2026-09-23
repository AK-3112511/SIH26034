"use client";

interface PaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  /** Disables both buttons while a fetch is in flight. */
  busy?: boolean;
  /** Plural noun for the count, e.g. "notices". */
  itemLabel?: string;
}

/**
 * Previous/next pager. Four near-identical copies existed; two of them could
 * page past the end because they compared against the item count rather than
 * the page count.
 */
export function Pagination({
  page,
  total,
  pageSize,
  onPageChange,
  busy = false,
  itemLabel = "records",
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  return (
    <nav className="mt-4 flex items-center justify-between" aria-label="Pagination">
      <span className="font-body text-xs text-ink-600">
        Page {page} of {totalPages} · {total} {itemLabel}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1 || busy}
          className="btn-secondary min-h-[36px] px-3 py-1 text-xs"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages || busy}
          className="btn-secondary min-h-[36px] px-3 py-1 text-xs"
        >
          Next
        </button>
      </div>
    </nav>
  );
}
