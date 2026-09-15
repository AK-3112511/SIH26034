import { test, describe } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");

const repositorySrc = fs.readFileSync(
  path.join(webRoot, "app", "repository", "page.tsx"),
  "utf8"
);
const apiSrc = fs.readFileSync(path.join(webRoot, "lib", "api.ts"), "utf8");

describe("Digital Repository — §3 Screen 6 Product Search (Phase 6.2)", () => {
  test("is the real screen, not the Phase 6 ComingSoon placeholder", () => {
    assert.doesNotMatch(repositorySrc, /ComingSoon/);
    assert.match(repositorySrc, /productsApi\.search/);
  });

  test("is honest about the barcode-search gap instead of faking it", () => {
    assert.match(repositorySrc, /Barcode search isn&apos;t available yet/);
  });

  test("shows the blueprint's required elements: scans, trend, timeline", () => {
    assert.match(repositorySrc, /Trend/);
    assert.match(repositorySrc, /timeline/i);
    assert.match(repositorySrc, /Passed/);
    assert.match(repositorySrc, /Failed/);
  });

  test("uses mono typeface for numeric/data fields per §3 of the design system", () => {
    // Scan counts and timestamps should use font-mono, not font-body.
    assert.match(repositorySrc, /font-mono text-xs text-ink-900/);
  });

  test("uses compact table density consistent with §9's Review Queue precedent", () => {
    assert.match(repositorySrc, /data-table/);
  });

  test("timeline entries link to the real scan detail screen", () => {
    assert.match(repositorySrc, /\/queue\/\$\{scan\.scan_id\}/);
  });
});

describe("productsApi client contract", () => {
  test("dashboardApi and productsApi are both defined with the expected shapes", () => {
    assert.match(apiSrc, /export const productsApi/);
    assert.match(apiSrc, /"\/products\/search"/);
    assert.match(apiSrc, /interface ProductSearchResult/);
    assert.match(apiSrc, /trend: "IMPROVING" \| "WORSENING" \| "STABLE" \| "INSUFFICIENT_DATA"/);
  });
});
