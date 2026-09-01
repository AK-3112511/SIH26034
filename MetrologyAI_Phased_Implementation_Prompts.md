# MetrologyAI — Phased Implementation Prompts (for Antigravity)
**Source docs:** MetrologyAI_Elevated_Blueprint.md, MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md, MetrologyAI_Design_System.md
**Sequencing logic:** Backend-first, dependency-ordered — not one phase per doc. Each phase only starts once what it depends on already exists, so Antigravity is never asked to invent fake data to fill a screen that has nothing real behind it yet.

**Standing instruction — append this to the end of every prompt you send, don't skip it even when it feels repetitive:**
> After completing this task, create `/audit/progress.md` if it doesn't exist, or append to it if it does. Log: date, what was built in this step, files created/modified, any deviation from the attached blueprint docs (and why), and what remains open or blocked for the next phase. Keep entries dated and in order — do not overwrite previous entries.

---

## Table of Contents
0. [Phase 0 — Foundation & Scaffolding](#phase-0--foundation--scaffolding)
1. [Phase 1 — Backend Core: Data + Auth (No AI Yet)](#phase-1--backend-core-data--auth-no-ai-yet)
2. [Phase 2 — Mobile App: Capture & Offline Queue](#phase-2--mobile-app-capture--offline-queue)
3. [Phase 3 — Backend AI Pipeline: Extraction, Calibration, Rule Engine](#phase-3--backend-ai-pipeline-extraction-calibration-rule-engine)
4. [Phase 4 — Web Dashboard Core: Queue + Scan Detail](#phase-4--web-dashboard-core-queue--scan-detail)
5. [Phase 5 — Trust & Legal Output: Hash Vault + Challan PDF](#phase-5--trust--legal-output-hash-vault--challan-pdf)
6. [Phase 6 — GIS Heatmap, Repository & Admin](#phase-6--gis-heatmap-repository--admin)
7. [Phase 7 — Real-Time Integration Layer](#phase-7--real-time-integration-layer)
8. [Phase 8 — Polish, Accessibility & Deployment](#phase-8--polish-accessibility--deployment)

---

## Phase 0 — Foundation & Scaffolding

Nothing functional yet — this phase just makes every later prompt land in the right place instead of Antigravity guessing a repo structure.

### 0.1 Repo & project scaffolding
**Attach:** all 3 MD files
```
Set up a monorepo (or three linked repos if you think that's cleaner — tell me which and why) for a project called MetrologyAI, based on the attached blueprint, UX/integration, and design-system docs. Create:
- /backend — Python FastAPI project skeleton, poetry or venv-based, empty routers folder structured by domain (scans, auth, challans, admin)
- /mobile — Flutter project skeleton (Android target first), standard feature-folder structure
- /web — Next.js project skeleton (App Router), TypeScript
- /audit — empty folder, will hold progress.md
Do not implement any business logic yet. Just get all three apps running (hello-world level) and confirm they boot. Create /audit/progress.md now with a first entry describing the scaffold.
```

### 0.2 Design tokens as code
**Attach:** MetrologyAI_Design_System.md, plus the /web and /mobile skeletons from 0.1
```
Using the attached design system doc, implement the color, typography, and spacing tokens as actual code — not just documentation. For /web: a Tailwind config (or CSS variables if you're not using Tailwind) with every token from §2–4 named exactly as in the doc (ink-900, paper-100, brass-500, verdict-pass, etc.). For /mobile: a Flutter ThemeData / design_tokens.dart file with the same values. Do not build any screens yet — this is purely the token layer both apps will import from. Confirm both apps still boot after wiring the theme in.
```

---

## Phase 1 — Backend Core: Data + Auth (No AI Yet)

Pure plumbing. No YOLOv8/PaddleOCR/Florence-2 here — the goal is a working, authenticated API with real tables, so every later phase has something true to write to and read from.

### 1.1 Database schema
**Attach:** MetrologyAI_Elevated_Blueprint.md (§11 has the schema)
```
Using §11 (Data Schema Design) of the attached blueprint, set up PostgreSQL 15 with the PostGIS extension in /backend, and write migrations (Alembic) for the scans, extracted_fields, rule_results, and challans tables exactly as specified. Include the location GEOMETRY(POINT,4326) column and a trigger to derive it from lat/lng on insert. Do not add any tables not in §11 without telling me first.
```

### 1.2 Auth service + RBAC
**Attach:** MetrologyAI_Elevated_Blueprint.md (§12), MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§6.1)
```
Implement a JWT-based auth service in /backend per §12 of the blueprint and §6.1 of the integration doc. Token payload must include lmo_id, role, and district. Implement the three roles exactly as named: field_lmo, senior_lmo, admin. Add a users table and a single /auth/login endpoint usable by both a future mobile client and web client. Add role-based route guards (a decorator/dependency) that later endpoints will use — but don't build any protected endpoints yet beyond a /auth/me test route to confirm the token round-trips correctly.
```

### 1.3 Scan ingestion endpoint (no AI processing)
**Attach:** MetrologyAI_Elevated_Blueprint.md (§10 API summary, §3.1 offline queue), MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§5.1)
```
Implement POST /api/v1/scans/ingest per §10 of the blueprint: accepts multipart image + lat/lng/captured_at_utc/device_id/reference_object_type, writes a row to `scans` with status QUEUED, stores the image in object storage (local disk is fine for now, but structure the code so swapping in S3-compatible storage later is a config change, not a rewrite). Do NOT call any AI model — just prove ingestion, storage, and a status field work end to end. Add GET /api/v1/scans/{scan_id} to read it back.
```

### 1.4 Audit log table
**Attach:** MetrologyAI_Elevated_Blueprint.md (§12, audit log bullet)
```
Add an append-only audit_log table (actor_id, action, target_type, target_id, timestamp, detail JSONB) per §12 of the blueprint. Wire it so every status-changing action from here on writes to it automatically (a shared helper, not manual calls scattered everywhere) — for now, just prove it by logging the login event and the scan ingestion event.
```

---

## Phase 2 — Mobile App: Capture & Offline Queue

The Flutter app, built against the real (if AI-less) backend from Phase 1. This is where the design tokens from 0.2 actually get used.

### 2.1 Login & Home screens
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§2, screens 1–2), design tokens from Phase 0.2
```
Build the Login and Home/Today's Scans screens for the Flutter app per §2 (screens 1–2) of the attached UX doc, using the design tokens set up in Phase 0.2 — do not introduce new colors or type sizes outside those tokens. Home screen lists today's captures with sync status chips (§5.4 of the design system: flat pill shape, distinct from the Seal Badge which doesn't exist yet). Wire Login to the real /auth/login endpoint from Phase 1.2. Home screen data can be mocked/empty for now since no captures exist yet.
```

### 2.2 Capture screen (AR guide)
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§2 screen 3, §4.1 layout sketch), MetrologyAI_Design_System.md (§8 mobile considerations)
```
Build the Capture screen per §2 (screen 3) and the ASCII layout sketch in §4.1 of the UX doc. Live camera preview using the device camera, a guide overlay box for the reference card, shutter button disabled until a card-like rectangle is detected in frame (basic OpenCV/ML Kit rectangle detection is fine for now — full calibration math comes in Phase 3, this screen only needs to gate the shutter). Apply the 48px minimum touch target and bottom-anchored primary action from §8 of the design system. Product-type toggle (Box/Bottle/Manual) per the layout sketch.
```

### 2.3 Offline queue (SQLite) + background sync
**Attach:** MetrologyAI_Elevated_Blueprint.md (§3.1 — exact schema and sync pseudo-code)
```
Implement the local SQLite `captures` table and sync worker exactly as specified in §3.1 of the blueprint (schema and pseudo-code both given — follow them precisely, including status values PENDING_UPLOAD/UPLOADING/SYNCED/FAILED and the retry_count/backoff behavior). Wire it to the /api/v1/scans/ingest endpoint from Phase 1.3. Confirm behavior specifically in airplane mode: capture should still succeed locally, then sync automatically once connectivity returns.
```

### 2.4 Sync Queue & Notifications screens
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§2, screens 6–7)
```
Build the Sync Queue screen (list of PENDING_UPLOAD/FAILED captures with manual retry) and a basic Notifications screen (static list UI for now — real push events don't exist until Phase 7) per §2 screens 6–7 of the UX doc. Use the sync status chip component from Phase 2.1, don't invent a new visual style for this screen.
```

---

## Phase 3 — Backend AI Pipeline: Extraction, Calibration, Rule Engine

This is the deterministic "brain" — build and test it against static test images before wiring it to the live ingestion queue.

### 3.1 Preprocessing (dewarp, glare removal)
**Attach:** MetrologyAI_Elevated_Blueprint.md (§4.3 steps 1–2)
```
Implement the OpenCV preprocessing stage exactly per §4.3 (steps 1–2) of the blueprint: YOLOv8 pass to detect package_face_bbox and reference_card_bbox, perspective correction on card corners, cylindrical dewarp when curvature heuristics suggest a bottle/can, CLAHE contrast pass. If reference_card_bbox confidence < 0.85, mark the scan CALIBRATION_FAILED and stop the pipeline here per the spec — do not attempt to estimate measurements without a detected card.
```

### 3.2 OCR + semantic mapping
**Attach:** MetrologyAI_Elevated_Blueprint.md (§4.1, §4.3 steps 4–5)
```
Integrate PaddleOCR (English + Hindi) over the post-dewarp package_face_bbox, then Florence-2 for zero-shot semantic mapping of the OCR strings into the schema fields listed in §4.3 step 5 (net_quantity, mrp, mfg_date, manufacturer_name, manufacturer_address, pincode, consumer_care, unit). Store OCR confidence and semantic confidence separately per field, exactly as specified — do not merge them into one blended score.
```

### 3.3 Spatial calibration math
**Attach:** MetrologyAI_Elevated_Blueprint.md (§4.2, §4.3 steps 3/6/7)
```
Implement the mm-per-pixel ratio calculation, font-height-to-mm conversion, and PDP area calculation exactly per §4.2 and §4.3 (steps 3, 6, 7) of the blueprint, including the cross-check between long-edge and short-edge derived ratios (§4.3 step 3) — if they disagree by more than 5%, flag LOW_CONFIDENCE_CALIBRATION rather than silently picking one.
```

### 3.4 Rule engine
**Attach:** MetrologyAI_Elevated_Blueprint.md (§5.1 — full pseudo-code given)
```
Implement the rule engine per §5.1 of the blueprint: each rule (6.1.a, 6.1.c, 6.1.e, 6.1.g, schedule_ii) as an independent pure function returning PASS/FAIL/UNVERIFIED, persisted individually to rule_results — never collapse to a single boolean. Build the Schedule II check against a config-driven ruleset table (versioned), NOT hardcoded values — I have not given you the verified current Schedule II area/font bands yet, so use clearly-labeled placeholder values and flag in progress.md that these must be replaced with verified figures before any real legal use.
```

### 3.5 Confidence gating
**Attach:** MetrologyAI_Elevated_Blueprint.md (§6.1 — pseudo-code given)
```
Implement per-field confidence gating exactly per §6.1 of the blueprint (ocr_confidence < 0.95 or semantic_confidence < 0.90 → UNVERIFIED), and the scan-level status rollup (FAILED / PENDING_REVIEW / PASSED) using the logic given. Wire the full pipeline (3.1→3.5) to actually run when a scan status is QUEUED, so scans ingested in Phase 1.3 now get real results.
```

---

## Phase 4 — Web Dashboard Core: Queue + Scan Detail

Now there's real data to show. Build the Next.js dashboard against it.

### 4.1 Auth + shell layout
**Attach:** design tokens (Phase 0.2), MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 1)
```
Build the web dashboard's login screen and main app shell (nav per §4.2's header layout sketch) using the design tokens from Phase 0.2. Wire login to the same /auth/login endpoint from Phase 1.2 — confirm a senior_lmo/admin token works and a field_lmo-only token is rejected for dashboard access.
```

### 4.2 Overview screen
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 2), MetrologyAI_Elevated_Blueprint.md (§10 heatmap endpoint — stub only for now)
```
Build the Overview screen per §3 screen 2: today's counts (scanned/passed/failed/pending review) pulled from real scan data now that Phase 3 populates it. Leave the heatmap as a placeholder map component for now — the real GIS aggregation query comes in Phase 6.
```

### 4.3 Review Queue
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 3, §4.2 layout sketch)
```
Build the Review Queue screen per §3 screen 3 and the layout sketch in §4.2, reading real PENDING_REVIEW scans from the backend. Sortable/filterable by district, confidence gap, age. One-at-a-time selection only — no bulk actions, per the doc's explicit reasoning.
```

### 4.4 Scan Detail
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 4, §4.3 layout sketch), MetrologyAI_Design_System.md (§5.1 Seal Badge, §5.5 data table)
```
Build the Scan Detail screen per §3 screen 4 and §4.3's layout sketch: full-res image with bounding boxes drawn from the stored bbox coordinates (not a burned-in image — render on top per the blueprint's chain-of-custody note in §2.1), per-rule pass/fail table using real rule_results, editable field overrides requiring a mandatory reviewer note, and implement the Seal Badge component from §5.1 of the design system for the verdict display. "Generate Challan" button should be present but disabled/non-functional until Phase 5.
```

