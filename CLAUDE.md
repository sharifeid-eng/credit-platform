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
- **State assumptions explicitly.** Before implementing any non-trivial feature, list your assumptions (data availability, API contract, column names, user workflow, external service behavior). If uncertain about any, ask — don't guess silently. (See lessons.md: sort order, registry format — all caused by silent assumptions.)
- **Surface ambiguity.** If a requirement could have 2+ interpretations, present all of them and ask the user to pick. Don't silently choose one. Example: "Add export" could mean API endpoint, file download, or background job — name the options.

### Coding Discipline (adapted from Karpathy's principles)

**These four principles are binding for all non-trivial work. For obvious one-liners, use judgment.**

**1. Think Before Coding — Don't assume. Don't hide confusion. Surface tradeoffs.**
- State your assumptions before writing code. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
- **For third-party integrations:** Install the package, inspect the API surface (`dir()`, `inspect.signature()`), write a minimal test BEFORE writing production code. Never code against a guessed interface.

**2. Simplicity First — Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- **Prefer files over infrastructure.** Before adding a database table, cache layer, or new storage format, verify you can't solve it with existing files (JSON, JSONL, CSV in `data/`) + in-process query.
- **Litmus test:** "Would a senior engineer say this is overcomplicated?" If yes, simplify.

**3. Surgical Changes — Touch only what you must. Clean up only your own mess.**
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code unless asked.
- **The test:** Every changed line should trace directly to the user's request.

**4. Goal-Driven Execution — Define success criteria. Loop until verified.**
- Transform tasks into verifiable goals:
  - "Add validation" → "Write tests for invalid inputs, then make them pass"
  - "Fix the bug" → "Write a test that reproduces it, then make it pass"
  - "Refactor X" → "Ensure tests pass before and after"
- For multi-step tasks, state a brief plan with verification per step:
  ```
  1. [Step] → verify: [check]
  2. [Step] → verify: [check]
  3. [Step] → verify: [check]
  ```
- Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

### Execution
- **Subagents:** Offload research, exploration, and parallel analysis to subagents. One task per subagent for focused execution. Keep main context window clean. **Quality gate:** Every subagent prompt must include (a) a written spec (what to do and why), (b) success criteria (3 items), (c) known constraints (specific modules, APIs, files to use). No blank-check subagents. When a subagent writes cross-module imports, verify function names exist (`grep "def function_name" target_module.py`).
- **Simplicity first:** Make every change as simple as possible. Minimal impact. Only touch what's necessary.
- **No laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Autonomous bug fixing:** When given a bug report: (1) reproduce it with a test, (2) find the root cause (check `tasks/lessons.md` for related patterns), (3) fix it. If the bug might be systemic (affects other companies, other endpoints), flag it before patching — don't silently fix one instance.

### Verification
- Never mark a task complete without proving it works — run tests, check logs, demonstrate correctness.
- **Test-first by default.** Before implementing: write the test for the happy path. Implementation is done when that test passes. Then add 2-3 edge-case tests. For financial functions, include at least one test with a non-1.0 FX multiplier.
- When a task depends on external data (tape edits, DB migrations), **verify the data first** before updating code that references it.

### Integration Discipline (learned 2026-04-17 — BINDING)
- **Plans organized by user outcome, not technical layer.** Each feature is a vertical slice through the stack (backend + frontend + wiring). A feature is not done until the user's experience changes.
- **Verification = user action.** Every verification step must start with what the user does ("Load dashboard → click X → observe Y"), not what code exists.
- **"Who calls this?" gate.** For every new function/hook/endpoint, identify the specific call site in a .jsx component or endpoint handler. If nothing calls it, it's dead capability — not a completed feature.
- **Integration sweep before marking multi-phase plans complete.** After all phases: does every backend capability have a frontend caller? Does every frontend hook have a component using it? Does every event listener do work (not just log)?
- **"Diff of user experience" gate.** Before marking done: "What does the user see differently?" If only "new endpoints exist" — it's infrastructure, not a feature.
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
- Generate AI-powered IC investment memos with data room research integration
- Query documents across data rooms using AI-powered research (Claude RAG)
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
- **SILQ** — POS lending, KSA. Data in SAR. Live dataset: `data/SILQ/KSA/` (4 tapes: Nov 2025, Jan 2026, Feb 2026, Mar 2026). Three product types: BNPL, RBF, RCL (Revolving Credit Line). Has dedicated analysis module (`core/analysis_silq.py`), validation (`core/validation_silq.py`), dynamic chart endpoint, and tests.
- **Ejari** — Rent Now Pay Later (RNPL), KSA. Data in USD. **Read-only summary** — no raw loan tape, only a pre-computed ODS workbook with 13 sheets of analysis. Rendered as a dedicated dashboard (`EjariDashboard.jsx`) without live computation. Parser: `core/analysis_ejari.py`. Config: `analysis_type: "ejari_summary"`. Live dataset: `data/Ejari/RNPL/`
- **Tamara** — Buy Now Pay Later (BNPL + BNPL+), KSA & UAE. Saudi Arabia's first fintech unicorn ($1B valuation, 20M+ users, 87K+ merchants). **Data room ingestion** — ~100 source files (vintage cohort matrices, Deloitte FDD, HSBC investor reports, financial models) parsed by `scripts/prepare_tamara_data.py` into structured JSON snapshots. Two products: KSA (SAR, 14 tabs) and UAE (AED, 10 tabs). Dashboard: `TamaraDashboard.jsx`. Parser: `core/analysis_tamara.py`. Config: `analysis_type: "tamara_summary"`. Securitisation: KSA $2.375B (Goldman, Citi, Apollo), UAE $131M (Goldman). Live dataset: `data/Tamara/{KSA,UAE}/`
- **Aajil** — SME raw materials trade credit, KSA. Data in SAR. **Live tape analytics** — multi-sheet xlsx (1,245 deals, 7 sheets: Deals, Payments, DPD Cohorts, Collections). 227 customers, SAR 381M GMV (Principal Amount), SAR 80M outstanding, 87.3% collection rate, 1.5% write-off (19 deals, all Bullet). 3 customer types: Manufacturer, Contractor, Wholesale Trader. Deal types: EMI (51%) and Bullet (49%). Has dedicated analysis module (`core/analysis_aajil.py`, 11 compute functions), validation (`core/validation_aajil.py`), dynamic chart endpoint, and 38 tests. Dashboard: `AajilDashboard.jsx` (13 tabs). Config: `analysis_type: "aajil"`. Live dataset: `data/Aajil/KSA/`. Uses Cascade Debt (app.cascadedebt.com) as external reporting platform. Dataroom: 14 files (investor deck, audited financials, tax returns, budget).
**Asset classes:** Receivables (insurance claims factoring), short-term consumer/POS loans, rent payment financing (RNPL), BNPL consumer instalment lending, and SME trade credit (raw materials).
**Data format:** Single Excel or CSV loan tapes, typically thousands to tens of thousands of rows. Each row is a deal/receivable. Snapshots are taken periodically (e.g. monthly) and named `YYYY-MM-DD_description.csv`. Also supports ODS files (Ejari summary workbook) and JSON files (Tamara data room ingestion).
**Data notes:**
- **Tapes available:** Sep 2025 (25 cols), Dec 2025 (xlsx), Feb 2026 (25 cols), Mar 2026 (60 cols), Apr 2026 (65 cols — latest full snapshot, 8,080 deals)
- Apr 2026 tape (8,080 deals, full portfolio) adds 5 columns: `Expected collection days`, `Collection days so far`, `AccountManager`, `SalesManager`, `Provider`. Enables direct DPD for PAR, temporal Paid vs Due, and direct DSO Operational.
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
- Portfolio computation engine (`core/portfolio.py`) reading snapshot-dimensioned DB (tape uploads + Integration API live pushes both create snapshots; Session 31)
- Frontend: 6 portfolio tabs (Borrowing Base, Concentration Limits, Covenants, Invoices, Payments, Bank Statements)
### Phase 3 — Team & IC Viewing Layer ✅ (partial)
- ✅ Role-based access (admin vs viewer via Cloudflare Access JWT)
- ✅ Cloud deployment (Hetzner VPS, Docker Compose, Cloudflare Access)
- Scheduled report delivery
- Expand roles (analyst, IC, read-only)
-----
## Tech Stack
- **Backend:** Python, FastAPI (`localhost:8000`), Pandas, Anthropic API (`claude-opus-4-6`), ReportLab (PDF)
- **Database:** PostgreSQL 18.3, SQLAlchemy 2.0 (async-ready), Alembic (migrations), psycopg2
- **Frontend:** React (Vite), Tailwind CSS, Recharts, Framer Motion, React Router, Axios (`localhost:5173`)
- **AI:** Anthropic API — portfolio commentary, per-tab insights, data chat, PDF integrity reports
- **PDF Reports:** Playwright (headless Chrome) for dashboard screenshots + ReportLab for PDF composition
- **Data sources:**
  - **Tape Analytics:** CSV/Excel files stored locally under `data/` (manual upload)
  - **Portfolio Analytics:** PostgreSQL database (REQUIRED — Session 31 removed the tape-fallback read path). Tape uploads populate DB via `scripts/ingest_tape.py` (one Snapshot per file); Integration API writes populate a rolling-daily `live-YYYY-MM-DD` snapshot. DB is the only runtime source.
-----
## How to Start the App (Every Session)
**One command (recommended):**
```powershell
cd C:\Users\SharifEid\credit-platform
.\start.ps1
```
Opens two terminal windows (backend + frontend) and launches the browser automatically.

**Manual start (if needed):**
- Terminal 1 — Backend: `cd credit-platform && venv\Scripts\activate && python -m uvicorn backend.main:app --reload`
  > **IMPORTANT:** Run from the project root, NOT from `backend/`. Running from `backend/` causes `backend/operator.py` to shadow Python's built-in `operator` module (circular import crash on Python 3.14+). Use `backend.main:app` (dot notation) from the project root.
