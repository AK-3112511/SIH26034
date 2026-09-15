import { test, describe } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");

const pageSrc = fs.readFileSync(
  path.join(webRoot, "app", "admin", "audit-log", "page.tsx"),
  "utf8"
);
const shellSrc = fs.readFileSync(
  path.join(webRoot, "app", "components", "AppShell.tsx"),
  "utf8"
);
const apiSrc = fs.readFileSync(path.join(webRoot, "lib", "api.ts"), "utf8");

describe("Audit Log — §3 Screen 10 (Phase 6.5)", () => {
  test("screen exists and calls the real API", () => {
    assert.match(pageSrc, /adminAuditLogApi/);
  });

  test("route stays admin-only", () => {
    assert.match(pageSrc, /user\.role !== "admin"/);
    assert.match(pageSrc, /Admin access required/);
  });

  test("is explicitly view-only — no edit/delete/mutation affordances", () => {
    assert.doesNotMatch(pageSrc, /onClick=\{.*[Dd]elete/);
    assert.doesNotMatch(pageSrc, /\.(post|patch|put|delete)\(/);
    assert.match(pageSrc, /No edit or delete actions/);
  });

  test("surfaces actor, action, target, and timestamp per §12", () => {
    assert.match(pageSrc, /actor_username/);
    assert.match(pageSrc, /entry\.action/);
    assert.match(pageSrc, /target_type/);
    assert.match(pageSrc, /formatTimestamp/);
  });
});

describe("AppShell nav includes Audit Log as a third admin-only destination", () => {
  test("href and admin-only role gate are present", () => {
    assert.match(shellSrc, /href:\s*"\/admin\/audit-log",\s*roles:\s*\["admin"\]/);
  });
});

describe("adminAuditLogApi client contract", () => {
  test("only a list/read method is defined — no write methods", () => {
    assert.match(apiSrc, /export const adminAuditLogApi/);
    assert.match(apiSrc, /"\/admin\/audit-log"/);
    assert.doesNotMatch(apiSrc, /adminAuditLogApi = \{[\s\S]*?(post|patch|put|delete):/);
  });
});