### 4.5 E-commerce ingestion screen
**Attach:** MetrologyAI_Elevated_Blueprint.md (§3.2), MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 5)
```
Build the E-Commerce Ingestion screen per §3.2 of the blueprint and §3 screen 5 of the UX doc: drag-and-drop screenshot upload, manual dimension input form, platform tag field. Submit into the same /api/v1/scans/ingest-derived pipeline from Phase 3 — add the manual-dimension calibration path described in §3.2 as an alternate input to the ratio calculation from Phase 3.3, not a separate pipeline.
```

---

## Phase 5 — Trust & Legal Output: Hash Vault + Challan PDF

### 5.1 Section 65B hash vault
**Attach:** MetrologyAI_Elevated_Blueprint.md (§6.2 — canonical payload formula given)
```
Implement the Section 65B evidence hash exactly per §6.2 of the blueprint — the canonical concatenation formula is given precisely (image_bytes + lat + lng + timestamp + device_id, SHA-256). Compute and store this at ingestion time (retrofit Phase 1.3's ingest endpoint), and expose a way to recompute and compare it on demand to prove the record hasn't been altered.
```

### 5.2 Challan PDF generator
**Attach:** MetrologyAI_Elevated_Blueprint.md (§7.2, §10 endpoint), MetrologyAI_Design_System.md (§9 print stylesheet note, §5.1 vector Seal Badge)
```
Implement POST /api/v1/challans/generate per §7.2 and §10 of the blueprint using ReportLab: government header, the original untouched image plus a separately-rendered annotated crop (per the chain-of-custody separation described in §7.2), the specific rule broken, GPS, and the Section 65B hash. Compute a second, PDF-level hash of the generated bytes per §2.1's note. Render the Seal Badge as vector per §5.1/§9 of the design system, not a raster image. Block generation with an explicit error if any required field (LMO ID, rule text, GPS) is null — per §2.1's failure-path note, never emit a partially-filled document.
```

