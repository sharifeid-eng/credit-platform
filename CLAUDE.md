# Laith Private Credit Platform
-----
## About This File
This is the **CLAUDE.md** for the project — automatically loaded by Claude Code at the start of every session. It serves as the single source of truth for project context, conventions, and current status.
**Update rule:** When significant decisions are made or features are completed, update this file to keep it current.
**Reminder rule:** After completing a major task or feature, remind the user to:
1. Update CLAUDE.md (offer to do it)
2. Commit and push to GitHub (offer to do it, confirm `.env` is not tracked)
-----
## Workflow Rules

### Planning
- Enter plan mode for any non-trivial task (3+ steps or architectural decisions). Write the plan to `tasks/todo.md` with checkable items.
- If something goes sideways, STOP and re-plan immediately — don't keep pushing.
- Write detailed specs upfront to reduce ambiguity. Check in with the user before starting implementation.

### Execution
- **Subagents:** Offload research, exploration, and parallel analysis to subagents. One task per subagent for focused execution. Keep main context window clean.
- **Simplicity first:** Make every change as simple as possible. Minimal impact. Only touch what's necessary.
- **No laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Autonomous bug fixing:** When given a bug report, just fix it. Point at logs, errors, failing tests — then resolve them. Zero context switching required from the user.

### Verification
- Never mark a task complete without proving it works — run tests, check logs, demonstrate correctness.
- When a task depends on external data (tape edits, DB migrations), **verify the data first** before updating code that references it.
- Ask yourself: "Would a staff engineer approve this?"

### Self-Improvement
- After ANY correction from the user, update `tasks/lessons.md` with the pattern. Write rules that prevent the same mistake.
- Review `tasks/lessons.md` at session start for this project.

### Progress Tracking
- Track plans and progress in `tasks/todo.md`. Mark items complete as you go.
- Explain changes with high-level summaries at each step.
- After completing a major task, add a review section to `tasks/todo.md` and capture lessons.

### Analysis Framework Authority
**The Analysis Framework (`core/ANALYSIS_FRAMEWORK.md`) is the authoritative source for ALL analytical decisions.** It is the "brain" of the platform — not just documentation, but the specification that drives every metric, dashboard, and AI prompt.

**Binding rules:**
- For any analytical decision (new metric, new company, methodology change), consult the framework FIRST
- Its hierarchy (L1–L5), denominator discipline, three clocks, and separation principle are non-negotiable
- New companies MUST be onboarded via `/onboard-company` which enforces framework compliance
- New metrics/tabs MUST be added via `/extend-framework` which propagates across all layers
- Periodic health checks via `/framework-audit` ensure no drift from the framework

**Quick reference:** `core/FRAMEWORK_INDEX.md` — fast lookup of sections, commands, existing companies, and core principles.

