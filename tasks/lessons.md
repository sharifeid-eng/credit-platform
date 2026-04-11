# Lessons Learned
Persistent log of mistakes and patterns. Claude reviews this at session start to avoid repeat errors.

---

## 2026-04-11 — Internal directories in `data/` must be filtered at the source
**Issue:** `_master_mind` directory lives under `data/` alongside real company directories. `get_companies()` returned it as a company, causing a ghost card on the landing page. The `operator.py` endpoint had its own `startswith("_")` filter, but `main.py`'s `/companies` and `/aggregate-stats` endpoints did not — fix at the source (`get_companies()`) rather than adding filters in every caller.
**Rule:** When a utility function like `get_companies()` returns data consumed by multiple callers, fix the function itself rather than patching each consumer. Defensive filters in callers are OK as belt-and-suspenders but should not be the primary fix.

## 2026-04-11 — Always add error states to pages that fetch data on mount
**Issue:** `OperatorCenter.jsx` fetched from `/operator/status` on mount, but only had a loading state — no error state. When the API was unreachable, the page rendered blank with no feedback. User sees nothing and can't diagnose the problem.
**Rule:** Every page/component that fetches data on mount needs three states: loading, error, and success. The error state should show what went wrong and offer a retry action. Never silently swallow API errors in a catch block that only logs to console.

---

## 2026-04-11 — EOD MUST merge feature branch into main before pushing
**Mistake:** `/eod` Step 9 says "push to main" but when work was done on a feature branch (`claude/prepare-context-DToUt`), I pushed to the feature branch instead and rationalized skipping the merge. The deploy script pulls `main` — so the code never reached production.
**Rule:** EOD Step 9 is non-negotiable: if on a feature branch, `git checkout main && git merge <branch> --no-edit && git push origin main`. The `/eod` command has been updated to make this explicit. Never skip this step regardless of what the session task instructions say about which branch to develop on.

---

## 2026-04-11 — Always verify requirements.txt matches local venv after adding new packages
**Mistake:** `python-multipart` was installed locally in session 4 (needed by `UploadFile` in `backend/legal.py`) but never added to `backend/requirements.txt`. The Docker container crashed on startup because the package was missing. The site was down and it wasn't caught for multiple sessions.
**Rule:** After any session that adds a new Python import, check `backend/requirements.txt` before EOD. A quick verification: `grep -r "^from\|^import" backend/ core/ | grep -v __pycache__ | sort -u` vs contents of requirements.txt. Also: the `/eod` function should eventually include a "verify Docker builds" step.

---

## 2026-04-11 — .gitignore blocks `.claude/` — use `git add -f` for slash commands
**Issue:** `.claude/` directory is in `.gitignore` (likely from a default template). When trying to `git add .claude/commands/ops.md`, git silently ignores it. Must use `git add -f .claude/commands/ops.md` to force-add individual files.
**Rule:** When adding new slash commands to `.claude/commands/`, always use `git add -f`.

---

## 2026-04-11 — Place log_activity() calls BEFORE the return statement, not after
**Mistake:** When adding `log_activity()` to the breach notification endpoint, the call was placed after the `return {...}` statement, making it unreachable dead code.
**Rule:** When instrumenting endpoints with logging, always place the log call before the return. If the return builds a dict inline, either: (1) assign to a variable first, log, then return, or (2) place the log call on the line before `return {`.

---

