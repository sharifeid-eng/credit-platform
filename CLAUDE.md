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
- **SILQ** — POS lending, KSA (Saudi Arabia). Data in SAR. Live dataset: `data/SILQ/KSA/` (1 tape: Jan 2026, 1,915 loans across 2 sheets: BNPL+RBF_NE + RBF_LT). Config: `analysis_type: "silq"`.
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
### Phase 1 — Loan Tape Analysis & Dashboards ✅ (current)
- Manual file upload workflow
- AI-powered dashboards per company/product
- Consistency checks across snapshots
- Investment committee-ready commentary
### Phase 2 — Borrowing Base Monitoring (backend ✅, frontend in progress)
- ✅ Backend computation engine for BB, concentration limits, covenants (both Klaim + SILQ)
- ✅ API endpoints with auto-dispatch by company type
- ✅ Facility params persistence (user-entered corporate-level data)
- Frontend wiring needed: connect portfolio components to real API, facility params input panel
- Covenant monitoring and breach alerts with notifications
### Phase 3 — Team & IC Viewing Layer
- Role-based access (analyst vs IC vs read-only)
- Scheduled report delivery
- Direct API integrations with portfolio companies' accounting or loan management systems
- Cloud deployment so the app runs 24/7
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
│   ├── analysis_silq.py    # SILQ tape analytics (8 compute functions, DPD/PAR-based)
│   ├── portfolio.py        # Portfolio Analytics engine — BB, concentration, covenants (both companies)
│   ├── loader.py           # File discovery, snapshot loading (incl. load_silq_snapshot multi-sheet)
│   ├── config.py           # Per-product config (currency, description) via config.json
│   ├── consistency.py      # Snapshot-to-snapshot data integrity checks
│   ├── migration.py        # Multi-snapshot roll-rate & cure-rate analysis
│   ├── validation.py       # Single-tape data quality checks (Klaim)
│   ├── validation_silq.py  # SILQ-specific tape validation (14 checks)
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
│   │   │       ├── ConcentrationLimits.jsx   # Limit cards with compliance badges
│   │   │       ├── Covenants.jsx             # Covenant cards with threshold bars
│   │   │       ├── WaterfallTable.jsx        # Borrowing base waterfall table
│   │   │       ├── LimitCard.jsx             # Concentration limit card component
│   │   │       ├── CovenantCard.jsx          # Covenant card with threshold visualization
│   │   │       ├── ComplianceBadge.jsx       # Shared Compliant/Breach badge
│   │   │       └── mockData.js               # Fallback mock data (to be replaced by API calls)
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
|`GET /companies/{co}/products/{p}/portfolio/borrowing-base`  |BB waterfall, KPIs, advance rates, facility|
|`GET /companies/{co}/products/{p}/portfolio/concentration-limits`|Concentration limits with compliance  |
|`GET /companies/{co}/products/{p}/portfolio/covenants`       |Covenant compliance tests              |
|`GET /companies/{co}/products/{p}/portfolio/flow`            |Monthly origination waterfall (SILQ)   |
|`GET /companies/{co}/products/{p}/portfolio/facility-params` |Load saved facility parameters         |
|`POST /companies/{co}/products/{p}/portfolio/facility-params`|Save facility parameters               |
All chart endpoints accept: `snapshot`, `as_of_date`, `currency` query params.
Portfolio endpoints auto-dispatch to SILQ or Klaim functions based on `config.json` `analysis_type`.
Chat endpoint also accepts `snapshot`, `currency`, `as_of_date` in the POST body (frontend sends them there).
-----
## Navigation Architecture
**Hierarchy:** Company → Product → (Tape Analytics | Portfolio Analytics)

