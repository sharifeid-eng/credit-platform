# Current Task Plan
Track active work here. Claude updates this as tasks progress.

---

## Completed — 2026-04-11 (session 8: Landing Page Bug Fixes)
- [x] **Fix `_master_mind` appearing as company card on landing page** — `get_companies()` in `core/loader.py` listed all directories in `data/` without filtering internal directories. Added `not d.startswith('_')` filter so `_master_mind` (fund-level Living Mind storage) is excluded from the company list. Fixes landing page, `/aggregate-stats`, and `/operator/status` (which had its own redundant filter).
- [x] **Fix blank Operator Command Center page** — `OperatorCenter.jsx` silently swallowed API failures (`catch` only logged to console), leaving `status` as `null` and rendering empty content with no user feedback. Added `error` state with red error message and Retry button when the backend is unreachable.

---

## Completed — 2026-04-11 (session 7: Operator Command Center + Weekend Deep Work Protocol)
- [x] **Weekend Deep Work protocol** — `WEEKEND_DEEP_WORK.md` committed to project root. 7 modes: Codebase Health Audit, Test Generation Sprint, Architecture Review, Documentation Sprint, Prompt Optimisation, Red Team Review, Regression Validation. Includes: state-save progress manifest, two-pass file analysis strategy, self-audit validation pass, financial business logic stress tests, tiered frequency schedule.
- [x] **Operator Command Center — backend** — `backend/operator.py` + `core/activity_log.py`:
  - `GET /operator/status`: aggregate company health, tape freshness, legal coverage, mind entries, AI cache, data room, gap detection, command menu
  - `GET/POST/PATCH/DELETE /operator/todo`: persistent follow-up list with company tags, priority (P0/P1/P2), categories
  - `GET/PATCH /operator/mind`: browse all mind entries, promote company→master, archive
  - `POST /operator/digest`: weekly Slack digest
  - `core/activity_log.py`: centralized JSONL logger, importable from any endpoint
- [x] **Operator Command Center — frontend** — `OperatorCenter.jsx` (530 lines):
  - 5-tab dashboard: Health Matrix, Commands, Follow-ups, Activity Log, Mind Review
  - Company health cards with freshness badges, stats grid, gap detection
  - Command menu grid (11 framework + 3 session + 7 deep work)
  - Todo CRUD with priority, category, company tags
  - Mind entry browser with promote-to-master action
- [x] **Frontend wiring** — `/operator` route, "Ops" link in Navbar, Operator Card in Home Resources
- [x] **Activity logging instrumentation** — `log_activity()` wired into 14 endpoints: AI (commentary, exec summary, tab insight, chat), Reports (PDF, compliance cert, memo export), Data (dataroom ingest, facility params), Research (query), Legal (upload, extraction), Mind (record), Alerts (breach notification)
- [x] **`/ops` slash command** — `.claude/commands/ops.md` for terminal operator briefing at session start

---

## Completed — 2026-04-10 (session 6: Legal Analysis — Document Review Follow-up)
- [x] **Account Debtor validation** — Cross-referenced MRPA 13 approved Account Debtors against tape Group column. Finding: CRITICAL DATA GAP — tape has no payer/insurance company column (Group = 143 healthcare providers, not insurance debtors). 10% non-eligible debtor concentration limit unenforceable from tape. Saved to `legal/debtor_validation.json` + Company Mind.
- [x] **Payment schedule storage** — 17-payment schedule ($6M draw, 13% p.a. ACT/360, quarterly profit + bullet maturity) stored in `legal/payment_schedule.json`. Backend reporting endpoint extended. Frontend ReportingCalendar.jsx updated with schedule table (4 KPI cards + 17-row table with PAID/NEXT badges).
- [x] **Consecutive breach history tracking** — `annotate_covenant_eod()` in `core/portfolio.py` classifies EoD status per MMA 18.3: `single_breach_not_eod` (PAR30), `single_breach_is_eod` (PAR60), `two_consecutive_breaches` (Collection/PvD). `covenant_history.json` persists prior periods (max 24). Frontend CovenantCard.jsx shows styled EoD badges.
- [x] **Legal Analysis tabs verified** — All 8 tabs rendering with live data from 4 merged extraction JSONs.
- [x] **Multi-document extraction merge** — Rewrote `load_latest_extraction()` to merge all 4 documents (MMA + MRPA + Fee Letter + Qard). Lists concatenated (deduped), dicts merged (primary wins). Fixed `get_legal_dir()` path resolution (relative → absolute).
- [x] **Legal extraction JSONs committed** — 4 human-reviewed extraction caches (96% confidence, $0 cost) plus 4 source PDFs.

---

## Completed — 2026-04-10 (session 5: Research Hub + Living Mind + Memo Engine)
- [x] **Phase 1: Foundation** — Data Room Engine, Living Mind, Analytics Snapshots, Frontend skeleton
  - `core/dataroom/` (12 files, 3,500 lines) — engine, parsers (PDF/Excel/CSV/JSON/DOCX/ODS), chunker, classifier, analytics_snapshot
  - `core/mind/` (3 files, 1,627 lines) — MasterMind (fund-level), CompanyMind (per-company), build_mind_context() 4-layer injector
  - Frontend: DocumentLibrary.jsx, ResearchChat.jsx, MemoArchive.jsx placeholder
  - Sidebar.jsx: Research section added (3 nav items)
  - App.jsx: 6 research routes added
  - api.js: 4 research API functions
  - Master Mind seeded from CLAUDE.md + ANALYSIS_FRAMEWORK.md
  - Mind context wired into ALL 4 `_build_*_full_context()` functions in main.py
