"use client";
/**
 * Placeholder for nav destinations that exist in the §4.2 header sketch
 * but belong to later phases (so those links do not 404).
 */
import { AppShell } from "@/app/components/AppShell";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";

export function ComingSoon({
  title,
  phase,
  description,
}: {
  title: string;
  phase: string;
  description: string;
}) {
  return (
    <AppShell>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900">{title}</h1>
          <p className="font-body text-sm text-ink-600 mt-1">{description}</p>
        </div>
        <span className="status-chip text-ink-600 border-ink-600/20 bg-ink-900/5">
          {phase} — Coming soon
        </span>
      </div>
      <CalibrationRuler className="mb-6" />
      <div
        className="card-surface flex flex-col items-center justify-center gap-3 text-center"
        style={{ minHeight: 280 }}
      >
        <p className="font-display text-base font-semibold text-ink-900">
          This screen is not in the current phase.
        </p>
        <p className="font-body text-sm text-ink-600 max-w-md">
          The header keeps this destination so navigation matches the §4.2 layout
          sketch. Functionality ships in {phase}.
        </p>
      </div>
    </AppShell>
  );
}
