# CLAUDE.md — Credit Platform Project Brief

> Paste this file's raw URL at the start of any new conversation to instantly resume work.
> Raw URL: https://raw.githubusercontent.com/sharifeid-eng/credit-platform/main/CLAUDE.md

---

## What This Project Is

**ACP Private Credit Platform** — a full-stack web application for analyzing asset-backed loan portfolios. Built for a private credit fund that purchases receivables (currently healthcare insurance claims via a company called Klaim, based in UAE).

The platform lets analysts upload loan tape snapshots (CSV/Excel), run data integrity checks, and explore portfolio performance through an interactive dashboard with AI-powered commentary and a natural language chat interface.

---

## Tech Stack

- **Backend**: Python, FastAPI, Pandas, Anthropic API (`claude-opus-4-6`), ReportLab (PDF generation)
- **Frontend**: React (Vite), Tailwind CSS, React Router, Axios
- **AI**: Anthropic API used for AI commentary, data chat, and PDF data integrity reports
- **Data**: CSV/Excel loan tape files stored locally under `data/`

---

## Project Structure

```
credit-platform/
├── analyze.py              # Legacy CLI analysis tool (still functional)
├── backend/
│   └── main.py             # FastAPI app — all REST API endpoints
├── core/
│   ├── loader.py           # File discovery, data loading, snapshot management
│   ├── config.py           # Per-product config (currency, description) via config.json
│   ├── consistency.py      # Snapshot-to-snapshot data integrity checks
│   ├── reporter.py         # AI-generated PDF data integrity reports (uses ReportLab)
│   └── analysis.py         # (exists but not yet read — likely additional analytics)
├── data/
│   └── {company}/
│       └── {product}/
│           ├── config.json                        # Currency + description config
│           └── YYYY-MM-DD_{name}.csv              # Loan tape snapshots
│   └── klaim/
│       └── UAE_healthcare/                        # Current live dataset
├── frontend/
│   ├── src/
│   │   ├── App.jsx                                # Router: / and /company/:name
│   │   ├── pages/
│   │   │   ├── Home.jsx                           # Company card grid
│   │   │   └── Company.jsx                        # Full dashboard with tabs
│   │   ├── components/
│   │   │   ├── CompanyCard.jsx                    # Card for each portfolio company
│   │   │   ├── KpiCard.jsx                        # Metric tile (blue/teal/red/gold)
│   │   │   ├── DataChat.jsx                       # AI chat component
│   │   │   ├── Navbar.jsx                         # Top navigation
│   │   │   └── charts/                            # (multiple chart components)
│   │   └── services/
│   │       └── api.js                             # All API calls via Axios
│   └── package.json
└── reports/                # Auto-generated PDF reports saved here
```

---

## Data Model

Loan tape files are CSVs/Excel with these key columns:

| Column | Description |
|---|---|
| `Deal date` | Date the deal was originated |
| `Status` | `Executed` (active) or `Completed` |
| `Purchase value` | Face value of the receivable |
| `Purchase price` | Price paid by the fund |
| `Gross revenue` | Expected gross return |
| `Collected till date` | Amount collected so far |
| `Denied by insurance` | Amount denied by insurer |
| `Pending insurance response` | Amount awaiting insurer decision |
| `Expected total` | Expected total collection |
| `Expected IRR` / `Actual IRR` | Deal-level returns |
| `Group` | Insurer/payer group name |
| `Product` | Sub-product type |
| `Discount` | Discount rate applied |
| `New business` | New vs repeat business flag |

Snapshots are named `YYYY-MM-DD_description.csv` — the date prefix is parsed for ordering.

---

## Backend API (FastAPI on localhost:8000)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/companies` | List all companies with product counts |
| GET | `/companies/{co}/products` | List products |
| GET | `/companies/{co}/products/{p}/snapshots` | List available snapshots |
| GET | `/companies/{co}/products/{p}/config` | Get currency/description config |
| GET | `/companies/{co}/products/{p}/date-range` | Min/max deal dates in snapshot |
| GET | `/companies/{co}/products/{p}/summary` | Portfolio KPIs |
| GET | `/companies/{co}/products/{p}/ai-commentary` | AI-generated portfolio commentary |
| GET | `/companies/{co}/products/{p}/charts/deployment` | Monthly deployment (new vs repeat) |
| GET | `/companies/{co}/products/{p}/charts/collection-velocity` | Collections by days outstanding |
| GET | `/companies/{co}/products/{p}/charts/denial-trend` | Monthly denial rate trend |
| GET | `/companies/{co}/products/{p}/charts/cohort` | Vintage cohort analysis |
| GET | `/companies/{co}/products/{p}/charts/actual-vs-expected` | Cumulative actual vs expected |
| GET | `/companies/{co}/products/{p}/charts/ageing` | Active deal ageing + health |
| GET | `/companies/{co}/products/{p}/charts/revenue` | Realised/unrealised revenue |
| GET | `/companies/{co}/products/{p}/charts/concentration` | Group/product/discount concentration |
| POST | `/companies/{co}/products/{p}/chat` | AI chat with portfolio data |