**Route structure:**
| Route | Component | Description |
|---|---|---|
| `/` | `Home` | Landing page — company grid |
| `/company/:co/:product/tape/:tab` | `TapeAnalytics` | 12-tab dashboard (tab slug in URL) |
| `/company/:co/:product/portfolio/:tab` | `PortfolioAnalytics` | 3-tab portfolio view (mock data) |
| `/company/:co/:product/methodology` | `Methodology` | Definitions & formulas reference |

**Sidebar navigation:** 240px persistent sidebar on all company pages. Sections: Company name, Products (if multiple), Tape Analytics (12 links), Portfolio Analytics (3 links), Methodology. Active state: gold left border + gold text.

**URL-based tabs:** Active tab driven by `:tab` URL param (not React state). Users can bookmark/share specific views. Slugs: `overview`, `actual-vs-expected`, `deployment`, `collection`, `denial-trend`, `ageing`, `revenue`, `portfolio-tab`, `cohort-analysis`, `returns`, `risk-migration`, `data-integrity`, `borrowing-base`, `concentration-limits`, `covenants`.

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
## Portfolio Analytics Tabs (3) — Backend Ready, Frontend Mock
|Tab                  |What It Shows                                                |
|---------------------|-------------------------------------------------------------|
|Borrowing Base       |KPI cards, waterfall (Total AR → Ineligible → Eligible → Conc Adj → Advance Rate → BB), advance rates by region/product, facility capacity|
|Concentration Limits |Summary bar (compliant/breach counts), limit cards with compliance badges, breach details|
|Covenants            |Covenant cards with threshold bars, calculation breakdowns, compliance badges|

**Backend:** `core/portfolio.py` has full computation functions for both companies. API endpoints live at `/portfolio/*`. Auto-dispatches by `analysis_type` in config.json.
**Frontend:** Still uses mock data (`mockData.js`). Next step: connect components to real API endpoints.

### SILQ Portfolio Analytics (computed from tape)
- **Borrowing Base:** Outstanding A/R → Ineligible (DPD>60, concentration excess) → Eligible → 80% advance → BB. Per-product breakdown (BNPL/RBF). Facility capacity with user-entered params.
- **Concentration Limits (from loan docs):** Tiered single-borrower limit (≤$10M→20%, $10-20M→15%, >$20M→10%; Approved Recipients→15%). Top-5 shop, product mix, weighted avg tenure.
- **Covenants (5, validated vs Dec 2025 cert):** PAR30 ≤10%, PAR90 ≤5%, Collection Ratio >33% (3M avg), Repayment at Term >95%, LTV ≤75% (needs facility_params).
- **Validation results:** PAR30 5.53% (cert 1.6% timing gap), Collection Ratio Oct 99.3%/Nov 92.9%/Dec 96.9% (exact match), Repayment at Term 97.18% (cert 97.33%).

### Klaim Portfolio Analytics (matching Creditit platform)
- **Borrowing Base:** Total A/R (outstanding of active deals) → Ineligible (age>365d, denied>50%) → Eligible → Concentration Adjustments (payer excess) → Advance Rate Discount (UAE 90%, Non-UAE 85%) → Adjusted Pool Balance + Cash = BB.
- **Concentration Limits (5):** Single receivable (0.5%), Top-10 receivables (50%), Single customer/Group (10%), Single payer (10% — with breach list + adjustment amount), Extended Age Receivables (5% — with WAL calculation).
- **Covenants (6):** Min Cash Balance (≥3.0x ratio, off-tape), WAL (<60 days), PAR30 (<7%), PAR60 (<5%), Collection Ratio (≥25%), Paid vs Due (≥95%).

