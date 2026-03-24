# Laith Private Credit Platform
-----
## About This File
This is the **CLAUDE.md** for the project — automatically loaded by Claude Code at the start of every session. It serves as the single source of truth for project context, conventions, and current status.
**Update rule:** When significant decisions are made or features are completed, update this file to keep it current.
**Reminder rule:** After completing a major task or feature, remind the user to:
1. Update CLAUDE.md (offer to do it)
2. Commit and push to GitHub (offer to do it, confirm `.env` is not tracked)
-----
## What This Project Is
**Laith** (with **AI** as a play in the name) — an institutional-grade, full-stack web application for analyzing and monitoring asset-backed loan portfolios. Built for a private credit fund (ACP) that purchases receivables and short-term loans from portfolio companies.
The platform allows analysts and investment committee members to:
- Upload loan tape snapshots (CSV/Excel) and explore portfolio performance
- Run automated data integrity checks across snapshots
- View interactive dashboards with 12 analysis tabs (including institutional risk analytics and data integrity)
- Generate AI-powered portfolio commentary and ask natural language questions about the data
-----
## Branding
- **Platform name:** Laith (لَيث — Arabic for "lion"; the AI in L-**AI**-th is intentional)
- **Logo:** Styled text logo built into components (gold "AI" highlight in "LAITH" + 🦁 icon mark)
- **Logo component:** `LaithLogo` exported from `Navbar.jsx`, used in Navbar (Home page removed duplicate)
- **Page title:** `Laith — Data Analytics` (set in `frontend/index.html` and Navbar)
- **Note:** Original SVG at `frontend/public/logo.svg` has white background, not suitable for dark theme. Using styled component instead.
-----
## Business Context
**Who uses it:** Sharif (fund analyst/PM) and eventually the broader investment committee.
**Current portfolio companies:**
- **Klaim** — medical insurance claims factoring, UAE. Data in AED. Live dataset: `data/klaim/UAE_healthcare/`
- **SILQ** — POS lending, KSA. Data in SAR. Live dataset: `data/SILQ/KSA/` (1 tape: Jan 2026). Has dedicated analysis module (`core/analysis_silq.py`), validation (`core/validation_silq.py`), dynamic chart endpoint, and tests.
**Asset classes:** Receivables (insurance claims factoring) and short-term consumer/POS loans.
**Data format:** Single Excel or CSV loan tapes, typically thousands to tens of thousands of rows. Each row is a deal/receivable. Snapshots are taken periodically (e.g. monthly) and named `YYYY-MM-DD_description.csv`.
**Data notes:**
- **Tapes available:** Sep 2025 (25 cols), Dec 2025 (xlsx), Feb 2026 (25 cols), Mar 2026 (60 cols — latest)
- Sep 2025 tape has `Expected IRR` and `Actual IRR` columns; Dec 2025 and Feb 2026 do not
- Mar 2026 tape restored IRR and added 35 new columns: collection curves (26 cols for expected/actual at 30d intervals up to 390d), `Owner`, `Released from`, `Collected till date by owner`, VAT columns, `FundStatus`
- `Actual IRR for owner` column in Mar 2026 tape has **garbage data** (mean ~2.56e44) — excluded from all analysis
- All tapes have `Discount` column (values range 1%–41%, concentrated at 4–7%)
- `New business` column available for new vs repeat analysis
- Fee columns: `Setup fee`, `Other fee`, `Adjustments`
- Loss tracking: `Provisions`, `Denied by insurance`
- **Column availability drives feature visibility** — features gracefully degrade (hidden, not estimated) on older tapes
-----
## Long-Term Vision (3 Phases)
### Phase 1 — Loan Tape Analysis & Dashboards ✅
- Manual CSV/Excel upload workflow
- AI-powered dashboards per company/product (12 tape analytics tabs)
- Consistency checks across snapshots
- Investment committee-ready commentary + one-click PDF reports
### Phase 2 — Borrowing Base Monitoring ✅
- PostgreSQL 18.3 database with SQLAlchemy 2.0 ORM + Alembic migrations
- Integration API (12 endpoints) for portfolio companies to push invoices/payments/bank statements
- Real-time borrowing base waterfall, concentration limits, covenant monitoring
- Portfolio computation engine (`core/portfolio.py`) with DB-optional fallback to tape data
- Frontend: 6 portfolio tabs (Borrowing Base, Concentration Limits, Covenants, Invoices, Payments, Bank Statements)
### Phase 3 — Team & IC Viewing Layer
- Role-based access (analyst vs IC vs read-only)
- Scheduled report delivery
- Cloud deployment so the app runs 24/7
-----
## Tech Stack
- **Backend:** Python, FastAPI (`localhost:8000`), Pandas, Anthropic API (`claude-opus-4-6`), ReportLab (PDF)
- **Database:** PostgreSQL 18.3, SQLAlchemy 2.0 (async-ready), Alembic (migrations), psycopg2
- **Frontend:** React (Vite), Tailwind CSS, Recharts, React Router, Axios (`localhost:5173`)
- **AI:** Anthropic API — portfolio commentary, per-tab insights, data chat, PDF integrity reports
- **PDF Reports:** Playwright (headless Chrome) for dashboard screenshots + ReportLab for PDF composition
- **Data sources:**
  - **Tape Analytics:** CSV/Excel files stored locally under `data/` (manual upload)
  - **Portfolio Analytics:** PostgreSQL database fed by Integration API (with fallback to tape data if DB not configured)
-----
## How to Start the App (Every Session)
**One command (recommended):**
```powershell
cd C:\Users\SharifEid\credit-platform
.\start.ps1
```
Opens two terminal windows (backend + frontend) and launches the browser automatically.