- [x] **Phase 2: Research Intelligence** — Dual-engine queries, NotebookLM integration
  - `core/research/` (6 files, 1,917 lines) — ClaudeQueryEngine, DualResearchEngine, ResearchSynthesizer, NotebookLMEngine, extractors
  - `notebooklm-py` installed and authenticated (9 notebooks detected)
  - `scikit-learn` installed for TF-IDF search
  - 15+ backend endpoints for dataroom, research, mind
- [x] **Phase 3: IC Memo Engine** — Templates, generation, versioning, PDF export
  - `core/memo/` (6 files, 2,797 lines) — templates (4 IC types), analytics_bridge, generator, storage, pdf_export
  - Frontend: MemoBuilder.jsx (4-step wizard), MemoEditor.jsx, MemoArchive.jsx (real data)
  - 10+ memo endpoints in main.py
- [x] **Legal Analysis merge** — Merged `claude/nervous-bardeen` into Research Hub
  - 3 merge conflicts resolved (main.py, App.jsx, api.js)
  - Legal findings seeded into Klaim Company Mind (6 data quality, 4 findings, 2 IC feedback)
  - Legal analysis doc registered in data room (18 chunks, searchable)
  - Master Mind updated with legal methodology preferences
- [x] **Assessment + P0 fixes** — Full audit, scored 5.6→6.9/10 after fixes
  - Registry format conflict fixed (AnalyticsSnapshotEngine → dict format)
  - Directory exclusion added (prevents self-referential ingestion)
  - CSV tape classifier fixed (date-named files → portfolio_tape)
  - sklearn installed for TF-IDF search
- [x] **Documentation finalization**
  - ANALYSIS_FRAMEWORK.md: sections 16-20 (Living Mind, Legal, Data Room, Research Hub, Memos)
  - FRAMEWORK_INDEX.md: 3 new commands, 3 new principles
  - CLAUDE.md: comprehensive updates across all sections
  - .gitignore: dataroom chunks/index, mind JSONL, .notebooklm excluded
- **Total: 27+ new Python modules, 14 React files, ~17,000 lines of new code, 156 tests passing**

---

## Completed — 2026-04-07 (session 4)
- [x] Legal Analysis — third analytical pillar (AI-powered facility agreement analysis)
  - `core/legal_schemas.py` — Pydantic models (FacilityTerms, EligibilityCriterion, AdvanceRate, ConcentrationLimit, FinancialCovenant, EventOfDefault, ReportingRequirement, RiskFlag, LegalExtractionResult)
  - `core/legal_parser.py` — PDF → markdown (pymupdf4llm) + table extraction (pdfplumber) + section chunking
  - `core/legal_extractor.py` — 5-pass Claude extraction (definitions, facility+eligibility+rates, covenants+limits, EOD+reporting+waterfall, risk assessment). ~$1.25/doc, cached forever.
  - `core/legal_compliance.py` — Compliance comparison (doc terms vs live portfolio), 3-tier facility params merge (document → manual → hardcoded), executive summary context builder
  - `core/LEGAL_EXTRACTION_SCHEMA.md` — Extraction taxonomy (7 sections), confidence grading, param mapping
  - `backend/legal.py` — FastAPI router, 12 endpoints (upload, documents, facility-terms, eligibility, covenants-extracted, events-of-default, reporting, risk-flags, compliance-comparison, amendment-diff)
  - `backend/main.py` — legal router included, `_load_facility_params()` updated for 3-tier priority, executive summary wired with legal context
  - `core/portfolio.py` — parameterized `ineligibility_age_days` (was 365) and `cash_ratio_limit` (was 3.0) via `facility_params.get()`
  - `frontend/src/pages/LegalAnalytics.jsx` — main page with AnimatePresence tab transitions
  - 8 tab components in `frontend/src/components/legal/`: DocumentUpload, FacilityTerms, EligibilityView, CovenantComparison, EventsOfDefault, ReportingCalendar, RiskAssessment, AmendmentHistory
  - `frontend/src/components/Sidebar.jsx` — LEGAL_TABS added, Legal Analysis section between Portfolio and Methodology
  - `frontend/src/App.jsx` — legal/:tab routes added
  - `frontend/src/services/api.js` — 12 legal API functions added
  - `tests/test_legal.py` — 22 tests (schemas, mapping, compliance comparison, parser utils), all passing
  - Total: 156 tests pass (134 existing + 22 new)
  - **Next steps:** Upload real Klaim facility agreement → validate extraction → compare against external legal tool via Chrome

---

## Active — Cloud Deployment (Phase 3 Gate)

### Phase 0 — Domain & Provider Setup ✅
- [x] Register domain name — `laithanalytics.ai` via Cloudflare (~$12/yr)
- [x] Create Hetzner Cloud account — CAX21 (4vCPU ARM, 8GB RAM, Helsinki)
- [x] Provision VPS (Ubuntu 24.04) — IP: `204.168.252.26`
- [x] Point domain DNS A record via Cloudflare (proxied, Flexible SSL)

### Phase 1 — Dockerize the Application ✅
- [x] Pin `requirements.txt` versions
- [x] Fix hardcoded `API_BASE` → env-aware (`VITE_API_URL`, undefined check)
- [x] Fix hardcoded CORS origins → env-aware (`CORS_ORIGINS`)
- [x] Fix hardcoded URLs in `generate_report.py` → env-aware
- [x] Create `docker/backend.Dockerfile` (Python 3.12, Playwright + Chromium)
- [x] Create `docker/frontend.Dockerfile` (Node 22 build → Nginx static)
- [x] Create `docker/nginx.conf` (reverse proxy: static + API routes)
- [x] Create `docker-compose.yml` (backend, frontend/nginx, postgres)
- [x] Create `.env.production.example`, `.dockerignore`, `deploy.sh`

