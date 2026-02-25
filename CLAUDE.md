# CLAUDE.md — ACP Private Credit Platform

> Start every new session by pasting this URL:
> `https://raw.githubusercontent.com/sharifeid-eng/credit-platform/main/CLAUDE.md`

---

## What This Project Is

**ACP Private Credit Platform** — an institutional-grade, full-stack web application for analyzing and monitoring asset-backed loan portfolios. Built for a private credit fund (ACP) that purchases receivables and short-term loans from portfolio companies.

The platform allows analysts and investment committee members to:
- Upload loan tape snapshots (CSV/Excel) and explore portfolio performance
- Run automated data integrity checks across snapshots
- View interactive dashboards with 9 analysis tabs
- Generate AI-powered portfolio commentary and ask natural language questions about the data

---

## Business Context

**Who uses it:** Sharif (fund analyst/PM) and eventually the broader investment committee.

**Current portfolio companies:**
- **Klaim** — medical insurance claims factoring, UAE. Data in AED. Live dataset: `data/klaim/UAE_healthcare/`
- **SILQ** — POS lending. Not yet onboarded into the platform.

**Asset classes:** Receivables (insurance claims factoring) and short-term consumer/POS loans.

**Data format:** Single Excel or CSV loan tapes, typically thousands to tens of thousands of rows. Each row is a deal/receivable. Snapshots are taken periodically (e.g. monthly) and named `YYYY-MM-DD_description.csv`.

---

## Long-Term Vision (3 Phases)

### Phase 1 — Loan Tape Analysis & Dashboards ✅ (current)
- Manual file upload workflow
- AI-powered dashboards per company/product
- Consistency checks across snapshots
- Investment committee-ready commentary

### Phase 2 — Borrowing Base Monitoring
- Automated eligibility testing against lending criteria
- Concentration limit tracking
- Advance rate calculations
- Covenant monitoring and breach alerts

### Phase 3 — Team & IC Viewing Layer
- Role-based access (analyst vs IC vs read-only)
- Scheduled report delivery
- Direct API integrations with portfolio companies' accounting or loan management systems (pulling data automatically instead of manual uploads)
- Cloud deployment so the app runs 24/7 without manual server starts

---

## Tech Stack

- **Backend:** Python, FastAPI (`localhost:8000`), Pandas, Anthropic API (`claude-opus-4-6`), ReportLab (PDF)
- **Frontend:** React (Vite), Tailwind CSS, Recharts, React Router, Axios (`localhost:5173`)
- **AI:** Anthropic API — portfolio commentary, per-tab insights, data chat, PDF integrity reports
- **Data:** CSV/Excel files stored locally under `data/`

---

## How to Start the App (Every Session)

**Terminal 1 — Backend:**
```bash
cd C:\Users\SharifEid\credit-platform
venv\Scripts\activate
cd backend
python -m uvicorn main:app --reload
```

**Terminal 2 — Frontend:**
```bash
cd C:\Users\SharifEid\credit-platform\frontend
npm run dev
```

Then open `http://localhost:5173` in the browser.

> Note: Both servers only run on your local machine. In a future cloud deployment, they'll run 24/7 without manual starting.

---

## Project Structure

```
credit-platform/
├── analyze.py              # Legacy CLI analysis tool (still functional)
├── CLAUDE.md               # This file — project brief for Claude
├── .env                    # API key — NEVER committed to GitHub
├── .env.example            # Placeholder showing required env vars
├── backend/
│   └── main.py             # FastAPI app — all REST endpoints (imports from core.analysis)
├── core/
│   ├── analysis.py         # All pure data computation functions (no I/O)
│   ├── loader.py           # File discovery, snapshot loading
│   ├── config.py           # Per-product config (currency, description) via config.json
│   ├── consistency.py      # Snapshot-to-snapshot data integrity checks
│   └── reporter.py         # AI-generated PDF data integrity reports (ReportLab)
├── data/
│   └── {company}/
│       └── {product}/
│           ├── config.json                    # Currency + description
│           └── YYYY-MM-DD_{name}.csv          # Loan tape snapshots
├── frontend/
│   ├── src/
│   │   ├── App.jsx                            # Router
│   │   ├── pages/
│   │   │   ├── Home.jsx                       # Company card grid
│   │   │   └── Company.jsx                    # Full dashboard
│   │   ├── components/
│   │   │   ├── CompanyCard.jsx
│   │   │   ├── KpiCard.jsx
│   │   │   ├── Navbar.jsx
│   │   │   ├── AICommentary.jsx               # On-demand commentary, cached across tab switches
│   │   │   ├── DataChat.jsx                   # Natural language chat with portfolio data
│   │   │   ├── TabInsight.jsx                 # Compact per-tab AI insight button
│   │   │   └── charts/
│   │   │       ├── ActualVsExpectedChart.jsx
│   │   │       ├── AgeingChart.jsx
│   │   │       ├── CohortTable.jsx
│   │   │       ├── CollectionVelocityChart.jsx
│   │   │       ├── ConcentrationChart.jsx
│   │   │       ├── DenialTrendChart.jsx
│   │   │       ├── DeploymentChart.jsx
│   │   │       └── RevenueChart.jsx
│   │   └── services/
│   │       └── api.js
│   └── package.json
└── reports/                # Auto-generated PDF integrity reports
```

---

## Data Model

Key columns in loan tape files:

| Column | Description |
|---|---|
| `Deal date` | Origination date |
| `Status` | `Executed` (active) or `Completed` |
| `Purchase value` | Face value of receivable |
| `Purchase price` | Price paid by fund |
| `Gross revenue` | Expected gross return |
| `Collected till date` | Amount collected |
| `Denied by insurance` | Amount denied |
| `Pending insurance response` | Amount awaiting decision |
| `Expected total` | Expected total collection |
| `Expected IRR` / `Actual IRR` | Deal-level returns |
| `Group` | Insurer/payer group |
| `Product` | Sub-product type |
| `Discount` | Discount rate |
| `New business` | New vs repeat flag |

---

## Backend API (`localhost:8000`)

| Endpoint | Description |
|---|---|
| `GET /companies` | List all companies |
| `GET /companies/{co}/products` | List products |
| `GET /companies/{co}/products/{p}/snapshots` | List snapshots |
| `GET /companies/{co}/products/{p}/config` | Currency/description config |
| `GET /companies/{co}/products/{p}/date-range` | Min/max deal dates |
| `GET /companies/{co}/products/{p}/summary` | Portfolio KPIs |
| `GET /companies/{co}/products/{p}/ai-commentary` | AI portfolio commentary |
| `GET /companies/{co}/products/{p}/ai-tab-insight` | Short AI insight for a specific tab |
| `GET /companies/{co}/products/{p}/charts/deployment` | Monthly deployment |
| `GET /companies/{co}/products/{p}/charts/collection-velocity` | Collection timing |
| `GET /companies/{co}/products/{p}/charts/denial-trend` | Denial rate trend |
| `GET /companies/{co}/products/{p}/charts/cohort` | Vintage cohort analysis |
| `GET /companies/{co}/products/{p}/charts/actual-vs-expected` | Cumulative actual vs expected |
| `GET /companies/{co}/products/{p}/charts/ageing` | Active deal health + ageing |
| `GET /companies/{co}/products/{p}/charts/revenue` | Revenue analysis |
| `GET /companies/{co}/products/{p}/charts/concentration` | Group/product concentration |
| `POST /companies/{co}/products/{p}/chat` | AI data chat |

All chart endpoints accept: `snapshot`, `as_of_date`, `currency` query params.

---

## Dashboard Tabs

| Tab | What It Shows |
|---|---|
| Overview | 8 KPI cards + AI commentary (cached) + Data Chat |
| Actual vs Expected | Cumulative collected vs expected area chart + performance % |
| Deployment | Monthly capital deployed (new vs repeat stacked bar) |
| Collection | Monthly collection rate + completed deals by days outstanding |
| Denial Trend | Monthly denial rate bars + 3M rolling average |
| Ageing | Health donut (Healthy/Watch/Delayed/Poor) + ageing bucket bars |
| Revenue | Realised/unrealised stacked bars + gross margin line + KPI tiles |
| Portfolio | Group + product concentration donuts + top 10 deals table |
| Cohort Analysis | Vintage table: collection rate, denial rate, IRR spread |

Each non-overview tab has a **TabInsight** component — a teal bar at the top with a one-click AI insight specific to that view.

Dashboard controls: Product selector, Snapshot (Data Tape) selector, Currency toggle (local ↔ USD), As-of Date picker.

---

## Currency System

Supported: `AED (0.2723)`, `USD (1.0)`, `EUR (1.08)`, `GBP (1.27)`, `SAR (0.2667)`, `KWD (3.26)`.

Each product has a `config.json` with its reported currency. The frontend shows a toggle between reported currency and USD. The backend applies a multiplier at query time via `apply_multiplier()` in `core/analysis.py`.

> TODO: Replace hardcoded FX rates with a live FX API call.

---

## Key Architectural Decisions

- **`core/analysis.py`** — all pure data computation lives here. No FastAPI, no I/O. Backend endpoints are thin wrappers that load data, call these functions, and return results.
- **`core/config.py`** — per-product `config.json` stores currency and description. Created interactively on first run via CLI, or manually.
- **Snapshot naming** — files must start with `YYYY-MM-DD_` for date parsing and ordering.
- **`filter_by_date()`** — filters deals to `Deal date <= as_of_date`, enabling time-travel analysis within a tape.
- **AICommentary caching** — commentary is stored in `Company.jsx` state and passed down as a `cached` prop, so it survives tab switches without re-generating.
- All AI calls use `claude-opus-4-6`.

---

## What's Working

- ✅ Full backend with all chart and AI endpoints
- ✅ 9-tab React dashboard
- ✅ AI commentary (cached), per-tab insights, data chat
- ✅ Currency toggle (local ↔ USD)
- ✅ Snapshot selector + as-of-date filtering
- ✅ Data integrity CLI with PDF report generation
- ✅ Cohort analysis with IRR tracking
- ✅ Portfolio concentration, ageing health classification
- ✅ `core/analysis.py` — clean separation of analytics logic

---

## Known Gaps & Next Steps

**Short term:**
- [ ] Onboard SILQ as a second portfolio company
- [ ] Add `core/analysis.py` unit tests
- [ ] Replace hardcoded FX rates with live API
- [ ] Startup script — single command to boot both servers

**Phase 2 (Borrowing Base Monitoring):**
- [ ] Eligibility criteria testing per deal
- [ ] Concentration limit tracking
- [ ] Advance rate calculations
- [ ] Covenant monitoring and breach alerts

**Phase 3 (Team & Deployment):**
- [ ] Cloud deployment (Railway, Render, or VM)
- [ ] Role-based access (analyst / IC / read-only)
- [ ] Scheduled report delivery
- [ ] Direct API integrations with portfolio companies' systems

---

## Environment

- **Machine:** Windows (PowerShell)
- **Python:** 3.14.3, virtual environment at `credit-platform/venv/`
- **Node:** v24
- **Repo:** https://github.com/sharifeid-eng/credit-platform
- **Required `.env`:** `ANTHROPIC_API_KEY=your_key_here`