**Manual start (if needed):**
- Terminal 1 — Backend: `cd credit-platform && venv\Scripts\activate && cd backend && python -m uvicorn main:app --reload`
- Terminal 2 — Frontend: `cd credit-platform\frontend && npm run dev`
- Then open `http://localhost:5173`
-----
## Project Structure
```
credit-platform/
├── analyze.py              # Legacy CLI analysis tool (still functional)
├── generate_report.py      # Playwright + ReportLab PDF report generator (CLI + backend)
├── .env                    # API key + DATABASE_URL — NEVER committed to GitHub
├── .gitignore              # Must include: .env, node_modules/, venv/, __pycache__/, reports/
├── alembic/
│   ├── env.py              # Alembic migration environment
│   └── versions/
│       └── aa1a0a4ec761_initial_schema_6_tables.py  # Initial migration (6 tables)
├── alembic.ini             # Alembic config
├── backend/
│   ├── main.py             # FastAPI app — all REST endpoints (tape + portfolio)
│   ├── auth.py             # X-API-Key authentication for integration endpoints
│   ├── integration.py      # 12 inbound integration API endpoints (invoices/payments/bank statements)
│   └── schemas.py          # Pydantic request/response models for integration API
├── core/
│   ├── analysis.py         # All pure Klaim data computation functions (no I/O)
│   ├── analysis_silq.py    # SILQ-specific analysis functions (9 compute functions)
│   ├── database.py         # SQLAlchemy 2.0 engine/session setup (DB-optional mode)
│   ├── db_loader.py        # DB → tape-compatible DataFrame bridge (Klaim + SILQ mappers)
│   ├── loader.py           # File discovery, snapshot loading
│   ├── config.py           # Per-product config (currency, description) via config.json
│   ├── consistency.py      # Snapshot-to-snapshot data integrity checks
│   ├── migration.py        # Multi-snapshot roll-rate & cure-rate analysis
│   ├── models.py           # SQLAlchemy ORM models (6 tables: Organization, Product, Invoice, Payment, BankStatement, FacilityConfig)
│   ├── portfolio.py        # Portfolio analytics computation (borrowing base, concentration, covenants)
│   ├── validation.py       # Single-tape data quality checks (Klaim)
│   ├── validation_silq.py  # SILQ-specific data quality checks
│   └── reporter.py         # AI-generated PDF data integrity reports (ReportLab)
├── data/
│   └── {company}/
│       └── {product}/
│           ├── config.json
│           └── YYYY-MM-DD_{name}.csv
├── frontend/
│   ├── public/
│   │   └── logo.svg        # Original logo (white bg — not used in dark theme)
│   ├── src/
│   │   ├── App.jsx                  # Nested routes with CompanyLayout
│   │   ├── contexts/
│   │   │   └── CompanyContext.jsx    # Shared state provider (company, product, snapshots, config)
│   │   ├── layouts/
│   │   │   └── CompanyLayout.jsx    # Sidebar + <Outlet> wrapper with CompanyProvider
│   │   ├── pages/
│   │   │   ├── Home.jsx             # Landing page — company grid
│   │   │   ├── TapeAnalytics.jsx    # 12-tab tape dashboard (extracted from old Company.jsx)
│   │   │   ├── PortfolioAnalytics.jsx  # 3-tab portfolio view (mock data)
│   │   │   └── Methodology.jsx      # Definitions, formulas, rationale for all analytics
│   │   ├── components/
│   │   │   ├── Sidebar.jsx          # 240px persistent sidebar nav (Tape + Portfolio + Methodology)
│   │   │   ├── KpiCard.jsx
│   │   │   ├── Navbar.jsx           # Contains LaithLogo component (exported)
│   │   │   ├── AICommentary.jsx
│   │   │   ├── DataChat.jsx
│   │   │   ├── TabInsight.jsx
│   │   │   ├── ChartPanel.jsx
│   │   │   ├── charts/
│   │   │   │   ├── ActualVsExpectedChart.jsx
│   │   │   │   ├── AgeingChart.jsx
│   │   │   │   ├── CohortTable.jsx           # Enhanced: IRR, pending, loss rate, totals row
│   │   │   │   ├── CollectionVelocityChart.jsx
│   │   │   │   ├── ConcentrationChart.jsx
│   │   │   │   ├── DenialTrendChart.jsx
│   │   │   │   ├── DeploymentChart.jsx
│   │   │   │   ├── RevenueChart.jsx
│   │   │   │   ├── ReturnsAnalysisChart.jsx  # Discount bands, margins, new vs repeat
│   │   │   │   ├── RiskMigrationChart.jsx    # Roll-rates, cure rates, EL model, stress test
│   │   │   │   ├── DenialFunnelChart.jsx     # Resolution pipeline funnel visualization
│   │   │   │   └── DataIntegrityChart.jsx    # Two-tape comparison, validation, AI report + notes
│   │   │   └── portfolio/
│   │   │       ├── BorrowingBase.jsx         # Waterfall, KPIs, advance rates, facility capacity
│   │   │       ├── ConcentrationLimits.jsx   # Limit cards with compliance badges + breaching items
│   │   │       ├── Covenants.jsx             # Covenant cards with threshold bars + historical dates
│   │   │       ├── WaterfallTable.jsx        # Borrowing base waterfall table
│   │   │       ├── LimitCard.jsx             # Click-to-expand limit card (breaching items, adjustments)
│   │   │       ├── CovenantCard.jsx          # Covenant card with threshold visualization
│   │   │       ├── ComplianceBadge.jsx       # Shared Compliant/Breach badge
│   │   │       ├── InvoicesTable.jsx         # Paginated invoice table (eligible/ineligible tabs, search)
│   │   │       ├── PaymentsTable.jsx         # Payment ledger (ADVANCE/PARTIAL/FINAL badges, filters)
│   │   │       ├── BankStatementsView.jsx    # Cash position KPIs + statement history
│   │   │       └── mockData.js               # Legacy mock data (retained for reference)
│   │   ├── styles/
│   │   │   ├── chartTheme.js
│   │   │   └── tokens.css
│   │   └── services/
│   │       └── api.js
│   └── package.json
├── tests/
│   ├── test_analysis_klaim.py  # Integration tests for Klaim analytics
│   └── test_analysis_silq.py   # Integration tests for SILQ analytics
├── scripts/
│   ├── seed_db.py          # CLI to seed PostgreSQL from existing tape CSV/Excel files
│   └── create_api_key.py   # CLI to generate API keys for portfolio companies
├── docs/
│   └── generate_guide.js   # Node.js script to generate Word docs with LAITH branding
└── reports/
```
-----
## Data Model
Key columns in loan tape files:
|Column                       |Description                       |
|-----------------------------|----------------------------------|
|`Deal date`                  |Origination date                  |
|`Status`                     |`Executed` (active) or `Completed`|
|`Purchase value`             |Face value of receivable          |
|`Purchase price`             |Price paid by fund                |
|`Discount`                   |Discount rate (1%–41%)            |
|`Gross revenue`              |Expected gross return             |
|`Collected till date`        |Amount collected                  |
|`Denied by insurance`        |Amount denied                     |
|`Pending insurance response` |Amount awaiting decision          |
|`Expected total`             |Expected total collection         |
|`Expected IRR` / `Actual IRR`|Deal-level returns (Sep 2025 tape only)|
|`Group`                      |Healthcare provider/client group  |
|`Product`                    |Sub-product type                  |
|`New business`               |New vs repeat flag                |
|`Setup fee` / `Other fee`    |Fee income                        |
|`Adjustments`                |Deal adjustments                  |
|`Provisions`                 |Loss provisions                   |
|`Claim count`                |Number of claims in deal          |
|`Reinvestment`               |Reinvestment flag/amount          |
|`Release amount`             |Released amount                   |
|`Expected till date`         |Expected collections to date      |
-----
## Backend API (`localhost:8000`)
|Endpoint                                                     |Description                        |
|-------------------------------------------------------------|-----------------------------------|
|`GET /companies`                                             |List all companies                 |
|`GET /companies/{co}/products`                               |List products                      |
|`GET /companies/{co}/products/{p}/snapshots`                 |List snapshots                     |
|`GET /companies/{co}/products/{p}/config`                    |Currency/description config        |
|`GET /companies/{co}/products/{p}/date-range`                |Min/max deal dates                 |
|`GET /companies/{co}/products/{p}/summary`                   |Portfolio KPIs                     |
|`GET /companies/{co}/products/{p}/ai-commentary`             |AI portfolio commentary            |
|`GET /companies/{co}/products/{p}/ai-tab-insight`            |Short AI insight for a specific tab|
|`GET /companies/{co}/products/{p}/charts/deployment`         |Monthly deployment                 |
|`GET /companies/{co}/products/{p}/charts/deployment-by-product`|Monthly deployment by product type|
|`GET /companies/{co}/products/{p}/charts/collection-velocity`|Collection timing + bucket breakdown|
|`GET /companies/{co}/products/{p}/charts/denial-trend`       |Denial rate trend                  |
|`GET /companies/{co}/products/{p}/charts/cohort`             |Vintage cohort analysis            |
|`GET /companies/{co}/products/{p}/charts/actual-vs-expected` |Cumulative actual vs expected      |
|`GET /companies/{co}/products/{p}/charts/ageing`             |Active deal health + ageing        |
|`GET /companies/{co}/products/{p}/charts/revenue`            |Revenue analysis                   |
|`GET /companies/{co}/products/{p}/charts/concentration`      |Group/product concentration        |
|`GET /companies/{co}/products/{p}/charts/returns-analysis`   |Returns, discounts, new vs repeat, IRR|
|`GET /companies/{co}/products/{p}/charts/collection-curves`  |Expected vs actual collection curves  |
|`GET /companies/{co}/products/{p}/charts/dso`                |DSO metrics (curve-based, weighted, median, p95)|
|`GET /companies/{co}/products/{p}/charts/denial-funnel`      |Resolution pipeline funnel          |
|`GET /companies/{co}/products/{p}/charts/stress-test`        |Provider concentration shock scenarios|
|`GET /companies/{co}/products/{p}/charts/expected-loss`      |PD × LGD × EAD expected loss model  |
|`GET /companies/{co}/products/{p}/charts/loss-triangle`      |Denial development by vintage       |
|`GET /companies/{co}/products/{p}/charts/group-performance`  |Per-group collection/denial/DSO     |
|`GET /companies/{co}/products/{p}/charts/risk-migration`     |Roll-rate matrix + cure rates       |
|`GET /companies/{co}/products/{p}/validate`                  |Single-tape data quality checks     |
|`GET /companies/{co}/products/{p}/integrity/cached`          |Check for cached integrity results   |
|`GET /companies/{co}/products/{p}/integrity`                 |Run validation + consistency checks  |
|`POST /companies/{co}/products/{p}/integrity/report`         |Generate AI integrity report         |
|`GET /companies/{co}/products/{p}/integrity/report`          |Get cached AI integrity report       |
|`POST /companies/{co}/products/{p}/integrity/notes`          |Save analyst notes for questions     |
|`GET /companies/{co}/products/{p}/integrity/notes`           |Get saved analyst notes              |
|`POST /companies/{co}/products/{p}/chat`                     |AI data chat (multi-turn)          |
|`POST /companies/{co}/products/{p}/generate-report`          |Generate PDF report (streams bytes) |
|`GET /fx-rates`                                              |Foreign exchange rates              |
|`GET /companies/{co}/products/{p}/charts/silq/{chart_name}`  |Dynamic SILQ chart routing          |

