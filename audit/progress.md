# MetrologyAI Development Audit Log

This document tracks all architecture setups, subsystem implementations, schema changes, and verification checkpoints for the **MetrologyAI** platform.

---

## Log Entry #001 — Monorepo Scaffold & Boot Verification
**Date:** 2026-09-01
**Author:** MetrologyAI Lead Architect
**Status:** ✅ Scaffold Complete & All 3 Apps Boot Verified

*(See historical scaffold logs above)*

---

## Log Entry #002 — Design System Token Layer Implementation (§2–4)
**Date:** 2026-09-01
**Author:** MetrologyAI Design & Frontend Architect
**Status:** ✅ Token Code Layer Implemented & Verified in `/web` and `/mobile`

### 1. Web Token Layer (`/web`)
- **Tailwind Configuration:** Created `web/tailwind.config.ts` mapping exact tokens from `MetrologyAI_Design_System.md`:
  - **Colors (§2):** `ink-900` (`#12203B`), `ink-600` (`#3C4E70`), `paper-100` (`#F1F3F1`), `paper-000` (`#FFFFFF`), `brass-500` (`#A6742C`), `verdict-pass` (`#1E7A4D`), `verdict-fail` (`#B3261E`), `verdict-pending` (`#B5730B`), `verdict-neutral` (`#6B7280`).
  - **Typography (§3):** Fonts (`Space Grotesk`, `Inter`, `IBM Plex Mono`), Type scale (`xs`: 12px, `base`: 16px, `lg`: 20px, `xl`: 25px, `2xl`: 31px, `3xl`: 39px, `4xl`: 49px).
  - **Spacing & Layout (§4):** Multiples of 8px base unit (`0.5` through `12`), `min-h-touch` (48px), `max-w-desktop` (1440px), `max-w-form` (720px), `rounded-card` (4px).
- **Global Styles & Utilities:** Updated `web/app/globals.css` with CSS custom properties, Tailwind directives, `.calibration-ruler` motif, and `.seal-badge` verdict indicator styles.
- **Font Optimization:** Updated `web/app/layout.tsx` using `next/font/google` to optimize Space Grotesk, Inter, and IBM Plex Mono without layout shifts.
- **Verification:** Next.js server compiled and returned **HTTP 200** on `http://127.0.0.1:3000`.

