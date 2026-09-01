# MetrologyAI — Design System
**Companion to:** MetrologyAI Elevated Blueprint & Mobile/Web UX Integration Blueprint
**Focus:** Visual identity, tokens, and component language for both the Flutter mobile app and the Next.js web dashboard

---

## Table of Contents
1. [Design Philosophy & Signature Element](#1-design-philosophy--signature-element)
2. [Color System](#2-color-system)
3. [Typography System](#3-typography-system)
4. [Spacing & Layout Grid](#4-spacing--layout-grid)
5. [Component Library](#5-component-library)
6. [Iconography](#6-iconography)
7. [Motion](#7-motion)
8. [Mobile-Specific Considerations](#8-mobile-specific-considerations)
9. [Web Dashboard-Specific Considerations](#9-web-dashboard-specific-considerations)
10. [Accessibility Floor](#10-accessibility-floor)

---

## 1. Design Philosophy & Signature Element

MetrologyAI is a measuring instrument and a legal-evidence system before it is an "app." The design should read like calibrated government instrumentation — a caliper, a certified scale, an official stamp — not like a consumer productivity tool. Trust is the product; the UI's job is to make every number look measured, not guessed, and every verdict look official, not just colored.

**Signature element: the Calibration Tick Rule.** A thin horizontal (or vertical, on narrow mobile layouts) ruler with millimeter-style tick marks is used as the structural divider between sections, replacing generic blank whitespace or hairline dividers. It is a direct, literal reference to the core mechanic of the product — measuring a font against a reference card — so it is never decorative, it always sits where a real division of content exists (never used as a purely aesthetic flourish).

**Signature element: the Seal Badge.** Every verdict (PASS / FAIL / PENDING REVIEW / CALIBRATION FAILED) is rendered as a double-ring circular badge reminiscent of an official rubber stamp or hallmark seal — not a flat colored pill. This is the one place the design allows itself some weight and texture; everywhere else stays quiet and disciplined so the seal badge keeps its authority.

---

## 2. Color System

| Token | Hex | Role |
|---|---|---|
| `ink-900` | `#12203B` | Primary brand ink — navigation, headers, primary buttons. Deep institutional navy, not black — signals official/government without being funereal. |
| `ink-600` | `#3C4E70` | Secondary text, inactive nav states |
| `paper-100` | `#F1F3F1` | App/dashboard background — a cool, slightly grey-green off-white (deliberately *not* the warm cream that's become an AI-design default) |
| `paper-000` | `#FFFFFF` | Card surfaces, elevated panels |
| `brass-500` | `#A6742C` | Signature accent — used only for the Seal Badge ring, the Calibration Tick Rule, and one primary CTA per screen. Evokes brass calipers/instrument hardware and wax-seal officialdom. Never used for large fills. |
| `verdict-pass` | `#1E7A4D` | PASS seal badge, success states |
| `verdict-fail` | `#B3261E` | FAIL seal badge, error states |
| `verdict-pending` | `#B5730B` | PENDING REVIEW seal badge, warning states |
| `verdict-neutral` | `#6B7280` | CALIBRATION FAILED / unknown states |

Verdict colors are **intentionally distinct** from `brass-500` — a common failure mode is letting the brand accent double as a semantic status color, which makes a PENDING badge and a "brand-colored" button visually interchangeable. They must never be confusable, since one is a legal judgment and the other is decoration.

---

## 3. Typography System

| Role | Typeface | Usage |
|---|---|---|
| Display | **Space Grotesk** (weights 500/700) | Screen titles, the Overview stat numbers, challan headers — a geometric, technical-feeling sans that reads as instrumentation rather than marketing |
| Body / UI | **Inter** (weights 400/500/600) | All body text, labels, buttons, form fields — chosen purely for legibility at small sizes on a phone screen in bright daylight |
| Data / Measurement | **IBM Plex Mono** (weight 500, tabular figures) | Every measured or extracted number: mm, cm², confidence %, GPS coordinates, rule IDs, timestamps, hash values. This is the deliberate typographic "tell" that a number came from measurement/extraction, not from prose — a reviewer should be able to tell at a glance which numbers are evidentiary data vs. UI copy. |

**Type scale (base 16px, 1.25 ratio):** 12 / 16 / 20 / 25 / 31 / 39 / 49px — display sizes start at 25px, body/UI stays at 14–16px, mono data labels sit at 14px with increased letter-spacing (`+0.02em`) for readability of dense digit strings.

---

## 4. Spacing & Layout Grid

* **Base unit:** 8px. All padding, margin, and gap values are multiples of 8 (4px allowed only for icon-to-label gaps).
* **Mobile grid:** single column, 16px screen margins, 48px minimum touch target height (field use means gloved or shaky-handed tapping, sunlight glare, and no room for precision taps).
* **Web grid:** 12-column grid, 24px gutters, max content width 1440px with the GIS heatmap and Review Queue allowed to run full-bleed since map/table density benefits from width; forms and detail panels stay capped at ~720px for readability.
* **The Calibration Tick Rule** sits at every major section boundary at a fixed 2px height, ticks every 8px (matching the base spacing unit — the ruler literally measures the grid it divides).

---

## 5. Component Library

### 5.1 Seal Badge (verdict indicator)
Double concentric ring, outer ring in `brass-500` at 1px, inner fill in the verdict color at 12% opacity, verdict color text/icon centered. Sizes: 24px (inline, list rows), 48px (scan detail header), 96px (challan PDF — rendered as a vector, not a raster, so it stays crisp at print resolution).

### 5.2 Buttons
- **Primary:** `ink-900` fill, white text, used once per screen for the single most important action ("Generate Challan", "New Scan").
- **Accent (rare):** `brass-500` fill — reserved for the one true "signature" CTA per major flow (e.g., the shutter button's ready state). Overusing this collapses the signature/utility distinction, so it should appear at most once per screen.
- **Secondary:** `paper-000` fill, `ink-900` 1px border.
- **Destructive:** `verdict-fail` fill, used only for irreversible actions (e.g., discarding a queued capture).

### 5.3 Cards
`paper-000` surface, 1px `ink-600` border at 8% opacity, 4px corner radius (small radius — sharp enough to feel like official documentation, not a consumer app's soft rounded cards), 16px internal padding.

### 5.4 Status Chips (non-verdict states)
Used for sync/queue status only (`Synced`, `Pending Upload`, `Failed`) — deliberately a *flat* pill shape, distinct from the Seal Badge, so a reviewer never confuses "this photo hasn't uploaded yet" with "this product failed a legal compliance rule." Different shape language for different stakes is the point.

### 5.5 Data Table (web)
Zebra-striped rows at 4% `ink-900` tint, mono typeface for any numeric column, sortable column headers with a small tick-mark caret (echoing the signature ruler motif at icon scale).

### 5.6 Forms
Label above field (never placeholder-as-label), 1px `ink-600` border at rest, `brass-500` border on focus, error state shows `verdict-fail` border plus inline text explaining what to fix — never just a red border with no explanation.

---

## 6. Iconography

A single-weight, 1.5px stroke icon set (e.g., Lucide, used consistently rather than mixing icon sets) — technical/schematic rather than playful. Where an icon needs to represent a MetrologyAI-specific concept with no existing standard icon (e.g., "reference card calibration," "PDP area"), draw a simple custom glyph based on the ruler-tick motif rather than reaching for an unrelated stock icon.

---

## 7. Motion

Kept deliberately minimal — this is an evidentiary tool, not a consumer app, and gratuitous motion undercuts the "instrument" feeling:
- **Capture screen:** the reference-card guide box transitions red→green over 150ms when detection succeeds — this is functional feedback, not decoration.
- **Seal Badge:** a single one-time "stamp impact" micro-animation (scale 0.9→1.0 with a slight overshoot, ~200ms) plays once when a verdict first renders on the Scan Detail screen — the one deliberate moment of personality in the whole system, echoing a physical rubber stamp coming down.
- Everything else (navigation, list loading, queue updates) uses simple opacity/position fades under 150ms — no bouncing, no parallax, no decorative loading animations.
- Reduced-motion OS setting disables both of the above in favor of an instant state change.

---

## 8. Mobile-Specific Considerations

* **Outdoor legibility:** all text meets a minimum 4.5:1 contrast against `paper-100`/`paper-000` even accounting for the additional wash-out of direct sunlight on a phone screen — verified against `ink-900` and verdict colors specifically, since these carry the legal information.
* **One-handed / gloved use:** 48px minimum tap targets, primary actions bottom-anchored within thumb reach (not top app-bar actions).
* **Low-connectivity feedback:** the sync status chip (§5.4) is always visible on the Home screen, never hidden behind a menu — an LMO needs to know at a glance whether today's evidence has actually left the device.
* **Dark mode:** not a priority for v1 — field use is daylight-dominant; if added later, `ink-900` and `paper-100` invert but verdict colors stay fixed (a FAIL badge must look the same in every LMO's hand, day or night, so it's never mistaken for a theme artifact).

---

## 9. Web Dashboard-Specific Considerations

* **Map styling (GIS heatmap):** a muted, low-saturation base map (grey/paper-toned, not a default bright Google-Maps-style basemap) so that the verdict-colored violation clusters are the only saturated color on screen and read immediately.
* **Data density:** the Review Queue and Repository Search screens are allowed real table density (compact row height, 32px) since senior LMOs are working through volume — this is the one place the design trades some breathing room for throughput, deliberately different from the mobile app's spacious touch-first layout.
* **Print stylesheet:** the Section 39 Challan PDF is not just "the web page printed" — it has its own fixed A4 layout, vector Seal Badge, and government header block, generated server-side via ReportLab (per the main blueprint), not via browser print CSS.

---

## 10. Accessibility Floor

* WCAG 2.1 AA contrast minimum across all text and verdict color pairings (verdict colors were chosen and will be re-checked specifically for colorblind differentiation — PASS/FAIL/PENDING must also be distinguishable by the Seal Badge's icon/shape, not color alone).
* All interactive elements have visible keyboard focus states on web (important since senior LMOs reviewing dozens of scans a day will want keyboard shortcuts eventually — Tab/Enter flow through the Review Queue should work even before shortcuts are built).
* Bilingual support (English/Hindi, matching the OCR's own language coverage) is a layout requirement, not just a translation task — Hindi text runs longer than English for the same content, so fixed-width labels and buttons are avoided in favor of flexible containers.
