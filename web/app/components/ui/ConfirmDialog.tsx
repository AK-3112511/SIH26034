"use client";
import { useEffect, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  /** Say plainly what will happen and that it is on the record. */
  body: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  /** Styles the confirm button as a destructive/legal action. */
  tone?: "default" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Confirmation step for actions that cannot be taken back: recording a
 * verdict, issuing a Section 39 notice, dispatching a field officer. Each of
 * those was previously a single unguarded click.
 */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "default",
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="w-full max-w-md space-y-4 rounded-card border border-ink-900/10 bg-paper-000 p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-ink-900/10 pb-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle
              size={20}
              className={tone === "danger" ? "mt-0.5 shrink-0 text-verdict-fail" : "mt-0.5 shrink-0 text-brass-500"}
              aria-hidden
            />
            <h2 id="confirm-dialog-title" className="font-display text-base font-semibold text-ink-900">
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            aria-label="Close"
            className="rounded p-1 text-ink-600 transition-colors hover:bg-ink-900/5 hover:text-ink-900"
          >
            <X size={18} />
          </button>
        </div>

        <div className="font-body text-sm text-ink-900">{body}</div>

        <div className="flex items-center justify-end gap-3 border-t border-ink-900/10 pt-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-secondary min-h-[40px] px-4 py-2 text-xs"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={
              tone === "danger"
                ? "inline-flex min-h-[40px] items-center justify-center gap-2 rounded-card bg-verdict-fail px-4 py-2 font-body text-xs font-semibold text-white transition-colors hover:bg-verdict-fail/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
                : "btn-primary min-h-[40px] px-4 py-2 text-xs"
            }
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
