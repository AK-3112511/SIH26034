# MetrologyAI (SIH26034) — Assessment & Phased Execution Plan

## Context

MetrologyAI is a Legal Metrology (Packaged Commodities) Rules 2011 compliance system: a Flutter field app captures a package photo beside an ISO/IEC 7810 reference card (offline-first, SQLite queue), a FastAPI backend runs a CV/OCR pipeline → spatial calibration (mm/px from the card) → deterministic PCR 2011 rule engine (6(1)(a),(c),(e),(g), Schedule II) with per-field confidence gating → Section 65B hash → Section 39 challan PDF; a Next.js dashboard gives senior LMOs a review queue, scan detail with bbox overlays, e-commerce ingestion, heatmap, repository, challan archive, and admin (rulesets/users/audit).

Phases 0–7 of the original plan are "done" per `audit/progress.md`, but the product does not actually work end-to-end on a real deployment. Owner decisions taken during discovery:

- **Demo env:** this laptop, install PostgreSQL+PostGIS locally (no Docker available).
- **AI:** CPU-only. Make real OCR work (PaddleOCR CPU); rule-based semantic mapper primary; Florence-2 optional.
- **Schedule II:** seed real statutory bands (≤100 cm² → 1 mm; ≤500 → 2 mm; ≤2500 → 4 mm; >2500 → 6 mm; ×2 for blown/embossed) as the active, non-placeholder ruleset.
- **Mobile offline auth:** remove the password-less bypass; only cached, previously-authenticated sessions work offline.
- **Brand/product name:** add as an extracted field + optional manual entry; repository searches by brand.

---

## A. Current state — what's actually true (verified)