### 5.3 Challan Archive screen
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 7)
```
Build the Challan Archive screen per §3 screen 7: searchable list of generated challans, re-download PDF, display the pdf_hash for verification. Wire the "Generate Challan" button from Phase 4.4 to actually call this now.
```

---

## Phase 6 — GIS Heatmap, Repository & Admin

### 6.1 PostGIS heatmap
**Attach:** MetrologyAI_Elevated_Blueprint.md (§7.1 implementation note, §10 endpoint), MetrologyAI_Design_System.md (§9 map styling)
```
Implement GET /api/v1/dashboard/heatmap using a PostGIS ST_ClusterKMeans (or ST_SnapToGrid) aggregation query per §7.1 of the blueprint — do not send raw unclustered points to the client. Style the map per §9 of the design system: muted/low-saturation basemap so verdict-colored clusters are the only saturated color. Replace the Phase 4.2 placeholder with this real component.
```

### 6.2 Digital Repository / Product Search
**Attach:** MetrologyAI_Elevated_Blueprint.md (§10 endpoint), MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 6)
```
Build GET /api/v1/products/search and the Product Search screen per §3 screen 6: search by brand/barcode, timeline of past scans nationally, trend indicator. Use the mono typeface for all numeric/data fields per §3 of the design system.
```

### 6.3 Admin: Ruleset config
**Attach:** MetrologyAI_Elevated_Blueprint.md (§5.1 ruleset versioning note), MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 8)
```
Build the Admin Ruleset Config screen per §3 screen 8: versioned editor for the Schedule II config table from Phase 3.4, "Save as new version" that never overwrites a version a past challan referenced, effective-date field. This is the screen where the real Schedule II numbers (still placeholders from Phase 3.4) will eventually get entered — flag that clearly in the UI copy, don't silently treat placeholders as real.
```

