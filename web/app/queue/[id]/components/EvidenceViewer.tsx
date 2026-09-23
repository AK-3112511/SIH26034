"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Layers, ShieldCheck } from "lucide-react";
import { bboxToStyle, type Size } from "@/lib/bbox";
import type { ExtractedField } from "@/lib/api";
import { humaniseFieldName } from "./rules";

interface EvidenceViewerProps {
  imageUrl: string;
  scanId: string;
  evidenceHash: string;
  mmPerPx: number | null;
  pdpAreaCm2: number | null;
  fields: ExtractedField[];
  /** Field currently highlighted from the table, if any. */
  activeField: string | null;
  onActiveFieldChange: (fieldName: string | null) => void;
  overriddenFields: Record<string, string>;
}

/**
 * The raw capture with the extracted-field boxes drawn over it.
 *
 * The image pixels are never modified — the overlay is a sibling layer, so the
 * bytes on screen are the bytes the evidence hash covers.
 *
 * Boxes are positioned against the *rendered* image rectangle, which is
 * measured rather than assumed: the image is `object-contain` inside a fixed
 * frame, so it is letterboxed by an amount that depends on both the photo's
 * aspect ratio and the current viewport width. A ResizeObserver keeps the
 * boxes attached to the photo as the window changes.
 */
export function EvidenceViewer({
  imageUrl,
  scanId,
  evidenceHash,
  mmPerPx,
  pdpAreaCm2,
  fields,
  activeField,
  onActiveFieldChange,
  overriddenFields,
}: EvidenceViewerProps) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [naturalSize, setNaturalSize] = useState<Size | null>(null);
  const [frameSize, setFrameSize] = useState<Size | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  const measureFrame = useCallback(() => {
    const el = frameRef.current;
    if (!el) return;
    setFrameSize({ width: el.clientWidth, height: el.clientHeight });
  }, []);

  useEffect(() => {
    measureFrame();
    const el = frameRef.current;
    if (!el || typeof ResizeObserver === "undefined") {
      // jsdom and very old browsers: fall back to window resize.
      window.addEventListener("resize", measureFrame);
      return () => window.removeEventListener("resize", measureFrame);
    }
    const observer = new ResizeObserver(measureFrame);
    observer.observe(el);
    return () => observer.disconnect();
  }, [measureFrame]);

  const drawableFields = fields
    .map((field) => ({ field, style: bboxToStyle(field.bbox, naturalSize, frameSize) }))
    .filter((entry): entry is { field: ExtractedField; style: NonNullable<ReturnType<typeof bboxToStyle>> } =>
      entry.style !== null
    );

  const withoutBoxes = fields.length - drawableFields.length;

  return (
    <section className="space-y-3" aria-labelledby="evidence-heading">
      <div className="flex items-center gap-2">
        <Layers size={16} className="text-brass-500" aria-hidden />
        <h2
          id="evidence-heading"
          className="font-display text-sm font-semibold uppercase tracking-wider text-ink-900"
        >
          Evidence image
        </h2>
      </div>

      <div
        ref={frameRef}
        className="relative flex h-[420px] select-none items-center justify-center overflow-hidden rounded-card border border-ink-900/10 bg-ink-900/5"
      >
        {imageFailed ? (
          <p className="px-6 text-center font-body text-sm text-ink-600">
            The evidence image could not be loaded. The scan record and its rule results are
            unaffected; check that the file store is reachable.
          </p>
        ) : (
          <img
            src={imageUrl}
            alt={`Evidence photograph for scan ${scanId}`}
            className="h-full w-full object-contain"
            onLoad={(e) => {
              const img = e.currentTarget;
              setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
              measureFrame();
            }}
            onError={() => setImageFailed(true)}
          />
        )}

        <div className="pointer-events-none absolute inset-0" data-testid="bbox-overlay">
          {drawableFields.map(({ field, style }) => {
            const isActive = activeField === field.field_name;
            const isOverridden = field.field_name in overriddenFields;

            return (
              <div
                key={field.id}
                data-testid={`bbox-${field.field_name}`}
                style={{
                  left: `${style.left}px`,
                  top: `${style.top}px`,
                  width: `${style.width}px`,
                  height: `${style.height}px`,
                }}
                className={`pointer-events-auto absolute cursor-pointer rounded-[2px] border-2 transition-colors duration-150 ${
                  isActive
                    ? "border-brass-500 bg-brass-500/20 ring-2 ring-brass-500/40"
                    : isOverridden
                    ? "border-ink-900 bg-ink-900/10"
                    : "border-verdict-fail/80 bg-verdict-fail/10"
                }`}
                onMouseEnter={() => onActiveFieldChange(field.field_name)}
                onMouseLeave={() => onActiveFieldChange(null)}
              >
                <span
                  className={`absolute -top-5 left-0 whitespace-nowrap rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                    isActive ? "z-20 bg-brass-500 text-white" : "bg-ink-900/80 text-white"
                  }`}
                >
                  {humaniseFieldName(field.field_name)}
                  {field.ocr_confidence !== null &&
                    ` ${Math.round(field.ocr_confidence * 100)}%`}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="card-surface flex flex-wrap items-center justify-between gap-2 bg-paper-100/60 p-3 text-xs">
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} className="text-verdict-pass" aria-hidden />
          <span className="font-mono text-[11px] text-ink-600">
            Hash {evidenceHash.slice(0, 16)}…{evidenceHash.slice(-8)}
          </span>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11px] text-ink-600">
          {mmPerPx !== null && <span>{mmPerPx.toFixed(3)} mm/px</span>}
          {pdpAreaCm2 !== null && <span>Panel {pdpAreaCm2.toFixed(1)} cm²</span>}
        </div>
      </div>

      {withoutBoxes > 0 && (
        <p className="font-body text-xs text-ink-600">
          {withoutBoxes} extracted {withoutBoxes === 1 ? "field has" : "fields have"} no recorded
          position on the image and {withoutBoxes === 1 ? "is" : "are"} listed below only.
        </p>
      )}
    </section>
  );
}
