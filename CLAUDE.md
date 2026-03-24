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
- View interactive dashboards with per-company analysis tabs (Klaim: 12 tabs, SILQ: 8 tabs — bespoke per asset class)
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
- **SILQ** — POS lending (BNPL & RBF), KSA. Data in SAR. Live dataset: `data/SILQ/KSA/`
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

**SILQ data notes:**
- **Tape available:** Jan 2026 (xlsx, 3 sheets — "Portfolio Commentary" + "BNPL+RBF_NE" + "RBF_LT")
- **1,915 loans total** (multi-sheet), 19 columns per sheet, SAR currency
- 3 products: `BNPL` (969 loans), `RBF_Exc` (943 loans from RBF_LT sheet), `RBF_NE` (3 loans)
- Column names include currency suffix: `Disbursed_Amount (SAR)`, `Outstanding_Amount (SAR)`, etc.
- 3 statuses: `Closed`, `CURRENT`, `OVERDUE` (normalised to title case by loader)
- Total disbursed: SAR 325.2M, Outstanding: SAR 76.2M
- **RBF_LT sheet lacks `Margin Collected` column** — revenue is structured differently in RBF (baked into repayment). Loader fills with 0.0 and marks `_margin_synthetic = True`. Yield tab shows info note.
- Portfolio Commentary sheet contains company-written narrative — displayed in Overview tab
- DPD computed as `max(0, ref_date - Repayment_Deadline)`, 0 for Closed loans. **ref_date = tape date or as-of date** (not today's date)
- `Outstanding_Amount` can exceed `Disbursed_Amount` (includes accrued margin) — not a data error
- **PAR methodology:** GBV-weighted (Outstanding of DPD>X loans / Total Outstanding of active loans), NOT count-based
- **Backward-date caveat:** When as-of date < tape date, balance columns (outstanding, collected, overdue, margins) still reflect tape date. Only deal selection is filtered. Dashboard shows warning banner + per-KPI ⚠ markers on stale metrics.
-----
## Long-Term Vision (3 Phases)
**Two distinct modes in one platform:**
- **Tape Analytics** — manual tape uploads, backward-looking deep analysis, bespoke per asset class. Analyst-driven. This is the proprietary edge.
- **Portfolio Analytics** — live facility monitoring via API integrations. Operational, real-time. Competes with / replaces Cascade Debt and Creditit for ACP's specific needs.

### Phase 1 — Tape Analytics ✅ (current)
- Manual file upload workflow (CSV/Excel loan tapes)
- AI-powered dashboards per company/product (Klaim: 12 tabs, SILQ: 9 tabs)
- Consistency checks across snapshots
- Investment committee-ready commentary
- Bespoke analysis per asset class (receivables factoring vs POS lending)
### Phase 2 — Portfolio Analytics (Borrowing Base Monitoring) ✅
- Real borrowing base calculations from tape data (compliance cert formulas)
- Automated eligibility testing against lending criteria
- Concentration limit tracking with live thresholds
- Advance rate calculations from actual portfolio data
- Covenant monitoring and breach alerts (auto-check from tape)
- `core/portfolio.py` computation engine with auto-dispatch (SILQ + Klaim)
- Frontend wired to 6 live API endpoints (no more mock data)
- **Future:** Live API connections to portfolio company databases for real-time feeds
### Phase 3 — Deployment & Team Access
- Cloud deployment on Railway (~$5/mo) — always-on, no laptop dependency
- Role-based access (analyst vs IC vs read-only)
- Scheduled report delivery
- Direct API integrations with portfolio companies' loan management systems (like Cascade's native DB connectors)
- Real-time covenant monitoring with automated alerts
-----
## Tech Stack
- **Backend:** Python, FastAPI (`localhost:8000`), Pandas, Anthropic API (`claude-opus-4-6`), ReportLab (PDF)
- **Frontend:** React (Vite), Tailwind CSS, Recharts, React Router, Axios (`localhost:5173`)
- **AI:** Anthropic API — portfolio commentary, per-tab insights, data chat, PDF integrity reports
- **PDF Reports:** Playwright (headless Chrome) for dashboard screenshots + ReportLab for PDF composition
- **Data:** CSV/Excel files stored locally under `data/`
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
├── .env                    # API key — NEVER committed to GitHub
├── .env.example            # Placeholder showing required env vars
├── .gitignore              # Must include: .env, node_modules/, venv/, __pycache__/, reports/
├── backend/
│   └── main.py             # FastAPI app — all REST endpoints
├── core/
│   ├── analysis.py         # Klaim pure data computation functions (no I/O)
│   ├── analysis_silq.py    # SILQ pure data computation functions (no I/O)
│   ├── loader.py           # File discovery, snapshot loading (multi-sheet Excel, malformed headers)
│   ├── config.py           # Per-product config (currency, description, analysis_type) via config.json
│   ├── consistency.py      # Snapshot-to-snapshot data integrity checks
│   ├── migration.py        # Multi-snapshot roll-rate & cure-rate analysis
│   ├── validation.py       # Klaim single-tape data quality checks
│   ├── validation_silq.py  # SILQ single-tape data quality checks
│   ├── portfolio.py        # Portfolio analytics engine (BB, conc limits, covenants) — SILQ + Klaim
│   └── reporter.py         # AI-generated PDF data integrity reports (ReportLab)
├── tests/
│   ├── test_analysis_klaim.py  # Klaim unit tests
│   └── test_analysis_silq.py   # SILQ unit tests (99+ tests total)
├── data/
│   └── {company}/
│       └── {product}/
│           ├── config.json
│           ├── facility_params.json  # Saved facility parameters (auto-generated)
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
│   │   │   ├── TapeAnalytics.jsx    # Multi-company tape dashboard (Klaim 12 tabs, SILQ 8 tabs)
│   │   │   ├── PortfolioAnalytics.jsx  # 3-tab portfolio view (live data from API)
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
│   │   │   │   │   ├── DenialFunnelChart.jsx     # Resolution pipeline funnel visualization
│   │   │   │   └── DataIntegrityChart.jsx    # Two-tape comparison, validation, AI report + notes
│   │   │   ├── silq/                        # SILQ-specific chart components
│   │   │   │   ├── DelinquencyChart.jsx     # DPD buckets, top overdue shops, monthly trend
│   │   │   │   ├── SilqCollectionsChart.jsx # Monthly collections, product comparison
│   │   │   │   ├── SilqConcentrationChart.jsx # Shop/product concentration, utilization
│   │   │   │   ├── SilqCohortTable.jsx      # Vintage table with heat-coded metrics
│   │   │   │   ├── YieldMarginsChart.jsx    # Margin trends, by product/tenure
│   │   │   │   └── TenureAnalysisChart.jsx  # Distribution, performance by band
│   │   │   └── portfolio/
│   │   │       ├── BorrowingBase.jsx         # Waterfall, KPIs, advance rates, facility capacity
│   │   │       ├── ConcentrationLimits.jsx   # Limit cards with compliance badges
│   │   │       ├── Covenants.jsx             # Covenant cards with threshold bars
│   │   │       ├── WaterfallTable.jsx        # Borrowing base waterfall table
│   │   │       ├── LimitCard.jsx             # Concentration limit card component
│   │   │       ├── CovenantCard.jsx          # Covenant card with threshold visualization
│   │   │       ├── ComplianceBadge.jsx       # Shared Compliant/Breach badge
│   │   │       └── mockData.js               # All mock data for portfolio tabs
│   │   ├── styles/
│   │   │   ├── chartTheme.js
│   │   │   └── tokens.css
│   │   └── services/
│   │       └── api.js
│   └── package.json
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
**SILQ-specific chart endpoints** (dispatched via `analysis_type` in config.json):
|Endpoint                                                     |Description                        |
|-------------------------------------------------------------|-----------------------------------|
|`GET /companies/{co}/products/{p}/charts/silq/delinquency`   |DPD buckets, top overdue shops, monthly trend|
|`GET /companies/{co}/products/{p}/charts/silq/collections`   |Monthly collections, product comparison|
|`GET /companies/{co}/products/{p}/charts/silq/concentration` |Shop/product concentration, utilization|
|`GET /companies/{co}/products/{p}/charts/silq/cohort`        |Vintage cohort table               |
|`GET /companies/{co}/products/{p}/charts/silq/yield-margins` |Margin trends, by product/tenure   |
|`GET /companies/{co}/products/{p}/charts/silq/tenure`        |Tenure distribution, performance   |
|`GET /companies/{co}/products/{p}/charts/silq/borrowing-base`|Waterfall, eligible amount         |
|`GET /companies/{co}/products/{p}/charts/silq/covenants`     |5 covenant compliance tests        |
**Portfolio Analytics endpoints** (auto-dispatch to SILQ or Klaim via `config.analysis_type`):
|Endpoint                                                     |Description                        |
|-------------------------------------------------------------|-----------------------------------|
|`GET /companies/{co}/products/{p}/portfolio/borrowing-base`   |Waterfall, KPIs, advance rates, facility capacity|
|`GET /companies/{co}/products/{p}/portfolio/concentration-limits`|Limit cards with compliance status|
|`GET /companies/{co}/products/{p}/portfolio/covenants`        |Covenant tests with breakdowns     |
|`GET /companies/{co}/products/{p}/portfolio/flow`             |Monthly origination waterfall      |
|`GET /companies/{co}/products/{p}/portfolio/facility-params`  |Load saved facility parameters     |
|`POST /companies/{co}/products/{p}/portfolio/facility-params` |Save facility parameters           |
All chart endpoints accept: `snapshot`, `as_of_date`, `currency` query params.
Chat endpoint also accepts `snapshot`, `currency`, `as_of_date` in the POST body (frontend sends them there).
Summary, validate, AI commentary, AI tab insight, and chat endpoints auto-dispatch to SILQ-specific logic when `config.analysis_type == 'silq'`.
-----
## Navigation Architecture
**Hierarchy:** Company → Product → (Tape Analytics | Portfolio Analytics)