### Facility Parameters (user-entered, stored per product)
Stored in `data/{company}/{product}/facility_params.json`. Editable via `POST /portfolio/facility-params`.
- **SILQ:** `facility_limit`, `facility_drawn`, `cash_balance`, `equity_injection`, `advance_rate`, `approved_recipients`
- **Klaim:** `facility_limit`, `facility_drawn`, `cash_balance`, `net_cash_burn`, `net_cash_burn_3m_avg`, `advance_rate`, `advance_rates_by_region`, `single_payer_limit`
-----
## Currency System
Supported: `AED (0.2723)`, `USD (1.0)`, `EUR (1.08)`, `GBP (1.27)`, `SAR (0.2667)`, `KWD (3.26)`.
Each product has a `config.json` with its reported currency. Frontend shows toggle between reported currency and USD. Backend applies multiplier via `apply_multiplier()` in `core/analysis.py`.
> TODO: Replace hardcoded FX rates with a live FX API call.
-----
## Dashboard Customization Philosophy
Each company/product has its own configured dashboard. The platform shares a common shell but specific views, metrics, and AI prompts are driven by asset class and available columns. Onboarding a new company requires designing the right views for that asset class.
**Current implementation:** Two asset classes supported: Klaim (insurance receivables) and SILQ (POS lending). Backend auto-dispatches by `analysis_type` in config.json. Portfolio Analytics engine (`core/portfolio.py`) has company-specific functions for both.
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
- **`core/portfolio.py`** — Standalone portfolio analytics module. SILQ functions import helpers from `analysis_silq.py` (`_dpd`, `_safe`, column aliases). Klaim functions use Klaim column names directly (`Purchase value`, `Group`, `Collected till date`). No cross-dependency between company-specific functions.
- **Portfolio auto-dispatch** — `_portfolio_load()` in `main.py` reads `analysis_type` from config.json. Returns 8-tuple `(df, sel, config, disp, mult, ref_date, facility_params, analysis_type)`. Endpoints use `if atype == 'silq'` to route to the right compute function.
- **SILQ concentration tiers (from loan docs)** — Single financing recipient limit scales with facility drawn: ≤$10M→20%, $10-20M→15%, >$20M→10%. Approved Recipients always 15%. Facility drawn converted to USD via `usd_rate` from config for tier lookup.
- **Facility params persistence** — Stored as `facility_params.json` in the product data directory. Allowed keys whitelisted in `save_facility_params()`. `usd_rate` auto-injected from config.json. Off-tape data (cash balance, facility drawn, net cash burn) enables covenants that can't be computed from tape alone (LTV, Min Cash Balance).
- **SILQ multi-sheet loader** — `load_silq_snapshot()` reads all Excel sheets, skips commentary sheets, detects malformed headers (summary-row-as-header), normalises `Loan_Type→Product`, fills missing `Margin Collected`, casts `Shop_ID` to string, normalises `Loan_Status` to title case. Returns `(df, commentary_text)`.
- **Klaim outstanding pattern** — Portfolio functions use `outstanding = Purchase value - Collected - Denied` (clipped at 0), same pattern as Ageing/Portfolio health in tape analytics. Consistent with Creditit's Total A/R definition.
- **SILQ covenant validation** — Validated against SILQ KSA Dec 2025 compliance certificate reconciliation Excel. Collection Ratio monthly breakdown matches exactly (Oct 99.3%, Nov 92.9%, Dec 96.9%). PAR30 timing gap expected (cert at Dec 31 vs tape at Jan 31). Repayment at Term within 0.15pp.
- **CompanyLayout** — Wraps `CompanyProvider` around `Sidebar` + `<Outlet>`. Simple flex layout: sidebar (240px fixed) + main content area (flex: 1).
- **Portfolio Analytics mock data** — All 3 portfolio tabs use hardcoded data from `components/portfolio/mockData.js`. Phase 2 will replace with real backend APIs.
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
- Portfolio borrowing-base: `res.waterfall[]`, `res.kpis{}` (total_ar, eligible_ar, borrowing_base, available_to_draw), `res.advance_rates[]`, `res.facility{}` (limit, outstanding, available, headroom_pct)
- Portfolio concentration-limits: `res.limits[]` (name, current, threshold, compliant, breakdown[], breaches[], conc_adjustment), `res.compliant_count`, `res.breach_count`
- Portfolio covenants: `res.covenants[]` (name, current, threshold, compliant, operator, format, period, available, partial, note, breakdown[]), `res.compliant_count`, `res.breach_count`, `res.partial_count`, `res.test_date`
- Portfolio facility-params: `res.facility_limit`, `res.facility_drawn`, `res.cash_balance`, etc. — user-entered, stored as JSON
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
- ✅ **Portfolio Analytics UI (mock data):**
  - Borrowing Base — 4 KPI cards, waterfall table, advance rates by region, facility capacity bar
  - Concentration Limits — summary bar, 2-column grid of limit cards with progress bars + compliance badges
  - Covenants — covenant cards with threshold bars, calculation breakdowns, compliance distance warnings
  - Frontend still uses `mockData.js` — next step: connect to real API endpoints