**Framework commands available:**
| Command | When to Use |
|---------|-------------|
| `/onboard-company` | Adding a new company or product to the platform |
| `/add-tape` | Adding a new tape file for an existing company |
| `/validate-tape` | Running data quality checks on any tape |
| `/framework-audit` | Periodic audit of all companies against the framework |
| `/extend-framework` | Adding new metrics, tabs, or analytical capabilities |
| `/methodology-sync` | Verifying methodology page matches backend code |
| `/company-health` | Quick diagnostic of any company's analytical coverage |
| `/eod` | End-of-session cleanup (tests, docs, commit, push) |
-----
## What This Project Is
**Laith** (with **AI** as a play in the name) — an institutional-grade, full-stack web application for analyzing and monitoring asset-backed loan portfolios. Built for a private credit fund (ACP) that purchases receivables and short-term loans from portfolio companies.
The platform allows analysts and investment committee members to:
- Upload loan tape snapshots (CSV/Excel) and explore portfolio performance
- Run automated data integrity checks across snapshots
- View interactive dashboards with 18 analysis tabs (including institutional risk analytics, loss attribution, and forward-looking signals)
- Explore the Analysis Framework — a structured analytical philosophy guiding all metrics
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
- **SILQ** — POS lending, KSA. Data in SAR. Live dataset: `data/SILQ/KSA/` (2 tapes: Jan 2026, Feb 2026). Three product types: BNPL, RBF, RCL (Revolving Credit Line). Has dedicated analysis module (`core/analysis_silq.py`), validation (`core/validation_silq.py`), dynamic chart endpoint, and tests.
- **Ejari** — Rent Now Pay Later (RNPL), KSA. Data in USD. **Read-only summary** — no raw loan tape, only a pre-computed ODS workbook with 13 sheets of analysis. Rendered as a dedicated dashboard (`EjariDashboard.jsx`) without live computation. Parser: `core/analysis_ejari.py`. Config: `analysis_type: "ejari_summary"`. Live dataset: `data/Ejari/RNPL/`
**Asset classes:** Receivables (insurance claims factoring), short-term consumer/POS loans, and rent payment financing (RNPL).
**Data format:** Single Excel or CSV loan tapes, typically thousands to tens of thousands of rows. Each row is a deal/receivable. Snapshots are taken periodically (e.g. monthly) and named `YYYY-MM-DD_description.csv`. Also supports ODS files (Ejari summary workbook).
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
- AI-powered dashboards per company/product (18 tape analytics tabs)
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
- **Frontend:** React (Vite), Tailwind CSS, Recharts, Framer Motion, React Router, Axios (`localhost:5173`)
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
│   ├── ANALYSIS_FRAMEWORK.md # Analytical philosophy document (14 sections: hierarchy, clocks, denominators, decision trees, compute registry)
│   ├── FRAMEWORK_INDEX.md  # Quick reference index — section map, company registry, command lookup, core principles
│   ├── metric_registry.py  # @metric decorator + METRIC_REGISTRY + get_methodology() — powers living methodology
│   ├── methodology_klaim.py # Klaim methodology metadata (16 sections, 29 metrics, 13 tables)
│   ├── methodology_silq.py # SILQ methodology metadata (15 sections, 23 metrics, 2 tables)
│   ├── analysis.py         # All pure Klaim data computation functions (no I/O) — 40+ compute functions
│   ├── analysis_silq.py    # SILQ-specific analysis functions (9 compute functions)
│   ├── analysis_ejari.py   # Ejari ODS workbook parser (read-only summary, 12 sections)
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
│   │   │   ├── Home.jsx             # Landing page — company grid + resources section
│   │   │   ├── TapeAnalytics.jsx    # 18-tab tape dashboard (extracted from old Company.jsx)
│   │   │   ├── PortfolioAnalytics.jsx  # 6-tab portfolio view (live data from DB/tape)
│   │   │   ├── Framework.jsx        # Analysis Framework page (/framework) — analytical philosophy with sticky TOC
│   │   │   ├── Methodology.jsx      # Definitions, formulas, rationale for all analytics
│   │   │   ├── ExecutiveSummary.jsx # AI Executive Summary — credit memo narrative + ranked findings
│   │   │   └── EjariDashboard.jsx  # Read-only Ejari summary dashboard (12 sections from ODS)
│   │   ├── components/
│   │   │   ├── Sidebar.jsx              # 240px persistent sidebar nav — Framer Motion animated active border
│   │   │   ├── KpiCard.jsx              # Framer Motion stagger + hover effects + optional sparklineData prop
│   │   │   ├── Navbar.jsx               # Contains LaithLogo component (exported)
│   │   │   ├── AICommentary.jsx         # Slide-up animation on commentary
│   │   │   ├── DataChat.jsx
│   │   │   ├── TabInsight.jsx           # Smooth expand/collapse with AnimatePresence
│   │   │   ├── ChartPanel.jsx           # Fade-in + skeleton chart loading
│   │   │   ├── PortfolioStatsHero.jsx   # Landing page stats strip — count-up aggregates across all companies
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
│   │   │   │   ├── DataIntegrityChart.jsx    # Two-tape comparison, validation, AI report + notes
│   │   │   │   ├── CohortLossWaterfallChart.jsx  # Loss waterfall table + vintage loss curves + loss categorization
│   │   │   │   ├── RecoveryAnalysisChart.jsx     # Recovery rates, timing, worst/best deals by vintage
│   │   │   │   ├── CollectionsTimingChart.jsx    # Timing bucket distribution using collection curves
│   │   │   │   ├── UnderwritingDriftChart.jsx    # Per-vintage quality metrics + drift flags
│   │   │   │   ├── SegmentAnalysisChart.jsx      # Multi-dimensional cuts with heat-map coloring
│   │   │   │   ├── SeasonalityChart.jsx          # YoY comparison + seasonal index
│   │   │   │   ├── CdrCcrChart.jsx               # CDR/CCR conditional rates by vintage (Klaim)
│   │   │   │   └── silq/                    # SILQ-specific chart components
│   │   │   │       ├── DelinquencyChart.jsx
│   │   │   │       ├── SilqCollectionsChart.jsx
│   │   │   │       ├── SilqConcentrationChart.jsx
│   │   │   │       ├── SilqCohortTable.jsx
│   │   │   │       ├── YieldMarginsChart.jsx
│   │   │   │       ├── TenureAnalysisChart.jsx
│   │   │   │       ├── SilqCovenantsChart.jsx
│   │   │   │       ├── SilqSeasonalityChart.jsx
│   │   │   │       └── SilqCdrCcrChart.jsx        # CDR/CCR conditional rates by vintage (SILQ)
│   │   │   │       ├── SilqLossWaterfallChart.jsx
│   │   │   │       └── SilqUnderwritingDriftChart.jsx
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
│   │   │       ├── FacilityParamsPanel.jsx    # Slide-out panel to edit facility parameters
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
│   ├── create_api_key.py   # CLI to generate API keys for portfolio companies
│   └── sync_framework_registry.py  # Auto-generate Section 12 in ANALYSIS_FRAMEWORK.md from metric registry
├── docs/
│   └── generate_guide.js   # Node.js script to generate Word docs with LAITH branding
└── reports/
    └── ai_cache/           # Disk cache for AI responses (auto-generated, gitignored)
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
|`GET /companies/{co}/products/{p}/ai-executive-summary`      |AI holistic findings from all metrics|
|`GET /companies/{co}/products/{p}/ai-tab-insight`            |Short AI insight for a specific tab|
|`GET /companies/{co}/products/{p}/ai-cache-status`           |Check which AI outputs are cached|
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
|`GET /companies/{co}/products/{p}/ejari-summary`             |Parsed Ejari ODS workbook (12 sections, cached)|
|`GET /companies/{co}/products/{p}/charts/par`                |PAR 30+/60+/90+ (Portfolio at Risk)  |
|`GET /companies/{co}/products/{p}/charts/dtfc`               |Days to First Cash (leading indicator)|
|`GET /companies/{co}/products/{p}/charts/cohort-loss-waterfall`|Cohort loss waterfall (per-vintage)  |
|`GET /companies/{co}/products/{p}/charts/recovery-analysis`  |Recovery rates, timing, worst/best deals|
|`GET /companies/{co}/products/{p}/charts/vintage-loss-curves`|Cumulative loss development curves    |
|`GET /companies/{co}/products/{p}/charts/loss-categorization`|Fraud/anomaly categorization heuristics|
|`GET /companies/{co}/products/{p}/charts/collections-timing` |Collections timing waterfall (curve-based)|
|`GET /companies/{co}/products/{p}/charts/underwriting-drift` |Underwriting drift flags by vintage   |
|`GET /companies/{co}/products/{p}/charts/segment-analysis`   |Multi-dimensional segment cuts        |
|`GET /companies/{co}/products/{p}/charts/hhi-timeseries`     |HHI concentration across all snapshots|
|`GET /companies/{co}/products/{p}/charts/seasonality`        |YoY seasonal patterns + seasonal index|
|`GET /companies/{co}/products/{p}/charts/cdr-ccr`            |CDR/CCR by vintage (annualized conditional default/collection rates)|
|`GET /companies/{co}/products/{p}/charts/methodology-log`    |Data corrections & column availability log|
|`GET /framework`                                             |Analysis Framework markdown document  |

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
| `/company/:co/:product/tape/:tab` | `TapeAnalytics` | 18-tab dashboard (tab slug in URL) |
| `/company/:co/:product/portfolio/:tab` | `PortfolioAnalytics` | 6-tab portfolio view (live data from DB/tape) |
| `/company/:co/:product/executive-summary` | `ExecutiveSummary` | AI-powered holistic findings from all metrics |
| `/company/:co/:product/methodology` | `Methodology` | Definitions & formulas reference |
| `/framework` | `Framework` | Analysis Framework — analytical philosophy with sticky TOC |

**Sidebar navigation:** 240px persistent sidebar on all company pages. Sections: Company name, Products (if multiple), Executive Summary (gold accent, AI-powered), Tape Analytics (18 links), Portfolio Analytics (6 links), Methodology. Active state: gold left border + gold text.

**URL-based tabs:** Active tab driven by `:tab` URL param (not React state). Users can bookmark/share specific views. Slugs: `overview`, `actual-vs-expected`, `deployment`, `collection`, `denial-trend`, `ageing`, `revenue`, `portfolio-tab`, `cohort-analysis`, `returns`, `risk-migration`, `data-integrity`, `loss-waterfall`, `recovery-analysis`, `collections-timing`, `underwriting-drift`, `segment-analysis`, `seasonality`, `cdr-ccr`, `borrowing-base`, `concentration-limits`, `covenants`, `invoices`, `payments`, `bank-statements`.

**Backward compat:** `/company/:co` and `/company/:co/:product` redirect to `tape/overview`.

**State management:** `CompanyContext` provides shared state (company, products, snapshots, config, currency, summary, etc.) consumed by both TapeAnalytics and PortfolioAnalytics.

