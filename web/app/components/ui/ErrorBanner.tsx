"use client";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBannerProps {
  /** Null or empty renders nothing, so callers can drop this in unconditionally. */
  message: string | null;
  /** Short heading; defaults to a neutral one. */
  title?: string;
  /** When given, a Retry button is shown. */
  onRetry?: () => void;
  className?: string;
}

/**
 * The single error presentation for the dashboard. Replaces nine hand-rolled
 * banners, three of which were built from inline `style` objects and so did
 * not follow the verdict colour tokens.
 */
export function ErrorBanner({ message, title, onRetry, className = "" }: ErrorBannerProps) {
  if (!message) return null;

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-card border border-verdict-fail/30 bg-verdict-fail/5 p-3 ${className}`}
    >
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-verdict-fail" aria-hidden />
      <div className="min-w-0 flex-1">
        {title && (
          <p className="font-body text-sm font-semibold text-verdict-fail">{title}</p>
        )}
        <p className="font-body text-xs text-ink-900">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-card border border-verdict-fail/40 px-2.5 py-1 font-body text-xs font-semibold text-verdict-fail transition-colors hover:bg-verdict-fail/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500"
        >
          <RefreshCw size={13} aria-hidden />
          Retry
        </button>
      )}
    </div>
  );
}