**Portfolio Analytics endpoints (real data — DB or tape fallback):**
|Endpoint                                                     |Description                        |
|-------------------------------------------------------------|-----------------------------------|
|`GET /companies/{co}/products/{p}/portfolio/borrowing-base`  |Waterfall + KPIs + facility capacity|
|`GET /companies/{co}/products/{p}/portfolio/concentration-limits`|Limit cards + breaching items    |
|`GET /companies/{co}/products/{p}/portfolio/covenants`       |Covenant compliance status          |
|`GET /companies/{co}/products/{p}/portfolio/flow`            |Portfolio cash flow                 |
|`GET /companies/{co}/products/{p}/portfolio/facility-params` |Get facility configuration           |
|`POST /companies/{co}/products/{p}/portfolio/facility-params`|Save facility configuration          |
|`GET /companies/{co}/products/{p}/portfolio/invoices`        |Paginated invoice list (DB/tape)    |
|`GET /companies/{co}/products/{p}/portfolio/payments`        |Paginated payment ledger            |
|`GET /companies/{co}/products/{p}/portfolio/bank-statements` |Bank statement history + KPIs       |
|`GET /companies/{co}/products/{p}/portfolio/covenant-dates`  |Historical covenant evaluation dates|

**Integration API (authenticated, org-scoped — `/api/integration/`):**
|Endpoint                                          |Description                              |
|--------------------------------------------------|-----------------------------------------|
|`GET /api/integration/invoices`                   |Paginated invoice list (org-scoped)      |
|`POST /api/integration/invoices`                  |Create single invoice                    |
|`POST /api/integration/invoices/bulk`             |Bulk create invoices (up to 5,000)       |
|`PATCH /api/integration/invoices/{id}`            |Partial update invoice                   |
|`DELETE /api/integration/invoices/{id}`           |Delete invoice (cascade)                 |
|`GET /api/integration/invoices/{id}/payments`     |Paginated payments per invoice           |
|`POST /api/integration/invoices/{id}/payments`    |Create single payment                    |
|`POST /api/integration/payments/bulk`             |Bulk create payments (up to 5,000)       |
|`GET /api/integration/bank-statements`            |Paginated bank statements                |
|`POST /api/integration/bank-statements`           |Create bank statement (optional PDF)     |

