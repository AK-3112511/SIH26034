/**
 * Shared formatting helpers.
 *
 * `timeAgo` previously existed in three separate copies (queue, repository,
 * challans) which had drifted apart — one of them reported "0m ago" for a scan
 * that had just arrived while another reported "1m ago".
 */

/** Human-readable age of an ISO-8601 timestamp, e.g. "2h ago". */
export function timeAgo(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  const then = new Date(isoString).getTime();
  if (Number.isNaN(then)) return "—";

  const diffMs = Date.now() - then;
  if (diffMs < 0) return "just now";

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Date only, in the officer's locale, e.g. "23 Sep 2026". */
export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Date and time, e.g. "23 Sep 2026, 14:05". */
export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "—";
  return `${formatDate(isoString)}, ${d.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })}`;
}

/**
 * First 8 characters of an identifier, for display only.
 * Clamped: a short or empty id must not throw in a table cell.
 */
export function shortId(id: string | null | undefined, length = 8): string {
  if (!id) return "—";
  return id.length <= length ? id : id.slice(0, length);
}

/** Coordinate pair for display, or a dash when the scan has no location. */
export function formatCoords(lat: number | null, lng: number | null): string {
  if (lat === null || lng === null) return "—";
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}
