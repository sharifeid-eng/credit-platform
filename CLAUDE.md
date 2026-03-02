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
- **Logo component:** `LaithLogo` exported from `Navbar.jsx`, used in both Navbar and Home page
- **Page title:** `Laith — Portfolio Analytics` (set in `frontend/index.html`)
- **Note:** Original SVG at `frontend/public/logo.svg` has white background, not suitable for dark theme. Using styled component instead.
-----
## Business Context
**Who uses it:** Sharif (fund analyst/PM) and eventually the broader investment committee.
**Current portfolio companies:**
- **Klaim** — medical insurance claims factoring, UAE. Data in AED. Live dataset: `data/klaim/UAE_healthcare/`
- **SILQ** — POS lending. Not yet onboarded into the platform.
**Asset classes:** Receivables (insurance claims factoring) and short-term consumer/POS loans.
**Data format:** Single Excel or CSV loan tapes, typically thousands to tens of thousands of rows. Each row is a deal/receivable. Snapshots are taken periodically (e.g. monthly) and named `YYYY-MM-DD_description.csv`.
**Data notes:**
- September 2025 tape has `Expected IRR` and `Actual IRR` columns; newer tapes (Dec 2025, Feb 2026) do not
- All tapes have `Discount` column (values range 1%–41%, concentrated at 4–7%)
- `New business` column available for new vs repeat analysis
- Fee columns: `Setup fee`, `Other fee`, `Adjustments`
- Loss tracking: `Provisions`, `Denied by insurance`
-----
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
- Direct API integrations with portfolio companies' accounting or loan management systems
- Cloud deployment so the app runs 24/7
-----
## Tech Stack
- **Backend:** Python, FastAPI (`localhost:8000`), Pandas, Anthropic API (`claude-opus-4-6`), ReportLab (PDF)
- **Frontend:** React (Vite), Tailwind CSS, Recharts, React Router, Axios (`localhost:5173`)
- **AI:** Anthropic API — portfolio commentary, per-tab insights, data chat, PDF integrity reports
- **Data:** CSV/Excel files stored locally under `data/`
-----
## How to Start the App (Every Session)
**Terminal 1 — Backend:**
```bash
cd C:\Users\SharifEid\credit-platform
venv\Scripts\activate
cd backend
python -m uvicorn main:app --reload
```
**Terminal 2 — Frontend (no venv needed):**
```bash
cd C:\Users\SharifEid\credit-platform\frontend
npm run dev
```
Then open `http://localhost:5173` in the browser.
-----
## Project Structure
```
credit-platform/
├── analyze.py              # Legacy CLI analysis tool (still functional)
├── .env                    # API key — NEVER committed to GitHub
├── .env.example            # Placeholder showing required env vars
├── .gitignore              # Must include: .env, node_modules/, venv/, __pycache__/, reports/
├── backend/
│   └── main.py             # FastAPI app — all REST endpoints
├── core/
│   ├── analysis.py         # All pure data computation functions (no I/O)
│   ├── loader.py           # File discovery, snapshot loading
│   ├── config.py           # Per-product config (currency, description) via config.json
│   ├── consistency.py      # Snapshot-to-snapshot data integrity checks
│   ├── migration.py        # Multi-snapshot roll-rate & cure-rate analysis
│   ├── validation.py       # Single-tape data quality checks
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
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── Company.jsx
│   │   │   └── Methodology.jsx    # Definitions, formulas, rationale for all analytics
│   │   ├── components/
│   │   │   ├── CompanyCard.jsx
│   │   │   ├── KpiCard.jsx
│   │   │   ├── Navbar.jsx          # Contains LaithLogo component (exported)
│   │   │   ├── AICommentary.jsx
│   │   │   ├── DataChat.jsx
│   │   │   ├── TabInsight.jsx
│   │   │   ├── ChartPanel.jsx
│   │   │   └── charts/
│   │   │       ├── ActualVsExpectedChart.jsx
│   │   │       ├── AgeingChart.jsx
│   │   │       ├── CohortTable.jsx           # Enhanced: IRR, pending, loss rate, totals row
│   │   │       ├── CollectionVelocityChart.jsx
│   │   │       ├── ConcentrationChart.jsx
│   │   │       ├── DenialTrendChart.jsx
│   │   │       ├── DeploymentChart.jsx
│   │   │       ├── RevenueChart.jsx
│   │   │       ├── ReturnsAnalysisChart.jsx  # Discount bands, margins, new vs repeat
│   │   │       ├── RiskMigrationChart.jsx   # Roll-rates, cure rates, EL model, stress test
│   │   │       ├── DenialFunnelChart.jsx    # Resolution pipeline funnel visualization
│   │   │       └── DataIntegrityChart.jsx   # Two-tape comparison, validation, AI report + notes
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
|`GET /companies/{co}/products/{p}/charts/collection-velocity`|Collection timing                  |
|`GET /companies/{co}/products/{p}/charts/denial-trend`       |Denial rate trend                  |
|`GET /companies/{co}/products/{p}/charts/cohort`             |Vintage cohort analysis            |
|`GET /companies/{co}/products/{p}/charts/actual-vs-expected` |Cumulative actual vs expected      |
|`GET /companies/{co}/products/{p}/charts/ageing`             |Active deal health + ageing        |
|`GET /companies/{co}/products/{p}/charts/revenue`            |Revenue analysis                   |
|`GET /companies/{co}/products/{p}/charts/concentration`      |Group/product concentration        |
|`GET /companies/{co}/products/{p}/charts/returns-analysis`   |Returns, discounts, new vs repeat  |
|`GET /companies/{co}/products/{p}/charts/dso`                |DSO metrics (weighted, median, p95) |
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
|`POST /companies/{co}/products/{p}/chat`                     |AI data chat                       |
All chart endpoints accept: `snapshot`, `as_of_date`, `currency` query params.
-----
## Dashboard Tabs (12)
|Tab               |What It Shows                                                   |
|------------------|----------------------------------------------------------------|
|Overview          |10 KPI cards (incl DSO + HHI) + AI commentary + Data Chat       |
|Actual vs Expected|Cumulative collected vs expected area chart + performance %     |
|Deployment        |Monthly capital deployed (new vs repeat stacked bar)            |
|Collection        |Monthly collection rate + completed deals by days outstanding   |
|Denial Trend      |Monthly denial rate bars + 3M rolling average                   |
|Ageing            |Health donut (Healthy/Watch/Delayed/Poor) + ageing bucket bars  |
|Revenue           |Realised/unrealised stacked bars + gross margin line + KPI tiles|
|Portfolio         |Group + product concentration donuts + top 10 deals table       |
|Cohort Analysis   |Enhanced vintage table: 14 columns incl IRR, pending, loss rate, totals row|
|Returns           |Margin KPIs, monthly returns chart, discount band analysis, new vs repeat|
|Risk & Migration  |Roll-rate matrix, cure rates, EL model (PD×LGD×EAD), stress test scenarios|
|Data Integrity    |Two-tape comparison: per-tape validation, cross-tape consistency, AI report + per-question notes|
Each non-overview tab (except Data Integrity) has a **TabInsight** component — a teal bar at the top with a one-click AI insight.
Dashboard controls: Product selector, Snapshot selector, As-of Date picker, Currency toggle (local ↔ USD).
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
- **AICommentary caching** — stored in `Company.jsx` state, survives tab switches, clears on snapshot change.
- **API response extraction** — `api.js` extracts: `.commentary` for AI commentary, `.insight` for tab insights, `.answer` for chat responses.
- **Text contrast** — `--text-muted` updated from `#4A5568` to `#8494A7` for readability on dark theme.
- **IRR derivation** — backend calculates IRR for tapes that lack IRR columns (derived from purchase price, collected, deal dates).
- All AI calls use `claude-opus-4-6`.
- **`core/migration.py`** — multi-snapshot roll-rate analysis. Requires ≥2 snapshots. Matches deals by ID column across tapes.
- **`core/validation.py`** — single-tape integrity checks (dupes, date sanity, negatives, nulls, logical consistency).
- **Risk migration endpoint** — auto-selects the two most recent snapshots for comparison. Also bundles stress test + EL model results.
- **Data Integrity tab** — two-step workflow: Run Checks (fast, no API cost) → Generate AI Report (Claude API call). Results, reports, and notes cached as JSON files in `reports/{company}_{product}/`. Auto-loads cached results on tab load. Notes saved with 500ms debounce.
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
- Ageing: health in `res.health_summary[]`, buckets in `res.ageing_buckets[]`
- Concentration: groups in `res.group[]`, top deals in `res.top_deals[]`, HHI in `res.hhi{}`
- Returns analysis: `res.summary{}`, `res.monthly[]`, `res.discount_bands[]`, `res.new_vs_repeat[]`
- DSO: `res.weighted_dso`, `res.median_dso`, `res.p95_dso`, `res.by_vintage[]`
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
- Summary API returns: `total_deals`, `total_purchase_value`, `total_collected`, `total_denied`, `total_pending`, `collection_rate`, `denial_rate`, `pending_rate`, `active_deals`, `completed_deals`
- Snapshots API returns objects `{filename, date}` — must extract `.filename`
- Companies API may return objects — must extract `.name`
-----
## What's Working
- ✅ Full backend with all chart and AI endpoints (including returns-analysis)
- ✅ 12-tab React dashboard with dark theme
- ✅ AI commentary (cached, clears on snapshot change)
- ✅ Per-tab AI insights (TabInsight)
- ✅ Data chat (natural language questions)
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
-----
## Known Gaps & Next Steps
**Short term:**
- [ ] Onboard SILQ — POS lending asset class
- [ ] Add `core/analysis.py` unit tests
- [ ] Replace hardcoded FX rates with live API
- [ ] Startup script — single command to boot both servers
**Phase 2 (Borrowing Base Monitoring):**
- [ ] Eligibility criteria testing per deal
- [ ] Concentration limit tracking
- [ ] Advance rate calculations
- [ ] Covenant monitoring and breach alerts
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