All tape chart endpoints accept: `snapshot`, `as_of_date`, `currency` query params.
Chat endpoint also accepts `snapshot`, `currency`, `as_of_date` in the POST body (frontend sends them there).
Integration endpoints require `X-API-Key` header (SHA-256 hashed, org-scoped).
-----
## Navigation Architecture
**Hierarchy:** Company → Product → (Tape Analytics | Portfolio Analytics)

**Route structure:**
| Route | Component | Description |
|---|---|---|
| `/` | `Home` | Landing page — company grid |
| `/company/:co/:product/tape/:tab` | `TapeAnalytics` | 12-tab dashboard (tab slug in URL) |
| `/company/:co/:product/portfolio/:tab` | `PortfolioAnalytics` | 6-tab portfolio view (live data from DB/tape) |
| `/company/:co/:product/methodology` | `Methodology` | Definitions & formulas reference |

**Sidebar navigation:** 240px persistent sidebar on all company pages. Sections: Company name, Products (if multiple), Tape Analytics (12 links), Portfolio Analytics (6 links), Methodology. Active state: gold left border + gold text.

**URL-based tabs:** Active tab driven by `:tab` URL param (not React state). Users can bookmark/share specific views. Slugs: `overview`, `actual-vs-expected`, `deployment`, `collection`, `denial-trend`, `ageing`, `revenue`, `portfolio-tab`, `cohort-analysis`, `returns`, `risk-migration`, `data-integrity`, `borrowing-base`, `concentration-limits`, `covenants`, `invoices`, `payments`, `bank-statements`.

**Backward compat:** `/company/:co` and `/company/:co/:product` redirect to `tape/overview`.

**State management:** `CompanyContext` provides shared state (company, products, snapshots, config, currency, summary, etc.) consumed by both TapeAnalytics and PortfolioAnalytics.

-----
## Tape Analytics Tabs (12)
|Tab               |What It Shows                                                   |
|------------------|----------------------------------------------------------------|
|Overview          |10 KPI cards (incl curve-based DSO + HHI; DSO hidden on older tapes) + AI commentary + Data Chat|
|Actual vs Expected|Cumulative collected vs expected area chart + Today marker + 6 KPI cards (purchase price, discount, expected, collected/pending/denied with %)|
|Deployment        |Monthly capital deployed: by business type (new vs repeat) + by product type (stacked bars)|
|Collection        |Monthly collection rate + 3M avg + expected rate line (forecast benchmark) + cash collection breakdown by deal age|
|Denial Trend      |Monthly denial rate bars + 3M rolling average                   |
|Ageing            |Monthly stacked bars by outstanding amount (PV − Collected − Denied) per health status + cumulative donut + ageing bucket bars — all based on outstanding, not face value|
|Revenue           |Realised/unrealised stacked bars + gross margin line + KPI tiles|
|Portfolio         |Group concentration donut + HHI badges + portfolio health donut + ageing by purchase date donut + group perf table + top 10 deals + Owner/SPV donut + owner perf table (Mar 2026+ only)|
|Cohort Analysis   |Enhanced vintage table: up to 17 columns incl IRR, pending, loss rate, totals row, collection speed (90d/180d/360d %, Mar 2026+ only)|
|Returns           |Margin KPIs (realised margin = completed deals only, capital recovery), monthly returns chart, discount band analysis, new vs repeat + IRR KPIs, vintage chart, distribution histogram (when tape has IRR)|
|Risk & Migration  |Roll-rate matrix, cure rates, EL model (PD×LGD×EAD), stress test scenarios|
|Data Integrity    |Two-tape comparison: per-tape validation, cross-tape consistency, AI report + per-question notes|
Each non-overview tab (except Data Integrity) has a **TabInsight** component — a teal bar at the top with a one-click AI insight.
Dashboard controls (Tape only): Snapshot selector, As-of Date picker, Currency toggle (local ↔ USD), PDF Report button.

-----
## Portfolio Analytics Tabs (6) — Live Data ✅
|Tab                  |What It Shows                                                |
|---------------------|-------------------------------------------------------------|
|Borrowing Base       |4 KPI cards, waterfall table (gross → eligible → BB), advance rates by region, facility capacity bar, breaching shops|
|Concentration Limits |Summary bar (compliant/breach counts), 2-column grid of limit cards with progress bars, click-to-expand breaching items + adjustment suggestions|
|Covenants            |Covenant cards with threshold bars, calculation breakdowns, compliance badges, historical evaluation dates dropdown|
|Invoices             |Paginated table (7,697+ rows), eligible/ineligible tabs, search/filter, per-invoice action menu|
|Payments             |Payment ledger with ADVANCE/PARTIAL/FINAL badges, transaction filters, date range picker|
|Bank Statements      |Cash position KPI cards (balance, collection), historical statement list, PDF download links|

**Data source:** Portfolio Analytics reads from PostgreSQL database when configured (`DATABASE_URL`). Falls back to tape CSV/Excel files if DB not available. The computation engine (`core/portfolio.py`) works with tape-compatible DataFrames regardless of source.
-----
## Data Source Architecture
**Two distinct data pipelines feed the platform:**

| | Tape Analytics | Portfolio Analytics |
|---|---|---|
| **Source** | CSV/Excel files in `data/` | PostgreSQL database (fallback: tape files) |
| **Ingestion** | Manual upload by analyst | Inbound API from portfolio companies |
| **Refresh** | Point-in-time snapshots (monthly) | Real-time (as companies push data) |
| **Purpose** | Retrospective analysis, IC reporting | Live monitoring, borrowing base, covenants |
| **Backend module** | `core/analysis.py` + `core/loader.py` | `core/portfolio.py` + `core/db_loader.py` |

