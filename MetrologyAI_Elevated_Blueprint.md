# MetrologyAI — Functional Design & Implementation Blueprint
**Problem Statement:** SIH26034 — Software System to Check Compliance of Packaged Commodities
**Focus:** Detailed Conceptual & Functional Architecture (Idea-Driven, 1:1 PS Alignment)

---

## Table of Contents
1. [System Overview & Problem Alignment](#1-system-overview--problem-alignment)
2. [Step-by-Step User Journey](#2-step-by-step-user-journey)
3. [Module 1: Multi-Modal Ingestion Engine](#3-module-1-multi-modal-ingestion-engine)
4. [Module 2: AI Extraction & Spatial Calibration](#4-module-2-ai-extraction--spatial-calibration)
5. [Module 3: PCR 2011 Compliance Matrix](#5-module-3-pcr-2011-compliance-matrix)
6. [Module 4: Evidence Security & The Trust Layer](#6-module-4-evidence-security--the-trust-layer)
7. [Module 5: Enforcement Dashboard & PDF Generation](#7-module-5-enforcement-dashboard--pdf-generation)
8. [System Architecture Flowchart](#8-system-architecture-flowchart)
9. [Technology Stack](#9-technology-stack)
10. [API Contract Summary](#10-api-contract-summary)
11. [Data Schema Design](#11-data-schema-design)
12. [Security & Access Control](#12-security--access-control)
13. [Deployment & Scaling Architecture](#13-deployment--scaling-architecture)

---

## 1. System Overview & Problem Alignment

The Ministry of Consumer Affairs requires an automated solution to replace manual, time-consuming field inspections. Currently, Legal Metrology Officers (LMOs) manually inspect packages using physical calipers to measure font sizes and memory to recall complex PCR 2011 rules.

**MetrologyAI** translates this manual process into a deterministic digital pipeline. The system uses AI strictly as a "reader" (to extract text) and relies on hard-coded mathematical rules (to measure font size) and legal logic (to judge compliance). This ensures the system is legally defensible, perfectly aligned with the Legal Metrology (Packaged Commodities) Rules, 2011, and free from AI hallucinations.

---

## 2. Step-by-Step User Journey

To understand how the modules interact, here is the exact chronological workflow of the primary user: the Legal Metrology Officer (LMO).

### Phase 1: Capture
1. **Initiation:** The LMO enters a retail store, identifies a packaged commodity (e.g., a packet of biscuits), and opens the MetrologyAI Mobile App.
2. **Alignment:** The app displays an AR (Augmented Reality) guide on the screen. The LMO places a standard reference object (like a debit card or ID) next to the packet and aligns them within the guide.
3. **Trigger:** The LMO takes the photo. The app captures the high-resolution image, locks the GPS coordinates, and records the UTC timestamp.

### Phase 2: Processing (The Cloud/Edge)
4. **Clarification:** The system automatically flattens curved surfaces (like bottles) and removes glare using mathematical preprocessing.
5. **Extraction:** The AI vision models scan the image, drawing bounding boxes around all text, and semantically tags them (e.g., identifying "₹ 50" as the MRP).
6. **Calibration:** The system calculates the physical size of the font in millimeters by comparing the text pixels to the known pixels of the reference card.

### Phase 3: Enforcement & Action
7. **Rule Evaluation:** The extracted data is passed through the PCR 2011 Rule Engine. The system checks if the font size matches the required Schedule II limits and if all mandatory declarations exist.
8. **Dashboard Review:** If a violation is flagged, the scan appears on the LMO Web Dashboard in the "Pending Review" queue. The LMO sees the image with red boxes highlighting the exact violation.
9. **Final Output:** The LMO clicks "Generate Challan", and the system instantly produces a legally binding Section 39 PDF notice containing the photo, GPS data, and a cryptographic tamper-proof seal.

### 2.1 Implementation Trace — What Actually Happens at Each Step

This is the same journey, but walked through as system events rather than user actions, including the failure branches your original flow doesn't cover.

| Step | User sees | System does | Failure path |
|---|---|---|---|
| 1–2 | AR overlay with a card-shaped guide box | Camera preview stream runs client-side edge detection (OpenCV.js/MediaPipe on-device) to detect a rectangular card-like object in frame and turns the guide box green when found | If no rectangular object is detected within N seconds, guide box stays red and app shows "Place reference card in frame" — capture button stays disabled |
| 3 | Shutter animation, "Uploading..." or "Saved for later" toast | App writes image to local `captures` table (SQLite) immediately, tags it `status: PENDING_UPLOAD`, attempts upload | If no network: image stays local, a background `WorkManager` (Android) / `BackgroundTasks` (iOS) job retries every sync interval |
| 4–6 | (invisible to LMO — happens server-side) | Celery worker picks job off Redis queue → runs dewarp/CLAHE (OpenCV) → runs YOLOv8 to isolate package face + card → runs PaddleOCR → runs Florence-2 for semantic mapping → computes mm/px ratio → computes font heights + PDP area | If YOLOv8 confidence for card detection < threshold: job is marked `CALIBRATION_FAILED`, image is NOT auto-scored, routed straight to human review with a note "no reference object detected — measurements unavailable" |
| 7 | (invisible) | Structured JSON passed to rule engine; each PCR rule evaluated independently and stored as a discrete pass/fail record, not a single boolean | If OCR confidence for a required field < 95%: that specific field is marked `UNVERIFIED`, not `FAILED` — see §6.1 |
| 8 | Dashboard queue entry with thumbnail, violation tags | Backend writes a `violations` row per broken rule, links to the `scan_id`, renders bounding box overlay by storing box coordinates (not a burned-in image) so the frontend draws them on top of the original — keeps the original image evidentiary-pure | — |
| 9 | PDF download / share sheet | ReportLab renders challan from a template, embeds the *original* untouched image plus a separately rendered annotated crop, computes final hash of the PDF bytes themselves (a second, PDF-level hash — distinct from the ingestion-time image hash) | If any required field for the challan (LMO ID, rule text, GPS) is null, generation is blocked with an explicit "incomplete record" error rather than emitting a partially-filled legal document |

---

## 3. Module 1: Multi-Modal Ingestion Engine

According to the problem statement, the system must handle both "packaged commodity labels" and "product listings" (e-commerce).

### Functional Capabilities:
* **Mobile App (Physical Products):** A Flutter-based app designed for LMOs and the public. It utilizes the device's native camera for lossless image capture.
* **Offline-First SQLite Queuing:** Rural retail stores often lack 4G/5G internet. If the LMO is offline, the app securely queues the photos in a local SQLite database. Once internet is restored, a background worker automatically pushes the queue to the central server.
* **Web Portal (E-Commerce Listings):** A Next.js web portal allowing LMOs to drag-and-drop screenshots of online products (e.g., Blinkit, Amazon). Because online screenshots lack physical dimension, the system provides a manual input field to declare the product's physical size, allowing the rule engine to calculate compliance dynamically.

### 3.1 Offline Queue — Implementation Detail

Local SQLite table (`sqflite`) on the Flutter app:

```
captures(
  local_id TEXT PRIMARY KEY,       -- UUID generated on-device
  image_path TEXT,                 -- local filesystem path
  lat REAL, lng REAL,
  captured_at_utc TEXT,
  reference_object_type TEXT,      -- 'debit_card' | 'pan_card' | 'manual'
  sync_status TEXT,                -- PENDING_UPLOAD | UPLOADING | SYNCED | FAILED
  retry_count INTEGER DEFAULT 0,
  server_scan_id TEXT NULL         -- populated once server ACKs
)
```

Sync worker logic (pseudo-code):
```
on connectivity_restored OR every 15 min:
    batch = select * from captures where sync_status in ('PENDING_UPLOAD','FAILED') limit 10
    for capture in batch:
        set sync_status = 'UPLOADING'
        try:
            response = POST /api/v1/scans/ingest (multipart image + metadata)
            set sync_status = 'SYNCED', server_scan_id = response.scan_id
            delete local image_path (server now source of truth)
        except NetworkError:
            set sync_status = 'FAILED', retry_count += 1
            if retry_count > 10: notify_user("photo stuck, check manually")
```

This keeps the LMO's flow non-blocking: they can keep shooting products even with zero connectivity, and nothing is lost if the app is killed mid-sync because state lives in SQLite, not memory.

### 3.2 E-Commerce Manual Dimension Input

Since a screenshot carries no physical scale, the web portal form captures:
- Declared net quantity (as printed on listing)
- A manually entered package dimension (LMO measures a physical retail sample once, or pulls it from the manufacturer's own declared dimensions if available)
- This manual value substitutes for the "reference card ratio" step in the calibration pipeline — the rest of the pipeline (font-height-to-mm conversion, rule evaluation) is unchanged, so Module 2 and Module 3 don't need a separate code path, just a different calibration input source.

---

## 4. Module 2: AI Extraction & Spatial Calibration

This module directly addresses the PS requirement for "Extraction of declarations from labels" and "Font size and readability analysis."

### 4.1 The Vision Extractors
We do not train a monolithic AI that guesses compliance. We orchestrate two highly specialized models:
1. **PaddleOCR:** A state-of-the-art optical character recognition engine. It identifies where the text is (bounding boxes) and reads the strings (English/Hindi).
2. **Florence-2 VLM (Semantic Mapping):** A Vision-Language Model that understands context. It takes the raw strings from PaddleOCR and maps them to Legal Metrology categories (e.g., realizing that "Packed on 12/2025" is the Manufacturing Date).

### 4.2 Spatial Calibration (The "Virtual Calipers")
To check "font size requirements," the system must measure in millimeters (mm), but cameras only see pixels.
* **The Reference Concept:** The user places an ISO/IEC 7810 card (like a PAN or Debit card, which is universally 85.60mm × 53.98mm) in the photo.
* **The Math:** The system detects the card and calculates the **mm-to-pixel ratio**. For example, if the card is 539 pixels tall, the ratio is `53.98mm / 539px = 0.1mm per pixel`.
* **The Measurement:** The system then measures the height of the Net Quantity font in pixels. If it is 30 pixels tall, it multiplies `30 * 0.1` to confidently declare the font is exactly `3.0 mm` tall in the real world.
* **The Area:** Using the same ratio, it calculates the total Principal Display Panel (PDP) area in square centimeters ($cm^2$), which dictates the legal font size requirement.

### 4.3 Pipeline Implementation Order & Failure Handling

```
1. YOLOv8 pass over raw image
   -> detects: [package_face_bbox, reference_card_bbox]
   -> if reference_card_bbox missing or confidence < 0.85:
        mark scan CALIBRATION_FAILED, skip to human review, DO NOT estimate mm from assumptions

2. OpenCV preprocessing (only if calibration succeeded)
   -> perspective correction on card corners (cv2.getPerspectiveTransform)
   -> cylindrical dewarp on package_face_bbox if aspect ratio / curvature heuristic
      suggests a bottle/can (not a flat box)
   -> CLAHE contrast pass to reduce glare/foil reflection

3. Ratio computation
   card_height_px = measured long edge of detected card in px
   mm_per_px = 53.98 / card_height_px   # using short edge; long edge = 85.60mm as cross-check
   -- cross-check: if long-edge-derived ratio and short-edge-derived ratio
      disagree by > 5%, flag LOW_CONFIDENCE_CALIBRATION (likely card was
      photographed at an angle despite the corrected perspective)

4. PaddleOCR over package_face_bbox (post-dewarp)
   -> returns [{text, bbox, confidence, lang}]

5. Florence-2 semantic mapping
   -> prompt-driven zero-shot NER over PaddleOCR output, not over raw pixels
   -> maps strings to schema fields: {net_quantity, mrp, mfg_date, manufacturer_name,
      manufacturer_address, pincode, consumer_care, unit}
   -> each mapped field carries its own confidence score, independent of OCR confidence
      (OCR can be 99% sure of the string "50" while Florence-2 is only 60% sure
      it means MRP vs. a batch number — both scores are kept, not merged)

6. Font height computation
   for each mapped field with a legally mandated minimum font size (Net Qty, MRP):
       font_height_px = bbox_height of that field's text run
       font_height_mm = font_height_px * mm_per_px

7. PDP area computation
   pdp_area_px2 = area of package_face_bbox (post-dewarp, so it approximates
                  the flattened real surface, not the foreshortened camera view)
   pdp_area_cm2 = pdp_area_px2 * (mm_per_px^2) / 100
```

Every numeric output of this pipeline (`mm_per_px`, `font_height_mm`, `pdp_area_cm2`, every OCR/Florence-2 confidence score) is persisted alongside the verdict — not just the final pass/fail — so a legal challenge can be answered with the exact intermediate math, not just "the AI said so."

---

## 5. Module 3: PCR 2011 Compliance Matrix

This is the deterministic "brain" of the system. It strictly enforces the Legal Metrology (Packaged Commodities) Rules, 2011.

| Legal Rule | Functional Check Performed by System | Failure Trigger / Non-Compliance |
| :--- | :--- | :--- |
| **Rule 6(1)(a): Manufacturer Details** | Scans for a recognizable company name and validates the presence of an address. Uses Regex to ensure a valid 6-digit Indian PIN code exists. | Missing Manufacturer Name OR Missing 6-digit PIN code. |
| **Rule 6(1)(c): Standard Metric Units** | Identifies the Net Quantity unit and normalizes it. Checks against the legal metric whitelist (g, kg, ml, L, cm, m). | Use of non-standard units (e.g., "gms", "ounces", "lbs"). |
| **Rule 6(1)(e): MRP Declaration** | Extracts the price string. Performs a strict substring match for the mandatory phrase "inclusive of all taxes". | MRP is missing entirely, or lacks the exact phrase "inclusive of all taxes". |
| **Rule 6(1)(g): Consumer Care Details** | Scans the label for contact vectors (Phone Numbers, Email Addresses, or specific Customer Care P.O. Boxes). | No valid contact mechanism found for consumer grievances. |
| **Schedule II: Font Height vs PDP Area** | Compares the calculated PDP Area ($cm^2$) to the calculated Font Height ($mm$). Applies the legal step-function logic (e.g., if Area > 500 $cm^2$, font must be $\ge 4.0mm$). | Font height in mm is mathematically smaller than the mandated Schedule II minimum. |

### 5.1 Rule Engine — Implementation Pattern

Every rule is implemented as an independent, pure function against the structured JSON, not a monolithic if/else block — this is what makes the system auditable and lets one rule be corrected (e.g., a Schedule II band amendment) without touching the others.

```
RuleResult = { rule_id, status: PASS | FAIL | UNVERIFIED, evidence, reason }

def check_manufacturer_details(fields):
    if not fields.manufacturer_name.value:
        return FAIL("no manufacturer name detected")
    if fields.manufacturer_name.confidence < 0.95:
        return UNVERIFIED("name detected but low OCR confidence, needs human check")
    if not regex_match(r"\d{6}", fields.address.value):
        return FAIL("no valid 6-digit PIN code in address")
    return PASS()

def check_mrp_declaration(fields):
    if not fields.mrp.value:
        return FAIL("MRP missing")
    if "inclusive of all taxes" not in normalize(fields.mrp.raw_text):
        return FAIL("MRP present but missing mandatory tax-inclusive phrase")
    return PASS()

def check_schedule_ii(font_height_mm, pdp_area_cm2, ruleset):
    # ruleset is a config-driven table, NOT hardcoded, e.g.:
    # [{max_area_cm2: 100, min_font_mm: 1.0},
    #  {max_area_cm2: 500, min_font_mm: 2.0},
    #  {max_area_cm2: None, min_font_mm: 4.0}]   <-- VERIFY EXACT BANDS AGAINST
    #                                                CURRENT PCR 2011 SCHEDULE II
    #                                                BEFORE PRODUCTION USE
    band = first band where pdp_area_cm2 <= band.max_area_cm2 (or last band if None)
    if font_height_mm < band.min_font_mm:
        return FAIL(f"font {font_height_mm}mm < required {band.min_font_mm}mm for {pdp_area_cm2}cm^2")
    return PASS()

def evaluate_scan(scan):
    results = [check_manufacturer_details(scan.fields),
               check_units(scan.fields),
               check_mrp_declaration(scan.fields),
               check_consumer_care(scan.fields),
               check_schedule_ii(scan.font_height_mm, scan.pdp_area_cm2, ACTIVE_RULESET)]
    scan.verdict = FAIL if any(r.status == FAIL for r in results) else \
                   PENDING_REVIEW if any(r.status == UNVERIFIED for r in results) else PASS
    persist(results)   # every individual rule result stored, not just the final verdict
```

Keeping the Schedule II bands in a config table (versioned, timestamped) rather than inline code means a regulatory amendment is a data change, not a code deploy — and every past challan still points to the ruleset version that was active when it was generated, which matters if a manufacturer contests it later.

---

## 6. Module 4: Evidence Security & The Trust Layer

If the system flags a violation, the evidence must hold up in a court of law against massive FMCG corporations.

### 6.1 Confidence Gating (Human-in-the-Loop)

AI is not perfect. If the OCR confidence score for a label is below 95%, the system will **not** automatically fail the product. Instead, it flags the product as `PENDING_REVIEW` and routes it to a human LMO on the dashboard, preventing false-positive harassment of compliant manufacturers.

Implementation: confidence gating happens **per field**, not per scan — a scan can have MRP verified at 99% confidence and manufacturer address at 80% simultaneously.

```
def gate_field(field):
    if field.ocr_confidence < 0.95 or field.semantic_confidence < 0.90:
        return UNVERIFIED
    return VERIFIED

# A scan's overall status is:
#   FAILED        -> at least one VERIFIED field breaks a rule
#   PENDING_REVIEW -> no VERIFIED failures, but at least one field UNVERIFIED
#   PASSED        -> all mandatory fields VERIFIED and all rules pass
```

This means a human never has to review a compliant, high-confidence scan (keeps the review queue small and focused), but nothing is auto-failed on shaky OCR — the two failure modes (false negatives on the LMO's time, false positives on the manufacturer) are handled by two separate thresholds rather than one blended confidence score.

### 6.2 Section 65B Cryptographic Vault

Under Section 65B of the Indian Evidence Act, digital photos can be challenged as tampered or photoshopped.
* At the exact millisecond a photo is ingested, the system generates a **SHA-256 Cryptographic Hash**.
* This hash mathematically binds the image pixels, the GPS coordinates, and the UTC timestamp together.
* If a manufacturer claims the photo was altered, the hash will change, instantly proving whether the evidence is pristine.

**Implementation detail on the binding:** the hash is not just `sha256(image_bytes)` — it's computed over a canonical, ordered concatenation so that GPS/timestamp tampering is caught even if the image bytes are untouched:

```
canonical_payload = image_bytes + b"|" + str(lat).encode() + b"|" + str(lng).encode()
                     + b"|" + captured_at_utc.isoformat().encode() + b"|" + device_id.encode()
evidence_hash = sha256(canonical_payload).hexdigest()
```

This hash is stored server-side at ingestion time and re-derivable at any later point from the immutable original — if anyone (including an MetrologyAI admin) edits the stored image, GPS, or timestamp, recomputing the hash produces a different value, which is the actual evidentiary claim under Section 65B (a certificate of authenticity, not just "we hashed it once").

---

## 7. Module 5: Enforcement Dashboard & PDF Generation

Addressing the PS requirement for "Generating compliance reports" and "Providing dashboards for enforcement officials."

### 7.1 The LMO Admin Dashboard

A web-based control center built for the Director of Legal Metrology and field LMOs.
* **GIS Spatial Map:** A live interactive heatmap of India. Red dots show where non-compliant products were scanned; green dots show compliant scans. This helps officials identify if a manufacturer is dumping non-compliant batches in specific rural districts.
* **Digital Repository:** A search interface where officials can type a barcode or brand name (e.g., "Parle-G") to pull up the complete historical compliance rating of that product nationwide.
* **Human Review Queue:** The interface where LMOs manually verify borderline scans.

Implementation note: the heatmap is a PostGIS `ST_ClusterKMeans` or `ST_SnapToGrid` aggregation query run server-side (not client-side clustering of raw points), because plotting millions of raw GPS points in-browser doesn't scale past a few thousand markers — the map tile layer requests pre-aggregated cluster counts per zoom level.

### 7.2 Section 39 Auto-Challan PDF Generator

When a violation is confirmed, the system completely automates the paperwork.
* The LMO clicks "Generate Report".
* The system injects the official Government Header, the captured image (with red bounding boxes highlighting the exact violation), the specific PCR 2011 rule broken, the GPS location, and the Section 65B security hash into an A4 PDF document.
* This document serves as the official compounding notice under Section 39 of the Legal Metrology Act, 2009.

Implementation note: bounding boxes are drawn onto a **rendered copy** at PDF-generation time (ReportLab draws the rectangle as a vector overlay on the placed image), while the original ingested image bytes — the ones the Section 65B hash was computed against — are stored untouched and separately attached/referenced in the PDF. This preserves the chain of custody: the annotated view is for human legibility, the original is what the hash and any forensic check refers to.

---

## 8. System Architecture Flowchart

```text
==========================================================================================
                              METROLOGYAI: FUNCTIONAL SYSTEM ARCHITECTURE
==========================================================================================

[ 1. CAPTURE & INGESTION ]
   ├── A. Field Mobile App (LMO)           ──► High-Res Photo + GPS + Reference Card
   └── B. Web Portal (Admin)               ──► Upload E-Commerce Screenshots / Labels
            │
            ▼ (Secure Upload Queue)
[ 2. VISION PRE-PROCESSING ]
   ├── Glare & Blur Check (Quality Gate)   ──► Rejects unusable photos instantly
   └── Cylindrical Dewarping (Math)        ──► Flattens curved bottles/cans digitally
            │
            ▼ (Optically Corrected Image)
[ 3. AI EXTRACTION & CALIBRATION ]
   ├── PaddleOCR (Text Reader)             ──► Extracts English/Hindi text & Bounding Boxes
   ├── Florence-2 VLM (Context Mapping)    ──► Maps raw strings to schema (e.g., MRP: ₹50)
   └── Spatial Math (Virtual Calipers)     ──► Uses Reference Card to convert pixels -> mm
            │
            ▼ (Structured JSON: {Net_Qty: 100g, Font_Height: 3.2mm, Area: 200cm²})
[ 4. PCR 2011 RULE ENGINE (DETERMINISTIC) ]
   ├── Rule 6(1)(a) Check                  ──► Validates Manufacturer Name & 6-Digit PIN
   ├── Rule 6(1)(c) & (e) Check            ──► Validates Metric Units & MRP "Inclusive of taxes"
   └── Schedule II Validation              ──► Checks if Font Height is legal for the PDP Area
            │
            ▼ (Compliance Verdict: PASSED / FAILED)
[ 5. TRUST & LEGAL OUTPUT LAYER ]
   ├── Confidence Gate (< 95%)             ──► Routes borderline AI scans to Human LMO for review
   ├── Section 65B Hash Vault              ──► Cryptographically seals image + GPS + Timestamp
   ├── Section 39 Notice Generator         ──► Auto-compiles PDF Challan for violations
   └── PostGIS Enforcement Dashboard       ──► Plots violations on Live Interactive Map of India
```

---

## 9. Technology Stack

To achieve this deterministic, highly accurate, and legally defensible architecture, we carefully selected a modern, open-source technology stack. We deliberately avoided "black-box" cloud AI (like OpenAI) to ensure data sovereignty and predictable mathematical outcomes.

### 9.1 Frontend & Mobile Edge (The Capture Layer)
* **Flutter (Mobile App):** Chosen for its cross-platform capability (iOS/Android) from a single codebase. It provides deep access to the Camera2 API for lossless, uncompressed image capture required for sub-millimeter OCR accuracy.
* **SQLite (Local Database):** Integrated via Flutter's `sqflite` to enable **Offline-First Resilience**. If an LMO is in a rural basement with no 4G, photos queue locally and sync later.
* **Next.js & React (Admin Dashboard):** Chosen for Server-Side Rendering (SSR) performance and deep integration with modern mapping libraries for the central GIS enforcement dashboard.

### 9.2 Vision & AI Engines (The Extraction Layer)
* **YOLOv8:** Fast, lightweight object detection. It instantly isolates the primary packaging face and the ISO reference card from noisy backgrounds.
* **PaddleOCR:** A highly accurate multilingual OCR engine capable of detecting non-linear bounding boxes (curved text) and reading both English and Hindi scripts perfectly.
* **Florence-2 VLM (Microsoft):** A state-of-the-art Vision-Language Model. Used purely for Zero-Shot Semantic NER (Named Entity Recognition) to map unstructured PaddleOCR strings into structured Legal Metrology schema fields (e.g., mapping `"100g"` to `Net_Quantity`).
* **OpenCV:** Essential for the mathematical geometry pipeline (Cylindrical Dewarping and CLAHE contrast equalization) to defeat curved bottle distortion and shiny foil glare before AI extraction.

### 9.3 Backend API & Database (The Logic & Persistence Layer)
* **Python FastAPI:** The backend engine. Chosen because it natively supports asynchronous I/O (perfect for handling thousands of concurrent image uploads from LMOs) and integrates seamlessly with our Python-based AI models.
* **PostgreSQL 15:** The primary relational database ensuring ACID compliance for the massive product repository.
* **PostGIS Extension:** Allows PostgreSQL to natively store `GEOMETRY(POINT)` data. This is critical for instantly querying and clustering millions of violation GPS coordinates onto the live National Heatmap.
* **Celery & Redis:** Used as an asynchronous task queue. AI vision processing is heavy; Celery ensures the API never blocks while processing an image.
* **ReportLab & Hashlib (Trust Layer):** Used for auto-generating the legally-binding Section 39 PDF Challans and computing the Section 65B SHA-256 cryptographic hashes for court admissibility.

---

## 10. API Contract Summary

A minimal but complete surface — enough to demonstrate the pipeline end-to-end for a hackathon judge without over-engineering.

| Endpoint | Method | Purpose | Key request fields | Key response fields |
|---|---|---|---|---|
| `/api/v1/scans/ingest` | POST | Mobile/web upload of a raw capture | multipart image, lat, lng, captured_at_utc, device_id, reference_object_type | scan_id, status: QUEUED |
| `/api/v1/scans/{scan_id}` | GET | Poll/fetch scan status + results | — | status, fields{}, rule_results[], verdict |
| `/api/v1/scans/{scan_id}/review` | POST | LMO submits manual verdict on a PENDING_REVIEW scan | reviewer_id, overridden_fields{}, decision | updated verdict |
| `/api/v1/challans/generate` | POST | Generate Section 39 PDF for a failed scan | scan_id, lmo_id | challan_id, pdf_url, pdf_hash |
| `/api/v1/dashboard/heatmap` | GET | Aggregated GIS points for map rendering | bbox, zoom | clustered points [{lat,lng,count,severity}] |
| `/api/v1/products/search` | GET | Digital repository lookup by brand/barcode | query | product history, past scans, verdict trend |
| `/api/v1/ecommerce/ingest` | POST | Web portal e-commerce screenshot + manual dimensions | image, declared_dimensions, platform | scan_id |

---

## 11. Data Schema Design

### 11.1 PostgreSQL — Core Tables (server, source of truth)

```
scans(
  scan_id UUID PRIMARY KEY,
  source TEXT,                     -- 'mobile' | 'ecommerce'
  image_url TEXT,                  -- immutable original, object storage reference
  evidence_hash TEXT,               -- Section 65B hash
  lat DOUBLE PRECISION, lng DOUBLE PRECISION,
  location GEOMETRY(POINT, 4326),  -- PostGIS, derived from lat/lng via trigger
  captured_at_utc TIMESTAMPTZ,
  mm_per_px REAL,
  pdp_area_cm2 REAL,
  status TEXT,                     -- PASSED | FAILED | PENDING_REVIEW | CALIBRATION_FAILED
  ruleset_version TEXT,             -- which Schedule II config was active
  created_at TIMESTAMPTZ
)

extracted_fields(
  id UUID PRIMARY KEY,
  scan_id UUID REFERENCES scans,
  field_name TEXT,                  -- net_quantity, mrp, manufacturer_name, etc.
  raw_text TEXT,
  bbox JSONB,
  ocr_confidence REAL,
  semantic_confidence REAL,
  font_height_mm REAL NULL
)

rule_results(
  id UUID PRIMARY KEY,
  scan_id UUID REFERENCES scans,
  rule_id TEXT,                     -- '6.1.a', '6.1.c', 'schedule_ii', etc.
  status TEXT,                      -- PASS | FAIL | UNVERIFIED
  reason TEXT,
  evidence JSONB
)

challans(
  challan_id UUID PRIMARY KEY,
  scan_id UUID REFERENCES scans,
  lmo_id UUID,
  pdf_url TEXT,
  pdf_hash TEXT,
  generated_at TIMESTAMPTZ
)
```

### 11.2 SQLite — Local Offline Queue (device only, transient)

See §3.1 `captures` table. Rows are deleted once `SYNCED` and the server has an object-storage copy — the device is never the long-term evidence store.

---

## 12. Security & Access Control

* **Authentication:** JWT-based auth for both the mobile app and dashboard, issued via a central auth service. LMOs authenticate with government-issued credentials (integration point for an existing state/central SSO if available — flagged as an external dependency, not something MetrologyAI builds itself).
* **Authorization (RBAC):** Three roles minimum — `field_lmo` (can capture, cannot generate challans or edit rulesets), `senior_lmo` (can review PENDING_REVIEW queue and generate challans), `admin` (can edit the Schedule II ruleset config, view national heatmap, manage users). Rule-of-thumb: nobody who can capture evidence should also be able to silently edit its verdict — capture and adjudication are separated roles.
* **Evidence immutability:** Original images are written to object storage (e.g., S3-compatible bucket) with object-lock/WORM (write-once-read-many) semantics where the provider supports it, so even an admin account cannot silently overwrite the bytes the Section 65B hash was computed against.
* **Transport security:** TLS everywhere; the mobile app pins the API certificate to prevent MITM tampering of uploads in transit, which matters specifically because upload integrity feeds directly into the evidentiary hash chain.
* **Audit log:** Every status-changing action (review override, challan generation, ruleset edit) is written to an append-only audit table with actor ID and timestamp — separate from the compliance data itself, so "who changed what" is answerable independent of "what does the evidence say."

---

## 13. Deployment & Scaling Architecture

* **Containerization:** FastAPI backend, Celery workers, and the Next.js dashboard each run as separate Docker containers, orchestrated via Kubernetes (or Docker Compose for a hackathon-scale demo — K8s is the production-scale answer, Compose is the honest answer for a 36-hour build).
* **Worker scaling:** Celery workers that run the AI pipeline (YOLOv8 + PaddleOCR + Florence-2) are GPU-bound and are scaled independently from the lightweight API/web containers — typically 1 GPU worker pod can handle a queue depth proportional to its inference latency (e.g., if end-to-end inference is ~3s/image, one worker clears ~1,200 images/hour; queue depth and worker count scale together via Redis queue length as the autoscaling signal).
* **Storage sizing (illustrative, not a commitment):** a high-res capture at ~5MB average, at a rate of e.g. 50,000 scans/day nationally, is ~250GB/day of raw image storage — this is the number that should drive the object storage tier choice (hot storage for recent/active review-queue images, cold/cheaper storage for the historical evidence archive once a challan is finalized).
* **Database:** PostgreSQL run as a managed instance (RDS/Cloud SQL-equivalent) with a read replica for the dashboard's heavy read queries (heatmap aggregation, repository search) so those don't contend with the write-heavy ingestion path.
* **CDN:** Dashboard static assets and generated challan PDFs served through a CDN; the raw evidentiary images are NOT CDN-cached (to keep a single controlled access path consistent with the chain-of-custody requirement in §12).