-----
## Tape Analytics Tabs (19)
|Tab               |What It Shows                                                   |
|------------------|----------------------------------------------------------------|
|Overview          |12+ KPI cards (incl curve-based DSO, HHI, PAR 30+/60+/90+, DTFC; graceful degradation on older tapes) + AI commentary + Data Chat|
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
|Loss Waterfall    |Per-vintage loss waterfall (Originated → Gross Default → Recovery → Net Loss), vintage loss curves, loss categorization pie chart|
|Recovery Analysis |Recovery rates and timing by vintage, worst/best performing deals drill-down|
|Collections Timing|Timing bucket distribution using collection curve columns (0-30d, 30-60d, etc.), stacked bars + portfolio distribution|
|Underwriting Drift|Per-vintage quality metrics (deal size, discount, collection rate) + drift flag badges when metrics deviate from historical norms|
|Segment Analysis  |Multi-dimensional cuts (product, provider size, deal size, new vs repeat) with sortable heat-map table and dimension dropdown|
|Seasonality       |YoY comparison by calendar month (grouped bars per year) + seasonal index line overlay|
|CDR / CCR         |Conditional Default Rate + Conditional Collection Rate by vintage (annualized by vintage age); 4 KPI tiles + dual-line chart + net spread line|
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
> FX rates fetched live from exchangerate-api.com with hardcoded fallback. Backend endpoint: `GET /fx-rates`.
-----
## Dashboard Customization Philosophy
Each company/product has its own configured dashboard. The platform shares a common shell but specific views, metrics, and AI prompts are driven by asset class and available columns. Onboarding a new company requires designing the right views for that asset class.
**Current implementation:** Klaim (healthcare receivables), SILQ (POS lending), and Ejari (RNPL read-only summary) all onboarded. SILQ has a dedicated analysis module (`core/analysis_silq.py`) and custom dashboard tabs configured via `config.json`. Ejari uses `analysis_type: "ejari_summary"` to render a dedicated read-only dashboard (`EjariDashboard.jsx`) that parses an ODS workbook instead of running live computations. The `analysisType` field in config determines which chart components render.

### Methodology Onboarding Checklist
When onboarding a new company, follow these steps to build its methodology page. Full guide in `core/ANALYSIS_FRAMEWORK.md` Section 7.
1. **Define `analysis_type`** in `config.json` — reuse existing type if same asset class, or create new one
2. **Build methodology sections covering all 5 hierarchy levels:**
   - L1 Size & Composition — what constitutes "a deal", volume metrics, product types
   - L2 Cash Conversion — collection rate formula, DSO variant, timing distribution
   - L3 Credit Quality — distress signal (DPD vs denial vs default), PAR method, health thresholds
   - L4 Loss Attribution — loss event definition, recovery path, margin structure, EL parameters
   - L5 Forward Signals — at least one leading indicator, covenant thresholds, stress scenarios