**DB-optional mode:** If `DATABASE_URL` is not set in `.env`, portfolio endpoints automatically fall back to computing from the latest tape CSV/Excel file. This allows the platform to run without PostgreSQL for tape-only analysis.

**Tape-compatible bridge:** `core/db_loader.py` maps database rows (Invoice + Payment records) to DataFrames with identical column names as CSV tapes. This means `core/portfolio.py` and `core/analysis.py` work identically regardless of data source — zero code changes needed.

**Integration API authentication:** Portfolio companies authenticate via `X-API-Key` header. Keys are generated with `scripts/create_api_key.py`, SHA-256 hashed, and stored in the `organizations` table. Each API key is scoped to one organization — queries automatically filter to that org's data.

**Database schema (6 tables):**
| Table | Purpose |
|---|---|
| `organizations` | Portfolio companies (Klaim, SILQ) with API key hash |
| `products` | Products per org with analysis_type, currency, facility_limit |
| `invoices` | Receivables pool (amount_due, status, customer, extra_data JSONB) |
| `payments` | Payment activity (ADVANCE/PARTIAL/FINAL types) |
| `bank_statements` | Cash position tracking with optional PDF file storage |
| `facility_configs` | Per-facility lending terms in JSONB (advance_rates, concentration_limits, covenants) |

