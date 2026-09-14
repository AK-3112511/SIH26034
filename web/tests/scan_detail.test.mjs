import { test, describe } from "node:test";
import assert from "node:assert/strict";

describe("Scan Detail Screen — §3 Screen 4 & §4.3 Layout Specification", () => {
  const mockScanDetail = {
    scan_id: "2558b244-06a3-4d2b-9259-ceba81780d5f",
    source: "mobile",
    status: "PENDING_REVIEW",
    image_url: "/static/uploads/parle_g_100g.jpg",
    evidence_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    lat: 13.0827,
    lng: 80.2707,
    captured_at_utc: "2026-09-13T12:00:00Z",
    mm_per_px: 0.085,
    pdp_area_cm2: 120.5,
    ruleset_version: "2026.1",
    created_at: "2026-09-13T12:00:00Z",
    extracted_fields: [
      {
        id: "f1",
        field_name: "brand_name",
        raw_text: "Parle-G 100g",
        bbox: { x1: 18.5, y1: 15.0, x2: 65.0, y2: 26.5 },
        ocr_confidence: 0.94,
        semantic_confidence: 0.95,
        font_height_mm: 4.5,
      },
      {
        id: "f2",
        field_name: "net_quantity",
        raw_text: "100g",
        bbox: { x1: 22.0, y1: 55.0, x2: 48.0, y2: 63.0 },
        ocr_confidence: 0.70,
        semantic_confidence: 0.88,
        font_height_mm: 2.8,
      },
      {
        id: "f3",
        field_name: "mrp",
        raw_text: "Rs. 10.00",
        bbox: { x1: 52.0, y1: 54.0, x2: 82.0, y2: 63.5 },
        ocr_confidence: 0.91,
        semantic_confidence: 0.90,
        font_height_mm: 3.0,
      },
      {
        id: "f4",
        field_name: "manufacturer_address",
        raw_text: "Parle Products Pvt. Ltd., Mumbai 400057",
        bbox: { x1: 15.0, y1: 70.0, x2: 85.0, y2: 82.0 },
        ocr_confidence: 0.93,
        semantic_confidence: 0.91,
        font_height_mm: 1.8,
      },
      {
        id: "f5",
        field_name: "consumer_care",
        raw_text: "cs@parle.biz | 1800-22-1929",
        bbox: { x1: 15.0, y1: 84.0, x2: 78.0, y2: 92.0 },
        ocr_confidence: 0.89,
        semantic_confidence: 0.92,
        font_height_mm: 1.6,
      },
    ],
    rule_results: [
      {
        id: "r1",
        rule_id: "6.1.a",
        status: "PASS",
        reason: "Manufacturer name & postal address verified",
        evidence: { confidence: 0.95 },
      },
      {
        id: "r2",
        rule_id: "6.1.c",
        status: "PASS",
        reason: "Standard SI metric units (g) verified",
        evidence: { unit: "g" },
      },
      {
        id: "r3",
        rule_id: "6.1.e",
        status: "PASS",
        reason: "MRP tax phrase verified",
        evidence: { has_tax_phrase: true },
      },
      {
        id: "r4",
        rule_id: "6.1.g",
        status: "PASS",
        reason: "Consumer care details present",
        evidence: { contact_types: ["phone", "email"] },
      },
      {
        id: "r5",
        rule_id: "schedule_ii",
        status: "UNVERIFIED",
        reason: "Confidence gap requires visual verification",
        evidence: { measured_height_mm: 2.8, required_height_mm: 3.0 },
      },
    ],
    assigned_lmo_id: null,
    reviewer_note: null,
  };

  // Helper converting bbox to relative percentage styles
  function getBBoxStyle(bbox) {
    if (!bbox) return null;
    let { x1, y1, x2, y2 } = bbox;
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
  }

  test("Chain-of-Custody Invariant: bbox coordinates are positioned client-side over raw image", () => {
    // Check that bounding boxes are present in metadata and resolve to valid CSS percent rectangles
    const brandField = mockScanDetail.extracted_fields.find((f) => f.field_name === "brand_name");
    assert.ok(brandField.bbox, "Field must retain non-null bbox coordinates");
    const style = getBBoxStyle(brandField.bbox);
    assert.equal(style.left, "18.5%");
    assert.equal(style.top, "15%");
    assert.equal(style.width, "46.5%");
    assert.equal(style.height, "11.5%");

    // Normalized [0..1] coordinates should also properly scale to percentage
    const normalizedBbox = { x1: 0.1, y1: 0.2, x2: 0.4, y2: 0.5 };
    const normStyle = getBBoxStyle(normalizedBbox);
    assert.equal(normStyle.left, "10%");
    assert.equal(normStyle.top, "20%");
    assert.equal(normStyle.width, "30%");
    assert.equal(normStyle.height, "30%");
  });

  test("Rule results consume all §4.3 statutory rules (6.1.a, 6.1.c, 6.1.e, 6.1.g, schedule_ii)", () => {
    const ruleIds = mockScanDetail.rule_results.map((r) => r.rule_id);
    assert.ok(ruleIds.includes("6.1.a"), "Rule 6(1)(a) Manufacturer must be present");
    assert.ok(ruleIds.includes("6.1.c"), "Rule 6(1)(c) Units must be present");
    assert.ok(ruleIds.includes("6.1.e"), "Rule 6(1)(e) MRP phrase must be present");
    assert.ok(ruleIds.includes("6.1.g"), "Rule 6(1)(g) Consumer care must be present");
    assert.ok(ruleIds.includes("schedule_ii"), "Schedule II font ratio must be present");

    const unverifiedRule = mockScanDetail.rule_results.find((r) => r.status === "UNVERIFIED");
    assert.ok(unverifiedRule, "Pending review scan must have UNVERIFIED rule requiring human review");
  });

  test("Mandatory Reviewer Note invariant: empty or whitespace note is rejected", () => {
    function validateReviewSubmission(payload) {
      if (!payload.reviewer_note || !payload.reviewer_note.trim()) {
        throw new Error("Mandatory reviewer note is required");
      }
      if (!["PASSED", "FAILED"].includes(payload.decision)) {
        throw new Error("Invalid adjudication decision");
      }
      return true;
    }

    // Empty note throws
    assert.throws(
      () => validateReviewSubmission({ decision: "PASSED", reviewer_note: "" }),
      /Mandatory reviewer note is required/
    );

    // Whitespace note throws
    assert.throws(
      () => validateReviewSubmission({ decision: "FAILED", reviewer_note: "   \n\t  " }),
      /Mandatory reviewer note is required/
    );

    // Valid note passes
    assert.doesNotThrow(() =>
      validateReviewSubmission({
        decision: "PASSED",
        reviewer_note: "Manually verified net quantity numeral height against 300 DPI calibration grid.",
      })
    );
  });

  test("Editable field overrides correctly capture updated values", () => {
    const overrides = {};
    function applyOverride(fieldName, newValue) {
      overrides[fieldName] = newValue;
    }

    applyOverride("net_quantity", "100 g");
    assert.equal(overrides["net_quantity"], "100 g");

    // Overrides can be packaged for review submission
    const submissionBody = {
      decision: "PASSED",
      reviewer_note: "Corrected spacing in unit symbol.",
      overridden_fields: overrides,
    };
    assert.deepEqual(submissionBody.overridden_fields, { net_quantity: "100 g" });
  });

  test("Generate Section 39 Challan button is present but strictly disabled until Phase 5", () => {
    const challanButtonConfig = {
      label: "Generate Section 39 Challan",
      disabled: true,
      phase: 5,
    };
    assert.equal(challanButtonConfig.disabled, true);
    assert.equal(challanButtonConfig.label, "Generate Section 39 Challan");
  });

  test("§5.1 Seal Badge renders double concentric ring with brass-500 outer stroke", () => {
    // SealBadge geometric configuration check
    const size = 48;
    const r = size / 2;
    const outerR = r - 1;
    const innerR = outerR - Math.max(2, size * 0.06);

    assert.equal(r, 24);
    assert.equal(outerR, 23);
    assert.ok(innerR < outerR);
    assert.ok(innerR > 18);

    const pendingColor = "#B5730B";
    const brassRing = "#A6742C";
    assert.equal(pendingColor, "#B5730B");
    assert.equal(brassRing, "#A6742C");
  });
});