3. **Add cross-cutting sections** — Product Types, Cohort Analysis, Data Caveats, Currency, Data Quality
4. **Add conditional branch** in `Methodology.jsx` — new `{TYPE}_SECTIONS` array with `level` tags, new content component
5. **Verify metrics match backend** — every formula in the methodology must correspond to an actual computation in the analysis module
-----
## Key Architectural Decisions
- **`core/analysis.py`** — all pure data computation. No FastAPI, no I/O.
- **`core/config.py`** — per-product `config.json` stores currency and description.
- **Snapshot naming** — files must start with `YYYY-MM-DD_` for date parsing.
- **`filter_by_date()`** — filters deals to `Deal date <= as_of_date`. **Important:** Only filters deal selection by origination date — does NOT adjust balance columns (collected, denied, outstanding). These always reflect the tape snapshot date. See ANALYSIS_FRAMEWORK.md Section 15.
- **`_load()` in main.py** — matches snapshots by `filename` or `date` field (fixed Feb 2026).
- **AICommentary caching** — two layers: (1) In-memory via `CompanyContext` state, survives tab switches within a session, clears on snapshot change. (2) Disk cache in `reports/ai_cache/` — persists across sessions and users (see below).
- **AI response disk cache** — All AI endpoints (executive summary, commentary, tab insights) cache responses to `reports/ai_cache/` as JSON files. Cache key: `(endpoint, company, product, snapshot_filename)` — currency excluded (only affects numeric display), `as_of_date` normalized (None/snapshot_date/future all map to same key). `?refresh=true` query param forces regeneration. One AI call per tape lifetime.
- **AI blocked on backdated views** — `_check_backdated()` returns HTTP 400 on all AI endpoints when `as_of_date < snapshot_date`. Balance metrics would be misleading (inflated collection rates, understated outstanding). Frontend: KpiCard shows `TAPE DATE` badge + dimmed value, BackdatedBanner classifies metrics, AI controls disabled with explanation.
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
- **SILQ multi-sheet Excel loader** — `core/loader.py` reads all data sheets from the Excel workbook and concatenates them. Three product types: BNPL, RBF, RCL. Row 1 is header (row 0 has formulas). `Loan_Type` column in RCL sheet mapped to `Product`.
- **As-of date default** — `date-range` endpoint returns `snapshot_date` extracted from filename. Frontend uses `max(data_max_date, snapshot_date)` as calendar upper bound and default.
- **Framer Motion integration** — Uses `motion.div` wrappers with `initial`/`animate`/`exit` props. `AnimatePresence mode="wait"` for tab transitions and chart loading states. KPI stagger via `index * 0.04s` delay. All animations use `transform`/`opacity` for GPU acceleration.
- **PDF report wait strategy** — 3-phase approach per tab: 4s initial mount wait → poll for "Loading..." spinners to disappear (max 20s, double-confirm) → 2s animation settle. ~6.5s per tab, ~70s total.
- **Analysis Framework** — `core/ANALYSIS_FRAMEWORK.md` defines a 5-level analytical hierarchy (Size → Cash Conversion → Credit Quality → Loss Attribution → Forward Signals). All new tabs and metrics are mapped to this hierarchy. Framework served via `GET /framework` endpoint, rendered as full-page markdown with sticky TOC.
- **PAR computation (dual perspective)** — 3-method approach: (1) Primary uses `Expected till date` shortfall-based estimated DPD, (2) Option C builds empirical benchmarks from 50+ completed deals, (3) Fallback returns `available: False`. **Dual denominator:** Active PAR (behind-schedule outstanding / active outstanding — monitoring view, was showing 46% PAR30) and Lifetime PAR (behind-schedule outstanding / total originated — IC view, shows 3.6% PAR30). Tape Analytics shows Lifetime as headline with Active as context subtitle. The issue: active outstanding is only ~8% of total originated, which dramatically inflated the active ratio. Portfolio Analytics uses eligible outstanding for covenants. "Derived from historical patterns" badge shown when Option C used.
- **DTFC (Days to First Cash)** — leading indicator that deteriorates before collection rate does. Curve-based method (precise) uses collection curve columns; estimated method (fallback) approximates from deal dates and collected amounts. Shows Median and P90 on Overview.
- **DSO dual perspectives** — DSO Capital (days from funding to collection) measures capital efficiency. DSO Operational (days from expected due date to collection) measures payer behavior. Both use curve-based and estimated methods.
- **Cohort loss waterfall** — "default" for Klaim = denial > 50% of purchase value (since there are no contractual due dates). Per-vintage waterfall: Originated → Gross Default → Recovery → Net Loss. Integrates vintage loss curves and loss categorization.
- **Separation Principle** — `separate_portfolio()` splits into clean (active + normal completed) vs loss (denial > 50% PV). Clean portfolio used for performance metrics; loss portfolio isolated for attribution analysis. Prevents loss deals from distorting healthy portfolio metrics.
- **Loss categorization heuristics** — `compute_loss_categorization()` applies rules-based classification: provider_issue (high denial from specific groups), coding_error (partial denials suggesting claim issues), credit/underwriting (remaining). Not ML — transparent heuristics for analyst interpretation.
- **Collections timing** — `compute_collections_timing()` uses collection curve columns (Expected/Actual at 30d intervals) to build timing bucket distributions. Returns both per-vintage and portfolio-level views. Requires Mar 2026+ tape with curve columns.
- **Segment analysis multi-dimensional cuts** — `compute_segment_analysis()` supports 4 dimensions: product type, provider_size (bucketed by PV volume), deal_size (quartile-based), new_repeat. Each dimension returns per-segment metrics with deal count, volume, collection/denial rates, margins.
- **HHI time series** — `compute_hhi_for_snapshot()` computes HHI for a single snapshot. Endpoint loads ALL snapshots to build time series, detects trend (increasing/decreasing/stable) and issues warnings when concentration is rising.
- **Underwriting drift** — `compute_underwriting_drift()` compares per-vintage metrics (avg deal size, discount, collection rate) against historical norms (rolling mean of prior vintages). Flags vintages where metrics deviate beyond 1 standard deviation.
- **Seasonality** — `compute_seasonality()` groups deployment by calendar month across years for YoY comparison. Computes seasonal index (month average / overall average) to identify seasonal patterns in origination.
- **Methodology log** — `compute_methodology_log()` documents all data corrections, column availability checks, and data quality decisions applied during analysis. Provides audit trail for IC-level transparency.
- **Summary field name convention** — The frontend expects canonical field names from `/summary`: `total_purchase_value`, `total_deals`, `collection_rate`, etc. Company-specific analysis functions may use domain terms (e.g. SILQ's `total_disbursed`). The summary must return BOTH the domain-specific name AND the canonical alias (e.g. `'total_purchase_value': _safe(total_disbursed)`). This ensures landing page cards and aggregate stats work uniformly across all companies.
- **Living Methodology architecture** — Methodology page content is stored as structured Python dicts in companion files (`core/methodology_klaim.py`, `core/methodology_silq.py`) rather than hardcoded JSX. Backend serves via `GET /methodology/{analysis_type}`. Frontend renders dynamically using existing Metric/Table/Note/Section components. Companion files (not inline decorators) chosen because methodology metadata is large (multi-line strings, nested structures) — keeping `analysis.py` as pure computation. Ejari uses static JSON file at `data/Ejari/RNPL/methodology.json`. New companies: create `methodology_{type}.py`, register at startup → page works automatically.
- **Ejari read-only summary pattern** — When `analysis_type` is `"ejari_summary"`, the platform bypasses all tape loading and computation. TapeAnalytics renders `EjariDashboard.jsx` which reads the URL `:tab` param and renders only the matching section. The `parse_ejari_workbook()` function in `core/analysis_ejari.py` reads the ODS file once (cached per session), extracting 12 structured sections. Config uses `hide_portfolio_tabs: true` to suppress Portfolio Analytics in sidebar, and sidebar header shows "Analysis" instead of "Tape Analytics". EjariDashboard uses shared `KpiCard` and `ChartPanel` components (same as Klaim/SILQ) for visual consistency. Only `DataTable` remains Ejari-specific (renders ODS tabular data). This pattern can be reused for any future company that provides pre-computed analysis instead of raw tapes.
- **ODS file support** — `core/loader.py` `get_snapshots()` now accepts `.ods` files alongside `.csv` and `.xlsx`. Requires `odfpy` package (`pip install odfpy`).
- **Overview page standardization** — All company overviews follow a consistent section structure guided by the L1-L5 analytical hierarchy: (1) Main KPIs (L1/L2, 5-col grid, bespoke per company), (2) "Credit Quality" section (L3, PAR 30+/60+/90+ as individual cards), (3) "Leading Indicators" section (L5, DTFC etc when available). PAR cards always use `{ccy} {amount}K at risk` subtitle format. Fixed 5-column grids prevent async reflow. Bespoke KPIs encouraged within each section.
- **Executive Summary always visible** — Sidebar shows Executive Summary for all companies including Ejari. Decoupled from `hide_portfolio_tabs` flag which only controls Portfolio Analytics tabs.
- **Executive Summary dual-output architecture** — Single AI call returns JSON object with `narrative` (sections array + summary_table + bottom_line) and `findings` (array, same as before). Company-specific section guidance injected into prompt. Response parsing handles both old format (array) and new format (object) for backward compat. `max_tokens=8000` for the combined output. Generation takes ~50-60s vs ~10s previously.
-----
## Design System — Dark Theme ✅
Full dark theme with ACP-aligned navy base and Framer Motion animations. See color palette:
|Token           |Value    |Usage                                      |
|----------------|---------|-------------------------------------------|
|`--bg-base`     |`#121C27`|Page background (ACP navy)                 |
|`--bg-surface`  |`#172231`|Cards, panels                              |
|`--bg-nav`      |`#0D1520`|Navbar                                     |
|`--bg-deep`     |`#0A1119`|Deeper backgrounds (inputs, AI panels)     |
|`--border`      |`#243040`|All borders                                |
|`--border-hover`|`#304058`|Border on hover state                      |
|`--accent-gold` |`#C9A84C`|Primary brand, active tab, AI panel        |
|`--accent-teal` |`#2DD4BF`|Collection rate, positive metrics, live dot|
|`--accent-red`  |`#F06060`|Denial rate, negative metrics              |
|`--accent-blue` |`#5B8DEF`|Pending/neutral metrics, deployment bars   |
|`--text-primary`|`#E8EAF0`|Main text                                  |
|`--text-muted`  |`#8494A7`|Secondary text (updated for contrast)      |
|`--text-faint`  |`#304050`|Labels, borders                            |
Typography: Inter for UI, IBM Plex Mono for numbers/data.

**Animations (Framer Motion):**
- KPI cards: stagger fade-in (50ms per card), hover lift + shadow + border brighten
- Tab content: fade-in/slide on tab switch (`opacity 0→1, y 8→0`, 250ms)
- ChartPanel: fade-in on mount, skeleton bar chart during loading
- TabInsight: smooth expand/collapse with AnimatePresence
- AICommentary: slide-up when commentary generates
- Sidebar: hover text brighten + subtle indent, active tint background
- Transition tokens: `--transition-fast: 150ms`, `--transition-normal: 250ms`
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
- PAR: `res.available`, `res.method` (`primary`/`option_c`/`unavailable`), `res.par_30{}`, `res.par_60{}`, `res.par_90{}` (each has `balance_pct`, `count_pct`, `balance`, `count`), `res.total_active_outstanding`, `res.total_active_count`
- DTFC: `res.available`, `res.method` (`curve_based`/`estimated`), `res.median_dtfc`, `res.p90_dtfc`, `res.by_vintage[]`
- DSO: also returns `res.dso_operational_weighted`, `res.dso_operational_median` when available
- Cohort loss waterfall: `res.vintages[]` (each has `vintage`, `originated`, `gross_default`, `recovery`, `net_loss`, `default_rate`, `recovery_rate`, `net_loss_rate`), `res.totals{}`
- Vintage loss curves: `res.available`, `res.curves[]` (per-vintage cumulative loss at age intervals)
- Loss categorization: `res.categories[]` (each has `category`, `count`, `total_denied`, `pct`), `res.total_loss_deals`
- Recovery analysis: `res.by_vintage[]` (recovery_rate, avg_recovery_days), `res.worst_deals[]`, `res.best_deals[]`, `res.portfolio_recovery_rate`
- Collections timing: `res.available`, `res.buckets[]` (timing bucket distribution), `res.by_vintage[]`, `res.portfolio_distribution{}`
- Underwriting drift: `res.vintages[]` (each has `vintage`, metrics, `flags[]`), `res.historical_norms{}`
- Segment analysis: `res.segments[]` (per-segment metrics), `res.segment_by`, `res.dimensions[]`
- HHI timeseries: `res.available`, `res.points[]` (each has `snapshot`, `hhi`), `res.trend`, `res.warning`
- Seasonality: `res.months[]` (per-month-per-year data), `res.seasonal_index[]`, `res.years[]`
- Methodology log: `res.corrections[]`, `res.column_availability{}`, `res.data_quality{}`
- Framework: `res.content` (markdown string)
-----
## What's Working
- ✅ **Creative UI redesign (branch: claude/creative-landing-page-research-5hdf6):**
  - Landing page: Islamic geometric SVG background pattern (Girih/8-point star, gold, 14% opacity, 140px tile) — stroke widths tuned for visibility (1.0 lines, 1.6 star, 2.2 dots)
  - Landing page: Syne 800 display font for hero headline + LAITH wordmark; `--font-display` CSS token
  - Landing page: TypewriterText subtitle (character-by-character, blinking cursor, respects prefers-reduced-motion)
  - Landing page: HeroLogo entrance animation (lion scale-pulse on load, gold glow pulse CSS keyframe)
  - Landing page: Two-banner PortfolioStatsHero strip — Banner 1 "Data Analyzed" (gold tint, live from `/aggregate-stats`): Face Value Analyzed, Deals Processed, Data Points (XM+), Snapshots Loaded, Portfolio Companies with ease-out expo count-up; Banner 2 "Live Portfolio" (neutral, all `—` until DB data connected): Active Exposure, PAR 30+, PAR 90+, Covenants in Breach, HHI
  - Landing page: CompanyCard two-row layout — Row 1 Tape Analytics (Face Value | Deals | Since); Row 2 Live Portfolio (Borr. Base | PAR 30+ | Covenants, all `—`). `CardRow`/`CardStat`/`CardDivider` sub-components. 3D hover tilt, animated top border sweep, 80ms stagger.
  - Landing page: LandingCanvas removed (geometric pattern provides ambient texture without JS overhead)
  - Company pages: Tab transitions enhanced — blur(3px→0) + y:12→0 with easeOut cubic, blur fade-out on exit
  - Company pages: Sidebar NavItem — animated left border (Framer Motion scaleY 0→1, origin top) + gold gradient background sweep on active state; micro-indent on hover
  - Company pages: KpiCard sparkline — optional `sparklineData` prop renders 60×18px inline SVG polyline with endpoint dot
  - Company pages: DataChat per-company question sets — `PROMPTS` map keyed by `analysisType` (`silq`, `ejari_summary`, `default`); relevant suggested questions for each asset class
  - Typography: Syne (display/hero), Space Grotesk (UI body), JetBrains Mono (data). Single Google Fonts load in index.html. All 55+ IBM Plex Mono / Inter hardcoded references replaced with CSS tokens.
  - Navbar: height 56→80px, lion icon 36→54px, LAITH wordmark 22→33px (Syne 800), "Data Analytics" label 10→15px
  - Landing page section labels: "Portfolio Companies" + "Resources" 9→13px
  - Backend: `/aggregate-stats` endpoint — 5 stats: face value (latest snapshot, no double-count, incl. Ejari total_funded), deals (all snapshots incl. Ejari ODS total_contracts), data points (rows×cols across all snapshots), snapshots, companies. Schema version `"4"` in fingerprint busts cache on field changes. FX-normalised to USD.
  - Backend: `/companies` endpoint extended with `since` field (earliest snapshot date across all products).
  - Backend: `/summary` for ejari_summary now returns real ODS data — `total_contracts` → deals, `total_funded` → face value. ODS values are comma-formatted strings (`'1,348'`) — stripped before int/float conversion.
  - New component: `PortfolioStatsHero.jsx` (two-banner stats strip)
  - New asset: `frontend/public/geometric-pattern.svg` (Islamic 8-point star lattice)
  - New slash command: `.claude/commands/eod.md` — 11-step end-of-session checklist (tests, .env check, cache cleanup, docs, commit, push, sync)
- ✅ **AI response caching (disk-based, cross-user):**
  - Executive summary (~$0.48/call), commentary (~$0.06/call), tab insights (~$0.02/call x 18 tabs) cached to `reports/ai_cache/`
  - Cache key: `(endpoint, company, product, snapshot)` — one AI call per tape lifetime, served instantly thereafter
  - `?refresh=true` query param forces regeneration; frontend shows CACHED badge + Regenerate button
  - `GET /ai-cache-status` endpoint reports what's cached for a given snapshot
- ✅ **Backdated view data integrity:**
  - Backend: AI endpoints blocked (HTTP 400) when `as_of_date < snapshot_date`
  - Frontend: KpiCard `TAPE DATE` badge + dimmed value on balance-dependent metrics
  - BackdatedBanner classifies metrics as ACCURATE (deal count, deployment) vs TAPE DATE (rates, outstanding, margins)
  - AICommentary, TabInsight, ExecutiveSummary disabled with explanation
  - ANALYSIS_FRAMEWORK.md Section 15 documents metric classification and enforcement rules
- ✅ Full backend with all chart and AI endpoints (including returns-analysis)
- ✅ 18-tab React dashboard with dark theme
- ✅ AI commentary (cached in-memory per session + disk cache across users)
- ✅ Per-tab AI insights (TabInsight, cached to disk)
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
- ✅ Enhanced Overview with 12+ KPI cards (DSO, HHI, PAR 30+/60+/90+, DTFC median/P90)
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
- ✅ **Sidebar navigation + URL-based routing** — Company pages use persistent sidebar with Tape Analytics (19 tabs) + Portfolio Analytics (6 tabs) + Methodology. Tabs are URL-driven (`/tape/:slug`, `/portfolio/:slug`), bookmarkable. Old horizontal tab bar replaced.
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
- ✅ **SILQ Feb 2026 tape onboarded:**
  - Three product types: BNPL, RBF, RCL — consistent across both tapes
  - Loader reads all data sheets and normalises `Loan_Type` → `Product`
  - Portfolio commentary from tape displayed in Overview tab
- ✅ **Ejari RNPL onboarded (read-only summary):**
  - Pre-computed ODS workbook with 13 sheets — no raw loan tape
  - `analysis_type: "ejari_summary"` bypasses normal tape loading, renders dedicated dashboard
  - Parser (`core/analysis_ejari.py`) extracts 12 structured sections from ODS
  - Dashboard (`EjariDashboard.jsx`) renders 12 tabs: Portfolio Overview (KPIs + DPD), Monthly Cohorts, Cohort Loss Waterfall, Roll Rates, Historical Performance, Collections by Month/Origination, Segment Analysis (6 dimensions), Credit Quality Trends, Najiz & Legal, Write-offs & Fraud, Data Notes
  - **Formatting aligned with Klaim/SILQ** — uses shared `KpiCard` (Framer Motion stagger, hover effects, gradient glow, subtitles) and `ChartPanel` wrappers. `AnimatePresence` tab transitions. Local `Kpi`/`Panel` components deleted.
  - **Sidebar navigation** — aligned with Klaim/SILQ design pattern: 12 tabs in left sidebar, URL-driven (`/tape/:slug`), single section rendered per tab. Sidebar header shows "Analysis" (not "Tape Analytics"). Portfolio Analytics section hidden via `hide_portfolio_tabs: true` in config. Executive Summary always visible (decoupled from `hide_portfolio_tabs`).
  - Loader updated to support `.ods` file extension (requires `odfpy` package in venv)
  - Cached parsing — ODS parsed once per session
- ✅ **PAR dual perspective (Tape Analytics):**
  - Active PAR 30+ was 46% (alarming) → Lifetime PAR 30+ is 3.6% (sensible for IC)
  - Active outstanding is only 7.8% of total originated — inflated the active ratio
  - Lifetime shown as headline, Active as context in subtitle
- ✅ **AI Executive Summary page (with holistic narrative):**
  - Single `GET /ai-executive-summary` endpoint computes ALL analytics and asks Claude for both a credit memo narrative AND ranked findings in one call
  - **Narrative section:** Company-specific sections (Ejari: 9 sections, Klaim: 7, SILQ: 6) — each with multi-paragraph analysis, assessment-colored metric pills, and gold conclusion line
  - **Summary table:** Key metrics with RAG-style colored assessment badges (Healthy/Acceptable/Warning/Critical/Monitor)
  - **Bottom line:** Gold-bordered verdict paragraph with specific diligence items for IC
  - **Key findings:** 5-10 ranked findings with severity badges (critical/warning/positive), data points, and "View Tab" navigation (unchanged from before)
  - Section guidance per company type: Ejari (Portfolio Overview → Monthly Cohorts → Loss Waterfall → Roll Rates → Historical Performance → Segment Analysis → Credit Quality → Najiz & Legal → Write-offs & Fraud), Klaim (Portfolio Overview → Cohort Performance → Collection & DSO → Denial & Loss Economics → Recovery & Risk Migration → Concentration & Segments → Forward Signals), SILQ (Portfolio Overview → Delinquency → Collections → Cohorts → Concentration → Yield & Tenure)
  - `max_tokens=8000` (was 2000) to accommodate full narrative + findings
  - Accessible from sidebar above Tape Analytics section (always visible, including Ejari)
  - `_build_ejari_full_context()` extracts portfolio overview, PAR, DPD, cohorts, loss waterfall, roll rates, segments, collections, credit quality, write-offs, legal recovery from parsed ODS
- ✅ **SILQ analytics expansion (3 new tabs):**
  - `compute_silq_seasonality()` — YoY calendar month patterns + seasonal index for POS lending
  - `compute_silq_cohort_loss_waterfall()` — per-vintage: Disbursed → DPD>90 Default → Recovery → Net Loss
  - `compute_silq_underwriting_drift()` — per-vintage quality metrics + z-score drift flags vs 6-month rolling norms
  - All 3 wired into SILQ_CHART_MAP, config.json tabs, frontend chart components, and sidebar
  - SILQ now has 13 tabs (was 9): overview, delinquency, collections, concentration, cohort-analysis, yield-margins, tenure, loss-waterfall, underwriting-drift, seasonality, cdr-ccr, covenants, data-integrity
- ✅ **Unit test coverage expanded:**
  - 134 tests total (66 Klaim + 68 SILQ), all passing
  - Klaim: added PAR dual perspective tests (5 tests)
  - SILQ: added seasonality, cohort loss waterfall, underwriting drift tests (9 tests)
- ✅ **Design elevation (Framer Motion):**
  - KPI cards: stagger fade-in on mount, hover lift + shadow + border brighten
  - Tab content: smooth fade-in/slide transitions on tab switch (Tape + Portfolio)
  - ChartPanel: fade-in animation, skeleton chart bars during loading
  - TabInsight: smooth expand/collapse with AnimatePresence
  - AICommentary: slide-up animation when commentary generates
  - Sidebar: hover effects (text brighten, subtle indent), active background tint
  - Navbar: chip hover transitions
- ✅ **Color scheme aligned to ACP brand:**
  - Base background shifted from `#0C1018` to `#121C27` (ACP navy)
  - All surfaces, borders, and hardcoded colors updated proportionally
  - Warmer, more institutional feel while preserving gold/teal/red/blue semantic palette
- ✅ **As-of date fix:** Defaults to snapshot date (from filename), not max deal date in data
- ✅ **Analysis Framework (Phase 0):**
  - `core/ANALYSIS_FRAMEWORK.md` — analytical philosophy document with 5-level hierarchy (Size → Cash Conversion → Credit Quality → Loss Attribution → Forward Signals)
  - 6 sections: Analytical Hierarchy, Metric Dictionary, Tape vs Portfolio Philosophy, Asset Class Adaptations, Leading vs Lagging Indicators, Separation Principle
  - `GET /framework` endpoint serves markdown content
  - `Framework.jsx` — full-page markdown renderer with sticky TOC, accessed via Navbar link
  - Resources section on Home page with Framework card (teal accent)
- ✅ **PAR (Portfolio at Risk) KPIs:**
  - `compute_par()` with 3 methods: primary (Expected till date shortfall-based estimated DPD), Option C (empirical benchmarks from 50+ completed deals, labeled "Derived"), fallback (`available: False`)
  - `_build_empirical_benchmark()` helper builds collection timing benchmarks from completed deal pool
  - PAR 30+/60+/90+ KPI cards on Overview (balance-weighted + count-based)
  - PAR denominator: active outstanding for Tape, eligible outstanding for Portfolio
- ✅ **Days to First Cash (DTFC):**
  - `compute_dtfc()` — curve-based (precise) and estimated (fallback) methods
  - DTFC Median and P90 KPI cards on Overview — leading indicator that deteriorates before collection rate
- ✅ **DSO Variants:**
  - Enhanced `compute_dso()` with DSO Capital (days from funding to collection) and DSO Operational (days from expected due date to collection)
  - Returns `dso_operational_weighted`, `dso_operational_median`
- ✅ **Loss Waterfall tab (13th tab):**
  - `compute_cohort_loss_waterfall()` — per-vintage: Originated → Gross Default → Recovery → Net Loss with rates
  - `compute_vintage_loss_curves()` — cumulative loss development curves by vintage
  - `compute_loss_categorization()` — rules-based heuristics (provider_issue, coding_error, credit/underwriting)
  - `CohortLossWaterfallChart.jsx` integrates 3 sub-sections: loss waterfall table, vintage loss curves, loss categorization pie
- ✅ **Recovery Analysis tab (14th tab):**
  - `compute_recovery_analysis()` — recovery rates, timing, worst/best deals by vintage
  - `RecoveryAnalysisChart.jsx`
- ✅ **Collections Timing tab (15th tab):**
  - `compute_collections_timing()` — timing bucket distribution using collection curve columns
  - `CollectionsTimingChart.jsx` — stacked bars + portfolio distribution
- ✅ **Underwriting Drift tab (16th tab):**
  - `compute_underwriting_drift()` — per-vintage quality metrics + drift flags when metrics deviate from historical norms
  - `UnderwritingDriftChart.jsx` — dual-axis chart + flag badges
- ✅ **Segment Analysis tab (17th tab):**
  - `compute_segment_analysis()` — multi-dimensional cuts (product, provider_size, deal_size, new_repeat)
  - `SegmentAnalysisChart.jsx` — dimension dropdown + sortable table with heat-map coloring
- ✅ **Seasonality tab (18th tab):**
  - `compute_seasonality()` — YoY comparison by calendar month + seasonal index
  - `SeasonalityChart.jsx` — grouped bars per year + seasonal index line
- ✅ **HHI Time Series:**
  - `compute_hhi_for_snapshot()` — computes HHI for a single snapshot
  - `GET .../charts/hhi-timeseries` endpoint loads ALL snapshots, detects concentration trends + warnings
- ✅ **Separation Principle (clean vs loss portfolio):**
  - `separate_portfolio()` helper splits portfolio into clean (active + normal completed) vs loss (denial > 50% PV)
  - Used by loss attribution functions to isolate write-off cohort
- ✅ **Methodology Transparency:**
  - `compute_methodology_log()` — documents corrections, column availability, data quality decisions for audit trail
- ✅ **Framework-as-Brain system (7 slash commands + framework expansion):**
  - `/onboard-company` — full 6-phase onboarding workflow with framework compliance checks (discovery, data inspection, config, backend, frontend, verification)
  - `/add-tape` — new tape validation, column compatibility, cross-tape consistency, feature impact assessment
  - `/validate-tape` — comprehensive data quality checks with framework-aligned quality scoring (A-F grades)
  - `/framework-audit` — audit ALL companies against framework: L1-L5 coverage, denominator discipline, separation principle, confidence grading, methodology completeness, test coverage
  - `/extend-framework` — add new metrics/tabs/capabilities with guaranteed propagation across all layers (framework doc → backend → frontend → methodology → tests → CLAUDE.md)
  - `/methodology-sync` — detect drift between methodology page and backend compute functions; formula verification, level tag audit
  - `/company-health` — quick diagnostic: coverage, freshness, gaps, comparison table, framework compliance score
  - `core/ANALYSIS_FRAMEWORK.md` expanded with 3 new sections: Compute Function Registry (Section 12), Column-to-Feature Dependency Map (Section 13), Asset Class Decision Tree (Section 14)
  - `core/FRAMEWORK_INDEX.md` — quick reference index for sessions (section map, company registry, command lookup, core principles)
  - CLAUDE.md updated with "Analysis Framework Authority" workflow rules making the framework binding for all analytical decisions
- ✅ **Living Methodology (auto-generated from backend metadata):**
  - `core/metric_registry.py` — decorator registry + `get_methodology()` + `get_registry()`
  - `core/methodology_klaim.py` — 16 sections, 29 metrics, 13 tables (Klaim methodology content as structured data)
  - `core/methodology_silq.py` — 15 sections, 23 metrics, 2 tables (SILQ methodology content as structured data)
  - `data/Ejari/RNPL/methodology.json` — static Ejari methodology served from same endpoint
  - `GET /methodology/{analysis_type}` — returns structured JSON consumed by frontend
  - `GET /methodology-registry` — raw registry for auditing and Section 12 generation
  - `frontend/src/pages/Methodology.jsx` rewritten: 1301 → 290 lines (data-driven renderer)
  - `scripts/sync_framework_registry.py` — auto-generates Section 12 in ANALYSIS_FRAMEWORK.md from the metric registry
  - Adding a new metric to methodology_*.py → Methodology page auto-updates, Section 12 auto-updates
-----
## Known Gaps & Next Steps
**Short term:**
- [x] Onboard SILQ — POS lending asset class (analysis module, validation, tests, 2 tapes live)
- [x] SILQ Feb 2026 tape — three product types (BNPL, RBF, RCL) consistent across both tapes
- [x] Add `core/analysis.py` unit tests — 120 tests (61 Klaim + 59 SILQ), full coverage of all 28 analysis functions
- [x] Replace hardcoded FX rates with live API (exchangerate-api.com, fallback to hardcoded)
- [x] Startup script — `start.ps1` boots both servers + opens browser
- [x] Design elevation — Framer Motion animations, card hover effects, skeleton loading, micro-interactions
- [x] Color scheme — shifted to ACP-aligned warmer navy (`#121C27` base)
- [x] As-of date fix — defaults to snapshot date, not max deal date
- [x] Analysis Framework — 5-level analytical hierarchy document + Framework page with sticky TOC
- [x] 6 new tape analytics tabs — Loss Waterfall, Recovery Analysis, Collections Timing, Underwriting Drift, Segment Analysis, Seasonality
- [x] PAR (Portfolio at Risk) KPIs — 3-method computation, Overview KPI cards
- [x] DTFC (Days to First Cash) — leading indicator on Overview
- [x] DSO Operational variant — days from expected due date to collection
- [x] HHI time series — concentration trend across all snapshots
- [x] Loss categorization — rules-based heuristic classification
- [x] Separation Principle — clean vs loss portfolio isolation
- [x] Methodology transparency log — data corrections and column availability audit trail
**Phase 2 — Borrowing Base Monitoring ✅ COMPLETE:**
- [x] PostgreSQL 18.3 database + SQLAlchemy ORM + Alembic migrations
- [x] Integration API (12 endpoints) with X-API-Key auth
- [x] Portfolio computation engine (borrowing base, concentration, covenants)
- [x] DB-optional fallback to tape data
- [x] Frontend: 6 portfolio tabs with live data
- [x] Seed script + API key generation CLI
**Analytical Framework Expansion ✅ COMPLETE (from Ejari/RNPL deep-dive — applied to ALL companies):**
- [x] PAR as headline Overview KPIs — dual perspective (active + lifetime), 3-method computation, Option C with "Derived" labeling
- [x] Collections timing waterfall — timing bucket distribution using collection curve columns (tab 15)
- [x] Cohort loss waterfall — per-vintage: Originated → Gross Default → Recovery → Net Loss (tab 13)
- [x] Credit quality / underwriting drift — per-vintage quality metrics + z-score drift flags (tab 16)
- [x] Enhanced segment analysis — multi-dimensional cuts: product, provider_size, deal_size, new_repeat (tab 17)
- [x] Roll rate enhancement — roll-rate matrix + cure rates in Risk & Migration tab (tab 11)
- [x] Recovery analysis post-default — recovery rates, timing, worst/best deals by vintage (tab 14)
- [x] Historical vintage performance curves — vintage loss curves in Loss Waterfall tab
- [x] Write-off / loss isolation — Separation Principle (`separate_portfolio()`) splits clean vs loss
- [x] Fraud/anomaly categorization — rules-based heuristics (provider_issue, coding_error, credit/underwriting)
- [x] HHI time series — concentration trend across all snapshots with trend detection + warnings
- [x] DTFC (Days to First Cash) — curve-based + estimated methods, median + P90 on Overview
- [x] DSO dual variants — DSO Capital + DSO Operational (weighted + median)
- [x] Seasonality dashboard — YoY comparison by calendar month + seasonal index (tab 18)
- [x] Methodology transparency — data corrections log, column availability audit trail
- [x] **Analysis Framework document expansion** — formalized: Analytical Hierarchy, Metric Doctrine (denominator/weighting/confidence), Three Clocks, Collection Rate Disambiguation, Dilution Framework, Denominator Discipline, Methodology Onboarding Guide with hierarchy-level mapping. Served via Framework page with sticky TOC.
- [x] **Company Methodology page updates** — Klaim: added PAR (dual denominator, 3 methods), Loss Waterfall (default def, categorization, recovery), Forward-Looking Signals (DTFC, HHI time series, DSO dual perspectives), Advanced Analytics (collections timing, underwriting drift, segment analysis, seasonality). Validation section updated with anomaly detection docs.
**Key analytical design decisions (documented for consistency):**
- PAR denominator: active outstanding (Tape), eligible outstanding (Portfolio). Lifetime rates live in Loss Waterfall as "Gross/Net Default Rate" — different metric, different location.
- PAR without contractual benchmarks: hide (graceful degradation), not estimate. Exception: Option C (empirical curves from completed deals) with explicit "Derived" labeling when robust enough (min N completed deals, min vintage depth).
- Tape Analytics = retrospective, IC-ready analysis. Portfolio Analytics = live monitoring, facility-grade.
- Completed-only metrics for margins/returns. Outstanding-based metrics for ageing/health (not face value).
- Separation principle: clean portfolio for performance metrics, loss portfolio isolated for attribution.
- Denominator discipline: every metric declares total vs active vs eligible. See ANALYSIS_FRAMEWORK.md Section 6.
- Three clocks: origination age, contractual DPD, operational delay. New asset classes must declare which clock drives delinquency. See ANALYSIS_FRAMEWORK.md Section 7.
- Collection rate = GLR (all cash vs face). CRR (capital recovery) shown separately in Returns. See ANALYSIS_FRAMEWORK.md Section 8.
- Dilution (non-credit loss) reframed for Klaim: denial = dilution by reason code. See ANALYSIS_FRAMEWORK.md Section 9.
- Metric doctrine: every metric must declare formula, denominator, weighting, inclusion, clock, confidence grade. See ANALYSIS_FRAMEWORK.md Section 10.
**Portfolio Analytics — Near-term enhancements:**
- [x] Trigger distance + projected breach date on Covenants tab — headroom line (teal ✓) when compliant, projected breach date (amber ⚠) when trend moving toward limit, ↘/↗ direction vs prior snapshot
- [x] Facility params input UI (edit advance rates, concentration limits, covenants from frontend) — FacilityParamsPanel.jsx + backend endpoints complete
- [x] BB Movement Attribution waterfall — period-over-period decomposition of BB drivers (Δ portfolio size, Δ eligibility, Δ concentration+rate, Δ cash). Frontend panel with mini diverging bars.
- [x] Breakeven analysis — eligible cushion + stress % added to borrowing-base endpoint; "Breakeven Analysis" panel in BorrowingBase.jsx shows headroom, stress threshold, cushion.
- [x] BB Sensitivity formulas — ∂BB/∂advance_rate per 1pp and ∂BB/∂ineligible per 1M; "Sensitivity" panel alongside breakeven.
**Data Quality — Near-term enhancements:**
- [x] Duplicate/anomaly detection in validation — 5 new checks: duplicate counterparty+amount+date combos, identical amount concentration, deal size outliers (3×IQR), discount outliers (3×IQR), balance identity violations
- [x] Confidence grading badges on metrics — A (observed), B (inferred), C (derived) displayed in UI via KpiCard `confidence` prop. Klaim Overview and PAR/DTFC/DSO cards graded dynamically.
**Portfolio Analytics — Medium-term:**
- [x] Automated compliance certificate / BBC export — `core/compliance_cert.py` (ReportLab dark-themed PDF: facility summary, waterfall, concentration limits, covenants, officer cert); `POST .../portfolio/compliance-cert` streams PDF; "Download BBC" button in BorrowingBase.jsx.
- [x] Conditional monthly rates (CDR/CCR) — `compute_cdr_ccr()` (Klaim) + `compute_silq_cdr_ccr()` (SILQ); new tab for both; annualizes cumulative default/collection rates by vintage age to strip out maturity effects; 4 KPI tiles + dual-line chart + net spread line
- [x] Breach notification system (Slack webhook) — `POST .../portfolio/notify-breaches` sends Slack block message; webhook URL in FacilityParamsPanel Notifications section; "Notify" bell button in Covenants header.
- [ ] Portfolio company onboarding flow (self-service API key provisioning)
- [ ] Facility-mode PD — probability of aging into ineligibility (not just credit default)
- [ ] Recovery discounting — PV-adjusted LGD using discount rate (undiscounted LGD overstates recovery value)
**Phase 3 (Team & Deployment):**
- [x] Cloud deployment
- [ ] Role-based access (RBAC)
- [ ] Scheduled report delivery
- [ ] Real-time webhook notifications to portfolio companies
- [ ] AI-powered covenant extraction — ingest facility agreement PDFs, extract advance rates, concentration limits, covenant formulas, eligibility criteria → auto-populate facility_configs
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
