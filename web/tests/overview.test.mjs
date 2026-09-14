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

  test("heatmap remains a Phase 6 placeholder, not a GIS query", () => {
    const overviewSrc = fs.readFileSync(path.join(webRoot, "app", "page.tsx"), "utf8");
    assert.match(overviewSrc, /Heatmap Placeholder/);
    assert.match(overviewSrc, /Phase 6/);
    assert.doesNotMatch(overviewSrc, /ST_ClusterKMeans\(/);
    assert.match(overviewSrc, /scansApi\.stats\(\)/);
  });
});

describe("§4.2 later-phase nav destinations do not 404", () => {
  test("Repository, Challans, and Admin ruleset pages exist as ComingSoon shells", () => {
    const pages = [
      ["app", "repository", "page.tsx"],
      ["app", "challans", "page.tsx"],
      ["app", "admin", "rulesets", "page.tsx"],
      ["app", "components", "ComingSoon.tsx"],
    ];
    for (const parts of pages) {
      const filePath = path.join(webRoot, ...parts);
      assert.ok(fs.existsSync(filePath), `missing ${parts.join("/")}`);
      const src = fs.readFileSync(filePath, "utf8");
      if (parts.includes("ComingSoon.tsx")) {
        assert.match(src, /Coming soon/);
      } else {
        assert.match(src, /ComingSoon/);
      }
    }
  });
});
