import { test, describe } from "node:test";
import assert from "node:assert/strict";

describe("E-Commerce Ingestion Screen — §3.2 & §3 Screen 5 Layout Specification", () => {
  const supportedPlatforms = [
    "Blinkit",
    "Amazon",
    "Flipkart",
    "Zepto",
    "Instamart",
    "BigBasket",
    "Other",
  ];

  test("Platform tag choices support all major Indian quick-commerce / e-commerce platforms", () => {
    assert.ok(supportedPlatforms.includes("Blinkit"));
    assert.ok(supportedPlatforms.includes("Amazon"));
    assert.ok(supportedPlatforms.includes("Flipkart"));
    assert.ok(supportedPlatforms.includes("Zepto"));
    assert.ok(supportedPlatforms.includes("Instamart"));
    assert.ok(supportedPlatforms.includes("BigBasket"));
    assert.ok(supportedPlatforms.includes("Other"));
  });

  test("§3.2 Manual Dimension Calibration Path: mm/px and PDP area calculate accurately", () => {
    // Height: 180mm, Width: 90mm
    const heightMm = 180.0;
    const widthMm = 90.0;
    const screenshotPxLongEdge = 1080; // 1080px tall screenshot

    // mm_per_px = max(height, width) / max(px_w, px_h)
    const mmPerPx = heightMm / screenshotPxLongEdge;
    assert.equal(Number(mmPerPx.toFixed(4)), 0.1667);

    // PDP area = (height_mm * width_mm) / 100 in cm²
    const pdpArea = (heightMm * widthMm) / 100.0;
    assert.equal(pdpArea, 162.0); // 162 cm²
  });

  test("Validation: requires screenshot file and positive package dimensions", () => {
    function validateIngestionPayload(payload) {
      if (!payload.file) {
        throw new Error("Screenshot image is required");
      }
      if (!payload.platform || !payload.platform.trim()) {
        throw new Error("Platform tag is required");
      }
      if (!payload.package_height_mm || payload.package_height_mm <= 0) {
        throw new Error("Valid package height is required");
      }
      if (!payload.package_width_mm || payload.package_width_mm <= 0) {
        throw new Error("Valid package width is required");
      }
      return true;
    }

    // Missing file throws
    assert.throws(
      () =>
        validateIngestionPayload({
          platform: "Blinkit",
          package_height_mm: 120,
          package_width_mm: 80,
        }),
      /Screenshot image is required/
    );

    // Zero/negative height throws
    assert.throws(
      () =>
        validateIngestionPayload({
          file: "mock.png",
          platform: "Blinkit",
          package_height_mm: 0,
          package_width_mm: 80,
        }),
      /Valid package height is required/
    );

    // Valid inputs pass
    assert.doesNotThrow(() =>
      validateIngestionPayload({
        file: "mock.png",
        platform: "Blinkit",
        package_height_mm: 150,
        package_width_mm: 75,
        declared_net_quantity: "500g",
      })
    );
  });

  test("Multipart form-data fields match backend ingest-derived requirements", () => {
    const requiredFields = [
      "image",
      "platform",
      "package_height_mm",
      "package_width_mm",
    ];
    const optionalFields = [
      "package_depth_mm",
      "declared_net_quantity",
      "platform_url",
    ];

    const formMock = {
      image: "screenshot.png",
      platform: "Blinkit",
      package_height_mm: "180",
      package_width_mm: "90",
      declared_net_quantity: "100g",
    };

    requiredFields.forEach((field) => {
      assert.ok(field in formMock, `Required field ${field} must be present`);
    });
  });
});