## 2026-04-11 — Operator state reads from existing files, no new infrastructure needed
**Design decision:** The Operator Command Center (`/operator/status`) reads from files that already exist (config.json, registry.json, mind/*.jsonl, legal/*_extracted.json, reports/ai_cache/) rather than introducing a new database or state system. Gap detection uses heuristic rules against these existing files. This keeps the system simple and avoids migration costs. Personal follow-ups are stored separately in `tasks/operator_todo.json` (not tasks/todo.md which is Claude's session scratch space).

---

## 2026-04-10 — Multi-document extraction must merge, not pick latest
**Mistake:** `load_latest_extraction()` picked the single document with the latest `extracted_at` timestamp. When all 4 Klaim documents had the same timestamp, it alphabetically chose "Fee letter" — returning 0 covenants, 0 reporting, 0 EODs (all the substance is in the MMA/MRPA).
**Rule:** For multi-document facilities, always merge all extractions. Lists (covenants, EODs, reporting) are concatenated and deduped by name. Dicts (facility_terms) are merged with primary credit_agreement winning on conflict. Track `source_documents` array for provenance.

---

## 2026-04-10 — Relative paths in core/ modules break when backend runs from subdirectory
**Mistake:** `get_legal_dir()` used `os.path.join('data', company, product, 'legal')` — a relative path. When uvicorn runs from `backend/`, this resolved to `backend/data/klaim/...` which doesn't exist. The function returned an empty list, making all Legal Analysis tabs show "no documents".
**Rule:** All path construction in `core/` modules must use `os.path.dirname(os.path.abspath(__file__))` to anchor to the project root, matching the pattern established in `core/loader.py`. Never use bare relative paths like `os.path.join('data', ...)`.

---

## 2026-04-10 — Tape columns represent sellers, not payers (Klaim)
**Lesson:** The `Group` column in Klaim tapes contains healthcare provider names (143 sellers), NOT insurance company names (payers/Account Debtors). The MRPA lists 13 approved Account Debtors (insurance companies), but the tape has no column to identify which insurer owes on each deal. This means the 10% non-eligible debtor concentration limit cannot be monitored from tape data alone. Recommendation: request a payer column in future tape exports.

---

## 2026-04-10 — Registry format must be consistent across all engines writing to the same file
**Mistake:** `AnalyticsSnapshotEngine` wrote `registry.json` as `list[dict]` while `DataRoomEngine` expected `dict[str, dict]`. Running both on the same company corrupted the registry — all DataRoomEngine operations (catalog, search, stats) crashed with `AttributeError: 'list' object has no attribute 'items'`.
**Rule:** When multiple modules read/write the same file, they MUST use the same schema. Either: (1) share a common `_load_registry`/`_save_registry`, (2) add a migration path in the reader (handle both old and new formats), or (3) use separate files. We chose option (2): the snapshot engine now auto-migrates list→dict on read.

---

## 2026-04-10 — Data room ingestion must exclude its own output directories
**Mistake:** `DataRoomEngine.ingest()` recursively scanned a directory and ingested files inside `dataroom/chunks/` — its own output. This created self-referential documents (chunk metadata tables appearing as searchable content), polluting search results and inflating document counts.
**Rule:** Any recursive file scanner MUST exclude directories it writes to. Add `_EXCLUDE_DIRS = {"dataroom", "mind", "__pycache__"}` and check path parts during traversal. More generally: write paths and read paths should never overlap without explicit exclusion.

---

## 2026-04-10 — Living Mind methodology layer requires registration at startup
**Mistake:** `build_mind_context()` Layer 3 (Methodology) returned empty during standalone tests. The methodology data only exists after `register_klaim_methodology()` is called at import time by `main.py`. Standalone scripts don't trigger this registration.
**Rule:** The metric registry is populated at import time via explicit `register_*()` calls in `main.py`. Any code that reads from the registry outside of the FastAPI app (scripts, tests, CLI) must call the registration functions first. This is by design — not a bug — but should be documented.

---

## 2026-04-10 — NotebookLM Python API is fully async with context manager
**Mistake:** First attempts to use `notebooklm-py` failed: `NotebookLMClient()` requires `auth` parameter, methods are coroutines needing `await`, and the client requires `async with` context manager. Took 5 attempts to find the correct pattern: `client = await NotebookLMClient.from_storage(); async with client: ...`
**Rule:** When integrating a new third-party library, inspect its API surface (`dir(module)`, `inspect.signature()`) before writing integration code. For async libraries called from sync code, use `asyncio.run()` with a wrapper function, and handle the "event loop already running" case via `ThreadPoolExecutor`.

---

## 2026-04-10 — Parallel worktree sessions need careful merge planning
**Mistake:** Two Claude sessions (Research Hub + Legal Analysis) worked in parallel on different worktrees, both modifying `main.py`, `Sidebar.jsx`, `App.jsx`, and `api.js`. Merge required resolving 3 conflicts.
**Rule:** When running parallel worktree sessions: (1) document which files each session will modify upfront, (2) have the session with fewer shared-file changes commit first, (3) use the handoff prompt pattern to transfer context between sessions. The merge was clean because both sessions added to different sections — additive changes merge well, overlapping edits don't.

---

## 2026-04-09 — Summary endpoint must pass through ALL fields from KPI builder, not cherry-pick
**Mistake:** `get_tamara_summary_kpis()` returned `face_value_label` and `deals_label` fields, but the `/summary` endpoint hardcoded a return dict that only picked specific fields (`total_deals`, `total_purchase_value`, `facility_limit`, etc.) and didn't include the label fields. The frontend received no label overrides and fell back to "Face Value" / "Deals".
**Rule:** When adding new fields to a KPI builder function, always check the endpoint that consumes it — if the endpoint constructs a hardcoded return dict (not `**kpis`), the new fields won't pass through. Either use `**kpis` spread or explicitly add every new field. Grep for the field name in the endpoint response to verify it's included.

---

## 2026-04-09 — Metrics with different semantics must not share the same label
**Mistake:** Tamara's `total_purchase_value` was outstanding AR (a point-in-time balance) but was displayed as "Face Value" (which for Klaim/SILQ means total originated — a cumulative metric). This inflated the aggregate banner from $308M to $665M by mixing fundamentally different metrics. The user caught it.
**Rule:** When onboarding a new company, audit every metric that feeds into shared display components (landing page cards, aggregate stats banner). If the metric has a different semantic meaning than what the label implies, either: (1) use a different field name, (2) pass a custom label, or (3) exclude it from aggregates. Never assume "total_purchase_value" means the same thing across all analysis types.

---

## 2026-04-09 — Uvicorn --reload only watches the --app-dir, not parent imports
**Mistake:** Changed `core/analysis_tamara.py` and `core/loader.py` expecting uvicorn's `--reload` to pick them up. It didn't — the server was started from `backend/` with `--reload` which only watches files in the `backend/` directory, not `core/` (which is a sibling). Had to manually restart the server multiple times.
**Rule:** When running `uvicorn main:app --reload` from `backend/`, file changes in `core/` will NOT trigger a reload. Either: (1) restart the server manually after changing `core/` files, (2) start uvicorn with `--reload-dir ../core` to add the watch path, or (3) touch `backend/main.py` after editing core files (but this is unreliable — the import cache may not refresh).

---

## 2026-04-09 — Adding file extensions to the loader catches unintended files
**Mistake:** Added `.json` to `get_snapshots()` for Tamara data room JSON files. This also matched `config.json` and `methodology.json` in the same directory — they have no date prefix (returning `date: null`) and aren't data snapshots. The frontend saw these extra entries and failed to pass a valid snapshot filename to `/summary`, causing a 404 that broke the Tamara card on the landing page.
**Rule:** When extending `get_snapshots()` to support new file extensions, always add an exclusion list for known non-data files in the same directory. Pattern: `_EXCLUDE = {'config.json', 'methodology.json'}` checked before the extension test. More generally: any time a file-discovery function is broadened, test it against ALL existing directories to check for false positives, not just the new one.

---

## 2026-04-07 — As-of-date only filters deals, not balances — AI must not run on backdated views
**Mistake:** The as_of_date picker filters deals by `Deal date <= as_of_date` but all balance columns (`Collected till date`, `Denied by insurance`, `Outstanding`, etc.) still reflect the tape snapshot date. This means collection rates are inflated, outstanding is understated, PAR is artificially low, and margins are wrong for any backdated view. AI analysis on this data would produce confident but misleading commentary.
**Rule:** (1) Every metric on a backdated view that depends on collection/denial/balance columns must be visually flagged as "reflects tape date". (2) AI endpoints (commentary, executive summary, tab insights) must refuse to run when `as_of_date < snapshot_date` — the AI has no way to distinguish safe from unsafe metrics and will present inflated numbers as fact. (3) When onboarding new tapes or companies, always verify: does `filter_by_date` affect only deal selection, or does it also adjust balances? For point-in-time tapes, the answer is always "deal selection only". (4) Safe metrics in a backdated view: deal count, originated volume, deployment, vintage composition. Unsafe: everything that uses Collected/Denied/Outstanding/Pending columns.

---

## 2026-04-07 — Never skip /eod even if "everything looks clean"
**Mistake:** User asked "do I need eod?" and I said no because the working tree was clean and changes were pushed. But `/eod` Step 10 (sync feature branch to main) was not done — the feature branch with all Docker/deployment code was never merged into main. The server was running from the feature branch instead of main.
**Rule:** Always run `/eod` or explicitly walk through every step. "Working tree is clean" doesn't mean the session is properly closed — branch merging, todo updates, and lessons are separate from commit status.

---

## 2026-04-07 — Roadmap Checklists Drift from "What's Working"
**Mistake:** 15 items in CLAUDE.md's "Analytical Framework Expansion" checklist were still marked `- [ ]` despite all being implemented and documented in "What's Working". The `/eod` command updated "What's Working" (Step 7) but never cross-referenced the roadmap checklists to check off completed items.
**Rule:** During `/eod` Step 7, always scan every `- [ ]` item in "Known Gaps & Next Steps" and check off any that were implemented. Cross-reference against "What's Working" entries. Mark entire sections `✅ COMPLETE` when all items are done. Two sources of truth = eventual drift.

---

## 2026-04-07 — Worktree Edits Don't Affect Running Server
**Mistake:** Edited `core/analysis_silq.py` in the worktree (`.claude/worktrees/serene-heisenberg/`) and expected the running uvicorn server to pick it up. The server was running from the main project root with different file paths. Also, the server was started without `--reload`, so even touching files in the correct directory wouldn't trigger a restart.
**Rule:** When a running backend is serving from the main project root, edits in a worktree won't be picked up. Either: (1) apply the fix to the main project's files directly, or (2) restart the server from the worktree. Also verify `--reload` is enabled — check with `Get-WmiObject Win32_Process` to see the actual command line args.

---

## 2026-04-07 — Standardize Summary Field Names Across Companies
**Mistake:** SILQ's `compute_silq_summary()` returned `total_disbursed` while the frontend expected `total_purchase_value` (the field name Klaim uses). This caused a blank Face Value on the landing page for SILQ. Each company used its own domain-specific field name without a common alias.
**Rule:** When adding a new company, ensure the `/summary` endpoint returns all fields the frontend consumes. The canonical field names are: `total_purchase_value`, `total_deals`, `total_collected`, `total_denied`, `total_pending`, `collection_rate`. If the domain uses a different term (e.g. `total_disbursed`), return BOTH the domain-specific name AND the canonical alias.

---

## 2026-04-07 — Companion metadata files beat inline decorators for large codebases
**Decision:** Instead of adding @metric decorators to 48 compute functions (which would add ~500 lines of metadata inline, cluttering the pure-compute modules), created separate companion files (`methodology_klaim.py`, `methodology_silq.py`) that register metadata after import. This keeps `analysis.py` clean (pure computation) while making methodology content easily editable.
**Rule:** When metadata is large (multi-line strings, nested structures), prefer companion registration files over inline decorators. Reserve decorators for small metadata (< 3 fields).

---

## 2026-04-06 — No new lessons this session (Framework tooling)
Session focused on creating framework slash commands, hooks, and documentation. No code errors or corrections — all deliverables were documentation/config.

---

## 2026-04-05 — No new lessons this session (Ejari formatting)
Session focused on aligning Ejari dashboard formatting with Klaim/SILQ. Straightforward component swap — no mistakes or corrections.

---

## 2026-04-05 — Session Source Determines Browser Access
**Mistake:** Spent significant time trying to configure Playwright MCP to connect to Chrome, going through CDP endpoints, executable paths, and multiple restarts. Root cause: the session was started from mobile (claude.ai), which runs the Claude Code agent in a cloud Linux sandbox with no access to the user's Windows machine. localhost:5173/8000 and Chrome are all unreachable from there.
**Rule:** Browser/Chrome access (via the Claude Code Chrome extension) only works when the session is started from the **Claude Code desktop app** on the same machine as Chrome. If `localhost` is unreachable and Chrome won't connect, the first question is: "Was this session started from mobile or web?" If yes, ask the user to restart from the desktop app. Never attempt Playwright MCP workarounds — they can't cross the sandbox boundary.

---

## 2026-04-05 — ODS Numbers Are Comma-Formatted Strings
**Mistake:** The Ejari ODS workbook stores numbers like `'1,348'` and `'12,727,014'` as formatted strings, not numeric types. `int('1,348')` throws `ValueError`, caught silently by `except Exception: contracts, funded = 0, 0`, returning zeros. Took multiple debugging rounds to find because the backend test (direct API call) wasn't being run until late.
**Rule:** When parsing ODS/Excel cells that should be numeric, always strip commas before converting: `int(str(v).replace(',', '').strip())`. Whenever a backend endpoint silently returns zeros for a field that should have data, immediately test the endpoint directly (`Invoke-RestMethod`) to confirm what's actually being returned before debugging frontend code.

---

## 2026-04-05 — Silent Failures from Wrong Loader Function
**Mistake:** Used `load_snapshot()` for SILQ tapes in `/aggregate-stats`. SILQ requires `load_silq_snapshot()` (multi-sheet Excel). The wrong loader returned empty data silently — bare `except Exception: pass` swallowed the error, leaving `total_deals = 0`.
**Rule:** Never use bare `except: pass` in data loops — at minimum log the error. When adding a new loop over all companies/snapshots, always dispatch to the correct loader per `analysis_type` (silq → `load_silq_snapshot`, klaim → `load_snapshot`, ejari_summary → handle separately).

---

## 2026-04-05 — load_silq_snapshot Returns a Tuple
**Mistake:** Called `df = load_silq_snapshot(...)` then `len(df)` — but `load_silq_snapshot` returns `(df, commentary_text)`. Assigning the tuple to `df` meant `len(df) == 2` and `df.columns` threw, again swallowed silently.
**Rule:** `load_silq_snapshot` always returns `(df, commentary_text)` — always unpack: `df, _ = load_silq_snapshot(...)`. Check the function signature before calling any loader that isn't `load_snapshot`.

---

## 2026-04-05 — Cache Fingerprint Must Include Schema Version
**Mistake:** Changed stats field names (`total_records` → `total_deals`) but the cache fingerprint only tracked snapshot filenames. The cache hit check matched and served stale data with old field names, causing the frontend to show zeros.
**Rule:** Any file-based cache fingerprint must include a schema version constant. Bump `STATS_SCHEMA_VERSION` whenever the response shape changes. Pattern: `fingerprint = ["schema:v3", ...snapshot_ids]`.

---

## 2026-04-02 — Worktree .env Not Found
**Mistake:** Started a uvicorn server in a git worktree (`/.claude/worktrees/peaceful-cray/backend/`) but the `.env` file only exists in the main project root. `load_dotenv()` traverses parent directories but won't find `.env` outside the worktree directory tree. The API call failed with an auth error.
**Rule:** When testing backend changes in a worktree, either: (1) copy `.env` into the worktree root, or (2) copy the changed files to the main project directory and test with the already-running server there. Option 2 is simpler when the main server has `--reload`. Clean up any `.env` copies from worktrees afterward.

---

## 2026-03-28 — SILQ Product Name Cleanup
**Mistake:** Updated all code references (tests, AI prompts, docs) to new product names (RCL, RBF) before verifying the tape data had actually been updated. Tests failed because the Excel file still had old names (RBF_Exc, RBF_NE).
**Rule:** When a task depends on external data changes (tape edits, DB migrations, config changes), verify the data first before updating code that references it. Run a quick data check (`df['column'].value_counts()`) before writing assertions.

---

## 2026-04-01 — Dynamic Grid Reflow from Async Data
**Mistake:** PAR KPI grid used `repeat(${parKpis.length + dtfcKpis.length}, 1fr)` — columns depended on async state. PAR loaded first (3 cols), then DTFC arrived and the grid jumped to 5 cols, visibly resizing the PAR cards mid-view.
**Rule:** Never derive CSS grid column count from async data that loads incrementally. Use a fixed column count (e.g. `repeat(5, 1fr)`) so the layout is stable from first render. Empty cells are better than layout shifts.

---

## 2026-04-09 — Inline styles + responsive design = useBreakpoint hook, not CSS media queries
**Context:** The entire frontend uses inline `style={{}}` objects (not CSS classes or Tailwind). Inline styles cannot use `@media` queries. The architectural choice for mobile responsiveness was a JS-based `useBreakpoint()` hook that returns `{ isMobile, isTablet, isDesktop }` via `matchMedia` listeners, with components branching their inline style values conditionally. An alternative was migrating everything to Tailwind classes, but that would have required rewriting hundreds of style objects across 40+ files.
**Rule:** When adding responsive behavior to an inline-style codebase, prefer a shared `useBreakpoint` hook over migrating to CSS classes. But for grid columns, prefer CSS `auto-fill`/`auto-fit` with `minmax()` — these are intrinsically responsive and don't need JS breakpoint detection at all. `repeat(auto-fill, minmax(140px, 1fr))` replaces `repeat(5, 1fr)` and works at any viewport width without importing any hook.

## 2026-04-09 — Fixed sidebar widths are the #1 mobile killer
**Context:** A 240px fixed sidebar consumed ~50% of a 375px mobile screen, making all company page content unreadable. The fix was converting it to a slide-in drawer with backdrop overlay, coordinated via a React context between the Navbar (hamburger button) and CompanyLayout (drawer).
**Rule:** Any persistent sidebar > 200px must have a mobile-drawer alternative. The pattern: (1) `MobileMenuContext` shared between navbar and layout, (2) sidebar becomes `position: fixed` + `transform: translateX(-100%)` on mobile, (3) backdrop overlay with click-to-close, (4) auto-close on route change, (5) body scroll lock when open.

---

## 2026-04-04 — Emoji Flags Don't Render on Windows Chrome
**Mistake:** Used regional indicator emoji (🇦🇪, 🇸🇦) for country flags on company cards. They render correctly on macOS/Linux but show as two-letter codes (AE, SA) on Windows Chrome — Windows has no built-in emoji flag support.
**Rule:** Never use emoji flags for flags that need to be visually correct across platforms. Use `<img src="https://flagcdn.com/16x12/{cc}.png">` with ISO 3166-1 alpha-2 country codes (ae, sa, us). flagcdn.com is free, fast, and renders consistently everywhere.

---

## 2026-04-04 — replace_all Misses Siblings with Different Indentation
**Mistake:** Used `replace_all: true` to increase font size on two sibling elements ("Portfolio Companies" and "Resources" section labels). Only the first was updated — the second had a different indentation (3 spaces vs 4 spaces), so the string didn't match.
**Rule:** When doing replace_all on repeated patterns that may have slight differences (trailing spaces, indent depth), verify the count of replacements made. If there are N occurrences to update and the tool only matched fewer, check each remaining one individually. Use Grep to confirm 0 remaining instances of the old value.

---

## 2026-04-04 — Rate Already a Percentage, Don't Multiply ×100
**Mistake:** Backend `/summary` returns `collection_rate` as a percentage (e.g. 85.3). The frontend multiplied it by 100 again (→ 8530%). The bug existed in two places: CompanyCard and PortfolioStatsHero.
**Rule:** Before displaying any rate/percentage from the backend, check what unit the endpoint returns. When in doubt, log the raw value. Never multiply a value by 100 without verifying it isn't already a percentage.

---

## 2026-04-04 — Remove Props When Component Becomes Self-Fetching
**Mistake:** After rebuilding PortfolioStatsHero to fetch its own data, Home.jsx still passed `companies={companies} summaries={summaries}` props to it. The component silently ignored them — no error, but dead prop passing.
**Rule:** When refactoring a component from prop-driven to self-fetching, immediately update every call site to remove the now-obsolete props. Grep for all usages before finishing the task.

---

## 2026-04-04 — Canvas z-index and Fixed Background Layering
**Context:** Adding a Canvas animation + SVG pattern behind page content on the landing page.
**Rule:** When stacking fixed-position layers (canvas, pattern, content), assign explicit z-indexes with a gap: `-1` for decorative backgrounds, `0` for canvas, `1` for interactive content. Use `position: relative; z-index: 1` on the stats hero/content wrappers to ensure they sit above the canvas. Without explicit z-index on content wrappers, fixed-positioned canvas can bleed through.

---

## 2026-04-04 — Framer Motion in SVG Context
**Context:** Added Sparkline SVG component inside KpiCard using a `<polyline>` — no Framer Motion needed for static sparklines.
**Rule:** Don't reflexively wrap SVG elements in `motion.*` — Framer Motion has limited SVG transform support. For simple static charts (sparklines, mini donuts) use plain SVG elements. Reserve Framer Motion for layout animations on DOM elements.

---

## 2026-04-04 — Prop Added, Data Not Wired = Half-Done
**Context:** Added `sparklineData` prop to KpiCard and `trend` prop already existed. Neither is being populated from TapeAnalytics because it requires computing a delta or extracting historical series.
**Rule:** When a UI prop is added but the data source isn't wired yet, note it explicitly in todo.md as a follow-up. Don't mark the task complete until data flows end-to-end and the feature is visible in the UI.

---


## 2026-04-09 — Showcase tabs must lead with charts, not tables — tables alone aren't a "showcase"
**Context:** The Tamara plan specified "rich interactive Recharts visualizations" for all 14 tabs, calling them "showcase highlights." In execution, 9 of 14 tabs were downgraded to raw data tables due to time pressure. The plan promised trend lines for financial performance, grouped bars for demographics, projection charts for business plan, and a 17-step waterfall for facility payments. None of these materialized. The result is functional but not the "best possible demonstration of Laith" the user requested.
**Rule:** When a task is explicitly flagged as a showcase or demo, prioritize the 5-6 highest-impact visualizations over completeness. Build the novel/impressive charts first (heatmap, covenant triggers, waterfall), then fill remaining tabs with tables. A dashboard with 5 stunning charts and 9 tables is more impressive than 14 mediocre tables. Also: estimate visualization complexity upfront — a Recharts LineChart takes 15 minutes, a CSS-grid heatmap takes 45, a custom waterfall takes 60. Budget accordingly.

---

## 2026-04-09 — Data extraction failures should be caught and reported, not silently empty
**Context:** The investor reporting, demographics, business plan, and financial master sections all parsed to empty arrays. The prepare script's `try/except` blocks swallowed errors, and the dashboard showed "No data available" without explaining why. The root causes were: (1) investor reporting sheet names don't match the hardcoded expectations, (2) demographics workbook has a different structure than assumed, (3) business plan summary sheet column layout varies. These were all fixable but invisible.
**Rule:** Data preparation scripts must log every extraction attempt with success/failure and row counts. At minimum: `print(f"  Parsed {len(records)} records from {source}")`. When a section returns 0 records, log a WARNING with the attempted file path and expected format. The dashboard should distinguish "data not available" (no source file) from "data extraction failed" (source exists but parser failed) — different colors, different messages.

---

## 2026-04-09 — AI Executive Summary context must be wired before marking a company "onboarded"
**Context:** Tamara was marked as onboarded and committed, but `_build_tamara_full_context()` was never implemented. The AI Executive Summary endpoint falls through to the generic Klaim context builder, which frames Tamara as "healthcare claims factoring" — completely wrong. This would produce a misleading IC-grade document if a user generates an executive summary.
**Rule:** A company is NOT fully onboarded until: (1) all tabs render with data, (2) AI Executive Summary works with correct context, (3) methodology serves correctly, (4) the company appears in FRAMEWORK_INDEX.md. Add these as checklist items in the `/onboard-company` command.

---

## 2026-04-09 — Data room ingestion is a distinct third pattern, not a variant of tape or summary
**Context:** Tamara has ~100 files across PDF, Excel, and mixed formats — nothing like a loan tape or a single ODS workbook. The initial instinct was to force it into the Ejari "summary" pattern, but the parser complexity was totally different. The solution was a three-layer architecture: (1) ETL script that reads raw data room files and produces structured JSON, (2) runtime parser that reads JSON and enriches with presentation fields, (3) frontend dashboard that renders from the enriched JSON. This separation means the messy multi-format parsing runs once (not per-request), the JSON is version-controlled and portable, and the runtime serving is fast.
**Rule:** When onboarding a company whose data is a data room (not a single tape or workbook), always use the ETL → JSON → parser pattern. Never try to parse PDFs or heterogeneous Excel files at runtime. The ETL script lives in `scripts/prepare_{company}_data.py`, the JSON lives in `data/{Company}/{Product}/`, and the parser lives in `core/analysis_{company}.py`. Re-run the ETL when new data arrives in the data room.

---

## 2026-04-09 — Research reports should be a platform capability, not per-company scripts
**Context:** Started to build `scripts/generate_tamara_report.py` as a one-off, but the user correctly identified that this should be a reusable platform feature. Every company benefits from a professional PDF credit research report — the data context, section structure, and AI narrative generation are all parameterizable by analysis_type.
**Rule:** When building a feature that works against a company's parsed data, always ask: "Does this generalize to all companies?" If yes, put it in `core/` with a backend endpoint, not in `scripts/`. The pattern: `core/{capability}.py` with company-specific builders dispatched by analysis_type, plus a `POST` endpoint in `main.py`.

---

## 2026-04-09 — HSBC PDF table parsing requires pdfplumber not PyPDF
**Context:** The HSBC investor reports have structured tables (BB waterfall, trigger tests, concentration limits, stratifications) that need tabular extraction. pdfplumber handles this well — it extracts tables as lists of lists. The table positions and headers are consistent across all 20 reports, making batch processing reliable. PyPDF only extracts raw text without table structure.
**Rule:** For PDF files with structured tables (investor reports, compliance certificates, facility agreements), use pdfplumber. For PDF files with only narrative text, raw text extraction (pypdf) is sufficient. Always test the parser against 2-3 sample files before batch-processing the full set.

---

## 2026-04-09 — Vintage cohort matrices have a consistent structure: header detection matters
**Context:** The ~50 vintage cohort Excel files all follow the same structure (triangular vintage × MOB matrix) but have slight variations: some have a year row above the month row, some don't; some use date strings, others use month names; the vintage column can be labeled "Breakdown D1" or just be the first column. A rigid parser that assumed exact headers would break on half the files.
**Rule:** When parsing Excel files from external sources, build header detection that searches the first 5 rows for known patterns (month names, date formats, keywords) rather than assuming a fixed row. Handle both date-string and month-name column headers. Always log warnings (not errors) for files that don't parse, and continue processing the rest.

---

## 2026-04-09 — Unicode arrows in print statements fail on Windows cp1252 console
**Mistake:** Used `→` (U+2192) in a Python print statement. Crashed on Windows because the console uses cp1252 encoding which doesn't support that character. Quick fix: replace with `->`.
**Rule:** In Python scripts that will run on Windows, never use Unicode arrows, em-dashes, or other non-ASCII symbols in print/log statements. Use ASCII equivalents: `->` not `→`, `--` not `—`, `*` not `•`. Or set `sys.stdout.reconfigure(encoding='utf-8')` at the top of the script, but the ASCII approach is more portable.

---

**Mistake:** SILQ's Overview crammed PAR30/PAR60 into inline KPI cards (PAR60 hidden as PAR30's subtitle), while Klaim had a dedicated "Portfolio at Risk" section with individual PAR cards. The Analysis Framework already defined a 5-level hierarchy (L1-L5) that should guide page structure, but it wasn't being applied to the frontend layout.
**Rule:** When adding a new company or tab, follow the established section structure (Main KPIs → Credit Quality → Leading Indicators). Use the Analysis Framework hierarchy to decide which section a metric belongs in. Don't inline L3 (Credit Quality) metrics with L1 (Size) KPIs. Consistency in section structure, bespoke content within sections.
