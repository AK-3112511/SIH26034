"use client";
/**
 * Scan detail — the screen where a senior officer decides whether a package
 * complies with the Packaged Commodities Rules, 2011.
 *
 * This file is the orchestrator only: it loads the scan, the notice already
 * issued for it and the officer directory, and owns the state those three
 * share. The evidence viewer, rule panel, field table, review form and
 * assignment dialog each live in `./components`. It was previously a single
 * 927-line component holding 22 pieces of state, where the bounding-box
 * geometry, the review form and the assignment modal were interleaved.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, MapPin, UserPlus } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { SealBadge, type VerdictStatus } from "@/app/components/SealBadge";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import {
  challansApi,
  eventsApi,
  scansApi,
  usersApi,
  type ChallanResponse,
  type FieldOfficer,
  type ScanDetail,
} from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { formatCoords, formatDateTime, shortId } from "@/lib/format";
import { EvidenceViewer } from "./components/EvidenceViewer";
import { RuleResultsPanel } from "./components/RuleResultsPanel";
import { ExtractedFieldsTable } from "./components/ExtractedFieldsTable";
import { ReviewForm, type ReviewDecision } from "./components/ReviewForm";
import { AssignTaskDialog } from "./components/AssignTaskDialog";

/** Plain-language explanation for the states that are not a verdict. */
const STATUS_NOTES: Partial<Record<ScanDetail["status"], string>> = {
  QUEUED: "This scan is waiting to be processed. Rule results will appear once it has run.",
  PROCESSING: "This scan is being processed now.",
  CALIBRATION_FAILED:
    "The reference card could not be located in the photograph, so no measurement was possible. The capture needs to be retaken.",
  LOW_CONFIDENCE_CALIBRATION:
    "The reference card was found, but not confidently enough to rely on the measurements. Treat the heights below as indicative.",
  PROCESSING_FAILED: "Processing did not complete for this scan.",
};

