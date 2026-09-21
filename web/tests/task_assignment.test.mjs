/**
 * Phase 7.3: Task Assignment Contract & Scan Detail Action Tests (§5.3)
 *
 * Verifies:
 * 1. usersApi.getFieldOfficers and scansApi.assignedToMe client contracts
 * 2. Scan Detail screen strictly scopes "Assign for field follow-up" to source === "ecommerce" && status === "FAILED"
 * 3. Assignment dialog and action buttons conform to §5.3 specification
 */
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const webRoot = path.resolve(__dirname, "..");

describe("Phase 7.3: Task Assignment Loop (§5.3)", () => {
  const apiFile = fs.readFileSync(path.join(webRoot, "lib", "api.ts"), "utf-8");
  const scanDetailPage = fs.readFileSync(
    path.join(webRoot, "app", "queue", "[id]", "page.tsx"),
    "utf-8"
  );

  test("usersApi is exported with getFieldOfficers method", () => {
    assert.match(apiFile, /export\s+const\s+usersApi\s*=\s*\{/);
    assert.match(apiFile, /getFieldOfficers:\s*\(district\?:/);
    assert.match(apiFile, /\/users\/field-officers/);
  });

  test("scansApi is exported with assignedToMe method", () => {
    assert.match(apiFile, /assignedToMe:\s*\(\)\s*=>/);
    assert.match(apiFile, /\/scans\/assigned-to-me/);
  });

  test("FieldOfficer and AssignedScan types are defined", () => {
    assert.match(apiFile, /export\s+interface\s+FieldOfficer\s*\{/);
    assert.match(apiFile, /export\s+interface\s+AssignedScan\s*\{/);
  });

  test("Scan Detail strictly scopes assignment to failed e-commerce scans per §5.3", () => {
    // Condition must explicitly require ecommerce source AND FAILED status
    assert.match(
      scanDetailPage,
      /scan\?\.source\s*===\s*["']ecommerce["']\s*&&\s*scan\?\.status\s*===\s*["']FAILED["']/
    );
  });

  test("Scan Detail renders field follow-up action and modal", () => {
    assert.match(scanDetailPage, /data-testid=["']field-followup-container["']/);
    assert.match(scanDetailPage, /data-testid=["']assign-field-followup-button["']/);
    assert.match(scanDetailPage, /data-testid=["']assign-officer-modal["']/);
    assert.match(scanDetailPage, /data-testid=["']field-officer-select["']/);
    assert.match(scanDetailPage, /data-testid=["']confirm-assignment-button["']/);
  });

  test("Scan Detail dispatches task.assigned event via eventsApi.assignTask", () => {
    assert.match(scanDetailPage, /eventsApi\.assignTask\(\{/);
    assert.match(scanDetailPage, /task_type:\s*["']field_followup["']/);
  });
});
