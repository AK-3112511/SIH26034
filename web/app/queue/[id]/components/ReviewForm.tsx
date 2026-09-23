"use client";
import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, FileText, Info } from "lucide-react";
import { ConfirmDialog } from "@/app/components/ui/ConfirmDialog";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import type { ChallanResponse, RuleResult, ScanStatus } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { ruleMeta } from "./rules";

export type ReviewDecision = "PASSED" | "FAILED";

interface ReviewFormProps {
  ruleResults: RuleResult[];
  scanStatus: ScanStatus;
  /** A note already on the record, shown so the reviewer can build on it. */
  existingNote: string | null;
  overrideCount: number;
  submitting: boolean;
  submitError: string | null;
  submitSuccess: string | null;
  onSubmit: (decision: ReviewDecision, note: string) => void;
  /** The Section 39 notice already issued for this scan, if there is one. */
  existingChallan: ChallanResponse | null;
  generatingChallan: boolean;
  challanError: string | null;
  onGenerateChallan: () => void;
}

/**
 * The reviewer decision that sets the legal outcome of a scan.
 *
 * The verdict defaults to what the engine found rather than to PASSED: a scan
 * that reached review carrying a failing rule should not be one careless click
 * away from being cleared. The verdict and the notice each require a
 * confirmation step, because neither can be taken back.
 */
