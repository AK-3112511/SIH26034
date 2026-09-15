import { test, describe } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");

describe("Overview — §3 Screen 2 counts and heatmap placeholder", () => {
  test("today's counts are four explicit cards from /scans/stats", () => {
    const stats = {
      scanned_today: 12,
      passed_today: 7,
      failed_today: 2,
      pending_review: 4,
      calibration_failed_today: 1,
    };

    const cards = [
      { label: "Scanned Today", value: stats.scanned_today },
      { label: "Passed", value: stats.passed_today },
      { label: "Failed", value: stats.failed_today },
      { label: "Pending Review", value: stats.pending_review },
    ];

    assert.equal(cards.length, 4);
    assert.equal(cards[0].value, 12);
    assert.equal(cards[3].value, 4);
    assert.ok(stats.pending_review !== stats.scanned_today);
  });

  test("heatmap is the real Phase 6.1 PostGIS-clustered component, not a placeholder", () => {
    const overviewSrc = fs.readFileSync(path.join(webRoot, "app", "page.tsx"), "utf8");
    assert.doesNotMatch(overviewSrc, /Heatmap Placeholder/);
    assert.doesNotMatch(overviewSrc, /Coming soon/i);
    assert.match(overviewSrc, /next\/dynamic/);
    assert.match(overviewSrc, /components\/Heatmap/);
    assert.match(overviewSrc, /ssr:\s*false/);
    assert.match(overviewSrc, /scansApi\.stats\(\)/);
  });
});

describe("Heatmap component — §7.1 server-side clustering, §9 map styling", () => {
  const heatmapSrc = fs.readFileSync(
    path.join(webRoot, "app", "components", "Heatmap.tsx"),
    "utf8"
  );

  test("fetches server-side clusters via dashboardApi, never raw points", () => {
    assert.match(heatmapSrc, /dashboardApi\.heatmap/);
    assert.match(heatmapSrc, /"use client"/);
  });

  test("uses a muted/low-saturation basemap per §9 (not default bright OSM/Google tiles)", () => {
    assert.match(heatmapSrc, /basemaps\.cartocdn\.com\/light_all/);
  });

  test("verdict-colored clusters use the design system's verdict tokens", () => {
    assert.match(heatmapSrc, /#B3261E/); // verdict-fail
    assert.match(heatmapSrc, /#1E7A4D/); // verdict-pass
    assert.match(heatmapSrc, /#B5730B/); // verdict-pending
  });

  test("refetches clusters on viewport change (zoom/bbox), not just once on mount", () => {
    assert.match(heatmapSrc, /moveend/);
    assert.match(heatmapSrc, /zoomend/);
  });
});

describe("§4.2 later-phase nav destinations do not 404", () => {
  // Note: as of Phase 5.3, Challans is a real screen, not a ComingSoon shell —
  // this test previously asserted the stale Phase-4-era placeholder text for
  // it and silently passed. Fixed here to just confirm the routes resolve;
  // ComingSoon.tsx itself is asserted separately since it's still used by
  // whichever admin screens haven't landed yet in the current phase.
  test("Repository, Challans, and Admin ruleset pages exist", () => {
    const pages = [
      ["app", "repository", "page.tsx"],
      ["app", "challans", "page.tsx"],
      ["app", "admin", "rulesets", "page.tsx"],
    ];
    for (const parts of pages) {
      const filePath = path.join(webRoot, ...parts);
      assert.ok(fs.existsSync(filePath), `missing ${parts.join("/")}`);
    }
  });

  test("ComingSoon shell component still exists for not-yet-built admin screens", () => {
    const filePath = path.join(webRoot, "app", "components", "ComingSoon.tsx");
    assert.ok(fs.existsSync(filePath));
    const src = fs.readFileSync(filePath, "utf8");
    assert.match(src, /Coming soon/);
  });
});
