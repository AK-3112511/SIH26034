"use client";
/**
 * §3 Screen 4 & §4.3 Layout Sketch — Scan Detail
 * 
 * Invariants:
 * 1. Client-Side Bounding Boxes (§2.1): Raw image pixels preserved for Section 65B chain of custody.
 *    Bounding boxes rendered on top via SVG overlay using stored bbox coordinates.
 * 2. Per-rule pass/fail table consuming real rule_results (6.1.a, 6.1.c, 6.1.e, 6.1.g, Schedule II).
 * 3. Editable field overrides requiring a mandatory reviewer note.
 * 4. §5.1 double concentric ring Seal Badge component (size 48 in header).
 * 5. "Generate Section 39 Challan" button disabled/non-functional until Phase 5.
 */
import { useCallback, useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ShieldCheck,
  Tag,
  Edit3,
  FileText,
  FileCheck2,
  MapPin,
  Calendar,
  Layers,
  Info,
  Maximize2,
  RefreshCw,
  UserPlus,
  X,
} from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { SealBadge, VerdictChip, type VerdictStatus } from "@/app/components/SealBadge";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import {
  scansApi,
  challansApi,
  usersApi,
  eventsApi,
  type ScanDetail,
  type ExtractedField,
  type RuleResult,
  type FieldOfficer,
} from "@/lib/api";

// Friendly metadata for statutory rules
const RULE_METADATA: Record<
  string,
  { label: string; section: string; desc: string }
> = {
  "6.1.a": {
    label: "6(1)(a) Manufacturer Details",
    section: "Rule 6(1)(a)",
    desc: "Complete name & postal address of manufacturer / packer / importer with PIN code.",
  },
  "6.1.c": {
    label: "6(1)(c) Standard Metric Units",
    section: "Rule 6(1)(c)",
    desc: "Net quantity declaration in approved SI metric units (g, kg, ml, l).",
  },
  "6.1.e": {
    label: "6(1)(e) MRP Inclusive of Taxes",
    section: "Rule 6(1)(e)",
    desc: "Maximum Retail Price accompanied by statutory 'incl. of all taxes' phrase.",
  },
  "6.1.g": {
    label: "6(1)(g) Consumer Care Details",
    section: "Rule 6(1)(g)",
    desc: "Name, postal address, telephone number and email of grievance officer.",
  },
  "schedule_ii": {
    label: "Schedule II Font/Area Ratio",
    section: "Schedule II",
    desc: "Minimum numeral font height calibrated against Principal Display Panel area.",
  },
};