- ✅ **Portfolio Analytics Backend (`core/portfolio.py`)** — computation engine for both companies:
  - **SILQ:** `compute_borrowing_base()` (DPD + tiered concentration ineligibility, 80% advance), `compute_concentration_limits()` (4 limits from loan docs, tiered by facility size), `compute_covenants()` (5 covenants: PAR30/90, Collection Ratio 3M avg, Repayment at Term, LTV), `compute_portfolio_flow()` (monthly origination waterfall)
  - **Klaim:** `compute_klaim_borrowing_base()` (Creditit-matching waterfall: Total AR → Ineligible → Eligible → Conc Adj → Advance Rate → Adjusted Pool + Cash), `compute_klaim_concentration_limits()` (5 limits: single receivable, top-10, customer, payer with breach list, extended age/WAL), `compute_klaim_covenants()` (6 covenants: cash balance ratio, WAL, PAR30/60, collection ratio, paid vs due)
  - Validated SILQ covenants against Dec 2025 compliance cert (Collection Ratio monthly breakdown exact match)
  - Validated Klaim structure against Creditit platform (same waterfall steps, limit names, covenant formulas)
  - Auto-dispatch in `main.py`: `_portfolio_load()` detects `analysis_type` from config, routes to correct functions
  - Facility params persistence: `GET/POST /portfolio/facility-params` saves to `data/{co}/{product}/facility_params.json`
- ✅ **SILQ onboarded:** `data/SILQ/KSA/` with config.json (`analysis_type: "silq"`, currency SAR), `core/analysis_silq.py` (8 compute functions), `core/validation_silq.py` (14 checks), `load_silq_snapshot()` multi-sheet loader in `core/loader.py`
-----
## Known Gaps & Next Steps
**Short term:**
- [x] Onboard SILQ — POS lending asset class (data + config + analysis_silq.py + validation_silq.py + loader)
- [ ] Add `core/analysis.py` unit tests
- [ ] Replace hardcoded FX rates with live API
- [x] Startup script — `start.ps1` boots both servers + opens browser
**Phase 2 (Borrowing Base Monitoring) — Backend done, frontend needs wiring:**
- [x] Backend API endpoints for borrowing base, concentration limits, covenants (both companies)
- [x] Core computation functions validated against reconciliation data and Creditit platform
- [x] Facility params save/load API for user-entered corporate-level data
- [ ] **Connect frontend Portfolio Analytics components to real API** (replace `mockData.js` imports with API calls in BorrowingBase.jsx, ConcentrationLimits.jsx, Covenants.jsx)
- [ ] **Facility params input panel** — UI for entering cash balance, facility drawn, net cash burn, etc.
- [ ] SILQ tape analytics frontend (9 tabs defined in config.json, 7 chart components exist in pedantic-swirles worktree)
- [ ] Covenant monitoring historical tracking and breach alerts
**Phase 3 (Team & Deployment):**
- [ ] Cloud deployment
- [ ] Role-based access
- [ ] Scheduled report delivery
- [ ] Direct API integrations with portfolio companies
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