export default function ScanDetailPage() {
  const params = useParams();
  const scanId = (params?.id as string) ?? "";

  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [activeField, setActiveField] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, string>>({});

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  const [challan, setChallan] = useState<ChallanResponse | null>(null);
  const [generatingChallan, setGeneratingChallan] = useState(false);
  const [challanError, setChallanError] = useState<string | null>(null);

  const [assignOpen, setAssignOpen] = useState(false);
  const [officers, setOfficers] = useState<FieldOfficer[]>([]);
  const [loadingOfficers, setLoadingOfficers] = useState(false);
  const [officersError, setOfficersError] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);
  const [assignedOfficer, setAssignedOfficer] = useState<FieldOfficer | null>(null);
  const [assignNotice, setAssignNotice] = useState<string | null>(null);

  /**
   * @param background true keeps the current scan on screen while refetching,
   *        so submitting a review does not blank the page the officer is
   *        reading.
   */
  const fetchScan = useCallback(
    async (background = false) => {
      if (!scanId) return;
      if (!background) setLoading(true);
      setLoadError(null);
      try {
        const { data } = await scansApi.detail(scanId);
        setScan(data);
      } catch (err) {
        setLoadError(apiErrorMessage(err, "This scan could not be loaded."));
      } finally {
        setLoading(false);
      }
    },
    [scanId]
  );

  const fetchChallan = useCallback(async () => {
    if (!scanId) return;
    try {
      setChallan(await challansApi.forScan(scanId));
    } catch {
      // Not being able to tell whether a notice exists is not worth an alarm
      // on load; issuing one is idempotent on the server either way.
    }
  }, [scanId]);

  const fetchOfficers = useCallback(async () => {
    setLoadingOfficers(true);
    setOfficersError(null);
    try {
      const { data } = await usersApi.getFieldOfficers();
      setOfficers(data);
    } catch (err) {
      setOfficers([]);
      setOfficersError(
        apiErrorMessage(err, "The field officer directory could not be loaded.")
      );
    } finally {
      setLoadingOfficers(false);
    }
  }, []);

  useEffect(() => {
    fetchScan();
    fetchChallan();
  }, [fetchScan, fetchChallan]);

  // Only load the directory where an assignment is possible.
  const canAssign = scan?.source === "ecommerce" && scan?.status === "FAILED";
  useEffect(() => {
    if (canAssign) fetchOfficers();
  }, [canAssign, fetchOfficers]);

  useEffect(() => {
    if (!scan?.assigned_lmo_id) return;
    setAssignedOfficer(officers.find((o) => o.id === scan.assigned_lmo_id) ?? null);
  }, [scan?.assigned_lmo_id, officers]);

  const handleOverride = (fieldName: string, value: string) =>
    setOverrides((prev) => ({ ...prev, [fieldName]: value }));

  const handleRevert = (fieldName: string) =>
    setOverrides((prev) => {
      const next = { ...prev };
      delete next[fieldName];
      return next;
    });

  const handleSubmitReview = async (decision: ReviewDecision, note: string) => {
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    try {
      await scansApi.review(scanId, {
        decision,
        reviewer_note: note,
        overridden_fields: Object.keys(overrides).length > 0 ? overrides : undefined,
      });
      setSubmitSuccess(
        decision === "FAILED"
          ? "Recorded as not compliant. The audit record has been updated."
          : "Recorded as compliant. The audit record has been updated."
      );
      setOverrides({});
      await fetchScan(true);
    } catch (err) {
      setSubmitError(apiErrorMessage(err, "The decision could not be recorded."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleGenerateChallan = async () => {
    setGeneratingChallan(true);
    setChallanError(null);
    try {
      const { data } = await challansApi.generate(scanId);
      setChallan(data);
    } catch (err) {
      setChallanError(apiErrorMessage(err, "The notice could not be issued."));
    } finally {
      setGeneratingChallan(false);
    }
  };

  const handleAssign = async (officerId: string, instructions: string) => {
    setAssigning(true);
    setAssignError(null);
    try {
      await eventsApi.assignTask({
        scan_id: scanId,
        assigned_to_lmo_id: officerId,
        task_type: "field_followup",
        instructions: instructions || undefined,
      });
      const officer = officers.find((o) => o.id === officerId) ?? null;
      setAssignedOfficer(officer);
      setAssignNotice(
        officer
          ? `Assigned to ${officer.full_name} for on-site verification.`
          : "Assigned for on-site verification."
      );
      setAssignOpen(false);
      await fetchScan(true);
    } catch (err) {
      setAssignError(apiErrorMessage(err, "The task could not be assigned."));
    } finally {
      setAssigning(false);
    }
  };

  const defaultInstructions = scan
    ? `Verify the package on site and serve the Section 39 notice for ${
        scan.product_name ?? "the scanned package"
      }.`
    : "Verify the package on site and serve the Section 39 notice.";

  const statusNote = scan ? STATUS_NOTES[scan.status] : undefined;

  return (
    <AppShell>
      <div className="mb-4 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3">
          <Link
            href="/queue"
            className="-ml-2 inline-flex items-center gap-1 rounded px-2 py-1 font-body text-sm font-semibold text-ink-600 transition-colors hover:text-ink-900 focus-visible:ring-2 focus-visible:ring-brass-500"
          >
            <ArrowLeft size={16} aria-hidden />
            Back to queue
          </Link>
          <span className="text-ink-600/40" aria-hidden>
            |
          </span>
          <span className="font-mono text-xs text-ink-600">
            Scan {shortId(scan?.scan_id ?? scanId)}
          </span>
        </div>

        {scan && (
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <span className="block font-body text-xs uppercase tracking-wider text-ink-600">
                Status
              </span>
              <span className="font-mono text-sm font-semibold text-ink-900">
                {scan.status.replace(/_/g, " ").toLowerCase()}
              </span>
            </div>
            <SealBadge verdict={scan.status as VerdictStatus} size={48} animate />
          </div>
        )}
      </div>

      <CalibrationRuler />

      {loading && (
        <p className="p-12 text-center font-mono text-sm text-ink-600">Loading the scan…</p>
      )}

      <ErrorBanner
        className="mt-6"
        title="This scan could not be loaded"
        message={loadError}
        onRetry={() => fetchScan()}
      />

      {scan && !loading && (
        <div className="mt-6 space-y-6">
          <header className="card-surface">
            <h1 className="font-display text-xl font-bold text-ink-900">
              {scan.product_name ?? "Unnamed package"}
            </h1>
            <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 font-body text-xs md:grid-cols-4">
              <div>
                <dt className="text-ink-600">Captured</dt>
                <dd className="font-mono text-ink-900">
                  {formatDateTime(scan.captured_at_utc ?? scan.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-ink-600">Location</dt>
                <dd className="font-mono text-ink-900">{formatCoords(scan.lat, scan.lng)}</dd>
              </div>
              <div>
                <dt className="text-ink-600">Source</dt>
                <dd className="font-mono text-ink-900">
                  {scan.source === "ecommerce"
                    ? `Online listing${scan.platform ? ` · ${scan.platform}` : ""}`
                    : "Field capture"}
                </dd>
              </div>
              <div>
                <dt className="text-ink-600">Reference object</dt>
                <dd className="font-mono text-ink-900">
                  {scan.reference_object_type?.replace(/_/g, " ") ?? "not recorded"}
                </dd>
              </div>
            </dl>

            {statusNote && (
              <p className="mt-3 rounded-card border border-verdict-pending/20 bg-verdict-pending/5 p-3 font-body text-xs text-ink-900">
                {statusNote}
                {scan.processing_error && (
                  <span className="mt-1 block font-mono text-[11px] text-ink-600">
                    {scan.processing_error}
                  </span>
                )}
              </p>
            )}
          </header>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <EvidenceViewer
                imageUrl={scan.image_url}
                scanId={scan.scan_id}
                evidenceHash={scan.evidence_hash}
                mmPerPx={scan.mm_per_px}
                pdpAreaCm2={scan.pdp_area_cm2}
                fields={scan.extracted_fields}
                activeField={activeField}
                onActiveFieldChange={setActiveField}
                overriddenFields={overrides}
              />
            </div>
            <div className="lg:col-span-5">
              <RuleResultsPanel
                results={scan.rule_results}
                rulesetVersion={scan.ruleset_version}
              />
            </div>
          </div>

          <div className="card-surface space-y-4">
            <div className="border-b border-ink-900/10 pb-3">
              <h2 className="font-display text-base font-semibold text-ink-900">
                Extracted fields
              </h2>
              <p className="mt-0.5 font-body text-xs text-ink-600">
                Correct anything the pipeline misread. Corrections are submitted with your
                decision and explained by your note.
              </p>
            </div>

            <ExtractedFieldsTable
              fields={scan.extracted_fields}
              overrides={overrides}
              onOverride={handleOverride}
              onRevert={handleRevert}
              activeField={activeField}
              onActiveFieldChange={setActiveField}
              disabled={submitting}
            />

            <ReviewForm
              ruleResults={scan.rule_results}
              scanStatus={scan.status}
              existingNote={scan.reviewer_note}
              overrideCount={Object.keys(overrides).length}
              submitting={submitting}
              submitError={submitError}
              submitSuccess={submitSuccess}
              onSubmit={handleSubmitReview}
              existingChallan={challan}
              generatingChallan={generatingChallan}
              challanError={challanError}
              onGenerateChallan={handleGenerateChallan}
            />

            {canAssign && (
              <div className="flex flex-col items-start gap-3 rounded-card border border-ink-900/10 bg-paper-100/60 p-3.5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-2.5">
                  <MapPin size={18} className="mt-0.5 shrink-0 text-brass-500" aria-hidden />
                  <div>
                    <p className="font-body text-xs font-semibold text-ink-900">
                      On-site verification
                    </p>
                    <p className="mt-0.5 font-body text-[11px] text-ink-600">
                      {assignedOfficer
                        ? `Assigned to ${assignedOfficer.full_name}.`
                        : "A listing found non-compliant needs a field officer to verify the package and serve notice at the premises."}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (officers.length === 0 && !loadingOfficers) fetchOfficers();
                    setAssignOpen(true);
                  }}
                  className="btn-secondary min-h-[40px] w-full px-3 py-1.5 text-xs sm:w-auto"
                  data-testid="assign-field-followup-button"
                >
                  <UserPlus size={14} aria-hidden />
                  {assignedOfficer ? "Reassign" : "Assign a field officer"}
                </button>
              </div>
            )}

            {assignNotice && (
              <p
                role="status"
                className="rounded-card border border-verdict-pass/30 bg-verdict-pass/5 p-3 font-body text-xs text-ink-900"
              >
                {assignNotice}
              </p>
            )}
          </div>
        </div>
      )}

      <AssignTaskDialog
        open={assignOpen}
        officers={officers}
        loadingOfficers={loadingOfficers}
        officersError={officersError}
        onRetryOfficers={fetchOfficers}
        assigning={assigning}
        assignError={assignError}
        defaultInstructions={defaultInstructions}
        onAssign={handleAssign}
        onClose={() => setAssignOpen(false)}
      />
    </AppShell>
  );
}
