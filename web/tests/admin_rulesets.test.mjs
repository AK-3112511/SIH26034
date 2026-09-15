import { test, describe } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");

const pageSrc = fs.readFileSync(
  path.join(webRoot, "app", "admin", "rulesets", "page.tsx"),
  "utf8"
);
const apiSrc = fs.readFileSync(path.join(webRoot, "lib", "api.ts"), "utf8");

describe("Admin: Ruleset Config — §3 Screen 8 (Phase 6.3)", () => {
  test("is the real screen, not the Phase 6 ComingSoon placeholder", () => {
    assert.doesNotMatch(pageSrc, /ComingSoon/);
    assert.match(pageSrc, /adminRulesetsApi/);
  });

  test("route stays admin-only, per the pre-existing guard convention", () => {
    assert.match(pageSrc, /user\.role !== "admin"/);
    assert.match(pageSrc, /Admin access required/);
  });

  test("has an effective-date field", () => {
    assert.match(pageSrc, /Effective Date/);
    assert.match(pageSrc, /type="date"/);
  });

  test('"Save as new version" is the only write action — no edit/overwrite affordance', () => {
    assert.match(pageSrc, /Save as New Version/);
    assert.doesNotMatch(pageSrc, />\s*Save Changes\s*</);
    assert.doesNotMatch(pageSrc, /Edit Version/i);
  });

  test("flags placeholder status clearly in the UI copy rather than treating it as real", () => {
    assert.match(pageSrc, /Placeholder figures in effect/);
    assert.match(pageSrc, /not verified statutory figures/);
  });

  test("warns explicitly when marking a version as non-placeholder", () => {
    assert.match(pageSrc, /asserts[\s\S]{0,80}verified, authoritative Schedule II figures/);
  });

  test("activation is a separate, explicit action from creation", () => {
    assert.match(pageSrc, /handleActivate/);
    assert.match(pageSrc, /Activate immediately/);
  });
});

describe("adminRulesetsApi client contract", () => {
  test("list/create/activate are all defined against /admin/rulesets", () => {
    assert.match(apiSrc, /export const adminRulesetsApi/);
    assert.match(apiSrc, /"\/admin\/rulesets"/);
    assert.match(apiSrc, /\/admin\/rulesets\/\$\{encodeURIComponent\(version\)\}\/activate/);
  });
});
