"use client";
import { useEffect, useState } from "react";
import { UserPlus, X } from "lucide-react";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import type { FieldOfficer } from "@/lib/api";

interface AssignTaskDialogProps {
  open: boolean;
  officers: FieldOfficer[];
  loadingOfficers: boolean;
  /** Non-null when the officer directory could not be read. */
  officersError: string | null;
  onRetryOfficers: () => void;
  assigning: boolean;
  assignError: string | null;
  defaultInstructions: string;
  onAssign: (officerId: string, instructions: string) => void;
  onClose: () => void;
}

/**
 * Sends a failed scan to a field officer for on-site verification.
 *
 * Two things were wrong here and both were invisible on screen. The dialog was
 * styled with Tailwind tokens that do not exist in this project
 * (`bg-surface`, `border-border`, `text-text-*`), so it rendered as
 * transparent text over the page behind it. And when the officer directory
 * failed to load, the catch block substituted a hard-coded person — a real
 * name, a real-looking district and a fabricated id — so a reviewer could
 * dispatch a task to somebody who does not exist. An empty directory now says
 * so and offers a retry.
 */
export function AssignTaskDialog({
  open,
  officers,
  loadingOfficers,
  officersError,
  onRetryOfficers,
  assigning,
  assignError,
  defaultInstructions,
  onAssign,
  onClose,
}: AssignTaskDialogProps) {
  const [selectedOfficerId, setSelectedOfficerId] = useState("");
  const [instructions, setInstructions] = useState(defaultInstructions);

  useEffect(() => {
    if (open) setInstructions(defaultInstructions);
  }, [open, defaultInstructions]);

  useEffect(() => {
    if (officers.length > 0 && !officers.some((o) => o.id === selectedOfficerId)) {
      setSelectedOfficerId(officers[0].id);
    }
    if (officers.length === 0 && selectedOfficerId) {
      setSelectedOfficerId("");
    }
  }, [officers, selectedOfficerId]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !assigning) onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, assigning, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="assign-dialog-title"
      data-testid="assign-officer-modal"
    >
      <div className="w-full max-w-lg space-y-4 rounded-card border border-ink-900/10 bg-paper-000 p-5 shadow-2xl">
        <div className="flex items-center justify-between border-b border-ink-900/10 pb-3">
          <div className="flex items-center gap-2">
            <UserPlus size={20} className="text-brass-500" aria-hidden />
            <h2 id="assign-dialog-title" className="font-display text-base font-semibold text-ink-900">
              Assign a field officer
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={assigning}
            aria-label="Close"
            className="rounded p-1 text-ink-600 transition-colors hover:bg-ink-900/5 hover:text-ink-900"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label htmlFor="assign-officer" className="form-label">
              Field officer
            </label>
            {loadingOfficers ? (
              <p className="py-2 font-body text-xs text-ink-600">Loading the officer directory…</p>
            ) : officersError ? (
              <ErrorBanner message={officersError} onRetry={onRetryOfficers} />
            ) : officers.length === 0 ? (
              <p className="py-2 font-body text-xs text-ink-900">
                No active field officers are listed for this jurisdiction. An administrator can add
                one on the Users screen.
              </p>
            ) : (
              <select
                id="assign-officer"
                value={selectedOfficerId}
                onChange={(e) => setSelectedOfficerId(e.target.value)}
                className="form-input"
                data-testid="field-officer-select"
              >
                {officers.map((officer) => (
                  <option key={officer.id} value={officer.id}>
                    {officer.full_name} — {officer.district ?? "no district recorded"}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label htmlFor="assign-instructions" className="form-label">
              Instructions for the officer
            </label>
            <textarea
              id="assign-instructions"
              rows={3}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="form-input py-2"
              placeholder="What to verify on site, and what notice to serve."
            />
            <p className="mt-1 font-body text-xs text-ink-600">
              These instructions reach the officer on their handset with the task.
            </p>
          </div>

          <ErrorBanner message={assignError} />
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-ink-900/10 pt-3">
          <button
            type="button"
            onClick={onClose}
            disabled={assigning}
            className="btn-secondary min-h-[40px] px-4 py-2 text-xs"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onAssign(selectedOfficerId, instructions.trim())}
            disabled={assigning || !selectedOfficerId}
            className="btn-primary min-h-[40px] px-4 py-2 text-xs"
            data-testid="confirm-assignment-button"
          >
            {assigning ? "Assigning…" : "Assign task"}
          </button>
        </div>
      </div>
    </div>
  );
}