-----
## Currency System
Supported: `AED (0.2723)`, `USD (1.0)`, `EUR (1.08)`, `GBP (1.27)`, `SAR (0.2667)`, `KWD (3.26)`.
Each product has a `config.json` with its reported currency. Frontend shows toggle between reported currency and USD. Backend applies multiplier via `apply_multiplier()` in `core/analysis.py`.
> TODO: Replace hardcoded FX rates with a live FX API call.
-----
## Dashboard Customization Philosophy
Each company/product has its own configured dashboard. The platform shares a common shell but specific views, metrics, and AI prompts are driven by asset class and available columns. Onboarding a new company requires designing the right views for that asset class.
**Current implementation:** Built around Klaim's healthcare receivables. Not yet abstracted for multi-asset-class use.
-----
## Key Architectural Decisions
- **`core/analysis.py`** — all pure data computation. No FastAPI, no I/O.
- **`core/config.py`** — per-product `config.json` stores currency and description.
- **Snapshot naming** — files must start with `YYYY-MM-DD_` for date parsing.
- **`filter_by_date()`** — filters deals to `Deal date <= as_of_date`.
- **`_load()` in main.py** — matches snapshots by `filename` or `date` field (fixed Feb 2026).
- **AICommentary caching** — stored in `CompanyContext` state, survives tab switches, clears on snapshot change.
- **API response extraction** — `api.js` extracts: `.commentary` for AI commentary, `.insight` for tab insights, `.answer` for chat responses.
- **Text contrast** — `--text-muted` updated from `#4A5568` to `#8494A7` for readability on dark theme.
- **IRR derivation** — backend calculates IRR for tapes that lack IRR columns (derived from purchase price, collected, deal dates).
- All AI calls use `claude-opus-4-6`.
- **`core/migration.py`** — multi-snapshot roll-rate analysis. Requires ≥2 snapshots. Matches deals by ID column across tapes.
- **`core/validation.py`** — single-tape integrity checks (dupes, date sanity, negatives, nulls, logical consistency).
- **Risk migration endpoint** — auto-selects the two most recent snapshots for comparison. Also bundles stress test + EL model results.
- **Data Integrity tab** — two-step workflow: Run Checks (fast, no API cost) → Generate AI Report (Claude API call). Results, reports, and notes cached as JSON files in `reports/{company}_{product}/`. Auto-loads cached results on tab load. Notes saved with 500ms debounce.
- **Data Chat history** — frontend sends `{role: 'ai', text: '...'}`, backend maps to Anthropic format `{role: 'assistant', content: '...'}`. Reads both `text` and `content` fields for compatibility.
- **Data Chat enriched context** — system prompt includes 7+ pre-computed data sections beyond basic KPIs: group performance (top 8 providers with collection/denial/DSO), active portfolio health (ageing buckets), DSO metrics, returns & margins, discount band performance, new vs repeat business, HHI concentration, plus (when available) IRR summary, collection speed by vintage, and owner/SPV allocation. Fallback instruction directs analysts to the full tape or deal team for deal-level questions.
- **Graceful degradation pattern** — new features that depend on Mar 2026 columns (curves, owner, IRR) check `if 'column' in df.columns` and return `{'available': False}` when missing. Frontend checks `.available` and hides sections entirely — no estimates, no placeholders.
- **DSO fix (Mar 2026)** — old method used `today - Deal date` (just deal age). New curve-based method uses `_estimate_dso_from_curves()` to find when 90% of collected amount arrived, interpolating between 30-day intervals. Returns `available: False` on tapes without curve columns.
- **Collection curves** — `compute_collection_curves()` aggregates expected/actual at 30-day intervals. Backend endpoint retained but **removed from dashboard** — aggregate view blends vintages at different life stages, making it misleading for IC audiences. Per-vintage collection speed is better served by the Cohort table (90d/180d/360d columns).
- **Owner/SPV breakdown** — `compute_owner_breakdown()` groups by `Owner` column, uses `Collected till date by owner` when available (450 deals differ from standard `Collected till date`).
- **`Actual IRR for owner`** — **excluded** from all analysis. Column has garbage data (mean ~2.56e44, likely parsing errors in source data).
- **Outstanding amount pattern** — Ageing and Portfolio health charts use `outstanding = PV - Collected - Denied` (clipped at 0) instead of face value. Shows actual risk exposure. Health `percentage` based on outstanding share.
- **Completed-only margins** — All margin calculations in Returns use completed deals only to avoid penalising vintages still collecting. `realised_margin` = `completed_margin`. Discount band, new vs repeat, and monthly margins also filtered to completed.
- **Expected collection rate** — Collection velocity endpoint returns `expected_rate = Expected till date / Purchase value` per month when column available (`has_forecast` flag). Frontend renders as blue dashed line alongside actual rate bars.
- **Sidebar navigation architecture** — Company pages use a persistent 240px sidebar (`Sidebar.jsx`) within `CompanyLayout`. Tabs are `<Link>` elements (not buttons). Active state: gold left border + text. Sidebar follows Methodology page's original pattern.
- **URL-based tab navigation** — Active tab stored in URL `:tab` param, not React state. Enables bookmarking/sharing. `TapeAnalytics` reads `useParams().tab`, maps slug to label via `SLUG_TO_LABEL`.
- **CompanyContext** — Central state provider extracted from old `Company.jsx`. Both `TapeAnalytics` and `PortfolioAnalytics` consume via `useCompany()` hook. Prevents re-fetches when switching between tape and portfolio views.
- **CompanyLayout** — Wraps `CompanyProvider` around `Sidebar` + `<Outlet>`. Simple flex layout: sidebar (240px fixed) + main content area (flex: 1).
- **Portfolio Analytics live data** — All 6 portfolio tabs now use real backend endpoints. `_portfolio_load()` in `main.py` auto-selects data source: DB if configured and has data, otherwise falls back to tape files. Returns tape-compatible DataFrame.
- **DB-optional architecture** — `core/database.py` checks for `DATABASE_URL` in env. If missing, all DB-touching code gracefully returns None. Portfolio endpoints fall back to tape data. App runs fine without PostgreSQL.
- **Tape-compatible DataFrame bridge** — `core/db_loader.py` maps Invoice+Payment DB records to DataFrames with identical column names as CSV tapes. `load_klaim_from_db()` and `load_silq_from_db()` handle company-specific mappings. Zero changes needed to analysis functions.
- **Integration API authentication** — `backend/auth.py` validates `X-API-Key` header via SHA-256 hash lookup. `get_current_org()` FastAPI dependency injects the authenticated Organization. All integration queries are org-scoped.
- **Bulk operations** — Integration API supports up to 5,000 invoices/payments per bulk request with per-item error tracking.
- **Tiered concentration limits** — Single-borrower limit scales with facility size per loan docs ($10M→20%, $20M→15%, >$20M→10%). Implemented in `core/portfolio.py` `_conc_threshold()`.
- **Facility config as JSONB** — `FacilityConfig` model stores advance_rates, concentration_limits, covenants as flexible JSON for per-facility customization.
- **Portfolio computation engine** — `core/portfolio.py` contains pure functions: `compute_borrowing_base()` (waterfall + eligibility), `compute_concentration_limits()` (4 limits with breach drill-down), `compute_covenants()` (5-6 per asset class), `compute_portfolio_flow()` (cash waterfall). Supports both Klaim and SILQ asset classes.
- **PDF report generation** — `generate_report.py` uses Playwright headless Chrome to screenshot all 11 tape tabs (excluding Data Integrity) via sidebar link navigation. Navigates to `/company/:co/:product/tape/:slug` URLs. ReportLab composes a professional PDF (dark cover page with LAITH branding, TOC, full-width tab screenshots). Backend `POST /generate-report` endpoint runs the script as a subprocess, streams the PDF via `FileResponse`, and auto-deletes the temp file via `BackgroundTask`. Frontend receives blob, creates `blob://` URL, opens in new tab. Nothing saved to disk — user saves manually from Chrome's PDF viewer. Playwright falls back to `channel="chrome"` (local Chrome) if managed Chromium is unavailable.
- **PDF report wait strategy** — 3-phase approach per tab: 4s initial mount wait → poll for "Loading..." spinners to disappear (max 20s, double-confirm) → 2s animation settle. ~6.5s per tab, ~70s total.
-----
## Design System — Dark Theme ✅
Full dark theme implemented. See color palette:
|Token           |Value    |Usage                                      |
|----------------|---------|-------------------------------------------|
|`--bg-base`     |`#0C1018`|Page background                            |
|`--bg-surface`  |`#111620`|Cards, panels                              |
|`--bg-nav`      |`#080B12`|Navbar                                     |
|`--border`      |`#1E2736`|All borders                                |
|`--accent-gold` |`#C9A84C`|Primary brand, active tab, AI panel        |
|`--accent-teal` |`#2DD4BF`|Collection rate, positive metrics, live dot|
|`--accent-red`  |`#F06060`|Denial rate, negative metrics              |
|`--accent-blue` |`#5B8DEF`|Pending/neutral metrics, deployment bars   |
|`--text-primary`|`#E8EAF0`|Main text                                  |
|`--text-muted`  |`#8494A7`|Secondary text (updated for contrast)      |
|`--text-faint`  |`#2A3548`|Labels, borders                            |
Typography: Inter for UI, IBM Plex Mono for numbers/data.
-----
## Key Backend Field Name Notes
- All chart endpoints return `Month` with capital M
- Collection velocity: data in `res.monthly[]`
- Revenue: data in `res.monthly[]`, totals in `res.totals{}`
- Cohort: data in `res.cohorts[]`
- Ageing: health in `res.health_summary[]` (`value` = outstanding, `face_value` = reference), buckets in `res.ageing_buckets[]` (`outstanding`, `purchase_value`), monthly health in `res.monthly_health[]`, `res.total_outstanding`, `res.total_active_value`
- Concentration: groups in `res.group[]`, top deals in `res.top_deals[]`, HHI in `res.hhi{}`, owner in `res.owner{}` (`available`, `owners[]`, `uses_owner_collected`)
- Returns analysis: `res.summary{}` (incl `has_irr`, IRR fields, `capital_recovery`, margins = completed deals only), `res.monthly[]` (margin = completed only, `completion_pct`), `res.discount_bands[]`, `res.new_vs_repeat[]`, `res.irr_by_vintage[]`, `res.irr_distribution[]`
- Collection curves: `res.available`, `res.curves[]` (per-vintage), `res.aggregate{points[]}` (portfolio)
- DSO: `res.available`, `res.weighted_dso`, `res.median_dso`, `res.p95_dso`, `res.by_vintage[]` (curve-based when available)
- Denial funnel: `res.stages[]`, `res.net_loss`, `res.recovery_rate`
- Stress test: `res.scenarios[]`, `res.base_collection_rate`
- Expected loss: `res.portfolio{}` (pd, lgd, ead, el, el_rate), `res.by_vintage[]`
- Group performance: `res.groups[]` (collection_rate, denial_rate, dso per group)
- Risk migration: `res.matrix[]`, `res.cure_rates{}`, `res.summary{}`, `res.stress_test{}`, `res.expected_loss{}`
- Validation: `res.critical[]`, `res.warnings[]`, `res.info[]`, `res.passed`, `res.total_rows`
- Consistency: `res.issues[]` (critical), `res.warnings[]`, `res.info[]`, `res.passed`
- Integrity run: `res.validation_old{}`, `res.validation_new{}`, `res.consistency{}`, `res.snapshot_old`, `res.snapshot_new`, `res.ran_at`
- Integrity report: `res.analysis_text`, `res.questions[]`, `res.pdf_path`, `res.generated_at`
- Integrity notes: `res.notes{}` (keyed by question index)
- Deployment by product: `res.monthly[]`, `res.products[]`
- Collection velocity: also returns `res.buckets[]`, `res.avg_days`, `res.median_days`, `res.total_completed`, `res.has_forecast`; monthly records include `expected_rate` when `Expected till date` column available
- Revenue: also returns `res.vat{}` (`available`, `vat_assets`, `vat_fees`, `total_vat`)
- Cohort: `res.cohorts[]` may include `collected_90d_pct`, `collected_180d_pct`, `collected_360d_pct` (when curve data available)
- Summary API returns: `total_deals`, `total_purchase_value`, `total_collected`, `total_denied`, `total_pending`, `total_expected`, `avg_discount`, `collection_rate`, `denial_rate`, `pending_rate`, `active_deals`, `completed_deals`, `dso_available`
- Snapshots API returns objects `{filename, date}` — must extract `.filename`
- Companies API may return objects — must extract `.name`
-----
## What's Working
- ✅ Full backend with all chart and AI endpoints (including returns-analysis)
- ✅ 12-tab React dashboard with dark theme
- ✅ AI commentary (cached, clears on snapshot change)
- ✅ Per-tab AI insights (TabInsight)
- ✅ Data chat (enriched context: group performance, ageing, DSO, margins, discount bands, new vs repeat, HHI; fallback for deal-level questions; answerable suggested questions)
- ✅ Currency toggle (local ↔ USD) across all charts and KPIs
- ✅ Snapshot switching — reloads all charts and KPIs correctly
- ✅ As-of Date picker — filters data across all views
- ✅ Loading indicators (gold animated bar + skeleton KPIs)
- ✅ Data integrity CLI with PDF report generation
- ✅ Enhanced cohort analysis (14 cols, IRR when available, totals row) — tested end-to-end
- ✅ Returns analysis tab (margins, discount bands, new vs repeat) — tested end-to-end
- ✅ Laith branding (styled logo in Navbar + Home, page title)
- ✅ Dark-theme SVG logo (replaces emoji + text mark)
- ✅ Favicon (Laith branded)
- ✅ Improved text contrast for readability
- ✅ .env scrubbed from git history, safely in .gitignore
- ✅ IRR calculation in backend for tapes lacking IRR columns (derived from purchase price, collected, deal dates)
- ✅ DSO (Days Sales Outstanding) — weighted, median, p95 on completed deals
- ✅ HHI (Herfindahl-Hirschman Index) — on Group and Product concentration
- ✅ Denial funnel / resolution pipeline (Total → Collected → Pending → Denied → Provisioned)
- ✅ Stress testing — top-1/3/5 provider shock scenarios
- ✅ Expected Loss model (PD × LGD × EAD from completed deal outcomes)
- ✅ Loss development triangle (denial by vintage age)
- ✅ Per-group performance table (collection rate, denial rate, DSO per provider)
- ✅ Roll-rate migration matrix across snapshots (cure rates, transition probabilities)
- ✅ Single-tape data quality validation (dupes, date sanity, negatives, nulls)
- ✅ Risk & Migration tab (11th tab) — institutional-grade risk analytics
- ✅ Enhanced Overview with 10 KPI cards (added DSO + HHI)
- ✅ Enhanced Concentration tab (HHI badges + group performance table)
- ✅ Methodology page (`/company/:name/methodology`) — company-scoped reference with definitions, formulas, rationale for all analytics; back-to-dashboard navigation; accessed via book icon in tab bar
- ✅ Data Integrity tab (12th tab) — pick two tapes to compare, per-tape validation + cross-tape consistency, cached results auto-load, AI report generation (separate button), per-question notes with debounced auto-save, PDF report saved to reports/
- ✅ Enhanced Actual vs Expected — 6 KPI summary cards (purchase price, discount, expected total, collected/pending/denied with % badges) + Today reference line
- ✅ Enhanced Deployment — dual charts: by business type (new/repeat) + by product type (new endpoint)
- ✅ Enhanced Collection — collection rate with 3M avg + cash collection breakdown by deal age (horizontal bars + donut + avg days outstanding)
- ✅ Enhanced Ageing — monthly stacked bars by health status (Healthy/Watch/Delayed/Poor) over time + cumulative donut, plus existing bucket bars
- ✅ Enhanced Portfolio — portfolio health donut + ageing by purchase date donut (side-by-side) added between concentration and performance sections
- ✅ **March 2026 tape analytics** (all gracefully degrade on older tapes):
  - Collection curves — removed from dashboard (aggregate view was misleading for IC; per-vintage collection speed covered by Cohort table). Backend endpoint retained.
  - IRR analysis — 4 KPIs (avg expected/actual IRR, spread, median), vintage bar chart, distribution histogram
  - Owner/SPV breakdown — concentration donut + performance table (6 owners: SPV1-4, KKTL, Wio)
  - Cohort collection speed — 90d/180d/360d % columns with SpeedHeat color coding
  - DSO fix — curve-based calculation (90% collection point), hidden on tapes without curve data
  - VAT summary in revenue endpoint (vat_assets + vat_fees)
  - Enriched Data Chat context with IRR, collection speed, owner sections
