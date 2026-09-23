"use client";
/**
 * §3 Screen 8 — Admin: Ruleset Config (Phase 6.3)
 * Versioned Schedule II editor. "Save as new version" only — the backend
 * never overwrites an existing version (append-only), so a past challan's
 * ruleset_version always still resolves to exactly what was active when it
 * was generated. Admin-only, per §12 of the blueprint.
 */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, Plus, Trash2 } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { AdminGuard } from "@/app/components/ui/AdminGuard";
import { adminRulesetsApi, type RulesetVersion, type ScheduleIIBand } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

const EMPTY_BAND: ScheduleIIBand = { max_area_cm2: 50, min_font_mm: 1.5, description: "" };
const EMPTY_OPEN_ENDED_BAND: ScheduleIIBand = { max_area_cm2: null, min_font_mm: 6, description: "" };

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
}

function RulesetAdminScreen() {
  const [versions, setVersions] = useState<RulesetVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyVersion, setBusyVersion] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [formVersion, setFormVersion] = useState("");
  const [formDate, setFormDate] = useState("");
  const [formNotice, setFormNotice] = useState("");
  const [formIsPlaceholder, setFormIsPlaceholder] = useState(true);
  const [formActivate, setFormActivate] = useState(false);
  const [formBands, setFormBands] = useState<ScheduleIIBand[]>([EMPTY_BAND, EMPTY_OPEN_ENDED_BAND]);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchVersions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await adminRulesetsApi.list();
      setVersions(data.versions);
    } catch (err) {
      setError(apiErrorMessage(err, "The ruleset versions could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVersions();
  }, [fetchVersions]);

  const activeVersion = versions.find((v) => v.is_active);

  const handleActivate = async (version: string) => {
    setBusyVersion(version);
    try {
      await adminRulesetsApi.activate(version);
      await fetchVersions();
    } catch (err) {
      setError(apiErrorMessage(err, `${version} could not be made active.`));
    } finally {
      setBusyVersion(null);
    }
  };

  const updateBand = (index: number, patch: Partial<ScheduleIIBand>) => {
    setFormBands((bands) => bands.map((b, i) => (i === index ? { ...b, ...patch } : b)));
  };

  const addBand = () => {
    setFormBands((bands) => [...bands, { max_area_cm2: 0, min_font_mm: 0, description: "" }]);
  };

  const removeBand = (index: number) => {
    setFormBands((bands) => bands.filter((_, i) => i !== index));
  };

  const resetForm = () => {
    setFormVersion("");
    setFormDate("");
    setFormNotice("");
    setFormIsPlaceholder(true);
    setFormActivate(false);
    setFormBands([EMPTY_BAND, EMPTY_OPEN_ENDED_BAND]);
    setFormError(null);
  };

  const handleSave = async () => {
    setFormError(null);
    if (!formVersion.trim() || !formDate || !formNotice.trim()) {
      setFormError("Version name, effective date, and notice are all required.");
      return;
    }
    const openEnded = formBands.filter((b) => b.max_area_cm2 === null);
    if (openEnded.length !== 1) {
      setFormError(
        "Bands must contain exactly one open-ended bracket (leave Max Area blank on exactly one row — the final bracket)."
      );
      return;
    }

    setSaving(true);
    try {
      await adminRulesetsApi.create(
        {
          version: formVersion.trim(),
          effective_date: formDate,
          is_placeholder: formIsPlaceholder,
          notice: formNotice.trim(),
          bands: formBands,
        },
        formActivate
      );
      resetForm();
      setShowForm(false);
      await fetchVersions();
    } catch (err) {
      setFormError(apiErrorMessage(err, "The ruleset version could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900">
            Admin: Ruleset Config
          </h1>
          <p className="font-body text-sm text-ink-600 mt-1">
            Versioned Schedule II font-height / PDP-area bands. Save as a new version — an
            existing version is never overwritten.
          </p>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

      {/* §3.4/6.3: This is explicitly the screen where real Schedule II numbers eventually
          get entered — never silently treat placeholder figures as real. */}
      {activeVersion?.is_placeholder !== false && (
        <div
          role="alert"
          className="mb-6 p-3 rounded-[4px] text-sm font-body flex items-start gap-2"
          style={{
            backgroundColor: "rgba(181,115,11,0.08)",
            border: "1px solid rgba(181,115,11,0.3)",
            color: "#B5730B",
          }}
        >
          <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
          <span>
            <strong>Placeholder figures in effect.</strong> The active ruleset&apos;s area/font
            bands are provisional approximations, not verified statutory figures. This is the
            screen where the real Legal Metrology (Packaged Commodities) Rules, 2011 Schedule II
            numbers must eventually be entered — do not rely on the current bands for real
            enforcement until they are replaced with verified figures and marked non-placeholder.
          </span>
        </div>
      )}

      <ErrorBanner className="mb-6" message={error} />

      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-lg font-semibold text-ink-900">Versions</h2>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="btn-secondary text-xs px-3 py-1.5 min-h-[40px] inline-flex items-center gap-1.5"
        >
          <Plus size={14} />
          {showForm ? "Cancel" : "New Version"}
        </button>
      </div>

      {showForm && (
        <div className="card-surface mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label htmlFor="rv-version" className="form-label">
                Version Name
              </label>
              <input
                id="rv-version"
                type="text"
                value={formVersion}
                onChange={(e) => setFormVersion(e.target.value)}
                placeholder="e.g. pcr_2011_schedule_ii_v2"
                className="form-input text-sm"
              />
            </div>
            <div>
              <label htmlFor="rv-date" className="form-label">
                Effective Date
              </label>
              <input
                id="rv-date"
                type="date"
                value={formDate}
                onChange={(e) => setFormDate(e.target.value)}
                className="form-input text-sm"
              />
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="rv-notice" className="form-label">
              Notice
            </label>
            <textarea
              id="rv-notice"
              value={formNotice}
              onChange={(e) => setFormNotice(e.target.value)}
              rows={2}
              placeholder="Legal/audit-facing note about this version's provenance"
              className="form-input text-sm"
            />
          </div>

          <div className="mb-4">
            <span className="form-label">Area / Font-Height Bands</span>
            <div className="flex flex-col gap-2">
              {formBands.map((band, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-32">
                    <input
                      type="number"
                      value={band.max_area_cm2 ?? ""}
                      onChange={(e) =>
                        updateBand(i, {
                          max_area_cm2: e.target.value === "" ? null : Number(e.target.value),
                        })
                      }
                      placeholder="Max cm² (blank=open)"
                      className="form-input font-mono text-xs py-1.5 min-h-[40px]"
                    />
                  </div>
                  <div className="w-28">
                    <input
                      type="number"
                      step="0.1"
                      value={band.min_font_mm}
                      onChange={(e) => updateBand(i, { min_font_mm: Number(e.target.value) })}
                      placeholder="Min mm"
                      className="form-input font-mono text-xs py-1.5 min-h-[40px]"
                    />
                  </div>
                  <input
                    type="text"
                    value={band.description}
                    onChange={(e) => updateBand(i, { description: e.target.value })}
                    placeholder="Description"
                    className="form-input text-xs py-1.5 min-h-[40px] flex-1"
                  />
                  <button
                    type="button"
                    onClick={() => removeBand(i)}
                    disabled={formBands.length <= 1}
                    aria-label="Remove band"
                    className="text-ink-600 hover:text-verdict-fail disabled:opacity-30 disabled:cursor-not-allowed p-2"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={addBand}
              className="mt-2 font-body text-xs font-semibold text-brass-500 hover:text-brass-500/80 inline-flex items-center gap-1"
            >
              <Plus size={12} /> Add band
            </button>
            <p className="font-body text-xs text-ink-600/70 mt-1">
              Exactly one row must have a blank Max Area — that is the final, open-ended bracket.
            </p>
          </div>

          <div className="flex items-center gap-6 mb-4">
            <label className="flex items-center gap-2 font-body text-sm text-ink-900">
              <input
                type="checkbox"
                checked={formIsPlaceholder}
                onChange={(e) => setFormIsPlaceholder(e.target.checked)}
                className="w-4 h-4"
              />
              Placeholder (not yet verified against the statute)
            </label>
            <label className="flex items-center gap-2 font-body text-sm text-ink-900">
              <input
                type="checkbox"
                checked={formActivate}
                onChange={(e) => setFormActivate(e.target.checked)}
                className="w-4 h-4"
              />
              Activate immediately
            </label>
          </div>

          {!formIsPlaceholder && (
            <div
              className="mb-4 p-3 rounded-[4px] text-xs font-body flex items-start gap-2"
              style={{
                backgroundColor: "rgba(179,38,30,0.08)",
                border: "1px solid rgba(179,38,30,0.3)",
                color: "#B3261E",
              }}
            >
              <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
              <span>
                You are marking this version as <strong>not</strong> a placeholder — this asserts
                the bands are verified, authoritative Schedule II figures. Only do this once
                confirmed against the current Legal Metrology (Packaged Commodities) Rules, 2011.
              </span>
            </div>
          )}

          {formError && (
            <div
              role="alert"
              className="mb-4 p-3 rounded-[4px] text-xs font-body"
              style={{
                backgroundColor: "rgba(179,38,30,0.08)",
                border: "1px solid rgba(179,38,30,0.3)",
                color: "#B3261E",
              }}
            >
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                resetForm();
                setShowForm(false);
              }}
              className="btn-secondary text-xs px-4 py-1.5 min-h-[40px]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="btn-primary text-xs px-4 py-1.5 min-h-[40px]"
            >
              {saving ? "Saving…" : "Save as New Version"}
            </button>
          </div>
        </div>
      )}

      <div className="card-surface p-0 overflow-x-auto shadow-sm">
        <table className="data-table w-full" aria-label="Ruleset versions">
          <thead>
            <tr>
              <th className="pl-4 py-3 font-semibold">Version</th>
              <th className="py-3 font-semibold">Effective</th>
              <th className="py-3 font-semibold text-center">Bands</th>
              <th className="py-3 font-semibold">Status</th>
              <th className="py-3 font-semibold">Created</th>
              <th className="py-3 pr-4 text-right font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="py-16 text-center">
                  <span className="font-mono text-sm text-ink-600 animate-pulse">
                    Loading ruleset versions…
                  </span>
                </td>
              </tr>
            ) : versions.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-16 text-center">
                  <p className="font-display text-base font-semibold text-ink-900">
                    No versions yet
                  </p>
                  <p className="font-body text-xs text-ink-600 mt-1">
                    The rule engine is running on the built-in placeholder default. Create the
                    first version above to start managing it here.
                  </p>
                </td>
              </tr>
            ) : (
              versions.map((v) => (
                <tr key={v.version} className="hover:bg-ink-900/[0.03] transition-colors">
                  <td className="pl-4 py-3 align-middle font-mono text-xs text-ink-900">
                    {v.version}
                  </td>
                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    {formatDate(v.effective_date)}
                  </td>
                  <td className="py-3 align-middle text-center font-mono text-xs text-ink-900">
                    {v.bands.length}
                  </td>
                  <td className="py-3 align-middle">
                    <div className="flex items-center gap-1.5">
                      {v.is_active && (
                        <span className="status-chip text-verdict-pass bg-verdict-pass/10 border-verdict-pass/20">
                          <CheckCircle2 size={11} /> Active
                        </span>
                      )}
                      {v.is_placeholder && (
                        <span className="status-chip text-verdict-pending bg-verdict-pending/10 border-verdict-pending/20">
                          <AlertTriangle size={11} /> Placeholder
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 align-middle font-mono text-xs text-ink-600">
                    {formatDate(v.created_at)}
                  </td>
                  <td className="pr-4 py-3 align-middle text-right">
                    <button
                      type="button"
                      onClick={() => handleActivate(v.version)}
                      disabled={v.is_active || busyVersion === v.version}
                      className="btn-secondary text-xs px-3 py-1 min-h-[36px]"
                    >
                      {busyVersion === v.version ? "Activating…" : v.is_active ? "Active" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}

export default function AdminRulesetsPage() {
  return (
    <AdminGuard>
      <RulesetAdminScreen />
    </AdminGuard>
  );
}