### Blocking / P0
| # | Finding | Where |
|---|---|---|
| 1 | **OCR is fake.** `paddleocr` not installed/listed; `auto` falls to `DeterministicOCREngine` which returns canned "BRITANNIA INDUSTRIES LIMITED / Net Quantity: 500 g / MRP Rs.120…" for **every** image. All real captures produce the same result. | `backend/app/services/vision/ocr/deterministic_ocr.py:40-52`, `extraction_pipeline.py:139-146` |
| 2 | **Backend cannot run on real Postgres.** `scans.source/status` and `rule_results.status` ENUMs lack `values_callable` → inserts fail; **no migration for `event_logs`** (Phase 7) → events silently swallowed / 500. | `models/scan.py:29-50`, `models/rule_result.py:31-34`, `alembic/versions/*` |
| 3 | **`.venv` is broken vs requirements**: `reportlab`, `Pillow` missing → `import app.main` fails; `requirements.txt` is UTF-16 (pip can't read it on Linux); `pyproject.toml` disagrees. | `backend/requirements.txt`, `pyproject.toml` |
| 4 | **Unauthenticated write endpoints**: `POST /scans/ingest`, `/scans/{id}/process`, `/scans/process-queued`. Mobile sends no bearer. Scans have no officer identity. | `routers/scans.py:233-245`, `mobile/.../sync_worker.dart:113-155` |
| 5 | **Mobile auth bypass**: `loginOffline()` fabricates a `field_lmo` session with no password; offered after *any* login error. | `auth_service.dart:179-204`, `login_screen.dart:279,441-462` |
| 6 | **GPS hardcoded** (11.0168, 76.9558) and `device_id` random per capture → Section 65B hash is bound to fabricated metadata. No location plugin/permission. | `capture_screen.dart:231-232`, `sync_worker.dart:126` |
| 7 | **Challan PDF crashes on pipeline scans**: bbox drawing expects list `[x,y,w,h]`; pipeline stores dict. E-commerce `verify-hash` always fails (two different timestamps). | `routers/challans.py:177-178`, `routers/scans.py:364,377` |
| 8 | **Phase 7 real-time layer is not wired on mobile**: `startPolling()` never called, `loadStoredToken()` never called (no session restore → background poll unauthenticated), `LocalNotificationService.initialize()` never called. Field officers can never see a verdict. | `event_polling_service.dart:69`, `main.dart`, `background_sync_dispatcher.dart` |
| 9 | **Web assign-task modal is visually broken**: uses Tailwind tokens (`bg-surface`, `border-border`, `text-text-*`) that don't exist → transparent modal; fabricated fallback officer "Ramesh Kumar" shown when API fails; "instructions" textarea never sent. | `web/app/queue/[id]/page.tsx:126-141, 773-902` |
| 10 | **Bbox overlay geometry wrong**: percentages relative to letterboxed container, not the rendered image; assumes normalised coords, pipeline emits pixels. | `web/app/queue/[id]/page.tsx:275-292, 373-437` |
| 11 | Evidence images + challan PDFs served **publicly** from `/static/uploads`. Hardcoded `JWT_SECRET_KEY` default. No upload size/type validation. | `main.py:35-36`, `core/config.py:12` |

### P1 — incomplete / incorrect
- Card detector gate requires conf ≥ 0.85 from geometric detector; real photos frequently `CALIBRATION_FAILED` before OCR; `reference_object_type` from ingest is ignored by the pipeline; `Scan.mm_per_px` never persisted by the pipeline.
- Mobile stores *product type* in `reference_object_type`; no "Review before upload" screen; no mobile Scan Detail (verdict) screen; no Profile/Settings; base URL not persisted; cleartext HTTP blocked on API 28+ (no network-security-config); "Failed" upload chip uses verdict-fail red (semantic collision).
- Web: no mobile nav (<768px hidden, no hamburger); queue polling blanks table and resets on every keystroke; hardcoded 4-district filter; no JWT expiry handling; `GET /scans/` loads all rows into Python (N+1 user lookups); district event routing mismatch (`"Chennai, TN"` vs `"Madurai"`); no confirmations on irreversible legal actions; dev jargon ("§5.3", "uvicorn app.main:app", "Event task.assigned dispatched") in user-facing copy; fonts never loaded via `next/font`.
- Backend: duplicate challans allowed; `review_scan` allows `CALIBRATION_FAILED` but blocks `LOW_CONFIDENCE_CALIBRATION`; unbounded pagination on challans/users; `ingest-derived` doesn't auto-process; `.env.example` uses a key the settings class ignores.
- Product name shown in queue is actually the net-quantity string.

### P2 — quality
- Web tests are regex-over-source / reimplementations (no rendering); backend has 13 copies of a SQLite shim (no `conftest.py`); mock/dev toggles ("Preview", "Simulate Reference Card", 5 seeded fake notifications) shipped in production UI; `home_screen.dart` 1004 lines; `queue/[id]/page.tsx` 927 lines with 22 `useState`; duplicated helpers (timeAgo ×3, pagination ×4, admin guard ×3, error banner ×9); dead code (`ComingSoon`, `app_colors.dart`, react-query dep, unused imports).

---

## B. Target architecture (what changes, what stays)

**Keep:** FastAPI + SQLAlchemy + Alembic + PostGIS; Next.js App Router + Tailwind tokens; Flutter + sqflite + WorkManager + opencv_dart; deterministic rule engine design; dual-engine fallback pattern; DB-backed polling for real-time (no WebSocket — right call for the timeline).

**Change:**
- Real OCR path: PaddleOCR (CPU, PP-OCRv4 en + Devanagari) as the default engine; `DeterministicOCREngine` renamed `MockOCREngine`, selectable only via explicit `OCR_ENGINE=mock` env, never by silent fallback in non-test runs (fail loudly instead).
- All ingestion authenticated; `scans.captured_by_id` FK added (who captured); static files served through an authenticated `GET /api/v1/files/{key}` (signed short-lived URLs for `<img>`), not a public mount.
- Single `conftest.py`; shared web UI primitives; mobile session restore + polling lifecycle wired in `main.dart`.
- One-command local bootstrap (`scripts/bootstrap.ps1` / `.sh`): create DB, enable PostGIS, migrate, seed users + statutory ruleset + demo scans.

---

## C. Execution phases

Each phase ends with: tests green (`pytest`, `npm test`, `flutter test`), build green (`next build`, `flutter analyze`), a manual run of the affected flow, and an `audit/progress.md` entry.

### Phase A — Make it run for real (backend foundation) — P0
1. **Dependencies & env**: rewrite `requirements.txt` as UTF-8 with pinned working set incl. `paddleocr`, `paddlepaddle` (CPU), `pillow`, `reportlab`, `boto3` optional extra; align `pyproject.toml`; fix `.env.example` (`SQLALCHEMY_DATABASE_URI`, `JWT_SECRET_KEY`, storage keys); make `Settings` refuse the default JWT secret when `ENV=production`.
2. **Postgres install + bootstrap**: document/automate local PostgreSQL 16 + PostGIS install; `scripts/bootstrap.ps1` (createdb, `CREATE EXTENSION postgis`, `alembic upgrade head`, seed).
3. **Schema fixes**: `values_callable` on all ENUM columns; new migration `0005_event_logs_and_capture_identity` — `event_logs` table, `scans.captured_by_id` (FK users), `scans.product_name`, `scans.platform`, `challans` unique(scan_id); verify `alembic upgrade head` from empty DB.
4. **Auth on ingestion**: `POST /scans/ingest` → `get_current_user` (field/senior/admin), sets `captured_by_id`; `/process` and `/process-queued` → `require_senior_lmo`; ownership scoping on `GET /scans/{id}` for `field_lmo` (own captures or assigned).
5. **Upload validation**: content-type sniff (JPEG/PNG/WebP), max size (config, default 15 MB), sanitised filename.
6. **Evidence file access**: replace public `/static/uploads` mount with `GET /api/v1/files/{key}` (auth) + `GET /api/v1/files/{key}?token=` short-lived HMAC token for `<img src>`; `image_url`/`pdf_url` become API paths; web `next.config` rewrite updated.
7. **Test infra**: single `backend/tests/conftest.py` (SQLite shim + fixtures + auth helpers); delete 13 copies; add a `@pytest.mark.postgres` optional suite that runs against the local DB when `TEST_DATABASE_URL` set.

### Phase B — Real vision pipeline (CPU) — P0
1. Install & wire `NativePaddleOCREngine` (en + hi models, `use_angle_cls`, lazy singleton, warm-up at startup via `lifespan`); make engine selection explicit (`OCR_ENGINE=paddle|mock`, default `paddle`); log engine provenance on each scan.
2. Semantic mapper: `RuleBasedSemanticMapper` primary; add `product_name` heuristic (largest-height non-numeric text line on PDP, excluding lines matched as mfr/address); Florence-2 behind `SEMANTIC_ENGINE=florence2` only.
3. Card detection robustness: relax geometric detector (aspect 1.35–1.85, contrast-normalised Canny, largest quad scoring), honour `reference_object_type` hint, expose `calibration_confidence` in scan detail; persist `Scan.mm_per_px` from pipeline.
4. `ingest-derived` auto-processes (BackgroundTasks); optional `product_name` + `platform` form fields persisted.
5. Bounded background processing: `asyncio.Semaphore(2)` around `process_scan`; status `PROCESSING` added to `ScanStatus`; failure → `PROCESSING_FAILED` with reason stored (never stuck in `QUEUED`).
6. Fix challan bbox (accept dict/list/normalised), unique challan per scan (return existing), fix e-commerce hash timestamp bug, fix `review_scan` status guard (allow `PENDING_REVIEW`, `LOW_CONFIDENCE_CALIBRATION`, `FAILED`, `PASSED` re-review by senior only; block `QUEUED/PROCESSING`).
7. Seed statutory Schedule II ruleset (`pcr_2011_schedule_ii_2011` active, `is_placeholder=False`, notice cites Rule 7(3) & Schedule II); keep the engineering placeholder as inactive history.
8. Rewrite `seed_scans.py` to run **real images** from `backend/uploads` samples through the real pipeline (so demo data is honest), plus a small deterministic fixture for tests.
9. Performance: `GET /scans/` → SQL filtering/sorting/pagination; batch district resolution; bounded `page_size` everywhere.

### Phase C — Mobile app: trust & completeness — P0/P1
1. **Auth**: remove `loginOffline` bypass; `main.dart` restores session via `loadStoredToken()` → `/auth/me` validation when online; offline = cached session only; persist base URL (`shared_preferences`); 401 → forced re-login; `network_security_config.xml` for cleartext to configured LAN host in debug.
2. **Real GPS**: add `geolocator` + permissions (fine/coarse); capture blocks with explanation if location denied (evidence requires it); store accuracy; stable `device_id` (generated once, persisted).
3. **Capture flow**: fix `reference_object_type` (card type selector: Debit/PAN/Aadhaar-size) separate from product type; add **Review Before Upload** screen (retake/confirm, optional product name); remove "Simulate Reference Card" from release builds (keep behind `kDebugMode`); aspect-correct `CameraPreview`; run detector off the UI isolate (`compute`).
4. **Sync worker**: send bearer token; refuse to upload missing/synthetic images (mark FAILED with reason); recover orphaned `UPLOADING` rows on start; exponential backoff; surface `lastSyncError` as friendly text.
5. **Verdict visibility**: persist `server_status`, `verdict_summary`, `rule_failures` on `captures`; poll `GET /scans/{id}` for synced captures until terminal; new **Scan Detail (mobile)** screen with Seal Badge, rule list, "View full report" web deep link; Home chips separate *sync* status (flat pills) from *verdict* (seal badge, 24px).
6. **Real-time**: start `EventPollingService` on Home (foreground, 20 s, pauses on background), initialise `LocalNotificationService` at boot, background dispatcher loads stored token before polling; notifications persisted in SQLite (`notifications` table) — remove 5 seeded mocks; deep links resolve to Scan Detail.
7. **Profile/Settings** screen: officer identity, district, server URL, Wi-Fi-only sync toggle (honoured by WorkManager constraints), app version, logout.
8. Cleanup: remove "Preview/Empty" toggle, "§x.y" strings, `app_colors.dart`, dead services; split `home_screen.dart` into widgets; loading/error states on Home & Sync Queue; guard `substring` crashes; app label "MetrologyAI"; bundle the three fonts.

### Phase D — Web dashboard: correctness & polish — P1
1. **Scan detail rewrite** (split into components: `EvidenceViewer`, `RuleResultsPanel`, `ExtractedFieldsTable`, `ReviewForm`, `AssignTaskDialog`): bbox overlay anchored to the rendered image via `onLoad` natural size + `ResizeObserver`, supports pixel/normalised coords; fix modal tokens; drop fabricated officer; send `instructions` (backend accepts, stored in audit + event payload); confirmation dialogs for verdict, challan, assignment; show existing challan; decision defaults from rule results; success states don't unmount the view.
2. **Queue**: debounced search, background refresh without blanking (`isRefreshing` vs `loading`), interval independent of filters, pause when tab hidden, district options from `GET /scans/districts`; subtle "N new" indicator on `scan.status_changed`.
3. **Shell**: mobile hamburger nav; JWT `exp` decode → proactive logout + `?expired=1` message; `/auth/me` revalidation on hydration; `middleware.ts` cookie-less guard is out of scope (keep client guard, but render nothing sensitive before check).
4. **Shared primitives** in `web/app/components/ui/`: `ErrorBanner` (with retry), `Pagination`, `TableState` (loading/empty), `ConfirmDialog`, `AdminGuard`, `useApiError()`; `lib/format.ts` (`timeAgo`, `formatDate`); replace 9/4/3 duplicates.
5. Load fonts with `next/font/google`; fix invalid spacing classes (`py-0.2`); consistent button system; remove dev jargon from copy; ESLint config + fix; remove dead `ComingSoon`, react-query, unused imports.
6. Repository: search by `product_name` or manufacturer (normalised); Overview: skeleton loading, retry on heatmap.
7. Tests: add Vitest + Testing Library + jsdom; replace regex tests for auth-context, bbox geometry, queue filters, assign dialog with real component tests; keep `npm test` green.

### Phase E — Integration, edge cases, security hardening — P1/P2
1. End-to-end run on this laptop: mobile (real device via LAN) → ingest → PaddleOCR → verdict → queue → review → notification on phone → challan PDF → archive. Fix whatever breaks.
2. District routing: normalise district strings (single `normalise_district()` used by users, scans, events).
3. Backend hardening: rate-limit login (in-memory sliding window), request-size limits, bounded pagination, CORS origins from settings, `trust_remote_code` off unless explicit, structured logging + global exception handler (no stack traces to clients), security headers.
4. Edge cases per surface: empty DB, first-run user, expired token mid-flow, offline capture → kill app → restart, duplicate rapid taps (idempotent challan/assign/review), slow backend (timeouts + retry UI), corrupt image upload.
5. Accessibility & motion (§7/§10): focus rings, Seal Badge shape/icon differentiation, `prefers-reduced-motion`, stamp animation once, red→green 150 ms transition already present.

### Phase F — Deployment & docs — P2
1. `docker-compose.yml`: db + api (+ optional worker profile) + web; `Dockerfile`s; `.env` templates.
2. README rewrite: architecture, one-command local setup (Windows + Linux), demo script (credentials, sample images, expected outcomes), troubleshooting.
3. `audit/progress.md` entries; retire stale statements in blueprint docs where architecture changed (file access, OCR engine policy, mobile auth).

---

## D. Deferred / needs owner call later
- Barcode/GTIN detection (explicitly out of scope).
- Florence-2 on GPU; YOLOv8 custom weights training (script exists, no data).
- Celery/Redis worker (BackgroundTasks + semaphore is adequate for demo; compose keeps a worker profile stub).
- Hindi UI localisation (§8.3) — layout flex fixes only, no translation.
- Kubernetes.

---

## E. Verification checklist (per phase, repeated at the end)
- `cd backend && pytest -q` (all green; postgres-marked suite green against local DB)
- `alembic downgrade base && alembic upgrade head` on empty DB
- `cd web && npm run lint && npx tsc --noEmit && npm test && npm run build`
- `cd mobile && flutter analyze && flutter test`
- Manual: login as each role on web; field login on phone; capture real biscuit packet + debit card; observe real OCR text in scan detail; review → phone notification; generate challan → PDF opens with correct boxes; admin activates ruleset → next scan uses it; audit log shows every action.

## F. Critical files
Backend: `app/core/config.py`, `app/main.py`, `app/models/scan.py`, `app/models/rule_result.py`, `alembic/versions/`, `app/routers/scans.py`, `app/routers/challans.py`, `app/routers/events.py`, `app/services/storage.py`, `app/services/vision/extraction_pipeline.py`, `app/services/vision/ocr/paddle_ocr.py`, `app/services/vision/detector.py`, `app/services/pipeline_orchestrator.py`, `app/services/rules/ruleset_config.py`, `app/db/seed_*.py`, `tests/conftest.py` (new).
Mobile: `lib/main.dart`, `features/auth/data/auth_service.dart`, `features/auth/presentation/login_screen.dart`, `features/capture/presentation/capture_screen.dart`, `features/scans/services/sync_worker.dart`, `core/database/database_helper.dart`, `features/scans/presentation/home_screen.dart`, `features/notifications/services/*`, `android/app/src/main/AndroidManifest.xml`, `pubspec.yaml`.
Web: `app/queue/[id]/page.tsx`, `app/queue/page.tsx`, `app/components/AppShell.tsx`, `lib/api.ts`, `lib/auth-context.tsx`, `next.config.mjs`, `tailwind.config.ts`, `app/layout.tsx`, `package.json`.