- ✅ March 2026 data tape added: `2026-03-03_uae_healthcare.csv` (7,697 deals, 60 columns)
- ✅ **Metric accuracy fixes** (completed-only margins, outstanding-based health):
  - Ageing tab: switched from face value to outstanding (PV − Collected − Denied) — AED 50.4M actual risk vs misleading AED 198.6M face value
  - Portfolio tab: health + ageing donuts aligned to outstanding metric
  - Returns tab: all margins (portfolio, monthly, discount bands, new vs repeat) now computed on completed deals only — Realised Margin 5.27% (was −4.16%). Added Capital Recovery KPI (95.84%)
  - Collection tab: added Expected Rate line (blue dashed) showing `Expected till date / Purchase value` per vintage — contextualises the rate cliff for recent months
- ✅ **One-click PDF Report** — gold "PDF Report" button in dashboard controls bar:
  - Playwright headless Chrome screenshots all 11 tabs (excl. Data Integrity)
  - ReportLab composes professional PDF: dark cover page (LAITH branding), TOC, tab pages with headers/footers
  - Streaming response — no files saved to disk; PDF opens in new browser tab as blob URL
  - Button states: idle (gold outline), generating (grey + spinner), error (red + retry)
  - ~70s generation time, 13-page ~2MB PDF
