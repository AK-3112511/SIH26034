export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="font-display text-2xl font-bold text-ink-900">
          Enforcement & Review Overview
        </h2>
        <p className="font-body text-base text-ink-600">
          Real-time oversight of PCR 2011 field inspections, e-commerce ingestion, and challan generations.
        </p>
      </div>

      {/* Signature Calibration Tick Rule Motif */}
      <div className="calibration-ruler" />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="card-surface space-y-3">
          <div className="flex justify-between items-center">
            <span className="font-body text-xs font-semibold text-ink-600 uppercase tracking-wider">
              Review Queue
            </span>
            <span className="seal-badge seal-badge-pass">
              PASS
            </span>
          </div>
          <p className="font-mono text-3xl font-bold text-ink-900">0</p>
          <p className="font-body text-xs text-ink-600">Pending Senior LMO Review</p>
        </div>

        <div className="card-surface space-y-3">
          <div className="flex justify-between items-center">
            <span className="font-body text-xs font-semibold text-ink-600 uppercase tracking-wider">
              Token Integration
            </span>
            <span className="font-body text-xs font-medium text-brass-500">
              Tailwind V3
            </span>
          </div>
          <p className="font-display text-xl font-bold text-ink-900">Design Tokens Layer</p>
          <p className="font-body text-xs text-ink-600">
            Colors, Typography (&sect;3), and Base Spacing (&sect;4) loaded.
          </p>
        </div>
      </div>
    </div>
  );
}
