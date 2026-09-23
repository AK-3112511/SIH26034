import { describe, expect, it } from "vitest";
import { bboxToStyle, containRect, normaliseBBox, projectBox } from "@/lib/bbox";

describe("normaliseBBox", () => {
  it("reads the shape the pipeline actually stores", () => {
    expect(normaliseBBox({ x_min: 10, y_min: 20, x_max: 110, y_max: 70 })).toEqual({
      x: 10,
      y: 20,
      w: 100,
      h: 50,
    });
  });

  it("still reads the older x1/y1/x2/y2 shape", () => {
    expect(normaliseBBox({ x1: 5, y1: 5, x2: 15, y2: 25 })).toEqual({ x: 5, y: 5, w: 10, h: 20 });
  });

  it("treats a four-element array as x, y, w, h, matching the backend", () => {
    expect(normaliseBBox([4, 8, 16, 32])).toEqual({ x: 4, y: 8, w: 16, h: 32 });
  });

  it("normalises a reversed box rather than producing a negative size", () => {
    expect(normaliseBBox({ x_min: 110, y_min: 70, x_max: 10, y_max: 20 })).toEqual({
      x: 10,
      y: 20,
      w: 100,
      h: 50,
    });
  });

  it("refuses anything it cannot place", () => {
    expect(normaliseBBox(null)).toBeNull();
    expect(normaliseBBox({})).toBeNull();
    expect(normaliseBBox({ left: 1, top: 2 })).toBeNull();
    expect(normaliseBBox([1, 2, 3])).toBeNull();
    expect(normaliseBBox({ x_min: 1, y_min: 1, x_max: 1, y_max: 9 })).toBeNull();
  });
});

describe("containRect", () => {
  it("letterboxes top and bottom when the image is wider than the frame", () => {
    // 200x100 image in a 400x400 frame: scaled x2, 200px tall, 100px bars.
    expect(containRect({ width: 200, height: 100 }, { width: 400, height: 400 })).toEqual({
      offsetX: 0,
      offsetY: 100,
      width: 400,
      height: 200,
    });
  });

  it("letterboxes left and right when the image is taller than the frame", () => {
    expect(containRect({ width: 100, height: 200 }, { width: 400, height: 400 })).toEqual({
      offsetX: 100,
      offsetY: 0,
      width: 200,
      height: 400,
    });
  });

  it("returns null for a frame that has not been measured yet", () => {
    expect(containRect({ width: 100, height: 100 }, { width: 0, height: 0 })).toBeNull();
  });
});

describe("projectBox", () => {
  it("places a box against the image, not against the frame", () => {
    const natural = { width: 200, height: 100 };
    const rendered = containRect(natural, { width: 400, height: 400 })!;

    // A box covering the top-left quarter of the photo.
    const style = projectBox({ x: 0, y: 0, w: 100, h: 50 }, natural, rendered);

    // Scaled x2, and pushed down by the 100px letterbox bar. Positioning this
    // as a percentage of the frame would have put it at the very top.
    expect(style).toEqual({ left: 0, top: 100, width: 200, height: 100 });
  });
});

describe("bboxToStyle", () => {
  it("draws nothing until the image reports its natural size", () => {
    expect(bboxToStyle({ x_min: 0, y_min: 0, x_max: 10, y_max: 10 }, null, { width: 100, height: 100 })).toBeNull();
  });

  it("converts a stored box straight to CSS offsets", () => {
    const style = bboxToStyle(
      { x_min: 50, y_min: 25, x_max: 150, y_max: 75 },
      { width: 200, height: 100 },
      { width: 400, height: 400 }
    );
    expect(style).toEqual({ left: 100, top: 150, width: 200, height: 100 });
  });
});
