/**
 * Bounding-box geometry for the evidence viewer.
 *
 * Two things were wrong before, and both of them silently produced boxes in
 * the wrong place rather than an error:
 *
 * 1. The stored bbox is `{x_min, y_min, x_max, y_max}` in *source image
 *    pixels*, but the viewer read `{x1, y1, x2, y2}` — every coordinate came
 *    back `undefined`, so every box was positioned at `NaN%`.
 * 2. Boxes were positioned as a percentage of the *container*, while the image
 *    inside it is `object-contain` and therefore letterboxed. Even with the
 *    right coordinates, every box would have been offset by the letterbox
 *    margin and scaled against the wrong dimension.
 *
 * The shapes accepted here mirror `normalise_bbox()` in
 * `backend/app/services/challan_pdf.py`, so a box drawn on screen and a box
 * drawn into the Section 39 notice describe the same region of the same photo.
 */

/** A box in source-image pixel space. */
export interface PixelBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Size {
  width: number;
  height: number;
}

/** Where the image actually is inside its `object-contain` container. */
export interface RenderedImage {
  offsetX: number;
  offsetY: number;
  width: number;
  height: number;
}

/** CSS offsets, in pixels relative to the container's top-left. */
export interface BoxStyle {
  left: number;
  top: number;
  width: number;
  height: number;
}

function isFiniteNumber(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/**
 * Normalise any stored bbox shape to `{x, y, w, h}` in source pixels.
 * Returns null for anything unrecognised — a box we cannot place is not drawn.
 */
export function normaliseBBox(bbox: unknown): PixelBox | null {
  if (!bbox) return null;

  if (Array.isArray(bbox)) {
    // Matches the backend: a 4-element array is [x, y, w, h].
    if (bbox.length !== 4 || !bbox.every(isFiniteNumber)) return null;
    const [x, y, w, h] = bbox as number[];
    return w <= 0 || h <= 0 ? null : { x, y, w, h };
  }

  if (typeof bbox !== "object") return null;
  const b = bbox as Record<string, unknown>;

  const pairs: Array<[string, string, string, string]> = [
    ["x_min", "y_min", "x_max", "y_max"],
    ["x1", "y1", "x2", "y2"],
  ];
  for (const [kx1, ky1, kx2, ky2] of pairs) {
    if (isFiniteNumber(b[kx1]) && isFiniteNumber(b[ky1]) && isFiniteNumber(b[kx2]) && isFiniteNumber(b[ky2])) {
      const x1 = b[kx1] as number;
      const y1 = b[ky1] as number;
      const x2 = b[kx2] as number;
      const y2 = b[ky2] as number;
      const w = Math.abs(x2 - x1);
      const h = Math.abs(y2 - y1);
      return w === 0 || h === 0 ? null : { x: Math.min(x1, x2), y: Math.min(y1, y2), w, h };
    }
  }

  if (isFiniteNumber(b.x) && isFiniteNumber(b.y) && isFiniteNumber(b.w) && isFiniteNumber(b.h)) {
    const w = b.w as number;
    const h = b.h as number;
    return w <= 0 || h <= 0 ? null : { x: b.x as number, y: b.y as number, w, h };
  }

  return null;
}

/**
 * Where an `object-contain` image sits inside its container.
 *
 * The image is scaled by the smaller of the two ratios and centred, leaving
 * letterbox bars on the other axis. Bounding boxes must be placed against
 * *this* rectangle, not the container.
 */
export function containRect(natural: Size, container: Size): RenderedImage | null {
  if (natural.width <= 0 || natural.height <= 0) return null;
  if (container.width <= 0 || container.height <= 0) return null;

  const scale = Math.min(container.width / natural.width, container.height / natural.height);
  const width = natural.width * scale;
  const height = natural.height * scale;

  return {
    offsetX: (container.width - width) / 2,
    offsetY: (container.height - height) / 2,
    width,
    height,
  };
}

/**
 * Project a source-pixel box onto the rendered image.
 *
 * `natural` may be smaller than the coordinates if the pipeline ran on a
 * different resolution than the stored image; the caller is responsible for
 * passing the natural size of the image it is actually displaying.
 */
export function projectBox(box: PixelBox, natural: Size, rendered: RenderedImage): BoxStyle | null {
  if (natural.width <= 0 || natural.height <= 0) return null;

  const scaleX = rendered.width / natural.width;
  const scaleY = rendered.height / natural.height;

  return {
    left: rendered.offsetX + box.x * scaleX,
    top: rendered.offsetY + box.y * scaleY,
    width: box.w * scaleX,
    height: box.h * scaleY,
  };
}

/** Convenience: stored bbox → CSS offsets, or null if it cannot be placed. */
export function bboxToStyle(
  bbox: unknown,
  natural: Size | null,
  container: Size | null
): BoxStyle | null {
  if (!natural || !container) return null;
  const box = normaliseBBox(bbox);
  if (!box) return null;
  const rendered = containRect(natural, container);
  if (!rendered) return null;
  return projectBox(box, natural, rendered);
}
