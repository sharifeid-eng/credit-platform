# Lessons Learned
Persistent log of mistakes and patterns. Claude reviews this at session start to avoid repeat errors.

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


**Mistake:** SILQ's Overview crammed PAR30/PAR60 into inline KPI cards (PAR60 hidden as PAR30's subtitle), while Klaim had a dedicated "Portfolio at Risk" section with individual PAR cards. The Analysis Framework already defined a 5-level hierarchy (L1-L5) that should guide page structure, but it wasn't being applied to the frontend layout.
**Rule:** When adding a new company or tab, follow the established section structure (Main KPIs → Credit Quality → Leading Indicators). Use the Analysis Framework hierarchy to decide which section a metric belongs in. Don't inline L3 (Credit Quality) metrics with L1 (Size) KPIs. Consistency in section structure, bespoke content within sections.