export function ReviewForm({
  ruleResults,
  scanStatus,
  existingNote,
  overrideCount,
  submitting,
  submitError,
  submitSuccess,
  onSubmit,
  existingChallan,
  generatingChallan,
  challanError,
  onGenerateChallan,
}: ReviewFormProps) {
  const failingRules = useMemo(
    () => ruleResults.filter((r) => r.status === "FAIL"),
    [ruleResults]
  );
  const unverifiedRules = useMemo(
    () => ruleResults.filter((r) => r.status === "UNVERIFIED"),
    [ruleResults]
  );

  const suggested: ReviewDecision = failingRules.length > 0 ? "FAILED" : "PASSED";

  const [decision, setDecision] = useState<ReviewDecision>(suggested);
  const [note, setNote] = useState(existingNote ?? "");
  const [confirming, setConfirming] = useState(false);
  const [confirmingChallan, setConfirmingChallan] = useState(false);
  const [noteTouched, setNoteTouched] = useState(false);
  const [decisionTouched, setDecisionTouched] = useState(false);

  // Track the engine until the reviewer makes a choice of their own.
  useEffect(() => {
    if (!decisionTouched) setDecision(suggested);
  }, [suggested, decisionTouched]);

  const noteMissing = !note.trim();
  const canGenerateChallan = scanStatus === "FAILED";

  return (
    <section className="space-y-4 border-t border-ink-900/10 pt-4" aria-labelledby="review-heading">
      <h2 id="review-heading" className="font-display text-base font-semibold text-ink-900">
        Reviewer decision
      </h2>

      {failingRules.length > 0 && (
        <div className="flex items-start gap-2 rounded-card border border-verdict-fail/20 bg-verdict-fail/5 p-3">
          <Info size={16} className="mt-0.5 shrink-0 text-verdict-fail" aria-hidden />
          <p className="font-body text-xs text-ink-900">
            The engine found{" "}
            <strong>
              {failingRules.length} breach{failingRules.length === 1 ? "" : "es"}
            </strong>
            : {failingRules.map((r) => ruleMeta(r.rule_id).section).join(", ")}. The verdict below
            is set accordingly. Change it only if you disagree, and say why.
          </p>
        </div>
      )}

      {unverifiedRules.length > 0 && (
        <div className="flex items-start gap-2 rounded-card border border-verdict-pending/20 bg-verdict-pending/5 p-3">
          <Info size={16} className="mt-0.5 shrink-0 text-verdict-pending" aria-hidden />
          <p className="font-body text-xs text-ink-900">
            {unverifiedRules.length} rule{unverifiedRules.length === 1 ? "" : "s"} could not be
            verified automatically and {unverifiedRules.length === 1 ? "needs" : "need"} your
            judgement: {unverifiedRules.map((r) => ruleMeta(r.rule_id).section).join(", ")}.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label htmlFor="decision-select" className="form-label">
            Verdict
          </label>
          <select
            id="decision-select"
            value={decision}
            onChange={(e) => {
              setDecisionTouched(true);
              setDecision(e.target.value as ReviewDecision);
            }}
            className="form-input"
            disabled={submitting}
          >
            <option value="PASSED">Compliant with PCR 2011</option>
            <option value="FAILED">Not compliant</option>
          </select>
        </div>

        <div>
          <label htmlFor="reviewer-note" className="form-label">
            Reason for the decision (required)
          </label>
          <textarea
            id="reviewer-note"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => setNoteTouched(true)}
            placeholder="State the statutory basis for this verdict, and explain any corrections you made."
            className={`form-input py-2 ${noteTouched && noteMissing ? "form-input-error" : ""}`}
            aria-describedby="reviewer-note-hint"
            aria-invalid={noteTouched && noteMissing}
            disabled={submitting}
          />
          <p id="reviewer-note-hint" className="mt-1 font-body text-xs text-ink-600">
            This note is written to the audit record under your name.
          </p>
        </div>
      </div>

      {overrideCount > 0 && (
        <p className="font-body text-xs text-ink-600">
          {overrideCount} field correction{overrideCount === 1 ? "" : "s"} will be submitted with
          this decision.
        </p>
      )}

      <ErrorBanner message={submitError} />
      {submitSuccess && (
        <div
          role="status"
          className="flex items-start gap-2 rounded-card border border-verdict-pass/30 bg-verdict-pass/5 p-3"
        >
          <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-verdict-pass" aria-hidden />
          <p className="font-body text-xs text-ink-900">{submitSuccess}</p>
        </div>
      )}

      <div className="flex flex-col items-stretch gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={() => {
            setNoteTouched(true);
            if (!noteMissing) setConfirming(true);
          }}
          disabled={submitting || noteMissing}
          className="btn-primary w-full sm:w-auto"
        >
          {submitting ? "Recording decision…" : "Record verdict"}
        </button>

        <div className="flex flex-col items-stretch gap-2 sm:items-end">
          {existingChallan ? (
            <div className="sm:text-right">
              <p className="font-body text-xs text-ink-600">
                Section 39 notice issued {formatDateTime(existingChallan.generated_at)}
              </p>
              {existingChallan.pdf_url && (
                <a
                  href={existingChallan.pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 font-body text-xs font-semibold text-brass-500 hover:underline"
                >
                  <FileText size={13} aria-hidden />
                  Open the notice
                </a>
              )}
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingChallan(true)}
              disabled={generatingChallan || !canGenerateChallan}
              className="btn-accent w-full sm:w-auto"
              title={
                canGenerateChallan
                  ? "Issue the Section 39 notice for this scan"
                  : "A notice can only be issued once the scan is recorded as not compliant"
              }
            >
              <FileText size={16} aria-hidden />
              {generatingChallan ? "Issuing…" : "Issue Section 39 notice"}
            </button>
          )}
          <ErrorBanner message={challanError} />
        </div>
      </div>

      <ConfirmDialog
        open={confirming}
        title={
          decision === "FAILED" ? "Record a non-compliant verdict?" : "Record a compliant verdict?"
        }
        tone={decision === "FAILED" ? "danger" : "default"}
        confirmLabel="Confirm verdict"
        busy={submitting}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          onSubmit(decision, note.trim());
        }}
        body={
          <div className="space-y-2">
            <p>
              This sets the legal outcome of the scan to{" "}
              <strong>{decision === "FAILED" ? "not compliant" : "compliant"}</strong>
              {overrideCount > 0 && (
                <>
                  {" "}
                  and submits {overrideCount} field correction
                  {overrideCount === 1 ? "" : "s"}
                </>
              )}
              .
            </p>
            {decision === "PASSED" && failingRules.length > 0 && (
              <p className="text-verdict-fail">
                You are clearing a scan the engine found in breach of{" "}
                {failingRules.map((r) => ruleMeta(r.rule_id).section).join(", ")}.
              </p>
            )}
            <p className="text-ink-600">
              Your name, the time and your reason are written to the audit record.
            </p>
          </div>
        }
      />

      <ConfirmDialog
        open={confirmingChallan}
        title="Issue a Section 39 notice?"
        tone="danger"
        confirmLabel="Issue notice"
        busy={generatingChallan}
        onCancel={() => setConfirmingChallan(false)}
        onConfirm={() => {
          setConfirmingChallan(false);
          onGenerateChallan();
        }}
        body={
          <div className="space-y-2">
            <p>
              This generates the statutory notice for this scan and files it in the challan
              archive. One notice exists per scan.
            </p>
            <p className="text-ink-600">The action is recorded against your name.</p>
          </div>
        }
      />
    </section>
  );
}
