import { test, describe } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");

const pageSrc = fs.readFileSync(
  path.join(webRoot, "app", "admin", "users", "page.tsx"),
  "utf8"
);
const shellSrc = fs.readFileSync(
  path.join(webRoot, "app", "components", "AppShell.tsx"),
  "utf8"
);
const apiSrc = fs.readFileSync(path.join(webRoot, "lib", "api.ts"), "utf8");

describe("Admin: User Management — §3 Screen 9 (Phase 6.4)", () => {
  test("screen exists and calls adminUsersApi", () => {
    assert.match(pageSrc, /adminUsersApi/);
  });

  test("route stays admin-only, per the pre-existing guard convention", () => {
    assert.match(pageSrc, /user\.role !== "admin"/);
    assert.match(pageSrc, /Admin access required/);
  });

  test("can assign all three roles per §12", () => {
    assert.match(pageSrc, /field_lmo/);
    assert.match(pageSrc, /senior_lmo/);
    assert.match(pageSrc, /"admin"/);
  });

  test("can assign district/zone", () => {
    assert.match(pageSrc, /District \/ [Zz]one/);
  });

  test("does not render or expose password/hashed_password for existing users", () => {
    assert.doesNotMatch(pageSrc, /user\.password/);
    assert.doesNotMatch(pageSrc, /user\.hashed_password/);
  });
});

describe("AppShell nav — Rulesets and Users are distinct admin-only destinations", () => {
  test("both /admin/rulesets and /admin/users are admin-gated nav items", () => {
    assert.match(shellSrc, /href:\s*"\/admin\/rulesets",\s*roles:\s*\["admin"\]/);
    assert.match(shellSrc, /href:\s*"\/admin\/users",\s*roles:\s*\["admin"\]/);
  });
});

describe("adminUsersApi client contract", () => {
  test("list/create/update are defined against /admin/users", () => {
    assert.match(apiSrc, /export const adminUsersApi/);
    assert.match(apiSrc, /"\/admin\/users"/);
    assert.match(apiSrc, /api\.patch<UserResponse>\(`\/admin\/users\/\$\{userId\}`/);
  });
});
