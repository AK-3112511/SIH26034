/**
 * One place that turns an unknown thrown value into a sentence an enforcement
 * officer can act on.
 *
 * Nine separate `catch` blocks used to reach into
 * `err.response.data.detail` by hand, each with a different fallback string,
 * and several of them displayed a raw stack-adjacent message.
 */

interface ApiErrorShape {
  response?: {
    status?: number;
    data?: { detail?: unknown };
  };
  code?: string;
  message?: string;
}

/** FastAPI returns `detail` as a string, or as a list of validation objects. */
function readDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => (typeof d === "object" && d !== null ? (d as { msg?: unknown }).msg : null))
      .filter((m): m is string => typeof m === "string");
    if (messages.length) return messages.join("; ");
  }
  return null;
}

/**
 * @param fallback what to say when the server gave us nothing usable —
 *                 phrase it as what failed, not as "an error occurred".
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const err = error as ApiErrorShape;

  const detail = readDetail(err?.response?.data?.detail);
  if (detail) return detail;

  const status = err?.response?.status;
  if (status === 403) return "Your account does not have permission for this action.";
  if (status === 404) return "That record no longer exists.";
  if (status === 409) return "This action has already been taken.";
  if (status && status >= 500) return "The server could not complete the request. Try again shortly.";

  // No response at all: the request never reached the backend.
  if (!err?.response) {
    return "Could not reach the server. Check that the backend is running and try again.";
  }

  return fallback;
}