All chart endpoints accept query params: `snapshot`, `as_of_date`, `currency`.

---

## Frontend Dashboard Tabs

| Tab | What It Shows |
|---|---|
| Overview | 8 KPI cards + AI commentary + Data Chat |
| Actual vs Expected | Cumulative collected vs expected over time |
| Deployment | Monthly capital deployed (new vs repeat) |
| Collection | Collection velocity by days outstanding + monthly breakdown |
| Ageing | Active deal health buckets + ageing analysis |
| Revenue | Realised vs unrealised revenue + gross margin |
| Portfolio | Group/insurer concentration + top 10 deals + discount distribution |
| Cohort Analysis | Vintage cohort table with IRR, collection, denial rates |

Dashboard controls: **Product selector**, **Snapshot (Data Tape) selector**, **Currency toggle** (local vs USD), **As-of Date** picker.

---

## Currency System

Supported: `AED (0.2723)`, `USD (1.0)`, `EUR (1.08)`, `GBP (1.27)`, `SAR (0.2667)`, `KWD (3.26)`.

Each product has a `config.json` with its reported currency. The frontend shows a toggle to switch between reported currency and USD. The backend applies a multiplier at query time.

---

## CLI Tool (analyze.py)

Legacy terminal-based tool. Lets you select company → product → snapshot, runs consistency checks across all snapshots, optionally generates an AI PDF report, then prints a financial summary with currency conversion.

---

## How to Run

```bash
# Backend (from project root)
cd backend
uvicorn main:app --reload

# Frontend (in separate terminal)
cd frontend
npm run dev
```

Backend: `http://localhost:8000`  
Frontend: `http://localhost:5173`

Environment variable needed: `ANTHROPIC_API_KEY` in `.env` file at project root.

---

## Current State & What's Working

- ✅ Full backend API with all chart endpoints
- ✅ Frontend dashboard with all 8 tabs
- ✅ AI commentary and data chat on Overview tab
- ✅ Currency conversion (local ↔ USD)
- ✅ Snapshot selector and as-of-date filtering
- ✅ Data integrity CLI tool with PDF report generation
- ✅ Cohort analysis with IRR tracking
- ✅ Portfolio concentration (group, product, discount)
- ✅ Ageing with health classification (Healthy/Watch/Delayed/Poor)

---

## Known Gaps / Next Steps (as of last session)

- `core/analysis.py` is empty — placeholder only, no logic yet
- All chart components fully read and understood (see Chart Components section below)
- No authentication / login system
- No multi-user support
- `analyze.py` CLI and backend are somewhat duplicated — could be unified

---

## Chart Components (frontend/src/components/charts/)

| Component | Library | What It Renders |
|---|---|---|
| `DeploymentChart` | Recharts BarChart | Stacked bar: new vs repeat business by month |
| `CollectionVelocityChart` | Recharts LineChart + BarChart | Monthly collection rate line + completed deal buckets by days |
| `DenialTrendChart` | Recharts ComposedChart | Bars for monthly denial rate + line for 3M rolling average |
| `ActualVsExpectedChart` | Recharts AreaChart | Cumulative collected vs expected, with performance % header |
| `AgeingChart` | Recharts PieChart + BarChart | Health donut (Healthy/Watch/Delayed/Poor) + ageing bucket bar chart |
| `RevenueChart` | Recharts ComposedChart | Stacked bars realised/unrealised + gross margin % line, plus 4 KPI tiles |
| `ConcentrationChart` | Recharts PieChart | Two donuts (Group + Product) + top 10 deals table |
| `CohortTable` | Plain HTML table | Vintage cohort rows with collection rate, denial rate, IRR spread |

All charts share the same dark theme palette (`#0A0F1E` bg, `#111D3E` cards, `#1B2B5A` borders) and a shared `formatMillions` helper. Custom tooltips are consistent across all charts.

`AICommentary` — on-demand button that calls `/ai-commentary` and renders the response with basic line parsing (headers in blue, bullets, paragraphs). Has Generate/Regenerate states with a spinner.

---

## Notes for Claude

- Always check `core/config.py` for the currency list before adding new currencies
- Data lives in `data/{company}/{product}/` — filenames must start with `YYYY-MM-DD_`
- The `filter_df()` function in `backend/main.py` filters deals by `Deal date <= as_of_date`
- `get_multiplier()` returns 1.0 unless display currency is USD and reported is not USD
- ReportLab is used for PDF generation in `core/reporter.py`
- All AI calls use `claude-opus-4-6` model