**Route structure:**
| Route | Component | Description |
|---|---|---|
| `/` | `Home` | Landing page — company grid |
| `/company/:co/:product/tape/:tab` | `TapeAnalytics` | 12-tab dashboard (tab slug in URL) |
| `/company/:co/:product/portfolio/:tab` | `PortfolioAnalytics` | 3-tab portfolio view (live data) |
| `/company/:co/:product/methodology` | `Methodology` | Definitions & formulas reference |

**Sidebar navigation:** 240px persistent sidebar on all company pages. Sections: Company name, Products (if multiple), Tape Analytics (12 links), Portfolio Analytics (3 links), Methodology. Active state: gold left border + gold text.

**URL-based tabs:** Active tab driven by `:tab` URL param (not React state). Users can bookmark/share specific views. Slugs: `overview`, `actual-vs-expected`, `deployment`, `collection`, `denial-trend`, `ageing`, `revenue`, `portfolio-tab`, `cohort-analysis`, `returns`, `risk-migration`, `data-integrity`, `borrowing-base`, `concentration-limits`, `covenants`.

**Backward compat:** `/company/:co` and `/company/:co/:product` redirect to `tape/overview`.

**State management:** `CompanyContext` provides shared state (company, products, snapshots, config, currency, summary, etc.) consumed by both TapeAnalytics and PortfolioAnalytics.