- Terminal 2 — Frontend: `cd credit-platform\frontend && npm run dev`
- Then open `http://localhost:5173`
-----
## Project Structure
```
credit-platform/
├── analyze.py              # Legacy CLI analysis tool (still functional)
├── generate_report.py      # Playwright + ReportLab PDF report generator (CLI + backend)
├── WEEKEND_DEEP_WORK.md    # 7-mode analytical audit protocol (health, tests, architecture, docs, prompts, red team, regression)
├── .env                    # API key + DATABASE_URL — NEVER committed to GitHub
├── .gitignore              # Must include: .env, node_modules/, venv/, __pycache__/, reports/
├── alembic/
│   ├── env.py              # Alembic migration environment
│   └── versions/
│       └── aa1a0a4ec761_initial_schema_6_tables.py  # Initial migration (6 tables)
├── alembic.ini             # Alembic config
├── backend/
│   ├── main.py             # FastAPI app — all REST endpoints (tape + portfolio + legal)
│   ├── legal.py            # Legal Analysis API endpoints (upload, extract, compare)
│   ├── auth.py             # X-API-Key authentication for integration endpoints
│   ├── cf_auth.py          # Cloudflare Access JWT verification, auth middleware, user auto-provision
│   ├── auth_routes.py      # Auth API routes (/auth/me, /auth/users CRUD)
│   ├── integration.py      # 12 inbound integration API endpoints (invoices/payments/bank statements)
│   ├── intelligence.py     # Intelligence System endpoints (thesis, briefing, learning, KB search, feedback)
│   ├── external.py         # External Intelligence endpoints — /api/pending-review, /api/asset-class-mind, /api/mind/promote
│   ├── onboarding.py       # Self-service org/product/API key provisioning (2 endpoints)
│   ├── operator.py         # Operator Command Center endpoints (status, todo, mind review, digest)
│   └── schemas.py          # Pydantic request/response models for integration API
├── core/
│   ├── activity_log.py     # Centralized JSONL event logger — imported by all instrumented endpoints
│   ├── ANALYSIS_FRAMEWORK.md # Analytical philosophy document (14 sections: hierarchy, clocks, denominators, decision trees, compute registry)
│   ├── FRAMEWORK_INDEX.md  # Quick reference index — section map, company registry, command lookup, core principles
│   ├── LEGAL_EXTRACTION_SCHEMA.md  # Legal extraction taxonomy — field schemas, confidence grading, param mapping
│   ├── legal_schemas.py    # Pydantic models for legal extraction output
│   ├── legal_parser.py     # PDF-to-markdown conversion (PyMuPDF + pymupdf4llm + pdfplumber)
│   ├── legal_extractor.py  # Multi-pass Claude extraction engine (5 passes, cached)
│   ├── legal_compliance.py # Compliance comparison: doc terms vs live portfolio metrics
│   ├── dataroom/              # Data room ingestion engine
│   │   ├── engine.py          # Main orchestrator: ingest, catalog, search, refresh, audit, wipe, rebuild_index_only
│   │   ├── analytics_snapshot.py  # Snapshot tape/portfolio/AI outputs as research sources
│   │   ├── chunker.py         # Document chunking for search (800-token chunks)
│   │   ├── classifier.py      # Rule-based document type classification (21 types: 16 original + 5 new)
│   │   ├── classifier_llm.py  # Haiku LLM fallback for OTHER (sha256-keyed cache)
│   │   ├── ingest_log.py      # Append-only JSONL manifest per ingest/refresh
│   │   └── parsers/           # Pluggable parsers: PDF, Excel, CSV, JSON, DOCX, ODS
│   ├── research/              # Research intelligence layer
│   │   ├── query_engine.py    # Claude RAG: retrieve + synthesize with citations
│   │   ├── dual_engine.py     # Research orchestrator (Claude RAG)
│   │   └── extractors.py      # Rules-based insight extraction at ingest time
│   ├── ai_client.py           # Central Anthropic client: retry/backoff, tier routing, cache helpers, cost est
│   ├── memo/                  # IC Memo Engine — Hybrid 6-Stage Pipeline
│   │   ├── templates.py       # 5 IC memo templates (credit, DD, monitoring, quarterly, amendment)
│   │   ├── analytics_bridge.py    # Pulls live analytics into memo sections (multi-company, aux sheets)
│   │   ├── generator.py       # Hybrid pipeline: parallel structured + agent research + citation audit + polish
│   │   ├── agent_research.py  # Short-burst agent research packs (5-turn cap, structured JSON, thesis recorder)
│   │   ├── storage.py         # File-based versioning + sidecar storage (research_packs.json, citation_issues.json)
│   │   └── pdf_export.py      # Dark-themed PDF export for memos
│   ├── external/              # External Intelligence — trust-boundary queue
│   │   ├── __init__.py
│   │   └── pending_review.py  # File-backed queue: external evidence never auto-writes to Mind
│   ├── mind/                  # Living Mind + Intelligence System
│   │   ├── master_mind.py     # Fund-level: preferences, IC norms, cross-company patterns, sector_context
│   │   ├── asset_class_mind.py # Per-asset-class (config.json `asset_class` field): benchmarks, typical_terms, external_research, peer_comparison (Layer 2.5)
│   │   ├── company_mind.py    # Per-company: corrections, findings, IC feedback, data quality
│   │   ├── promotion.py       # Company → Asset Class → Master promotion with full provenance
│   │   ├── schema.py          # KnowledgeNode + Relation dataclasses (extends MindEntry)
│   │   ├── relation_index.py  # Bidirectional adjacency list for node relations
│   │   ├── event_bus.py       # Lightweight sync pub/sub for knowledge events
│   │   ├── graph.py           # Graph-aware query engine with scoring + traversal
│   │   ├── entity_extractor.py # Regex-based entity extraction (7 types) from text + metrics
│   │   ├── compiler.py        # Incremental compilation: one input → many node updates
│   │   ├── learning.py        # Closed-loop learning: correction → auto-rule generation
│   │   ├── listeners.py       # Event bus listeners (compilation, learning, thesis)
│   │   ├── thesis.py          # Investment thesis tracker with drift detection
│   │   ├── intelligence.py    # Cross-company pattern detection
│   │   ├── briefing.py        # Morning briefing generator (urgency-scored)
│   │   ├── analyst.py         # Persistent analyst context store
│   │   ├── session.py         # Session state tracker for delta briefings
│   │   ├── kb_decomposer.py   # Decomposes lessons.md + CLAUDE.md into KnowledgeNodes
│   │   ├── kb_query.py        # Unified search across all knowledge stores
│   │   └── framework_codification.py  # Session 28 D6 — surfaces framework_evolution queue + mark_codified flag
│   ├── metric_registry.py  # @metric decorator + METRIC_REGISTRY + get_methodology() — powers living methodology
│   ├── methodology_klaim.py # Klaim methodology metadata (16 sections, 29 metrics, 13 tables)
│   ├── methodology_silq.py # SILQ methodology metadata (15 sections, 23 metrics, 2 tables)
│   ├── analysis.py         # All pure Klaim data computation functions (no I/O) — 40+ compute functions
│   ├── analysis_silq.py    # SILQ-specific analysis functions (9 compute functions)
│   ├── analysis_ejari.py   # Ejari ODS workbook parser (read-only summary, 12 sections)
│   ├── analysis_tamara.py  # Tamara BNPL JSON parser + enrichment (data room ingestion pattern)
│   ├── analysis_aajil.py   # Aajil SME trade credit JSON parser + enrichment (investor deck pattern)
│   ├── research_report.py  # Platform-level credit research report PDF generator (any company)
│   ├── database.py         # SQLAlchemy 2.0 engine/session setup
│   ├── db_loader.py        # Snapshot-scoped DB → tape-compatible DataFrame (list_snapshots, resolve_snapshot, extra_data spread-back)
│   ├── loader.py           # File discovery, snapshot loading
│   ├── config.py           # Per-product config (currency, description) via config.json
│   ├── consistency.py      # Snapshot-to-snapshot data integrity checks
│   ├── migration.py        # Multi-snapshot roll-rate & cure-rate analysis
│   ├── models.py           # SQLAlchemy ORM models (6 tables: Organization, Product, Invoice, Payment, BankStatement, FacilityConfig)
│   ├── portfolio.py        # Portfolio analytics computation (borrowing base, concentration, covenants)
│   ├── validation.py       # Single-tape data quality checks (Klaim)
│   ├── validation_silq.py  # SILQ-specific data quality checks
│   ├── validation_aajil.py # Aajil-specific data quality checks (13 checks)
│   └── reporter.py         # AI-generated PDF data integrity reports (ReportLab)
├── data/
│   ├── _master_mind/          # Fund-level Living Mind (JSONL files)
│   ├── _asset_class_mind/     # NEW — Per-analysis_type Living Mind (one JSONL per asset class)
│   ├── _pending_review/       # NEW — External-origin entries awaiting analyst approval (queue.jsonl)
│   └── {company}/
│       ├── mind/              # Company-level Living Mind (JSONL files)
│       ├── legal/             # Legal documents and extraction cache
│       ├── dataroom/          # Ingested documents, chunks, search index
│       │   ├── registry.json
│       │   ├── chunks/
│       │   ├── analytics/
│       │   └── index.pkl
│       └── {product}/
│           ├── config.json
│           └── YYYY-MM-DD_{name}.csv
├── frontend/
│   ├── public/
│   │   └── logo.svg        # Original logo (white bg — not used in dark theme)
│   ├── src/
│   │   ├── App.jsx                  # Nested routes with CompanyLayout
│   │   ├── contexts/
│   │   │   ├── AuthContext.jsx       # Auth state provider (user, isAdmin, logout, refreshUser)
│   │   │   ├── CompanyContext.jsx    # Shared state provider (company, product, snapshots, config)
│   │   │   └── MobileMenuContext.jsx # Sidebar drawer state (open/close/toggle) + body scroll lock
│   │   ├── layouts/
│   │   │   └── CompanyLayout.jsx    # Sidebar + <Outlet> wrapper with CompanyProvider + mobile backdrop
│   │   ├── pages/
│   │   │   ├── Home.jsx             # Landing page — company grid + resources section
│   │   │   ├── TapeAnalytics.jsx    # 18-tab tape dashboard (extracted from old Company.jsx)
│   │   │   ├── PortfolioAnalytics.jsx  # 6-tab portfolio view (live data from DB/tape)
│   │   │   ├── LegalAnalytics.jsx   # 8-tab legal document analysis
│   │   │   ├── Framework.jsx        # Analysis Framework page (/framework) — analytical philosophy with sticky TOC
│   │   │   ├── Architecture.jsx     # NEW — Platform architecture (/architecture) — live stats + feedback-loops + component diagrams
│   │   │   ├── Methodology.jsx      # Definitions, formulas, rationale for all analytics
│   │   │   ├── ExecutiveSummary.jsx # AI Executive Summary — credit memo narrative + ranked findings
│   │   │   ├── OperatorCenter.jsx  # Operator Command Center (5-tab: health, commands, follow-ups, activity, mind)
│   │   │   ├── UserManagement.jsx  # Admin user management page (/admin/users)
│   │   │   ├── EjariDashboard.jsx  # Read-only Ejari summary dashboard (12 sections from ODS)
│   │   │   ├── TamaraDashboard.jsx # Tamara BNPL dashboard (14 KSA + 10 UAE tabs, VintageHeatmap, CovenantTriggerCards)
│   │   │   ├── AajilDashboard.jsx  # Aajil SME trade credit dashboard (13 tabs, Cascade-inspired Traction + GrowthStats)
│   │   │   └── Onboarding.jsx      # Self-service company onboarding (4-step form: org → products → review → API key)
│   │   │   ├── research/          # Research Hub pages
│   │   │   │   ├── DocumentLibrary.jsx   # Browse ingested documents
│   │   │   │   ├── ResearchChat.jsx      # AI chat across all documents
│   │   │   │   ├── MemoBuilder.jsx       # 4-step memo creation wizard
│   │   │   │   ├── MemoEditor.jsx        # View/edit/regenerate memo sections
│   │   │   │   └── MemoArchive.jsx       # Historical memos with filter
│   │   ├── hooks/
│   │   │   └── useBreakpoint.js         # Mobile/tablet/desktop detection via matchMedia listeners
│   │   ├── components/
│   │   │   ├── ProtectedRoute.jsx       # Auth route guard (redirects if not authenticated/not admin)
│   │   │   ├── Sidebar.jsx              # Persistent nav — 240px desktop, slide-in drawer on mobile
│   │   │   ├── KpiCard.jsx              # Framer Motion stagger + hover effects + optional sparklineData prop
│   │   │   ├── Navbar.jsx               # Responsive — hamburger menu on mobile, contains LaithLogo + UserMenu
│   │   │   ├── AICommentary.jsx         # Slide-up animation on commentary
│   │   │   ├── DataChat.jsx
│   │   │   ├── TabInsight.jsx           # Smooth expand/collapse with AnimatePresence
│   │   │   ├── ChartPanel.jsx           # Fade-in + skeleton chart loading + overflowX auto
│   │   │   ├── PortfolioStatsHero.jsx   # Landing page stats strip — responsive gap/sizing for mobile
│   │   │   ├── SnapshotSelect.jsx       # Custom dropdown with TAPE/LIVE/MANUAL colour-coded pills; keyboard nav; used by Tape Analytics + Data Integrity chart
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
│   │   │   │   ├── VintageHeatmap.jsx            # Shared: CSS grid vintage × MOB heatmap (from Tamara)
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
│   │   │   ├── legal/
│   │   │   │   ├── DocumentUpload.jsx     # PDF upload + document inventory
│   │   │   │   ├── FacilityTerms.jsx      # Extracted facility overview
│   │   │   │   ├── EligibilityView.jsx    # Eligibility criteria + advance rates
│   │   │   │   ├── CovenantComparison.jsx # Doc thresholds vs live compliance
│   │   │   │   ├── EventsOfDefault.jsx    # EOD triggers + severity
│   │   │   │   ├── ReportingCalendar.jsx  # Reporting obligations
│   │   │   │   ├── RiskAssessment.jsx     # AI risk flags
│   │   │   │   └── AmendmentHistory.jsx   # Version comparison
│   │   │   └── portfolio/
│   │   │       ├── BorrowingBase.jsx         # Waterfall, KPIs, advance rates, facility capacity
│   │   │       ├── ConcentrationLimits.jsx   # Limit cards with compliance badges + breaching items
│   │   │       ├── Covenants.jsx             # Covenant cards with threshold bars + historical dates
│   │   │       ├── WaterfallTable.jsx        # Borrowing base waterfall table
│   │   │       ├── LimitCard.jsx             # Click-to-expand limit card (breaching items, adjustments)
│   │   │       ├── CovenantCard.jsx          # Covenant card with threshold visualization
│   │   │       ├── CovenantTriggerCard.jsx  # Shared: 3-level trigger zone visualization (from Tamara)
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
│   ├── test_analysis_silq.py   # Integration tests for SILQ analytics
│   ├── test_analysis_aajil.py  # Integration tests for Aajil analytics (38 tests)
│   ├── test_ai_client.py         # Central client: tier routing, caching, retry (18 tests)
│   ├── test_memo_agent_research.py # Research pack parser + format helper (15 tests)
│   ├── test_memo_pipeline.py       # End-to-end hybrid pipeline (8 tests)
│   ├── test_memo_enhancements.py   # 5 quality enhancements (19 tests)
│   ├── test_external_intelligence.py # Session 28 D3 — AssetClassMind + pending-review + promotion + web_search (24 tests)
│   ├── test_asset_class_resolution.py # Session 28 Finding #3 — Layer 2.5 config field resolution precedence (5 tests)
│   ├── test_dataroom_pipeline.py    # Session 29 — ingest/refresh exclusions, hash dedup, filepath relink, dedupe_registry (12 tests)
│   ├── test_db_snapshots.py         # Session 31 — snapshot ingest round-trip, extra_data preservation, resolve_snapshot, DB↔tape equivalence, isolation, live-snapshot helper (28 tests)
│   ├── test_integration_snapshots.py # Session 31 — Integration API UPSERT by (snapshot, invoice_number), 409 on tape/prior-day-live, payment inheritance (10 tests)
│   ├── test_exec_summary_stream.py  # Session 32-33 — SSE event contract + analytics_coverage pass-through + parser tests (16 tests)
│   ├── test_exec_summary_prompt.py  # Session 33 — prompt-contract tests locking in the 5 binding rule sections (arithmetic, compute-don't-estimate, section/findings discipline, severity calibration) (20 tests)
├── scripts/
│   ├── seed_db.py          # Legacy CLI (replaced by ingest_tape.py for tape-snapshot ingest)
│   ├── ingest_tape.py      # CLI to create one Snapshot per tape file; extra_data preserves all non-core columns
│   ├── create_api_key.py   # CLI to generate API keys for portfolio companies
│   ├── sync_framework_registry.py  # Auto-generate Section 12 in ANALYSIS_FRAMEWORK.md from metric registry
│   ├── prepare_tamara_data.py  # Data room ETL: reads ~100 source files → structured JSON snapshots for Tamara
│   ├── prepare_aajil_data.py   # Investor deck extraction → structured JSON snapshot for Aajil
│   ├── dataroom_ctl.py         # Unified dataroom operator CLI (audit/ingest/refresh/rebuild-index/wipe/classify)
│   ├── seed_master_mind.py     # Seeds master mind from ANALYSIS_FRAMEWORK.md + CLAUDE.md lessons
│   ├── seed_asset_class_mind.py # Seeds Asset Class Mind with platform-docs entries (D4, idempotent)
│   └── verify_external_intelligence.py # 16-check harness (also ported to tests/test_external_intelligence.py)
├── docs/
│   └── generate_guide.js   # Node.js script to generate Word docs with LAITH branding
└── reports/
    ├── ai_cache/           # Disk cache for AI responses (auto-generated, gitignored)
    └── memos/              # Generated memos (versioned JSON)
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
|`GET /companies/{co}/products/{p}/ai-executive-summary/stream`|SSE streaming variant — emits start/text/tool_call/tool_result/result/done + 20s heartbeats; agent runs in a dedicated thread so sync Anthropic client doesn't block the event loop|
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
|`GET /companies/{co}/products/{p}/tamara-summary`            |Parsed Tamara BNPL JSON (data room ingestion, cached)|
|`POST /companies/{co}/products/{p}/research-report`          |Generate credit research report PDF (any company)|
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
|`GET /companies/{co}/products/{p}/charts/facility-pd`        |Facility-mode PD (Markov chain DPD bucket transitions)             |
|`GET /companies/{co}/products/{p}/charts/methodology-log`    |Data corrections & column availability log|
|`GET /framework`                                             |Analysis Framework markdown document  |

**Portfolio Analytics endpoints (snapshot-scoped DB reads; response includes `data_source='database'` + `snapshot_source`):**
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

**Research Hub endpoints:**
|Endpoint                                                     |Description                        |
|-------------------------------------------------------------|-----------------------------------|
|`POST /companies/{co}/products/{p}/dataroom/ingest`          |Scan & ingest data room directory  |
|`GET /companies/{co}/products/{p}/dataroom/documents`        |List all ingested documents        |
|`GET /companies/{co}/products/{p}/dataroom/stats`            |Data room aggregate stats          |
|`GET /companies/{co}/products/{p}/dataroom/search?q=...`     |Search across all documents        |
|`GET /companies/{co}/products/{p}/dataroom/documents/{id}/view`|Stream original file for browser viewing|
|`POST /companies/{co}/products/{p}/dataroom/snapshot-analytics`|Snapshot current analytics       |
|`POST /companies/{co}/products/{p}/research/query`           |Claude RAG research query          |
|`POST /companies/{co}/products/{p}/research/chat`            |Research chat (for frontend)       |
|`GET /companies/{co}/products/{p}/mind/profile`              |Company mind profile               |
|`POST /companies/{co}/products/{p}/mind/record`              |Record mind entry                  |
|`GET /mind/master/context`                                   |Preview master mind context        |

**Onboarding endpoints:**
|Endpoint                                                     |Description                        |
|-------------------------------------------------------------|-----------------------------------|
|`POST /api/onboarding/validate`                              |Check org name uniqueness          |
|`POST /api/onboarding/organizations`                         |Create org + products + API key    |

**Memo Engine endpoints:**
|Endpoint                                                     |Description                        |
|-------------------------------------------------------------|-----------------------------------|
|`GET /memo-templates`                                        |List all IC memo templates         |
|`POST /companies/{co}/products/{p}/memos/generate`           |Generate full IC memo              |
|`GET /companies/{co}/products/{p}/memos`                     |List memos for company             |
|`GET /companies/{co}/products/{p}/memos/{id}`                |Get memo (latest version)          |
|`PATCH /companies/{co}/products/{p}/memos/{id}/sections/{key}`|Update single section             |
|`POST /companies/{co}/products/{p}/memos/{id}/sections/{key}/regenerate`|Regenerate section      |
|`PATCH /companies/{co}/products/{p}/memos/{id}/status`       |Change status                      |
|`POST /companies/{co}/products/{p}/memos/{id}/export-pdf`    |Export memo as PDF                 |

**Operator Command Center endpoints:** (moved under `/api/operator/` 2026-04-18 to avoid colliding with the SPA route `/operator`)
|Endpoint                                   |Method |Description                              |
|-------------------------------------------|-------|-----------------------------------------|
|`/api/operator/status`                     |GET    |Aggregate health, commands, gaps, activity|
|`/api/operator/todo`                       |GET    |List operator follow-up items            |
|`/api/operator/todo`                       |POST   |Create follow-up item                    |
|`/api/operator/todo/{id}`                  |PATCH  |Update follow-up (toggle complete, edit) |
|`/api/operator/todo/{id}`                  |DELETE |Delete follow-up item                    |
|`/api/operator/mind`                       |GET    |Browse all mind entries (master + company)|
|`/api/operator/mind/{id}`                  |PATCH  |Promote/archive a mind entry             |
|`/api/operator/digest`                     |POST   |Generate weekly digest (Slack or JSON)   |
|`/api/operator/briefing`                   |GET    |Morning briefing (priority actions, thesis alerts, recommendations)|
|`/api/operator/learning`                   |GET    |Corrections, auto-rules, codification candidates|
|`/api/operator/learning/rules`             |GET    |All active learning rules across companies|

**Intelligence System endpoints:**
|Endpoint                                                     |Method |Description                        |
|-------------------------------------------------------------|-------|-----------------------------------|
|`/companies/{co}/products/{p}/thesis`                        |GET    |Load current investment thesis     |
|`/companies/{co}/products/{p}/thesis`                        |POST   |Create or update thesis            |
|`/companies/{co}/products/{p}/thesis/drift`                  |GET    |Check drift against latest metrics |
|`/companies/{co}/products/{p}/thesis/log`                    |GET    |Thesis change history              |
|`/knowledge/search`                                          |GET    |Unified KB search (mind+lessons+decisions+entities)|
|`/companies/{co}/products/{p}/chat-feedback`                 |POST   |Record thumbs up/down on AI chat   |

All tape chart endpoints accept: `snapshot`, `as_of_date`, `currency` query params.
Chat endpoint also accepts `snapshot`, `currency`, `as_of_date` in the POST body (frontend sends them there).
Integration endpoints require `X-API-Key` header (SHA-256 hashed, org-scoped).
-----
## Navigation Architecture
**Hierarchy:** Company → Product → (Tape Analytics | Portfolio Analytics | Legal Analysis)

**Route structure:**
| Route | Component | Description |
|---|---|---|
| `/` | `Home` | Landing page — company grid |
| `/company/:co/:product/tape/:tab` | `TapeAnalytics` | 18-tab dashboard (tab slug in URL) |
| `/company/:co/:product/portfolio/:tab` | `PortfolioAnalytics` | 6-tab portfolio view (live data from DB/tape) |
| `/company/:co/:product/legal/:tab` | `LegalAnalytics` | 8-tab legal document analysis |
| `/company/:co/:product/executive-summary` | `ExecutiveSummary` | AI-powered holistic findings from all metrics |
| `/company/:co/:product/methodology` | `Methodology` | Definitions & formulas reference |
| `/company/:co/:product/research/library` | `DocumentLibrary` | Browse ingested data room documents |
| `/company/:co/:product/research/chat` | `ResearchChat` | AI research queries across documents |
| `/company/:co/:product/research/memos` | `MemoArchive` | Historical investment memos |
| `/company/:co/:product/research/memos/new` | `MemoBuilder` | Create new IC memo (4-step wizard) |
| `/company/:co/:product/research/memos/:memoId` | `MemoEditor` | View/edit/regenerate memo |
| `/company/:co/:product/legal/:tab` | `LegalAnalytics` | Legal analysis 8-tab dashboard |
| `/operator` | `OperatorCenter` | Command Center — health matrix, commands, follow-ups, activity log, mind review |
| `/framework` | `Framework` | Analysis Framework — analytical philosophy with sticky TOC |
| `/onboard` | `Onboarding` | Self-service company onboarding (4-step form) |

**Sidebar navigation:** 240px persistent sidebar on all company pages. Sections: Company name, Products (if multiple), Executive Summary (gold accent, AI-powered), Tape Analytics (18 links), Portfolio Analytics (6 links), Legal Analysis (8 links), Research Hub (Document Library, Research Chat, IC Memos), Methodology. Active state: gold left border + gold text.

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

**Data source (post Session 31):** Portfolio Analytics reads from the snapshot-dimensioned PostgreSQL DB exclusively. Tape uploads populate DB via `scripts/ingest_tape.py` (one Snapshot per tape file, `source='tape'`). Integration API pushes populate a rolling-daily `live-YYYY-MM-DD` snapshot. `core/db_loader.py` produces tape-compatible DataFrames by spreading the `Invoice.extra_data` JSONB back onto DataFrame columns under each tape column's ORIGINAL name — so new tape columns flow through the entire stack automatically. No tape-fallback read path; portfolio endpoints 404 with a hint pointing at `ingest_tape.py` when no snapshot matches.
-----
## Legal Analysis Tabs (8) — AI-Powered Document Analysis
|Tab                |What It Shows                                                |
|-------------------|-------------------------------------------------------------|
|Documents          |PDF upload (drag-drop), document inventory, extraction status badges, re-extract/delete actions|
|Facility Terms     |4 KPI cards (limit, type, maturity, governing law), detail table with all extracted terms|
|Eligibility & Rates|Eligibility criteria table (name, value, section ref, confidence), advance rate schedule cards|
|Covenants & Limits |Two-column comparison: document thresholds vs live portfolio values, breach distance gauge, discrepancy flags|
|Events of Default  |EOD triggers grouped by severity (payment/covenant/cross_default/MAC/operational), cure periods|
|Reporting          |Reporting obligations timeline with frequency badges, normal + default payment waterfall priority|
|Risk Assessment    |AI-generated risk flags (missing provisions, below-market terms), severity badges, recommendations|
|Amendment History  |Document version picker, material changes diff table (old value → new value)|

**Data source:** PDF facility agreements uploaded to `data/{company}/legal/` (company-level, not product-level). AI extraction via Claude (~$1.25/doc, cached forever). Extracted terms auto-populate `facility_params` via 3-tier priority: document → manual override → hardcoded default.

**Legal Analysis endpoints (under `/companies/{co}/products/{p}/legal/`):**
|Endpoint                     |Method|Description                              |
|-----------------------------|------|-----------------------------------------|
|`/upload`                    |POST  |Upload PDF, trigger background extraction|
|`/documents`                 |GET   |List all documents + extraction status   |
|`/documents/{filename}`      |GET   |Document details + full extraction result|
|`/documents/{filename}/re-extract`|POST|Re-run extraction                     |
|`/facility-terms`            |GET   |Extracted facility terms                 |
|`/eligibility`               |GET   |Eligibility criteria + advance rates     |
|`/covenants-extracted`       |GET   |Covenant thresholds + concentration limits|
|`/events-of-default`         |GET   |EOD triggers with severity               |
|`/reporting`                 |GET   |Reporting obligations + waterfall        |
|`/risk-flags`                |GET   |AI risk assessment flags                 |
|`/compliance-comparison`     |GET   |Doc terms vs live portfolio (side-by-side)|
|`/amendment-diff`            |GET   |Compare two document versions            |
-----
## Data Source Architecture
**Three distinct data pipelines feed the platform:**

| | Tape Analytics | Portfolio Analytics | Legal Analysis |
|---|---|---|---|
| **Source** | CSV/Excel files in `data/` | PostgreSQL database (fallback: tape files) | PDF facility agreements in `data/.../legal/` |
| **Ingestion** | Manual upload by analyst | Inbound API from portfolio companies | PDF upload via Legal Analysis tab |
| **Refresh** | Point-in-time snapshots (monthly) | Real-time (as companies push data) | On document upload or amendment |
| **Purpose** | Retrospective analysis, IC reporting | Live monitoring, borrowing base, covenants | Contractual truth, compliance comparison |
| **Backend module** | `core/analysis.py` + `core/loader.py` | `core/portfolio.py` + `core/db_loader.py` | `core/legal_extractor.py` + `core/legal_compliance.py` |

**PostgreSQL is required post-Session-31.** The tape-fallback read path was removed; portfolio endpoints query DB only. `DATABASE_URL` must be set. To bootstrap a fresh environment: apply migrations (`alembic upgrade head`), then populate snapshots from tape files (`python scripts/ingest_tape.py --all`).

**Tape-compatible bridge:** `core/db_loader.py` maps DB rows (Invoice + Payment, filtered by `snapshot_id`) to DataFrames with tape-column names. Every non-core tape column round-trips through `Invoice.extra_data` JSONB using its original tape column name (e.g., `'Expected collection days'`, `'Collection days so far'`, `'Provider'`). `core/portfolio.py` and `core/analysis.py` work identically — zero code changes when new tape columns arrive.

**Integration API authentication:** Portfolio companies authenticate via `X-API-Key` header. Keys are generated with `scripts/create_api_key.py`, SHA-256 hashed, and stored in the `organizations` table. Each API key is scoped to one organization — queries automatically filter to that org's data.

**Database schema (8 tables):**
| Table | Purpose |
|---|---|
| `users` | Platform users with email, name, role (admin/viewer), active status |
| `organizations` | Portfolio companies (Klaim, SILQ) with API key hash |
| `products` | Products per org with analysis_type, currency, facility_limit |
| `snapshots` | Point-in-time views per product (source='tape'/'live'/'manual', taken_at, row_count). Created by `ingest_tape.py` per tape file OR by Integration API on first write each UTC day. Session 31. |
| `invoices` | Receivables pool, tagged with `snapshot_id`. Composite unique `(snapshot_id, invoice_number)` — same invoice can exist in many snapshots. `extra_data` JSONB carries every non-core tape column verbatim. |
| `payments` | Payment activity (ADVANCE/PARTIAL/FINAL), tagged with `snapshot_id` (inherited from parent invoice on write) |
| `bank_statements` | Cash position tracking with optional PDF file storage; nullable `snapshot_id` for batch traceability |
| `facility_configs` | Per-facility lending terms in JSONB (advance_rates, concentration_limits, covenants) — singleton per product, snapshot-independent |

-----
## Research Hub & Memo Engine
The platform includes an AI-powered research and memo generation system built on three layers:

**Data Room Engine** (`core/dataroom/`):
- Ingests any directory of files (PDF, Excel, CSV, JSON, DOCX, ODS)
- Chunks documents for search, builds TF-IDF index
- Classifies documents by type (16 categories)
- Snapshots platform analytics as searchable research sources
- Registry: `data/{co}/{prod}/dataroom/registry.json`

**Research Intelligence** (`core/research/`):
- Claude RAG query engine with source citations
- Rules-based insight extraction at ingest time (metrics, covenants, dates, risk flags)

**IC Memo Engine** (`core/memo/`):
- 4 templates: Credit Memo (12 sections), Due Diligence (9), Monthly Monitoring (6), Quarterly Review (5)
- Analytics Bridge: injects live tape/portfolio metrics into memo sections
- AI section generation with prior section coherence + mind context
- Versioning: draft → review → final (immutable versions)
- PDF export in dark theme matching existing research reports

-----
## Living Mind — Institutional Memory
Two-tier knowledge system that makes every AI output smarter over time.

**Master Mind** (`data/_master_mind/`):
- Fund-level knowledge: analytical preferences, IC norms, cross-company patterns, writing style
- Seeded from ANALYSIS_FRAMEWORK.md principles and existing CLAUDE.md lessons
- Feeds into ALL AI prompts as Layer 2 (between Framework and Methodology)
- **Tracking policy:** `*.jsonl` files are TRACKED in git — shared institutional knowledge, no per-machine UUIDs. Master Mind content converges across all machines via `main`.

**Company Mind** (`data/{co}/mind/`):
- Per-company: corrections, memo edits, research findings, IC feedback, data quality notes
- Auto-populated: legal findings, data quality discoveries, analyst corrections
- Feeds into AI prompts as Layer 4 (most specific context)
- **Tracking policy:** gitignored — holds UUIDs referenced by per-machine `relations.json`, mutates under the event bus on every tape/document ingest. Per-machine by construction.

**4-Layer Prompt Context:**
1. Analysis Framework (codified rules) — always included
2. Master Mind (fund-level lessons) — filtered by task type
3. Company Methodology (codified company rules) — key formulas and caveats
4. Company Mind (position-level notes) — most recent and relevant

**Knowledge Lifecycle:** Company Mind → Master Mind promotion (cross-company pattern) → Framework codification (permanent rule)

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
1. **Define `analysis_type`** in `config.json` — reuse existing type if same asset class, or create new one. Also set `face_value_column` to the tape column that represents originated/funded value (e.g. `"Purchase value"`, `"Principal Amount"`, `"Disbursed_Amount (SAR)"`). This drives the landing page aggregate stats.
2. **Build methodology sections covering all 5 hierarchy levels:**
   - L1 Size & Composition — what constitutes "a deal", volume metrics, product types
   - L2 Cash Conversion — collection rate formula, DSO variant, timing distribution
   - L3 Credit Quality — distress signal (DPD vs denial vs default), PAR method, health thresholds
   - L4 Loss Attribution — loss event definition, recovery path, margin structure, EL parameters
   - L5 Forward Signals — at least one leading indicator, covenant thresholds, stress scenarios
3. **Add cross-cutting sections** — Product Types, Cohort Analysis, Data Caveats, Currency, Data Quality
4. **Add conditional branch** in `Methodology.jsx` — new `{TYPE}_SECTIONS` array with `level` tags, new content component
5. **Verify metrics match backend** — every formula in the methodology must correspond to an actual computation in the analysis module

### Agent Tool Coverage Checklist (required before Executive Summary reads well)
New analysis types don't automatically get coverage in every analytics tool — each tool's dispatch table has to be extended or the tool must gracefully skip. When onboarding a new company, audit `core/agents/tools/analytics.py` (and `compliance.py`) against this checklist:
1. **Register an Aajil-style branch** in `_get_portfolio_summary`, `_get_cohort_analysis`, `_get_concentration`, `_get_collection_velocity`, `_get_deployment`, `_get_ageing_breakdown`, `_get_loss_waterfall`, `_get_covenants` — these are the 8 tools the exec summary agent calls most often. Either dispatch to a company-specific compute function or return a graceful-skip hint (`"X not available for analysis_type={at} — try Y instead"`).
2. **Graceful-skip strings must not start with `Error:` or `Tool error`** — the runtime counts those toward the 3-consecutive-errors circuit breaker (`core/agents/runtime.py:470`). Leading with "X not available for…" is safe.
3. **Audit every `load_tape(...)` call** for the new analysis type — `load_tape` only handles Klaim-shaped tapes. Every other type needs its own loader branch (e.g. `load_aajil_tape`) or an explicit early-return guard.
4. **Check `config.json` section_guidance_map** in both `core/agents/internal.py:generate_agent_executive_summary` AND `backend/main.py` (stream endpoint) — add a per-company sections list matching the L1-L5 hierarchy. Missing entries fall back to the generic default, which drifts from company-specific priorities.
5. **Add regression tests** in `tests/test_agent_tools.py` — one handler test per tool pinning the graceful-skip contract (no crash, no `Error:` prefix, hints at a working alternative). See `TestAajilHandlerSignatures` for the pattern.
6. **Accept that some metrics genuinely don't apply** — DSO isn't meaningful for installment lending; PAR needs contractual due dates the tape may not have; covenants require a facility document. Tools for these return graceful skips; the Executive Summary agent then populates `analytics_coverage` (rendered as a callout between Bottom Line and Key Findings) instead of filing findings about missing tools.

The Executive Summary prompt (in `core/agents/prompts.py`) encodes this behavior: findings are credit observations only; tool gaps go to `analytics_coverage`. New companies automatically benefit — no prompt changes needed when onboarding, just tool coverage.
-----
## Key Architectural Decisions
- **Framework §17 Population Discipline (session 34)** — every compute function output dict carries `confidence: 'A' | 'B' | 'C'` + `population: <code>` per Framework §17. Covenant + concentration-limit dicts MUST carry these fields (audit guard enforced via `tests/test_population_discipline_guard.py`). Dual views required when the same metric serves two analytical questions (e.g., Active + Lifetime PAR, blended + clean cohort rate, Operational + Realized WAL). Session-34 primitives: `separate_{klaim,silq,aajil}_portfolio()`, `classify_{klaim,silq,aajil}_deal_stale()`, `compute_{klaim,silq,aajil}_operational_wal()` consistent across all three live-tape asset classes. UI disclosure via `frontend/src/components/ConfidenceBadge.jsx` (A/B/C letter pill with hover tooltip disclosing population + method + proxy column). AI integration via `MasterMind.load_framework_context()` appending §17 guidance into Layer 1 of `build_mind_context` — every memo / exec summary / chat / thesis prompt gets it automatically. See `core/ANALYSIS_FRAMEWORK.md` §17 + `reports/metric_population_audit_2026-04-22.md` + `reports/blended_field_deprecation_plan_2026-04-24.md`.
- **`core/analysis.py`** — all pure data computation. No FastAPI, no I/O.
- **`core/config.py`** — per-product `config.json` stores currency and description.
- **Snapshot naming** — files must start with `YYYY-MM-DD_` for date parsing.
- **`filter_by_date()`** — filters deals to `Deal date <= as_of_date`. **Always returns a copy** — never mutates the input DataFrame. **Important:** Only filters deal selection by origination date — does NOT adjust balance columns (collected, denied, outstanding). These always reflect the tape snapshot date. See ANALYSIS_FRAMEWORK.md Section 15.
- **`_load()` in main.py** — matches snapshots by `filename` or `date` field (fixed Feb 2026).
- **AICommentary caching** — two layers: (1) In-memory via `CompanyContext` state, survives tab switches within a session, clears on snapshot change. (2) Disk cache in `reports/ai_cache/` — persists across sessions and users (see below).
- **AI response disk cache** — All AI endpoints (executive summary, commentary, tab insights) cache responses to `reports/ai_cache/` as JSON files. Cache key: `(endpoint, company, product, snapshot_filename, currency, file_mtime)` — currency included because AI commentary embeds currency-specific amounts; file mtime included to auto-invalidate when a same-name file is replaced. `as_of_date` normalized (None/snapshot_date/future all map to same key). `?refresh=true` query param forces regeneration.
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
- **Sidebar navigation architecture** — Company pages use a persistent 240px sidebar (`Sidebar.jsx`) within `CompanyLayout`. On mobile, sidebar becomes a slide-in drawer (fixed position, `translateX` animation) with dark backdrop overlay, coordinated via `MobileMenuContext`. Hamburger button in Navbar toggles the drawer. Auto-closes on route change, locks body scroll when open. Tabs are `<Link>` elements (not buttons). Active state: gold left border + text.
- **Mobile responsiveness architecture** — All styling uses inline `style={{}}` objects (no Tailwind classes). Responsive behavior uses a `useBreakpoint()` hook (`frontend/src/hooks/useBreakpoint.js`) returning `{ isMobile, isTablet, isDesktop }` via `matchMedia` listeners. For grid columns, CSS `auto-fill`/`auto-fit` with `minmax()` is preferred over JS breakpoints — intrinsically responsive. Breakpoints: mobile < 768px, tablet 768-1023px, desktop >= 1024px. `--navbar-height` CSS variable responds to viewport. **Important:** Any flex container that switches between sidebar (desktop) and stacked (mobile) layout MUST include `flexDirection: isMobile ? 'column' : 'row'` — the default `row` breaks mobile.
- **URL-based tab navigation** — Active tab stored in URL `:tab` param, not React state. Enables bookmarking/sharing. `TapeAnalytics` reads `useParams().tab`, maps slug to label via `SLUG_TO_LABEL`.
- **CompanyContext** — Central state provider extracted from old `Company.jsx`. Both `TapeAnalytics` and `PortfolioAnalytics` consume via `useCompany()` hook. Prevents re-fetches when switching between tape and portfolio views.
- **CompanyLayout** — Wraps `CompanyProvider` around `Sidebar` + `<Outlet>`. Simple flex layout: sidebar (240px fixed) + main content area (flex: 1).
- **Portfolio Analytics data source — snapshot-dimensioned DB (Session 31)** — All 6 portfolio tabs read from the DB. `_portfolio_load()` in `main.py` is DB-only; it resolves the `snapshot` query param to a Snapshot row via `resolve_snapshot()` and loads invoices + payments filtered by `snapshot_id`. No tape-fallback. 404s on unknown snapshot with a hint pointing at `scripts/ingest_tape.py`. Tape files populate DB via `ingest_tape.py` (one Snapshot per tape); Integration API pushes populate a rolling-daily `live-YYYY-MM-DD` snapshot. `sel['date'] = snap.taken_at` (real date, not `datetime.now()` — the old bug).
- **As-of-date auto-resolves to matching snapshot** — When the caller passes an `as_of_date` that matches a real snapshot's `taken_at`, `_portfolio_load` prefers that snapshot over the one named in the `snapshot` query param. This lets the existing Portfolio `<select>` (a date picker, not a snapshot picker) act as a snapshot selector without a frontend rewrite. If no snapshot matches the date, falls back to the named snapshot + date filter.
- **Same-day tape + live collision** — If a tape is uploaded AND a live snapshot exists for the same `taken_at`, `resolve_snapshot` orders by `ingested_at DESC` and returns the most-recently-ingested. Rule of thumb: the LAST write wins. Analysts should be aware when picking a snapshot on a day both sources exist — use the explicit snapshot dropdown in Tape Analytics for unambiguous selection.
- **`Invoice.extra_data` JSONB round-trip** — Every non-core tape column (everything except `invoice_number`, `amount_due`, `status`, `customer_name`, `payer_name`, `invoice_date`, `due_date`) is stored in `extra_data` KEYED BY THE ORIGINAL TAPE COLUMN NAME. `db_loader.load_klaim_from_db` / `load_silq_from_db` spread every key back onto the DataFrame under that same name. A new analytical column in a tape (e.g., Apr 15's `Expected collection days`, `Collection days so far`, `Provider`) flows through the entire stack automatically — no schema migration, no loader-mapping change. Reserve the relational schema for INDEX/JOIN columns only.
- **Tape-compatible DataFrame bridge** — `core/db_loader.py` maps Invoice+Payment DB records to DataFrames with identical column names as CSV tapes. `load_klaim_from_db()` and `load_silq_from_db()` handle company-specific core columns; `extra_data` handles the rest. Zero changes needed to analysis functions when tape schema evolves.
- **Rolling-daily live snapshot (Integration API write path, Session 31)** — `get_or_create_live_snapshot(db, product)` creates `live-YYYY-MM-DD` on first Integration API write of each UTC day. Subsequent same-day writes UPSERT by `(snapshot_id, invoice_number)` into that snapshot. Next day's first write creates a new snapshot; prior day becomes frozen history. `is_snapshot_mutable(snapshot, today)` — True only for today's live snapshot. PATCH/DELETE on tape or prior-day-live returns 409. Concurrent first-push race is resolved by the unique `(product_id, name)` constraint (loser reads winner's row).
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
- **Summary field name convention** — The frontend expects canonical field names from `/summary`: `total_purchase_value`, `total_deals`, `collection_rate`, etc. Company-specific analysis functions may use domain terms (e.g. SILQ's `total_disbursed`). The summary must return BOTH the domain-specific name AND the canonical alias (e.g. `'total_purchase_value': _safe(total_disbursed)`). This ensures landing page cards and aggregate stats work uniformly across all companies. **Label override pattern:** Tamara's `total_purchase_value` is outstanding AR (not originated), so it returns `face_value_label: "Outstanding AR"` and `deals_label: "Reports"`. The frontend reads these optional fields and overrides the default card labels. Companies that don't return these fields get the defaults ("Face Value", "Deals"). Tamara is excluded from the aggregate "Face Value Analyzed" banner to avoid mixing outstanding with originated.
- **Living Methodology architecture** — Methodology page content is stored as structured Python dicts in companion files (`core/methodology_klaim.py`, `core/methodology_silq.py`) rather than hardcoded JSX. Backend serves via `GET /methodology/{analysis_type}`. Frontend renders dynamically using existing Metric/Table/Note/Section components. Companion files (not inline decorators) chosen because methodology metadata is large (multi-line strings, nested structures) — keeping `analysis.py` as pure computation. Ejari uses static JSON file at `data/Ejari/RNPL/methodology.json`. New companies: create `methodology_{type}.py`, register at startup → page works automatically.
- **Ejari read-only summary pattern** — When `analysis_type` is `"ejari_summary"`, the platform bypasses all tape loading and computation. TapeAnalytics renders `EjariDashboard.jsx` which reads the URL `:tab` param and renders only the matching section. The `parse_ejari_workbook()` function in `core/analysis_ejari.py` reads the ODS file once (cached per session), extracting 12 structured sections. Config uses `hide_portfolio_tabs: true` to suppress Portfolio Analytics in sidebar, and sidebar header shows "Analysis" instead of "Tape Analytics". EjariDashboard uses shared `KpiCard` and `ChartPanel` components (same as Klaim/SILQ) for visual consistency. Only `DataTable` remains Ejari-specific (renders ODS tabular data). This pattern can be reused for any future company that provides pre-computed analysis instead of raw tapes.
- **Tamara data room ingestion pattern** — When `analysis_type` is `"tamara_summary"`, the platform loads a pre-processed JSON snapshot instead of a tape or ODS workbook. The JSON is produced by `scripts/prepare_tamara_data.py` which reads ~100 source files from the data room (vintage cohort Excel matrices, Deloitte FDD loan portfolio, HSBC investor report PDFs via pdfplumber, financial models, portfolio demographics). The ETL runs once offline; the runtime parser (`core/analysis_tamara.py`) loads JSON, enriches with presentation fields (covenant status colors, heatmap color scales, derived KPIs), and serves via a single cached endpoint. This is the **third data ingestion pattern** alongside raw tapes and pre-computed summaries. `loader.py` extended to recognize `.json` files in `get_snapshots()`.
- **Credit Research Report platform capability** — `core/research_report.py` generates comprehensive dark-themed PDF credit research reports for ANY company, not just Tamara. Uses ReportLab Platypus with Laith branding (navy background, gold headers, styled tables). Backend endpoint `POST /research-report` dispatches to company-specific builders based on `analysis_type`. Tamara builder produces 8 sections (exec summary, company overview, portfolio analytics, vintage performance, covenants, facility structure, DPD analysis, data sources). Accepts optional `ai_narrative` parameter for Claude-powered narrative sections. Generic fallback builder handles companies without a dedicated builder.
- **ODS and JSON file support** — `core/loader.py` `get_snapshots()` now accepts `.ods` and `.json` files alongside `.csv` and `.xlsx`. ODS requires `odfpy` package. **Important:** `config.json` and `methodology.json` are excluded via `_EXCLUDE` set to prevent non-data files from appearing as snapshots.
- **Overview page standardization** — All company overviews follow a consistent section structure guided by the L1-L5 analytical hierarchy: (1) Main KPIs (L1/L2, 5-col grid, bespoke per company), (2) "Credit Quality" section (L3, PAR 30+/60+/90+ as individual cards), (3) "Leading Indicators" section (L5, DTFC etc when available). PAR cards always use `{ccy} {amount}K at risk` subtitle format. Fixed 5-column grids prevent async reflow. Bespoke KPIs encouraged within each section.
- **Executive Summary always visible** — Sidebar shows Executive Summary for all companies including Ejari. Decoupled from `hide_portfolio_tabs` flag which only controls Portfolio Analytics tabs.
- **Executive Summary dual-output architecture** — Single AI call returns JSON object with `narrative` (sections array + summary_table + bottom_line) and `findings` (array, same as before). Company-specific section guidance injected into prompt. Response parsing handles both old format (array) and new format (object) for backward compat. `max_tokens=8000` for the combined output. Generation takes ~50-60s vs ~10s previously.
- **Legal Analysis — third analytical pillar** — AI-powered facility agreement analysis alongside Tape Analytics and Portfolio Analytics. PDF upload → 5-pass Claude extraction → structured JSON (eligibility, advance rates, covenants, concentration limits, EOD, reporting, waterfall) → cached to `data/{co}/{prod}/legal/`. 8 frontend tabs in sidebar between Portfolio Analytics and Methodology. Hidden when `hide_portfolio_tabs: true` (same as Portfolio — legal analysis requires portfolio context).
- **Legal extraction engine** — `core/legal_extractor.py` runs 5 passes: (1) definitions & structure, (2) facility + eligibility + advance rates, (3) covenants + concentration limits, (4) EOD + reporting + waterfall, (5) AI risk assessment. Each pass prepends the definitions glossary and targets specific sections. ~$1.25/document, cached forever. Sonnet for passes 1-4, Opus for risk assessment.
- **3-tier facility params priority** — `_load_facility_params()` in `main.py` merges: (1) document-extracted values from `legal/` (baseline), (2) manual overrides from `facility_params.json` (precedence), (3) hardcoded defaults in compute functions (fallback). `_sources` dict tracks provenance per field. FacilityParamsPanel shows `Source: Document` vs `Source: Manual` badges.
- **Legal compliance comparison** — `core/legal_compliance.py` `build_compliance_comparison()` matches extracted covenant thresholds against live portfolio values from `compute_klaim_covenants()`. Returns breach distance (% headroom), discrepancy flags (document vs hardcoded default), and overall compliance summary. Fed into executive summary AI context.
- **PDF parsing pipeline** — `core/legal_parser.py` uses PyMuPDF (`pymupdf4llm`) for markdown conversion preserving headers/structure, plus `pdfplumber` for table extraction (advance rate schedules, concentration tier tables). Semantic chunking by article/section headers (legal docs are well-structured). Definitions section isolated first as context for all subsequent extraction passes.
- **Legal extraction schema** — `core/LEGAL_EXTRACTION_SCHEMA.md` defines extraction taxonomy (7 sections), Pydantic models in `core/legal_schemas.py`, confidence grading (HIGH >= 0.85, MED >= 0.70, LOW < 0.70), and facility_params mapping table (12 fields). Companion to ANALYSIS_FRAMEWORK.md Section 16.
- **Living Mind 4-layer architecture** — Framework (codified rules) → Master Mind (fund lessons) → Methodology (company rules) → Company Mind (position notes). Every AI prompt sees all 4 layers. Knowledge flows upward: fast corrections → consolidation → codification.
- **Research engine** — Claude RAG queries across all ingested documents with source citations. **Important:** `ClaudeQueryEngine._get_client()` uses `load_dotenv(override=True)` to ensure `.env` values override empty env vars inherited from parent shell — without `override`, an empty `ANTHROPIC_API_KEY` in the shell silently disables Claude synthesis.
- **Analytics-as-source** — Platform-computed analytics (tape summaries, PAR, DSO) snapshotted into the data room as searchable documents. Memos can cite "Tape Analytics — PAR Analysis, Mar 2026" alongside "HSBC Investor Report, Jan 2026".
- **Memo feedback loop** — Analyst edits to AI-generated memo sections are recorded in Company Mind. Future memos benefit from accumulated style preferences and corrections.
- **Legal extraction caching** — Extract once per PDF, cache forever. 5-pass Claude pipeline (~$1.25/doc). 3-tier merge: document > manual > hardcoded.
- **Multi-document extraction merge** — `load_latest_extraction()` merges all `*_extracted.json` files in the legal directory. Lists (covenants, EODs, reporting) concatenated and deduped by name. Dicts (facility_terms) merged with primary credit_agreement winning on conflict. Tracks `source_documents` array for provenance.
- **Consecutive breach EoD tracking** — `annotate_covenant_eod()` in `core/portfolio.py` (pure function) + `covenant_history.json` (I/O in `main.py`). Per MMA 18.3: `single_breach_not_eod` (PAR30), `single_breach_is_eod` (PAR60, Parent Cash), `two_consecutive_breaches` (Collection Ratio, Paid vs Due). History persists max 24 periods, dedupes by date.
- **Payment schedule as static data** — Stored in `data/{co}/legal/payment_schedule.json` (not extracted by AI). Backend reporting endpoint loads and serves it alongside extracted reporting requirements. Frontend renders with PAID/NEXT badges relative to today's date.
- **Registry format** — Both DataRoomEngine and AnalyticsSnapshotEngine use dict[str, dict] registry format (keyed by doc_id). Auto-migrates old list format on read. Filepaths normalized to forward slashes via `_normalize_filepath()` for cross-platform compatibility (Windows ingestion → Linux production). View endpoint resolves relative paths against project root.
- **Intelligence System — Knowledge Graph architecture** — KnowledgeNode extends MindEntry via composition (not inheritance). New fields stored in `metadata["_graph"]` subkey for backward-compatible JSONL storage. Lazy upgrade on read via `upgrade_entry()` — no batch migration needed. RelationIndex is a separate JSON file (`relations.json`) per scope — bidirectional adjacency list. Event bus is synchronous, in-process, with `disable()` for test isolation.
- **Intelligence System — Incremental compilation** — Entity extraction (regex-based, 7 types) feeds into a KnowledgeCompiler that creates/supersedes/reinforces/contradicts existing nodes. One document → 10-15 knowledge updates. Compilation reports logged to `compilation_log.jsonl`. Entities stored in dedicated `entities.jsonl` per company.
- **Intelligence System — Closed-loop learning** — Every analyst correction auto-classified (tone_shift, threshold_override, data_caveat, etc.) and auto-generates learning rules as KnowledgeNodes (node_type="rule"). Patterns extracted when same correction type appears 3+ times → codification candidates. Rules have `last_triggered` and `trigger_count` metadata for decay tracking.
- **Intelligence System — Thesis tracker** — Per-company investment thesis with measurable pillars linked to computed metrics (e.g., "collection_rate" > 0.85). Auto-drift detection on tape ingestion: holding → weakening (within 10% of threshold) → broken (breached). Conviction score (0-100) aggregated from pillar scores. Thesis injected as Layer 5 in AI prompts.
- **Intelligence System — 5-layer AI context** — Framework (L1) → Master Mind (L2) → Methodology (L3) → Company Mind (L4) → Thesis (L5, new). Layer 5 includes active pillars with statuses and drift alerts, making every AI output thesis-aware.
- **Cloudflare Access JWT auth** — Platform authentication delegated to Cloudflare Access (team: `amwalcp`). Backend reads `CF_Authorization` cookie or `Cf-Access-Jwt-Assertion` header, verifies RS256 JWT against public keys from `amwalcp.cloudflareaccess.com/cdn-cgi/access/certs` (cached 1hr). User table maps email → role (admin/viewer). Auto-provisions users on first login. `ADMIN_EMAIL` env var bootstraps first admin. Auth middleware skips `/auth/*`, `/api/integration/*`, OPTIONS. When `CF_TEAM` not set (local dev), middleware passes all requests through — zero friction for development. Existing X-API-Key integration auth completely untouched.
- **docker-compose env var precedence** — `environment` section overrides `env_file` values. Auth vars (`CF_TEAM`, `CF_APP_AUD`, `ADMIN_EMAIL`) must only be in `.env.production` via `env_file`, NOT in the `environment` section (which reads from host shell and gets empty strings).
- **Production data sync pipeline** — Raw dataroom files (PDFs, xlsx, docx) are not in git. `scripts/sync-data.ps1` pushes them from laptop to server via scp (excludes chunks/analytics/index.pkl). `deploy.sh` auto-ingests any dataroom with registry.json but no chunks/ directory, calling `DataRoomEngine.ingest()` directly via Python import (bypasses HTTP auth). Deploy also auto-detects backend/core code changes and forces `--no-cache` rebuild. Data volume is read-write (`./data:/app/data`) to allow chunk creation. `/health` endpoint added for unauthenticated health checks.
- **Operator Command Center** — `/api/operator/status` reads from existing files only (config.json, registry.json, mind/*.jsonl, legal/*_extracted.json, reports/ai_cache/). No new data infrastructure. Gap detection uses heuristic rules. Personal follow-ups stored in `tasks/operator_todo.json` (separate from Claude's `tasks/todo.md`). Backend router at `/api/operator/*` (moved 2026-04-18 from `/operator/*` to avoid collision with the SPA route). Frontend at `/operator` with 8 tabs: Health Matrix, Commands, Follow-ups, Activity Log, Mind Review, Briefing, Learning, Data Rooms. `/ops` slash command provides terminal briefing.
- **Activity logging** — `core/activity_log.py` appends to `reports/activity_log.jsonl`. Imported by 14 endpoints (AI, reports, legal, data room, memos, mind, alerts). Log_activity() calls placed before return statements. Only logs fresh operations (not cache hits for AI endpoints).
- **Weekend Deep Work protocol** — `WEEKEND_DEEP_WORK.md` defines 7 analytical modes for long Claude Code sessions. State-save via `reports/deep-work/progress.json`. Two-pass file analysis (core engines before UI). Self-audit validation pass. Tiered frequency schedule (weekly Red Team → quarterly Full Combo).
- **Memo pipeline BaseException discipline** — `_generate_parallel` in `core/memo/generator.py` catches `BaseException` (not just `Exception`) around `fut.result()` so `GeneratorExit`/`SystemExit` from SSE client disconnect can't tear down the `as_completed` loop. Null-slot backfill synthesizes error placeholders so template order is preserved. Downstream stages (citation audit, polish) now run whenever `any(s.get("content") for s in sections)` rather than being blocked by ANY earlier error — prevents single-section failures from silently truncating the memo.
- **SSE agent endpoints MUST offload to a thread** — Session 32. `GET /ai-executive-summary/stream` (backend/main.py) runs the analyst agent in a dedicated `threading.Thread` with its own asyncio event loop, pushing `StreamEvent`s to the main loop's `asyncio.Queue` via `loop.call_soon_threadsafe`. This is non-negotiable: `AgentRunner.stream()` is async-declared but internally calls the SYNC `anthropic.Anthropic` client's `messages.stream()`, which blocks its OS thread for the duration of each Claude HTTP call. Awaiting that async generator inline in an `asyncio.create_task` freezes uvicorn's single worker entirely — heartbeats can't fire, the queue-drain consumer can't run, and `/health` on the same instance stops responding. Symptom during Aajil browser test: stage stuck at "Starting…" for 83s while backend log showed tool calls actually executing. See `tasks/lessons.md` 2026-04-22 entry "Sync client in an async SSE endpoint freezes the whole event loop". `backend/agents.py::_stream_agent` still uses the broken inline pattern — works in the short-call common case but has the same latent bug; refactor when touched.
- **All backend API routes under `/api/*`** — `/api/integration/*`, `/api/operator/*`, `/api/onboarding/*`. Bare prefixes like `/operator` collided with the SPA's React Router route of the same name (reverse proxy prefix-matched to backend, 404'd on direct URL / browser refresh). Rule: any new `APIRouter(prefix=...)` or bare `@app.get(...)` must start with `/api/` unless justified. Auth middleware's `_SKIP_PREFIXES` is a documented exception list.
- **`core.ai_client` strips `temperature` kwarg for Opus-routed tiers** — `_STRIPS_TEMPERATURE_TIERS = {"polish", "judgment"}` in `complete()`. Opus 4.7 deprecated `temperature`; rather than hunt call sites across backend/core on every future deprecation, the tier router quietly drops the kwarg for tiers whose models reject it. Callers can keep passing it; Sonnet-routed tiers (structured/research/auto) preserve it.
- **Bidirectional orphan sweep in dataroom pipeline** — `DataRoomEngine.prune()` deletes chunk files whose doc_id isn't in registry. Complements the existing registry-orphan eviction (registry entries whose chunks file is missing). Both directions are now checked on every `ingest()` and `refresh()`. Because `doc_id = uuid4()`, forced re-ingests leave old chunk files behind — sha256 dedup keeps registry clean but filesystem leaks without prune.
- **Dataroom within-pass hash dedup + auto-heal (session 29, 2026-04-20)** — Four layered fixes in `core/dataroom/engine.py`:
  1. `_EXCLUDE_FILENAMES` expanded from 4 to 10 entries (`meta.json`, `ingest_log.jsonl`, `covenant_history.json`, `facility_params.json`, `debtor_validation.json`, `payment_schedule.json`) + dotfile rejection in `_is_supported`. Kills self-pollution where engine-written state (`.classification_cache.json`, `meta.json`) was being ingested AS data.
  2. `ingest()` now updates `existing_hashes` after every successful ingest. `refresh()` gained a parallel `registry_hashes` dict updated the same way. Two files with identical bytes at different folder paths get deduped within one pass instead of both becoming registry entries with different doc_ids.
  3. `refresh()` relink-instead-of-skip: when a disk file's hash matches an existing entry but the entry's registered filepath is no longer on disk, **update the entry's filepath to the disk path** rather than dedup-skipping. Otherwise the end-of-function removal sweep drops the entry AND the disk file stays unreferenced — silent data loss (bit 55 Klaim docs after a nested-dir cleanup). New `relinked` counter in result payload distinguishes this from genuine duplicate-skips.
  4. `dedupe_registry()` method — idempotent healing pass: groups surviving entries by sha256 (keeps earliest `ingested_at`, drops the rest + their chunk files) and evicts entries whose filename is now on the exclusion list. Auto-called at the top of `ingest()` and `refresh()` so state converges on every run without manual intervention. Also exposed as `dataroom_ctl dedupe [--company X]`.
  - Frontend companion: `frontend/src/pages/research/DocumentLibrary.jsx` `CATEGORY_CONFIG` extended from 9 to 28 entries covering every backend `DocumentType` enum. Was rendering "Other (N) Other (N) Other (N)" chips keyed by raw enum values but labelled identically via fallback; now each type gets its real label.
  - 12 regression tests in `tests/test_dataroom_pipeline.py` pin each class of bug. 473 tests total.
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
- ✅ **Session 30 continuation — 5 follow-up tasks + deploy + Mind sync (2026-04-22):**
  - **5 spawned tasks merged end-to-end:** CovenantCard Path B display fix (`dae0d02`), curve-based close-age fallback for `_klaim_wal_total` (`2abf3b9`), Macaulay cash-flow-weighted duration metric (`80fd0a1`), Operational WAL + Stale Exposure tape-vs-portfolio split (`b527ed2` + `6cf5978`), and snapshot-filename silent-fallback kill (`6867c85`). Plus a task-#2 test-catchup commit (`5aa246f`) for a cross-file `wal_total_method` assertion in `test_db_snapshots.py` that needed accepting the new `collection_days_so_far_with_curve_fallback` tag.
  - **CovenantCard fix** — Apr 15 WAL card no longer shows nonsensical "Breach projected: 9 Feb 2025 / -436d" + "✓ -78 days headroom" lines when compliant via Path B carve-out. Implementer chose Option A: suppress Path A projection/headroom, replace with muted "Compliant via carve-out (Extended Age 4.4% ≤ 5%)" note. Pixel-identical rendering for every other covenant (single-path covenants unchanged).
  - **Curve-based close-age fallback** — new Tier 2 proxy walks the `Actual in X days` curve columns (30, 60, …, 390) and uses the last 30-day bucket with positive cash delta as close-age when primary `Collection days so far` is missing/negative. Method tag upgrades to `collection_days_so_far_with_curve_fallback` when curves fill gaps. 58 corrupted-primary rows on Apr 15 Klaim now resolve to observed close-age (vs contractual fallback before). WAL Total drifts from 137 → 137.56d; Active WAL + Path B unchanged.
  - **Macaulay cash-flow-weighted duration** — new `compute_klaim_cash_duration` in `core/analysis.py` + `GET /charts/cash-duration` endpoint. PV-weighted Macaulay duration across curve columns answers "if a dollar is deployed, how quickly does it come back" — distinct from WAL which just measures time on book. Methodology entry at L2, fractional-order 3.5 insertion (no renumbering). Display surface deferred per task spec.
  - **Operational WAL + Stale Exposure — Tape vs Portfolio split.** Tape-side of the Klaim dashboard now reports **Operational WAL 79d / Realized WAL 65d** on a clean book (zombies stripped) alongside a **Stale Exposure 16.5% / 926 deals** panel with category breakdown + top-25 offender drill-down (the 1,184-day VALIANT deal from 2023-01-17 is #1 by PV). Portfolio-side covenant WAL card **renders byte-identical** to pre-change (148d Active / 137d Total / Path B carve-out). Zombie classification uses 3 rules: loss_completed (denial > 50% PV), stuck_active (age > 91d + outstanding < 10% PV), denial_dominant_active. Mar 3 tape degrades gracefully (`confidence=C, method=elapsed_only, realized_wal_days=null`). Implements the framework candidate recorded in `data/_master_mind/framework_evolution.jsonl` today: "Tape vs Portfolio metric duality — Tape strips stale, Portfolio reports covenant-bound".
  - **Snapshot-filename silent-fallback kill.** Pre-fix: `/snapshots` returned DB-backed names WITHOUT `.csv`, `_load()` matched filesystem names WITH `.csv`, UI snapshot switcher silently fell back to latest when it couldn't match — analysts were looking at the wrong snapshot's data and didn't know it. Fix: new `_match_snapshot()` helper with 4-tier resolution (exact → extension-stripped → single-date → HTTP 400 with "Available: …" list). Both `_load()` and `_resolve_snapshot()` delegate. End-to-end proof on Klaim `/summary`: before fix Sept 23 / Dec 8 / Mar 3 all silently returned 7,697 deals; after fix 6,290 / 4,988 / 7,697 — distinct data per snapshot.
  - **EoD skill upgraded** (`e15d8aa`) — Step 2 gains a mandatory warning-drift check. Pytest warning count baseline documented at **158** (session 30 end). Future EoDs compare against this number; jumps > 10 flag the top 3 categories. Known background noise (12× `datetime.utcnow()` + 1× Pydantic `class Config`) explicitly listed so new deprecations don't hide inside existing noise. Deprecation cleanup task chipped for next session — will drop the baseline to ~15 once run.
  - **Mind institutional knowledge synced to production.** 7 JSONL entries from today's zombie-cohort + PAR-vs-Stale duality analysis live on prod: 4 Company Mind (Klaim `findings.jsonl`), 2 Asset Class Mind (`healthcare_receivables.jsonl` — diagnostic pattern + reporting doctrine), 1 Framework codification candidate (`_master_mind/framework_evolution.jsonl` — Tape vs Portfolio duality). Site live at https://laithanalytics.ai with deploy backend rebuilt, frontend rebuilt, alembic migrations clean, all dataroom registries aligned.
  - **Tests:** 630 passing, 158 warnings (unchanged across all 5 task merges — no new deprecations introduced by today's work).
  - **Two new lessons** in `tasks/lessons.md`:
    1. Semantic upgrades to compute-function outputs need cross-file test grep, not just in-module (task #2 test-catchup caught at merge time, one-line fix).
    2. `git` 3-way merge collapses identical prologues across parallel additions (tasks #3 + #4 both added endpoints with identical `df, sel = _load(...)` prologues — resolution: N independent complete functions, never one blended function).
  - **Surfaced during deploy, not fixed:** prod host missing `libxfixes3` (Playwright PDF-report dep). One-line `apt-get install -y libxfixes3` on server when convenient. Non-blocking.
- ✅ **Session 34 — Framework §17 Population Discipline codified + full platform implementation (2026-04-22 audit, 2026-04-24 implementation + follow-up sweep):**
  - **Audit output** (`reports/metric_population_audit_2026-04-22.md`, 732 lines): 52 compute_* functions across Klaim + SILQ + Aajil + Tamara + Ejari classified by numerator / denominator / population (7 §17 codes) / confidence (A/B/C) / dual-view availability / gap flag. 6 P0, 8 P1, 5 P2, 3 UNCERTAIN.
  - **Initial sweep** (12 commits `a4d0d34..03192d0`): all 6 P0s + 8 P1s + 5 P2s + 3 UNCERTAIN resolutions + §17 Framework codification + methodology updates + Mind entry codified. 627 passing (baseline 548 + 79 new).
  - **Follow-up sweep** (10 commits `7549312..current`): SILQ `classify_silq_deal_stale` + `compute_silq_operational_wal`; platform-wide HHI clean duals (Klaim + SILQ); audit-guard meta-test; `compute_silq_methodology_log` + `compute_aajil_methodology_log` (Klaim already extended); Aajil methodology page (`core/methodology_aajil.py` 15 sections, wired via `backend/main.py register_aajil_methodology()`); memo engine §17 prompt disciplines + `analytics_bridge` confidence/population transmission; MasterMind Layer 1 §17 guidance injection (reaches every AI call); ConfidenceBadge + PopulationPill UI primitives; CovenantCard + LimitCard wiring. 678 passing across both sweeps.
  - **Framework codification:** new §17 "Population Discipline & the Tape-vs-Portfolio Duality" in `core/ANALYSIS_FRAMEWORK.md` (after §16). Renumbered 17→18, 18→19, 19→20, 20→21, 21→22. 7 standard populations (`total_originated`, `active_outstanding`, `active_pv`, `completed_only`, `clean_book`, `loss_subset`, `zombie_subset`). Confidence grading mandatory on every covenant + limit dict. `method_to_confidence()` helper in `core/analysis.py`.
  - **Platform primitives now consistent across all asset classes:**
    - Klaim: `separate_portfolio` + `classify_klaim_deal_stale` + `compute_klaim_operational_wal` + `compute_methodology_log` (extended with §17 entries)
    - SILQ: `separate_silq_portfolio` + `classify_silq_deal_stale` + `compute_silq_operational_wal` + `compute_silq_methodology_log` (all NEW this session)
    - Aajil: `separate_aajil_portfolio` + `classify_aajil_deal_stale` + `compute_aajil_operational_wal` + `compute_aajil_methodology_log` (all NEW this session)
  - **UI disclosure:** `ConfidenceBadge` component (A/B/C letter pill, hover tooltip with population + method + note). Wired into `KpiCard`, `CovenantCard`, `LimitCard`. Population codes translated to human-readable labels in tooltip. Klaim Single Payer limit reveals `proxy_column: 'Group'` when Payer column absent (B grade); WAL covenant shows both `Active A` + `Total B` sub-grades in tooltip.
  - **AI integration:** MasterMind.`load_framework_context()` now always appends §17 guidance after FRAMEWORK_INDEX Core Principles — 25-line block naming all 7 populations + ABC rules + dual-view doctrine. Every AI call (memo, exec summary, chat, thesis drift, research RAG, operator briefing) gets §17 through Layer 1 automatically. Memo section prompt + exec summary prompt carry task-specific §17 elaboration. `analytics_bridge.format_as_memo_block` appends `[Confidence X, pop=Y]` tags on metrics that carry the fields.
  - **Audit guard meta-test:** `tests/test_population_discipline_guard.py` — walks every covenant + concentration-limit dict from 4 compute functions and asserts §17 contract (confidence ∈ {A,B,C}, population matches 10-token taxonomy). Also pins the method→confidence mapping and the taxonomy prefix set as frozen contracts. 9 tests.
  - **Deprecation plan:** `reports/blended_field_deprecation_plan_2026-04-24.md` tracks which blended-view fields are candidates for removal (with 3-memo promotion rule). Covers Aajil yield blended / overall_rate / hhi_customer, SILQ hhi, Klaim cohort rates. Rename-without-remove candidates flagged separately.
  - **Session 30 → Framework codification complete:** `framework_evolution.jsonl` entry `6e0978f7-…` was blocked on "second data point". This sweep provided two (SILQ Coll Ratio P0-1 + Aajil P0-2/P0-3). Entry now carries `codified=true`, `codified_commit=0dec8ae`, `codified_section="§17 Population Discipline"`, `promoted=true` + platform-standard audit fields.
  - **Commits on branch `claude/objective-mendel-7c5b74`:** audit report `4e14b59`; initial sweep `a4d0d34..03192d0` (12); follow-up `7549312..<current>` (10). Total 22 commits. Net diff ~4,800 lines (2,173 initial + ~2,600 follow-up). Zero regressions at every commit. No pushes.
- ✅ **Session 33 — Executive Summary hardening: Aajil audit + 5 prompt disciplines (2026-04-22):**
  - **Six commits landed over four symptom-fix cycles** — each commit surfaced the next layer of failure. Aajil was the stress case because its tool coverage is partial; Klaim/SILQ had masked the same latent issues through fuller coverage.
  - **Cycle 1 — `86c12a8` + `b6a9d04`:** tool signatures + JSON contract. First-pass audit fixed `_get_covenants` (imported nonexistent `compute_aajil_covenants`), `_get_deployment` (assumed Klaim's `Month` column), `_get_ageing_breakdown` (assumed `Status='Executed'`). Sync-path exec summary prompt rewritten to mirror stream endpoint's JSON contract (was asking for markdown narrative; fell into a fallback that wrapped raw markdown as `severity='positive'` "Agent Summary" — rendered as misleading teal POSITIVE card). New `_parse_agent_exec_summary_response()` helper strips ```json fences → tries `json.loads()` → extracts outermost `{...}` substring on preamble like "I now have comprehensive data…" → final fallback is `severity='warning'` "Summary generated (unparsed)" (never 'positive').
  - **Cycle 2 — `9673b22`:** `max_tokens_per_response` bump. Analyst default (2000) was catastrophically low for structured JSON with 6-10 sections + findings. Response truncated mid-string at `"assessment":`. `_run_agent_sync()` gained override param; both exec summary call sites bump to 16000. Other analyst calls (commentary, tab_insight, chat) keep the 2000 cap.
  - **Cycle 3 — `df76558`:** Error propagation through terminal `done`. Backend captured runtime-yielded `StreamEvent("error")` into SSE stream but never set `stream_error`, so terminal `done` payload had no `error` field. Frontend's `onError` fired with real message, then `onDone` clobbered it with generic "Stream ended without a result". Backend now captures runtime errors; frontend `onDone` only fires its fallback if `errorSet` is false.
  - **Cycle 4 — `e232d55`:** Second-pass audit caught `_get_dso_analysis` and `_get_dtfc_analysis` — both called `load_tape(Aajil)` in their `else` branch. Both metrics are Klaim-specific (DSO = days-from-funding; DTFC = days-to-first-cash); Aajil uses installment DPD. Both handlers now return hint strings pointing at working alternatives. Full audit of all 19 `load_tape()` call sites: all guarded.
  - **Cycle 5 — `abacdcf`:** Content-review output. After the pipeline worked end-to-end and produced a real Executive Summary PDF, a content review surfaced 6 agent-behavior issues independent of the transport/tooling bugs. NEW: `core/agents/prompts.py` — single source of truth for Executive Summary prompt. Both sync + stream endpoints import `build_executive_summary_prompt()`. Five new binding rule sections:
    1. **ARITHMETIC DISCIPLINE** — derived numbers must reconcile (gross − recoveries = net verified to last digit); category sums must equal totals or explicitly flag residuals; completed-vs-portfolio denominators must be named and reconciled.
    2. **COMPUTE, DON'T ESTIMATE** — tool-computable numbers must be called; explicit ban on "estimated", "approximately", "likely exceeds" as computation substitutes; aggregates spanning categories must list components and sum them.
    3. **SECTION DISCIPLINE** — produce exactly the sections in the guidance, no silent substitution; e.g. if guidance names "Cohorts" the agent must call `analytics.get_cohort_analysis`, not swap in "Loss Attribution".
    4. **FINDINGS DISCIPLINE** — ranked findings are credit/portfolio observations only. Tool-availability gaps and undefined-thesis status go to the new `analytics_coverage` callout, not the findings list.
    5. **SEVERITY CALIBRATION** — explicit thresholds so recovery rate <30% = Critical (not Warning), single-name concentration >10% = Warning, >15% = Critical, sector >50% = Warning, >70% = Critical, covenant breach = Critical.
  - **NEW schema field: `analytics_coverage`** (optional string). 1-3 sentence callout naming unavailable analytics + undefined thesis. Parser normalises empty/whitespace/non-string values to `None` so the frontend doesn't render a placeholder. Rendered as a muted amber `AnalyticsCoverageCallout` between Bottom Line and Key Findings — visually distinct from credit severity signals.
  - **CLAUDE.md new "Agent Tool Coverage Checklist"** (6 items) next to the Methodology checklist. Locks in: graceful-skip strings must NOT start with `Error:` or `Tool error` (runtime's 3-errors circuit breaker, `core/agents/runtime.py:470`); every `load_tape()` call site needs a guard or company-specific branch; section_guidance_map in BOTH `core/agents/internal.py` and `backend/main.py` needs per-company entries; regression tests in `tests/test_agent_tools.py` per analysis_type.
  - **Scope:** 6 of 7 content issues were prompt-level, affecting every company. Klaim/SILQ hadn't surfaced them only because their tool coverage was fuller. No per-company prompt changes needed for future onboards — only tool coverage + section_guidance_map entries.
  - **Tests: 525 passing, 59 skipped** (baseline 504). New: `tests/test_exec_summary_prompt.py` (20 prompt-contract tests that lock in each of the 5 rule sections as text contracts) + 4 new tests in `tests/test_exec_summary_stream.py` covering `analytics_coverage` pass-through + SSE round-trip + non-string defense. Existing error-propagation test strengthened to assert terminal done carries runtime error message.
  - **5 new lessons** in `tasks/lessons.md` — ask-latent-elsewhere-before-fixing (scope discipline), fallback-severity-must-render-as-failure, audit-tool-dispatch-per-analysis-type, max-tokens-guards-cost-not-correctness, button-labels-must-match-action.
  - **Commits:** `86c12a8`, `b6a9d04`, `9673b22`, `df76558`, `e232d55`, `abacdcf`.
- ✅ **Session 32 — Executive Summary SSE stream (2026-04-22):**
  - **Root cause fixed.** Aajil `/executive-summary` returned HTTP 524 (Cloudflare origin timeout, ~100s cap on Free plan). Frontend used `getExecutiveSummaryAgent` → `generate_agent_executive_summary` → analyst agent with `max_turns=20`. On Aajil the agent legitimately exceeds 100s because most analytics tools crash on Klaim-specific column assumptions and the agent loops on tool errors. Blocking GET → CF kills connection → 524.
  - **New SSE endpoint** `GET /companies/{co}/products/{p}/ai-executive-summary/stream` (`backend/main.py`). Cache-hit fast path emits `start → cached → result → done` instantly (uniform code path for the client). Cache miss: builds an agent prompt extended with an explicit JSON output contract, runs the analyst agent in a **dedicated thread with its own event loop**, pushes `StreamEvent`s to the main loop's `asyncio.Queue` via `loop.call_soon_threadsafe`. 20s `: keepalive\n\n` heartbeat on idle survives CF's 100s cap. Intercepts the runtime's `done`, parses accumulated text as JSON, caches, emits structured `result` + one terminal `done` carrying `turns_used` + token counts. Sync endpoint preserved untouched.
  - **Thread offload was critical.** Initial implementation awaited `runner.stream()` inline in an asyncio task — uvicorn's main event loop froze every time the agent's SYNC Anthropic client made an HTTP call. Heartbeats didn't fire, queue didn't drain, `/health` timed out. Symptom: stage stuck at "Starting…" for 83s while backend log showed tool calls actually executing. Fix documented in `tasks/lessons.md` 2026-04-22 entry + "Key Architectural Decisions" note — binding for any future agent SSE endpoint.
  - **Frontend `streamExecutiveSummary` helper** (`frontend/src/services/api.js`) — `fetch` + `ReadableStream` + `AbortController` (not `EventSource`: need cookie credentials). Parses SSE frames, dispatches to per-event handlers (`onStart`, `onCached`, `onText`, `onToolCall`, `onToolResult`, `onBudgetWarning`, `onResult`, `onError`, `onDone`, `onHeartbeat`, `onAbort`).
  - **Live progress UI.** `ExecutiveSummary.jsx` rewritten to consume the stream. New `StreamProgressPanel` — terminal-style live timeline: current stage with blinking cursor + elapsed `mm:ss` + prior stages with ✓ in a scroll box. Friendly labels for 20+ tool names (`get_par_analysis` → "Assessing portfolio at risk", `get_cohort_analysis` → "Walking vintage cohorts", etc). Hint banner appears after 45s. Stale-closure bug avoided via `resultEmitted` local flag.
  - **4 regression tests** (`tests/test_exec_summary_stream.py`): cache-hit event sequence, agent-path forwarding + single terminal done + cache-write side effect + result-after-last-text ordering, JSON-parse fallback to warning finding, error-event forwarding.
  - **Browser-verified end-to-end:** stream held open **4m24s** on Aajil in Chrome — **4.4× past** the old CF 524 point. 15+ tool calls streamed live; every stage transition rendered in real time. 488 tests pass (59 DB tests skipped in worktree — DATABASE_URL not set).
  - **Follow-up spawned separately:** Aajil agent tools have pre-existing bugs (`compute_aajil_covenants` doesn't exist; `_get_deployment`/`_get_ageing_breakdown` assume Klaim's `Month`/`Status` columns). Agent quality for Aajil is gated on those fixes — but SSE transport is now proven working regardless.
- ✅ **Session 31 — DB as snapshotted source of truth (2026-04-22):**
  - **Root cause fixed.** `_portfolio_load` silently preferred the DB path when `has_db_data()` was True, but DB was seeded once from an older Mar 3 tape, had no snapshot dimension, and `db_loader` dropped every non-core column. On 2026-04-21 Apr 15 covenants returned `wal_active=183d / Breach / Total WAL=n/a / sel['date']=datetime.now()` instead of 148d / Path B / 137d / 2026-04-15. See `tasks/lessons.md` entry "Silent data-source routing betrays every downstream consumer" for the full post-mortem.
  - **New ORM table `snapshots`** (migration `c3d4e5f6a7b8`, destructive per D1a, applied to both local + prod). `product_id + name` unique; `source ∈ tape/live/manual`; `taken_at` (asset date); `ingested_at`; `row_count`. `Invoice.snapshot_id NOT NULL FK` with composite unique `(snapshot_id, invoice_number)` — same invoice can exist in many snapshots with different state at each. `Payment.snapshot_id NOT NULL FK` (duplicated from invoice for efficient querying). `BankStatement.snapshot_id` nullable. `FacilityConfig` unchanged (singleton per product).
  - **`scripts/ingest_tape.py` (new CLI).** One tape file → one Snapshot row + N invoices + M payments. `Invoice.extra_data` JSONB keys use the **original tape column names verbatim** ('Expected collection days', 'Collection days so far', 'Provider', …). Reader spreads every key back onto the DataFrame with its original name — new analytical columns flow through the entire stack automatically, never need a `db_loader` mapping update. CLI: `--company/--product/--file`, `--all`, `--dry-run`, `--force`. Idempotent on (product_id, name).
  - **Read path rewrite (`core/db_loader.py`).** New `list_snapshots(db, co, prod)` and `resolve_snapshot(db, co, prod, snapshot)` (accepts snapshot name, filename-with-extension, or ISO date; falls back to latest by `taken_at`). `load_klaim_from_db` / `load_silq_from_db` now take `snapshot_id` kwarg. `has_db_data` removed — DB is the only runtime source, no tape fallback.
  - **`_portfolio_load` rewritten** (`backend/main.py`): DB-only; 404s on unknown snapshot with a hint pointing at `ingest_tape.py`. `sel['date'] = snap.taken_at` (real date, not `datetime.now()`). As-of-date auto-resolves to snapshot: when caller passes `as_of_date` matching a real snapshot's `taken_at`, prefer that snapshot — lets the existing Portfolio as-of-date dropdown act as a snapshot selector without frontend rewrite.
  - **Honest data-source badge.** Every portfolio endpoint returns `data_source='database'` + `snapshot_source=sel.source`. `PortfolioAnalytics.jsx:127` badge reads these verbatim — "Tape Fallback" lie replaced with "Live Data".
  - **Rolling-daily live snapshot (Integration API write path).** `get_or_create_live_snapshot(db, product)` creates `live-YYYY-MM-DD` on first push of each UTC day; subsequent same-day pushes UPSERT by `(snapshot_id, invoice_number)` into it; next day creates a new snapshot, prior day becomes frozen history. `is_snapshot_mutable(snapshot, today)` — True only for today's live snapshot. Integration API endpoints: POST /invoices + /bulk UPSERT into today's snapshot; PATCH/DELETE require live-today else 409; POST /payments inherit parent invoice's `snapshot_id`. Request/response contracts unchanged — no caller-visible breaking change.
  - **`SnapshotSelect` component** (`frontend/src/components/SnapshotSelect.jsx`, new): custom dropdown with colour-coded pills (TAPE=gold, LIVE=teal, MANUAL=blue) next to each option, keyboard nav (arrows/Enter/Esc), click-outside, ARIA `role=option` + `aria-selected`. Replaces native `<select>` in TapeAnalytics controls bar and DataIntegrityChart's Old Tape / New Tape dropdowns. `CompanyContext` exposes `snapshotsMeta` (full `{filename, date, source, row_count}` objects) alongside the existing `snapshots` string array — back-compat preserved for all legacy consumers. Dead `DarkSelect` helpers removed from both locations.
  - **9 snapshots backfilled locally + on prod** (5 Klaim + 4 SILQ), 42,535 rows total. Every tape file ever uploaded is now an immutable snapshot in DB. Verified end-to-end in browser on both local and prod: Apr 15 → 148d / Path B / Total WAL 137d; Mar 3 → 140d / Path B / Total WAL n/a (graceful degradation when tape lacks `Collection days so far`). Badge reads "Live Data". No phantom `2026-04-21` snapshot in dropdown.
  - **38 new tests** (`tests/test_db_snapshots.py` 28 + `tests/test_integration_snapshots.py` 10). **498 tests passing** (was 460). Covers: ingest round-trip + `extra_data` preservation (Apr 15 new columns), Mar 3 graceful degradation, snapshot resolution modes, DB↔tape equivalence, snapshot isolation (Apr 15 ≠ Mar 3), live-snapshot helper idempotency, mutability rules, Integration API UPSERT + 409 on tape/prior-day-live.
  - **Commits on `main`:** `dae0d02` (CovenantCard Path B), `aba8994` (schema + read path), `074d382` (live write path + tests), `ccff5ab` (SnapshotSelect UI).
- ✅ **Session 30 — Klaim Apr 15 tape: validation fixes + Provider + dual-view WAL (2026-04-21):**
  - **Part 1 — validation/consistency recalibration** (`4f2d186`): Balance Identity check rewritten to Klaim identity `Paid + Denied + Pending ≡ Purchase value` (1% tolerance); old rule fired on 2,775/8,080 deals (34% false positive) because `Collected` legitimately exceeds `Paid` via VAT + fees. After fix: 2,775 → 0 flags on Apr 15. Graceful skip on tapes without `Paid by insurance`. Separate Over-Collection (`Coll > 1.5 × PV`) check kept (catches 1 deal on Apr 15 — structural sanity signal). Status reversal `Completed → Executed` downgraded from CRITICAL to WARNING with `note` field (known Klaim denial-reopen pattern: deal closes on booked payment, subsequent denial reopens it to Executed for dispute/collection work). Mar 3 → Apr 15: 55 critical reversals → 55 warnings, 0 critical. Note propagates into AI integrity report prompt + frontend ConsistencyItem (italic subtitle). Other reversal paths stay CRITICAL. 6 regression tests (TestBalanceIdentityKlaim, TestStatusReversalSeverityKlaim).
  - **Part 3 — dual-view WAL** (`1bfdbf2`): `wal_active_days` (148d Apr 15, outstanding-weighted) remains the covenant value per MMA Art. 21 (Confidence A). New `wal_total_days` (137d Apr 15, PV-weighted across active + completed) is an IC/monitoring view that strips retention bias from active-only WAL (Confidence B). Close-date proxy for completed deals: `Collection days so far` observed, clipped to `[0, elapsed]`, fallback to `Expected collection days` when observed is missing/negative. Documented in `compute_methodology_log()` as a `close_date_proxy` adjustment. Covenant card (`frontend/src/components/portfolio/CovenantCard.jsx`) renders both in breakdown + dashed-divider `view_note` block. Covenant compliance decision still keyed only to Active WAL (Path A ≤ 70d OR Path B Extended Age ≤ 5%). Older tapes (Mar 3 and earlier): wal_total = None, `wal_total_available: false`, graceful. `column_availability` in methodology log now tracks `Paid by insurance`, `Pending insurance response`, `Expected collection days`, `Collection days so far`, `Provider`. 8 regression tests (TestDualViewWAL).
  - **Part 2 — Provider column wired** (`300bcde`): Apr 15 tape introduces `Provider` (216 distinct), a strict sub-dimension of `Group` (144 distinct). 16 Groups have multiple Provider branches (ZNEEM PHARMACIES 20, MANARA GROUP 19, etc.); 128 are 1:1. No Provider maps to multiple Groups — clean tree. `compute_concentration` emits `result.provider` (top-15, same shape as group). `compute_hhi` adds `provider` (Apr 15 HHI = 0.0201 ≈ 201 bps²). `compute_hhi_for_snapshot` emits `provider_hhi` in time series (null on older tapes). `compute_segment_analysis` accepts two new dimensions `group` (144 → top-25 + Other) and `provider` (216 → top-25 + Other) — high-cardinality collapse keeps dropdown + heat-map readable. Frontend: ConcentrationChart gains Provider donut + top-8 inline list and a Provider HHI badge. SegmentAnalysisChart's dimension selector now filters against `res.available_dimensions` so older tapes auto-hide Provider. Live dev-server smoke test (Chrome): Apr 15 renders ALPINE/ALRAIAA/AFAQ top 3 providers, Provider HHI badge, zero console errors; Mar 3 hides Provider artefacts + Provider dim button. 12 regression tests (TestProviderConcentration, TestProviderSegmentAnalysis). **Not the Account Debtor** — still no insurance-payer column; this is branch-level operational attribution only.
  - **Part 4 — covenant history method tagging** (`9a9bc84`): every covenant dict in `compute_klaim_covenants` now carries a `method` field describing how the current reading was computed — `direct` (uses Expected collection days), `proxy`, `age_pending`, `cumulative`, `stable`, `manual`. Paid vs Due's `pvd_method` variable was already set locally but never written to the dict; now it is. `_save_covenant_history` persists `method` on every append. `annotate_covenant_eod`'s `two_consecutive_breaches` rule now checks method consistency — if prior record's method differs from current, status becomes `first_breach_after_method_change` + `method_changed_vs_prior: true` flag, chain does NOT escalate to EoD. This eliminates a false Paid-vs-Due EoD that would otherwise have fired: Apr 13 entry was computed on March tape with `proxy` method (no Expected collection days), Apr 15 entry uses `direct` — two points weren't methodology-comparable. PAR60 EoD (single-breach rule, methods matched `age_pending` on both) correctly remains triggered. Legacy history entries without `method` are treated as unknown and not penalised (`bool(None and X)` short-circuits). Backfilled Klaim Apr 13 entries with real methods used. 5 regression tests (TestCovenantMethodTagging).
  - **Part 5 — DataChat HHI context cleanup** (`5a3032b`): `chat_with_data` HHI context builder labelled `key='group'` as "Provider" (stale from before Provider column existed) and only iterated over `['group', 'product']`. AI chat saw Group HHI under a Provider heading and never saw actual Provider HHI. Fixed to iterate `['group', 'provider', 'product']` with correct labels.
  - **3 new lessons** in `tasks/lessons.md` — validate-identity-before-writing-check (Part 1), observed-over-contractual-for-dual-weighted-invariants (Part 3), persistent-history-files-must-record-compute-method-per-entry (Part 4).
  - **Totals:** 6 commits, **504 tests passing** (was 473). Every touched line traces to one of the five parts.
- ✅ **Session 29 — Klaim data-room doubling: 4-bug fix + heal (2026-04-20):**
  - User reported Klaim Document Library showing 153 docs (real count: 76). Three independent bugs compounded on top of a latent filesystem duplicate (nested `data/klaim/dataroom/dataroom/` from session-17 migration). Fourth bug surfaced during recovery.
  - **Bug 1 — engine self-pollution** — `_EXCLUDE_FILENAMES` expanded from 4 → 10 entries (`meta.json`, `ingest_log.jsonl`, `covenant_history.json`, `facility_params.json`, `debtor_validation.json`, `payment_schedule.json`) + unconditional dotfile rejection in `_is_supported()`. Kills ingestion of `.classification_cache.json` and similar engine-written sidecars.
  - **Bug 2 — within-pass hash dedup** — `ingest()` now updates `existing_hashes` after every successful ingest; `refresh()` gained a parallel `registry_hashes` dict with the same semantics. Same-bytes files at different folder paths (common for ESOP plans, cap tables, founder bios referenced from multiple deal folders) now dedup to one registry entry per pass. New `duplicates_skipped` counter.
  - **Bug 3 — frontend `CATEGORY_CONFIG`** — extended from 9 → 28 entries covering every backend `DocumentType` enum (investor_report, fdd_report, financial_model, tax_filing, vintage_cohort, bank_statement, audit_report, cap_table, board_pack, kyc_compliance, …). Also fixed latent `financial_statement` singular/plural mismatch. Document Library chips now show real type labels instead of a row of "Other (2), Other (6), Other (14)…" keyed by raw enum values.
  - **Bug 4 — refresh filepath relink** — when a disk file's hash matches an existing entry but the entry's registered filepath is no longer on disk (source moved/renamed/deleted), the entry now gets its `filepath` field updated to the current disk path ("relink") instead of being dedup-skipped. The earlier dedup-skip logic + removal sweep combo dropped 55 Klaim entries silently after the user cleaned up the nested dir. New `relinked` counter distinguishes this from genuine duplicate-skips.
  - **Auto-heal `dedupe_registry()` method** — idempotent healing pass: collapses sha256-duplicate entries (keeps earliest `ingested_at` winner, drops rest + their chunk files), evicts entries whose filename is now excluded. Auto-called at top of `ingest()` and `refresh()` so pre-existing bad state converges every run. Also exposed as `dataroom_ctl dedupe [--company X]`.
  - **Prod healing run** — Klaim dedupe result: 75 sha-dupes removed, 2 excluded-filename entries removed, registry 153 → 76. Nested `data/klaim/dataroom/dataroom/` 128MB duplicate tree removed after moving its unique `notebooklm_state.json` to parent + taking a tarball backup. Final audit on prod: `registry=76 chunks=76 aligned=true unclassified=3 index=ok`.
  - **12 regression tests** in `tests/test_dataroom_pipeline.py` pin each class of bug (TestExclusions, TestWithinPassHashDedup, TestRefreshRelink, TestDedupeRegistry). 473 tests total, all passing.
  - **3 new lessons** in `tasks/lessons.md` — dedup-maps-must-update-in-loop, engine-must-not-ingest-its-own-files, hash-match-without-relink-is-data-loss.
  - **1 doc left un-indexed** — `1.5.2.3.2 AFS_KT DMCC_2023.pdf` — `qpdf --linearize` rewrote the xref but PyMuPDF still choked on a deeper xref-stream issue. Skipped as 1 of 76; Chrome print-roundtrip available if needed.
- ✅ **Post-Session-24 rollout bugfix patch (session 25 — 2026-04-18):**
  - **Bidirectional orphan eviction + `prune` subcommand** (`core/dataroom/engine.py`, `scripts/dataroom_ctl.py`) — session 24 handled registry→chunks-missing eviction but not the reverse (chunks→registry-missing). Because `doc_id` is uuid4, every forced re-ingest leaves old chunk files behind; registry stays clean via sha256 dedup, but filesystem leaks. New `DataRoomEngine.prune()` sweeps orphan chunk files; auto-called at top of `ingest()` and `refresh()`; `orphan_chunks_deleted` surfaces in result dict + `ingest_log.jsonl` extras. CLI: `dataroom_ctl prune [--company X] [--product Y]`.
  - **CLI output ordering hygiene** (`scripts/dataroom_ctl.py`) — `_emit()` flushes stderr before stdout, guaranteeing human summary lands before JSON in merged pipes (`2>&1 | head -1`).
  - **Polish `temperature` deprecation fix** (`core/memo/generator.py`, `core/ai_client.py`) — Stage 6 polish was 400ing (Opus 4.7 rejects `temperature`); memos saved un-polished, contradictions unresolved. Dropped `temperature=0.3` from polish call + added tier-aware filter in `ai_client.complete()` (`_STRIPS_TEMPERATURE_TIERS = {"polish", "judgment"}`) so the router quietly drops the kwarg for tiers routing to Opus 4.7-era models. Sonnet citation audit `temperature=0.1` left intact (Sonnet still accepts).
  - **Memo pipeline short-circuit protection** (`core/memo/generator.py`) — **the critical fix.** Production symptom: 3-of-12 sections saved, no Haiku/Opus in `models_used`, no sidecars, `total_elapsed_s=39.86s`. Investigation: storage.py writes sections verbatim (confirmed no save-layer filter), so upstream truncation. Defensive changes: (1) `_generate_parallel` catches `BaseException` around `fut.result()` so `GeneratorExit`/`SystemExit` from progress_cb during SSE client disconnect can't tear down the `as_completed` loop; (2) null-slot backfill — if `results[idx]` is None at loop end, synthesize an error placeholder so template order is preserved; (3) `_generate_parallel` returns `(sections, errors)` tuple with stage attribution (`parallel_worker`/`parallel_future`/`parallel_backfill`); (4) `_generate_judgment_sections` wraps synthesis in try/except so one Opus failure doesn't block subsequent judgment sections, returns third `errors` list element; (5) **error gate inverted** — Stage 5.5 (citation audit) and Stage 6 (polish) now run whenever `any(s.get("content") for s in memo["sections"])` rather than being blocked by ANY earlier error. New SSE event types: `section_error`, `pipeline_error`. New regression test: `test_parallel_failure_does_not_truncate_pipeline`.
  - **`/operator/*` → `/api/operator/*` route rename** (`backend/operator.py`, `backend/intelligence.py`, `frontend/src/services/api.js`, CLAUDE.md endpoints table) — bare `/operator` SPA route collided with `APIRouter(prefix="/operator")`; reverse proxy prefix-matched `/operator` to backend which 404'd (no exact-match route there). In-app navigation worked; direct URL / browser refresh failed. Moved all backend operator endpoints under `/api/operator/*` (matches existing `/api/integration/*` convention). Auth middleware verified: `/api/operator/*` doesn't accidentally match the `/api/integration/` skip prefix.
  - **Tests:** 420 passing (was 268+ baseline). Added 3 ai_client tier-filter tests + 1 memo pipeline failure-injection regression test.
  - **Post-rollout follow-ups:**
    - **Fix 5b — nginx `/operator` proxy block removed** (`docker/nginx.conf`): the Python rename alone wasn't enough; `docker/nginx.conf:54` had an explicit `location /operator { proxy_pass http://backend:8000 }` block baked into the frontend image at build time. After deploy, nginx still forwarded `/operator` to backend (which now had no handler), returning `{"detail":"Not Found"}`. Deleted the block — the existing `try_files $uri $uri/ /index.html` SPA fallback now catches `/operator`; `/api/operator/*` still routes via the `/api/` block.
    - **OperatorCenter Health tab dataroom path fix** (`backend/operator.py:102`): stale product-level path (`product_path / "dataroom" / "registry.json"`) left over from before session 17's company-level migration. Legal and Mind paths had been migrated; dataroom probe in the Health tab was missed, causing every company to show "— DOCS" and "Data room not ingested" even when fully populated. Corrected to `Path(DATA_DIR) / company / "dataroom" / "registry.json"` matching the rest of the file.
- ✅ **Memo polish fix + SSE transport hardening (session 26.2):**
  - **Stage 6 polish JSON truncation fixed** (`163cba6`) — `core/memo/generator.py` `_polish_memo` + `_validate_citations` rewritten to per-section parallel loop at `LAITH_PARALLEL_SECTIONS` cap. Kills the ~40K-char Opus 4.7 single-blob truncation that left memos at `polished: false`. `_MAX_TOKENS_POLISH_SECTION = 4000`, per-section `generation_meta["polish"]` block (attempted/polished/failed tallies). Partial failures retain pre-polish content with section-key attributed errors. **428 tests passing** (added `test_polish_runs_per_section`, `test_partial_polish_failure_preserves_memo`). Backfill script `scripts/backfill_polish.py` created; 5 historical Klaim memos healed to v2.
  - **Cloudflare HTTP/2 + SSE fixed via 20s heartbeat** (`f5d2a7b`) — `backend/agents.py` `memo_generate_stream` emits `: keepalive\n\n` SSE comment lines when the event queue is idle ≥20s, keeping byte flow alive under CF Free's ~100s idle-proxy cap during long pipeline stages. Comment lines are spec-ignored by clients + by the MemoBuilder manual-parser. 15-line patch, no frontend change, zero infra. **Verified end-to-end:** fresh Klaim memo `13a852f9-4ba` in 2m35s, $5.27, `polished=True`, fully green browser UX — no error toast, smooth progress, auto-redirect.
  - **Registry.json git-tracking eliminated** (`5844c92` + `fc66e7c`) — dropped `!data/*/dataroom/registry.json` negation from `.gitignore`; untracked 4 per-machine registry files. Server now authoritative on both rails (sync-data.ps1 AND git). Collision pattern from session 26 EOD structurally impossible.
  - **Cost estimate docs updated** (`68d1bde`) — per-section polish fan-out ships prior-sections context with each parallel Opus call (~11× input tokens vs monolithic). Baseline `~$1.50-2.50` → `~$3.50-6.00` per full Credit Memo. Trade-off explicit: reliability over token economy.
- ✅ **Data Room Pipeline Hardening — production acceptance (session 26):**
  - **Acceptance Checks A/B/C PASSED end-to-end on Hetzner VPS** — Klaim Credit Memo `c1686e76-841` generated, persisted, and verified on production. 12/12 sections, hybrid-v1 pipeline, Opus 4.7 + Sonnet 4.6 in `models_used`, both sidecars present. $0.71 cost, 33K tokens.
  - **Agent tool signature fixes** (`0e82f35`) — `core/agents/tools/analytics.py` had 4 hard errors (TypeError on 2-arg compute_cohorts/compute_returns_analysis called with 4 args; ImportError on compute_klaim_covenants in wrong module; `asyncio.get_event_loop()` raising in ThreadPoolExecutor on Python 3.12) + 2 silent-correctness bugs (`compute_segment_analysis` routing `dimension` through `as_of_date` positional slot). Fixed via patch prompt to fresh session. 6 new smoke tests in `test_agent_tools.py`. 426 tests passing.
  - **Cloudflare HTTP/3 disabled** — QUIC + SSE edge-proxy incompatibility caused browser `ERR_QUIC_PROTOCOL_ERROR` on memo generate. HTTP/3 off at CF eliminates the symptom. (HTTP/2 + SSE still has edge-buffering issues — backend persists memo regardless of browser stream state; follow-up tracked.)
  - **Verification pattern change** — when SSE transport fails mid-pipeline, inspect persisted memo artifacts (`v1.json`, `meta.json`, sidecars) directly before re-running. Backend completes writes before emitting final `done` event, so data is recoverable even with a broken browser stream.
- ✅ **Data Room Pipeline Hardening (session 24 — prevents silent degradation):**
  - **Orphan-eviction dedup** — `engine.ingest()` + `engine.refresh()` verify `chunks/{doc_id}.json` exists on disk before trusting registry sha256 keys. Missing chunks → evict the registry entry so the file re-ingests. Kills the "0 new, 40 skipped" failure mode caused by pushing a pre-populated registry to a server without chunks. Result field `orphans_dropped` surfaces the count.
  - **Startup dependency probe** (`backend/main.py` lifespan) — imports 5 optional deps (pdfplumber, docx, sklearn, pymupdf4llm, pymupdf) at app start, logs ERROR for each missing, writes `data/_platform_health.json` with `missing[]` + `present[]`. Makes silent dep rot impossible.
  - **`index_status` in meta.json** — `_build_index()`/`_search_tfidf()` log WARNING on ImportError and set `index_status: "degraded_no_sklearn"`. Surfaced via `/dataroom/health` endpoint so operators see degradation without reading logs.
  - **`engine.audit(company, product)`** — returns `{registry_count, chunk_count, aligned, missing_chunks[], orphan_chunks[], unclassified_count, index_status, index_age_seconds, last_ingest}` — detects both directions of registry-vs-chunks misalignment plus classification gaps.
  - **`engine.wipe()` + `engine.rebuild_index_only()`** — operator-level repair primitives. wipe() deletes registry/chunks/index/meta (source files preserved); rebuild_index_only() reruns TF-IDF from existing chunks without re-parsing.
  - **`/dataroom/health` endpoint** — `GET /dataroom/health` (all companies) + `GET /companies/{co}/products/{p}/dataroom/health`. Powers OperatorCenter Data Rooms tab.
  - **`scripts/dataroom_ctl.py` unified CLI** — 6 subcommands (audit, ingest, refresh, rebuild-index, wipe, classify). JSON on stdout (deploy.sh/CI-scrapeable) + human text on stderr. Semantic exit codes (0=ok, 1=misalignment, 2=usage, 3=failed, 4=aborted). `--only-other --use-llm` for retroactive classification without re-parse.
  - **`core/dataroom/ingest_log.py`** — append-only JSONL manifest at `data/{co}/dataroom/ingest_log.jsonl`. One line per ingest/refresh with duration, counts, errors, index status. Consumed by audit() for `last_ingest` field.
  - **deploy.sh alignment check** — replaced fragile "chunks dir non-empty → skip" heuristic with `registry_count == chunk_count` check. Catches first-time setup, post-sync, partial failures, orphans. Invokes `dataroom_ctl ingest` (not inline Python). `git stash` removed (was silently eating server-side state).
  - **sync-data.ps1 fixes** — excludes `registry.json` from push (server is authoritative registry owner). Adds `-o ServerAliveInterval=30 -o ServerAliveCountMax=20` to every ssh/scp call for long ingests.
  - **Session 26.1 follow-up: `.gitignore` registry-negation removal** (commits `5844c92` + `fc66e7c`) — closed the second collision rail. `.gitignore` had `!data/*/dataroom/registry.json` that overrode the blanket `data/*/dataroom/*` ignore, re-tracking registries despite sync-data.ps1 exclusion. All 4 registries (SILQ/klaim/Tamara/Aajil) `git rm --cached` and the negation removed. Server now owns `registry.json` on both rails (sync pipeline AND git pipeline). Collision pattern is now structurally impossible.
  - **Classifier expansion** — 5 new DocumentType enum values (BANK_STATEMENT, AUDIT_REPORT, CAP_TABLE, BOARD_PACK, KYC_COMPLIANCE), UNKNOWN distinct from OTHER. New filename rules (zakat, kpmg_, ey_, cap.?table, board.?pack, kyc, credit.?policy). New content rules (opening balance, audit opinion, fully diluted, board of directors). New `_SHEET_RULES` for Excel tab-name inspection — vintage/covenant/cap table/P&L patterns.
  - **`core/dataroom/classifier_llm.py`** — Haiku fallback invoked only when rule classifier returns OTHER. SHA-256 keyed cache at `data/{co}/dataroom/.classification_cache.json` (same file never triggers a second LLM call, cross-company). Strict JSON parsing with ```json fence tolerance. Confidence < 0.6 → DocumentType.UNKNOWN. Lazy import of core.ai_client (rule classifier works standalone). ~$0.001/doc, ~$0.04 for all 40 SILQ files.
  - **OperatorCenter "Data Rooms" tab (8th tab)** — per-company cards showing Registry/Chunks/Missing/Orphans/Unclassified/Index stats + last_ingest timestamp. Colored borders (teal=aligned, gold=misaligned, red=error). Repair command hint per card.
- ✅ **Hybrid 6-stage memo pipeline (`core/memo/generator.py`, `core/ai_client.py`, `core/memo/agent_research.py`):**
  - Stage 1: Context assembly — analytics + data-room chunks + 5-layer mind context
  - Stage 2: 9 structured sections generated in **parallel** via ThreadPoolExecutor (`LAITH_PARALLEL_SECTIONS=3` cap) — Sonnet 4.6
  - Stage 3: 1 auto section (appendix) — Haiku 4
  - Stage 4: **Short-burst research packs** per judgment section — Sonnet agent, 5-turn hard cap, returns structured JSON (key_metrics, quotes, contradictions, recommended_stance, supporting_evidence)
  - Stage 5: Judgment synthesis — Opus 4.7, sequential (for coherence), consumes research packs
  - Stage 5.5: **Citation validation** — Sonnet per-section parallel calls (at `LAITH_PARALLEL_SECTIONS` cap), skipped for sections with no citations
  - Stage 6: **Polish pass** — Opus 4.7 per-section parallel calls (at `LAITH_PARALLEL_SECTIONS` cap), preserves metrics/citations, explicitly resolves contradictions with resolve/flag rules. Per-section fan-out fixed the ~40K-char JSON truncation that plagued the original single-blob call. `polished=True` only when all polishable sections succeed; partial failures retain pre-polish content with error attribution in `generation_meta["polish"]`.
  - Post-save: `record_memo_thesis_to_mind()` writes agent-recommended stance to CompanyMind findings (memo_id provenance) — future memos see prior recommendations
  - Sidecar storage: `_research_packs` → `research_packs.json`, `_citation_issues` → `citation_issues.json` (audit trail, immutable on first save, stripped from `v{N}.json`)
  - Rate-limit engineering: SDK retry/backoff via `max_retries=3` (configurable via `LAITH_AI_MAX_RETRIES`), parallel cap prevents ITPM bursts
  - Model routing: 5 tiers (auto/structured/research/judgment/polish), env-overridable via `LAITH_MODEL_*`, fallback chains (Opus 4.7 → 4.6 → 4.20250514) on NotFoundError
  - Cost: ~$3.50-6.00 per full Credit Memo, ~3-5 min wall-clock. Higher than the pre-fix ~$1.50-2.50 baseline because per-section polish fan-out ships the full prior-sections context with each of the N parallel Opus calls (~11× input tokens vs a single monolithic call). Trade-off: reliability over token economy — Opus 4.7 single-blob hit a ~40K char output ceiling that truncated polish output mid-string.
  - Memo metadata: `generation_mode: "hybrid-v1"`, `polished: bool`, `models_used: {...}`, `total_tokens_in/out`, `cost_usd_estimate` in meta.json
  - Both save paths use the pipeline: agent SSE endpoint (`/agents/{co}/{prod}/memo/generate`) streams live progress events (`pipeline_start`, `section_start/done`, `research_start/done`, `citation_audit_start/done`, `polish_start/done`, `saved`, `done`) AND saves the memo; legacy endpoint (`/companies/{co}/products/{prod}/memos/generate`) returns JSON after save
- ✅ **Central Anthropic client (`core/ai_client.py`):**
  - Singleton client with `max_retries=3` (SDK exponential backoff on 429/529/503)
  - `complete(tier, system, messages, max_tokens, ...)` wrapper — logs token usage + cache hits, attaches `_laith_metadata` (tier, model, elapsed_s, cache tokens)
  - `get_model(tier)` — env override → fallback chain → cached
  - `_mark_unavailable()` — walks fallback chain on NotFoundError (Opus 4.7 → 4.6 → 4.20250514)
  - Prompt caching helpers: `system_with_cache()`, `cache_last_tool()`
  - Cost estimation: `estimate_cost(model, in_tokens, out_tokens, cache_read)` with 10% discount on cache hits
  - Migration complete: 8 call sites now routed through `complete()` — backend/main.py (5), core/legal_extractor.py, core/research/query_engine.py, core/reporter.py. Agent runtime (`core/agents/runtime.py`) also uses shared client for retry config.
- ✅ **Extended prompt caching:**
  - System prompts (4 locations, pre-existing): runtime.py run/stream, legal_extractor, memo generator
  - **NEW:** Tool schema prefix cached via `cache_last_tool()` on every agent run/stream call — ~20-30% token savings on multi-turn
  - Bare-string system prompts auto-wrapped with `cache_control` via `ai_client.complete()`
- ✅ **Authentication + RBAC (Cloudflare Access JWT + app-side roles):**
  - Cloudflare Access handles login (email OTP, allowlists, geo-restrictions) — branded login page with dark navy background + lion logo
  - Backend: `backend/cf_auth.py` — reads `CF_Authorization` cookie / `Cf-Access-Jwt-Assertion` header, verifies RS256 JWT against Cloudflare public keys, caches keys (1hr TTL)
  - Auto-provisioning: first login creates User record. `ADMIN_EMAIL` env var gets admin role, all others get viewer
  - Auth middleware: `CloudflareAuthMiddleware` — skips `/auth/*`, `/api/integration/*`, OPTIONS. Dev mode (no `CF_TEAM`) passes all requests through
  - Auth routes: `backend/auth_routes.py` — `/auth/me`, `/auth/logout-url`, `/auth/users` CRUD (admin-only)
  - User model: `core/models.py` `User` table (email, name, role, is_active, timestamps). Migration `b2f3a8c91d45`
  - Frontend: `AuthContext.jsx` (calls `/auth/me` on mount), `ProtectedRoute.jsx` (route guard), `UserMenu` dropdown in Navbar (initials avatar, email, role badge, "Manage Users" for admin, "Log out")
  - User Management: `/admin/users` page — invite users, edit roles, deactivate/reactivate (admin-only)
  - Env vars: `CF_TEAM`, `CF_APP_AUD`, `ADMIN_EMAIL` in `.env.production`
  - Existing X-API-Key integration auth completely untouched
- ✅ **Operator Command Center (`/operator` page + `/ops` slash command):**
  - Backend: `backend/operator.py` — `GET /operator/status` (aggregate health, gaps, commands), todo CRUD, mind browse/promote, Slack digest
  - Activity logging: `core/activity_log.py` — centralized JSONL logger wired into 14 endpoints (AI, reports, legal, data room, memos, mind, alerts)
  - Frontend: `OperatorCenter.jsx` — 5-tab dashboard (Health Matrix, Commands, Follow-ups, Activity Log, Mind Review)
  - Health Matrix: per-company cards with tape freshness badges (green/amber/red), legal/dataroom/mind stats, auto-detected gaps
  - Command menu: 11 framework + 3 session + 7 deep work modes in categorized grid
  - Follow-ups: persistent todo list (`tasks/operator_todo.json`) with priority, category, company tags — separate from Claude's `tasks/todo.md`
  - Mind Review: browse all mind entries (master + company), filter by source, promote company entries to master mind
  - Navigation: `/operator` route, "Ops" link in Navbar, Operator Card in Home Resources
  - `/ops` slash command: terminal operator briefing at session start
- ✅ **Weekend Deep Work protocol (`WEEKEND_DEEP_WORK.md`):**
  - 7 modes: Codebase Health Audit, Test Generation Sprint, Architecture Review, Documentation Sprint, Prompt Optimisation, Red Team Review, Regression Validation
  - State-save progress manifest (`reports/deep-work/progress.json`) for session resumption
  - Two-pass file analysis strategy (core engines before UI)
  - Self-audit validation pass cross-referencing CLAUDE.md and ANALYSIS_FRAMEWORK.md
  - Financial business logic stress tests (covenant leakage, waterfall errors, separation principle)
  - Tiered frequency: weekly (Red Team) → bi-weekly (Health + Tests) → monthly (Architecture + Regression) → quarterly (Full Combo)
- ✅ **Legal Analysis (third pillar):**
  - PDF upload + 5-pass AI extraction engine (`core/legal_extractor.py`) — ~$1.25/doc, cached forever
  - Pydantic extraction schemas (`core/legal_schemas.py`) — Tier 1 (facility, eligibility, advance rates, covenants, concentration), Tier 2 (EOD, reporting, waterfall), Tier 3 (risk flags)
  - 3-tier facility params priority: document → manual → hardcoded default. `_load_facility_params()` auto-merges
  - Compliance comparison engine (`core/legal_compliance.py`) — doc terms vs live portfolio metrics side-by-side
  - 12 backend endpoints (`backend/legal.py`) — upload, documents, facility-terms, eligibility, covenants-extracted, events-of-default, reporting, risk-flags, compliance-comparison, amendment-diff
  - Frontend: `LegalAnalytics.jsx` + 8 tab components (DocumentUpload, FacilityTerms, EligibilityView, CovenantComparison, EventsOfDefault, ReportingCalendar, RiskAssessment, AmendmentHistory)
  - Sidebar: Legal Analysis section between Portfolio Analytics and Methodology (hidden when `hide_portfolio_tabs: true`)
  - Executive summary integration: legal compliance context fed into `_build_klaim_full_context()`
  - Framework: `LEGAL_EXTRACTION_SCHEMA.md` — extraction taxonomy, confidence grading, param mapping
  - 22 tests (schemas, mapping, compliance comparison, parser utils) — all passing
  - Parameterized `ineligibility_age_days` and `cash_ratio_limit` in `core/portfolio.py` (was hardcoded 365 and 3.0)
  - **Klaim facility documents reviewed:** 4 PDFs (MMA 130pp, MRPA 60pp, Qard 15pp, Fee Letter 3pp) with human-reviewed extraction JSONs at 96% confidence, $0 AI cost
  - **Multi-document extraction merge:** `load_latest_extraction()` merges all documents — lists concatenated (deduped by name), dicts merged (primary credit_agreement wins)
  - **Account Debtor validation:** CRITICAL DATA GAP — tape has no payer column; 10% non-eligible debtor limit unenforceable from tape data. Saved to `legal/debtor_validation.json`
  - **Payment schedule:** 17-payment schedule ($6M, 13% p.a., ACT/360) stored in `legal/payment_schedule.json`, served via reporting endpoint, rendered in ReportingCalendar.jsx
  - **Consecutive breach history:** `annotate_covenant_eod()` + `covenant_history.json` persistence per MMA 18.3 — `first_breach`, `breach_no_eod`, `eod_triggered` statuses with styled frontend badges
  - **Path fix:** `get_legal_dir()` now uses absolute path (was relative, broke when backend ran from subdirectory)
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
  - Research Chat: per-company suggested questions — `SUGGESTED_QUESTIONS` map keyed by `analysisType` (`klaim`, `silq`, `ejari_summary`, `tamara_summary`, `default`); tailored data room questions per company
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
  - Cache key: `(endpoint, company, product, snapshot, currency, file_mtime)` — separate cache per currency, auto-invalidates on file replacement
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
  - 8 tables: users, organizations, products, snapshots, invoices, payments, bank_statements, facility_configs (snapshots added in Session 31)
  - Tape-compatible DataFrame bridge (`core/db_loader.py`) — snapshot-scoped reads, `extra_data` JSONB round-trip, zero changes to analysis functions when tape schema evolves
  - Tape ingest CLI (`scripts/ingest_tape.py`) — one Snapshot per tape file, `--all` / `--dry-run` / `--force` flags; legacy `scripts/seed_db.py` still present for reference
- ✅ **Phase 2B — Integration API:**
  - 12 inbound endpoints under `/api/integration/` for portfolio companies to push data
  - X-API-Key authentication (SHA-256 hashed, org-scoped)
  - Invoices: CRUD + bulk create (up to 5,000/request), rolling-daily UPSERT by `(snapshot_id, invoice_number)` into `live-YYYY-MM-DD` snapshot (Session 31)
  - Payments: create + bulk create, inherit invoice's `snapshot_id` on write
  - Bank statements: create with optional base64 PDF upload, tagged with live snapshot
  - PATCH/DELETE return 409 on tape or prior-day-live snapshots (immutability rule, Session 31)
  - API key generation CLI (`scripts/create_api_key.py`)
- ✅ **Phase 2C — Portfolio computation engine:**
  - `core/portfolio.py` — borrowing base waterfall, concentration limits (4 types, tiered thresholds), covenants (5-6 per asset class), portfolio cash flow
  - Supports both Klaim (receivables factoring) and SILQ (POS lending) asset classes
  - `_portfolio_load()` — DB-only read path, resolves snapshot via `resolve_snapshot()`, 404s on unknown snapshot (Session 31)
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
- ✅ **Mobile responsiveness (comprehensive, 29 files):**
  - `useBreakpoint` hook — `{ isMobile, isTablet, isDesktop }` via matchMedia listeners
  - `MobileMenuContext` — sidebar drawer coordination (open/close/toggle), route-change auto-close, body scroll lock
  - Sidebar: 240px fixed → slide-in drawer on mobile (fixed position, translateX animation, dark backdrop overlay, close button)
  - Navbar: 80px → 56px on mobile, hamburger menu on company pages, hidden Framework/Live/v0.5 chips, scaled-down logo
  - All KPI grids (`repeat(5,1fr)`, `repeat(4,1fr)`, `repeat(3,1fr)`) → `repeat(auto-fill, minmax(140-150px, 1fr))`
  - All 2-column layouts (`1fr 1fr`) → `repeat(auto-fit, minmax(280px, 1fr))` — single column on mobile
  - PortfolioStatsHero: gap 56px → 12px, values/labels scaled down, dividers hidden, empty Live Portfolio banner hidden on mobile
  - Padding reduced 28px → 14px on all pages for mobile
  - Framework/Methodology: sidebar TOC hidden on mobile (content takes full width)
  - ChartPanel: added `overflowX: auto` for wide table horizontal scrolling
  - CSS tokens: `--navbar-height` responsive variable, table scroll override
  - Desktop layout preserved identically — zero regressions
- ✅ **As-of date fix:** Defaults to snapshot date (from filename), not max deal date in data
- ✅ **Analysis Framework (Phase 0):**
  - `core/ANALYSIS_FRAMEWORK.md` — analytical philosophy document with 5-level hierarchy (Size → Cash Conversion → Credit Quality → Loss Attribution → Forward Signals)
  - 6 sections: Analytical Hierarchy, Metric Dictionary, Tape vs Portfolio Philosophy, Asset Class Adaptations, Leading vs Lagging Indicators, Separation Principle
  - `GET /framework` endpoint serves markdown content
  - `Framework.jsx` — full-page markdown renderer with sticky TOC, accessed via Navbar link
  - Resources section on Home page with Framework card (teal accent)
- ✅ **Resources section revamp — live cards + Architecture page (Commit 1a):**
  - OperatorCard + FrameworkCard now fetch live vitals from `/api/operator/status` and `/api/platform-stats` (gaps, follow-ups, stale tapes, framework section count + "+N new since last visit" badge via localStorage)
  - New ArchitectureCard (violet accent, `⚙`) on the landing page → `/architecture` page with live platform capability stats (endpoints, DB tables, mind entries, dataroom docs, legal docs, tests, memos, framework sections) and inline SVG system architecture diagram following the Cocoon-AI architecture-diagram-generator skill guide (JetBrains Mono, dashed platform boundary, users-left/services-right, legend, bottom summary strip with 3 columns). Stats refresh on every visit — no manual regeneration.
  - New backend endpoint `GET /api/platform-stats` — live counts: companies, products, snapshots, routes (total + grouped by prefix), DB tables (from SQLAlchemy metadata), mind entries (master + per-company JSONL row counts), framework sections, methodology pages, dataroom docs, legal docs, tests, memos, AI tiers, framework last-modified timestamp.
  - Route added: `/architecture` in App.jsx. Three Resources cards now: Operator, Framework, Architecture.
  - **1b (feedback-loops diagram):** Added a `LoopsDiagram` SVG above the component diagram. Three loops — Ingestion (tape → Mind → Thesis → Briefing), Learning (correction → classify → rule → AI context), Intelligence (doc → entity → cross-company scan → Master Mind). Each loop closes back on itself with a dashed arc + caption. New "Self-Improvement Loops" CapabilityCard added as the first card. Component diagram retained as the "what it's made of" view beneath the "how it thinks" loops view.
- ✅ **External Intelligence — four-layer system (Commit 2):**
  - **Asset Class Mind (top-level store):** `core/mind/asset_class_mind.py`, storage at `data/_asset_class_mind/{asset_class}.jsonl`. Sits between Master Mind (fund-level) and Company Mind (per-company) — keyed by the **semantic `asset_class`** field in each company's `config.json` (one of `healthcare_receivables`, `bnpl`, `pos_lending`, `rnpl`, `sme_trade_credit`). Categories: benchmarks, typical_terms, external_research, sector_context, peer_comparison, methodology_note. Every company with the same `asset_class` value shares the same Asset Class Mind. **Note:** session 28 Finding #3 discovered Layer 2.5 had originally been keyed by `analysis_type` (company-shortname like "klaim"), which never matched the semantic asset-class filenames — leaving Layer 2.5 empty for every company. Now distinctly keyed.
  - **Layer 2.5 injection in `build_mind_context()`:** AI context builder assembles **6 layers**: Framework → Master → **Asset Class** → Methodology → Company → Thesis. Resolution order for the asset-class key: explicit `analysis_type` argument → `cfg["asset_class"]` → `cfg["analysis_type"]` fallback (legacy configs). `MindLayeredContext` dataclass carries an `asset_class` field. Empty asset-class result falls back gracefully (no-op).
  - **MasterMind extended:** Added `sector_context` category + generic `record(category, content, metadata)` method so external-origin sector/regulatory knowledge can land at the fund level via the pending-review promotion path.
  - **Pending Review Queue (NEW):** `core/external/pending_review.py` — file-backed queue at `data/_pending_review/queue.jsonl`. Trust model: external evidence NEVER auto-writes to any Mind. Every external-origin entry lands here first with `status=pending`, citations, provenance. Analyst approves → promotes to target mind store (CompanyMind / AssetClassMind / MasterMind) based on declared `target_scope`. Rejected entries retained for audit trail. Entry schema includes query, source, target_scope, target_key, category, title, content, citations[], status, review metadata, promoted_entry_id.
  - **Agent tool `external.web_search`:** `core/agents/tools/external.py` — wraps Anthropic's server-side `web_search_20250305` tool. Registered in the tool registry. Model supplies query + target scope/key/category; handler makes a nested Claude call with web_search enabled, extracts citations and synthesized answer, creates ONE pending-review entry (one entry per search keeps analyst review tractable), returns a summary. Category validation per target_scope enforced at tool-call time.
  - **Backend API (`/api/*`):** `backend/external.py` adds endpoints under `/api/pending-review` (list/get/create/approve/reject, plus counts) and `/api/asset-class-mind` (list all, list entries per class, create manual entry). Registered in main.py.
  - **OperatorCenter "Pending" tab (9th tab):** shows count-badge with current pending total, lists each entry with source/scope/category chips, query, full content, clickable citation links, Approve/Reject buttons. Audit trail visible via status counts row (pending / approved / rejected). Action errors surface inline.
  - **Architectural note:** web search never writes directly to any Mind. This preserves trust — the Mind stays analyst-curated; external evidence goes through a reviewable queue. Same contract scales to future sources (news polling, SEC EDGAR, industry APIs) — they all land in pending-review first.
  - **Promotion pipeline (Commit 3):** `core/mind/promotion.py` — `promote_entry(source_scope, source_key, entry_id, target_scope, target_key, target_category, note)`. Chain: Company → Asset Class → Master. Source entry is never moved — a copy is written to the target with `metadata.promoted_from` chain preserved, and the source's `metadata.promoted_to` list is appended + `promoted=True`. Asset-class entries can only promote to Master (enforced). Backend: `POST /api/mind/promote`. UI: new 10th OperatorCenter tab "Asset Classes" with per-class browser + "↑ Promote to Master" button on each entry. Source retains provenance pointer; destination shows `← from {scope}/{key}` in the browser.
  - **Diagnostic endpoint updated:** `GET /companies/{co}/products/{prod}/mind/context` now reports `asset_class_length` + `thesis_length` alongside the other four layers for full 6-layer observability.
  - **Session 28 hardening:**
    - **Per-tool runtime timeout override** — `AgentRunner.TOOL_TIMEOUT_OVERRIDES_BY_PREFIX = {"external.": 180}` + `_timeout_for_tool()` classmethod. Default 30s was cutting off `external.web_search` (nested Claude call routinely takes 40-90s) even when the handler completed successfully on its own thread.
    - **CALL BUDGET clause in tool description** — `external.web_search` description now explicitly says "make ONE comprehensive call per user request". Pairs with regression test that greps for the phrase so doc drift breaks CI.
    - **Asset class seeding** — `scripts/seed_asset_class_mind.py` writes 12 conservative platform-docs entries across all 5 asset classes on first install. Strict sourcing rule: every seed traces to CLAUDE.md or methodology_*.py (zero fabricated benchmarks). Idempotent.
    - **memo_writer agent gets `external.*`** — memo drafts can trigger pending-review web research mid-draft.
    - **Legacy soft-flag removed** — `PATCH /operator/mind/{id}` endpoint (plus `MindUpdate` model and `_promote_to_master` helper) deleted; UI now uses real `/api/mind/promote` for Company → Master too.
- ✅ **Framework Codification Hook (session 28 D6):**
  - `core/mind/framework_codification.py` — `get_codification_candidates()`, `mark_codified()`, `codification_counts()` over `data/_master_mind/framework_evolution.jsonl`. Atomic JSONL rewrite on mark (.tmp + fsync + rename). Entries stay after codification for audit history.
  - `GET /api/framework/codification-candidates?include_codified=false` — returns `{candidates, counts}` for analyst visibility.
  - `POST /api/framework/codify/{entry_id}` — body `{commit_sha?, framework_section?, codified_by?}` → sets audit fields on source entry.
  - OperatorCenter **Codification tab** (13th tab) — stats row (Pending/Codified/Total), pending/all filter, per-entry card with status chip + provenance ("← from asset_class/bnpl") + inline mark-codified form.
  - Intended first consumer: the `/extend-framework` slash command (reads candidates → proposes Framework updates → calls codify endpoint after PR lands).
- ✅ **Layer 2.5 citation rendering in AI output (session 28 D2):**
  - `MindLayeredContext.asset_class_sources: List[Dict]` populated by `build_mind_context()` from every Asset Class Mind entry's `metadata.citations`. Deduped by URL, capped at 50. Each row carries entry category + title + source type + page_age.
  - **Chat endpoint** (Klaim + SILQ branches) returns `asset_class_sources` in response; `DataChat.jsx` renders collapsible "▸ Informed by N asset-class sources" footer, up to 25 clickable titles with provenance suffixes.
  - **Executive Summary endpoint** returns `asset_class_sources`; `ExecutiveSummary.jsx` renders matching `AssetClassSourcesFooter` component between Bottom Line and Key Findings.
  - Framing is "Informed by" (not "citing") because we don't have per-paragraph provenance — the list represents "what was in context during generation", which is honest. AI Commentary deliberately skipped (currently injects zero mind context; adding citations would require rewriting the prompt to include Layer 2.5 first).
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
- ✅ **Tamara BNPL onboarded (data room ingestion — third pattern):**
  - Saudi Arabia's first fintech unicorn ($1B valuation, 20M+ users, 87K+ merchants)
  - **Data room ingestion pipeline:** `scripts/prepare_tamara_data.py` reads ~100 source files (vintage cohort matrices, Deloitte FDD, HSBC investor reports, financial models, demographics) from OneDrive data room → structured JSON snapshots
  - **Two products:** KSA (SAR, 18 tabs) and UAE (AED, 14 tabs) — geography-based split matching securitization facilities
  - `analysis_type: "tamara_summary"` — follows Ejari read-only summary pattern but with much richer data
  - **18 KSA tabs:** Overview, Vintage Performance, Delinquency, Default Analysis, Dilution, Collections, Repayment Lifecycle, Customer Behavior, Concentration, Covenant Compliance, Trigger Trends, Facility Structure, Payment Waterfall, Demographics, Financial Performance, Business Plan, BNPL+ Deep Dive, Data Notes
  - **Novel visualizations:** VintageHeatmap (CSS-grid color-coded vintage × MOB matrix with toggle for default/delinquency/dilution), CovenantTriggerCard (3-level L1/L2/L3 trigger zone visualization), ConcentrationGauge (horizontal gauge bars)
  - **Securitisation facilities:** KSA $2.375B (Goldman, Citi, Atlas/Apollo, Morgan Stanley — 5 tranches), UAE $131M (Goldman — 2 tranches)
  - **Products:** BNPL (Pi2-6, up to SAR 5K), BNPL+ (Pi4-24, SAR 5K-20K, Murabaha profit APR 21-40%)
  - **Data sources parsed:** ~50 vintage cohort Excel files, Deloitte FDD loan portfolio (12,799 rows), 20 HSBC PDF investor reports, monthly investor reporting (25 months), portfolio demographics, 5-year business plan, Repayment Status & Transaction History (quarterly stratification Q4 2023–Q1 2026)
  - Frontend: `TamaraDashboard.jsx` (821 lines, all components inline), Recharts interactive charts
  - Backend: `core/analysis_tamara.py` parser, `/tamara-summary` endpoint, `tamara_summary` branches in 7 existing endpoints
- ✅ **Credit Research Report — platform capability:**
  - `core/research_report.py` — generates comprehensive dark-themed PDF credit research reports for ANY company
  - Backend endpoint: `POST /companies/{co}/products/{prod}/research-report`
  - 8-section structure for Tamara: Executive Summary, Company Overview, Portfolio Analytics, Vintage Cohort Performance, Covenant Compliance, Facility Structure, DPD Analysis, Data Sources
  - Laith dark theme branding (navy background, gold headers, teal/red metrics)
  - ReportLab Platypus composition with styled tables, cover page, page numbering
  - Accepts optional `ai_narrative` parameter for Claude-powered narrative sections
  - Extensible: generic fallback builder for non-Tamara companies, company-specific builders can be added
- ✅ **Four data ingestion patterns now supported:**
  - **Raw Tape** (Klaim, SILQ): CSV/Excel loan-level data → live computation per request
  - **Pre-computed Summary** (Ejari): Single ODS workbook → parse once, render
  - **Data Room Ingestion** (Tamara): ~100 multi-format files → ETL script → JSON snapshot → parser → dashboard
  - **Investor Deck Extraction** (Aajil): Single PDF → manual data extraction script → JSON snapshot → parser → dashboard
- ✅ **Aajil SME Trade Credit — full live tape analytics (session 19):**
  - New asset class: SME raw materials trade credit (KSA, SAR) — 5th portfolio company
  - `analysis_type: "aajil"` — live tape analytics from multi-sheet xlsx (1,245 deals, 7 sheets)
  - 11 compute functions: summary, traction, delinquency, collections, cohorts, concentration, underwriting, yield, loss_waterfall, customer_segments, seasonality
  - `core/validation_aajil.py` — 13 tape quality checks
  - 38 tests (306 total passing)
  - `AAJIL_CHART_MAP` + generic `/charts/aajil/{chart_name}` endpoint
  - 13-tab dashboard: Overview, Traction (Volume/Balance toggle), Delinquency (overdue buckets + by Deal Type), Collections, Cohort Analysis (DPD time series + vintage table), Concentration (HHI + top-15 + industry), Underwriting (drift by vintage), Trust & Collections (trust score system), Customer Segments (EMI/Bullet + industry + size), Yield & Margins (revenue decomposition), Loss Waterfall (per-vintage), Covenants, Data Notes
  - Cascade Debt alignment: Volume = Principal Amount (99.9% match), MoM = +32.36% (exact), Collection rate = Realised/Principal (87.3%)
  - Dataroom: 14 files ingested (investor deck, 3 audited financials, 2 tax returns, monthly statements, budget, debt overview)
  - Key finding: ALL 19 write-offs are Bullet deals (0 EMI) — structural shift to EMI reducing default risk
- ✅ **Tamara P0 fixes — data extraction, AI context, dashboard charts:**
  - Fixed column-offset bug (labels in col 1 not col 0) across investor reporting, business plan, financial master parsers
  - Fixed demographics pivot (AE+SA side-by-side → per-country dimension extraction)
  - Fixed Financial Master filename mismatch (54.2.2.2 prefix)
  - Now populated: 73 KPIs, 136 financial line items, 5 demographic dimensions (26 records), 51 BP metrics, 152 FM metrics
  - `_build_tamara_full_context()` — 40 context lines for BNPL-specific AI Executive Summary
  - Dashboard upgraded 821→988 lines, 8→23 Recharts containers: financial trend chart, business plan projection chart, demographics grouped bars with dimension selector
  - Concentration gauges wired to HSBC data + instalment type pie chart
- ✅ **Landing page multi-product card carousel:**
  - Dual flags: `countryCode` supports arrays (`['sa', 'ae']`) — renders both flags side-by-side
  - Auto-rotating carousel for multi-product companies: cycles stats every 3.5s with Framer Motion crossfade
  - Dot indicators (click to manually switch), pause on hover, resume on leave
  - Row 2 adapts: "Facility" row for multi-product (Limit, Merchants, Users) vs "Live Portfolio" for single-product
  - All product summaries fetched (not just first) to populate carousel data
  - Single-product cards (Klaim, SILQ, Ejari) completely unaffected
- ✅ **Research Hub (data room ingestion + Claude RAG research):**
  - Data room engine: ingest any directory (PDF, Excel, CSV, JSON, DOCX), chunk, index, search
  - Claude RAG query engine with source citations
  - Rules-based insight extraction at ingest time
  - Analytics snapshots as searchable research sources
  - Frontend: DocumentLibrary, ResearchChat
  - **Tamara data room ingested** (session 21, fresh re-ingest): 134 files, 4,076 chunks, 1,744 pages, 9 document types, 63 PDFs. Document classification: vintage cohort matrices (51) are whole-book data, HSBC investor reports (20) + legal DD are facility-specific.
  - **Klaim data room ingested** (session 17): 28 docs, 492 chunks, 320 pages
- ✅ **Living Mind (institutional memory):**
  - Master Mind: fund-level preferences, IC norms, cross-company patterns
  - Company Mind: per-company corrections, findings, IC feedback, data quality
  - 4-layer context injected into ALL AI prompts
  - Klaim seeded with legal analysis findings (6 data quality + 4 findings + 2 IC feedback)
  - Tamara KSA seeded with entity extraction from data room (Event of Default risk flag from HSBC reports)
- ✅ **IC Memo Engine:**
  - 4 templates: Credit Memo, Due Diligence, Monthly Monitoring, Quarterly Review
  - Analytics Bridge: live metrics from tape/portfolio analytics
  - AI section generator with mind context
  - Versioning: draft → review → final
  - PDF export in dark theme
  - Frontend: MemoBuilder wizard, MemoEditor (mobile-responsive), MemoArchive
  - Bug fixes: MemoEditor mobile layout (flex-direction), section edit/regenerate endpoint args
- ✅ **Legal Analysis (third analytical pillar):**
  - 5-pass Claude extraction from facility agreement PDFs
  - Pydantic schemas for all extracted terms
  - 3-tier facility params merge (document > manual > hardcoded)
  - Compliance comparison (extracted vs live analytics)
  - 8-tab frontend dashboard
  - Klaim: 4 documents reviewed, 7 parameter updates from MMA/MRPA
- ✅ **Red Team Review + 28 Finding Fixes (Mode 6 Deep Work):**
  - First adversarial review: 8 critical, 14 warning, 6 improvement findings across ~50 files
  - Report: `reports/deep-work/2026-04-11-red-team-report.md`, progress: `reports/deep-work/progress.json`
  - **Security:** Path traversal in legal upload fixed (`os.path.basename`), CF_TEAM empty-string auth bypass guarded
  - **Calculation fixes:** Weighted avg discount double-multiply removed, revenue inf guarded, CDR seasoning filter (< 3 months skipped), PAR benchmark uses snapshot date not `now()`
  - **Business logic:** Snapshot index inverted (BB movement/covenant trends), covenant Collection Ratio marked as cumulative approximation, EoD consecutive period validation, amendment covenant dedup prefers later timestamp
  - **AI hardening:** 22 `try/except: pass` blocks replaced with `data_gaps[]` tracking + DATA GAPS section in context, currency added to AI cache key, file mtime in cache key for same-name replacement
  - **Frontend:** Race condition fixed (AbortController), TabInsight/AICommentary cleared on snapshot change, Tamara read-only badge, PortfolioAnalytics data source badge, DataChat empty response handling
  - **Performance:** db_loader N+1 queries → single pre-aggregate, bounded in-memory caches (max 10)
  - All 156 tests passing after fixes
- ✅ **Intelligence System — Self-Learning "Second Brain" (7-phase build, inspired by Claude+Obsidian pattern):**
  - **Phase 0 Foundation:** `core/mind/schema.py` (KnowledgeNode + Relation dataclasses, backward-compatible via metadata._graph), `core/mind/relation_index.py` (bidirectional adjacency list, BFS chain traversal), `core/mind/event_bus.py` (sync pub/sub, disable for tests). master_mind.py + company_mind.py upgraded with graph metadata + event publishing.
  - **Phase 1 Knowledge Graph:** `core/mind/graph.py` — graph-aware query engine with recency/category/graph bonus scoring, supersession exclusion, contradiction penalty. Neighborhood BFS, staleness detection (60d threshold), compaction of superseded chains.
  - **Phase 2 Incremental Compilation:** `core/mind/entity_extractor.py` (regex extraction of 7 entity types from text + tape metrics), `core/mind/compiler.py` (one-input-many-updates: create/supersede/reinforce/contradict pipeline, compilation reports in JSONL, cross-document discrepancy detection).
  - **Phase 3 Closed-Loop Learning:** `core/mind/learning.py` — LearningEngine auto-classifies corrections (tone_shift, threshold_override, data_caveat, factual_error, missing_context, methodology_correction). Rules auto-generated as KnowledgeNodes (node_type="rule"). Pattern extraction groups 3+ similar corrections into codification candidates. Correction frequency tracking by type.
  - **Phase 4 Thesis Tracker:** `core/mind/thesis.py` — InvestmentThesis + ThesisPillar + DriftAlert. Per-company structured theses with measurable pillars linked to computed metrics. Auto-drift detection: holding → weakening (within 10%) → broken (breached). Conviction score 0-100 per company. Versioned thesis log (JSONL). AI context injection as Layer 5.
  - **Phase 5 Proactive Intelligence:** `core/mind/intelligence.py` (cross-company pattern detection: metric trends, risk convergence, covenant pressure across 2+ companies). `core/mind/briefing.py` (morning briefing with urgency-scored priority actions, thesis alerts, learning summary, recommendations). `core/mind/analyst.py` (persistent analyst context: last session, priority companies, IC dates, focus areas).
  - **Phase 6 Session Tracker:** `core/mind/session.py` — tracks tapes/docs/corrections/rules per session, persists to `reports/session_state.json`, delta computation for "since last session" briefings.
  - **Phase 7 Queryable KB:** `core/mind/kb_decomposer.py` (parses lessons.md entries + CLAUDE.md decisions into linked KnowledgeNodes with stable IDs and topic tags). `core/mind/kb_query.py` (unified search across mind entries + lessons + decisions + entity nodes with text/metadata/tag scoring).
  - **Event Listeners:** `core/mind/listeners.py` — wires TAPE_INGESTED → metric compilation + thesis drift check, DOCUMENT_INGESTED → entity extraction + compilation, MEMO_EDITED → learning rule generation, CORRECTION_RECORDED → correction analysis.
  - **6 Slash Commands:** `/morning` (session-start briefing), `/thesis {company}` (create/review thesis), `/drift` (check all theses), `/learn` (review corrections + auto-rules), `/emerge` (cross-company patterns), `/know {question}` (KB search).
  - **Tests:** 93 new tests (42 foundation + 51 system), all 249 total passing.
  - **Architecture:** JSONL-first (no migration), lazy schema upgrade, event bus with disable() for test isolation, backward-compatible metadata._graph storage. File-based, no new PostgreSQL dependency.
- ✅ **Intelligence System — Backend Integration (wired into live app):**
  - **Event wiring:** `register_all_listeners()` called at app startup. 4 events fire from live endpoints: TAPE_INGESTED (deduped per session), DOCUMENT_INGESTED (from dataroom engine), MEMO_EDITED (with old content for learning), CORRECTION_RECORDED (from chat feedback).
  - **Layer 5 AI context:** `build_mind_context()` now assembles 5 layers (was 4). Layer 5 = ThesisTracker.get_ai_context(). All 4 `_build_*_full_context()` functions benefit automatically. Backward-compatible (empty string when no thesis exists).
  - **10 API endpoints in `backend/intelligence.py`:** thesis CRUD + drift check + log, morning briefing, KB search, learning summary + rules, chat feedback. Router registered in main.py.
  - **OperatorCenter:** 7 tabs (was 5) — added Briefing (priority cards, thesis alerts, recommendations, learning summary) and Learning (correction frequency, auto-rules, codification candidates).
  - **DataChat feedback:** Thumbs up/down buttons on AI responses. Thumbs-down fires CORRECTION_RECORDED, records in CompanyMind.
  - **263 tests passing** (was 249).
- ✅ **Klaim Data Room + Memo Exercise (session 17):**
  - **Legal Analysis tabs** — all 8 validated rendering with extracted data from 4 facility PDFs
  - **Account Debtor validation** — confirmed tape lacks payer column (Group = 143 providers, not 13 approved insurance payers). Recorded in Company Mind.
  - **Consecutive breach history** — `annotate_covenant_eod()` + `covenant_history.json` verified working per MMA 18.3
  - **Klaim data room ingested** — 87 files from `data/klaim/dataroom/`, 1,720 chunks, 1,334 pages. Intelligence System events fired (entity extraction + compilation).
  - **Klaim Credit Memo** — 12 AI sections with Claude RAG research. Full 5-layer context pipeline. Renders in MemoEditor.
  - **Tamara Credit Memo v2** (session 21) — `f3af2d4e-b88`, 12 AI sections (~55K chars), 45 data room citations, covers both KSA + UAE. Old placeholder `0ae5cbe3-095` deleted.
- ✅ **Data room engine moved to company level:**
  - Path: `data/{company}/dataroom/` (was `data/{company}/{product}/dataroom/`)
  - `_dataroom_dir()` updated in engine.py, analytics_snapshot.py
  - `dataroom` excluded from product discovery in `get_products()`
  - Default ingest source: `data/{company}/dataroom/` (removed OneDrive fallback)
  - `_EXCLUDE_DIRS` now blocks `chunks`/`analytics` subdirs instead of "dataroom" itself
- ✅ **Legal and Mind dirs moved to company level:**
  - `legal/`: `data/{company}/legal/` (was `data/{company}/{product}/legal/`). `get_legal_dir()` updated, `'legal'` added to `_NON_PRODUCT_DIRS`
  - `mind/`: `data/{company}/mind/` (was `data/{company}/{product}/mind/`). CompanyMind, ThesisTracker, listeners, and all discovery loops (operator, intelligence, briefing, kb_query, master_mind) updated
  - Matches existing pattern for `dataroom/` at company level
  - Klaim files moved: `data/klaim/UAE_healthcare/{legal,mind}/` → `data/klaim/{legal,mind}/`
  - 5 new tests (268 total, all passing)
- ✅ **Bug fixes (session 17):**
  - `core/loader.py`: Added `covenant_history.json`, `facility_params.json`, `debtor_validation.json` to `_EXCLUDE` (was crashing snapshot sort with None date)
  - `core/loader.py`: Added `_NON_PRODUCT_DIRS` set to exclude `dataroom`, `_master_mind`, `mind` from product discovery
  - `core/memo/analytics_bridge.py`: `isinstance()` check for list vs dict covenant triggers (Tamara uses list, Klaim uses dict)
  - `backend/main.py`: Null-safe sort in `list_companies` (`date or '0000-00-00'`)
- ✅ **Document Library enhancements (session 17):**
  - Category filter chips: clickable pills per document_type with colored borders (gold=Facility Agreement, blue=Company Presentation, teal=Business Plan, purple=Portfolio Tape, gray=Other)
  - Category badges on cards replace generic "FILE" label — human-readable names ("Facility Agreement" not "FACILITY_AGREEMENT")
  - Sort dropdown: Name, Category, Pages, Date Ingested
  - Folder breadcrumbs: last 2 folder segments from filepath shown in italic below filename
  - File viewing: PDF cards clickable, open in new browser tab via `GET /dataroom/documents/{id}/view` endpoint (streams original file with correct MIME type)
  - Text length shown in card metadata (e.g. "18.4K chars")
  - Results count when filtered ("Showing 3 of 87 documents in Company Presentation")
- ✅ **Direct DPD from Expected collection days (session 17 continued):**
  - `compute_par()`: when `Expected collection days` column available, computes `DPD = max(0, today - (Deal date + Expected collection days))` per deal. Replaces shortfall proxy. Method reported as `direct` vs `proxy`. Falls back to proxy for older tapes.
  - `compute_dso()`: DSO Operational = `true_dso - Expected collection days` per deal (was crude `median_term * 0.5` proxy)
  - `compute_klaim_covenants()` Paid vs Due: temporal filtering — only counts deals with expected payment date in period (was all deals with Deal date in period)
  - April 15 tape loaded: 8,080 deals (full portfolio), 65 columns, 5 new incl Expected collection days. Direct DPD working. PAR30 covenant breached (36.6% vs 7% threshold).
- ✅ **Data Room Pipeline Hardening (session 24):**
  - Dedup contract now: sha256 key + artifact presence. `engine.ingest()`/`refresh()` verify `chunks/{doc_id}.json` exists before trusting registry entries; missing chunks evict the orphan so the file re-ingests. `orphans_dropped` returned from ingest result.
  - Server is authoritative registry owner. `sync-data.ps1` excludes `registry.json` from push. Laptop is pure file transport.
  - All ImportError paths log WARNING + write machine-readable status. `backend/main.py` lifespan probes 5 optional deps on startup (pdfplumber/docx/sklearn/pymupdf/pymupdf4llm), writes `data/_platform_health.json`. Engine `_build_index`/`_search_tfidf` set `index_status` in `meta.json` so audit surfaces degradation.
  - `engine.audit()` returns structured health (registry_count, chunk_count, aligned, missing_chunks, orphan_chunks, unclassified_count, index_status, last_ingest). Detects both directions of misalignment. Powers `/dataroom/health` endpoint + OperatorCenter Data Rooms tab.
  - `scripts/dataroom_ctl.py` is the single CLI entry for all dataroom ops. JSON stdout (scrapeable), human stderr, semantic exit codes. deploy.sh invokes it instead of inline `python -c`. Destructive `wipe` requires `--yes` gate.
  - `git stash` removed from deploy.sh — server should have zero local edits; pull failures now stop deploy explicitly.
  - Classifier now has UNKNOWN distinct from OTHER: rule-based first pass returns OTHER for no-match, LLM fallback returns UNKNOWN when confidence < 0.6. `audit()` reports `unclassified_count` as the union.
  - `classifier_llm.py` cache is sha256-keyed cross-company — re-running `classify --only-other` is free on a re-ingest.
-----
## Known Gaps & Next Steps

**Session 33 — Executive Summary hardening: Aajil audit + 5 prompt disciplines ✅ COMPLETE (2026-04-22):**
- [x] **Pass 1 — 3 Aajil tool crashes fixed** (commit `86c12a8`). `_get_covenants` (nonexistent `compute_aajil_covenants`), `_get_deployment` (assumed Klaim's `Month`), `_get_ageing_breakdown` (assumed `Status='Executed'`) now have Aajil branches or graceful skips. 3 regression tests in `TestAajilHandlerSignatures`.
- [x] **Pass 2 — JSON contract + robust parser** (commit `b6a9d04`). Sync-path Exec Summary prompt rewritten to mirror stream endpoint's JSON schema. New `_parse_agent_exec_summary_response()` helper: strips ```json fences → tries `json.loads()` → extracts outermost `{...}` substring on preamble → fallback is severity='warning' "Summary generated (unparsed)" (never 'positive'). 8 parser tests lock in each extraction path + "severity never positive on failure" regression.
- [x] **Pass 3 — max_tokens bump** (commit `9673b22`). Analyst `max_tokens_per_response` was 2000 — catastrophically low for structured JSON with 6-10 sections + findings. Truncation at `"assessment":` mid-string. `_run_agent_sync()` gained override param; both exec summary call sites bump to 16000. Other analyst calls stay at 2000 to cap runaway cost.
- [x] **Pass 4 — Error propagation** (commit `df76558`). Backend wasn't capturing runtime-yielded `StreamEvent("error")` into `stream_error`, so terminal `done` had no error field. Frontend's `onError` fired with real message, then `onDone` clobbered it with "Stream ended without a result". Backend now captures runtime errors; frontend tracks `errorSet` locally.
- [x] **Pass 5 — Second tool audit** (commit `e232d55`). Found 2 more unguarded tools: `_get_dso_analysis` and `_get_dtfc_analysis`. Both Klaim-specific metrics; Aajil uses installment DPD. Graceful-skip hint strings point at working alternatives. Full audit of all 19 `load_tape()` call sites complete.
- [x] **Pass 6 — 5 prompt disciplines + analytics_coverage callout** (commit `abacdcf`). Content review of production PDF output surfaced 6 agent-behavior issues: arithmetic drift, "estimated" when computable, silent section substitution, platform findings mixed with credit findings, lenient severity calibration, metric reconciliation gaps. NEW: `core/agents/prompts.py` — single source of truth for Executive Summary prompt. Five new rule sections (ARITHMETIC DISCIPLINE, COMPUTE-DON'T-ESTIMATE, SECTION DISCIPLINE, FINDINGS DISCIPLINE, SEVERITY CALIBRATION). NEW optional schema field `analytics_coverage` — moves tool-gap + undefined-thesis concerns OUT of ranked findings into a muted amber callout. Frontend `AnalyticsCoverageCallout` component. 20 new prompt-contract tests + 4 SSE round-trip tests.
- [x] **CLAUDE.md Agent Tool Coverage Checklist** (6 items) added next to Methodology checklist. Locks in graceful-skip contract, `load_tape()` audit requirement, section_guidance_map per-company expectation for future onboards.
- [x] **5 new lessons** in `tasks/lessons.md` — ask-latent-elsewhere-before-fixing, fallback-severity-must-render-as-failure, audit-tool-dispatch-per-analysis-type, max-tokens-guards-cost-not-correctness, button-labels-must-match-action.
- [x] **Scope finding:** 6 of 7 content issues were prompt-level, affecting every company (not just Aajil). No per-company prompt changes needed for future onboards.
- [x] **Tests: 525 passing, 59 skipped** (baseline 504).

**Session 31 — DB as snapshotted source of truth ✅ COMPLETE (2026-04-22):**
- [x] **Phase 1 — Schema + migration** (commit `aba8994`). `snapshots` table + snapshot_id FKs on invoices/payments/bank_statements. Migration `c3d4e5f6a7b8` applied local + prod.
- [x] **Phase 2 — Ingest tooling** (commit `aba8994`). `scripts/ingest_tape.py` with `extra_data` JSONB preserving every non-core tape column under its original name. 9 snapshots backfilled (5 Klaim + 4 SILQ), 42,535 rows.
- [x] **Phase 3 — Read path rewrite** (commit `aba8994`). `_portfolio_load` DB-only; `resolve_snapshot()` handles name/filename/ISO-date/None; `load_{klaim,silq}_from_db` take snapshot_id; `has_db_data` removed. Tape-fallback code path gone.
- [x] **Phase 4 — Snapshots endpoint** (commit `aba8994`). `list_product_snapshots` reads DB for klaim/silq; filesystem fallback for ejari/tamara/aajil.
- [x] **Phase 5 — Integration API live-snapshot write path** (commit `074d382`). `get_or_create_live_snapshot(db, product)` rolling-daily; `is_snapshot_mutable()` enforces only-today-accepts-writes; POST /invoices + /bulk UPSERT; PATCH/DELETE 409 on tape/prior-day-live; payment inherits invoice.snapshot_id.
- [x] **Phase 6 — Frontend honesty** (commits `aba8994`, `ccff5ab`). `data_source='database'` + `snapshot_source` on every portfolio response. "Tape Fallback" lie replaced with "Live Data". `SnapshotSelect` component with TAPE/LIVE/MANUAL pills replaces native `<select>` in TapeAnalytics + DataIntegrityChart.
- [x] **Phase 7 — Tests** (commit `074d382`). 38 new tests (28 DB snapshot layer + 10 Integration API). 498 total passing (was 460). Covers ingest round-trip, `extra_data` preservation, snapshot isolation, DB↔tape equivalence, live-snapshot idempotency, mutability rules, Integration API UPSERT + 409.
- [x] **Phase 8 — Verification & acceptance.** Browser-verified end-to-end on local (Apr 15 WAL 148d / Path B / Total WAL 137d; Mar 3 WAL 140d / Path B / n/a graceful) AND on prod https://laithanalytics.ai. Zero app console errors. Data source badge reads "Live Data". No phantom `2026-04-21` snapshot in dropdown.
- [x] **CovenantCard Path B rendering fix** (commit `dae0d02`, pre-Session-31 trigger). Suppresses Path A headroom + breach projection when `compliance_path === 'Path B (carve-out)'` — replaces with muted `note` line. 1 contract test.

**Session 27 — Resources revamp + External Intelligence ✅ COMPLETE (2026-04-20):**
- [x] Commit 1a (`20303e9`): `/api/platform-stats` endpoint + live vitals on Operator + Framework cards + new ArchitectureCard + `/architecture` page with component diagram. Rebased onto main after session 24–26.2 divergence; adopted `/api/*` route convention.
- [x] Commit 1b (`6bc621f`): `LoopsDiagram` SVG — three feedback loops (Ingestion / Learning / Intelligence) with closing arcs above the component diagram. "Self-Improvement Loops" capability card.
- [x] Commit 2 (`1d17e31`): External Intelligence four-layer system — `AssetClassMind` store, `PendingReviewQueue` (trust boundary), `external.web_search` agent tool, Layer 2.5 in `build_mind_context()` (6 layers now), `/api/pending-review` + `/api/asset-class-mind` endpoints, OperatorCenter 9th tab "Pending", MasterMind `sector_context` category + generic `record()`.
- [x] Commit 3 (`aa5bed0`): `core/mind/promotion.py` with full provenance (promoted_from / promoted_to chains), `POST /api/mind/promote`, OperatorCenter 10th tab "Asset Classes" with per-class browser + ↑ Promote-to-Master button.
- [x] Follow-up fixes: analyst agent config exposes `external.*` (`b60d8d3`); platform-stats test counter tolerant regex (`b2c6afe`); Architecture diagram loop-label crowding + arrow overlaps (`3b68f96`); `scripts/verify_external_intelligence.py` 16-check harness — 16/16 pass on user's laptop (`4952ea3`); `ScrollToTopOnNavigate` route-change scroll reset (`0ac4b4d`).
- [x] Agents surfaced on Architecture page (`cc11f78`) — `/api/platform-stats` introspects `core/agents/definitions/` + `registry.tool_names()` + `data/_agent_sessions/`. Architecture.jsx gains 3 stat tiles (Agents / Agent Tools / Sessions, amber), an Agents box in the System Architecture diagram under Integration API, and an "Agents" capability card naming analyst/memo_writer/compliance_monitor/onboarding + session-tracking pointer. Closes a genuine gap from session 27 where agents were invisible on the Architecture page despite being core platform infrastructure.

**Session 28 — External Intelligence acceptance + 3 bug fixes + 4 deferred items (2026-04-20):**
- [x] **Real `external.web_search` smoke test via Klaim DataChat** — drove Chrome end-to-end: query → 3 pending entries created with 30-40 citations each → approve → asset_class_mind → promote to Master → provenance chain verified on disk. Report: `reports/web-search-smoke/smoke-test-results.md`. 3 bugs surfaced, 3 bugs fixed same session.
- [x] **Finding #1** — agent runtime 30s tool timeout cuts off `external.web_search` (nested Claude web_search takes 40-90s). Handler completes + writes pending entry, but runtime tells agent the call failed. Fix: `AgentRunner.TOOL_TIMEOUT_OVERRIDES_BY_PREFIX = {"external.": 180}` + `_timeout_for_tool()` classmethod, 2 regression tests. Commit `48809db`.
- [x] **Finding #2** — agent was splitting one user request into 3 parallel web_search calls (one pending entry per sub-query; cost triples). Fix: added CALL BUDGET clause to `external.web_search` description ("make ONE comprehensive call per user request"), regression test locks it in. Commit `c30ac17`.
- [x] **Finding #3 (highest-impact)** — Layer 2.5 was keyed by `analysis_type` which is the company-shortname ("klaim", "silq") — never matched the semantic asset-class files ("healthcare_receivables", "bnpl"). Layer 2.5 empty for every company regardless of entries. Fix: new `asset_class` field in every `config.json`; `build_mind_context()` prefers it over `analysis_type` with legacy fallback. Commit `c30ac17`. All 6 company configs updated.
- [x] **D1 — Company → Asset Class promote button** — inline form in OperatorCenter Mind tab with asset-class + category dropdowns + optional note, wires to real `/api/mind/promote` (not the soft-flag legacy behaviour). Commit `684b66d`.
- [x] **D3 — Pytest port of verify_external_intelligence.py** — all 16 checks now in `tests/test_external_intelligence.py`, grouped into 5 classes, same isolation strategy via `isolated_project` fixture. Standalone script preserved. Commit `ff75f5f`.
- [x] **D4 — Seed Asset Class Mind** — `scripts/seed_asset_class_mind.py` writes 12 conservative platform-docs entries across all 5 asset classes (no fabricated benchmarks — every entry traces to CLAUDE.md or methodology_*.py). Idempotent. `.gitignore` now covers `_asset_class_mind/`, `_pending_review/`, `_platform_health.json` following `_master_mind/` pattern. Commit `a3b1ad1`.
- [x] **D5 — memo_writer gets external.*** — one-line config change so memo drafts can trigger pending-review web research mid-draft. Commit `e71d49f`.
- [x] Test count: 453 passing (was 436 at session start; +16 from D3, +1 D5 test, +8 Finding tests across runtime/tool/asset_class_resolution).

**Session 28 follow-up — D2, D6, legacy soft-flag (2026-04-20):**
- [x] **D2 — Layer 2.5 citation rendering in DataChat** — `MindLayeredContext.asset_class_sources: List[Dict]` populated by `build_mind_context()` from every Asset Class Mind entry's `metadata.citations`, deduped by URL and capped at 50. Chat endpoint (Klaim + SILQ branches) returns `asset_class_sources` in response payload. `DataChat.jsx` renders collapsible "▸ Informed by N asset-class sources" footer with up to 25 clickable titles + `· {category} · {source} · {page_age}` provenance suffixes. Commit `d37c425`. Also fixed 5 latent executive-summary callers that still passed company-shortname as `analysis_type` (same bug as Finding #3, this time in `_build_{klaim,silq,aajil,tamara,ejari}_full_context()`).
- [x] **D6 — Framework codification hook** — new `core/mind/framework_codification.py` module exposes `get_codification_candidates()`, `mark_codified()`, `codification_counts()` over `data/_master_mind/framework_evolution.jsonl`. Two new endpoints under `/api/framework/`: GET `codification-candidates` (returns `{candidates, counts}`) and POST `codify/{entry_id}` (body `{commit_sha, framework_section, codified_by}` → sets codified audit fields, atomic JSONL rewrite). Intended first consumer is the `/extend-framework` slash command. Backend-half only — no OperatorCenter UI surface this session. Commit `465e0c4`.
- [x] **Legacy "Promote to Master" soft-flag** — MindEntryRow's existing button called `updateOperatorMindEntry(id, {promoted: true})`, a soft flag that only marked the source entry but never copied content into `data/_master_mind/`. Now wired to real `/api/mind/promote` via inline form matching the D1 pattern: Master-category dropdown (6 values from `_MASTER_FILES`), optional note, shared error/submitting state. State refactor: `activeForm` (`null | 'asset_class' | 'master'`) replaces single `showPromoteForm`; both promotion paths mutually exclusive. Commit `00fccf3`. The legacy PATCH `/api/operator/mind/{id}` endpoint still exists but no UI calls it.
- [x] Test count: 461 passing (was 453; +3 D2 `TestAssetClassSources` + 5 D6 `TestFrameworkCodification`).

**Session 28 follow-up round 2 (2026-04-20):**
- [x] **Legacy PATCH `/operator/mind/{id}` endpoint removed** — `update_mind_entry` handler + `MindUpdate` model + `_promote_to_master` helper all deleted from `backend/operator.py` (commit `dd0849c`). The endpoint had been orphaned since the 00fccf3 UI rewiring; this commit removes the backend code so nobody reintroduces a soft-flag promotion path. `updateOperatorMindEntry` export also removed from `frontend/src/services/api.js`.
- [x] **D6 UI surface — Codification tab** (commit `1f631db`) — OperatorCenter gains a 13th tab ("Codification", between Asset Classes and any future tab). New `CodificationTab` component shows 3-number stats row + pending/all filter + per-entry `CodificationCard` (status chip, provenance chain "← from asset_class/bnpl", inline mark-codified form with optional commit_sha + framework_section inputs). `getFrameworkCodificationCandidates` + `markFrameworkEntryCodified` API helpers added. Tab badge shows pending count.
- [x] **D2 broader — Executive Summary citations** (commit `36bd63d`) — `/ai-executive-summary` response gains `asset_class_sources` (same shape as chat endpoint). `ExecutiveSummary.jsx` renders collapsible "▸ Informed by N asset-class sources" footer between Bottom Line and Key Findings, up to 25 clickable titles visible, overflow hint points to Asset Classes tab.

**Session 29 — Klaim data-room doubling investigation ✅ COMPLETE (2026-04-20):**
- [x] **Investigation** — User reported Klaim Document Library showing 153 documents, suspected double-counting. Three independent bugs compounding + a latent filesystem duplicate (full `data/klaim/dataroom/dataroom/` from session-17 migration). Correct state: 76 docs.
- [x] **Bug 1 — engine self-pollution via dotfile** (commit `25bb4c3`) — `_EXCLUDE_FILENAMES` only excluded 4 entries; `.classification_cache.json`, `meta.json`, `ingest_log.jsonl` were being walked + ingested as data. Fix: expanded exclusion list to 10 entries + unconditional dotfile rejection in `_is_supported()`.
- [x] **Bug 2 — within-pass hash dedup missing** (commit `25bb4c3`) — `existing_hashes` in `ingest()` was built once from prior registry, never updated in the loop. Same bytes at two paths both got ingested (ESOP plans, cap tables, audited accounts all duplicated). `refresh()` had the same issue keyed on filepath not hash. Fix: update hash maps after every successful ingest; new `duplicates_skipped` counter.
- [x] **Bug 3 — frontend CATEGORY_CONFIG stale** (commit `25bb4c3`) — `DocumentLibrary.jsx` had only 9 of ~28 backend `DocumentType` values mapped. Every unmapped type rendered as its own chip keyed by raw enum value but labelled "Other" via fallback — UI showed a row of "Other (2), Other (2), Other (6), Other (14), Other (36)…". Fix: extended `CATEGORY_CONFIG` to 28 entries; fixed latent `financial_statement` singular/plural mismatch.
- [x] **Auto-heal `dedupe_registry()` method** (commit `25bb4c3`) — idempotent cleanup pass that collapses sha256-duplicate registry entries (keeps earliest `ingested_at`) and evicts registry entries whose filename is now on the exclusion list. Auto-called at top of `ingest()` and `refresh()` so pre-existing bad state converges on every run. Also exposed as `dataroom_ctl dedupe [--company X]`. Klaim dedupe on prod: 75 sha-dupes + 2 excluded entries removed; registry 153 → 76.
- [x] **Nested `/opt/credit-platform/data/klaim/dataroom/dataroom/` cleanup** — 128MB full-duplicate tree from session-17 migration. `notebooklm_state.json` (only unique file) moved up to parent. Tarball backup taken; `rm -rf` executed.
- [x] **Bug 4 — refresh hash-match without filepath relink** (commit this EOD) — After nested-dir cleanup, `refresh` silently dropped 55 entries: within-pass dedup was `duplicates_skipped`-ing disk files whose registered filepath had just been deleted, then the removal sweep dropped the entries. Fix: when hash matches but registered filepath is NOT on disk, UPDATE the entry's filepath to the disk path ("relink") instead of skip. New `relinked` counter in result payload. Removal sweep now honors `relinked_disk_paths`. Recovery path: `dataroom_ctl ingest --company klaim` re-scanned disk and re-created 55 entries; final audit `registry=76 chunks=76 aligned=true`.
- [x] **12 regression tests** in `tests/test_dataroom_pipeline.py` — `TestExclusions` (5), `TestWithinPassHashDedup` (2), `TestRefreshRelink` (2), `TestDedupeRegistry` (3). 473 total passing (was 461).
- [x] **3 new lessons in `tasks/lessons.md`** — dedup-map-must-update-in-loop, engine-must-not-ingest-its-own-files, hash-match-without-relink-is-data-loss. Each includes a full "how to apply" block with regression test pointers.
- [ ] **`1.5.2.3.2 AFS_KT DMCC_2023.pdf`** — qpdf-fixed xref but PyMuPDF still chokes on a deeper xref-stream issue. Skipped for now (1 of 76 docs); Chrome print-roundtrip fallback available if needed.

**Still deferred (indefinitely):**
- [ ] D7: Scheduled external pollers (parked — on-demand model preferred)
- [ ] D2 for AI Commentary — commentary currently injects zero mind context; adding citations would require rewriting what the AI sees. Separate design discussion if analysts ask.

**Post-Session-24 Rollout Bugfix Patch ✅ COMPLETE (session 25 — 2026-04-18):**
- [x] Fix 1: Bidirectional orphan eviction — `DataRoomEngine.prune()` + auto-call in `ingest()`/`refresh()` + `dataroom_ctl prune` subcommand
- [x] Fix 2: CLI output ordering — `sys.stderr.flush()` in `_emit()` guarantees human summary before JSON in merged pipes
- [x] Fix 3: Polish `temperature` deprecation — dropped from Stage 6 call + tier-aware filter in `ai_client.complete()` (`_STRIPS_TEMPERATURE_TIERS`)
- [x] Fix 4: Memo pipeline short-circuit protection — `BaseException` catch around `fut.result()`, null-slot backfill, content-presence gate replaces error-count gate, new `section_error`/`pipeline_error` SSE events, regression test
- [x] Fix 5: `/operator` → `/api/operator` route rename — backend router prefix + 3 intelligence routes + 10 frontend callers + CLAUDE.md endpoints table
- [x] Fix 6: Dockerfile `COPY scripts/` — already landed as `286cf18` on 2026-04-17
- [x] **Fix 5b** (post-deploy follow-up): Remove `docker/nginx.conf` explicit `/operator` proxy block — SPA now serves `/operator` via `try_files` fallback (commit `7ea5ea6`)
- [x] **Post-deploy follow-up**: `backend/operator.py` Health tab dataroom path migrated from stale product-level to company-level (commit `d0863ea`)

**Data Room Pipeline Hardening ✅ COMPLETE (session 24):**
- [x] Tier 1.1: Orphan-eviction dedup in `engine.ingest()` + `engine.refresh()`
- [x] Tier 1.2: Exclude `registry.json` from `sync-data.ps1` push
- [x] Tier 1.3: `deploy.sh` registry-vs-chunks alignment check (replaces fragile non-empty heuristic)
- [x] Tier 1.4: Remove `git stash` trap from `deploy.sh`
- [x] Tier 1.5: Startup dependency probe → `data/_platform_health.json`
- [x] Tier 1.6: WARNING-log + `index_status` flag for sklearn/pdfplumber ImportError paths
- [x] Tier 1.7: SSH keepalive (`-o ServerAliveInterval=30`) on every ssh/scp in sync-data.ps1
- [x] Tier 2.1: `scripts/dataroom_ctl.py` unified CLI (6 subcommands, JSON stdout, semantic exit codes)
- [x] Tier 2.2: `engine.audit()` + `GET /dataroom/health` endpoint (all + per-company)
- [x] Tier 2.3: `core/dataroom/ingest_log.py` append-only JSONL manifest
- [x] Tier 2.4: `deploy.sh` invokes `dataroom_ctl ingest` (not inline Python)
- [x] Tier 2.5: OperatorCenter "Data Rooms" tab (8th tab)
- [x] `engine.wipe()` + `engine.rebuild_index_only()` repair primitives
- [x] Tier 3.1: 5 new DocumentType enum values + UNKNOWN distinct from OTHER; filename/content/sheet rules
- [x] Tier 3.2: `classifier_llm.py` Haiku fallback with sha256-keyed cross-company cache
- [x] Tier 3.3: LLM fallback wired into `engine._ingest_single_file()` + `dataroom_ctl classify --only-other --use-llm`
- [x] **Acceptance Checks A/B/C (session 26)** — Klaim Credit Memo end-to-end smoke test on Hetzner VPS. Memo `c1686e76-841` persisted with 12/12 sections + sidecars; $0.71 cost; 33K tokens.
- [x] **Agent tool signature audit (session 26, commit `0e82f35`)** — 4 hard errors (TypeError/ImportError in `core/agents/tools/analytics.py`) + 2 silent-correctness bugs fixed; 6 smoke tests added.
- [x] **Cloudflare HTTP/3 disabled** — eliminates QUIC+SSE incompatibility causing browser "network error" during memo generate.
- [x] **Cloudflare HTTP/2 + SSE transport** — resolved via 20s SSE heartbeat in `memo_generate_stream` (commit `f5d2a7b`, session 26.2). Comment-line `:`-prefixed keepalive keeps byte flow alive under CF Free's ~100s idle-proxy cap during long pipeline stages (research, polish). Verified end-to-end with fresh memo `13a852f9-4ba` — 2m35s wall-clock, $5.27, polished=True, browser UX fully green. No Cloudflare Tunnel needed.
- [x] **Memo Stage 6 polish JSON truncation** — resolved session 26.2 via per-section parallel polish (commit `163cba6`). Opus 4.7 single-blob for all-12-sections JSON hit ~40K char ceiling mid-string; `_polish_memo` and `_validate_citations` rewritten to per-section parallel at `LAITH_PARALLEL_SECTIONS` cap with `_MAX_TOKENS_POLISH_SECTION = 4000`. Partial-failure preservation. 5 historical memos backfilled via `scripts/backfill_polish.py`. 428 tests passing. Verified end-to-end with fresh memo `13a852f9-4ba` (2m35s, $5.27, polished=True).


**Memo Pipeline ✅ COMPLETE (session 23):**
- [x] Hybrid 6-stage memo pipeline — parallel structured + short-burst agent research + Opus 4.7 polish
- [x] Central AI client (`core/ai_client.py`) with retry/backoff + tier routing + prompt caching
- [x] Research packs with structured JSON output (contradictions, key metrics, stance)
- [x] Sidecar storage for research packs + citation issues (immutable audit trail)
- [x] Citation validation pass (Sonnet) — flags unverifiable citations before polish
- [x] Contradiction handling in polish — explicit resolve/flag rules
- [x] Thesis recording to Company Mind after save — future memos see prior recommendations
- [x] `analytics.get_metric_trend` tool — research packs can ground claims in time series
- [x] 8 direct `messages.create` call sites migrated to central client (inherit retry)
- [x] Prompt caching extended to tool definitions (~20-30% savings on multi-turn)
- [x] Memo SSE endpoint persists memos (was fire-and-forget) + emits `saved` event with memo_id

**Intelligence System Activation ✅ COMPLETE (session 23):**
- [x] TAPE_INGESTED event now carries real metrics (was `{}` — killed entity extraction, thesis drift)
- [x] DataChat feedback pipeline wired (thumbs-down records to CompanyMind even without correction)
- [x] Graph-aware scoring activated (`query_text` passed to `build_mind_context()` from chat endpoints)
- [x] `entities.jsonl` added to CompanyMind `_FILES` + `_TASK_RELEVANCE`
- [x] Entity extractor overhauled — ~80 patterns across all 7 types (11 entities from real text vs ~1 before)
- [x] Mind seeded for Klaim (18 entries, from legal analysis findings) + Tamara (11 entries, from data room entity extraction). Master Mind 7→26. **Known gap:** SILQ/Aajil/Ejari mind directories not yet created — Health tab flags "Company Mind not populated" (AI context on those companies will be limited until seeded via `/thesis <co>` or a data room ingest).

**Documentation ✅ COMPLETE (session 23):**
- [x] ANALYSIS_FRAMEWORK.md Section 21 (Intelligence System) added
- [x] FRAMEWORK_INDEX.md updated with Aajil + current fn/test counts
- [x] Ejari methodology expanded 2→12 sections
- [x] Klaim methodology — CDR/CCR + Facility-Mode PD registered
- [x] Framework Section 3 — added Ejari/Tamara/Aajil asset class subsections

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
- [x] Portfolio company onboarding flow — `backend/onboarding.py` (validate + create org/product/API key), `Onboarding.jsx` (4-step form), route `/onboard`
- [x] Facility-mode PD — `compute_facility_pd()` Markov chain (DPD bucket transitions, forward PD curve), endpoint `/charts/facility-pd`
- [x] Recovery discounting — `_compute_pv_adjusted_lgd()` discounts recoveries by time-to-recovery (8% annual rate), integrated into `compute_expected_loss()` output as `lgd_pv_adjusted`
**Tamara — P0 ✅ COMPLETE:**
- [x] AI Executive Summary — `_build_tamara_full_context()` (40 context lines), section_guidance, tab_slugs
- [x] Concentration gauges wired to HSBC data + instalment type pie chart added
- [x] Data extraction fixed — 73 KPIs, 136 financials, 5 demographic dims, 51 BP metrics, 152 FM metrics
- [x] Landing page — dual flags (SA+AE), auto-rotating carousel (3.5s crossfade, dot indicators, pause-on-hover)
- [x] Financial Performance trend chart + Business Plan projection chart + Demographics grouped bars
**Intelligence System — Integration ✅ (partial — backend wiring + Operator Center + DataChat):**
- [x] Wire `register_all_listeners()` into backend main.py app startup
- [x] Add thesis API endpoints (GET/POST thesis, drift, log)
- [x] Add briefing API endpoint (GET /operator/briefing)
- [x] Add knowledge search endpoint (GET /knowledge/search)
- [x] Add chat feedback endpoint (POST chat-feedback)
- [x] Wire TAPE_INGESTED/DOCUMENT_INGESTED/MEMO_EDITED events into existing endpoints
- [x] Add Briefing + Learning tabs to OperatorCenter
- [x] Add DataChat thumbs-up/down feedback buttons
- [x] Add Layer 5 (thesis context) to AI prompts — `build_mind_context()` now 5-layer
- [x] Create ThesisTracker.jsx frontend (pillar cards, drift history, edit mode) — 8th OperatorCenter tab
- [x] Enhance build_mind_context() with graph-aware scoring (Phase 1B) — `query_text` param, KnowledgeGraph for Layers 2+4
- [x] Copy 6 new slash commands — /morning, /thesis, /drift, /learn, /emerge, /know
**Research Hub & Memo — Near-term:**
- [x] CSV tape classifier improvement — text-preview rule for loan column headers
- [x] Seed Tamara Company Mind — 11 entries + relations at company level (`data/Tamara/mind/`)
- [ ] Insight extraction integration tests with real investor reports
- [x] Amendment memo template — 9-section `amendment_memo` in templates.py
- [ ] Add framework sections 16-20 to ANALYSIS_FRAMEWORK.md (documenting new systems)
**Tamara — P1 ✅ COMPLETE (session 20):**
- [x] Facility payment waterfall — `facility-waterfall` tab (horizontal bar chart + detail table)
- [x] Dilution time-series by vintage — enhanced dilution tab with vintage line chart
- [x] HSBC trigger trend heatmap — `trigger-trends` tab (CSS grid heatmap)
- [ ] Collections by BB delinquency bucket
- [x] Promote VintageHeatmap and CovenantTriggerCard to shared components
**Tamara — P2 (polish):**
- [ ] AI-powered research report narrative — wire `ai_narrative` to Claude
- [ ] Frontend "Generate Research Report" button
- [ ] Product-level DPD trends (13 products, only aggregate rendered)
- [ ] HSBC stratification rendering (2 of 6 dimensions visualized, need remaining 4)
**Data Room Ingestion — Platform capability ✅ COMPLETE (generalized via Research Hub):**
- [x] Generalized data room ingestion — `core/dataroom/engine.py` ingests any directory of mixed files (PDF, Excel, CSV, JSON, DOCX, ODS), auto-classifies (16 types), chunks for search, builds TF-IDF index. Replaces `prepare_tamara_data.py` proof-of-concept.
- [x] Data room file inventory — `registry.json` catalogs all files (type, size, page count, chunk count, classification)
- [x] PDF table extraction — pluggable parsers in `core/dataroom/parsers/` standardize extraction
- [x] Incremental data room updates — `POST /dataroom/refresh` now defaults to company dataroom dir
**Research Report — Platform capability ✅ MOSTLY COMPLETE (session 20):**
- [x] Company-specific report builders for Ejari, Klaim, SILQ — dedicated builders + dispatch + TOC
- [ ] AI narrative injection for all companies via Claude prompt per analysis_type
- [x] Report template customization — `section_order` + `excluded_sections` params; tape data loaded for report generation
- [ ] Historical report versioning — saved with timestamps, comparison across dates
**Phase 3 (Team & Deployment):**
- [x] Cloud deployment
- [x] Role-based access (RBAC) — Cloudflare Access JWT + admin/viewer roles, user management page
- [ ] Scheduled report delivery
- [ ] Real-time webhook notifications to portfolio companies
- [x] AI-powered legal analysis — ingest facility agreement PDFs, 5-pass Claude extraction (eligibility, advance rates, covenants, concentration limits, EOD, reporting, risk flags), auto-populate facility_configs via 3-tier priority, compliance comparison, 8-tab frontend, 22 tests. **Next:** validate with real Klaim facility agreement + external legal tool comparison
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