- ✅ **Sidebar navigation + URL-based routing** — Company pages use persistent sidebar with Tape Analytics (12 tabs) + Portfolio Analytics (3 tabs) + Methodology. Tabs are URL-driven (`/tape/:slug`, `/portfolio/:slug`), bookmarkable. Old horizontal tab bar replaced.
- ✅ **CompanyContext + CompanyLayout** — Shared state provider (`CompanyContext.jsx`) consumed by all company pages. `CompanyLayout.jsx` renders sidebar + `<Outlet>`. Extracted from old `Company.jsx` (deleted).
- ✅ **Landing page cleanup** — Removed duplicate logo (Navbar already shows it). Enriched company cards with product chips and snapshot counts. Companies API returns `{name, products, total_snapshots}`.
- ✅ **Portfolio Analytics UI (live data from DB/tape):**
  - Borrowing Base — 4 KPI cards, waterfall table, advance rates by region, facility capacity bar, breaching shops
  - Concentration Limits — summary bar, 2-column grid of limit cards with progress bars + compliance badges + click-to-expand breaching items
  - Covenants — covenant cards with threshold bars, calculation breakdowns, compliance distance warnings, historical evaluation dates
  - Invoices — paginated table (7,697+ rows), eligible/ineligible tabs, search/filter
  - Payments — payment ledger with ADVANCE/PARTIAL/FINAL badges, transaction filters
  - Bank Statements — cash position KPI cards, historical statement list
- ✅ **Phase 2A — PostgreSQL database:**
  - PostgreSQL 18.3 with SQLAlchemy 2.0 ORM + Alembic migrations
  - 6 tables: organizations, products, invoices, payments, bank_statements, facility_configs
  - DB-optional mode — app runs without PostgreSQL, falls back to tape data
  - Tape-compatible DataFrame bridge (`core/db_loader.py`) — zero changes to analysis functions
  - Seed script (`scripts/seed_db.py`) to populate DB from existing tape files
- ✅ **Phase 2B — Integration API:**
  - 12 inbound endpoints under `/api/integration/` for portfolio companies to push data
  - X-API-Key authentication (SHA-256 hashed, org-scoped)
  - Invoices: CRUD + bulk create (up to 5,000/request)
  - Payments: create + bulk create, linked to invoices
  - Bank statements: create with optional base64 PDF upload
  - API key generation CLI (`scripts/create_api_key.py`)
- ✅ **Phase 2C — Portfolio computation engine:**
  - `core/portfolio.py` — borrowing base waterfall, concentration limits (4 types, tiered thresholds), covenants (5-6 per asset class), portfolio cash flow
  - Supports both Klaim (receivables factoring) and SILQ (POS lending) asset classes
  - `_portfolio_load()` auto-selects data source (DB → tape fallback)
-----
## Known Gaps & Next Steps
**Short term:**
- [x] Onboard SILQ — POS lending asset class (analysis module, validation, tests, 1 tape live)
- [ ] SILQ — add more tapes + expand dashboard coverage
- [ ] Add `core/analysis.py` unit tests
- [ ] Replace hardcoded FX rates with live API
- [x] Startup script — `start.ps1` boots both servers + opens browser
**Phase 2 — Borrowing Base Monitoring ✅ COMPLETE:**
- [x] PostgreSQL 18.3 database + SQLAlchemy ORM + Alembic migrations
- [x] Integration API (12 endpoints) with X-API-Key auth
- [x] Portfolio computation engine (borrowing base, concentration, covenants)
- [x] DB-optional fallback to tape data
- [x] Frontend: 6 portfolio tabs with live data
- [x] Seed script + API key generation CLI
**Phase 2 — Remaining polish:**
- [ ] Facility params input UI (edit advance rates, concentration limits, covenants from frontend)
- [ ] Breach notification system (email/Slack alerts on covenant breach)
- [ ] Portfolio company onboarding flow (self-service API key provisioning)
**Phase 3 (Team & Deployment):**
- [ ] Cloud deployment
- [ ] Role-based access (RBAC)
- [ ] Scheduled report delivery
- [ ] Real-time webhook notifications to portfolio companies
-----
## Environment
- **Machine:** Windows (PowerShell)
- **Python:** 3.14.3, virtual environment at `credit-platform/venv/`
- **Node:** v24
- **PostgreSQL:** 18.3 (local, default port 5432)
- **Database:** `laith_credit` (user: `laith`, password: `laith`)
- **Repo:** https://github.com/sharifeid-eng/credit-platform
- **Required `.env`:** NEVER commit this file
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  DATABASE_URL=postgresql://laith:laith@localhost:5432/laith_credit
  ```
  `DATABASE_URL` is optional — app works without it (tape-only mode). When set, Portfolio Analytics reads from PostgreSQL.
-----
## .env Safety Checklist (run if unsure)
```powershell
# Check if .env is in .gitignore
Select-String -Path .gitignore -Pattern "\.env"
# Check if .env is being tracked by git
git ls-files .env
# If this returns ".env", it's tracked and must be removed:
git rm --cached .env
git commit -m 'Remove .env from tracking'
git push origin main
```
**PowerShell git commit note:** Always use single quotes for commit messages in PowerShell:
```powershell
git commit -m 'your message here'
```