### 6.4 Admin: User management + RBAC UI
**Attach:** MetrologyAI_Elevated_Blueprint.md (§12), MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 9)
```
Build the User Management screen per §3 screen 9 and §12 of the blueprint: assign field_lmo/senior_lmo/admin roles, assign district/zone. Enforce that this screen is itself admin-only via the RBAC guard from Phase 1.2.
```

### 6.5 Audit Log screen
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§3 screen 10)
```
Build the read-only Audit Log screen per §3 screen 10, surfacing the audit_log table from Phase 1.4. No edit/delete actions — this screen is view-only by design.
```

---

## Phase 7 — Real-Time Integration Layer

Deliberately last, per the UX doc's own build-order recommendation (§7) — everything up to here should already work via manual refresh/polling before adding push infrastructure.

### 7.1 Real-time channel (or polling fallback — pick one and say why)
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§6.2 — event payloads given)
```
Implement the real-time update layer per §6.2 of the UX doc. Given this is a hackathon timeline, default to the polling fallback explicitly mentioned in §6.2 (15–30s interval) unless you judge WebSocket/SSE infra is cheap enough in our stack to justify — tell me which you chose and why before building extensively on top of it. Implement the two event types exactly as specified: scan.status_changed and task.assigned.
```

### 7.2 Mobile push notifications
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§5.2, §2 screen 7)
```
Wire the scan.status_changed event to real push notifications on the mobile Notifications screen (built as static UI in Phase 2.4) per §5.2 of the UX doc — a field LMO gets notified when their own scan's verdict is confirmed/overridden by a senior LMO.
```