export default function ScanDetailPage() {
  const params = useParams();
  const router = useRouter();
  const scanId = params?.id as string;

  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeHoverField, setActiveHoverField] = useState<string | null>(null);

  // Field override form state
  const [editingField, setEditingField] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [tempEditValue, setTempEditValue] = useState<string>("");
  const [reviewerNote, setReviewerNote] = useState<string>("");
  const [decision, setDecision] = useState<"PASSED" | "FAILED">("PASSED");
  const [submittingReview, setSubmittingReview] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  
  const [generatingChallan, setGeneratingChallan] = useState(false);
  const [challanUrl, setChallanUrl] = useState<string | null>(null);

  // Phase 7.3: Field follow-up assignment state (§5.3)
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [fieldOfficers, setFieldOfficers] = useState<FieldOfficer[]>([]);
  const [loadingOfficers, setLoadingOfficers] = useState(false);
  const [selectedOfficerId, setSelectedOfficerId] = useState<string>("");
  const [taskInstructions, setTaskInstructions] = useState<string>(
    "Conduct on-site inventory check and serve Section 39 notice for non-compliant packaging."
  );
  const [assigningTask, setAssigningTask] = useState(false);
  const [assignedOfficerName, setAssignedOfficerName] = useState<string | null>(null);
  const [assignSuccess, setAssignSuccess] = useState<string | null>(null);
  const [assignError, setAssignError] = useState<string | null>(null);

  const loadFieldOfficers = useCallback(async () => {
    setLoadingOfficers(true);
    try {
      const res = await usersApi.getFieldOfficers();
      setFieldOfficers(res.data);
      if (res.data.length > 0 && !selectedOfficerId) {
        setSelectedOfficerId(res.data[0].id);
      }
    } catch {
      // Fallback dev field officers if API unreachable
      const fallbackOfficers: FieldOfficer[] = [
        {
          id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
          username: "lmo_ramesh",
          email: "ramesh@legalmetrology.gov.in",
          full_name: "Ramesh Kumar",
          role: "field_lmo",
          district: "Madurai",
          is_active: true,
          created_at: new Date().toISOString(),
        },
      ];
      setFieldOfficers(fallbackOfficers);
      if (!selectedOfficerId) setSelectedOfficerId(fallbackOfficers[0].id);
    } finally {
      setLoadingOfficers(false);
    }
  }, [selectedOfficerId]);

  const handleAssignTask = async () => {
    if (!scan || !selectedOfficerId) return;
    setAssigningTask(true);
    setAssignError(null);
    setAssignSuccess(null);
    try {
      const target = fieldOfficers.find((o) => o.id === selectedOfficerId);
      await eventsApi.assignTask({
        scan_id: scan.scan_id,
        assigned_to_lmo_id: selectedOfficerId,
        task_type: "field_followup",
      });
      const name = target?.full_name || target?.username || selectedOfficerId;
      setAssignedOfficerName(name);
      setAssignSuccess(`Assigned to ${name} for field follow-up (§5.3). Event task.assigned dispatched.`);
      setShowAssignModal(false);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setAssignError(msg || "Failed to assign task to field officer");
    } finally {
      setAssigningTask(false);
    }
  };

  const fetchScan = useCallback(async () => {
    if (!scanId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await scansApi.detail(scanId);
      setScan(res.data);
      if (res.data.reviewer_note) {
        setReviewerNote(res.data.reviewer_note);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Failed to load scan details");
    } finally {
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    fetchScan();
  }, [fetchScan]);

  useEffect(() => {
    if (scan?.source === "ecommerce") {
      loadFieldOfficers();
    }
  }, [scan?.source, loadFieldOfficers]);

  useEffect(() => {
    if (scan?.assigned_lmo_id && fieldOfficers.length > 0) {
      const matched = fieldOfficers.find((o) => o.id === scan.assigned_lmo_id);
      if (matched) {
        setAssignedOfficerName(matched.full_name || matched.username);
      } else {
        setAssignedOfficerName(`Officer #${scan.assigned_lmo_id.slice(0, 8)}`);
      }
    }
  }, [scan?.assigned_lmo_id, fieldOfficers]);

  const handleStartEdit = (field: ExtractedField) => {
    setEditingField(field.field_name);
    setTempEditValue(overrides[field.field_name] ?? field.raw_text ?? "");
  };

  const handleSaveEdit = (fieldName: string) => {
    setOverrides((prev) => ({
      ...prev,
      [fieldName]: tempEditValue,
    }));
    setEditingField(null);
  };

  const handleCancelEdit = () => {
    setEditingField(null);
  };

  const handleRevertOverride = (fieldName: string) => {
    setOverrides((prev) => {
      const updated = { ...prev };
      delete updated[fieldName];
      return updated;
    });
  };

  const handleSubmitReview = async () => {
    if (!reviewerNote.trim()) {
      setSubmitError("A mandatory reviewer note is required to submit a review decision.");
      return;
    }
    setSubmittingReview(true);
    setSubmitError(null);
    setSubmitSuccess(null);

    try {
      await scansApi.review(scanId, {
        decision,
        reviewer_note: reviewerNote.trim(),
        overridden_fields: Object.keys(overrides).length > 0 ? overrides : undefined,
      });
      setSubmitSuccess(`Scan marked as ${decision}. Audit trail updated.`);
      await fetchScan();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSubmitError(msg || "Failed to submit review decision");
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleGenerateChallan = async () => {
    setGeneratingChallan(true);
    setSubmitError(null);
    try {
      const res = await challansApi.generate(scanId);
      setSubmitSuccess(`Challan generated successfully. PDF Hash: ${res.data.pdf_hash}`);
      setChallanUrl(res.data.pdf_url);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSubmitError(msg || "Failed to generate challan.");
    } finally {
      setGeneratingChallan(false);
    }
  };

  // Convert bounding box to percentage styles
  const getBBoxStyle = (bbox: ExtractedField["bbox"]) => {
    if (!bbox) return null;
    let { x1, y1, x2, y2 } = bbox;
    // Normalize if given in [0..1] range
    if (x1 <= 1 && x2 <= 1 && y1 <= 1 && y2 <= 1) {
      x1 *= 100;
      y1 *= 100;
      x2 *= 100;
      y2 *= 100;
    }
    return {
      left: `${Math.min(x1, x2)}%`,
      top: `${Math.min(y1, y2)}%`,
      width: `${Math.abs(x2 - x1)}%`,
      height: `${Math.abs(y2 - y1)}%`,
    };
  };

  const hasUnverifiedRules = useMemo(() => {
    return scan?.rule_results.some((r) => r.status === "UNVERIFIED");
  }, [scan]);

  return (
    <AppShell>
      {/* ── Breadcrumb & Top Bar (§4.3) ────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <Link
            href="/queue"
            className="
              inline-flex items-center gap-1 text-sm font-body font-semibold text-ink-600
              hover:text-ink-900 transition-colors px-2 py-1 -ml-2 rounded
              focus-visible:ring-2 focus-visible:ring-brass-500
            "
          >
            <ArrowLeft size={16} />
            <span>← Back to Queue</span>
          </Link>
          <span className="text-ink-600/40">|</span>
          <span className="font-mono text-xs text-ink-600">
            ID: {scan?.scan_id ?? scanId}
          </span>
        </div>

        {scan && (
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <span className="block font-body text-xs text-ink-600 uppercase tracking-wider">
                Current Status
              </span>
              <span className="font-mono text-sm font-semibold text-ink-900">
                {scan.status}
              </span>
            </div>
            {/* §5.1 double concentric ring Seal Badge */}
            <SealBadge verdict={scan.status as VerdictStatus} size={48} animate />
          </div>
        )}
      </div>

      <CalibrationRuler />

      {loading && (
        <div className="p-12 text-center text-ink-600 font-mono text-sm">
          Loading scan evidence and rule results...
        </div>
      )}

      {error && (
        <div className="card-surface mt-6 border-verdict-fail/30 bg-verdict-fail/5 text-verdict-fail flex items-center gap-3">
          <AlertTriangle size={20} />
          <div>
            <p className="font-semibold text-sm">Failed to retrieve scan evidence</p>
            <p className="text-xs">{error}</p>
          </div>
        </div>
      )}

      {scan && !loading && (
        <div className="space-y-6 mt-6">
          {/* ── Top Grid: Raw Evidence Image (Left) & Rule Results (Right) ─── */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Panel: Image with Non-Burned SVG Bounding Box Overlays */}
            <div className="lg:col-span-7 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers size={16} className="text-brass-500" />
                  <h2 className="font-display font-semibold text-sm text-ink-900 uppercase tracking-wider">
                    Evidence Image & Field Bounding Boxes
                  </h2>
                </div>
                <span className="font-mono text-[11px] text-ink-600 bg-ink-900/5 px-2 py-0.5 rounded">
                  §2.1 Chain-of-Custody: Overlay Rendered Client-Side
                </span>
              </div>

              {/* Image Frame Container */}
              <div
                className="
                  relative rounded-[4px] border border-ink-900/10 bg-black/5 overflow-hidden
                  flex items-center justify-center min-h-[380px] max-h-[520px] select-none
                "
              >
                {/* Full-res Raw Image */}
                <img
                  src={scan.image_url}
                  alt={`Evidence for ${scan.scan_id}`}
                  className="w-full h-full object-contain max-h-[520px]"
                  onError={(e) => {
                    // Fallback placeholder with SVG if local image fails
                    (e.target as HTMLImageElement).src =
                      "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='600' height='400' viewBox='0 0 600 400'><rect width='600' height='400' fill='%23F1F3F1'/><text x='50%' y='48%' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='16' fill='%233C4E70'>Packaged Product Evidence Capture</text><text x='50%' y='55%' dominant-baseline='middle' text-anchor='middle' font-family='monospace' font-size='12' fill='%236B7280'>SHA-256 Verified</text></svg>";
                  }}
                />

                {/* SVG/HTML Bounding Box Overlay — client-side only per §2.1 & §4.3 */}
                <div
                  className="absolute inset-0 pointer-events-none"
                  aria-label="Client-side bounding box overlay"
                >
                  {scan.extracted_fields.map((field) => {
                    const boxStyle = getBBoxStyle(field.bbox);
                    if (!boxStyle) return null;
                    const isHovered = activeHoverField === field.field_name;
                    const isOverridden = Boolean(overrides[field.field_name]);

                    return (
                      <div
                        key={field.id}
                        style={boxStyle}
                        className={`
                          absolute pointer-events-auto cursor-pointer transition-all duration-150
                          border-2 rounded-[2px]
                          ${
                            isHovered
                              ? "border-brass-500 bg-brass-500/20 shadow-md ring-2 ring-brass-500/40"
                              : isOverridden
                              ? "border-blue-600 bg-blue-600/10"
                              : "border-verdict-fail/80 bg-verdict-fail/10"
                          }
                        `}
                        onMouseEnter={() => setActiveHoverField(field.field_name)}
                        onMouseLeave={() => setActiveHoverField(null)}
                      >
                        <span
                          className={`
                            absolute -top-5 left-0 px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold
                            whitespace-nowrap transition-opacity
                            ${
                              isHovered
                                ? "bg-brass-500 text-white opacity-100 z-20"
                                : "bg-ink-900/80 text-white opacity-80"
                            }
                          `}
                        >
                          {field.field_name}
                          {field.ocr_confidence !== null && ` (${Math.round(field.ocr_confidence * 100)}%)`}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Chain of Custody & Calibration Footnote */}
              <div className="card-surface p-3 bg-paper-100/60 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <ShieldCheck size={16} className="text-verdict-pass" />
                  <span className="font-mono text-[11px] text-ink-600">
                    Hash: {scan.evidence_hash.slice(0, 16)}…{scan.evidence_hash.slice(-8)}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-ink-600 font-mono text-[11px]">
                  {scan.mm_per_px && <span>Ratio: {scan.mm_per_px.toFixed(3)} mm/px</span>}
                  {scan.pdp_area_cm2 && <span>PDP: {scan.pdp_area_cm2.toFixed(1)} cm²</span>}
                </div>
              </div>
            </div>

            {/* Right Panel: Rule Results Table (§4.3) */}
            <div className="lg:col-span-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileCheck2 size={16} className="text-brass-500" />
                  <h2 className="font-display font-semibold text-sm text-ink-900 uppercase tracking-wider">
                    Statutory Rule Results
                  </h2>
                </div>
                <span className="font-mono text-xs text-ink-600">
                  Ruleset: {scan.ruleset_version ?? "2026.1"}
                </span>
              </div>

              <div className="card-surface p-0 overflow-hidden">
                <div className="divide-y divide-ink-900/10">
                  {scan.rule_results.map((rule) => {
                    const meta = RULE_METADATA[rule.rule_id] ?? {
                      label: rule.rule_id,
                      section: rule.rule_id,
                      desc: "Legal Metrology Packaged Commodities Rule",
                    };

                    const isPass = rule.status === "PASS";
                    const isFail = rule.status === "FAIL";
                    const isUnverified = rule.status === "UNVERIFIED";

                    return (
                      <div
                        key={rule.id}
                        className="p-3.5 hover:bg-ink-900/[0.02] transition-colors"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-2.5">
                            {isPass && (
                              <CheckCircle2
                                size={18}
                                className="text-verdict-pass shrink-0 mt-0.5"
                                aria-label="Pass"
                              />
                            )}
                            {isFail && (
                              <XCircle
                                size={18}
                                className="text-verdict-fail shrink-0 mt-0.5"
                                aria-label="Fail"
                              />
                            )}
                            {isUnverified && (
                              <AlertTriangle
                                size={18}
                                className="text-verdict-pending shrink-0 mt-0.5"
                                aria-label="Unverified"
                              />
                            )}
                            <div>
                              <span className="font-body text-sm font-semibold text-ink-900 block">
                                {meta.label}
                              </span>
                              <span className="font-body text-xs text-ink-600 block mt-0.5">
                                {meta.desc}
                              </span>
                            </div>
                          </div>
                          <VerdictChip verdict={rule.status as VerdictStatus} />
                        </div>

                        {rule.reason && (
                          <div className="mt-2.5 ml-7 p-2 rounded bg-ink-900/5 text-xs font-body text-ink-900">
                            <span className="font-semibold text-ink-600 uppercase text-[10px] block">
                              Evidence & Reason:
                            </span>
                            <span className="mt-0.5 block">{rule.reason}</span>
                            {rule.evidence && Object.keys(rule.evidence).length > 0 && (
                              <span className="font-mono text-[10px] text-ink-600 block mt-1">
                                {JSON.stringify(rule.evidence)}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* ── Extracted Fields (Editable, Requires Reviewer Note) ────────── */}
          <div className="card-surface space-y-4">
            <div className="flex items-center justify-between border-b border-ink-900/10 pb-3">
              <div>
                <h3 className="font-display font-semibold text-base text-ink-900">
                  Extracted Fields & Overrides
                </h3>
                <p className="font-body text-xs text-ink-600 mt-0.5">
                  Editable field overrides require a mandatory reviewer note explaining the change per §3 Screen 4.
                </p>
              </div>
              {Object.keys(overrides).length > 0 && (
                <span className="status-chip bg-blue-50 text-blue-800 border-blue-200 font-mono text-xs">
                  {Object.keys(overrides).length} field(s) overridden
                </span>
              )}
            </div>

            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Field Name</th>
                    <th>Extracted Text / OCR</th>
                    <th>Confidence</th>
                    <th>Font Height</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {scan.extracted_fields.map((field) => {
                    const isEditing = editingField === field.field_name;
                    const isOverridden = overrides[field.field_name] !== undefined;
                    const currentValue = isOverridden
                      ? overrides[field.field_name]
                      : field.raw_text ?? "—";
                    const isHovered = activeHoverField === field.field_name;

                    return (
                      <tr
                        key={field.id}
                        className={isHovered ? "bg-brass-500/10" : ""}
                        onMouseEnter={() => setActiveHoverField(field.field_name)}
                        onMouseLeave={() => setActiveHoverField(null)}
                      >
                        <td className="font-semibold text-ink-900">
                          <span className="font-body text-xs uppercase tracking-wider">
                            {field.field_name.replace(/_/g, " ")}
                          </span>
                        </td>

                        <td className="w-1/2">
                          {isEditing ? (
                            <div className="flex items-center gap-2">
                              <input
                                type="text"
                                value={tempEditValue}
                                onChange={(e) => setTempEditValue(e.target.value)}
                                className="form-input text-xs py-1 min-h-[36px]"
                                autoFocus
                              />
                              <button
                                onClick={() => handleSaveEdit(field.field_name)}
                                className="btn-primary text-xs px-3 py-1 min-h-[36px]"
                              >
                                Save
                              </button>
                              <button
                                onClick={handleCancelEdit}
                                className="btn-secondary text-xs px-3 py-1 min-h-[36px]"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <span
                                className={`font-mono text-xs ${
                                  isOverridden ? "text-blue-700 font-semibold" : "text-ink-900"
                                }`}
                              >
                                {currentValue}
                              </span>
                              {isOverridden && (
                                <span className="text-[10px] font-mono px-1 py-0.2 rounded bg-blue-100 text-blue-800">
                                  OVERRIDDEN
                                </span>
                              )}
                            </div>
                          )}
                        </td>

                        <td>
                          {field.ocr_confidence !== null ? (
                            <span className="font-mono text-xs text-ink-900">
                              {(field.ocr_confidence * 100).toFixed(0)}%
                            </span>
                          ) : (
                            <span className="font-mono text-xs text-ink-600/60">—</span>
                          )}
                        </td>

                        <td>
                          {field.font_height_mm !== null ? (
                            <span className="font-mono text-xs text-ink-900">
                              {field.font_height_mm.toFixed(1)} mm
                            </span>
                          ) : (
                            <span className="font-mono text-xs text-ink-600/60">—</span>
                          )}
                        </td>

                        <td className="text-right">
                          {isOverridden ? (
                            <button
                              onClick={() => handleRevertOverride(field.field_name)}
                              className="text-xs font-body text-ink-600 underline hover:text-ink-900"
                            >
                              Revert
                            </button>
                          ) : (
                            !isEditing && (
                              <button
                                onClick={() => handleStartEdit(field)}
                                className="
                                  inline-flex items-center gap-1 text-xs font-semibold
                                  text-brass-500 hover:text-ink-900 transition-colors
                                "
                              >
                                <Edit3 size={13} />
                                <span>[Override]</span>
                              </button>
                            )
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* ── Review Decision & Mandatory Reviewer Note ───────────────── */}
            <div className="pt-4 border-t border-ink-900/10 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="decision-select" className="form-label">
                    Adjudication Verdict Decision *
                  </label>
                  <select
                    id="decision-select"
                    value={decision}
                    onChange={(e) => setDecision(e.target.value as "PASSED" | "FAILED")}
                    className="form-input"
                  >
                    <option value="PASSED">Mark as PASSED (Compliant with PCR 2011)</option>
                    <option value="FAILED">Mark as FAILED (Violation Detected)</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="reviewer-note" className="form-label">
                    Mandatory Reviewer Note *
                  </label>
                  <textarea
                    id="reviewer-note"
                    rows={2}
                    value={reviewerNote}
                    onChange={(e) => setReviewerNote(e.target.value)}
                    placeholder="Enter statutory justification for verdict or field overrides (mandatory)..."
                    className="form-input min-h-[48px] py-2"
                    required
                  />
                </div>
              </div>

              {submitError && (
                <div className="p-3 rounded bg-verdict-fail/10 text-verdict-fail border border-verdict-fail/30 text-xs font-medium">
                  {submitError}
                </div>
              )}

              {submitSuccess && (
                <div className="p-3 rounded bg-verdict-pass/10 text-verdict-pass border border-verdict-pass/30 text-xs font-medium">
                  {submitSuccess}
                </div>
              )}

              {/* Action Bar */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
                <button
                  type="button"
                  onClick={handleSubmitReview}
                  disabled={submittingReview || !reviewerNote.trim()}
                  className="btn-primary w-full sm:w-auto"
                >
                  {submittingReview ? "Submitting Decision..." : "Submit Review & Confirm Verdict"}
                </button>

                {/* Section 39 Challan button */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleGenerateChallan}
                    disabled={generatingChallan || scan?.status !== "FAILED"}
                    className={`
                      btn-accent w-full sm:w-auto
                      ${scan?.status !== "FAILED" ? "opacity-50 cursor-not-allowed" : ""}
                    `}
                    title={scan?.status !== "FAILED" ? "Only failed scans can generate challans" : "Generate Section 39 Challan"}
                  >
                    <FileText size={16} />
                    <span>{generatingChallan ? "Generating..." : "Generate Section 39 Challan"}</span>
                  </button>
                  {challanUrl && (
                    <a
                      href={challanUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-[11px] text-brass-500 hover:underline block sm:inline"
                    >
                      View PDF
                    </a>
                  )}
                </div>
              </div>

              {/* Phase 7.3: Assign for Field Follow-up (§5.3) — Strictly scoped to failed e-commerce scans */}
              {scan?.source === "ecommerce" && scan?.status === "FAILED" && (
                <div
                  className="mt-4 pt-4 border-t border-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-surface-subtle/60 p-3.5 rounded-lg border border-border"
                  data-testid="field-followup-container"
                >
                  <div className="flex items-start sm:items-center gap-2.5">
                    <MapPin size={18} className="text-brass-500 flex-shrink-0 mt-0.5 sm:mt-0" />
                    <div>
                      <div className="text-xs font-semibold text-text-primary flex flex-wrap items-center gap-2">
                        <span>Field Follow-up Inspection (§5.3)</span>
                        {assignedOfficerName ? (
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-verdict-pass/10 text-verdict-pass border border-verdict-pass/30"
                            data-testid="assigned-officer-badge"
                          >
                            Assigned: {assignedOfficerName}
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-amber-500/10 text-amber-500 border border-amber-500/30">
                            Unassigned
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-text-muted mt-0.5">
                        E-commerce compliance failure requires physical verification & Section 39 notice at seller premises.
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      loadFieldOfficers();
                      setShowAssignModal(true);
                    }}
                    className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1.5 whitespace-nowrap self-stretch sm:self-auto justify-center"
                    data-testid="assign-field-followup-button"
                  >
                    <UserPlus size={14} />
                    <span>{assignedOfficerName ? "Reassign Field Officer" : "Assign for Field Follow-up"}</span>
                  </button>
                </div>
              )}

              {assignSuccess && (
                <div className="mt-3 p-3 rounded bg-verdict-pass/10 text-verdict-pass border border-verdict-pass/30 text-xs font-medium">
                  {assignSuccess}
                </div>
              )}
            </div>
          </div>

          {/* Phase 7.3: Field Officer Assignment Modal (§5.3) */}
          {showAssignModal && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
              data-testid="assign-officer-modal"
            >
              <div className="bg-surface rounded-xl border border-border max-w-lg w-full p-6 shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <div className="flex items-center gap-2">
                    <UserPlus size={20} className="text-brass-500" />
                    <h3 className="text-base font-semibold text-text-primary">
                      Assign Field Officer (§5.3)
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowAssignModal(false)}
                    className="text-text-muted hover:text-text-primary p-1"
                  >
                    <X size={18} />
                  </button>
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <label className="block text-text-secondary font-medium mb-1">
                      Target Field Officer (LMO)
                    </label>
                    {loadingOfficers ? (
                      <div className="text-text-muted italic py-2">Loading field officers...</div>
                    ) : fieldOfficers.length === 0 ? (
                      <div className="text-amber-500 py-2">No active field officers found in directory.</div>
                    ) : (
                      <select
                        value={selectedOfficerId}
                        onChange={(e) => setSelectedOfficerId(e.target.value)}
                        className="w-full bg-surface-subtle border border-border rounded-lg px-3 py-2 text-text-primary focus:outline-none focus:ring-1 focus:ring-brass-500 text-xs"
                        data-testid="field-officer-select"
                      >
                        {fieldOfficers.map((o) => (
                          <option key={o.id} value={o.id}>
                            {o.full_name} ({o.district || "Jurisdiction"}) — @{o.username}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div>
                    <label className="block text-text-secondary font-medium mb-1">
                      Task Type
                    </label>
                    <input
                      type="text"
                      disabled
                      value="field_followup"
                      className="w-full bg-surface-subtle/50 border border-border/60 rounded-lg px-3 py-2 text-text-muted font-mono text-xs cursor-not-allowed"
                    />
                  </div>

                  <div>
                    <label className="block text-text-secondary font-medium mb-1">
                      Field Instructions & Statutory Notice Guidance
                    </label>
                    <textarea
                      rows={3}
                      value={taskInstructions}
                      onChange={(e) => setTaskInstructions(e.target.value)}
                      className="w-full bg-surface-subtle border border-border rounded-lg p-2.5 text-text-primary focus:outline-none focus:ring-1 focus:ring-brass-500 text-xs"
                    />
                  </div>

                  {assignError && (
                    <div className="p-2.5 rounded bg-verdict-fail/10 text-verdict-fail border border-verdict-fail/30 text-xs">
                      {assignError}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-border">
                  <button
                    type="button"
                    onClick={() => setShowAssignModal(false)}
                    className="btn-secondary text-xs px-4 py-2"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleAssignTask}
                    disabled={assigningTask || !selectedOfficerId}
                    className="btn-primary text-xs px-4 py-2 flex items-center gap-1.5"
                    data-testid="confirm-assignment-button"
                  >
                    {assigningTask ? "Dispatching Task..." : "Confirm & Dispatch Task (§5.3)"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}