-----
## Klaim Tape Analytics Tabs (12)
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
## SILQ Tape Analytics Tabs (9)
|Tab               |What It Shows                                                   |
|------------------|----------------------------------------------------------------|
|Overview          |10 KPI cards (Disbursed, Outstanding, Overdue, Collection Rate, PAR30, PAR90, Active, Avg Tenure, HHI Shop, Total Repaid) + AI commentary + Data Chat|
|Delinquency       |3 PAR KPI cards + DPD bucket distribution chart + Top 10 overdue shops + Monthly delinquency trend (overdue rate + PAR30)|
|Collections       |4 KPI cards (repaid, rate, margin, principal) + Monthly collections ComposedChart (stacked principal+margin + rate line) + Product comparison|
|Concentration     |3 KPI cards (HHI, top shop, total shops) + Shop concentration pie + Product mix pie + Credit utilization bars + Loan size distribution|
|Cohort Analysis   |Vintage table: deals, disbursed, repaid, outstanding, overdue, collection %, overdue %, PAR30 %, avg tenure — heat-coded cells + totals row|
|Yield & Margins   |3 KPI cards (margin rate, realised margin, total margin) + Monthly margin trend + By product + By tenure band|
|Tenure Analysis   |2 KPI cards (avg/median tenure) + Distribution histogram + Performance by tenure band (grouped bars) + By product|
|Covenants         |5 covenant cards: PAR30 ≤ 10%, PAR90 ≤ 5%, Collection Ratio > 33% (3M avg), Repayment at Term > 95%, LTV ≤ 75% (partial). Compliance badges, threshold bars, calculation breakdowns. Values reconcile with Dec 2025 compliance certificate.|
|Data Integrity    |Two-tape comparison: per-tape validation, cross-tape consistency (reuses Klaim Data Integrity infrastructure)|
Each non-overview tab has a **TabInsight** component with one-click AI insight.
Dashboard controls: Snapshot selector, As-of Date picker, Currency toggle (SAR ↔ USD). PDF Report button hidden for SILQ.

