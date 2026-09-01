# MetrologyAI — Mobile App & Web Dashboard: UX Flow & Integration Blueprint
**Companion to:** MetrologyAI Elevated Blueprint
**Focus:** Screen-by-screen design of both surfaces, and the exact points where they must talk to each other

---

## Table of Contents
1. [Why Two Surfaces, One System](#1-why-two-surfaces-one-system)
2. [Mobile App — Screen Inventory & Flow](#2-mobile-app--screen-inventory--flow)
3. [Web Dashboard — Screen Inventory & Flow](#3-web-dashboard--screen-inventory--flow)
4. [Key Screen Layout Sketches](#4-key-screen-layout-sketches)
5. [Integration Scenarios — Where Mobile and Web Must Connect](#5-integration-scenarios--where-mobile-and-web-must-connect)
6. [Integration Architecture](#6-integration-architecture)
7. [Build Order Recommendation](#7-build-order-recommendation)

---

## 1. Why Two Surfaces, One System

The mobile app is the **capture and field-status surface** — an LMO uses it standing in a shop, often on bad connectivity, doing one thing: get evidence, know its status. The web dashboard is the **review, decision, and command surface** — used at a desk, doing everything the phone shouldn't try to do: reviewing borderline cases, generating legal PDFs, viewing the national map, managing rulesets and users.

They are not two separate products with a shared logo — they are two views into the same `scans` table (§11 of the main blueprint), and the integration work is really about **keeping both views honest about the same underlying state in near-real-time**, not about moving data between two databases.

---

## 2. Mobile App — Screen Inventory & Flow

| # | Screen | Primary purpose | Key elements |
|---|---|---|---|
| 1 | **Login** | Auth via LMO government credential | ID/OTP or SSO button, offline-mode notice if no network |
| 2 | **Home / Today's Scans** | Landing screen after login | List of today's captures with sync status chips (Synced / Pending / Failed), big "New Scan" button |
| 3 | **Capture (AR guide)** | Core action screen | Live camera preview, guide overlay box for reference card, shutter button (disabled until card detected — §2.1 of main blueprint), toggle for product type (flat box / bottle / e-commerce manual mode) |
| 4 | **Review Before Upload** | Quick self-check before committing | Captured photo, "retake" vs "confirm" — no AI processing shown here, this is just a framing check, not a compliance check |
| 5 | **Scan Detail (mobile, read-only)** | Check status of one past scan | Thumbnail, status (Passed / Failed / Pending Review / Calibration Failed), if Failed: which rule(s), a "View full report" deep link that opens the web dashboard's scan detail in a mobile browser (mobile app does NOT reimplement the annotated-image/report view — see §5.2) |
| 6 | **Sync Queue** | Visibility into offline queue | List of PENDING_UPLOAD / FAILED captures, manual "retry now" action, storage usage indicator |
| 7 | **Notifications** | Pushed updates | "Your scan at [store] was marked Failed — Rule 6(1)(e)", "3 scans in your queue synced successfully" |
| 8 | **Profile / Settings** | LMO identity, jurisdiction, app config | LMO ID, assigned district/zone, data-usage settings (Wi-Fi only sync toggle — important for rural data costs), app version |

**Flow shape:** Login → Home → Capture → (auto) Review Before Upload → back to Home with a new Pending row → (later) push notification updates that row's status in place.

---

## 3. Web Dashboard — Screen Inventory & Flow

| # | Screen | Primary purpose | Key elements |
|---|---|---|---|
| 1 | **Login** | Auth for senior LMOs / admins | Same auth backend as mobile — see §6.1 |
| 2 | **Overview** | Landing screen | National heatmap (§7.1 of main blueprint), today's counts (scanned / passed / failed / pending review), a shortcut into the Review Queue |
| 3 | **Review Queue** | The core work surface for senior LMOs | Sortable/filterable list of PENDING_REVIEW scans (by district, by confidence gap, by age), bulk-select isn't recommended — each review is a legal judgment call, so it stays one-at-a-time |
| 4 | **Scan Detail** | Full inspection of one scan | Full-res image with bounding boxes drawn per extracted field, per-rule pass/fail table, editable field overrides (with mandatory reviewer note), "Generate Challan" button (enabled only once verdict is FAILED and no fields remain UNVERIFIED) |
| 5 | **E-Commerce Ingestion** | Manual upload path (§3.2 of main blueprint) | Drag-and-drop screenshot, manual dimension input form, platform tag (Blinkit/Amazon/etc.), submits into the same pipeline as mobile scans from Module 3 onward |
| 6 | **Digital Repository / Product Search** | Historical compliance lookup | Search by brand/barcode, timeline of past scans for that product across the country, trend indicator (improving/worsening compliance) |
| 7 | **Challan Archive** | All generated Section 39 notices | Searchable list, re-download PDF, shows pdf_hash for verification |
| 8 | **Admin: Ruleset Config** | Edit the Schedule II bands and rule thresholds (§5.1 of main blueprint) | Versioned config editor, "Save as new version" (never overwrites a version a past challan referenced), effective-date field |
| 9 | **Admin: User Management** | RBAC (§12 of main blueprint) | Assign field_lmo / senior_lmo / admin roles, assign district/zone |
| 10 | **Audit Log** | Read-only trail | Who reviewed/overrode what, when — separate from compliance data per §12 |

**Flow shape:** Login → Overview → Review Queue → Scan Detail → (decision) → Generate Challan, with Product Search and Admin screens as side branches off the main nav, not part of the linear flow.

---

## 4. Key Screen Layout Sketches

Text-based layout sketches — enough to hand to a designer or build against directly, not final visual design.

### 4.1 Mobile — Capture Screen

```
┌─────────────────────────────┐
│ ← Back            [⚡ Flash] │
│                              │
│   ┌─────────────────────┐   │
│   │                     │   │
│   │   [ live camera ]   │   │
│   │                     │   │
│   │  ┌───────────┐      │   │  <- reference card guide box
│   │  │  card here │      │   │     turns GREEN when detected
│   │  └───────────┘      │   │
│   │                     │   │
│   └─────────────────────┘   │
│                              │
│  Product type:               │
│  ( Box )  ( Bottle )  ( Manual )
│                              │
│         ┌──────┐            │
│         │  ●   │  <- shutter, disabled/grey
│         └──────┘     until card detected
│                              │
│  "Place a debit/PAN card     │
│   next to the product"       │
└─────────────────────────────┘
```

### 4.2 Web — Review Queue

```
┌──────────────────────────────────────────────────────────┐
│ MetrologyAI Dashboard          [Overview] [Review Queue*] │
│                                  [Repository] [Admin]  👤  │
├──────────────────────────────────────────────────────────┤
│ Filter: [District ▾] [Confidence ▾] [Age ▾]     [Search] │
├──────────────────────────────────────────────────────────┤
│ 🖼  Parle-G 100g        Chennai, TN     2h ago   [Review]│
│ 🖼  Amul Butter 500g    Coimbatore      5h ago   [Review]│
│ 🖼  Maggi Noodles 70g   Madurai         1d ago   [Review]│
│ ...                                                       │
└──────────────────────────────────────────────────────────┘
```

### 4.3 Web — Scan Detail

```
┌──────────────────────────────────────────────────────────┐
│  ← Back to Queue                                          │
├───────────────────────────────┬────────────────────────────┤
│                                │  Rule Results              │
│   [ image with red boxes ]    │  ✅ 6(1)(a) Manufacturer    │
│   drawn over extracted        │  ✅ 6(1)(c) Units           │
│   field bounding boxes         │  ❌ 6(1)(e) MRP tax phrase  │
│                                │  ✅ 6(1)(g) Consumer care   │
│                                │  ❌ Schedule II font/area   │
├───────────────────────────────┴────────────────────────────┤
│  Extracted Fields (editable, requires note on override)    │
│  Net Qty: 100g (98% conf)   MRP: ₹20 (94% conf) [override] │
├──────────────────────────────────────────────────────────┤
│                              [ Generate Section 39 Challan ]│
└──────────────────────────────────────────────────────────┘
```

---

## 5. Integration Scenarios — Where Mobile and Web Must Connect

This is the part your instinct correctly flagged as needed — here are the concrete scenarios, not just "they're connected":

### 5.1 Mobile capture → appears in Web review queue
An LMO captures a scan offline. It syncs later (§3.1 of main blueprint). The moment it's `SYNCED` and processed through the pipeline, if it lands as `PENDING_REVIEW` or `FAILED`, it must appear on the web Review Queue **without a manual refresh** by the senior LMO watching that queue.

### 5.2 Web review decision → notifies the field LMO's mobile app
A senior LMO overrides or confirms a verdict on the web. The field LMO who originally captured it should get a push notification on their phone ("Your scan at [store] confirmed FAILED — Rule 6(1)(e)"), because they may need to go back to that store for a re-inspection or to physically hand over the challan.

### 5.3 E-commerce ingestion (web-only) still needs field follow-up
A senior LMO uploads a Blinkit screenshot on the web portal and it fails compliance. There is no "field LMO" tied to this scan — the system needs an **assignment step**: web dashboard assigns the follow-up (e.g., physical verification, or issuing notice to the seller) to a field LMO, who then sees it appear on their **mobile Home screen** as an assigned task, not something they captured themselves.

### 5.4 Shared identity across both surfaces
An LMO's scans, their review overrides, and their assigned follow-ups must resolve to the *same* LMO ID whether they're acting from the phone or (rarely) logging into the web dashboard directly. One auth service, one user table, is what makes §5.2 and §5.3 possible at all.

### 5.5 Calibration/ruleset consistency
If an admin edits the Schedule II ruleset config on the web (§3, Admin screen), the mobile app's local "quick check" (if any lightweight on-device pre-check exists) must not silently use a stale ruleset — the source of truth for rules is always server-side; the mobile app never evaluates compliance itself, only captures.

---

## 6. Integration Architecture

### 6.1 Shared Authentication
Single auth service (JWT issuer) used by both the Flutter app and the Next.js dashboard. Both clients hit the same `/auth/login` and carry the same token shape (`lmo_id`, `role`, `district`) — this is what makes a notification or an assignment resolvable to the right person regardless of which surface they're on.

### 6.2 Real-Time Update Channel
[Likely — reasonable default, confirm before building] A WebSocket (or simpler: Server-Sent Events) channel per authenticated user, used for:
- Web dashboard: new item appears in Review Queue live (§5.1)
- Mobile app: push notification for status changes on own scans (§5.2) and new assigned tasks (§5.3)

If you'd rather keep this simpler for a hackathon build, a 15–30 second polling interval on both clients achieves the same user-visible effect with far less infrastructure — flagging this as the pragmatic fallback if WebSocket infra is more than the timeline allows.

```
Event: scan.status_changed
  payload: { scan_id, new_status, rule_results[], assigned_lmo_id }
  -> pushed to: assigned_lmo_id (mobile notification)
  -> pushed to: all connected senior_lmo/admin dashboard sessions in that district (queue update)

Event: task.assigned
  payload: { scan_id, assigned_to_lmo_id, task_type: 'field_followup' }
  -> pushed to: assigned_to_lmo_id (mobile Home screen new item)
```

### 6.3 Single API, Two Clients
Both surfaces call the same FastAPI backend (§10 of main blueprint) — there is no separate "mobile API" and "web API." The dashboard additionally uses admin-only endpoints (ruleset config, user management) that the mobile app's role never has access to (enforced via RBAC, §12), but the scan/review/status endpoints are shared.

---

## 7. Build Order Recommendation

Given this is a hackathon-scale build, the sequence that gets you a demoable end-to-end story fastest:

1. Mobile capture → offline queue → sync → backend ingestion (no AI yet — just prove the plumbing)
2. Backend pipeline (Modules 2–3 from main blueprint) running on a synced image
3. Web dashboard Review Queue + Scan Detail, reading directly from the DB (polling, no WebSocket yet)
4. Challan generation
5. Only after 1–4 work end-to-end: add the real-time push layer (§6.2) and the e-commerce → mobile task-assignment loop (§5.3) — these are the "impressive integration" pieces but they're the least load-bearing for a first working demo.