### Phase 2 — Server Setup & Deploy ✅
- [x] Install Docker 29.4 + Compose 5.1 on VPS
- [x] Configure UFW firewall (22, 80, 443)
- [x] Clone repo, upload `data/` directory, create `.env.production`
- [x] Build and launch containers — all 3 healthy
- [x] SSL via Cloudflare Flexible mode (no Certbot needed)
- [x] Site live at `https://laithanalytics.ai`

### Phase 3 — Operational Basics
- [ ] Set up daily PostgreSQL backup cron (pg_dump → compressed file)
- [x] Docker restart policies (`restart: unless-stopped`) — already in docker-compose.yml
- [x] Deploy script (`deploy.sh`) — already created
- [ ] Test PDF generation works (Playwright + Chromium inside container)

### Phase 4 — CORS & Security Hardening
- [x] CORS locked to production domain (env-aware, set in docker-compose.yml)
- [ ] Verify `.env` and `data/` are not accessible via web
- [ ] Set `X-API-Key` for integration endpoints
- [ ] Basic rate limiting on AI endpoints

### Decision Log
- **Provider: Hetzner** — best price/performance for single VPS. 4GB ARM at €7/mo vs DigitalOcean $24/mo for comparable specs. EU data center acceptable (no UAE residency requirement confirmed).
- **Architecture: Docker Compose on single VPS** — simplest path for 1-5 users. Nginx as reverse proxy handles SSL termination + static frontend + API routing. All services on one machine.
- **Data strategy:** Loan tapes mounted as Docker volume from host filesystem. Not baked into images. Git tracks the data (it's not sensitive enough to require removal — internal fund data, not PII). If this changes, add `data/` to `.gitignore` and use volume-only.
- **Why not Railway/Render/Fly.io:** These PaaS options are simpler but: (a) Playwright needs custom Docker with Chromium which complicates PaaS, (b) persistent file storage for loan tapes is awkward on ephemeral containers, (c) PostgreSQL add-ons are $15-30/mo alone. VPS is cheaper and gives full control.
- **Upgrade path:** If IC usage grows, the move is: Hetzner VPS → Hetzner Load Balancer + 2 VPS nodes + Managed PostgreSQL. Same Docker images, just orchestrated differently.

---

## Completed — 2026-04-07 (session 3)
- [x] AI response caching — file-based disk cache (`reports/ai_cache/`) for executive summary (~$0.48/call), commentary (~$0.06/call), and tab insights (~$0.02/call x 18 tabs). Cache key: `(endpoint, company, product, snapshot)`. One AI call per tape lifetime, served instantly to all users thereafter.
- [x] Cache key normalization — `as_of_date` normalized: None, snapshot_date, and future dates all map to same key. Currency excluded (only affects numeric display, not analytical findings).
- [x] `?refresh=true` parameter on all 3 AI endpoints for force-regeneration
- [x] Frontend cache awareness — `CACHED` badges on AICommentary, TabInsight, ExecutiveSummary. Regenerate buttons for force-refresh. `getAICacheStatus` API function.
- [x] Backdated view data integrity — `filter_by_date()` only filters deal selection, not balance columns. When `as_of_date < snapshot_date`:
  - Backend: AI endpoints return HTTP 400 (misleading data)
  - Frontend: KpiCard shows `TAPE DATE` badge with dimmed value (50% opacity)
  - BackdatedBanner classifies metrics as ACCURATE vs TAPE DATE
  - AICommentary, TabInsight, ExecutiveSummary disabled with explanation
  - All 18 Klaim + 11 SILQ ChartTabs pass `isBackdated` to TabInsight
- [x] ANALYSIS_FRAMEWORK.md Section 15 — As-of-Date Filtering & Data Integrity (metric classification table, enforcement rules)
- [x] lessons.md — root cause analysis of as_of_date limitation with prevention rules

## Completed — 2026-04-07 (session 2)
- [x] Fix SILQ Face Value blank on landing page — `compute_silq_summary()` returned `total_disbursed` but frontend expected `total_purchase_value`. Added `total_purchase_value` alias mapped to `total_disbursed`. Same pattern now consistent across Klaim, Ejari, SILQ.
- [x] Removed tracked `backend/__pycache__/main.cpython-314.pyc` from git

## Completed — 2026-04-07 (session 1)
- [x] Living Methodology system — auto-generated from backend metadata
  - `core/metric_registry.py` — decorator registry + `get_methodology()` + `get_registry()`
  - `core/methodology_klaim.py` — 16 sections, 29 metrics, 13 tables (all Klaim methodology content)
  - `core/methodology_silq.py` — 15 sections, 23 metrics, 2 tables (all SILQ methodology content)
  - `data/Ejari/RNPL/methodology.json` — static Ejari methodology
  - `GET /methodology/{analysis_type}` + `GET /methodology-registry` — new API endpoints
  - `frontend/src/pages/Methodology.jsx` rewritten: 1301 → 290 lines (data-driven from API)
  - `frontend/src/services/api.js` — added `getMethodology()` export
  - `scripts/sync_framework_registry.py` — auto-generates Section 12 in ANALYSIS_FRAMEWORK.md
  - Section 12 now auto-generated from the metric registry (no more manual tables)

---

## Completed — 2026-04-06
- [x] Framework-as-Brain system — 7 slash commands + framework expansion + hooks + memory
  - `/onboard-company` — full 6-phase onboarding (discovery, data inspection, config, backend, frontend, verification)
  - `/add-tape` — validate new tape, column compatibility, cross-tape consistency, feature impact
  - `/validate-tape` — comprehensive data quality with A-F grading, framework-aligned checks
  - `/framework-audit` — audit all companies: L1-L5 coverage, denominator discipline, separation principle, tests
  - `/extend-framework` — propagate new metrics across all layers (doc → backend → frontend → methodology → tests)
  - `/methodology-sync` — detect drift between Methodology.jsx and backend compute functions
  - `/company-health` — quick diagnostic with health cards, coverage, freshness, gaps
  - `core/ANALYSIS_FRAMEWORK.md` expanded: Compute Function Registry (Sec 12), Column-to-Feature Map (Sec 13), Decision Tree (Sec 14)
  - `core/FRAMEWORK_INDEX.md` — quick reference index for sessions
  - `.claude/hooks/` — auto-reminders: analysis module edits → methodology-sync, new data files → add-tape, session start → command list
  - `.claude/settings.json` — hooks configuration (FileChanged + SessionStart events)
  - CLAUDE.md updated: "Analysis Framework Authority" workflow rule, command table, project structure
  - Memory notes saved: framework-as-brain intent, user profile, full-scope delivery preference

---

## Completed — 2026-04-05
- [x] Ejari dashboard formatting aligned with Klaim/SILQ — replaced local `Kpi` with shared `KpiCard` (Framer Motion stagger, hover lift/shadow, gradient glow, 22px values, subtitles), replaced local `Panel` with `ChartPanel`, added `AnimatePresence` tab transitions, "Credit Quality" section header. DataTable kept as-is. Deleted unused local `Kpi` and `Panel` functions.
- [x] LandingCanvas.jsx deleted — removed file, import, `hoveredCompany` state, and `onHoverChange` prop from Home.jsx/CompanyCard. CLAUDE.md updated.
- [x] Banner 1 expanded to 5 stats — added Deals Processed + Data Points (rows×cols); renamed Records Processed → Deals Processed
- [x] `/aggregate-stats` backend improvements:
  - `load_silq_snapshot` used for SILQ tapes (was using `load_snapshot`, silently failing)
  - Tuple unpacking fixed: `df, _ = load_silq_snapshot(...)` (returns tuple, not just df)
  - Ejari included: ODS parsed for `total_contracts` (deals) + rows×cols across all sheets (data points)
  - Ejari face value (`total_funded`) now included in aggregate face value total
  - Schema version `"3"→"4"` in cache fingerprint — busts cache automatically on field changes
- [x] Data Points format: 1162K+ → 1.2M+ (divided by 1M instead of 1K)
- [x] Company card two-row layout:
  - Row 1 Tape Analytics: Face Value | Deals | Since (earliest snapshot date)
  - Row 2 Live Portfolio: Borr. Base | PAR 30+ | Covenants (all `—` until DB connected)
  - `/companies` API extended with `since` field (earliest snapshot date)
  - `CardRow`, `CardStat`, `CardDivider` sub-components added
- [x] Ejari company card data fix (root cause: ODS comma-formatted strings) — `int('1,348')` threw ValueError caught silently. Fixed with `.replace(',', '')` before int/float conversion in both `/summary` and `/aggregate-stats`. Card now shows $13M / 1,348 deals.
- [x] `/eod` slash command — 11-step end-of-session checklist: inventory, tests, .env check, cache cleanup, todo/lessons/CLAUDE.md update, commit, push, sync feature branch, verify. Stored in `.claude/commands/eod.md`, tracked in git.
- [x] Playwright MCP exploration — added then removed `.mcp.json`. Root cause: session started from mobile (cloud sandbox), not desktop app. Chrome extension only works from desktop app on same machine. Lesson documented.

---

## Completed — 2026-04-04 (previous session)
- [x] Typography overhaul — Syne 800 (display/hero), Space Grotesk 400-700 (UI), JetBrains Mono (data). Single load point in index.html. All 55+ IBM Plex Mono / Inter references replaced with CSS tokens.
- [x] Islamic geometric background — SVG stroke widths tuned to be visible (1.0 lines, 1.6 star, 2.2 dots), opacity 14%, backgroundSize 140px.
- [x] Navbar enlarged 50% — height 56→80px, lion 36→54px, LAITH wordmark 22→33px. Syne font applied to wordmark. "Data Analytics" label 10→15px.
- [x] Section labels enlarged — "Portfolio Companies" and "Resources" 9→13px.
- [x] Per-company DataChat questions — `PROMPTS` map in DataChat.jsx keyed by `analysisType` (`silq`, `ejari_summary`, `default`). Relevant questions for each asset class.
- [x] Flag rendering fix — emoji flags (🇦🇪, 🇸🇦) don't render on Windows Chrome. Switched to flagcdn.com `<img>` tags using ISO country codes.
- [x] Collection rate bug fix — `summary.collection_rate` was already a percentage; multiplying ×100 showed 8500%. Fixed in CompanyCard and PortfolioStatsHero.
- [x] LandingCanvas removed from landing page — performance vs. complexity trade-off; geometric pattern provides ambient texture without JS overhead.
- [x] Two-banner stats strip — `PortfolioStatsHero.jsx` rebuilt as two stacked banners:
  - Banner 1 "Data Analyzed" (gold tint): live from `/aggregate-stats` — Face Value Analyzed, Records Processed, Snapshots Loaded, Portfolio Companies. Cached by snapshot fingerprint.
  - Banner 2 "Live Portfolio" (neutral): Active Exposure, PAR 30+, PAR 90+, Covenants in Breach, HHI — all `—` until real DB data connected.
  - `useCountUp` hook with ease-out expo animation; `Skeleton` shimmer during load.
- [x] `/aggregate-stats` backend endpoint — face value from latest snapshot only (no double-counting), total records from all snapshots, FX-normalised to USD (AED×0.2723, SAR×0.2667). File-based cache invalidated by snapshot fingerprint.

---

## Creative UI Redesign — Landing Page & Company Pages
**Status: COMPLETE — all phases + data-wiring done**

### Data-wiring (both complete)
- [x] **P4.1 — KPI delta indicators**: Previous snapshot summary fetched, δcoll / δdenial / δactive computed, passed as `trend` prop to Collection Rate, Denial Rate, Active Deals KPI cards.
- [x] **P4.4 — Sparkline data**: Collection velocity + deployment chart fetched in OverviewTab; last 6 monthly values extracted; passed as `sparklineData` to Purchase Value (deployment totals) and Collection Rate (monthly rate) KPI cards.
**Branch:** `claude/creative-landing-page-research-5hdf6`
**Goal:** Transform the landing page from a generic card grid into an institutional, MENA-identity-driven experience. Elevate company pages with richer data density and interaction.

### Phase 1 — Quick Wins: Landing Page Identity (no new libraries)

- [x] **P1.1 — Islamic geometric background pattern**
  - Create `frontend/public/geometric-pattern.svg` — a Girih/Mashrabiya tile pattern using gold (`#C9A84C`) on transparent, seamlessly tileable (~120px tile), 8-point star geometry
  - Apply as CSS `background-image` on Home.jsx at 4–5% opacity (zero runtime cost — pure SVG + CSS)

- [x] **P1.2 — Display serif font for hero text**
  - Add Playfair Display (Google Fonts) to `frontend/index.html` — weights 400, 700
  - Add `--font-display: 'Playfair Display', Georgia, serif;` to `styles/tokens.css`
  - In Home.jsx, add hero headline above company grid: *"Institutional Credit Analytics"* in display serif, 48–56px, gold gradient text
  - Subtitle in Inter: *"Private credit portfolio intelligence for MENA asset-backed lending"*

- [x] **P1.3 — Aggregate portfolio stats hero strip**
  - New component `frontend/src/components/PortfolioStatsHero.jsx`
  - Fetches per-company `/summary` on mount, aggregates: Total Deployed, Weighted Collection Rate, Total Active Deals
  - Custom `useCountUp(target, duration)` hook using `requestAnimationFrame` (no library)
  - Layout: dark strip with gold top/bottom border lines, mono font stats, small-caps labels
  - Positioned between Navbar and the company grid

- [x] **P1.4 — Country/region identity on company cards**
  - Add country flag emoji + region label to CompanyCard (AED→🇦🇪 UAE, SAR→🇸🇦 KSA, USD→check config)
  - Add asset class label in small caps: "Healthcare Receivables", "POS Lending", "Rent Finance"
  - Show one headline metric prominently (collection rate % from summary endpoint)
  - Taller cards (min-height: 200px), more breathing room, less decoration

### Phase 2 — Cinematic Entrance & Card Elevation

- [x] **P2.1 — Hero typewriter effect**
  - `useTypewriter(text, speed)` hook — types subtitle character by character on load
  - Blinking cursor that fades after typing completes
  - Respects `prefers-reduced-motion` (shows full text instantly if reduced motion preferred)

- [x] **P2.2 — Logo draw-on entrance animation**
  - Landing page standalone logo: lion icon scale-pulse (CSS keyframe 0.3s)
  - "L"+"TH" fade in (0.2s) → "AI" gold glow (0.2s delay) — sequential reveal
  - Subtitle typewriter starts after logo sequence completes

- [x] **P2.3 — Company cards enhanced stagger + 3D hover**
  - Increase stagger to 80ms for more dramatic cascade
  - Add `rotateX: 2` + CSS `perspective: 800px` on hover for subtle 3D tilt
  - Gradient top border animates width 0%→100% on first appearance (not just hover)

### Phase 3 — Animated Canvas Background

- [x] **P3.1 — Canvas network animation**
  - New `frontend/src/components/LandingCanvas.jsx` — fixed `<canvas>` behind content (z-index: 0)
  - Pure Canvas API (no Three.js — keeps bundle lean):
    - Company nodes: larger, gold, pulsing sine-wave radius
    - Deal nodes: ~15 small, muted teal, Brownian drift with boundary bounce
    - Connecting lines: gold→teal gradient stroke at ~15% opacity, proximity-threshold based
  - 30fps throttled via `requestAnimationFrame` + frame counter
  - Pauses on hidden tab (`visibilityState`), resizes on window resize (debounced), cleanup on unmount

- [x] **P3.2 — Canvas ↔ card hover connection**
  - Shared `hoveredCompany` state: CompanyCard sets it on hover, LandingCanvas reads it
  - Hovered company's node glows brighter + emits expanding pulse ring (opacity fade-out)

### Phase 4 — Company Page Enhancements

- [x] **P4.1 — KPI card delta indicators**
  - Add optional `delta` + `deltaLabel` props to `KpiCard.jsx`
  - Render small pill below value: green ▲ / red ▼ with delta amount
  - Populate on Klaim Overview for: collection rate, active deals, total deployed (vs prior snapshot)
  - Frontend diff: call `/summary` for current + previous snapshot, compute deltas

- [x] **P4.2 — Sidebar active state animation**
  - Active left border: animate in via Framer Motion `scaleY` 0→1 (origin top, 150ms)
  - Active item: subtle gold gradient sweep left→right (5%→0% opacity background)
  - Hover: `translateX: 2px` micro-indent on non-active items

- [x] **P4.3 — Tab transition enhancement**
  - Add `filter: blur(4px)→blur(0)` on entering tab content
  - Increase y offset 8→12 for more cinematic feel
  - Switch from linear to `easeOut` spring easing

- [x] **P4.4 — Inline sparklines on KPI cards (stretch)**
  - New optional `sparklineData` prop on KpiCard — array of 6 values
  - Render as 40×20px inline SVG `<polyline>` with gold stroke, no axes
  - Populate on Overview KPIs that have natural time-series: collection rate, deployment volume
  - Data: last 6 points from existing chart endpoint arrays (pass through from TapeAnalytics)

### Phase 5 — Polish & Integration

- [x] **P5.1 — Dark mode consistency + performance pass**
  - Audit new components for hardcoded colors, replace with CSS tokens
  - Canvas: test on throttled CPU (Chrome DevTools); confirm no scroll jank
  - Adjust pattern opacity if needed for different brightness levels

- [x] **P5.2 — Responsive + accessibility**
  - Mobile breakpoints for hero strip, card redesign
  - Canvas disabled on mobile (`max-width: 768px`) — too battery intensive
  - Typewriter + entrance animations respect `prefers-reduced-motion`

- [x] **P5.3 — Commit, push, update CLAUDE.md**
  - Commit all to `claude/creative-landing-page-research-5hdf6`
  - Push to remote
  - Update CLAUDE.md: new components in structure, design decisions documented

---

## Completed — 2026-04-09 (session 2 — continued)
- [x] **Loader fix: exclude config.json and methodology.json from snapshot discovery** — adding `.json` extension support for Tamara also matched non-data JSON files, causing 404 on `/summary` endpoint. Added `_EXCLUDE` set in `get_snapshots()`.
- [x] **Tamara metric labeling fix** — `total_purchase_value` is outstanding AR (not originated), `total_deals` was vintage count (14) not real count. Fixed: `face_value_label`/`deals_label` fields passed through `/summary` endpoint; card shows "Outstanding AR" and "Reports" for Tamara. Aggregate stats no longer mix Tamara outstanding into "Face Value Analyzed" ($665M -> $308M). Schema version bumped to "5".
- [x] **SILQ Mar 2026 tape validated** — 2026-03-31_KSA.xlsx: 2,514 rows (+297 from Feb), SAR 449M disbursed (+64M), 3 product types (BNPL 1295, RCL 1211, RBF 8), 0 critical issues, 68 tests passing.

## Completed — 2026-04-09 (session 2)
- [x] **Tamara BNPL onboarded** — Saudi Arabia's first fintech unicorn ($1B valuation, 20M+ users, 87K+ merchants)
  - Data room ingestion pipeline: `scripts/prepare_tamara_data.py` reads ~100 source files (vintage cohort matrices, Deloitte FDD, HSBC investor reports, financial models, demographics) from OneDrive data room → structured JSON snapshots
  - Two products: KSA (SAR, 14 tabs) and UAE (AED, 10 tabs)
  - `analysis_type: "tamara_summary"` — third data ingestion pattern (ETL → JSON → parser)
  - Novel visualizations: VintageHeatmap (CSS-grid vintage × MOB matrix), CovenantTriggerCard (3-level L1/L2/L3 zones), ConcentrationGauge
  - `TamaraDashboard.jsx` (821 lines): Overview, Vintage Performance, Delinquency, Default Analysis, Dilution, Collections, Concentration, Covenant Compliance, Facility Structure, Demographics, Financial Performance, Business Plan, BNPL+ Deep Dive, Data Notes
  - `core/analysis_tamara.py`: JSON parser + enrichment (covenant status, heatmap colors, DPD summary)
  - Backend: `/tamara-summary` endpoint + `tamara_summary` branches in 7 existing endpoints + `/research-report` endpoint
  - 16 files changed, 34,522 insertions, 134 tests passing
- [x] **Credit Research Report — platform capability** (not per-company script)
  - `core/research_report.py`: generates professional dark-themed PDF credit research reports for ANY company
  - `POST /companies/{co}/products/{prod}/research-report` endpoint
  - 8-section Tamara report: Executive Summary, Company Overview, Portfolio Analytics, Vintage Cohort Performance, Covenant Compliance, Facility Structure, DPD Analysis, Data Sources
  - Extensible: generic fallback for non-Tamara companies, `ai_narrative` parameter for Claude-powered narrative
  - Laith dark theme branding (navy, gold, teal/red, ReportLab Platypus)
- [x] **Three data ingestion patterns formalized:**
  - Raw Tape (Klaim, SILQ): CSV/Excel → live computation per request
  - Pre-computed Summary (Ejari): Single ODS → parse once, render
  - Data Room Ingestion (Tamara): ~100 multi-format files → ETL script → JSON → parser → dashboard

## Completed — 2026-04-09 (session 1)
- [x] Mobile responsiveness — comprehensive overhaul across 29 files (2 new, 27 modified):
  - `useBreakpoint` hook — `{ isMobile, isTablet, isDesktop }` via matchMedia listeners
  - `MobileMenuContext` — sidebar drawer state coordination (open/close/toggle), route-change auto-close, body scroll lock
  - Sidebar: 240px fixed → slide-in drawer on mobile with dark backdrop overlay + close button
  - Navbar: 80px → 56px on mobile, hamburger menu on company pages, hide Framework/Live/v0.5 chips, smaller logo
  - All KPI grids converted to responsive auto-fill/auto-fit with minmax breakpoints
  - All 2-column layouts → `repeat(auto-fit, minmax(280px, 1fr))` — stacks on mobile
  - PortfolioStatsHero: gap 56px → 12px, scaled-down values, hidden empty Live Portfolio banner
  - Padding reduced 28px → 14px on all pages for mobile
  - Framework/Methodology sidebar TOC hidden on mobile
  - ChartPanel: added overflowX auto for wide tables
  - CSS tokens: `--navbar-height` responsive var, table scroll override
  - Build verified, all desktop layouts preserved

## Completed — 2026-04-02
- [x] Executive Summary holistic narrative — single AI call now produces a credit memo-style narrative (company-specific sections with conclusions + metric pills) AND a summary table AND a bottom line verdict, displayed above the existing ranked findings. Ejari gets 9 sections (Portfolio Overview → Write-offs & Fraud), Klaim 7, SILQ 6. max_tokens 2000→8000.

## Up Next
**Tamara — P0 Critical ✅ COMPLETE:**
- [x] **AI Executive Summary context** — `_build_tamara_full_context()` implemented (40 context lines), `tamara_summary` branch + section_guidance + tab_slugs added
- [x] **Concentration gauge wiring** — HSBC concentration_limits data wired to gauges, instalment type pie chart added
- [x] **Empty data sections fixed** — column-offset bug (labels col 1 not col 0), demographics pivot, Financial Master filename. Now: 73 KPIs, 136 financials, 5 demographic dims, 51 business plan metrics, 152 financial master metrics
- [x] **Landing page carousel** — dual flags (SA+AE), auto-rotating product stats every 3.5s with crossfade, dot indicators, pause-on-hover

**Tamara — P1 Showcase Visualizations ✅ MOSTLY COMPLETE:**
- [x] **Financial Performance trend lines** — GMV/Revenue ComposedChart added above KPI tables
- [x] **Business Plan projection chart** — GMV/Revenue/EBTDA chart with bars + lines above detail table
- [x] **Demographics grouped bars** — dimension selector + ComposedChart (AR bars + Ever-90 rate line overlay)
- [ ] **Facility payment waterfall** — create `FacilityWaterfall` component: 17-step horizontal waterfall showing cash flow from collections through senior/mezz/junior tranches (26 waterfall steps available in Oct HSBC report)
- [ ] **Dilution time-series** — replace single-value bar with vintage timeline showing dilution progression per cohort
- [ ] **Collections buyer breakdown** — replace pending/writeoff trend with BB amounts by delinquency bucket from HSBC reports
- [ ] **HSBC trigger trend heatmap** — 6 metrics × 10 months showing which covenants are tightening/loosening
- [ ] **HSBC stratification rendering** — render all 6 stratification dimensions (only merchant category shown; Instalments, Obligors, Pending Amount Buckets, Outstanding Balance repeat/non-repeat all unused)

**Tamara — P2 Polish & Completeness:**
- [ ] AI-powered research report — wire `ai_narrative` parameter to Claude API for narrative sections
- [ ] Frontend "Generate Research Report" button on TamaraDashboard
- [ ] Promote VintageHeatmap and CovenantTriggerCard to shared components
- [ ] BNPL+ deep dive enrichment — parse Question 5 PDFs (Nov 2025 BNPL+ data)
- [ ] Financial Master parsing — fix path for 66-sheet management accounts
- [ ] Product-level DPD trends — 13 products available in Deloitte FDD but dashboard shows portfolio aggregate only
- [ ] Daily DPD7 visualization — parsed but not consumed by any tab
- [ ] Historical covenant evolution — 10 monthly snapshots of compliance but only latest rendered
- [ ] Extract component files from TamaraDashboard — VintageHeatmap, CovenantTriggerCard, ConcentrationGauge currently inlined (821 lines in one file)

**Data Room Ingestion — Platform capability:**
- [ ] **Data room ingestion tool / command** — generalize the Tamara ETL pattern into a platform-level `/ingest-data-room` command. Given a folder path with mixed files (PDFs, Excel, DOCX), automatically detect file types, parse tabular data, extract key metrics, and produce a structured JSON snapshot. The prepare_tamara_data.py script is the proof-of-concept; the generalized version would handle any new company's data room with minimal custom code.
- [ ] Data room file inventory — auto-discover and catalog all files in a data room folder (type, size, sheet count, date), present to analyst for review before parsing
- [ ] PDF table extraction library — standardize pdfplumber table extraction patterns across investor reports, compliance certs, facility agreements
- [ ] Incremental data room updates — detect new/changed files and re-parse only those, merging into existing JSON snapshot

**Research Report — Platform capability expansion:**
- [ ] Company-specific report builders for Ejari, Klaim, SILQ (currently only Tamara has a rich builder; others use the generic fallback)
- [ ] AI-powered narrative for all companies — common `_build_full_context()` pattern per analysis_type → Claude prompt → narrative sections injected into PDF
- [ ] Report template customization — allow analyst to select which sections to include, add custom commentary sections
- [ ] Historical report versioning — save generated reports with timestamps, allow comparison of reports across dates

**Phase 3 — Team & Deployment:**
- [x] Cloud deployment (Phase 3 gate) — live at laithanalytics.ai
- [ ] Role-based access (RBAC) — analyst vs IC vs read-only
- [ ] Scheduled report delivery — automated PDF reports on cadence
- [ ] Real-time webhook notifications to portfolio companies

**Portfolio Analytics — Remaining enhancements:**
- [ ] Portfolio company onboarding flow (self-service API key provisioning)
- [ ] Facility-mode PD — probability of aging into ineligibility (not just credit default)
- [ ] Recovery discounting — PV-adjusted LGD using discount rate

**AI-powered features:**
- [ ] AI covenant extraction — ingest facility agreement PDFs → auto-populate facility_configs

## Completed — 2026-04-01
- [x] Fix PAR KPI card sizing inconsistency — PAR 30+ subtitle was longer than PAR 60+/90+, causing uneven heights. Standardized all to `{ccy} {amount}K at risk`
- [x] Fix dynamic grid reflow — PAR+DTFC grid used async-derived column count, causing layout shift when DTFC loaded. Fixed to `repeat(5, 1fr)`
- [x] Standardize Overview page structure across all companies — consistent sections: Main KPIs (L1/L2) → Credit Quality (L3, PAR cards) → Leading Indicators (L5, DTFC). Applied to Klaim, SILQ, Ejari
- [x] SILQ Overview refactor — extracted PAR30/PAR90 from inline KPIs into dedicated Credit Quality section with 3 individual cards. Added Overdue Rate and Completed Loans to main grid
- [x] Renamed Klaim sections — "Portfolio at Risk" → "Credit Quality", separated DTFC into "Leading Indicators" section
- [x] Added "Credit Quality" section header to Ejari Dashboard PAR cards
- [x] Added AI Executive Summary to Ejari — `_build_ejari_full_context()` builds 20 context lines from ODS workbook. Endpoint now handles `ejari_summary` analysis type
- [x] Decoupled Executive Summary from `hide_portfolio_tabs` — now always visible in sidebar

## Completed — 2026-03-31 (session 4)
- [x] CDR/CCR tab — `compute_cdr_ccr()` (Klaim) + `compute_silq_cdr_ccr()` (SILQ); annualizes cumulative rates by vintage age to strip out maturity effects; 4 KPI tiles, dual-line CDR/CCR chart, net spread line with per-point color; new tab for both Klaim (19th) and SILQ (13th)

---

## Completed — 2026-03-31 (session 3)
- [x] BB Breakeven analysis — eligible cushion + stress % added to borrowing-base endpoint as `analytics.breakeven`; rendered in two-column panel in BorrowingBase.jsx
- [x] BB Sensitivity formulas — ∂BB/∂advance_rate per 1pp and ∂BB/∂ineligible per 1M added as `analytics.sensitivity`; rendered alongside breakeven panel
- [x] Compliance Certificate (BBC PDF) — `core/compliance_cert.py` with ReportLab dark-themed PDF (facility summary, waterfall, concentration limits, covenants, officer cert block); `POST .../portfolio/compliance-cert` streams the PDF; "Download BBC" button in BorrowingBase.jsx
- [x] Breach Notification System (Slack) — `POST .../portfolio/notify-breaches` sends Slack block message; webhook URL field added to FacilityParamsPanel Notifications section; "Notify" bell button in Covenants header with send/sent/error states

---

## Completed — 2026-03-31 (session 2)
- [x] BB Movement Attribution waterfall — period-over-period decomposition of BB drivers
  - Backend: loads previous snapshot, diffs total A/R, eligibility, concentration+rate, cash
  - Frontend BorrowingBase: new "Movement Attribution" panel with signed delta rows + mini diverging bars
- [x] Validation anomaly detection — 5 new checks (9–13)
  - Duplicate counterparty+amount+date combos
  - Identical amount concentration (>5% of deals at same value)
  - Deal size outliers (3×IQR fence)
  - Discount outliers (3×IQR fence, valid range only)
  - Balance identity violations (collected+denied+pending > 105% PV)
- [x] Confidence grading badges A/B/C on KPI cards
  - KpiCard: new `confidence` prop renders teal/gold/muted pill badge at bottom-right with hover tooltip
  - Klaim Overview KPIs: A for direct tape reads, B for DSO/PAR primary/DTFC curve-based, C for PAR derived/DTFC estimated
- [x] Klaim Methodology expansion
  - New sections: PAR (dual denominator, 3 methods, thresholds), Loss Waterfall (default definition, categorization, recovery), Forward-Looking Signals (DTFC, HHI time series, DSO dual perspectives), Advanced Analytics (collections timing, underwriting drift, segment analysis, seasonality)
  - Updated Data Quality Validation: added Anomaly Detection subsection documenting all 5 new checks

## Completed — 2026-03-31 (session 1)
- [x] Covenants: trigger distance + projected breach date
  - Backend: covenants endpoint loads previous snapshot, computes rate-of-change, adds `previous_value` + `days_since_previous` per covenant
  - Frontend CovenantCard: headroom line (teal ✓) when compliant, projected breach date (amber ⚠) when trend moving toward limit, ↘/↗ direction vs prior snapshot
- [x] Confirmed facility params input UI already complete (FacilityParamsPanel.jsx + backend endpoints)
- [x] Cleaned up stale claude/ branches on GitHub (epic-liskov, friendly-beaver, pedantic-swirles, silly-mestorf, zen-moore, condescending-bose) — all fully merged into main

## Completed — 2026-03-28
- [x] SILQ product name cleanup — remove all references to RBF_Exc, RBF_NE, old sheet names
- [x] Update Methodology.jsx with BNPL/RBF/RCL product definitions
- [x] All 59 SILQ tests passing with new product names
- [x] Workflow rules added to CLAUDE.md (planning, execution, verification, self-improvement)
- [x] tasks/lessons.md and tasks/todo.md created for persistent tracking
- [x] Methodology onboarding guide — Section 11 in ANALYSIS_FRAMEWORK.md, hierarchy-level badges in Methodology.jsx TOC, checklist in CLAUDE.md
- [x] ABL-grade framework expansion — 5 new sections in ANALYSIS_FRAMEWORK.md
- [x] CLAUDE.md roadmap updated with tiered enhancement items from ABL manual + industry research
