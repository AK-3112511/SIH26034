import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EvidenceViewer } from "@/app/queue/[id]/components/EvidenceViewer";
import type { ExtractedField } from "@/lib/api";

const FRAME_WIDTH = 400;
const FRAME_HEIGHT = 400;
const NATURAL_WIDTH = 200;
const NATURAL_HEIGHT = 100;

const fields: ExtractedField[] = [
  {
    id: "f1",
    field_name: "mrp",
    raw_text: "MRP Rs.120",
    bbox: { x_min: 0, y_min: 0, x_max: 100, y_max: 50 },
    ocr_confidence: 0.91,
    semantic_confidence: 0.88,
    font_height_mm: 2.4,
  },
  {
    id: "f2",
    field_name: "net_quantity",
    raw_text: "500 g",
    bbox: null,
    ocr_confidence: 0.8,
    semantic_confidence: 0.8,
    font_height_mm: 1.9,
  },
];

/**
 * jsdom reports every element as 0x0 and every image as having no natural
 * size, so both have to be stubbed for the geometry to be exercised at all.
 */
function stubLayout() {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(FRAME_WIDTH);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(FRAME_HEIGHT);
  vi.spyOn(HTMLImageElement.prototype, "naturalWidth", "get").mockReturnValue(NATURAL_WIDTH);
  vi.spyOn(HTMLImageElement.prototype, "naturalHeight", "get").mockReturnValue(NATURAL_HEIGHT);
}

function renderViewer() {
  return render(
    <EvidenceViewer
      imageUrl="/api/v1/files/evidence.jpg"
      scanId="scan-1"
      evidenceHash={"a".repeat(64)}
      mmPerPx={0.152}
      pdpAreaCm2={230.4}
      fields={fields}
      activeField={null}
      onActiveFieldChange={() => {}}
      overriddenFields={{}}
    />
  );
}

describe("EvidenceViewer", () => {
  it("draws no boxes until the image has loaded and reported its size", () => {
    stubLayout();
    renderViewer();
    expect(screen.queryByTestId("bbox-mrp")).not.toBeInTheDocument();
  });

  it("anchors a box to the rendered image, allowing for the letterbox", () => {
    stubLayout();
    renderViewer();

    fireEvent.load(screen.getByAltText(/evidence photograph/i));

    const box = screen.getByTestId("bbox-mrp");
    // 200x100 photo in a 400x400 frame is scaled x2 and centred vertically,
    // leaving a 100px bar above it. A box on the top-left quarter of the photo
    // therefore starts 100px down, not at the top of the frame.
    expect(box.style.left).toBe("0px");
    expect(box.style.top).toBe("100px");
    expect(box.style.width).toBe("200px");
    expect(box.style.height).toBe("100px");
  });

  it("says how many fields have no position rather than dropping them silently", () => {
    stubLayout();
    renderViewer();
    fireEvent.load(screen.getByAltText(/evidence photograph/i));

    expect(screen.queryByTestId("bbox-net_quantity")).not.toBeInTheDocument();
    expect(screen.getByText(/1 extracted field has no recorded position/i)).toBeInTheDocument();
  });

  it("explains a missing image instead of showing a broken frame", () => {
    stubLayout();
    renderViewer();

    fireEvent.error(screen.getByAltText(/evidence photograph/i));
    expect(screen.getByText(/could not be loaded/i)).toBeInTheDocument();
  });

  it("shows the evidence hash so it can be checked against the record", () => {
    stubLayout();
    renderViewer();
    expect(screen.getByText(/Hash a{16}/)).toBeInTheDocument();
  });
});
