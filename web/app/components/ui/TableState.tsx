"use client";

interface TableStateProps {
  colSpan: number;
  loading: boolean;
  isEmpty: boolean;
  loadingLabel?: string;
  emptyTitle?: string;
  emptyHint?: string;
}

/**
 * The loading and empty rows for a data table.
 *
 * Returns null when there is data to show, so a table body reads:
 *   <TableState … /> {items.map(…)}
 * and a background refresh keeps the existing rows on screen instead of
 * replacing them with a spinner.
 */
export function TableState({
  colSpan,
  loading,
  isEmpty,
  loadingLabel = "Loading…",
  emptyTitle = "Nothing to show",
  emptyHint,
}: TableStateProps) {
  if (loading) {
    return (
      <tr>
        <td colSpan={colSpan} className="py-16 text-center">
          <span className="animate-pulse font-mono text-sm text-ink-600">{loadingLabel}</span>
        </td>
      </tr>
    );
  }

  if (isEmpty) {
    return (
      <tr>
        <td colSpan={colSpan} className="py-16 text-center">
          <div className="mx-auto max-w-md">
            <p className="font-display text-base font-semibold text-ink-900">{emptyTitle}</p>
            {emptyHint && <p className="mt-1 font-body text-xs text-ink-600">{emptyHint}</p>}
          </div>
        </td>
      </tr>
    );
  }

  return null;
}