-----
## Portfolio Analytics Tabs (3) — Live Data
|Tab                  |What It Shows                                                |
|---------------------|-------------------------------------------------------------|
|Borrowing Base       |4 KPI cards, waterfall table (gross → eligible → BB), advance rates by segment, facility capacity bar|
|Concentration Limits |Summary bar (compliant/breach counts), 2-column grid of limit cards with progress bars|
|Covenants            |Covenant cards with threshold bars, calculation breakdowns, compliance badges|

**Data source:** Real-time computation from loan tape data via `core/portfolio.py`. Auto-dispatches to SILQ or Klaim computation based on `config.analysis_type`. Frontend fetches from `/portfolio/borrowing-base`, `/portfolio/concentration-limits`, `/portfolio/covenants` endpoints.
-----
## Currency System
Supported: `AED (0.2723)`, `USD (1.0)`, `EUR (1.08)`, `GBP (1.27)`, `SAR (0.2667)`, `KWD (3.26)`.
Each product has a `config.json` with its reported currency. Frontend shows toggle between reported currency and USD. Backend applies multiplier via `apply_multiplier()` in `core/analysis.py`.
FX rates are fetched live on backend startup (with hardcoded fallback if API unavailable).
-----
## Dashboard Customization Philosophy
Each company/product has its own configured dashboard. The platform shares a common shell but specific views, metrics, and AI prompts are driven by asset class and available columns. Onboarding a new company requires designing the right views for that asset class.
**Current implementation:** Two asset classes live — Klaim (healthcare receivables, 12 tape tabs) and SILQ (POS lending, 9 tape tabs). `core/portfolio.py` auto-dispatches to asset-class-specific computations via `config.analysis_type`.
-----
## Key Architectural Decisions
- **Multi-company dispatch** — `config.json` has `analysis_type` field (`"klaim"` or `"silq"`) that routes endpoints to the correct analysis module. `_get_analysis_type()` helper in `main.py`. Each company has its own `core/analysis_*.py` and `core/validation_*.py`.
- **Per-product tab config** — `config.json` has `tabs` array driving `Sidebar.jsx` dynamically. Falls back to `DEFAULT_TAPE_TABS` (Klaim's 12 tabs) when no `tabs` in config.
- **SILQ chart routing** — Generic `/charts/silq/{chart_name}` endpoint dispatches via `SILQ_CHART_MAP` dict to the correct compute function.
- **Multi-sheet Excel loading** — `core/loader.py` has `load_silq_snapshot()` for SILQ: loads all data sheets, separates Portfolio Commentary, normalises columns (Loan_Type→Product, status to title case, Shop_ID to str), fills missing `Margin Collected` with 0.0 + `_margin_synthetic` flag, and `pd.concat`s into one DataFrame. Original `load_snapshot()` for Klaim picks the sheet with most data rows. Both detect malformed headers (all numeric/Unnamed columns) and reload with `header=1`.
- **DPD ref_date** — `_dpd(df, ref_date)` uses tape date or as-of date, not today. All compute functions pass `ref_date` through. This ensures PAR/DPD metrics reflect the correct point in time.
- **PAR methodology** — All SILQ PAR ratios are GBV-weighted: `Outstanding of DPD>X / Total Outstanding of active loans`. Klaim uses GBV-weighted collection/denial/pending rates. Klaim PD (Expected Loss) is intentionally count-based (probability metric).
- **Backward-date caveat system** — `CompanyContext` stores `snapshotDate` from date-range API and derives `isBackdated = asOfDate < snapshotDate`. When true: `BackdatedBanner.jsx` renders a gold warning bar below controls; `KpiCard.jsx` accepts `stale` prop showing ⚠ icon on balance-derived KPIs. Overview tabs (both Klaim and SILQ) mark stale vs accurate KPIs.
- **`core/analysis.py`** — Klaim pure data computation. No FastAPI, no I/O.
- **`core/analysis_silq.py`** — SILQ pure data computation. Column aliases map short names to actual names with currency suffix (e.g., `C_DISBURSED = 'Disbursed_Amount (SAR)'`). `_safe()` converts numpy types for JSON serialization.
- **`core/config.py`** — per-product `config.json` stores currency, description, analysis_type, and tabs.
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
- **Portfolio Analytics engine** — `core/portfolio.py` (1139 lines) computes borrowing base, concentration limits, and covenants for both SILQ and Klaim. Auto-dispatches via `config.analysis_type`. Frontend fetches live data from 6 portfolio API endpoints. Facility params (corporate-level data) persist as JSON in `data/{company}/{product}/facility_params.json`.
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
- ✅ **Portfolio Analytics (live data):**
  - `core/portfolio.py` — computation engine (1139 lines) with auto-dispatch for SILQ and Klaim
  - 6 backend API endpoints: borrowing-base, concentration-limits, covenants, flow, facility-params (GET + POST)
  - Frontend wired to real APIs — Borrowing Base, Concentration Limits, Covenants tabs show live computed data
  - SILQ: DPD-based ineligibility, tiered concentration (per facility size), 5 covenants (PAR30/90, collection ratio, repayment at term, LTV)
  - Klaim: Outstanding-based waterfall, 5 concentration limits (single receivable, top-10, customer, payer, extended age), 6 covenants
  - Facility params persistence (corporate-level data: facility limit, drawn, cash balance, advance rates)
- ✅ **SILQ onboarded** — full multi-company architecture:
  - `core/analysis_silq.py` — 8 compute functions (summary, delinquency, collections, concentration, cohorts, yield, tenure, borrowing base)
  - `core/validation_silq.py` — SILQ-specific data quality checks
  - `core/loader.py` — multi-sheet Excel support, malformed header detection
  - Backend dispatch via `analysis_type` in config.json → SILQ-specific logic for summary, charts, validation, AI commentary, AI tab insight, chat
  - 7 SILQ chart endpoints under `/charts/silq/{chart_name}`
  - 6 frontend chart components in `components/charts/silq/`
  - Dynamic sidebar tabs from config.json (8 SILQ tabs vs 12 Klaim tabs)
  - `TapeAnalytics.jsx` dispatches to `SilqTabContent` or `KlaimTabContent` based on `analysisType`
  - SILQ Overview with 10 bespoke KPIs (PAR30/60/90, HHI shop, avg tenure, etc.)
  - AI commentary and Data Chat with SILQ-specific prompts and enriched context
  - Currency toggle SAR ↔ USD working
  - Jan 2026 tape: 1,915 loans (3 sheets), 3 products (BNPL + RBF_Exc + RBF_NE), SAR 325.2M disbursed
- ✅ **Multi-sheet SILQ loader** — loads all data sheets from Excel, normalises columns across BNPL and RBF_LT sheets, extracts Portfolio Commentary text
- ✅ **Portfolio Commentary panel** — company-written narrative from tape's Commentary sheet displayed in SILQ Overview
- ✅ **GBV-weighted PAR** — all SILQ PAR ratios (6 calculation sites) corrected from count-based to Outstanding Amount-weighted
- ✅ **DPD ref-date fix** — `_dpd()` uses tape/as-of date instead of today; PAR90 now matches Commentary's SAR 1.10M exactly
- ✅ **RBF margin note** — info note on Yield tab explaining RBF_Exc 0% margin (source sheet lacks Margin Collected column)
- ✅ **Backward-date caveat system** — gold warning banner + per-KPI ⚠ stale indicators when as-of date < tape date. Marks balance-derived metrics (outstanding, collected, overdue, rates, margins) while leaving accurate metrics (disbursed, counts, tenure, discount) unmarked
- ✅ **Compliance certificate reconciliation** — verified dashboard data aligns with company Commentary (Jan 31) and Dec 2025 compliance cert (methodology differences documented)
- ✅ **Unit tests** — 99 tests across `tests/test_analysis_silq.py` (59) and `tests/test_analysis_klaim.py` (40). Covers all compute functions, DPD logic, GBV-weighted PAR, compliance cert reconciliation, Commentary alignment, covenant monitoring. Run: `python -m pytest tests/ -v`
- ✅ **Live FX rates** — `core/config.py` fetches from `open.er-api.com` (free, no key). 1-hour cache, automatic fallback to hardcoded rates. `GET /fx-rates` endpoint returns rates + source (`live` or `fallback`). EUR/GBP rates now current.
- ✅ **SILQ Covenant monitoring** — 9th SILQ tab. Auto-checks 5 facility covenants from tape data: PAR30 ≤ 10% (5.5%), PAR90 ≤ 5% (1.4%), Collection Ratio > 33% (96.4% 3M avg), Repayment at Term > 95% (97.2%), LTV ≤ 75% (partial — needs corporate data). Values reconcile with Dec 2025 compliance certificate. Reuses `CovenantCard` + `ComplianceBadge` components.
-----
## Known Gaps & Next Steps
**Completed:**
- [x] Onboard SILQ — POS lending asset class (3 products, multi-sheet loader, 9 tabs)
- [x] Add `core/analysis.py` unit tests (99 tests passing)
- [x] Replace hardcoded FX rates with live API
- [x] Startup script — `start.ps1` boots both servers + opens browser
- [x] Covenant monitoring alerts — auto-check PAR30, PAR90, Collection Ratio, Repayment at Term, LTV
- [x] Compliance cert reconciliation — verified against Dec 2025 cert and Jan 2026 Commentary
- [x] GBV-weighted PAR, DPD ref-date fix, backward-date caveat system
- [x] SILQ-specific Methodology page
- [x] Portfolio analytics computation engine — `core/portfolio.py` with auto-dispatch for SILQ and Klaim
- [x] Frontend portfolio tabs wired to real backend APIs (replaced mock data)
- [x] 6 portfolio API endpoints (borrowing base, concentration limits, covenants, flow, facility params)
- [x] Facility params persistence (corporate-level data saved as JSON)
**Short term:**
- [ ] SILQ Data Integrity tab — needs second tape for cross-tape consistency checks
- [ ] Facility params input UI panel (currently no frontend for editing facility params)
- [ ] Portfolio flow tab UI (backend endpoint exists, no frontend tab yet)

**SILQ Compliance Certificate — Extracted Formulas (Dec 2025 cert, reconciliation Excel at `Downloads/SILQ_KSA_Compliance_Reconciliation.xlsx`):**

| # | Covenant | Formula | Threshold | Cert Value | Computable from tape? |
|---|----------|---------|-----------|------------|----------------------|
| 1 | Debt/Equity | Corporate-level | ≤ 3.0x | 1.2x | ❌ Off-tape |
| 2 | Min Cash Balance | Cash / max(month burn, 3m avg) | b > a | 57.8M > 21.1M | ❌ Off-tape |
| 3 | PAR 30 | GBV >30 DPD / GBV outstanding (active) | ≤ 10% | 1.6% | ✅ Already live |
| 4 | Collection Ratio | 3-month avg of (Repaid / Collectable) by maturity month | > 33% | 95.53% | ✅ Already live |
| 5 | Repayment at Term | Collections / GBV for loans maturing 3-6 months prior | > 95% | 97.33% | ✅ Already live |
| 6 | LTV | Facility outstanding / (Receivables + Cash) | ≤ 75% | 74.85% | ⚠️ Partial (receivables yes, facility/cash no) |

**Borrowing base waterfall (from cert):**
1. Total A/R = sum of outstanding for active loans (SAR 69.3M at Dec 31)
2. Ineligible = DPD>90 + concentration excess + age violations
3. Eligible = Total A/R − Ineligible
4. Advance rate discount (SILQ-specific rates TBD from facility agreement)
5. Borrowing Base = Eligible × Advance Rate

**Key reconciliation findings:**
- PAR30: Cert 1.6% (Dec 31) vs tape 5.5% (Jan 31) — increase due to one month aging, directionally consistent
- Collection Ratio: Cert 95.53% 3M avg — tape rates higher because extra month of collections occurred
- Repayment at Term: Cert 97.33% vs tape 96.86% — Δ 0.47pp, within expected tolerance
- LTV: 74.85%, only 15bps below 75% limit — tightest covenant, depends on cash injection
**Phase 3 (Deployment & Live Monitoring):**
- [ ] Cloud deployment — Railway (~$5/mo), deploys from GitHub, auto-HTTPS. Data files committed to repo (small enough). Add simple auth before exposing.
- [ ] Role-based access (analyst vs IC vs read-only)
- [ ] Scheduled report delivery
- [ ] Live API integrations — connect to portfolio company databases for real-time Portfolio Analytics (Cascade Debt / Creditit alternative). Tape Analytics stays manual.
-----
## Environment
- **Machine:** Windows (PowerShell)
- **Python:** 3.14.3, virtual environment at `credit-platform/venv/`
- **Node:** v24
- **Repo:** https://github.com/sharifeid-eng/credit-platform
- **Required `.env`:** `ANTHROPIC_API_KEY=sk-ant-...` in project root — NEVER commit this file
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