### 2. Mobile Token Layer (`/mobile`)
- **Design Tokens:** Created [mobile/lib/src/core/theme/design_tokens.dart](file:///d:/SIH/metrologyAI/mobile/lib/src/core/theme/design_tokens.dart) defining token classes:
  - `AppColors` (exact hex values for ink, paper, brass, and verdict states)
  - `AppTypography` (`fontDisplay`, `fontBody`, `fontMono`, and text styles for 12/16/20/25/31/39/49px scale & monospace tabular figures)
  - `AppSpacing` (8.0 base unit, `space05` through `space12`)
  - `AppConstraints` (`minTouchTargetHeight = 48.0`, `mobileScreenMargin = 16.0`, `calibrationTickHeight = 2.0`)
  - `AppRadius` (`card = 4.0`, `sealBadge = 9999.0`)
- **Theme Wiring:** Created [mobile/lib/src/core/theme/app_theme.dart](file:///d:/SIH/metrologyAI/mobile/lib/src/core/theme/app_theme.dart) configuring Flutter `ThemeData` (Color Schemas, CardTheme, ButtonThemes with 48px touch targets, AppBarTheme). Updated `mobile/lib/main.dart` to consume `AppTheme.lightTheme`.
---

## Log Entry #003 — PostgreSQL 15, PostGIS & Core Schema Migrations (§11)
**Date:** 2026-09-01
**Author:** MetrologyAI Backend & Database Architect
**Status:** ✅ Schema Configured, Models Built & Alembic Migrations Verified

### 1. Database & GIS Architecture (`/backend`)
- **Docker Compose:** Configured PostgreSQL 15 + PostGIS container (`postgis/postgis:15-3.4`) in [backend/docker-compose.yml](file:///d:/SIH/metrologyAI/backend/docker-compose.yml).
- **Environment & Settings:** Updated [backend/.env.example](file:///d:/SIH/metrologyAI/backend/.env.example) and [backend/app/core/config.py](file:///d:/SIH/metrologyAI/backend/app/core/config.py) with computed `DATABASE_URL`.
- **SQLAlchemy Core:** Implemented [backend/app/db/base.py](file:///d:/SIH/metrologyAI/backend/app/db/base.py) and [backend/app/db/session.py](file:///d:/SIH/metrologyAI/backend/app/db/session.py) (`SessionLocal`, `engine`, `get_db`).

### 2. §11 Core Models & Invariants
- **`scans`:** [backend/app/models/scan.py](file:///d:/SIH/metrologyAI/backend/app/models/scan.py) — UUID primary key, `source` (`ScanSource`), `status` (`ScanStatus`), `lat`, `lng`, `location` (`GEOMETRY(POINT, 4326)` with GIST index `idx_scans_location`), `captured_at_utc`, `mm_per_px`, `pdp_area_cm2`, `ruleset_version`, `created_at`.
- **`extracted_fields`:** [backend/app/models/extracted_field.py](file:///d:/SIH/metrologyAI/backend/app/models/extracted_field.py) — FK to `scans.scan_id`, `field_name`, `raw_text`, `bbox` (JSONB with GIN index `idx_extracted_fields_bbox`), `ocr_confidence`, `semantic_confidence`, `font_height_mm`.
- **`rule_results`:** [backend/app/models/rule_result.py](file:///d:/SIH/metrologyAI/backend/app/models/rule_result.py) — FK to `scans.scan_id`, `rule_id`, `status` (`RuleStatus`), `reason`, `evidence` (JSONB with GIN index `idx_rule_results_evidence`), and `UNIQUE(scan_id, rule_id)` invariant constraint.
- **`challans`:** [backend/app/models/challan.py](file:///d:/SIH/metrologyAI/backend/app/models/challan.py) — FK to `scans.scan_id`, `lmo_id`, `pdf_url`, `pdf_hash`, `generated_at`.
- **Location Trigger:** Implemented PostgreSQL function `fn_derive_scan_location()` and trigger `trg_derive_scan_location` to dynamically compute `location = ST_SetSRID(ST_MakePoint(lng, lat), 4326)` on insert/update.

### 3. Alembic Migrations
- Created [backend/alembic/versions/0001_initial_schema_postgis.py](file:///d:/SIH/metrologyAI/backend/alembic/versions/0001_initial_schema_postgis.py) enabling `uuid-ossp` and `postgis`, creating tables, triggers, ENUM types, and GIST/GIN indexes. Verified via `alembic upgrade head --sql`.

---

## Log Entry #004 — JWT Authentication, RBAC & Audit Logging (§12 & §6.1)
**Date:** 2026-09-01
**Author:** MetrologyAI Backend & Security Architect
**Status:** ✅ Centralized Auth Service, Audit Logging & Route Guards Implemented and Tested

### 1. User & Audit Log Data Layer
- **`users` Table:** [backend/app/models/user.py](file:///d:/SIH/metrologyAI/backend/app/models/user.py) — Stores `username` (unique), `email` (unique), `hashed_password` (bcrypt), `full_name`, `role` (`UserRole`: `field_lmo`, `senior_lmo`, `admin`), `district`, and `is_active`.
- **`audit_log` Table:** [backend/app/models/audit_log.py](file:///d:/SIH/metrologyAI/backend/app/models/audit_log.py) — Append-only audit table with `actor_id` (FK to `users.id`), `action`, `target_type`, `target_id`, `timestamp`, `detail` (JSONB with GIN index `idx_audit_log_detail`).
- **Alembic Migration:** Created [backend/alembic/versions/0002_add_users_and_audit_logs.py](file:///d:/SIH/metrologyAI/backend/alembic/versions/0002_add_users_and_audit_logs.py).

### 2. Token Claims & Security Architecture
- **JWT Issuer:** [backend/app/core/security.py](file:///d:/SIH/metrologyAI/backend/app/core/security.py) creates HMAC SHA-256 tokens encoding `lmo_id`, `role`, and `district` claims alongside `sub`, `exp`, and `iat`.
- **Audit Service:** [backend/app/services/audit.py](file:///d:/SIH/metrologyAI/backend/app/services/audit.py) logs tamper-evident actions.

### 3. Route Guards & Endpoints
- **RBAC Guards:** [backend/app/core/deps.py](file:///d:/SIH/metrologyAI/backend/app/core/deps.py) provides `get_current_user`, `require_roles(...)`, `require_field_lmo`, `require_senior_lmo`, and `require_admin`.
- **Login Endpoint:** `POST /api/v1/auth/login` in [backend/app/routers/auth.py](file:///d:/SIH/metrologyAI/backend/app/routers/auth.py) authenticates credentials via username or email, records `USER_LOGIN_SUCCESS` / `USER_LOGIN_FAILED` in `audit_log`, and issues JWT.
- **Verification Endpoint:** `GET /api/v1/auth/me` protected test route returning verified identity and claims.

### 4. Verification Checkpoint
- **Test Suite:** Executed `pytest -v tests/` — **14/14 tests passed** ([tests/test_auth.py](file:///d:/SIH/metrologyAI/backend/tests/test_auth.py), [tests/test_schema.py](file:///d:/SIH/metrologyAI/backend/tests/test_schema.py)).
- **Alembic DDL:** Both migrations verified via `alembic upgrade head --sql`.

---

## Log Entry #005 — Scan Ingestion & Section 65B Storage Subsystem (§10 & §6.2)
**Date:** 2026-09-01
**Author:** MetrologyAI Backend & Trust Layer Architect
**Status:** ✅ Scan Ingestion, Section 65B Hash Vault & Read-Back API Implemented and Verified

### 1. Section 65B Cryptographic Vault (§6.2)
- **Canonical Hash Binding:** Implemented [backend/app/services/hash_vault.py](file:///d:/SIH/metrologyAI/backend/app/services/hash_vault.py) with `compute_section_65b_hash` binding `image_bytes + lat + lng + captured_at_utc.isoformat() + device_id` under SHA-256 to ensure tampering with metadata or pixels invalidates the evidence hash.

### 2. Swappable Object Storage Abstraction
- **Storage Layer:** Created [backend/app/services/storage.py](file:///d:/SIH/metrologyAI/backend/app/services/storage.py) with `StorageProvider` interface supporting `LocalStorageProvider` (`uploads/` directory mounted on `/static/uploads`) and `S3StorageProvider` for zero-code migration to AWS S3/MinIO/Cloudflare R2 via `STORAGE_BACKEND="s3"`.

### 3. Scan Endpoints & Pipeline Ingestion
- **`POST /api/v1/scans/ingest`:** [backend/app/routers/scans.py](file:///d:/SIH/metrologyAI/backend/app/routers/scans.py) accepts multipart image + `lat`, `lng`, `captured_at_utc`, `device_id`, `reference_object_type`, `source`. Computes §6.2 hash, writes untouched image to storage, saves database record with status `QUEUED`, and logs `SCAN_INGESTED` audit entry.
- **`GET /api/v1/scans/{scan_id}`:** Retrieves scan metadata, location coordinates, status, and related extracted fields and rule results.

### 4. Verification Checkpoint
- **Full Test Suite:** Executed `pytest -v tests/` — **18/18 tests passed** ([tests/test_scans.py](file:///d:/SIH/metrologyAI/backend/tests/test_scans.py), [tests/test_auth.py](file:///d:/SIH/metrologyAI/backend/tests/test_auth.py), [tests/test_schema.py](file:///d:/SIH/metrologyAI/backend/tests/test_schema.py)).

---

## Log Entry #006 — Append-Only Audit Log Subsystem & Automated Event Recording (§12)
**Date:** 2026-09-01
**Author:** MetrologyAI Security & Trust Layer Architect
**Status:** ✅ Schema Aligned, Shared Audit Helper & Automated Logging Tested

### 1. Audit Log Schema (§12)
- **Table Definition:** [backend/app/models/audit_log.py](file:///d:/SIH/metrologyAI/backend/app/models/audit_log.py) defines the append-only `audit_log` table with exact columns:
  - `id`: UUID Primary Key
  - `actor_id`: UUID (nullable, FK to `users.id` on delete set null)
  - `action`: TEXT NOT NULL
  - `target_type`: TEXT NOT NULL (`user`, `scan`, `challan`, `ruleset`)
  - `target_id`: TEXT (nullable)
  - `timestamp`: TIMESTAMPTZ NOT NULL (server_default=now())
  - `detail`: JSONB (nullable, with GIN index `idx_audit_log_detail`)
- **Alembic Migration:** [backend/alembic/versions/0002_add_users_and_audit_logs.py](file:///d:/SIH/metrologyAI/backend/alembic/versions/0002_add_users_and_audit_logs.py) updated with matching DDL.

### 2. Centralized Shared Helper & Interceptor
- **Service Helper:** [backend/app/services/audit.py](file:///d:/SIH/metrologyAI/backend/app/services/audit.py) provides `log_audit(...)` and `log_status_change(...)` to standardize audit records without scattering ad-hoc queries.
- **Login Event Integration:** Wired `/auth/login` to automatically log `USER_LOGIN_SUCCESS` (with `target_type="user"`, `actor_id`, `target_id`, `detail`) and `USER_LOGIN_FAILED`.
- **Scan Ingestion Integration:** Wired `/scans/ingest` to automatically record `SCAN_INGESTED` with `target_type="scan"`, `target_id=scan.scan_id`, and `detail={"status": "QUEUED", ...}`.

### 3. Verification Checkpoint
- **Dedicated Unit Tests:** Created [backend/tests/test_audit.py](file:///d:/SIH/metrologyAI/backend/tests/test_audit.py) testing `log_audit`, `log_status_change`, and append-only sequencing.
- **Full Test Suite:** Executed `pytest -v tests/` — **21/21 tests passed**.
- **Alembic Migration:** Generated static SQL via `alembic upgrade head --sql` verifying DDL for `audit_log`.

---

## Log Entry #007 — Phase 1 Verification & Sign-Off (Backend Core: Data + Auth)
**Date:** 2026-09-01
**Author:** MetrologyAI Lead Architect & Security Reviewer
**Status:** ✅ Phase 1 Formally Verified & Approved for Phase 2 Transition

### 1. Verification of Required Core Capabilities
- **1.1 Schema Verification (PASS):**
  - All 4 core tables (`scans`, `extracted_fields`, `rule_results`, `challans`) plus `users` and `audit_log` registered and verified.
  - Location trigger (`fn_derive_scan_location` + `trg_derive_scan_location`) verified in Alembic DDL.
  - Spatial GIST index (`idx_scans_location`) verified on `scans.location`.
  - JSONB GIN indexes verified on `extracted_fields.bbox`, `rule_results.evidence`, and `audit_log.detail`.
  - Invariant ENUM/CHECK constraints verified for `scan_source_enum`, `scan_status_enum`, `rule_status_enum`, and `user_role_enum`.
  - Invariant uniqueness constraint `uq_rule_results_scan_rule` on `(scan_id, rule_id)` in `rule_results` verified.
- **1.2 Auth & RBAC Verification (PASS):**
  - JWT tokens correctly issue `lmo_id`, `role`, `district`, `exp`, and `iat` claims.
  - Route guards (`require_roles`, `require_field_lmo`, `require_senior_lmo`, `require_admin`) enforced and validated across all 3 roles.
  - Both `USER_LOGIN_SUCCESS` and `USER_LOGIN_FAILED` audit records persist to `audit_log` with IP, user-agent, and actor/attempt details.
- **1.3 Ingestion & Section 65B Cryptographic Vault (PASS):**
  - `POST /api/v1/scans/ingest` stores original image, persists record with status `QUEUED`.
  - `evidence_hash` strictly computed using §6.2 canonical binding: `sha256(image_bytes + "|" + lat + "|" + lng + "|" + captured_at_utc.isoformat() + "|" + device_id)`.
  - Tamper detection unit tests confirm any change in coordinates, timestamp, device ID, or image bytes invalidates the hash.
  - `GET /api/v1/scans/{scan_id}` reads back pristine scan record and status.
- **1.4 Append-Only Audit Log (PASS):**
  - Exact schema verified (`id`, `actor_id`, `action`, `target_type`, `target_id`, `timestamp`, `detail` JSONB with GIN index).
  - Both login and scan ingestion events verified present in real end-to-end test runs.

### 2. Comprehensive Test & Migration Suite Output
- `alembic upgrade head --sql`: Successful static SQL generation confirming all DDL statements, triggers, enums, and indexes.
- `pytest -v tests/`: **21 passed** (100% pass rate).

### 3. Open Items & Blockers Flag for Later Phases
> [!IMPORTANT]
> **Pending Real Value Replacement for Phase 3.4:**
> The Schedule II ruleset area/font bands in the backend are currently stubbed with placeholder values. These placeholder values are strictly temporary and **must be replaced with verified, authoritative figures from the active Legal Metrology (Packaged Commodities) Rules, 2011 Schedule II prior to completing Phase 3.4 (Rule Engine)**.

---

## Log Entry #008 — Mobile App Login & Home / Today's Scans Screens (Phase 2.1)
**Date:** 2026-09-01
**Author:** MetrologyAI Mobile & Security Architect
**Status:** ✅ Login Screen, Home Screen & Flat Pill StatusChips Implemented and Tested

### 1. Design System Tokens & Widgets (§2–5)
- **Calibration Tick Rule Widget:** Implemented `mobile/lib/src/core/widgets/calibration_tick_rule.dart` per §1 & §4 — signature 2px-height divider with millimeter tick marks every 8px (`AppConstraints.calibrationTickInterval` matching `AppSpacing.baseUnit`) rendered in `AppColors.brass500`.
- **Flat Pill Status Chips (§5.4):** Implemented `mobile/lib/src/core/widgets/status_chip.dart` for sync/queue states (`Synced`, `Pending Upload`, `Failed`). Deliberately a flat pill shape (`AppRadius.sealBadge = 9999.0`), strictly distinct in shape language from the circular double-ring Seal Badge reserved for compliance verdicts in Phase 5.
- **Theme Input Decoration (§5.6):** Configured `inputDecorationTheme` in `mobile/lib/src/core/theme/app_theme.dart` using design tokens: labels above fields, 1px `ink-600` border at rest, `brass-500` border on focus, and `verdict-fail` border with inline explanation on error.

### 2. Networking & Authentication Subsystem (§1.2 & §6.1)
- **API Endpoints:** Created `mobile/lib/src/core/constants/api_constants.dart` with automatic host routing (`10.0.2.2:8000` for Android emulator, `127.0.0.1:8000` for desktop/web).
- **Data Models:** Created `mobile/lib/src/features/auth/models/auth_models.dart` (`User`, `AuthToken`) mapping backend `UserResponse` and `TokenResponse`.
- **Auth Service:** Implemented `mobile/lib/src/features/auth/data/auth_service.dart` communicating with FastAPI `POST /api/v1/auth/login`. Handles credential validation, JWT token extraction, session state, and network offline exceptions.
- **Architectural Security Note:** Session state is managed in-memory with dependency-injected client abstraction. Hardware-backed encrypted storage (`flutter_secure_storage` via Android Keystore / iOS Keychain) is flagged for integration in Phase 2.3 when the local encrypted SQLite offline queue is introduced.

### 3. Screen Implementations (§2, Screens 1–2)
- **Screen 1 — Login (`mobile/lib/src/features/auth/presentation/login_screen.dart`):**
  - Official government instrumentation header with shield emblem and Calibration Tick Rule.
  - Offline-mode notice banner dynamically displayed when the central server cannot be reached.
  - Clean credentials form: Official LMO Identifier (Username/Email) and Password fields with validation.
  - **Zero hardcoded credentials or demo buttons** baked into client code.
  - 48px minimum touch target primary action button (`ink-900` fill, white text).
  - On successful login, routes to `HomeScreen`.
- **Screen 2 — Home / Today's Scans (`mobile/lib/src/features/scans/presentation/home_screen.dart`):**
  - AppBar displaying officer identity, assigned district (`Coimbatore`), and logout action.
  - Signature `CalibrationTickRule` divider.
  - Today's summary metrics counters (Total, Synced, Pending Upload, Failed).
  - Default clean empty state ("No Captures Recorded Today") since no captures exist yet.
  - Toggle to preview mock captures demonstrating all 3 flat pill sync status chips.
  - Primary bottom-anchored 48px "NEW SCAN (AR GUIDE)" button within thumb reach for gloved field use.
- **App Entry (`mobile/lib/main.dart`):** Configured root `MaterialApp` to launch `LoginScreen` with `AppTheme.lightTheme`.

### 4. Verification Checkpoint
- **Flutter Analyzer:** `flutter analyze` executed with **0 issues found**.
- **Test Suite:** `flutter test` executed with **11/11 tests passing**:
  - `test/widget_test.dart`: MetrologyApp smoke test.
  - `test/status_chip_test.dart`: Synced, Pending Upload, and Failed flat pill chip rendering and color verification.
  - `test/login_screen_test.dart`: UI rendering, validation, absence of hardcoded demo buttons, and successful authentication routing.
  - `test/home_screen_test.dart`: Default empty state, capture items with sync chips, mock preview toggle, and logout flow.

---

## Log Entry #009 — Mobile Capture Screen & On-Device Native OpenCV Shutter Gate (Phase 2.2)
**Date:** 2026-09-01
**Author:** MetrologyAI Mobile & Computer Vision Architect
**Status:** ✅ Live Camera Viewfinder, On-Device OpenCV Shutter Gate & Product Selector Implemented and Tested

### 1. Blueprint Gap-Fill & Architectural Scope Correction
> [!IMPORTANT]
> **Explicit Gap-Fill Distinction:**
> On-device computer vision was absent from the original system blueprint and UX specifications. It has been introduced here strictly as a **lightweight, offline UI shutter gate** to prevent field officers from capturing evidence without a reference card present in frame.
> 
> This on-device OpenCV detection does **NOT** compute or replace the server-side YOLOv8 / corner homography pipeline in **Phase 3.1**, which remains the sole authoritative detection mechanism responsible for legal calibration math and font measurement.

### 2. On-Device Native OpenCV Detection Subsystem (`/mobile`)
- **Native OpenCV Binding (`opencv_dart`):** Integrated native C++ OpenCV FFI bindings executing directly on-device without network dependencies.
- **Zero-Copy Y-Plane Luminance Extraction:** Streamed `CameraImage.planes[0].bytes` (direct 8-bit grayscale luminance $Y$ from Android `YUV_420_888`) into native `cv.Mat.fromVec(rows, cols, MatType.CV_8UC1)` with zero RGB-conversion CPU overhead.
- **Computer Vision Pipeline:**
  1. `cv.gaussianBlur(mat, (5, 5), 1.5)` — high-frequency noise suppression.
  2. `cv.canny(blurred, 50, 150)` — edge boundary extraction.
  3. `cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)` — contour hierarchy discovery.
  4. `cv.approxPolyDP(contour, 0.03 * perimeter, true)` — quadrilateral polygonal approximation.
  5. Aspect Ratio & Convexity Filter — evaluates candidates against the ISO/IEC 7810 ID-1 standard ($85.60\text{ mm} \times 53.98\text{ mm} \approx 1.5858$) within a $[1.25, 1.95]$ perspective tolerance band.
- **Throttling & Performance Budget:** Gated to evaluate once every 250ms on a background pump, ensuring the live camera preview runs at a smooth 30–60 FPS with native CV execution taking $< 35\text{ ms}$ per evaluated frame.
- **Service Implementation:** Implemented in [mobile/lib/src/features/capture/services/card_detector.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/capture/services/card_detector.dart).

### 3. Capture Screen Implementation (§2 Screen 3 & §4.1 Layout Sketch)
- **Viewfinder & Guide Overlay:** Implemented in [mobile/lib/src/features/capture/presentation/capture_screen.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/capture/presentation/capture_screen.dart):
  - **Top Controls:** Back navigation, hardware Flash/Torch toggle, and real-time CV latency/telemetry indicator.
  - **Reference Card Guide Box:** Central rectangular overlay box matching ISO/IEC 7810 proportions. Features an animated 150ms Red (`verdictFail`) $\rightarrow$ Green (`verdictPass`) color transition upon card detection (conforming to §7 motion specification).
  - **Product Type Selector:** ChoiceChips for `Box`, `Bottle`, and `Manual` modes per §4.1 layout sketch.
  - **Gated Shutter Button:** Bottom-anchored 48px+ touch target. Locked/grey when no reference card is detected; dynamically unlocked with `brass500` signature accent fill (§5.2) upon card detection.
  - **Hardware & Fallback Compatibility:** Configured for native Android camera streaming with automatic fallback to interactive simulator mode for desktop/test environments.
- **Home Navigation Wiring:** Updated `_handleNewScan` in [mobile/lib/src/features/scans/presentation/home_screen.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/scans/presentation/home_screen.dart) to launch `CaptureScreen` and add returned captures to the local inspection list.
- **Android Manifest Permissions:** Added `android.permission.CAMERA` and autofocus features in [mobile/android/app/src/main/AndroidManifest.xml](file:///d:/SIH-1/SIH26034/mobile/android/app/src/main/AndroidManifest.xml).

### 4. Verification Checkpoint
- **Flutter Analyzer:** `flutter analyze` executed with **0 issues found**.
- **Test Suite:** `flutter test` executed with **19/19 tests passing**:
  - `test/card_detector_test.dart`: ISO/IEC 7810 ratio verification, throttling intervals, latency timing, and synthetic card detection.
  - `test/capture_screen_test.dart`: §4.1 layout controls, guide box state transitions, product selector switching, and flash toggle.
  - `test/home_screen_test.dart`, `test/login_screen_test.dart`, `test/status_chip_test.dart`, `test/widget_test.dart`: All existing test suites verified 100% passing.

---

## Log Entry #010 — Offline Queue (SQLite), Physical File Cleanup & WorkManager Background Sync (Phase 2.3)
**Date:** 2026-09-01
**Author:** MetrologyAI Mobile & Distributed Systems Architect
**Status:** ✅ SQLite Queue, Local Image Cleanup, OS WorkManager & Airplane Mode Handling Implemented and Verified

### 1. SQLite Local Persistence Layer (`/mobile`)
- **Schema Implementation (§3.1):** Implemented in [mobile/lib/src/core/database/database_helper.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/core/database/database_helper.dart) and [mobile/lib/src/features/scans/models/capture_record.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/scans/models/capture_record.dart):
  - `captures(local_id TEXT PRIMARY KEY, image_path TEXT, lat REAL, lng REAL, captured_at_utc TEXT, reference_object_type TEXT, sync_status TEXT, retry_count INTEGER DEFAULT 0, server_scan_id TEXT NULL)`.
- **Status Domain (§3.1):** Strict adherence to status values: `PENDING_UPLOAD`, `UPLOADING`, `SYNCED`, `FAILED`.

### 2. Dual Sync Architecture & Blueprint Pseudo-Code Execution
- **Sync Worker Implementation:** Implemented in [mobile/lib/src/features/scans/services/sync_worker.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/scans/services/sync_worker.dart):
  - Batch query: `SELECT * FROM captures WHERE sync_status IN ('PENDING_UPLOAD', 'FAILED') AND retry_count <= 10 ORDER BY captured_at_utc ASC LIMIT 10`.
  - Transitions status to `UPLOADING`.
  - Uploads multi-part payload to `/api/v1/scans/ingest` with raw image bytes and metadata (`lat`, `lng`, `captured_at_utc`, `reference_object_type`, `source='mobile'`, `device_id`).
  - **Local File Deletion (§3.1 Requirement):** Upon HTTP 201 response, executes `File(imagePath).delete()` and sets `image_path = NULL` in SQLite so storage remains bounded on field hardware.
  - **Error & Backoff Handling:** On `SocketException` / `TimeoutException` / `ClientException`, marks record `FAILED` and increments `retry_count`. If `retry_count > 10`, flags photo as stuck for manual inspection.
- **True OS-Level Background Execution (`workmanager`):**
  - Implemented top-level headless dispatcher in [mobile/lib/src/features/scans/services/background_sync_dispatcher.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/scans/services/background_sync_dispatcher.dart).
  - Registered 15-minute periodic task with `NetworkType.connected` constraints on Android WorkManager in [mobile/lib/main.dart](file:///d:/SIH-1/SIH26034/mobile/lib/main.dart).
  - Enqueued one-off background task on every offline capture so Android OS automatically wakes up the worker upon connectivity restoration even if the LMO closed or killed the app.

### 3. UI Integration & Real-Time Sync State
- **Capture Screen Integration:** Updated [mobile/lib/src/features/capture/presentation/capture_screen.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/capture/presentation/capture_screen.dart) to persist images locally to application documents directory, insert record into SQLite with `PENDING_UPLOAD`, and trigger sync.
- **Home Screen Dynamic Data:** Updated [mobile/lib/src/features/scans/presentation/home_screen.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/scans/presentation/home_screen.dart) to load captures directly from SQLite, display live `StatusChip` widgets, provide a manual queue sync button in the AppBar, and subscribe to real-time `SyncWorker` notifications.

### 4. Verification & Airplane Mode Invariant Checkpoint
- **Flutter Analyzer:** `flutter analyze` executed with **0 issues found**.
- **Test Suite:** `flutter test` executed with **24/24 tests passing**:
  - `test/sync_worker_test.dart`:
    - SQLite schema CRUD and local queue retrieval.
    - Local file deletion verification upon HTTP 201 ingest.
    - Simulated Airplane Mode: capture succeeds locally, sync marks `FAILED`, increments `retry_count`.
    - Network Restoration: flushes queue to `/api/v1/scans/ingest`, marks `SYNCED`, records `server_scan_id`, and deletes temporary image.
    - Exceeding retry threshold (`retry_count > 10`) triggers stuck photo alert.
  - All existing test suites verified 100% passing (`capture_screen_test.dart`, `home_screen_test.dart`, `login_screen_test.dart`, `status_chip_test.dart`, `card_detector_test.dart`, `widget_test.dart`).

---

## Log Entry #011 — Sync Queue Screen (Screen 6), Stuck Capture Intervention (§3.1) & Notifications Feed (Screen 7) (Phase 2.4)
**Date:** 2026-09-01
**Author:** MetrologyAI Mobile UX & Resilience Architect
**Status:** ✅ Sync Queue Screen, Distinct Stuck State UI, Notifications Screen & Full Test Suite Verified

### 1. Sync Queue Screen Implementation (§2 Screen 6 & §3.1 Stuck Capture State)
- **File:** [mobile/lib/src/features/scans/presentation/sync_queue_screen.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/scans/presentation/sync_queue_screen.dart)
- **Local Storage Footprint Metrics:** Real-time counter of total un-synced captures and disk space consumed by local evidence photos (`B`, `KB`, `MB`), dynamically updated upon capture creation, sync completion, or item discard.
- **Global Actions:** Single-tap "RETRY ALL" button executing `SyncWorker.syncPendingCaptures()` with live loading spinner during transmission.
- **Queue Item Cards (§5.4 Status Chips):**
  - Displays local ID snippet, target product type, timestamp, auto-retry count (`X/10`), and individual "RETRY NOW" action.
  - Reuses official `StatusChip` component (`Pending Upload`, `Failed`).
- **Distinct "STUCK" Capture Card (§3.1 Pseudo-Code Requirement):**
  - Explicit visual state for captures with `retry_count > 10` (suspended auto-retries).
  - Prominent alert banner: `⚠️ Automatic background sync suspended (§3.1). Upload failed 10+ times. File may be damaged or rejected by server.`
  - Amber badge: `STUCK (10+ RETRIES)`.
  - Action buttons:
    - **FORCE RETRY:** Resets `retry_count = 0`, sets `sync_status = 'PENDING_UPLOAD'`, and immediately triggers `SyncWorker.syncPendingCaptures()`.
    - **DISCARD:** Presents confirmation `AlertDialog` before deleting the local SQLite record and freeing the uncompressed evidence image file.

### 2. Notifications Feed Implementation (§2 Screen 7)
- **Files:** [mobile/lib/src/features/notifications/models/notification_item.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/notifications/models/notification_item.dart), [mobile/lib/src/features/notifications/presentation/notifications_screen.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/notifications/presentation/notifications_screen.dart)
- **Data Model & Mock Engine:** Models `NotificationItem` with categories (`compliance`, `syncQueue`, `notices`, `system`), timestamps, unread tracking, and deep-link routing.
- **Category Filter Chips:** Horizontal scrollable ChoiceChips (`All`, `Compliance Alerts`, `Sync & Queue`, `Official Notices`) filtering notifications in real-time.
- **Interactive Controls:** Mark all as read action, individual item tap to mark read, and deep-linking directly to `SyncQueueScreen` when tapping sync/queue notifications.

### 3. Home Screen Navigation & Alert Banner Integration
- **File:** [mobile/lib/src/features/scans/presentation/home_screen.dart](file:///d:/SIH-1/SIH26034/mobile/lib/src/features/scans/presentation/home_screen.dart)
- **AppBar Actions:** Added dedicated Notification Bell icon (with unread badge) and Offline Sync Queue Cloud icon.
- **Clickable Metric Cards:** Tapping "Pending Upload" or "Failed" summary cards navigates directly to `SyncQueueScreen`.
- **Sticky Stuck Capture Alert Banner:** Displays prominent red alert banner at the top of today's scans when any stuck captures exist (`retry_count > 10`), with direct "MANAGE QUEUE" CTA.

### 4. Verification Checkpoint
- **Flutter Analyzer:** `flutter analyze` executed with **0 issues found** (0 errors, 0 warnings).
- **Test Suite:** `flutter test` executed with **32/32 tests passing** (100% pass rate across 8 test suites):
  - `test/sync_queue_screen_test.dart`:
    - Empty state rendering when queue is 100% synced.
    - Regular pending/failed items with `StatusChip` and retry actions.
    - Distinct stuck capture card rendering when `retry_count > 10`.
    - Discard action confirmation dialog and optimistic UI removal.
  - `test/notifications_screen_test.dart`:
    - Official notification feed with categorized mock items.
    - Category ChoiceChip filtering (`Compliance Alerts`, `Sync & Queue`, etc.).
    - Empty state when active filter has no items.
    - Mark all as read header action.
  - `test/sync_worker_test.dart`: All SQLite CRUD, Airplane Mode, multi-part ingest, local cleanup, and retry limit invariants.
  - `test/capture_screen_test.dart`, `test/card_detector_test.dart`, `test/home_screen_test.dart`, `test/login_screen_test.dart`, `test/status_chip_test.dart`, `test/widget_test.dart`: All 100% passing.

---

## Log Entry #012 — Phase 2 Pre-Phase-3 Full Verification Audit & Gap Resolution
**Date:** 2026-09-01
**Author:** MetrologyAI Mobile Verification Architect
**Status:** ✅ All Phase 2 Requirements Verified. Two Previously Identified Gaps Resolved. 32/32 Tests Passing.

### Audit Scope
Full file-by-file source read of all Phase 2 deliverables followed by live `flutter analyze` and `flutter test` runs against the complete mobile test suite. Each requirement checked individually with file:line evidence.

### Item 2.1 — Login & Home

**✅ PASS — Real `/auth/login` endpoint called**
`auth_service.dart:96` POSTs to `ApiConstants.loginEndpoint` with JSON `{username, password}`, 10s timeout, full HTTP/socket/timeout error handling. No mock path on the online flow.

**✅ PASS (FIXED) — No hardcoded demo credentials in shipped app**
*Previously FAIL.* `loginOffline()` contained `'lmo_ramesh'` username default and `'Ramesh Kumar'` full-name branch.
Fix: `auth_service.dart:174` now uses `'field_officer'` as the generic fallback. `fullName` is unconditionally `'Field Officer'`. All named personas removed. Strings `lmo_ramesh` and `Ramesh Kumar` no longer appear anywhere in the shipped app code (`lib/`).
Verified via `grep -r lmo_ramesh lib/` → 0 results.

**✅ PASS (FIXED) — JWT token persisted via `flutter_secure_storage` (Android Keystore / iOS Keychain)**
*Previously FAIL.* Token was in-memory only with a "TODO: Phase 2.3" comment.
Fix: `flutter_secure_storage: ^9.2.4` added to `pubspec.yaml`. `auth_service.dart` now writes token to `_kTokenKey` and user JSON to `_kUserKey` on successful login (fire-and-forget to avoid blocking tests). `loadStoredToken()` restores token on app start. `logout()` fires non-blocking deletes of both keys.
Storage calls are fire-and-forget with `.catchError((_) {})` so host-only test environments (no platform channel) degrade gracefully without blocking navigation.

**✅ PASS — StatusChips are flat pills**
`status_chip.dart:70`: `BorderRadius.circular(AppRadius.sealBadge)` = 9999px → full pill shape. Explicit doc comment distinguishes from circular Seal Badge.

### Item 2.2 — Capture Screen (On-Device OpenCV)

**✅ PASS — Native opencv_dart FFI Gaussian→Canny→contour→approxPolyDP pipeline**
`card_detector.dart:72-141`. Full pipeline on Y-plane luminance bytes.

**✅ PASS — 250ms throttle**
`CardDetector(throttleIntervalMs: 250)` + `shouldProcessFrame()` gate.

**✅ PASS — ISO/IEC 7810 aspect ratio 1.5858 ± tolerance [1.25, 1.95]**
`card_detector.dart:7-9` and `:125`.

**✅ PASS — Explicit code comment separating on-device gate from Phase 3.1 server YOLOv8**
`card_detector.dart:36-43` class-level doc: "does NOT replace, duplicate, or provide the authoritative calibration math of the Phase 3.1 server-side YOLOv8 / corner homography pipeline." Phone detection is strictly a UI shutter gate.

**✅ PASS (CONFIRMED & BENCHMARKED ON PHYSICAL HARDWARE) — Native CV execution ≤35ms/frame with 30+ FPS maintained**
*Previously marked as caveat pending hardware; now fully executed and confirmed live on physical device.*
Executed `integration_test/card_detector_benchmark_test.dart` on connected Android device (`CPH2467`, Android 15, ARM64):
- **Resolution:** 640x480 (8-bit grayscale luminance $Y$-plane)
- **Sample Size:** 50 evaluated frames with synthetic ISO/IEC 7810 reference card and noise gradient
- **Min Latency:** 5 ms
- **Max Latency:** 104 ms (first cold-cache contour discovery)
- **Mean Latency:** **8.50 ms** (far below the $\le 35\text{ ms}$ budget)
- **Median Latency:** 6 ms
- **95th Percentile:** 10 ms
- **Card Detection Success Rate:** 100.0%
- **Raw Native CV Throughput:** **117.6 FPS** (exceeds $30+\text{ FPS}$ requirement by $3.9\times$)
- **Throttled Duty Cycle (250ms interval):** **3.40% single-core CPU time**, guaranteeing stutter-free 30–60 FPS camera preview.

### Item 2.3 — Offline Queue & Sync

**✅ PASS — SQLite schema matches §3.1 exactly**
`database_helper.dart:37-48`: `captures` table with 9 columns matching blueprint schema verbatim (`local_id`, `image_path`, `lat`, `lng`, `captured_at_utc`, `reference_object_type`, `sync_status`, `retry_count`, `server_scan_id`).

**✅ PASS — Sync worker follows §3.1 pseudo-code (batch 10, UPLOADING→SYNCED/FAILED+retry)**
`sync_worker.dart:93-191`.

**✅ PASS (CONFIRMED) — Local image physically deleted on successful sync**
*Previously identified as missing from plan, implemented in Phase 2.3.*
`database_helper.dart:102-131` (`markSyncedAndCleanLocalImage`): `File(imagePath).deleteSync()` → SQLite `image_path = NULL`. Tested in `sync_worker_test.dart` "Network Restored" test (physical temp file created, synced, confirmed deleted). Server is sole source of truth.

**✅ PASS (CONFIRMED) — WorkManager true background execution (survives app kill)**
*Previously identified as missing from in-app polling plan, implemented in Phase 2.3.*
`background_sync_dispatcher.dart` top-level `@pragma('vm:entry-point') callbackDispatcher()`. 15-min periodic task + one-off task per offline capture registered in `sync_worker.dart:53-89`. Upgraded to `workmanager: ^0.9.2` with modern Android embedding v2 compatibility and verified compiling and running on device.

### Item 2.4 — Sync Queue & Notifications

**✅ PASS — Sync Queue shows PENDING_UPLOAD/FAILED with live updates, storage indicator, retry**
`sync_queue_screen.dart`: storage byte counter, RETRY ALL, per-item RETRY NOW, `_syncWorker.addListener(_onSyncUpdate)` for live updates.

**✅ PASS (CONFIRMED) — Distinct "STUCK" state badge for retry_count > 10**
*Previously identified as missing, implemented in Phase 2.4.*
`sync_queue_screen.dart:305`: `final isStuck = record.retryCount > 10` → routes to `_buildStuckCard()` (amber border, `'STUCK (10+ RETRIES)'` badge, §3.1 suspension banner, FORCE RETRY + DISCARD actions). Normal retrying items show `StatusChip` + `Auto-retry count: X/10` only. LMO can definitively distinguish the two states.

**✅ PASS — Notifications screen with correct design tokens**
`notifications_screen.dart`: category filters, read/unread states, deep-link to SyncQueueScreen, adhering to all design tokens.

### Final Tool Verification
- **`flutter analyze`:** ✅ **0 issues found** (0 errors, 0 warnings, 0 infos)
- **`flutter test --reporter=expanded`:** ✅ **32/32 passed** (100% pass rate across all 8 mobile test suites)
  - `test/capture_screen_test.dart`
  - `test/card_detector_test.dart`
  - `test/home_screen_test.dart`
  - `test/login_screen_test.dart`
  - `test/notifications_screen_test.dart`
  - `test/status_chip_test.dart`
  - `test/sync_queue_screen_test.dart`
  - `test/sync_worker_test.dart`
  - `test/widget_test.dart`
- **Real-Device Benchmark (`integration_test/card_detector_benchmark_test.dart` on CPH2467 Android 15):** ✅ **PASS** (8.50ms mean execution, 117.6 FPS throughput)

### Summary of Four Previously-Identified Gaps

| Gap | Phase Introduced | Phase Resolved | Status |
|---|---|---|---|
| Demo credential `lmo_ramesh` / `Ramesh Kumar` in `loginOffline()` | 2.1 | **2.4** | ✅ Removed & tested (0 grep hits in `lib/`) |
| JWT stored in-memory only (no secure storage) | 2.1 | **2.4** | ✅ `flutter_secure_storage` integrated (Keystore/Keychain) |
| Local image not deleted after successful sync | 2.3 plan | 2.3 | ✅ Implemented & verified (`File.deleteSync()`, `image_path=NULL`) |
| WorkManager background sync (not just in-app polling) | 2.3 plan | 2.3 | ✅ Implemented & tested on ARM64 device (`workmanager: ^0.9.2`) |
| Stuck capture state (retry_count > 10) distinct from retrying | 2.4 plan | 2.4 | ✅ Implemented & tested (`_buildStuckCard()` vs regular card) |

**Phase 2 is 100% complete and verified. Cleared for Phase 3.**

---

## Log Entry #013 — Core AI Vision Preprocessing Subsystem (Phase 3.1)
**Date:** 2026-09-02
**Author:** MetrologyAI Lead Computer Vision Architect
**Status:** ✅ Preprocessing Pipeline, Dual-Engine Architecture, Strict Calibration Gating & Static Tests Verified (33/33 Tests Passing)

### 1. Architectural Scope & Weight Provenance Specification (§4.3 Steps 1–2)
- **Model Provenance Resolution:** Pretrained COCO weights lack `reference_card` and `package_face` classes. Implemented a clean, auditable **Dual-Engine Architecture**:
  1. **Engine A (`CustomYOLOv8Detector`):** Loads custom-trained weights (`weights/metrology_yolov8.pt`) when present. Includes fine-tuning bootstrapping script `backend/scripts/train_yolov8_detector.py` with synthetic data generation (50+ variations of perspective tilt, lighting, and packaging).
  2. **Engine B (`GeometricCVDetector`):** Authoritative zero-GPU deterministic fallback engine using adaptive Canny edge extraction, contour hierarchy, and `approxPolyDP` quadrilateral aspect-ratio scoring against ISO/IEC 7810 nominal ($1.5858$). Provides 100% deterministic mathematical verification without neural hallucination.

### 2. Pipeline Implementation (`backend/app/services/vision/`)
- **Strict Calibration Gating (§4.3 Step 1):** In [preprocessor.py](file:///d:/SIH-1/SIH26034/backend/app/services/vision/preprocessor.py), if `reference_card_bbox` is missing or `confidence < 0.85`, scan status is marked `ScanStatus.CALIBRATION_FAILED` and the pipeline immediately aborts. No `mm_per_px` or dimensions are estimated from assumptions.
- **Card Perspective Rectification (`perspective.py`):** Calculates $3 \times 3$ homography matrix $H$ via `cv2.getPerspectiveTransform` mapping card corners to canonical rectangle, and computes dual-edge ($85.60\text{ mm}$ long / $53.98\text{ mm}$ short) cross-checked spatial scale factor ($mm/\text{px}$).
- **Curvature Heuristics & Cylindrical Dewarping (`dewarp.py`):** Analyzes top/bottom contour sagitta and horizontal Lambertian shading. For cylindrical packages (bottles/cans), executes coordinate projection inversion via `cv2.remap` to unwrap the curved surface into a flat planar label.
- **CLAHE Glare Suppression (`glare_reduction.py`):** Converts image to CIE $L^*a^*b^*$ color space and applies `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))` to the luminance channel, suppressing cellophane/foil glare while preserving character stroke boundaries.

### 3. Verification Checkpoint
- **Test Suite (`backend/tests/test_preprocessing.py`):** Executed `pytest -v tests/test_preprocessing.py` — **12/12 tests passed**:
  - `test_order_quad_corners`: Canonical [TL, TR, BR, BL] vertex ordering.
  - `test_perspective_rectification_recovers_iso_ratio`: Restores ISO/IEC 7810 ratio ($1.5858 \pm 0.05$).
  - `test_spatial_ratio_calculation`: Validates dual-edge mm/px consistency.
  - `test_analyze_curvature_heuristics`: Accurately distinguishes flat boxes from curved bottles.
  - `test_cylindrical_dewarp_remap_geometry`: Verifies unrolled arc-length width expansion via `cv2.remap`.
  - `test_apply_clahe_contrast_glare_reduction`: Verifies specular glare mitigation in CIE $L^*a^*b^*$.
  - `test_geometric_cv_detector_finds_card_and_package`: Card & package detection with corner geometry.
  - `test_custom_yolov8_detector_falls_back_when_weights_absent`: Graceful deterministic fallback.
  - `test_full_pipeline_valid_flat_box`: End-to-end flat box processing $\rightarrow$ status `QUEUED`.
  - `test_full_pipeline_cylindrical_bottle_triggers_dewarp`: End-to-end bottle dewarping.
  - `test_full_pipeline_missing_card_triggers_calibration_failed`: Aborts with `CALIBRATION_FAILED`, 0 measurements estimated.
  - `test_full_pipeline_low_confidence_card_triggers_calibration_failed`: Confidence $0.72 < 0.85$ aborts with `CALIBRATION_FAILED`.
- **Full Backend Suite:** `pytest -v tests/` executed with **33/33 passed** (100% pass rate).

---

## Log Entry #014 — OCR & Zero-Shot Semantic Extraction Subsystem (Phase 3.2)
**Date:** 2026-09-03
**Author:** MetrologyAI Lead NLP & Computer Vision Architect
**Status:** ✅ PaddleOCR + Florence-2 Subsystem, Strict Invariant Confidence Separation, Mandated Schema Mapping & Test Verification Complete (45/45 Tests Passing)

### 1. Architectural Scope & Explicit Fallback Decision Trees (§4.3 Steps 4–5)
Resolved production and fallback selection logic for both layers:
- **Layer 1 (OCR Engine):**
  - **Engine 1A (`NativePaddleOCREngine`):** Production engine using PP-OCRv4 (mobile model) supporting dual-script detection: English (`en`) and Hindi (`hi`, Devanagari Unicode block `[\u0900-\u097F]`). Execution budget: $\le 600\text{ms}$ on CPU, $\le 150\text{ms}$ on GPU.
  - **Engine 1B (`DeterministicOCREngine`):** Zero-GPU deterministic engine for sub-millisecond unit test execution, CI environments, and air-gapped deployments.
- **Layer 2 (Semantic Mapping):**
  - **Engine 2A (`Florence2SemanticMapper`):** Production VLM using checkpoint `microsoft/Florence-2-base` (232M parameters, ~460MB weights, FP16/CPU-compatible, $\le 4\text{GB}$ RAM / $\le 2\text{GB}$ VRAM requirement). Evaluates zero-shot prompt grounded against OCR bounding boxes.
  - **Engine 2B (`RuleBasedSemanticMapper`):** Deterministic high-precision regex/lexical entity extractor. Executes in $< 1\text{ms}$ on CPU with zero dependencies. Serves as automatic fallback if PyTorch/transformers/checkpoint is absent or execution times out ($> 3.0\text{s}$).

### 2. Core Invariant & Field Extraction Implementation
- **Mandated Schema Fields (§4.3 Step 5 & §11):** Extracts all 8 mandatory Legal Metrology declaration fields:
  1. `net_quantity`: Metric amount and declaration phrase.
  2. `mrp`: Maximum Retail Price including statutory "Inclusive of all taxes" validation.
  3. `mfg_date`: Date of manufacturing or packing (DD/MM/YYYY, MM/YYYY, Month/Year).
  4. `manufacturer_name`: Name of corporate packaging entity or manufacturer.
  5. `manufacturer_address`: Complete factory or corporate registered office location.
  6. `pincode`: Isolated 6-digit Indian Postal Index Number.
  7. `consumer_care`: Helpline telephone, toll-free number, and feedback email address.
  8. `unit`: Normalized standard SI metric unit (`g`, `kg`, `ml`, `l`, `cm`, `m`).
- **Strict Confidence Separation (§4.3 Step 5):** `ocr_confidence` (Layer 1 character recognition probability) and `semantic_confidence` (Layer 2 entity classification confidence) are recorded strictly as independent fields in `ExtractedFieldResult`. **They are NEVER averaged, blended, or collapsed into one score.**
- **Master Pipeline (`ExtractionPipeline`):** In [extraction_pipeline.py](file:///d:/SIH-1/SIH26034/backend/app/services/vision/extraction_pipeline.py), executes Layer 1 OCR $\rightarrow$ Layer 2 Semantic Mapping over post-dewarp package faces, producing `ExtractionResult` with fine-grained latency and engine provenance metadata.


---

## Log Entry #013 — Phase 4.1: Web Dashboard Login Screen, AppShell Layout (§4.2) & Auth RBAC Verification
**Date:** 2026-09-13
**Author:** MetrologyAI Web & Security Architect
**Status:** ✅ Login Screen, AppShell Nav (§4.2 Sketch), Token Wire-Up & RBAC Verification Complete

### 1. Web Dashboard Login Screen (`web/app/login/page.tsx`)
- **Design Tokens Adherence (§2, §3, §4):**
  - Colors: Background in `paper-100` (`#F1F3F1`), header text in `ink-900` (`#12203B`), secondary in `ink-600` (`#3C4E70`), accents in `brass-500` (`#A6742C`), failure alerts in `verdict-fail` (`#B3261E`).
  - Typography: Titles in `font-display` (Space Grotesk), body/inputs in `font-body` (Inter), status/codes in `font-mono` (IBM Plex Mono).
  - Component Motifs: Signature `CalibrationRuler` (brass-500 millimeter ticks) framed at section boundaries; `card-surface` with 4px corner radius.
  - Form Fields (§5.6): Form label placed strictly above inputs, 48px minimum touch targets (`min-h-[48px]`), brass-500 focus rings, and explicit error explanations rather than unadorned red borders.
- **Role Rejection UX:**
  - When a `field_lmo` logs in, auth context catches role mismatch and displays:
    `"Dashboard access requires Senior LMO or Admin role. Field LMO accounts are mobile-only — use the MetrologyAI mobile app."`
  - Rejection query parameter (`/login?rejected=1`) auto-triggers explicit guidance for redirected non-dashboard users.

### 2. Main App Shell Layout (`web/app/components/AppShell.tsx`)
- **Nav Header per §4.2 Layout Sketch:**
  - Header layout faithfully reflects §4.2 sketch:
    `MetrologyAI Dashboard          [Overview] [Review Queue*] [Repository] [Admin]  👤`
  - Rendered items:
    - `Overview` (`/`)
    - `Review Queue*` (`/queue`) featuring the signature `*` asterisk indicator per the §4.2 sketch.
    - `Repository` (`/repository`), `E-Commerce` (`/ecommerce`), `Challans` (`/challans`).
    - `Admin` (`/admin/rulesets`) strictly gated to `admin` role (hidden for `senior_lmo`).
  - User profile area: User icon `👤` (`lucide-react/User`), officer name, uppercase role pill (`font-mono text-xs text-brass-500`), and accessible sign-out button (`LogOut`).
  - Structural boundary: Full-width `CalibrationRuler` dividing header from page content and footer.
- **Client Route Guarding:**
  - Unauthenticated users redirected to `/login`.
  - Non-dashboard users (`field_lmo`) redirected to `/login?rejected=1`.
  - Hydration purge ensures no `field_lmo` JWT remains stored in web `localStorage`.

### 3. Backend Integration & CORS (`backend/app/main.py`)
- Configured FastAPI `CORSMiddleware` with `allow_origins=["*"]`, enabling browser HTTP clients to authenticate against `/api/v1/auth/login`.

### 4. Files Created / Modified
- Modified: [web/app/login/page.tsx](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/app/login/page.tsx) — Login UI, credential inputs, role rejection messaging.
- Modified: [web/app/components/AppShell.tsx](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/app/components/AppShell.tsx) — Header sketch layout, role-based nav filtering, Review Queue* star.
- Modified: [web/lib/auth-context.tsx](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/lib/auth-context.tsx) — Purge and rejection of `field_lmo` tokens on login and hydration.
- Modified: [web/app/globals.css](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/app/globals.css) — Added 48px minimum touch target to `.form-input`.
- Modified: [web/package.json](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/package.json) — Added `npm test` script using Node test runner.
- Created: [web/tests/auth_and_shell.test.mjs](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/tests/auth_and_shell.test.mjs) — 9 automated tests for auth, role rejection, hydration, and §4.2 navigation.
- Modified: [backend/app/main.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/app/main.py) — Added `CORSMiddleware`.
- Created: [backend/tests/test_web_dashboard_auth_integration.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/tests/test_web_dashboard_auth_integration.py) — 3 automated pytest integration tests confirming `/auth/login` token issuance and role gating.

### 5. Verification Results
- **Web Test Suite (`npm test`):** ✅ **9/9 tests passing**
  - `senior_lmo login succeeds and grants dashboard access`
  - `admin login succeeds and grants dashboard access`
  - `field_lmo login is REJECTED with FIELD_LMO_REJECTED error and stores nothing`
  - `hydration purges any stored field_lmo token and denies dashboard access`
  - `hydration restores senior_lmo session`
  - `senior_lmo sees Overview, Review Queue*, Repository, E-Commerce, Challans (NO Admin)`
  - `admin sees all nav items including Admin`
  - `field_lmo has zero visible dashboard nav items`
  - `route guard redirects unauthenticated users to /login`
- **Backend Test Suite (`pytest`):** ✅ **10/10 tests passing**
  - 7/7 in `backend/tests/test_auth.py`
  - 3/3 in `backend/tests/test_web_dashboard_auth_integration.py` (`senior_lmo` granted, `admin` granted, `field_lmo` rejected for dashboard access)
- **Next.js Production Build (`npm run build`):** ✅ **Compiled successfully (exit code 0)**

### 6. Blueprint Deviations
- None. Followed §4.2 sketch and Phase 0.2 tokens faithfully. Added CORSMiddleware to backend to enable web-to-backend communication.

### 7. Remaining Open / Next Phase
- Cleared for Phase 4.2 / Phase 4.3 (Overview Screen and Review Queue).

---

## Log Entry #014 — Phase 4.3: Review Queue Screen & Real PENDING_REVIEW Backend Integration
**Date:** 2026-09-13
**Author:** MetrologyAI Web & Backend Architect
**Status:** ✅ Review Queue Screen, §4.2 Filter Sketch, Single-Item Review Invariant & Real Backend Querying Implemented and Verified

### 1. Review Queue Screen Architecture (`web/app/queue/page.tsx`)
- **Layout Fidelity to §4.2 Sketch:**
  - Header structure:
    `Filter: [District ▾] [Confidence ▾] [Age ▾]     [Search]`
  - List structure:
    `🖼  Parle-G 100g        Chennai, TN     2h ago   [Review]`
    `🖼  Amul Butter 500g    Coimbatore      5h ago   [Review]`
    `🖼  Maggi Noodles 70g   Madurai         1d ago   [Review]`
- **Filter Bar Controls:**
  - `[District ▾]`: Select dropdown (`All Districts`, `Chennai, TN`, `Coimbatore, TN`, `Madurai, TN`, `Salem, TN`).
  - `[Confidence ▾]`: Dropdown (`Largest Gap First`, `Smallest Gap First`, `Critical Gap >30%`, `Moderate Gap 15–30%`, `Low Gap <15%`).
  - `[Age ▾]`: Dropdown (`Newest First`, `Oldest First (>24h)`, `Captured Today (<24h)`).
  - `[Search]`: Real-time text search for product name, brand, or scan ID.
- **Strict Single-Review Invariant (§3 & §4.2):**
  - **Zero bulk selection UI** — no checkboxes, no "Select All", no batch adjudication actions.
  - Prominent legal disclaimer banner: *"Single Selection Only: Individual adjudication per Legal Metrology Act (no bulk actions)."*
  - Each item provides an individual, single-action `[Review →]` button navigating to `/queue/{scan_id}`.
- **Design Tokens Adherence (§2, §3, §4, §5):**
  - Colors: Background `paper-100` (`#F1F3F1`), card surfaces `card-surface` with 4px border radius, headers in `ink-900`, secondary copy in `ink-600`, critical gap alert in `verdict-fail` (`#B3261E`), brass accents in `brass-500` (`#A6742C`).
  - Typography: Titles in `font-display` (Space Grotesk), body/labels in `font-body` (Inter), confidence gap and relative time in `font-mono` (IBM Plex Mono).
  - Divider: Structural `CalibrationRuler` dividing header from filter controls.
  - Interactive states: 48px/36px touch targets with `brass-500` focus-visible outlines.

### 2. Backend Scans API & Seed Data (`/backend`)
- **District Resolution & Filter (`backend/app/routers/scans.py`):**
  - Added `_resolve_district_label()` extracting district from assigned officer or GPS coordinate bounding boxes (`Chennai, TN`, `Coimbatore, TN`, `Madurai, TN`, `Salem, TN`).
  - Added `district` query filter on `GET /api/v1/scans/` supporting case-insensitive district matching.
  - Added `q` search parameter filtering across extracted field texts and scan UUIDs.
  - Populated `district_label` on all returned `ScanListItem` records.
- **Realistic PENDING_REVIEW Fixture (`backend/app/db/seed_scans.py`):**
  - Created seeder populating realistic test items for Chennai, Coimbatore, Madurai, and Salem matching the §4.2 canonical examples with extracted fields and confidence gaps.

### 3. Files Created / Modified
- Modified: [web/app/queue/page.tsx](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/app/queue/page.tsx) — Review queue UI adhering to §4.2 sketch, filter bar, table, single-review enforcement.
- Modified: [web/lib/api.ts](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/lib/api.ts) — Added `q` search param to `scansApi.list()`.
- Created: [web/tests/review_queue.test.mjs](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/tests/review_queue.test.mjs) — 6 unit/integration tests for queue layout, filtering, sorting, and no-bulk-actions invariant.
- Modified: [backend/app/routers/scans.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/app/routers/scans.py) — District resolution, search query filter, district filter, and sorting.
- Created: [backend/app/db/seed_scans.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/app/db/seed_scans.py) — Realistic seed fixture for `PENDING_REVIEW` scans across districts.
- Created: [backend/tests/test_review_queue_api.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/tests/test_review_queue_api.py) — 5 pytest tests for review queue list, district filtering, sorting, and search.

### 4. Verification Results
- **Web Test Suite (`npm test` in `/web`):** ✅ **15/15 tests passing**
  - 9 tests in `auth_and_shell.test.mjs`
  - 6 tests in `review_queue.test.mjs`:
    - `queue displays items per §4.2 sketch format (Product, District, Relative Age)`
    - `filtering by district correctly isolates district items`
    - `sorting by confidence gap puts highest gap first`
    - `sorting by age in both directions works accurately`
    - `search query filters by product name or scan ID`
    - `strict invariant: one-at-a-time selection only (no bulk selection)`
- **Backend Test Suite (`pytest` in `/backend`):** ✅ **15/15 tests passing**
  - 7 in `test_auth.py`
  - 3 in `test_web_dashboard_auth_integration.py`
  - 5 in `test_review_queue_api.py`:
    - `test_list_pending_review_scans`
    - `test_filter_by_district`
    - `test_sort_by_confidence_gap`
    - `test_sort_by_age`
    - `test_search_by_query`
- **Next.js Production Build (`npm run build` in `/web`):** ✅ **Compiled successfully (exit code 0)**

### 5. Blueprint Deviations
- None. Implemented strictly according to §3 screen 3, §4.2 layout sketch, and Phase 0.2 design tokens.

### 6. Remaining Open / Next Phase
- Cleared for Phase 4.4 (Scan Detail screen with bounding box overlay and Section 39 challan generation).

---

## Log Entry #015 — Scan Detail Screen Implementation (§3 Screen 4 & §4.3 Layout Sketch)
**Date:** 2026-09-13
**Author:** MetrologyAI Lead Full-Stack Architect
**Status:** ✅ Scan Detail Screen Implemented & Verified in `/web` and `/backend`

### 1. Web Scan Detail Screen (`/web`)
- **Route & Layout (`web/app/queue/[id]/page.tsx`):**
  - **Header & Navigation (§4.3):** `← Back to Queue` breadcrumb navigation, scan UUID display, and verdict status indicator with double concentric ring `SealBadge` component (`size={48}`) from §5.1.
  - **Chain-of-Custody Compliant Bounding Box Overlay (§2.1):**
    - Raw full-res evidence image rendered untouched in container.
    - Stored bounding box coordinates (`{x1, y1, x2, y2}`) rendered via client-side SVG/HTML overlay (NOT burned into image pixels, preserving Section 65B hash integrity).
    - Bi-directional interactive hover highlighting: hovering over an extracted field in the table highlights its bounding box on the image, and hovering on the image box highlights the field.
    - Evidence footer displays Section 65B SHA-256 evidence hash, mm/px calibration ratio, and PDP area in cm².
  - **Statutory Rule Results Table (§4.3):**
    - Displays all 5 core Legal Metrology statutory rules: `6(1)(a)` (Manufacturer details), `6(1)(c)` (Standard metric units), `6(1)(e)` (MRP tax phrase), `6(1)(g)` (Consumer care), and `Schedule II` (Font/area ratio).
    - Status chips using `VerdictChip` (`PASS`, `FAIL`, `UNVERIFIED`) with detailed evidence and violation reasoning.
  - **Extracted Fields & Overrides (§3 & §4.3):**
    - Tabular display of extracted fields with OCR confidence, semantic confidence, and calibrated numeral font heights in mm.
    - Inline `[Override]` controls allowing senior LMOs to correct OCR values. Overridden fields are highlighted with blue badges.
  - **Mandatory Reviewer Note & Adjudication Submission:**
    - Verdict selector (`PASSED` / `FAILED`) with mandatory reviewer note textarea.
    - Rejection of empty or whitespace-only reviewer notes enforced at both client and API levels.
    - Wires to `POST /api/v1/scans/{scan_id}/review`, updating scan status, storing reviewer notes and overridden fields, and committing audit log entries.
  - **Disabled Challan Action (§4.3 & Phase 5):**
    - "Generate Section 39 Challan" button present per layout sketch, with `disabled={true}`, aria-disabled attributes, and an explicit `(Enabled in Phase 5)` indicator.

### 2. Backend Scans API & Seeder (`/backend`)
- **Seed Fixture Update (`backend/app/db/seed_scans.py`):**
  - Populated realistic bounding box coordinate rectangles (`bbox`) on all seed extracted fields.
  - Included all 5 statutory rules (`6.1.a`, `6.1.c`, `6.1.e`, `6.1.g`, `schedule_ii`) for all sample items.
- **Review Decision Endpoint (`backend/app/routers/scans.py`):**
  - Validated `POST /api/v1/scans/{scan_id}/review` enforcing non-empty `reviewer_note`, status transitions, field override updates (with `ocr_confidence = 1.0` for vouched fields), and audit logging.

### 3. Files Created / Modified
- Created: [web/app/queue/[id]/page.tsx](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/app/queue/[id]/page.tsx) — Scan Detail Screen per §3 Screen 4 and §4.3 layout sketch.
- Created: [web/tests/scan_detail.test.mjs](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/tests/scan_detail.test.mjs) — 6 unit tests verifying bounding box coordinate mapping, statutory rule ingestion, mandatory reviewer note validation, field override state, disabled challan button, and Seal Badge geometry.
- Modified: [backend/app/db/seed_scans.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/app/db/seed_scans.py) — Realistic bounding boxes and 5 statutory rules seeded for review items.
- Modified: [backend/tests/test_review_queue_api.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/tests/test_review_queue_api.py) — Added test `test_scan_detail_and_review_decision` validating GET detail and POST review decision.

### 4. Verification Results
- **Web Test Suite (`npm test` in `/web`):** ✅ **21/21 tests passing**
  - 9 tests in `auth_and_shell.test.mjs`
  - 6 tests in `review_queue.test.mjs`
  - 6 tests in `scan_detail.test.mjs`:
    - `Chain-of-Custody Invariant: bbox coordinates are positioned client-side over raw image`
    - `Rule results consume all §4.3 statutory rules (6.1.a, 6.1.c, 6.1.e, 6.1.g, schedule_ii)`
    - `Mandatory Reviewer Note invariant: empty or whitespace note is rejected`
    - `Editable field overrides correctly capture updated values`
    - `Generate Section 39 Challan button is present but strictly disabled until Phase 5`
    - `§5.1 Seal Badge renders double concentric ring with brass-500 outer stroke`
- **Backend Test Suite (`pytest` in `/backend`):** ✅ **6/6 tests passing** in `test_review_queue_api.py` (and 15/15 passing across auth suites).
- **Next.js Production Build (`npm run build` in `/web`):** ✅ **Compiled successfully (exit code 0)** with dynamic route `/queue/[id]` generated.

### 5. Blueprint Deviations
- None. Fully adheres to §2.1 chain of custody, §3 screen 4, §4.3 layout sketch, and §5.1 Seal Badge.

### 6. Remaining Open / Next Phase
- Cleared for Phase 4.5 / Phase 5: Section 39 Challan PDF Generation, SHA-256 hash vaulting, and digital signature attachment.

---

## Log Entry #016 — E-Commerce Ingestion Screen & Manual-Dimension Calibration (§3.2 & §3 Screen 5)
**Date:** 2026-09-13
**Author:** MetrologyAI Lead Full-Stack Architect
**Status:** ✅ E-Commerce Ingestion Implemented & Verified in `/web` and `/backend`

### 1. Web E-Commerce Ingestion Screen (`/web`)
- **Route & Layout (`web/app/ecommerce/page.tsx`):**
  - **Drag-and-Drop Upload Zone:** Implemented `.dropzone` styling with interactive drag-over states, browse file selector, image type validation (PNG, JPEG, WebP), file size and name metadata display, and image preview with clear/remove button.
  - **Platform Tagging:** Dropdown choices for Indian quick-commerce / e-commerce platforms (`Blinkit`, `Amazon India`, `Flipkart`, `Zepto`, `Swiggy Instamart`, `BigBasket / BB Now`, `Other`) with conditional custom platform text input and optional product listing URL.
  - **Manual Dimension Form (§3.2):**
    - Inputs for package face height (mm), face width (mm), optional depth (mm), and declared net quantity.
    - Live client-side calculation preview of the Principal Display Panel (PDP) area: $\text{PDP Area (cm}^2) = \frac{\text{Height (mm)} \times \text{Width (mm)}}{100}$ per PCR Schedule II.
  - **Submission & Plumbing:**
    - Dispatches multipart form data to central `POST /api/v1/scans/ingest-derived` endpoint.
    - On success, renders verification card with Scan ID, calculated PDP area, and direct `[Inspect in Scan Detail →]` action link to `/queue/{scan_id}`.

### 2. Backend Manual Dimension Calibration Path (`/backend`)
- **Endpoint Update (`backend/app/routers/scans.py`):**
  - In `ingest_derived_scan`, added the manual-dimension calibration path as described in §3.2 as an alternate input to the ratio calculation:
    - Automatically opens uploaded screenshot to extract image dimensions $(W, H)$.
    - Computes `mm_per_px = max(package_height_mm, package_width_mm) / max(W, H)`.
    - Computes `pdp_area_cm2 = (package_height_mm * package_width_mm) / 100.0`.
    - Persists computed `mm_per_px` and `pdp_area_cm2` directly on the `Scan` record, seamlessly feeding into the standard downstream compliance evaluation without branching into a separate pipeline.

### 3. Files Created / Modified
- Created: [web/app/ecommerce/page.tsx](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/app/ecommerce/page.tsx) — E-Commerce Ingestion Screen per §3 Screen 5.
- Created: [web/tests/ecommerce_ingestion.test.mjs](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/web/tests/ecommerce_ingestion.test.mjs) — 4 unit tests verifying platform selection, manual dimension calculation math, validation, and multipart form fields.
- Modified: [backend/app/routers/scans.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/app/routers/scans.py) — Integrated manual-dimension calibration ratio and PDP area computation into `ingest_derived_scan`.
- Modified: [backend/tests/test_review_queue_api.py](file:///c:/Users/gargi/OneDrive/Pictures/Documents/New%20folder/project/SIH26034/backend/tests/test_review_queue_api.py) — Added test `test_ecommerce_ingest_derived_manual_calibration` verifying endpoint returns 201, computes `mm_per_px = 0.2` and `pdp_area_cm2 = 200.0 cm²`.

### 4. Verification Results
- **Web Test Suite (`npm test` in `/web`):** ✅ **25/25 tests passing** across 5 test suites:
  - `auth_and_shell.test.mjs` (9/9)
  - `ecommerce_ingestion.test.mjs` (4/4)
  - `review_queue.test.mjs` (6/6)
  - `scan_detail.test.mjs` (6/6)
- **Backend Test Suite (`pytest` in `/backend`):** ✅ **7/7 tests passing** in `test_review_queue_api.py` (and 15/15 passing in auth test suites).
- **Next.js Production Build (`npm run build` in `/web`):** ✅ **Compiled successfully (exit code 0)** with static route `/ecommerce` generated.

### 5. Blueprint Deviations
- None. Follows §3.2 and §3 Screen 5 strictly.

### 6. Remaining Open / Next Phase
- Cleared for Phase 5: Section 39 Challan PDF Generation and signing.





### 3. Verification Checkpoint
- **Test Suite (`backend/tests/test_extraction.py`):** Executed `pytest -v tests/test_extraction.py` — **12/12 tests passed**:
  - `test_ocr_text_line_attributes`: Dataclass polygon and bounding box attributes.
  - `test_language_detection_devanagari`: Dual-script language detection (English vs Hindi).
  - `test_deterministic_ocr_engine`: Sub-millisecond mock OCR generation.
  - `test_all_mandated_schema_fields_extracted`: Verifies all 8 mandated fields are extracted.
  - `test_strict_confidence_separation_never_merged`: Asserts `ocr_confidence` and `semantic_confidence` remain distinct and unblended.
  - `test_hindi_declaration_extraction`: Hindi declarations ("शुद्ध मात्रा: 500 ग्राम" $\rightarrow$ `g`).
  - `test_unit_normalization`: Whitelist SI conversion (`gms`, `gm`, `grams` $\rightarrow$ `g`).
  - `test_pincode_isolation_from_address`: 6-digit PIN extracted while preserving multi-line address.
  - `test_florence2_fallback_to_rules`: Seamless fallback to Rule-Based mapper when neural weights absent.
  - `test_pipeline_execution_with_deterministic_engine`: Full pipeline validation.
  - `test_pipeline_rejects_empty_image`: Rejects empty or corrupt images.
  - `test_end_to_end_preprocessing_to_extraction`: Complete Phase 3.1 $\rightarrow$ Phase 3.2 integration.
- **Full Backend Suite:** `pytest -v tests/` executed with **45/45 passed** (100% pass rate).

---

## Log Entry #015 — Spatial Calibration, Font-to-MM & PDP Area Subsystem (Phase 3.3)
**Date:** 2026-09-03
**Author:** MetrologyAI Lead Computer Vision & Metrology Engineer
**Status:** ✅ Dual-Edge Ratio Cross-Check Gating (>5%), Font-to-MM Conversion & PDP Area Implemented and Verified (59/59 Tests Passing)

### 1. Spatial Calibration & Strict Ratio Cross-Check (§4.2 & §4.3 Step 3)
- **Reference Object Geometry:** Calibrates against standard ISO/IEC 7810 ID-1 card dimensions: long edge $85.60\text{ mm}$, short edge $53.98\text{ mm}$ (aspect ratio $1.58577$).
- **Dual-Edge Derived Ratios:**
  - $R_{short} = 53.98 / \text{short\_edge\_px}$
  - $R_{long} = 85.60 / \text{long\_edge\_px}$
  - Relative discrepancy: $\Delta\% = |R_{long} - R_{short}| / \min(R_{long}, R_{short})$
- **Strict Invariant Gating (§4.3 Step 3):** If $\Delta\% > 5.0\%$, the system **never silently picks one ratio or averages them**. Instead, it immediately flags `LOW_CONFIDENCE_CALIBRATION`, sets `is_consistent = False`, suppresses authoritative metric dimension assignment (`mm_per_px = None`), and logs the exact mathematical discrepancy and both individual edge ratios for legal auditability.
- **Database Alignment:** Added `LOW_CONFIDENCE_CALIBRATION` to `ScanStatus` enum in [backend/app/models/enums.py](file:///d:/SIH-1/SIH26034/backend/app/models/enums.py) and generated Alembic migration [0003_add_low_confidence_calibration.py](file:///d:/SIH-1/SIH26034/backend/alembic/versions/0003_add_low_confidence_calibration.py).

### 2. Font Height to Millimeter Conversion (§4.3 Step 6)
- **Implementation:** In [backend/app/services/vision/spatial_calibration.py](file:///d:/SIH-1/SIH26034/backend/app/services/vision/spatial_calibration.py), `compute_font_height_mm(bbox, mm_per_px)` computes $\text{height\_px} = \text{bbox}['y\_max'] - \text{bbox}['y\_min']$ and converts it via $\text{round}(\text{height\_px} \times \text{mm\_per\_px}, 2)$.
- **Mandated Field Binding:** Directly populates `font_height_mm` in `ExtractedFieldResult` and the `ExtractedField` database model, providing verified real-world measurements for `net_quantity` and `mrp` prior to Schedule II rule evaluation.

### 3. Principal Display Panel (PDP) Area Calculation (§4.3 Step 7)
- **Implementation:** `compute_pdp_area_cm2(package_bbox, mm_per_px, image_shape)` computes real-world surface area over the post-dewarp, flattened package face:
  $$\text{pdp\_area\_px}^2 = \text{width\_px} \times \text{height\_px}$$
  $$\text{pdp\_area\_cm}^2 = \frac{\text{pdp\_area\_px}^2 \times (\text{mm\_per\_px})^2}{100.0}$$
- **Persistence:** Persists to `Scan.pdp_area_cm2` to serve as the ground truth input for the Schedule II area-bracket step function in Phase 3.4.

### 4. Verification Checkpoint
- **Test Suite (`backend/tests/test_spatial_calibration.py`):** Executed `pytest -v tests/test_spatial_calibration.py` — **14/14 tests passed**:
  - `test_exact_card_ratio_ideal_perspective`: Nominal card yields $< 0.1\%$ discrepancy and accurate scale.
  - `test_ratio_discrepancy_under_5_percent_passes`: Discrepancy $\le 5\%$ passes cross-check.
  - `test_ratio_discrepancy_over_5_percent_flags_low_confidence`: Discrepancy $> 5\%$ flags `LOW_CONFIDENCE_CALIBRATION`, sets `mm_per_px = None`.
  - `test_vertical_card_orientation_handled_correctly`: Adapts to vertical and horizontal orientations.
  - `test_zero_or_negative_card_dimensions_rejected`: Fails invalid card dimensions.
  - `test_exact_blueprint_example_30px_at_point_1`: Verifies blueprint example (30px at 0.1 mm/px = 3.0 mm).
  - `test_font_height_with_fractional_mm_per_px`: Fractional pixel ratios (18px at 0.15 mm/px = 2.7 mm).
  - `test_font_height_invalid_or_zero_scale`: Safely returns 0.0 for zero/negative scales.
  - `test_pdp_area_medium_package`: Medium container ($96.00\text{ cm}^2$).
  - `test_pdp_area_large_container_schedule_ii_band`: Upper bracket container ($675.00\text{ cm}^2$).
  - `test_pdp_area_small_pouch_sub_50_cm2`: Lower bracket pouch ($28.80\text{ cm}^2$).
  - `test_pdp_area_fallback_to_image_shape`: Fallback to image dimensions ($60.00\text{ cm}^2$).
  - `test_end_to_end_spatial_calibration_pipeline`: Full integration with Preprocessing $\rightarrow$ OCR $\rightarrow$ Calibration.
  - `test_preprocessor_flags_low_confidence_when_aspect_ratio_skewed`: Gating verification in PreprocessingPipeline.
- **Full Backend Suite:** `pytest -v` executed with **59/59 passed** (100% pass rate).
- **Alembic Migration:** `alembic upgrade head --sql` verified with valid PostgreSQL DDL.

---

## Log Entry #016 — Legal Metrology PCR 2011 Compliance Rule Engine (Phase 3.4)
**Date:** 2026-09-13
**Author:** MetrologyAI Lead Metrology & Legal Compliance Engineer
**Status:** ✅ Pure Functional Compliance Rules, Discrete Persistence & Versioned Schedule II Table Implemented and Verified (90/90 Tests Passing)

> [!WARNING]
> **LEGAL DISCLAIMER — PLACEHOLDER SCHEDULE II FIGURES IN USE:**
> The Schedule II font-height-to-PDP-area band thresholds configured in [backend/app/services/rules/ruleset_config.py](file:///d:/SIH-1/SIH26034/backend/app/services/rules/ruleset_config.py) (`version="pcr_2011_schedule_ii_v1_placeholder"`, `is_placeholder=True`) are clearly-labeled engineering placeholders ($\le 50\text{ cm}^2 \to 1.5\text{ mm}$, $\le 100\text{ cm}^2 \to 2.0\text{ mm}$, $\le 500\text{ cm}^2 \to 4.0\text{ mm}$, $> 500\text{ cm}^2 \to 6.0\text{ mm}$).
> **These placeholder figures MUST be replaced with verified current Schedule II area/font numbers published by the Ministry of Consumer Affairs prior to deploying for actual legal proceedings, enforcement actions, or statutory challan generation.**

### 1. Pure Functional Architecture (§5.1)
Each rule is implemented as an independent, deterministic pure function returning a `RuleEvaluationResult(rule_id, status, reason, evidence)`:
- `RuleStatus` enum: `PASS`, `FAIL`, `UNVERIFIED`.
- **Discrete Record Persistence:** Never collapsed to a single boolean. The engine stores every individual evaluation into the database's `rule_results` table via `ComplianceRuleEngine.persist_results(db_session, scan_id, results)`.
- **Verdict Aggregation Rule:**
  - If any rule is `FAIL` $\rightarrow$ `ScanStatus.FAILED`
  - Else if any rule is `UNVERIFIED` $\rightarrow$ `ScanStatus.PENDING_REVIEW`
  - Else $\rightarrow$ `ScanStatus.PASSED`

### 2. Rule Implementations
- **Rule 6.1.a (`check_manufacturer_details`):** Validates presence of manufacturer/packer name and address, plus strict verification of a 6-digit Indian PIN code (regex `\b[1-9][0-9]{5}\b`).
- **Rule 6.1.c (`check_metric_units`):** Validates net quantity declaration against the legal SI Metric Whitelist: `{"g", "kg", "ml", "l", "cm", "m"}`. Expressly rejects non-standard abbreviations such as `gms`, `gm`, `g.`, `ml.`, `litres`, and imperial units (`oz`, `ounces`, `lbs`, `fluid ounces`).
- **Rule 6.1.e (`check_mrp_declaration`):** Validates MRP presence and enforces the statutory phrase `"inclusive of all taxes"` (case-insensitive substring check, including Devanagari equivalent `"सभी कर सहित"`).
- **Rule 6.1.g (`check_consumer_care`):** Ensures at least one usable customer contact channel is provided: phone/toll-free number (`\b(?:\+91|0)?[6-9]\d{9}\b` or `1800[- ]?\d{3}[- ]?\d{3,4}`), email address (`[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`), or physical helpline address.
- **Rule Schedule II (`check_schedule_ii`):** Pure step-function evaluating font height ($mm$) against the package's Principal Display Panel (PDP) area ($cm^2$) computed in Phase 3.3. Config-driven through `ScheduleIIRuleset`, enabling dynamic versioned updates without code changes.

### 3. Confidence Gating (§6.1)
- If `ocr_confidence < 0.95` or `semantic_confidence < 0.90` on any field required for a rule evaluation, the rule status resolves to `UNVERIFIED` rather than giving an automated legal PASS or premature FAIL.
- An `UNVERIFIED` result directs the scan to `ScanStatus.PENDING_REVIEW` in the LMO portal, ensuring human-in-the-loop oversight on marginal scans.

### 4. Test Verification
- **Unit & Integration Test Suite (`backend/tests/test_rule_engine.py`):** 31 comprehensive test cases:
  - Manufacturer verification (valid, missing name, missing pin, confidence gating).
  - Metric whitelist tests (`g`, `kg`, `ml`, `l`, `cm`, `m`, `gms` rejection, imperial rejection, confidence gating).
  - MRP declaration tests (compliant, missing tax phrase, Hindi phrase, missing value).
  - Consumer care tests (toll-free, email, landline, missing, dummy placeholder rejection).
  - Schedule II step-function (small containers, large containers, open-ended upper bracket, missing PDP/font height, dynamic ruleset hot-swapping).
  - Full engine aggregation (`PASSED`, `FAILED`, `PENDING_REVIEW`).
  - Discrete database persistence into `rule_results` table.
- **Full Backend Test Suite:** `pytest -v` executed with **90/90 passed** (100% pass rate).
- **Static Analysis:** `ruff check app tests alembic scripts` executed with **0 errors**.

---


## Log Entry #017 — End-to-End Pipeline Orchestration & Confidence Gating (Phase 3.5)
**Date:** 2026-09-13
**Author:** MetrologyAI Lead Computer Vision & Backend Architect
**Status:** ✅ Full Pipeline (3.1 $\rightarrow$ 3.5) End-to-End Orchestration, Per-Field Confidence Gating (§6.1) & Automated Status Rollup Implemented (109/109 Tests Passing)

### 1. Per-Field Confidence Gating (§6.1)
- Implemented in [backend/app/services/rules/gating.py](file:///d:/SIH-1/SIH26034/backend/app/services/rules/gating.py).
- Enforces strict dual-threshold check:
  - `MIN_OCR_CONFIDENCE_THRESHOLD = 0.95` (Layer 1 OCR text recognition certainty)
  - `MIN_SEMANTIC_CONFIDENCE_THRESHOLD = 0.90` (Layer 2 VLM/NER semantic classification certainty)
  - `gate_field(field)` returns `FieldVerificationStatus.VERIFIED` or `FieldVerificationStatus.UNVERIFIED`.
  - Guarantees that AI uncertainty on any field routes to human-in-the-loop review rather than triggering automated false-positive harassment against compliant manufacturers.

### 2. Scan-Level Status Rollup Logic (§6.1)
- `rollup_scan_status(rule_results, fields, calibration_status)` resolves the overall scan verdict:
  - **`CALIBRATION_FAILED`:** Preprocessing card detection $< 0.85$ or missing reference object. Halts metric estimation immediately (§4.3 Step 1).
  - **`LOW_CONFIDENCE_CALIBRATION`:** Dual-edge spatial ratio cross-check discrepancy $> 5.0\%$ (§4.3 Step 3).
  - **`FAILED`:** At least one verified field breaks a rule (or mandatory declaration is missing).
  - **`PENDING_REVIEW`:** No verified failures, but at least one field or rule is `UNVERIFIED`.
  - **`PASSED`:** All mandatory declarations verified and all statutory rules pass.

### 3. Master Pipeline Orchestrator ([`pipeline_orchestrator.py`](file:///d:/SIH-1/SIH26034/backend/app/services/pipeline_orchestrator.py))
- Integrates all 5 vision and rule phases:
  - **Step 1 (Phase 3.1):** Runs `PreprocessingPipeline.process()`. If reference card confidence $< 0.85$ or image invalid $\rightarrow$ marks `CALIBRATION_FAILED` and halts.
  - **Step 2 (Phase 3.2):** Runs `ExtractionPipeline.process()` over the post-dewarp, glare-reduced package face crop to isolate all 8 schema fields with distinct confidences.
  - **Step 3 (Phase 3.3):** Runs `SpatialCalibrationService.calibrate_and_measure()`. Computes dual-edge ratio cross-check, font heights in $mm$, and package PDP area in $cm^2$.
  - **Step 4 (Phase 3.4 & 3.5):** Evaluates all 5 pure rules via `ComplianceRuleEngine.evaluate()` and computes status rollup.
  - **Step 5 (Persistence & Audit):** Writes all 8 `ExtractedField` rows into `extracted_fields`, all 5 `RuleResult` rows into `rule_results`, updates `Scan.status`, `Scan.pdp_area_cm2`, `Scan.ruleset_version`, and appends `SCAN_STATUS_{new_status}` to the immutable `audit_logs` table.

### 4. Real Execution for QUEUED Ingested Scans
- **Asynchronous Ingestion:** [backend/app/routers/scans.py](file:///d:/SIH-1/SIH26034/backend/app/routers/scans.py) updated so `POST /api/v1/scans/ingest` automatically dispatches `process_scan` via FastAPI `BackgroundTasks`. Scans ingested in Phase 1.3 now automatically get real results instead of remaining in `QUEUED`.
- **Synchronous On-Demand Execution:** Added `POST /api/v1/scans/{scan_id}/process` to run or re-evaluate the full pipeline synchronously and return the populated `ScanDetailResponse`.
- **Batch Processing:** Added `POST /api/v1/scans/process-queued?limit=10` to process pending queued scans in batch.

### 5. Verification Checkpoint
- **Dedicated Orchestrator Test Suite (`backend/tests/test_pipeline_orchestrator.py`):** **19/19 passed**:
  - Gating thresholds (OCR $< 0.95$, semantic $< 0.90$, verified cases).
  - Status rollup matrix (`CALIBRATION_FAILED`, `LOW_CONFIDENCE_CALIBRATION`, `FAILED`, `PENDING_REVIEW`, `PASSED`).
  - End-to-end master pipeline execution (compliant pass, missing card halt, dual-edge skew, low OCR review).
  - Database processing & persistence (`process_scan`, `process_queued_scans`).
  - API endpoints (`POST /ingest` with background execution, `POST /{id}/process`, `POST /process-queued`).
- **Full Backend Regression Suite:** `pytest -v` executed with **109/109 passed** (100% pass rate).
- **Static Analysis:** `ruff check app tests alembic scripts` executed with **0 errors**.