### 7.3 E-commerce → field task assignment loop
**Attach:** MetrologyAI_Mobile_Web_UX_Integration_Blueprint.md (§5.3)
```
Implement the assignment flow per §5.3: when a senior LMO's e-commerce ingestion (Phase 4.5) fails compliance, add an "Assign for field follow-up" action on the Scan Detail screen (Phase 4.4) that assigns it to a field_lmo, triggering the task.assigned event so it appears on that LMO's mobile Home screen as an assigned item (not a self-captured scan) — this needs a small UI distinction on mobile between "my captures" and "assigned to me."
```

---

## Phase 8 — Polish, Accessibility & Deployment

### 8.1 Accessibility pass
**Attach:** MetrologyAI_Design_System.md (§10)
```
Audit both /web and /mobile against §10 of the design system: WCAG 2.1 AA contrast on all text and verdict color pairs, colorblind-safe differentiation on Seal Badges (shape/icon, not color alone), visible keyboard focus states on every interactive web element. Fix what fails.
```

### 8.2 Motion pass
**Attach:** MetrologyAI_Design_System.md (§7)
```
Implement the motion spec exactly per §7 of the design system — the red→green capture guide transition, the one-time Seal Badge stamp-impact animation, and reduced-motion OS setting support. Do not add any motion beyond what's specified in §7.
```

### 8.3 Bilingual layout
**Attach:** MetrologyAI_Design_System.md (§10, bilingual note)
```
Verify all fixed-width labels/buttons across both apps flex correctly for Hindi text per §10's note that Hindi runs longer than English for equivalent content. Fix any layout that breaks or truncates.
```

### 8.4 Deployment
**Attach:** MetrologyAI_Elevated_Blueprint.md (§13)
```
Containerize per §13 of the blueprint: separate Docker containers for FastAPI backend, Celery workers, and the Next.js dashboard. Use Docker Compose for now (§13 explicitly notes Compose as the honest answer for a hackathon-scale build, Kubernetes as the later production answer) — don't build K8s manifests unless I ask for them specifically.
```
