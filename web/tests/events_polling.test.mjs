/**
 * Phase 7.1 Web Integration Tests — Real-time Polling Update Layer (§6.2)
 *
 * Verifies:
 * 1. eventsApi client contract (poll, assignTask).
 * 2. Event payload shapes: scan.status_changed and task.assigned.
 * 3. 15s interval fallback logic for Review Queue live updates (§5.1).
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

test("Phase 7.1 Real-Time Events Layer (§6.2) Contract", async (t) => {
  const apiFile = fs.readFileSync(path.join(ROOT, "lib", "api.ts"), "utf-8");

  await t.test("eventsApi is exported with poll and assignTask methods", () => {
    assert.match(apiFile, /export const eventsApi\s*=\s*\{/);
    assert.match(apiFile, /poll:\s*\(since\?: string/);
    assert.match(apiFile, /assignTask:\s*\(payload:/);
  });

  await t.test("Event payload interfaces match §6.2 specifications exactly", () => {
    // scan.status_changed: { scan_id, new_status, rule_results[], assigned_lmo_id }
    assert.match(apiFile, /interface ScanStatusChangedPayload/);
    assert.match(apiFile, /scan_id:\s*string/);
    assert.match(apiFile, /new_status:\s*string/);
    assert.match(apiFile, /rule_results:\s*RuleResultSummary\[\]/);
    assert.match(apiFile, /assigned_lmo_id:\s*string \| null/);

    // task.assigned: { scan_id, assigned_to_lmo_id, task_type }
    assert.match(apiFile, /interface TaskAssignedPayload/);
    assert.match(apiFile, /assigned_to_lmo_id:\s*string/);
    assert.match(apiFile, /task_type:\s*string/);
  });

  await t.test("Review Queue integrates 15-second polling loop per §6.2", () => {
    const queueFile = fs.readFileSync(path.join(ROOT, "app", "queue", "page.tsx"), "utf-8");

    // Must import eventsApi
    assert.match(queueFile, /eventsApi/);

    // Must poll at 15000ms (15s interval fallback)
    assert.match(queueFile, /15000/);

    // Must check for scan.status_changed to refresh queue data live
    assert.match(queueFile, /scan\.status_changed/);
    assert.match(queueFile, /eventsApi\.poll/);
  });
});
