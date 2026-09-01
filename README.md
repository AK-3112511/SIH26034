# MetrologyAI Monorepo

**MetrologyAI** (SIH26034) is an automated digital compliance & evidence verification platform for packaged commodities, built to enforce the Legal Metrology (Packaged Commodities) Rules, 2011 (PCR 2011).

---

## Monorepo Layout

```
metrologyAI/
├── backend/            # Python FastAPI service & deterministic PCR 2011 rule engine
├── mobile/             # Flutter mobile app for Legal Metrology Officers (Field LMOs)
├── web/                # Next.js App Router TypeScript enforcement & review dashboard
└── audit/              # Progress tracking and audit history logs
```

---

## Subsystem Overview

### 1. Backend (`/backend`)
- **Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Pydantic
- **Key Domains:**
  - `/scans`: Multi-modal ingestion, status polling, and review handling
  - `/auth`: Government LMO authentication & token verification
  - `/challans`: Section 39 PDF notice generation & Section 65B evidence hashing
  - `/admin`: Ruleset config (Schedule II bands) & RBAC management
- **Running Locally:**
  ```bash
  cd backend
  python -m venv .venv
  # On Windows PowerShell:
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  uvicorn app.main:app --reload --port 8000
  ```

### 2. Mobile (`/mobile`)
- **Tech Stack:** Flutter / Dart (Targeting Android first)
- **Key Features:** Field LMO capture interface, offline SQLite queue, AR alignment guide stubs
- **Design System Tokens:** Primary Ink (`#12203B`), Paper (`#F1F3F1`), Brass (`#A6742C`)
- **Running Locally:**
  ```bash
  cd mobile
  flutter pub get
  flutter run
  ```

### 3. Web Dashboard (`/web`)
- **Tech Stack:** Next.js (App Router), TypeScript, Tailwind CSS / Vanilla CSS
- **Key Features:** Senior LMO review queue, GIS national heatmap container, product repository search
- **Running Locally:**
  ```bash
  cd web
  npm install
  npm run dev
  ```

### 4. Audit Log (`/audit`)
- Contains `/audit/progress.md` with step-by-step records of scaffold setup, API integration checkpoints, and verification results.
