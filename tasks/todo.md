# Current Task Plan
Track active work here. Claude updates this as tasks progress.

---

## Active

_Nothing in progress._

---

## Completed — 2026-04-22

### Session 33 — Executive Summary hardening: Aajil audit + 5 prompt disciplines — SHIPPED

Starting state: Session 32 shipped the SSE stream endpoint but production revealed three follow-on failures on the Aajil Executive Summary. Each symptom surfaced after fixing the prior one, which is exactly what happens when you don't have error propagation: you keep "fixing" the visible message until the real cause shows up.

**Symptoms encountered (in order):**
1. `/company/Aajil/KSA/executive-summary` rendered a single POSITIVE "Agent Summary" card dumping raw markdown with literal `**bold**` and `| tables |` — cache-hit from the sync endpoint's fallback.
2. After the first fix: "WARNING / Summary generated (unparsed)" with raw text ending mid-string at `"assessment":` — agent output truncated by max_tokens.
3. After the second fix: generic "Stream ended without a result" with no visible error — backend swallowed runtime-yielded error events.
4. After error propagation fix: "3 consecutive tool errors — stopping to avoid loop" — real error now visible; analyst agent was tripping on unguarded `load_tape(Aajil)` calls.

**Six commits landed:**

1. **`86c12a8` (pre-session)** — `fix(agents)`: Aajil-aware branches for `_get_covenants` (graceful skip — no `compute_aajil_covenants` exists), `_get_deployment` (dispatch to `compute_aajil_traction`), `_get_ageing_breakdown` (dispatch to `compute_aajil_delinquency`). 3 new regression tests in `tests/test_agent_tools.py` `TestAajilHandlerSignatures`.

2. **`b6a9d04`** — `fix(exec-summary)`: JSON contract in sync prompt + robust parser.
   - Rewrote `generate_agent_executive_summary` sync prompt to mirror stream endpoint's JSON schema (was asking for markdown narrative; fell back to wrapping raw markdown as severity='positive' "Agent Summary" — matching the screenshot exactly).
   - Added `_parse_agent_exec_summary_response()` helper: strips ```json fences → tries `json.loads()` → falls back to outermost `{...}` substring extraction (handles conversational preamble like "I now have comprehensive data…") → final fallback is severity='warning' 'Summary generated (unparsed)' (never 'positive', never 'Agent Summary').
   - Both sync (`main.py:2855`) and stream (`main.py:3294`) paths use the helper. Dead code removed.
   - 8 new `TestParseAgentExecSummaryResponse` tests lock in the extraction paths + "severity never positive on failure" regression.

3. **`9673b22`** — `fix(exec-summary)`: bump analyst `max_tokens_per_response` to 16000 for structured JSON output.
   - Root cause of symptom #2. Analyst default was 2000 tokens — catastrophically low for 6-10 narrative sections × 300-500 words + findings array. Opus 4.6 supports 32K output; 16K is safely within limits.
   - `_run_agent_sync()` gained `max_tokens_per_response` override param (mirrors existing `max_turns` override).
   - Both exec summary call sites bump to 16000; other analyst calls (commentary, tab_insight, chat) keep the 2000 default so runaway cost is capped elsewhere.

4. **`df76558`** — `fix(exec-summary)`: propagate runtime error messages through terminal done.
   - Root cause of symptom #3. When the runtime yielded `StreamEvent("error", …)` (e.g. tool-loop abort), the backend passed it through as an SSE `error` event but never set `stream_error` — so the terminal `done` payload was `{"ok": false}` with no `error` field. Frontend's `onError` fired with the real message, then `onDone` overwrote it with the fallback "Stream ended without a result".
   - Backend now captures runtime-yielded errors into `stream_error` so terminal `done` carries the message.
   - Frontend tracks `errorSet` locally and `onDone` fallback only fires if nothing else surfaced an error.
   - Strengthened existing `test_agent_error_event_is_forwarded` to assert terminal done carries the propagated message.

5. **`e232d55`** — `fix(agents)`: graceful-skip `_get_dso_analysis` and `_get_dtfc_analysis` on Aajil.
   - Root cause of symptom #4. Second-pass audit revealed two more tools calling `load_tape(Aajil)` in their `else` branch without guards. Both metrics are Klaim-specific (DSO = days-from-funding, DTFC = days-to-first-cash). Aajil uses installment-based DPD instead.
   - Both handlers now return hint strings pointing at working alternatives (`get_ageing_breakdown`, `get_cohort_analysis`) so the agent moves on in 1 turn instead of burning 3 on error retries.
   - Full audit of all 19 `load_tape()` call sites in `analytics.py` — all now properly guarded.
   - 2 new regression tests lock in the graceful-skip contract including "must not start with `Error:`" (runtime counts those toward the 3-errors circuit breaker).

6. **`abacdcf`** — `feat(exec-summary)`: 5 prompt disciplines + `analytics_coverage` callout.
   - Full content review of the PDF output (13 pages, Aajil Exec Summary) surfaced 6 content-level issues beyond the rendering bugs: arithmetic drift (gross 4.2M / recoveries 0.9M / net 3.4M doesn't reconcile), "estimated >60%" when computable, silent section substitution (swapped Cohorts for Loss Attribution), platform findings mixed with credit findings (tool gaps + undefined thesis ranked top-3), lenient severity (16.9% recovery = Warning should be Critical), metric reconciliation gaps (298.3M vs 332.3M realised without naming denominators).
   - NEW: `core/agents/prompts.py` — single source of truth for Executive Summary prompt. Both sync + stream endpoints import `build_executive_summary_prompt()`.
   - 5 new binding rule sections: ARITHMETIC DISCIPLINE, COMPUTE-DON'T-ESTIMATE, SECTION DISCIPLINE, FINDINGS DISCIPLINE, SEVERITY CALIBRATION.
   - NEW optional schema field `analytics_coverage` (string). 1-3 sentence callout naming unavailable tools + undefined thesis. Rendered as muted amber block between Bottom Line and Key Findings — distinct from credit severity signals. Parser normalises empty/whitespace/non-string to None so frontend doesn't render placeholder.
   - Frontend: new `AnalyticsCoverageCallout` component + `analyticsCoverage` state; wired into result handler.
   - CLAUDE.md: new "Agent Tool Coverage Checklist" (6 items) alongside Methodology checklist — locks in graceful-skip contract, load_tape audit requirement, section_guidance_map per-company expectation.
   - NEW `tests/test_exec_summary_prompt.py` (20 prompt-contract tests) + 4 new tests in `test_exec_summary_stream.py` covering analytics_coverage pass-through + round-trip.

**Scope answer (user's explicit question):** 6 of 7 content issues are prompt-level and apply to every company. Klaim and SILQ didn't surface them because their tool coverage is fuller — less room for agent drift. Aajil stressed the system with gaps. Same fixes benefit all companies; no per-company prompt changes needed when onboarding (only tool coverage + section_guidance_map entries).

**Final state: 525 passing, 59 skipped, 0 failures** (baseline was 504).

---

### Session 32 — Executive Summary SSE stream — SHIPPED

User report: Aajil `/executive-summary` returned **HTTP 524** (Cloudflare edge-proxy origin timeout, ~100s on CF Free). Diagnosed: frontend was using `getExecutiveSummaryAgent` (`mode=agent`) which routes to `generate_agent_executive_summary` — analyst agent with `max_turns=20` + internal 120s timeout. Aajil legitimately exceeds 100s because most of its analytics tools crash on Klaim-specific column assumptions, so the agent loops on tool errors. Blocking GET → CF kills connection before agent finishes → 524.

Options presented: (1) revert to non-agent path (1-line, ships in minutes), (2) cut `max_turns` to 12, (3) convert endpoint to SSE with heartbeats like `memo_generate_stream`. User chose (3) with "option b" — full stage events, not just a spinner.

**Shipped:**

1. **[backend/main.py](backend/main.py) — new `GET /companies/{co}/products/{p}/ai-executive-summary/stream`** SSE endpoint.
   - Cache-hit fast path: emits `start → cached → result → done` instantly (still SSE so the client has one code path).
   - Cache-miss: builds the agent prompt (extended with an explicit JSON output contract so we can parse narrative+findings after streaming), runs the `analyst` agent in a **dedicated thread with its own event loop**, pushes `StreamEvent`s to an `asyncio.Queue` via `loop.call_soon_threadsafe`. Drain loop emits `: keepalive\n\n` every 20s of idle time. This thread offload was the critical fix — without it, the sync Anthropic client blocked uvicorn's main event loop, freezing both heartbeats AND the queue drain (symptom during browser test: stage stuck at "Starting…" for 83s while backend log showed tool calls executing).
   - Intercepts the runtime's `done`, parses accumulated text as JSON, writes to cache (same `_ai_cache_key` as sync endpoint so both share state), emits a structured `result` event, then emits a single terminal `done` with `turns_used` + token counts.
   - Preserves the existing sync endpoint untouched (analysts on non-agent paths still work).

2. **[frontend/src/services/api.js](frontend/src/services/api.js) — new `streamExecutiveSummary(co, prod, snap, cur, asOf, handlers, {refresh})`** helper. `fetch` + `ReadableStream` (not `EventSource` — need cookie credentials + AbortController). Parses SSE frames, dispatches to per-event handlers (`onStart`, `onCached`, `onText`, `onToolCall`, `onToolResult`, `onBudgetWarning`, `onResult`, `onError`, `onDone`, `onHeartbeat`, `onAbort`). Returns the `AbortController` for caller cancellation.

3. **[frontend/src/pages/ExecutiveSummary.jsx](frontend/src/pages/ExecutiveSummary.jsx) — rewrote `generate()` to consume the stream.**
   - Replaced the pulsing skeleton with a new `StreamProgressPanel` — terminal-style live timeline: current stage (with blinking cursor + gold arrow marker) + elapsed `mm:ss` counter + prior stages with ✓ checkmarks in a scroll box.
   - Friendly labels for 20+ tool names: `get_portfolio_summary` → "Pulling portfolio summary", `get_par_analysis` → "Assessing portfolio at risk", `get_cohort_analysis` → "Walking vintage cohorts", etc. Unknown tools fall back to `Running {tool_name_prettified}`.
   - Hint banner appears after 45s: "Executive summaries typically complete in 60-120 seconds. The stream is kept alive with heartbeats so long runs won't be cut off."
   - Stale-closure bug avoided via `resultEmitted` local flag (instead of reading `findings` state in `onDone` callback).
   - Cleanup on unmount: aborts stream + clears elapsed timer.
   - Meta-bar refactored: drops `coverage`/`cached_at` (agent mode doesn't compute these), adds AGENT + CACHED chips.

4. **[tests/test_exec_summary_stream.py](tests/test_exec_summary_stream.py) — 4 regression tests** pinning the SSE contract:
   - `test_cache_hit_streams_result_immediately` — exactly `start → cached → result → done`; cached payload round-trips; done carries `from_cache=True`.
   - `test_agent_events_forward_and_result_is_parsed` — `tool_call`/`tool_result`/`text` forwarded as-is; result lands AFTER the last text chunk; exactly ONE terminal `done` (no double-done); agent metadata (`turns_used`, tokens) merged into our done; side effect: parsed payload written to cache.
   - `test_unparseable_text_falls_back_to_warning_finding` — JSON parse failure still produces a renderable result (`narrative: null`, one warning finding carrying the raw text as explanation).
   - `test_agent_error_event_is_forwarded` — runtime error events pass through; terminal done still fires with `ok: false`.

**Browser verification:** Stream held open **4m 24s** on Aajil (well past CF's 100s cap that produced the original 524). 15+ tool calls streamed live. Every stage transition rendered in real time; prior stages collapsed into a ✓-marked scroll box. All 488 tests still pass (59 DB tests skipped — DATABASE_URL not set in worktree).

**Follow-up spawned separately:** Aajil's agent tools crash (`compute_aajil_covenants` doesn't exist; `_get_deployment`/`_get_ageing_breakdown` assume Klaim's `Month`/`Status` columns). The SSE transport works — the agent's quality for Aajil specifically is gated on those pre-existing bugs. Tracked as its own task/worktree.

### Session 31 (continued) — DB as snapshotted source of truth — SHIPPED

Started 2026-04-21, shipped + deployed 2026-04-22. Root cause of the investigation: `_portfolio_load` silently preferred the DB path when `has_db_data()` was True, but DB had no snapshot dimension and `db_loader` dropped every non-core column. Apr 15 covenants returned `wal_active=183d / Breach / Total WAL=n/a / Extended Age=12.7% / sel['date']=datetime.now()` instead of `148d / Path B / 137d / 4.4% / 2026-04-15`. Three commits on branch `claude/hardcore-johnson-94c5fe`:

1. **`dae0d02` — fix(klaim): CovenantCard Path B carve-out suppression** (pre-Session-31, the original trigger).
   - WAL is the only Klaim covenant with dual-path compliance. On Path B, `headroom=current-threshold` is negative and the breach projection lands in the past — both mathematically correct vs Path A but operationally misleading. Guarded by `compliance_path === 'Path B (carve-out)'`; renders the covenant's own `note` ("Compliant via carve-out (Extended Age X.X% ≤ Y%)") in a muted line.
   - 1 new backend contract test (`test_path_b_carve_out_contract_for_frontend`) pins the exact string + note shape the frontend guard depends on.

2. **`aba8994` — feat(db): snapshots as first-class dimension + DB as authoritative source** (Phases 1-6).
   - **Schema (migration `c3d4e5f6a7b8`, destructive per D1a):** new `snapshots` table (product_id + name unique; source ∈ tape/live/manual; taken_at, ingested_at, row_count). `Invoice.snapshot_id NOT NULL FK` + `(snapshot_id, invoice_number)` unique. `Payment.snapshot_id NOT NULL FK`. `BankStatement.snapshot_id` nullable FK. All existing 9,612 invoices + 8,866 payments deleted (D1a).
   - **`scripts/ingest_tape.py`** (new CLI): one tape → one Snapshot + N Invoices + M Payments. `extra_data` JSONB keys use the original tape column names verbatim — new analytical columns flow through DB automatically, no loader-mapping change ever needed. CLI: `--company/--product/--file`, `--all`, `--dry-run`, `--force`. Idempotent on (product_id, name).
   - **Read path rewrite (`core/db_loader.py`):** new `list_snapshots(db, co, prod)` and `resolve_snapshot(db, co, prod, snapshot)`. `load_klaim_from_db` / `load_silq_from_db` take `snapshot_id` param, spread `extra_data` keys back onto the DataFrame. Apr 15 DataFrame once again carries all 65 columns including the ones required for direct-DPD PAR + dual-view WAL. `has_db_data` removed.
   - **`_portfolio_load` rewritten:** DB-only, no tape fallback. Resolves snapshot via `resolve_snapshot`, 404s on miss. `sel['date'] = snap.taken_at` (real date, not `datetime.now()`). As-of-date auto-resolves to matching snapshot so the existing Portfolio as-of-date dropdown acts as a snapshot selector without a frontend rewrite.
   - **Honesty:** every portfolio endpoint returns `data_source='database'` + `snapshot_source=sel.source`. `PortfolioAnalytics.jsx:127` badge stops lying about "Tape Fallback".
   - **9 snapshots backfilled** (5 Klaim + 4 SILQ), 42,535 rows total. Verified end-to-end: Apr 15 → 148d / Path B / Total WAL 137d; Mar 3 → 140d / Path B / n/a (graceful).

3. **`074d382` — feat(integration): live-snapshot write path + 38 snapshot-layer tests** (Phases 5+7).
   - **Rolling-daily live snapshot** (`live-YYYY-MM-DD`). `get_or_create_live_snapshot(db, product)` — idempotent under concurrent race. `is_snapshot_mutable(snapshot, today)` — True only for today's live snapshot; tape + prior-day live are frozen.
   - **Integration API:** POST /invoices UPSERTs by `(snapshot_id, invoice_number)` within today's snapshot. PATCH/DELETE require live-today snapshot (else 409). Payment inherits `invoice.snapshot_id` on write. Bulk paths + bank statements all tagged.
   - **28 DB snapshot layer tests** (`tests/test_db_snapshots.py`): ingest round-trip, `extra_data` preservation (Apr 15 new columns), Mar 3 graceful degradation, resolve by name/filename/ISO-date/None, list ordering, DB↔tape equivalence, snapshot isolation (Apr 15 ≠ Mar 3), live-snapshot helper create-if-needed + idempotent, mutability rules.
   - **10 Integration API tests** (`tests/test_integration_snapshots.py`): first-push creates snapshot, same-day reuses, same invoice_number UPSERTs, bulk 5x in one snapshot, PATCH/DELETE on tape → 409, payment inherits snapshot_id, read-path compat.
   - **498 tests passing** total (was 460).

4. **`ccff5ab` — feat(frontend): SnapshotSelect component with TAPE/LIVE/MANUAL pills.**
   - Custom dropdown replacing native `<select>` in TapeAnalytics controls bar + DataIntegrityChart Old Tape / New Tape dropdowns. Colour-coded chip per source (TAPE=gold, LIVE=teal, MANUAL=blue). Keyboard nav (arrows/Enter/Esc), click-outside, ARIA `role=option` + `aria-selected`.
   - `CompanyContext` gains `snapshotsMeta` (full `{filename, date, source, row_count}` objects) alongside the existing `snapshots` string array — back-compat preserved.
   - Dead `DarkSelect` helper removed from both TapeAnalytics.jsx and DataIntegrityChart.jsx.
   - Vite build passes clean (1108 modules).

**Production deployed:** Hetzner VPS pulled `main`, rebuilt backend with `--no-cache`, applied migration `c3d4e5f6a7b8` inside container, ingested 42,535 rows across 9 snapshots. Site live at https://laithanalytics.ai. Browser-verified: Apr 15 WAL 148d / Path B / Total WAL 137d, Live Data badge, real snapshot dropdown — all matching local.

**Still deferred (not this session):**
- D7 — scheduled external pollers (still parked)
- Klaim Account Debtor validation (CRITICAL DATA GAP — waiting on company communication before designing data source)

---

## Session 31 — DB as snapshotted source of truth (SHIPPED — historical plan)

### Context

Session 30 left behind a latent architectural defect: `_portfolio_load` silently prefers the DB path when `has_db_data(db, co, prod)` returns True. The DB currently holds a single "current state" of invoices — there is no snapshot dimension. Consequences, all surfaced on 2026-04-21:

- Snapshot selector on `/portfolio/covenants` is non-functional when DB has data (same DataFrame served regardless of chosen snapshot; only `ref_date` varies via `as_of_date`).
- DB-loader mapper (`load_klaim_from_db`) ignores `Invoice.extra_data` JSONB, so any tape column added after last seed is dropped. Apr 15 tape's `Expected collection days`, `Collection days so far`, `Provider`, `AccountManager`, `SalesManager` are all lost → `Total WAL = n/a`, direct-DPD PAR degrades to shortfall proxy, Provider chart missing.
- `sel['date']` defaults to `datetime.now()` on the DB path — API response echoes back a "snapshot" date that doesn't correspond to any real file.
- "Tape Fallback" badge in `PortfolioAnalytics.jsx:127` lies: reads `data.data_source || 'tape'` but covenants/BB/concentration endpoints never return `data_source`, so badge defaults to "Tape Fallback" even when DB is serving.

User intent (2026-04-21): **"we are very close to integrate live data. create a plan for the best long term solution and lets implement."** — no midway fixes. DB becomes authoritative for both tape snapshots and live Integration API writes; snapshots become a first-class dimension.

### Architectural decisions (need user call before implementation)

**D1 — Existing DB data fate.** 7,697 current Klaim invoices + any SILQ rows were seeded once from Mar 3 tape and have drifted from reality (no snapshot lineage, no extra_data, wrong column set). Two options:
- (a) **Drop + clean re-seed from all tape files.** Every tape file in `data/{co}/{prod}/*.csv` becomes one Snapshot row; invoices re-created with `extra_data` fully populated. 7,697 rows is derived data — zero information loss. Recommended.
- (b) Tag existing rows as `source='legacy_initial_seed'` snapshot; re-seed only goes forward. Preserves write history but that history is not analytically useful.

**D2 — Live snapshot granularity.** Once portfolio companies push via Integration API, how do writes partition into snapshots?
- (a) **Rolling daily.** On first push each UTC day, create `live-YYYY-MM-DD` snapshot; all that day's writes go into it; same-day duplicate `invoice_number` → UPSERT within the day's snapshot; next day → new snapshot, prior day frozen. Gives naturally-spaced history without flooding the dropdown. Recommended.
- (b) Singleton mutable `live` snapshot. One row per invoice, overwritten on push. Loses history — same bug class we're fixing.
- (c) Per-call snapshot. Too granular; dropdown floods.

**D3 — Tape files post-ingest.** Once DB carries every row with full `extra_data`:
- (a) **Keep `data/{co}/{prod}/*.csv` files as archival source-of-truth.** Analysts continue to upload CSVs manually; `scripts/ingest_tape.py` reads them into DB snapshots; files stay on disk for audit. Recommended.
- (b) Delete files post-ingest. Saves disk but loses bit-identical replay capability.

**Default recommendations to proceed with unless you say otherwise: D1(a), D2(a), D3(a).**

### Implementation plan

**Phase 1 — Schema & migration** → verify: `alembic upgrade head` runs cleanly; new tables visible; all old data either dropped or tagged per D1.
- [ ] New `Snapshot` ORM model in `core/models.py`: `id UUID`, `product_id FK`, `name str`, `source enum('tape','live','manual')`, `taken_at date`, `ingested_at datetime`, `row_count int`, `notes text?`, unique `(product_id, name)`.
- [ ] `Invoice`: add `snapshot_id UUID FK NOT NULL`. Drop existing `Index("ix_invoices_org_product", ...)`, replace with `ix_invoices_snapshot_product` and composite unique `(snapshot_id, invoice_number)`. Keep `extra_data JSONB` — this is where every non-core tape column lands.
- [ ] `Payment`: add `snapshot_id UUID FK NOT NULL` (duplicated on write — payments inherit their invoice's snapshot; FK lets us query payments per snapshot without a join).
- [ ] `BankStatement`: add `snapshot_id UUID FK` (nullable — bank statements are time-series, not snapshot-scoped; but we index them by snapshot for consistency).
- [ ] `FacilityConfig`: **unchanged** (one per product, snapshot-independent).
- [ ] Alembic migration: create `snapshots` table, add FKs, backfill per D1 choice, enforce NOT NULL at the end.

**Phase 2 — Seed & ingestion tooling** → verify: `python scripts/ingest_tape.py --company klaim --product UAE_healthcare --file 2026-04-15_uae_healthcare.csv` creates one Snapshot row + 8,080 Invoice rows with `extra_data` populated.
- [ ] `scripts/ingest_tape.py` (new). Reads tape file via existing `load_snapshot()`, creates Snapshot, bulk-inserts invoices in batches of 1,000, populates `extra_data` with every column not already in the relational schema. Idempotent: same tape file → UPSERT by `(product_id, snapshot_id, invoice_number)`.
- [ ] Replace/augment `scripts/seed_db.py`: iterates all tapes per company/product, calls `ingest_tape.py` logic per file. Produces N snapshots per product.
- [ ] Dry-run mode (`--dry-run`) — shows counts without writing.

**Phase 3 — Read path rewrite** → verify: `curl /portfolio/covenants?snapshot=2026-04-15_uae_healthcare` returns 148d / Path B (matching test fixture), same as direct Python call.
- [ ] `core/db_loader.py::load_klaim_from_db(db, co, prod, snapshot_id=None)` — signature change. Filters invoices by snapshot_id (defaults to latest by `taken_at`). Reads every `extra_data` JSONB key back onto the DataFrame with its original tape column name. Same for `load_silq_from_db`, `load_from_db` dispatcher.
- [ ] `core/db_loader.py::list_snapshots(db, co, prod)` — returns `[{id, name, source, taken_at, row_count}, ...]` ordered by `taken_at`.
- [ ] `backend/main.py::_portfolio_load`: always DB path (tape fallback removed). Resolves `snapshot` query param against `list_snapshots` by name; 404 if not found. `sel = snapshot_row` — real date, real name, real source.
- [ ] Remove `has_db_data` short-circuit + tape-fallback code path.

**Phase 4 — Snapshots endpoint & list** → verify: `GET /companies/klaim/products/UAE_healthcare/snapshots` returns DB rows, not filesystem listing.
- [ ] `get_snapshots` endpoint reads from DB via `list_snapshots`. Returns `{filename, date, source}` to preserve frontend contract (filename = snapshot.name, source new).
- [ ] `get_snapshots` in `core/loader.py` becomes a pure-file-system helper used only by `ingest_tape.py` and `seed_db.py` — never by live endpoints.

**Phase 5 — Integration API** → verify: bulk invoice push with 5,000 rows creates or appends to today's live snapshot; dashboard dropdown shows `live-2026-04-21` with row count.
- [ ] New helper `get_or_create_live_snapshot(db, product, as_of_date=None)` in db_loader. On first push of a given UTC day, create `live-YYYY-MM-DD` snapshot. Subsequent same-day pushes reuse it.
- [ ] `POST /api/integration/invoices` + `/bulk`: auto-tag with today's live snapshot. Contract unchanged (no new required fields from caller).
- [ ] `PATCH /api/integration/invoices/{id}`: disallow edits to non-live snapshots (historical snapshots immutable). Reject with 409 if target invoice's snapshot is `source='tape'`.
- [ ] `DELETE /api/integration/invoices/{id}`: same constraint.
- [ ] `POST /api/integration/payments` + `/bulk` + `/invoices/{id}/payments`: inherit invoice's snapshot_id on write.

**Phase 6 — Frontend honesty** → verify: badge reads "Live Data" on DB response, source chips render in dropdown.
- [ ] Covenants/BB/Concentration endpoints return `data_source: 'database'` + `snapshot_source: 'tape' | 'live' | 'manual'`.
- [ ] `PortfolioAnalytics.jsx:127` uses `data_source` honestly. Add `snapshot_source` chip next to snapshot name in dropdown (small Tape/Live tag).

**Phase 7 — Tests** → verify: all pre-existing 505 tests still pass, plus ~50 new snapshot-layer tests.
- [ ] `tests/test_db_snapshots.py` (new): snapshot creation, uniqueness, invoice isolation across snapshots, extra_data round-trip (all 5 Apr 15 columns survive DB → DataFrame), historical query (Mar 3 snapshot ≠ Apr 15 snapshot).
- [ ] `tests/test_integration_api_snapshots.py` (new): bulk push creates live snapshot, same-day upsert, next-day new snapshot, edit rejected on tape snapshot.
- [ ] `tests/test_portfolio_load.py` (new or extend existing): `_portfolio_load` resolves named snapshot, falls back to latest, 404 on missing.
- [ ] Existing `test_analysis_klaim.py::TestDualViewWAL` should now pass against DB-loaded Apr 15 tape (wal_total = 137d).

**Phase 8 — Verification & acceptance** → verify in browser + curl.
- [ ] Browser: Klaim / covenants / Apr 15 → WAL shows 148d / Path B (matches session 30 screenshot + new CovenantCard fix).
- [ ] Browser: Klaim / covenants / Mar 3 → WAL shows 140d / Path B.
- [ ] Browser: data source badge says "Live Data" (because DB is now serving); snapshot chip says "Tape".
- [ ] curl `/snapshots` returns Snapshot rows, not filesystem listing.
- [ ] Seed a mock live push for Klaim (bulk POST 10 invoices via Integration API with today's date); confirm new `live-2026-04-21` snapshot appears in dropdown; confirm historical tape snapshots unchanged.
- [ ] 505 + ~50 tests all green.

### Scope, risk, sequencing

- **Estimated effort:** 15–20 focused hours. Real schema change, not a patch. Will land in 4–6 commits along phase boundaries.
- **Blast radius:** touches `core/models.py`, `core/db_loader.py`, `backend/main.py` (`_portfolio_load`, snapshots endpoint), `backend/integration.py`, `scripts/seed_db.py`, new `scripts/ingest_tape.py`, new Alembic migration, `frontend/src/pages/PortfolioAnalytics.jsx`. 3 new test files.
- **Biggest risk:** the Alembic migration on data that's hot in production. I'll write a reversible migration + dry-run path, test on a fresh DB first, then on a staging copy.
- **What breaks in between:** nothing visible to the analyst if phases land in order. Integration API contract is preserved throughout. Tape-fallback is removed in Phase 3 — after Phase 2 has populated DB with all historical snapshots, so dashboard continues to show every historical tape that existed before.
- **What's out of scope this session:** bank statement snapshot semantics (file remains singleton-per-org); facility_config changes; admin UI for tape upload (still a CLI); UI for browsing snapshot diffs.

### Blocking on user decisions before writing any code

**D1** drop + re-seed / tag legacy?
**D2** rolling daily live / singleton mutable / per-call?
**D3** keep tape files post-ingest / delete?

Recommend proceeding with **D1(a), D2(a), D3(a)**. Say "proceed" and I'll start Phase 1; say "adjust X" and I'll revise.

---

## Session 30 — Klaim Apr 15 tape: validation fixes + Provider + dual-view WAL (2026-04-21)

**Part 1 — validation/consistency recalibration** (`4f2d186`)
- Balance Identity check rewritten to Klaim accounting identity `Paid + Denied + Pending ≡ Purchase value` (1% tolerance). Was using `Collected + Denied + Pending > 1.05 × PV` which fired on **2,775 / 8,080 deals (34%)** on Apr 15 — all false positives because Collected legitimately exceeds Paid (VAT + fees on top of claim principal). After fix: **2,775 → 0 flags** on Apr 15.
- Status reversal `Completed → Executed` downgraded from CRITICAL to WARNING with explanatory `note` field. Known Klaim pattern: deal closes on booked payment, subsequent insurance denial re-opens it (Denied becomes non-zero, Status returns to Executed for dispute/collection). Mar 3 → Apr 15: **55 critical reversals → 0 critical, 55 warnings**. Note propagates into AI integrity report prompt + frontend ConsistencyItem renderer (italic subtitle). Other reversal paths (Completed→Pending, Completed→null) still CRITICAL.
- Tests: 6 new — `TestBalanceIdentityKlaim`, `TestStatusReversalSeverityKlaim`.

**Part 3 — dual-view WAL** (`1bfdbf2`)
- `wal_active_days` (148d on Apr 15): outstanding-weighted active-only, **unchanged — still the covenant value per MMA Art. 21**. Framework Confidence A.
- `wal_total_days` (137d on Apr 15): PV-weighted across active + completed — IC/monitoring view that strips the retention bias of active-only WAL (slow payers overweighted because fast ones leave the pool quickly). Framework Confidence B.
- Close-date proxy for completed deals: `Collection days so far` (observed), clipped to `[0, elapsed]`, fallback to `Expected collection days` when observed is missing/negative. Documented in `compute_methodology_log()` as a `close_date_proxy` adjustment entry.
- Initially tried `Expected collection days` as primary proxy → wal_total (152.8d) > wal_active (148d), invariant failed. Switched to observed `Collection days so far` → wal_total (137.2d) < wal_active (148d) ✓. Lesson recorded.
- Covenant card renders both in breakdown + dashed-divider `view_note` block explaining the split. Covenant compliance still keyed to Active WAL only (Path A ≤ 70d OR Path B Extended Age ≤ 5%). Mar 3 and older: wal_total = None, graceful.
- `column_availability` in methodology log now tracks `Paid by insurance`, `Pending insurance response`, `Expected collection days`, `Collection days so far`, `Provider`.
- Tests: 8 new — `TestDualViewWAL` (active=148±1, total<active invariant, graceful degradation on Mar 3, covenant keyed to active not total, view_note present, proxy documented, new columns registered).

**Part 2 — Provider column wired end-to-end** (`300bcde`)
- `compute_concentration`: emits `result.provider` (top-15, same shape as group) when column present. Apr 15 top 3: ALPINE 5.3%, ALRAIAA 4.7%, AFAQ 4.5%.
- `compute_hhi`: adds `provider` section (Apr 15 HHI = 0.0201 ≈ 201 bps²). `compute_hhi_for_snapshot` emits `provider_hhi` in time series — null on pre-Apr 15 tapes.
- `compute_segment_analysis`: two new dimensions `group` and `provider`; both high-cardinality (144 / 216 distinct), collapsed to **top-25 by originated volume + `Other` bucket** for tractable dropdown + heat-map. Frontend dropdown filters against `available_dimensions` so older tapes hide Provider automatically.
- Frontend: ConcentrationChart gains Provider donut + top-8 inline list and a Provider HHI badge (gold/teal/red coloured). SegmentAnalysisChart wraps DIMENSIONS through `availableDims` filter. All conditional on payload presence — Mar 3 UI unchanged.
- Live dev-server verified (Apr 15 Chrome smoke test): Provider HHI visible, Provider Concentration section renders, ALPINE/ALRAIAA show in top 3; zero console errors. Mar 3 check: Provider artefacts + Provider dim button both absent.
- Tests: 12 new — `TestProviderConcentration` (6), `TestProviderSegmentAnalysis` (6).

**Part 4 — covenant history method tagging** (`9a9bc84`)
- Added `method` field to every covenant dict in `compute_klaim_covenants` — describes how the current reading was computed: `direct` (uses Expected collection days), `proxy`, `age_pending`, `cumulative`, `stable`, `manual`. Paid vs Due's `pvd_method` variable existed locally but was never written to the dict; now it is.
- `_save_covenant_history` persists `method` on every append. `annotate_covenant_eod` checks method consistency on the `two_consecutive_breaches` rule — if prior record's method differs from current, status becomes `first_breach_after_method_change` + `method_changed_vs_prior: true` flag, chain does NOT escalate to EoD.
- Problem this solves: the backfilled Klaim Apr 13 entry (Mar tape, proxy method) combined with the Apr 15 tape (direct method) was producing a spurious Paid-vs-Due EoD on the two-consecutive rule — the methodology transition was being silently counted as a second breach. Now correctly reads as first direct-method breach.
- PAR60 EoD on Apr 15 remains correct (single-breach rule, methods matched across both dates — `age_pending` on both).
- Legacy history entries missing `method` are treated as unknown and not penalised (`bool(None and X)` short-circuits) — preserves backwards compat.
- Backfilled Klaim Apr 13 entries with real methods: PAR30/PAR60 = `age_pending`, Collection Ratio = `cumulative`, Paid vs Due = `proxy`, Parent Cash = `manual`.
- Tests: 5 new — `TestCovenantMethodTagging`.

**Part 5 — DataChat HHI context cleanup** (`5a3032b`)
- `chat_with_data` HHI context builder was labelling `key='group'` as "Provider" (stale from before the Provider column existed) and only iterating over `['group', 'product']`. AI chat was seeing Group HHI under a Provider heading and never seeing the actual Provider HHI. Fixed to iterate `['group', 'provider', 'product']` with correct labels.

**Totals:** 6 commits, **504 tests passing** (was 473). Every touched line traces to one of the five parts.

**Follow-ups still open (not in scope):**
- `DB path` (db_loader.py) doesn't carry Apr 15's new columns → wal_total, provider features naturally degrade to unavailable when `DATABASE_URL` is set. Same as older tapes. Fine.
- Multi-branch Group intra-drilldown (click-to-expand Provider breakdown inside Group table row) — marked as nice-to-have, not implemented.
- Stale worktrees (~50 in `git worktree list`) — user to undertake separately.

---

## Next Session Priorities

### Aajil — Remaining
- [ ] **Generate AI commentary** — executive summary, tab insights, data chat verification
- [ ] **Implement Loan/Borrower cohort toggle** (Cascade feature)
- [ ] **Implement With/Without Cure toggle** (Cascade feature, needs multi-snapshot)
- [ ] **Monthly vintage heatmap** (Cascade has 46 monthly, we have 17 quarterly)
- [ ] **Weekly collection curves** (Cascade Analytics Pro feature)

### Cascade-Inspired Platform Improvements
- [x] **Configurable DPD thresholds** — `dpd_thresholds` in config.json (Aajil: 7/30/60/90)
- [x] **GrowthStats component** — MoM/QoQ/YoY with partial-month skip (Aajil Traction tab)
- [x] **Traction dual view** — Volume + Balance toggle (Aajil Traction tab)
- [ ] **GrowthStats platform-wide** — apply to all company Overview tabs
- [ ] **Global "Display by" segmentation** — Cascade-style cross-tab filter

### Intelligence System — Remaining
- [ ] **Create first investment thesis** — `/thesis klaim` to test full pipeline

### External Intelligence — remaining after session 28
- [ ] **D7** — Scheduled external pollers (parked indefinitely — on-demand model preferred)
- [ ] **D2 for AI Commentary** — commentary currently injects zero mind context; adding citations would require rewriting the prompt to see Layer 2.5. Separate design discussion if analysts ask.
- [ ] **D5 for compliance_monitor + onboarding agents** — session 28 D5 extended memo_writer only. Add when a specific use case emerges (analyst + memo_writer + web_search is the primary flow for now).

### Klaim memo refresh (optional)
- [ ] **Regenerate Klaim Credit Memo** — the existing memo was generated before session-28 Finding #3 landed, so its Layer 2.5 was silently empty. A fresh run would pick up ~14.7K chars of healthcare_receivables content (MENA/GCC denial rates, account-debtor tape-gap methodology note). Not urgent; do when there's a reason to refresh (upcoming IC, new tape, material change). Cost: ~$3.50-6 + 3-5min.

---

## Completed — 2026-04-20 (session 29: Klaim data-room doubling investigation + 3 fixes)

User reported the Klaim Document Library showing 153 documents, suspected double-counting. Investigation surfaced three independent bugs compounding on top of each other plus a latent filesystem duplicate (full nested `dataroom/dataroom/` directory from the session-17 migration). Ended with Klaim at a healthy 76 documents, aligned registry/chunks, and three regression tests pinning each class of bug so we don't regress.

### Commit `25bb4c3` — initial three-bug fix (dedup + frontend chips)

- **Bug 1 — engine self-pollution via dotfile.** `_EXCLUDE_FILENAMES` in `core/dataroom/engine.py:82` only excluded `config.json`, `methodology.json`, `registry.json`, `index.pkl`. The LLM classifier wrote its cache to `data/{co}/dataroom/.classification_cache.json` — inside the very directory the ingest walker traverses — so every ingest picked it up as a JSON "document." Same story for `meta.json`, `ingest_log.jsonl`, and similar engine-state sidecars.
  - Fix: added six engine-written filenames to `_EXCLUDE_FILENAMES`, added a dotfile rejection check to `_is_supported` so anything starting with "." is skipped regardless of extension.
- **Bug 2 — within-pass hash dedup missing (ingest + refresh).** `existing_hashes` in `ingest()` was built once from the prior registry then never updated as new files were processed. Any file whose bytes existed at two paths (common when the same corporate doc is referenced from multiple deal folders — ESOP plans, cap tables, founder bios, audited accounts) produced two registry entries with different doc_ids, identical metadata. `refresh()` had the same shape (keyed on filepath, not hash).
  - Fix for `ingest()`: `existing_hashes[file_hash] = doc_record["doc_id"]` after every successful ingest; `duplicates_skipped` counter added for observability.
  - Fix for `refresh()`: new `registry_hashes` dict, updated as we go; second copies dedup-skipped.
- **Bug 3 — frontend CATEGORY_CONFIG stale.** `frontend/src/pages/research/DocumentLibrary.jsx` only had 9 of the ~28 backend `DocumentType` enum values mapped. Unmapped types fell through to the "Other" fallback — but each type still rendered as its OWN chip (keyed by raw enum value), so the UI showed a row of "Other (2), Other (2), Other (6), Other (14), Other (36)…" each labelled identically.
  - Fix: extended `CATEGORY_CONFIG` to 28 entries covering every backend enum (investor_report, fdd_report, financial_model, tax_filing, vintage_cohort, bank_statement, audit_report, cap_table, board_pack, kyc_compliance, unknown, …). Also fixed the latent `financial_statement` singular/plural mismatch.
- **Auto-healing pipeline.** New `dedupe_registry()` method on `DataRoomEngine` — collapses sha256-duplicate registry entries (keeps earliest `ingested_at`, deletes the rest along with their chunk files) and evicts registry entries whose filename is now on the exclusion list. Idempotent. Auto-called at the top of `ingest()` and `refresh()` so state converges on every run without manual intervention. Also exposed as `dataroom_ctl dedupe [--company X]` for explicit cleanup.

### Commit `???????` — refresh filepath-relink fix + regression tests

After the initial fix deployed successfully (Klaim dedup ran: 75 sha-duplicates removed, 2 excluded-filename entries removed, registry 153 → 76), and the user cleaned up a latent `data/klaim/dataroom/dataroom/` full duplicate directory on the server, a **fourth bug** surfaced: running `refresh` afterwards showed `removed=55 unchanged=21 duplicates_skipped=55` — 55 registry entries silently disappeared.

- **Bug 4 — refresh hash-match without filepath relink.** When a disk file's hash matched an existing registry entry but the entry's registered filepath was no longer on disk (because the user moved or deleted the old folder), my new within-pass hash-dedup logic in `refresh()` chose "dedup-skip" instead of "relink". The removal sweep at end-of-pass then dropped the entry because its filepath wasn't on disk. Net: the disk file is still there but no registry entry points to it, and no fresh ingest pulls it in → silent data loss.
  - Fix: when hash matches but registered filepath is NOT on disk, **update the entry's filepath to the new disk path** (relink). Only dedup-skip when the registered path IS still on disk (genuine second copy). New `relinked` counter in result payload. Removal sweep now honors relinked paths via a `relinked_disk_paths` set.
  - Recovered prod state by running a fresh `ingest` which re-scanned disk and created new registry entries for the 55 orphaned files. Final state: registry=76, aligned.

### Session 29 — other cleanup

- **qpdf-fixed `1.5.2.3.2 AFS_KT DMCC_2023.pdf`** — PyMuPDF was choking on a malformed xref ("`'L' format requires 0 <= number <= 4294967295`"). Ran `qpdf --linearize` on the server to rewrite the xref; `qpdf --check` passed, but PyMuPDF still failed after the fix (some deeper xref-stream issue qpdf didn't touch). Decided to skip that one doc rather than Chrome-print-roundtrip it. 75 of 76 docs indexed and searchable.
- **Nested `/opt/credit-platform/data/klaim/dataroom/dataroom/` directory removed.** 128MB leftover from session-17 product-level → company-level migration. `notebooklm_state.json` (only unique file in nested) moved up to parent. Tarball backup taken before `rm -rf`; can delete after a day or two of green UI.
- **12 new regression tests** in `tests/test_dataroom_pipeline.py` — three classes (`TestExclusions`, `TestWithinPassHashDedup`, `TestRefreshRelink`, `TestDedupeRegistry`) pin each bug class. 473 total tests passing (up from 461).
- **`.gitignore` check** — `.classification_cache.json`, `meta.json`, `ingest_log.jsonl` were already gitignored via the `data/*/dataroom/*` blanket pattern; no registry-negation leaks.

### Key facts

- **Klaim final state:** registry=76 chunks=76 aligned=true unclassified=3 index=ok. Was 153 at session start.
- **Dedup heuristics:** keep earliest `ingested_at` per sha256 group; exclusion list now 10 filenames + all dotfiles.
- **Deploy cadence:** main pushed 3 times this session (25bb4c3 initial fix, this EOD commit, plus the follow-up redeploy to pick up the refresh-relink fix).
- **Tests:** 461 → 473 (+12 dataroom pipeline tests). All green.

---

## Completed — 2026-04-20 (session 28 follow-up: Agents representation on Architecture page)

Quick focused follow-up after the main session 28 EOD. User asked whether
the Resources revamp / Architecture page surfaced the four agents — honest
audit showed they weren't represented (no stat tile, no box in the system
diagram, no capability card). One commit closes that gap.

### Commit `cc11f78` — Agents as first-class citizens on Architecture
- **Backend `/api/platform-stats`** — introspects:
  - `core/agents/definitions/*/config.json` — per-agent model, tool patterns, max_turns → returns `agents` array + `agents` count
  - `core.agents.tools.registry.tool_names()` — live `agent_tools` count (sidesteps drift between definitions and actual registration)
  - `data/_agent_sessions/*.json` — `agent_sessions` count
- **Architecture.jsx** —
  - 3 new amber stat tiles at the end of the row: Agents / Agent Tools / Sessions
  - New orange "Agents" box in the System Architecture diagram under Integration API, sublines name all 4 definitions (analyst, memo_writer, compliance_monitor, onboarding)
  - New "Agents" capability card between "Research Hub & Memos" and "Living Mind" with bullets for each definition + session tracking pointer

### Review
- 1 commit on `main`, pushed, verified on real GitHub via `ls-remote`.
- 115/115 pandas-and-anthropic-free tests pass in sandbox; full-suite verification needed on laptop (expected 428/428 — no tests added/removed).
- Applied the ls-remote verification lesson from earlier in the day.

---

## Completed — 2026-04-20 (session 28: Smoke test + Findings #1/#2/#3 + D1/D3/D4/D5 + D6 + D2 + legacy cleanup)

Session executed the real `external.web_search` smoke test the kickoff prompt
asked for, surfaced 3 bugs, shipped fixes, then cleared D1/D3/D4/D5 → D6 → D2
broader → legacy endpoint cleanup. 12 commits on `main`, all pushed.

### Part A — Real smoke test + 3 findings fixed
- `reports/web-search-smoke/smoke-test-results.md` — per-step pass/fail of the 15-step Chrome-driven smoke (Klaim DataChat → 3 pending entries → approve → promote → disk provenance verified). 13/15 clean pass; steps 6, 8, 14 surfaced the 3 findings below.
- `48809db` — **Finding #1** — `AgentRunner.TOOL_TIMEOUT_OVERRIDES_BY_PREFIX = {"external.": 180}` + `_timeout_for_tool()` classmethod. Default 30s was killing `external.web_search` at 30s even when the handler completed; runtime now gives `external.*` 180s. 2 regression tests.
- `c30ac17` — **Finding #2 + #3** — **(#3, highest-impact)** new `asset_class` field in every `config.json`; `build_mind_context()` prefers it over `analysis_type`. Before this, Layer 2.5 was silently empty for every company (Klaim's `analysis_type="klaim"` → looked for nonexistent `klaim.jsonl`). Now `healthcare_receivables.jsonl` with 14.7K chars reaches Klaim's AI context. **(#2)** CALL BUDGET clause added to `external.web_search` description so the agent makes ONE comprehensive call per request, not 3. 6 regression tests.

### Deferred items from kickoff — all except D7 landed
- `ff75f5f` — **D3** — 16 checks from `scripts/verify_external_intelligence.py` ported into `tests/test_external_intelligence.py`, grouped into 5 pytest classes. `isolated_project` fixture preserves the standalone harness's monkeypatch semantics. Standalone script retained.
- `a3b1ad1` — **D4** — `scripts/seed_asset_class_mind.py` writes 12 platform-docs entries across all 5 asset classes (bnpl, pos_lending, rnpl, sme_trade_credit, healthcare_receivables). Strict sourcing rule: every seed traces to CLAUDE.md or methodology_*.py (zero fabricated benchmarks). Idempotent. `.gitignore` extended for `_asset_class_mind/`, `_pending_review/`, `_platform_health.json` following the `_master_mind/` pattern.
- `684b66d` — **D1** — MindEntryRow's "Promote to Asset Class" inline form with asset-class dropdown + category dropdown + optional note. Wires to the real `/api/mind/promote` pipeline (provenance chain + promoted_to backlink).
- `e71d49f` — **D5** — memo_writer's `config.json` adds `external.*` to its tool pattern list. Memo drafts can now trigger pending-review web research mid-draft. Regression test locks it in.
- `465e0c4` — **D6 backend** — new `core/mind/framework_codification.py` module (`get_codification_candidates`, `mark_codified`, `codification_counts`). 2 new endpoints: `GET /api/framework/codification-candidates`, `POST /api/framework/codify/{entry_id}`. 5 regression tests.
- `36bd63d` — **D2 broader** — `/ai-executive-summary` response gains `asset_class_sources`; `ExecutiveSummary.jsx` renders `AssetClassSourcesFooter` component between Bottom Line and Key Findings.
- `d37c425` — **D2** — `/chat` response (Klaim + SILQ branches) gains `asset_class_sources`; `DataChat.jsx` renders collapsible "▸ Informed by N asset-class sources" footer with up to 25 clickable citations. Also fixed 5 latent executive-summary callers that passed company-shortname as `analysis_type` (same Finding #3 bug in a different location).

### Legacy + UI round 2
- `00fccf3` — **Legacy soft-flag Mind→Master button** replaced with real promotion via inline Master-category form. State refactor: `activeForm` (`null | 'asset_class' | 'master'`) replaces single `showPromoteForm`. Both promotion paths mutually exclusive.
- `dd0849c` — **Legacy PATCH /operator/mind/{id} endpoint removed** from `backend/operator.py` (the handler, `MindUpdate` model, `_promote_to_master` helper). Corresponding `updateOperatorMindEntry` removed from `api.js`. D6 API client helpers added in the same commit.
- `1f631db` — **D6 UI — Codification tab** (13th OperatorCenter tab) with stats row, pending/all filter, per-entry mark-codified form (optional commit_sha + framework_section inputs).

### Docs + lessons
- `0dd50b6` (session 28 round 1 close-out) + `80f4a49` (round 2 close-out) — CLAUDE.md + 5 new lessons across both rounds covering: Layer 2.5 asset_class keying trap, verification-harness blind spots, per-tool timeouts, call-budget clauses in tool descriptions, gitignored-source/tracked-index mismatches, UI buttons that must do what they say, not flattening context early, backwards-compat function-signature decisions, pragmatic scoping vs refactor purity, removing stale endpoints as you rewire.

### Outcome
- **461 tests passing** (was 436 at session start; +8 from Findings, +16 from D3, +1 D5 test, +5 D6 tests, +3 D2 sources tests).
- **12 commits on `origin/main`**: `48809db`, `c30ac17`, `ff75f5f`, `e71d49f`, `684b66d`, `a3b1ad1`, `88b1a55` (round-1 docs), `00fccf3`, `d37c425`, `465e0c4`, `0dd50b6` (round-1 close), `dd0849c`, `1f631db`, `36bd63d`, `80f4a49` (round-2 close).
- **Deferred remaining**: D7 (parked), D2 for AI Commentary (requires prompt rewrite — separate decision), D5 for compliance_monitor/onboarding agents (wait for use case).

---

## Completed — 2026-04-20 (session 27: Resources revamp + Architecture page + External Intelligence)

Session focused on the landing-page Resources section and grew into a four-layer
External Intelligence system built on trust-boundary semantics.

### Commit 1a (`20303e9`) — Resources section live cards + Architecture page
- `GET /api/platform-stats` — live counts (routes, DB tables, mind entries, framework sections, dataroom/legal/memos/tests). Introspected per-request.
- OperatorCard + FrameworkCard + new ArchitectureCard now pull live vitals instead of static text.
- `/architecture` page with component diagram per the Cocoon-AI skill guide (JetBrains Mono, dashed platform boundary, legend, bottom summary strip).
- Rebased onto main; adopted `/api/operator/*` route convention; dropped Cross-Co tab since main's Data Rooms tab shipped in the same slot.

### Commit 1b (`6bc621f`) — Feedback-loops diagram
- New `LoopsDiagram` SVG above the component diagram showing three loops: Ingestion (tape → Mind → Thesis → Briefing), Learning (correction → classify → rule → AI context), Intelligence (doc → entity → cross-co pattern → Master Mind). Each loop closes back on itself with a dashed arc + caption.
- Added "Self-Improvement Loops" CapabilityCard as the first card.

### Commit 2 (`1d17e31`) — External Intelligence four-layer system
- **Asset Class Mind** (new top-level store): `core/mind/asset_class_mind.py`, `data/_asset_class_mind/{analysis_type}.jsonl`. Categories: benchmarks, typical_terms, external_research, sector_context, peer_comparison, methodology_note.
- **Pending Review Queue**: `core/external/pending_review.py`, `data/_pending_review/queue.jsonl`. Trust boundary — external evidence never auto-writes to any Mind. approve() promotes to target with full citation provenance; reject() retains for audit.
- **Layer 2.5 in `build_mind_context()`**: AI context is now 6 layers (Framework → Master → Asset Class → Methodology → Company → Thesis). `analysis_type` auto-resolved from company config.
- **MasterMind extended**: `sector_context` category + generic `record()` method for external-origin fund-level landing.
- **Agent tool `external.web_search`**: wraps Anthropic's `web_search_20250305`. Every result lands in pending-review.
- Backend API: 8 endpoints under `/api/pending-review` and `/api/asset-class-mind`.
- OperatorCenter: new 9th tab "Pending" with approve/reject UI.

### Commit 3 (`aa5bed0`) — Promotion pipeline + Asset Classes browser
- `core/mind/promotion.py` — `promote_entry()` with full provenance tracking. Source entry is never moved; a copy is written to target with `metadata.promoted_from` chain preserved, and source's `promoted_to` list is appended.
- `POST /api/mind/promote` endpoint.
- OperatorCenter: new 10th tab "Asset Classes" with per-class browser + "↑ Promote to Master" button per entry.

### Follow-up fixes (same session)
- `b60d8d3` — analyst agent config exposes `external.*` tools (caught during smoke-test prep before first try).
- `b2c6afe` — `/api/platform-stats` test counter: tolerant regex for indented/async `def test_` patterns (was returning 0).
- `3b68f96` — Architecture diagram: loop-label crowding fix (topPad 60→90, font 10→11px, offset -8→-24) + overlong-arrow label overlaps (LLM/FX shortened to boundary edge; JWT arc raised dy -120→-180 and label dropped).
- `4952ea3` — `scripts/verify_external_intelligence.py`: 16-check self-contained verification harness. Ran 16/16 on user's laptop.
- `0ac4b4d` — `ScrollToTopOnNavigate` in App.jsx: React Router preserves scroll across navigations by default, causing pages to land mid-scroll. One-time reset on pathname change.

### Review
- 9 commits on branch `claude/resources-section-discussion-lMMAr`, all pushed.
- Verification: 16/16 on backend modules; live UI smoke on cards and Architecture page. Not yet merged to main as of this EOD wrap-up; user will merge then continue live.
- Deferred items (D1–D7) parked in "Next Session Priorities" above.

---

## Completed — 2026-04-19 (session 26.2: Stage 6 polish fix + CF SSE heartbeat + registry collision close-out)

Session picked up from session 26 summary context; executed three meaningful ship items and corresponding doc/ops cleanup.

### Ship items

- [x] **Stage 6 polish JSON truncation fixed via per-section parallelization (commit `163cba6`)** — `_polish_memo` and `_validate_citations` in `core/memo/generator.py` rewritten to per-section parallel loop at `LAITH_PARALLEL_SECTIONS` cap, `_MAX_TOKENS_POLISH_SECTION = 4000`, per-section `generation_meta["polish"]` block (attempted/polished/failed tallies). `polished=True` only when all polishable sections succeed; partial failures retain pre-polish content with error attribution. **428 tests passing** (added `test_polish_runs_per_section`, `test_partial_polish_failure_preserves_memo`). Backfill script `scripts/backfill_polish.py` created; 5 historical Klaim memos healed to v2 with `polished=True`.

- [x] **Cloudflare HTTP/2 + SSE transport resolved via 20s heartbeat (commit `f5d2a7b`)** — `backend/agents.py` `memo_generate_stream` emits `: keepalive\n\n` SSE comment lines when the event queue is idle ≥20s, keeping byte flow alive under CF Free's ~100s idle-proxy cap during long pipeline stages (research, polish each 60-90s). SSE comment lines are spec-ignored by clients and by the existing MemoBuilder manual-parser. 15-line patch, zero frontend change, zero infra. Verified end-to-end: fresh Klaim memo `13a852f9-4ba` completed in 2m35s, $5.27, polished=True, fully green browser UX. Path C (Cloudflare Tunnel) not needed.

- [x] **Registry.json git-tracking eliminated (commits `5844c92` + `fc66e7c`)** — dropped `!data/*/dataroom/registry.json` negation from `.gitignore`; untracked 4 per-machine registry files; server becomes authoritative on both rails (sync-data.ps1 AND git). Collision pattern from session 26 EOD structurally impossible going forward.

### Docs/ops hygiene

- [x] **CLAUDE.md cost estimate updated (commit `68d1bde`)** — `~$1.50-2.50` → `~$3.50-6.00` per full Credit Memo, with explanatory note on per-section fan-out's ~11× input-token trade-off.
- [x] **CLAUDE.md Stage 5.5/6 descriptions updated** — reflect per-section parallel semantics and partial-failure preservation.
- [x] **`tasks/lessons.md` — three new durable lessons recorded**: (1) `.gitignore` negations for server-local state are a collision trap, (2) `rm -rf` on non-existent path exits 0 silently (masking wrong-path bugs), (3) CF HTTP/2/3 SSE proxy-break with **Resolution footer** on (3) capturing the heartbeat pattern.
- [x] **Session 26 addendum commit (commit `86e964f`)** — post-EOD close-out documenting the registry collision recovery for future reference.
- [x] **Fresh verification memo `ad7cc868-a64` deleted from VPS** — was a disposable artifact from the Stage 6 verification; path convention drama surfaced (flat `klaim_UAE_healthcare/` not nested `klaim/UAE_healthcare/`) and captured as a lesson.
- [x] **Stale plan file `indexed-singing-whisper.md` removed** from `.claude/plans/`.

### Post-EOD addendum (after commit `959df8d`)

Reviewed two saved prompts from prior sessions to confirm their work had been absorbed:

- [x] **Prompt 1 verified: bidirectional orphan prune + CLI flush** — landed in session 25, commit `5025fe3`. `DataRoomEngine.prune()` at `engine.py:675`, auto-called in `ingest()`/`refresh()` with `orphan_chunks_deleted` surfaced in manifests, `prune` subcommand in `dataroom_ctl.py:200`, `_emit()` stderr flush fix at `dataroom_ctl.py:62`. Zero gaps remaining.
- [x] **Prompt 2 verified: `/operator` route collision** — resolved across `5025fe3` → `7ea5ea6` (nginx block removal) → `418c54c` (lesson captured) → `d0863ea` (Health tab path fix) → `cca4f80` (docs reconciliation). Backend router uses `/api/operator/*`, frontend `api.js:326-342` consumes it, nginx.conf has no `/operator` block. Bookmarked URLs + refresh both work.
- [x] **Classify residual closeout (commit `af87733`)** — VPS audit confirmed 12 unclassified docs across 4 companies (SILQ 3 / klaim 5 / Tamara 1 / Aajil 3 = 2.4% of 493) match session 26.1 addendum post-LLM residual exactly. Genuine `unknown` verdicts (Haiku confidence <0.6); re-running classify would cache-hit. Flipped the open checkbox to done with terminal-state rationale.

### Non-blocking carry-overs

- [ ] **Stale `blissful-albattani` worktree directory** — git admin record removed, filesystem directory held by an unknown Windows process. Session 26.3 re-attempted `rm -rf` and rename — both still returned `Device or resource busy`, confirming the lock persists across sessions. Harmless, ~100MB. Will delete on next reboot.
- [x] **`pd.to_datetime` "Deal date" log spam** — closed in session 26.3, commit `ea6aa99`. Root cause: pandas `UserWarning: Could not infer format, so each element will be parsed individually, falling back to dateutil`; Python's default warning formatter prints the source line along with the warning text, which is why backend logs showed the literal code. Added `format='mixed'` to 7 runtime "Deal date" call sites (`core/analysis.py` ×3, `core/loader.py`, `core/migration.py` ×2, `core/validation.py`, `core/db_loader.py`); `scripts/seed_db.py` left alone (not in request path). Verified identical output on mixed formats / NaN / empty / already-datetime series; no warning under `simplefilter('error')`.
- [x] **Second heartbeat sweep for `_stream_agent`** — closed in session 26.3, commit `328d503` (Approach A, belt-and-suspenders). `_stream_agent` refactored to mirror `memo_generate_stream`: background producer task drains `agent.stream()` into an `asyncio.Queue`; consumer loop wakes every 500ms and emits `: keepalive\n\n` after 20s idle. All 4 SSE endpoints (analyst, memo_regenerate_section, compliance, onboarding) now protected uniformly against CF's ~100s idle-proxy cut during slow tool calls. No frontend change; disconnect handling, token accounting, rate-limiter bookkeeping preserved.

### Verification

- Tests: **428 passed, 0 failed** (39.55s), zero regressions from per-section polish rewrite.
- Production: `laithanalytics.ai` live, all 4 dataroom audits aligned (493 docs total), backend healthy, memo generation fully green end-to-end.

---

## Completed — 2026-04-19 (session 26: Data Room Pipeline Hardening — production acceptance close-out)

Session closing out the full Data Room Pipeline Hardening & Quality Overhaul initiative via end-to-end Klaim Credit Memo acceptance checks on the Hetzner VPS.

### Acceptance Checks A / B / C
- [x] **Check A — backend shape** — `GET /memo-templates` returns `credit_memo` with 12 sections, `due_diligence=9`, `monitoring_update=6`, `amendment_memo=9`, `quarterly_review=5`.
- [x] **Check B — browser visual** — `/company/klaim/UAE_healthcare/research/memos/new` MemoBuilder step 2 renders 12 section toggles for Credit Memo after template-key drift fix (commit `a111667`).
- [x] **Check C — end-to-end memo smoke test** — memo `c1686e76-841` persisted to production with 12 sections, hybrid-v1 pipeline, Opus 4.7 + Sonnet 4.6 in `models_used`, both sidecars present (`research_packs.json` 2 entries, `citation_issues.json` 16 entries), $0.71 cost, 33K tokens. **Conditional pass** — `polished: false` due to a pre-existing (non-initiative) Stage 6 JSON truncation bug.

### Agent tool signature fixes (commit `0e82f35`)
Browser `POST /agents/.../memo/generate` returned "network error" because three `compute_*` functions were called with drifted signatures inside `core/agents/tools/analytics.py`. Patched via a fresh session given a detailed brief; fixed + tested + deployed.
- [x] **4 original TypeError/ImportError bugs fixed**:
  - `compute_cohorts(df, mult, date, as_of_date)` → `compute_cohorts(df, mult)` + result wrapped as `{"cohorts": [...]}`
  - `compute_returns_analysis(df, mult, date, as_of_date)` → `(df, mult)`
  - `compute_klaim_covenants` wrong module (`core.analysis` → `core.portfolio`) + signature `(df, mult, ref_date=...)`
  - `asyncio.get_event_loop()` raising in ThreadPoolExecutor thread on Python 3.12 → try/except new loop
- [x] **2 silent-correctness bugs found during audit**:
  - `compute_collection_velocity(df, mult, date, as_of_date)` — date routed through wrong slot
  - `compute_segment_analysis(df, mult, dimension)` — dimension routed through `as_of_date` positional (ignored silently)
- [x] **6 new tests added** — `tests/test_agent_tools.py` (5 Klaim handler smoke tests + 1 event-loop guard). **426 tests passing**.
- [x] **Deployed to Hetzner** — `a111667..0e82f35` fast-forward merge, backend rebuilt `--no-cache`, in-container smoke test confirmed cohort/returns/covenants tools return real data.

### Cloudflare SSE transport ✅ RESOLVED (session 26.2, commit `f5d2a7b`)
Browser memo-generate progress stream failed with `ERR_QUIC_PROTOCOL_ERROR` then `ERR_HTTP2_PROTOCOL_ERROR` — Cloudflare edge + SSE bug.
- [x] **Disabled HTTP/3 at Cloudflare** — eliminates QUIC+SSE incompatibility.
- [x] **Verified backend completes independently** — memo `c1686e76-841` persisted end-to-end on server despite browser SSE disconnect. Victory conditions verified directly from `v1.json` + `meta.json` + sidecars.
- [x] **HTTP/2 + SSE fixed via 20s heartbeat** — `backend/agents.py` `memo_generate_stream` emits `: keepalive\n\n` comment lines when the event queue is idle ≥20s, keeping byte flow alive under CF Free's ~100s idle-proxy cap. SSE comment lines are spec-ignored by clients, including the existing MemoBuilder manual-parser (falls through `event:`/`data:` check). 15-line patch, no frontend change, zero infra. Verified end-to-end: fresh Klaim memo `13a852f9-4ba` completed in 2m35s, $5.27 cost, polished=True, browser UX fully green — no error toast, smooth progress bar, auto-redirect to memo view. Path C (Cloudflare Tunnel) held in reserve if future SSE endpoints hit HTTP/2 protocol-cut failure modes distinct from idle-timeout.

### Follow-ups spawned (not blocking initiative close)
- [ ] **Memo Stage 6 polish JSON truncation** — spawned side-task. Opus 4.7 response cut mid-string when asked for all-12-sections JSON (~40K chars). Reproduces across recent memos. Recommended fix: per-section polish loop instead of one-shot JSON. Same pattern affects Stage 5.5 citation audit on large memos.
- [x] **Cloudflare HTTP/2 + SSE transport fix** — resolved via heartbeat patch (commit `f5d2a7b`, session 26.2). See section above.
- [ ] **Route-rename reverse-proxy checklist** — add nginx.conf audit to the three-layer rule.

### Initiative close-out — Data Room Pipeline Hardening & Quality Overhaul ✅
All three tiers shipped (session 24), rollout bugs patched (session 25), acceptance checks passed (session 26). Dataroom pipeline is self-diagnosing (audit, health endpoint, OperatorCenter tab), self-healing (prune, orphan eviction on ingest/refresh), and usefully classified (Haiku fallback with cross-company cache). Memo pipeline resilient to parallel-worker BaseException and template drift. Nginx reverse-proxy + React Router namespaces disambiguated (`/api/operator/*` vs SPA `/operator`).

### Post-EOD addendum: `.gitignore` registry.json negation removal (commits `5844c92` + `fc66e7c`)
The session-26 EOD commit (`8f8209e`) inadvertently staged `data/SILQ/dataroom/registry.json` — which collided with the server's untracked authoritative registry on `git pull` (`untracked working tree files would be overwritten by merge`). Root cause: `.gitignore` had `!data/*/dataroom/registry.json` that defeated session-24 Tier 1.2's intent of "server is authoritative registry owner".
- [x] **Server-side recovery on VPS** — backed up authoritative registry, reset to HEAD for merge, pulled, restored from backup. Audit confirmed all 4 companies aligned (SILQ 40/40, klaim 153/153, Tamara 271/271, Aajil 29/29).
- [x] **Root-cause fix: untrack 4 registries from git** — `git rm --cached` on SILQ, klaim, Tamara, Aajil registries (commit `5844c92`).
- [x] **Root-cause fix: drop `!data/*/dataroom/registry.json` negation from `.gitignore`** (commit `fc66e7c`). `check-ignore` confirms all 4 registries now match `data/*/dataroom/*` with zero negations.
- [x] **Collision pattern now structurally impossible** — sync-data.ps1 already excluded registry.json from push (Tier 1.2); .gitignore now excludes it from git entirely. Laptop pushes code. Server owns dataroom state.
- [x] **Remaining unclassified confirmed terminal (session 26.2)** — VPS audit shows exactly the post-LLM residual: SILQ 3, klaim 5, Tamara 1, Aajil 3 (12 total, 2.4% of 493 docs). Counts match session 26.1 addendum — LLM classify pass already ran; these are genuine `unknown` verdicts (Haiku confidence <0.6) on genuinely ambiguous docs. Re-running `classify --only-other --use-llm` cache-hits and returns same verdicts. Nothing further to fix.

---

## Completed — 2026-04-18 (session 25: Post-Session-24 rollout bugfix patch)

Follow-up patch after the session-24 rollout surfaced five production bugs on the Hetzner VPS.

### Fix 1 — Bidirectional orphan eviction + `prune` subcommand
- [x] **`DataRoomEngine.prune()` method** — sweeps chunk files on disk whose doc_id is not in registry. Returns `{"deleted", "kept", "chunk_dir_missing"}`. Idempotent.
- [x] **Auto-prune on `ingest()` and `refresh()`** — both call `prune()` right after registry load; `orphan_chunks_deleted` surfaces in result dict and `ingest_log.jsonl` extras.
- [x] **`dataroom_ctl prune [--company X] [--product Y]` subcommand** — iterates all companies if `--company` omitted. Exit codes: 0 success, 3 engine error.

### Fix 2 — CLI output ordering hygiene
- [x] **`_emit()` flushes stderr before and stdout after** — guarantees human summary lines (stderr) land before the JSON payload (stdout) when merged via `2>&1 | head -1`. Centralised fix applies to every subcommand.

### Fix 3 — Polish `temperature` deprecation (URGENT: degraded memo quality)
- [x] **Removed `temperature=0.3` from Stage 6 polish call** in `core/memo/generator.py:858` (Opus 4.7 rejects it with HTTP 400; memos were saved un-polished).
- [x] **Added tier-aware filter in `core/ai_client.complete()`** — `_STRIPS_TEMPERATURE_TIERS = {"polish", "judgment"}` silently drops the kwarg for tiers routing to Opus 4.7-era models. Belt-and-suspenders against future recurrences.
- [x] **Citation audit `temperature=0.1` left as-is** — it routes to Sonnet 4.6 which still accepts temperature; preserves explicit determinism. (User-confirmed scope.)
- [x] **Three new tests in `test_ai_client.py`** — asserts strip for polish/judgment, no-strip for structured.

### Fix 4 — Memo pipeline short-circuits after Stage 2 batch 1 (MOST CRITICAL)
Production evidence: `e2bc4a3f-d68` Klaim memo had 3/12 sections, no Haiku/Opus in `models_used`, no `research_packs.json`/`citation_issues.json` sidecars, `total_elapsed_s=39.86s` (too short for Stages 4+5 to have run).
- [x] **`_generate_parallel` catches `BaseException`** around `fut.result()` — SystemExit/GeneratorExit (plausible source: SSE client disconnect) no longer tears down the as_completed loop.
- [x] **Backfill of null slots** — sections whose future never returned a result get explicit error-object placeholders so template order is preserved and downstream stages always see a full list.
- [x] **`_generate_parallel` returns `(sections, errors)` tuple** — errors are attributed with `stage: parallel_worker | parallel_future | parallel_backfill`.
- [x] **`_generate_judgment_sections` wraps synthesis in per-section try/except** — one Opus failure doesn't block subsequent judgment sections. Returns additional `errors` list.
- [x] **Error-gate logic inverted** — Stage 5.5 (citation audit) and Stage 6 (polish) now run whenever `any(s.content for s in sections)` rather than being blocked by ANY earlier error. Critical behavior change that directly fixes the production symptom.
- [x] **Terminal-error path** — if all sections fail, memo saved with `status="error"`; `pipeline_error` SSE event emitted for UI.
- [x] **New SSE event types** — `section_error` (per-section failures with stage attribution), `pipeline_error` (all sections failed).
- [x] **Regression test `test_parallel_failure_does_not_truncate_pipeline`** — injects SystemExit in one worker, asserts 12 sections present, polish ran, error recorded with stage attribution, `section_error` event emitted.

### Fix 5 — `/operator` backend route collision with SPA route
- [x] **Backend router prefix renamed** — `backend/operator.py` `/operator` → `/api/operator`.
- [x] **Three intelligence routes moved** — `backend/intelligence.py` `/operator/briefing`, `/operator/learning`, `/operator/learning/rules` → `/api/operator/*`.
- [x] **Frontend API callers updated** — all 10 `/operator/*` references in `frontend/src/services/api.js` → `/api/operator/*`.
- [x] **CLAUDE.md endpoints table updated** — with note explaining why the rename happened.
- [x] **Auth middleware verified** — `/api/operator/*` doesn't accidentally match `/api/integration/*` skip prefix.

### Fix 6 — Dockerfile `COPY scripts/`
- [x] Already landed as commit `286cf18` on 2026-04-17 — no action this session.

### Verification
- [x] Full test suite: **420 passed, 0 failed** (baseline was 268+). Added 4 new tests (3 for ai_client, 1 for memo pipeline).
- [x] Fix 1 + Fix 2 verified locally via dataroom_ctl CLI (orphan created, detected, pruned, idempotent).

### Post-eod follow-up commits (surfaced during production smoke test)
- [x] **Fix 5b: Remove nginx `/operator` proxy block** (`docker/nginx.conf`, commit `7ea5ea6`) — the Python route rename was not enough. `docker/nginx.conf` had an explicit `location /operator { proxy_pass http://backend:8000 }` block baked into the frontend image at build time, forwarding `/operator` to backend regardless of what Python routes existed. Backend returned FastAPI's `{"detail":"Not Found"}` instead of the SPA falling through. Deleted the block so the existing `try_files $uri $uri/ /index.html` SPA fallback catches `/operator`. `/api/operator/*` still routes via the `/api/` proxy block.
- [x] **Lesson captured: route-rename must audit reverse proxy config** (`tasks/lessons.md`, commit `418c54c`) — three-layer checklist: (1) Python route decorators, (2) frontend callers, (3) reverse proxy config. Missing any one leaves the bug live.
- [x] **Fix: OperatorCenter Health tab stale dataroom path** (`backend/operator.py`, commit `d0863ea`) — line 102 still referenced `data/{company}/{product}/dataroom/registry.json` (pre-session-17 path). Session 17 moved datarooms to company-level; legal and mind paths were updated but the operator health-matrix dataroom probe was missed. Symptom: every company showed "— DOCS" and "Data room not ingested" info chip in the Health tab. One-line fix using `Path(DATA_DIR) / company / "dataroom"` to match the rest of the file.

---

## Completed — 2026-04-18 (session 24: Data Room Pipeline Hardening & Quality Overhaul)

### Tier 1 — Root-cause fixes (eliminate this session's hurdles)
- [x] **Tier 1.1: engine.ingest() dedup-skip fix** — verify chunks file exists on disk before trusting registry; evict orphan registry entries so the file re-ingests. Same fix applied to `refresh()`. Result field `orphans_dropped` reports count. Kills the "0 new, 40 skipped" bug.
- [x] **Tier 1.2: Stop syncing registry.json from laptop** — `scripts/sync-data.ps1` `$rootFiles` filter excludes `registry.json`. Server becomes authoritative registry owner.
- [x] **Tier 1.3: deploy.sh alignment check** — replaced "chunks dir non-empty → skip" with registry-vs-chunks alignment (`registry_count == chunk_count`). Catches first-time setup, post-sync, partial failures, orphans.
- [x] **Tier 1.4: deploy.sh git stash removed** — silently eating ingest artifacts. Now git-pull failures stop the deploy (explicit).
- [x] **Tier 1.5: Startup dependency probe** — `backend/main.py` lifespan imports 5 optional deps (pdfplumber, docx, sklearn, pymupdf4llm, pymupdf), writes `data/_platform_health.json`, logs ERROR for missing.
- [x] **Tier 1.6: Surface silent import failures** — `_build_index`/`_search_tfidf` now log WARNING and set `index_status` flag in `meta.json` instead of bare `except ImportError: return`.
- [x] **Tier 1.7: SSH keepalive** — `sync-data.ps1` sets `-o ServerAliveInterval=30 -o ServerAliveCountMax=20` on every ssh/scp invocation.

### Tier 2 — Operational tooling
- [x] **Tier 2.1: scripts/dataroom_ctl.py unified CLI** — 6 subcommands (audit, ingest, refresh, rebuild-index, wipe, classify). JSON on stdout, human text on stderr. Exit codes 0/1/2/3/4 for automation. Wraps existing DataRoomEngine methods.
- [x] **Tier 2.2: engine.audit() + /dataroom/health endpoint** — returns structured health per company (registry_count, chunk_count, aligned, missing_chunks, orphan_chunks, unclassified_count, index_status, index_age_seconds, last_ingest). Two endpoints: `/dataroom/health` (all companies) + `/companies/{co}/products/{p}/dataroom/health`.
- [x] **Tier 2.3: ingest_log.py manifest writer** — structured JSONL at `data/{co}/dataroom/ingest_log.jsonl`. Records duration, counts, errors, index status, classifier fallback use. Append-only audit trail.
- [x] **Tier 2.4: deploy.sh uses dataroom_ctl** — replaced inline `python -c "..."` ingest with `docker compose exec -T backend python scripts/dataroom_ctl.py ingest --company X`.
- [x] **Tier 2.5: OperatorCenter Data Rooms tab** — 8th tab in `/operator` with per-company cards showing Registry/Chunks/Missing/Orphans/Unclassified/Index stats. Colored borders (teal=aligned, gold=misaligned, red=error). Repair command hint per card.
- [x] **Engine methods: rebuild_index_only() + wipe()** — rebuild_index_only() re-runs TF-IDF from existing chunks without re-parsing; wipe() deletes registry/chunks/index/meta (source files preserved); returns counts.

### Tier 3 — Classification quality
- [x] **Tier 3.1: Expanded rule-based classifier** — 5 new DocumentType enum values (BANK_STATEMENT, AUDIT_REPORT, CAP_TABLE, BOARD_PACK, KYC_COMPLIANCE), UNKNOWN distinct from OTHER. New filename rules (bank statement, EY/KPMG audit, cap table, board pack, KYC, zakat). New content rules (opening balance, audit opinion, fully diluted, board minutes). New `_SHEET_RULES` for Excel tab-name inspection (vintage/covenant/cap table/P&L).
- [x] **Tier 3.2: classifier_llm.py Haiku fallback** — invoked only when rules return OTHER. SHA-256 keyed cache at `data/{co}/dataroom/.classification_cache.json` (same file never triggers a second LLM call, even cross-company). Strict JSON parsing with fence tolerance, confidence < 0.6 → UNKNOWN. Lazy import of `core.ai_client` so rule classifier works without AI client.
- [x] **Tier 3.3: LLM wired into ingest + --only-other CLI flag** — `engine._ingest_single_file()` calls Haiku fallback when rule result is OTHER, confidence threshold 0.6, low-confidence → UNKNOWN. `dataroom_ctl classify --only-other --use-llm` re-classifies without re-parsing for retroactive fixes.

### Verification
- [x] **416 tests passing** (0 new failures)
- [x] **Classifier spot-check** — 10 test cases including new patterns (bank_statement, audit_report, cap_table, board_pack, kyc_compliance, tax_filing via zakat), sheet-name rules (vintage_cohort via sheets), opaque filenames falling through to OTHER for LLM fallback
- [x] **Orphan eviction smoke test** — synthetic registry with 1 orphan; `audit` flagged `missing=1`; `ingest` logged eviction + reported `orphans_dropped=1`; registry correctly rewritten
- [x] **Local audit CLI** — detected real post-sync state (registries present, chunks absent), exit code 1

### Files added
- `core/dataroom/classifier_llm.py` (190 lines) — Haiku LLM fallback with cache
- `core/dataroom/ingest_log.py` (146 lines) — structured manifest writer
- `scripts/dataroom_ctl.py` (361 lines) — unified operator CLI

### Files modified
- `core/dataroom/engine.py` — orphan eviction in ingest()/refresh(), `audit()`, `wipe()`, `rebuild_index_only()`, `_meta_status()`, logger-instrumented import failures
- `core/dataroom/classifier.py` — 5 new enum values, new filename/content/sheet rules
- `backend/main.py` — `/dataroom/health` endpoints + startup dep probe
- `deploy.sh` — alignment check, git stash removed, dataroom_ctl invocation
- `scripts/sync-data.ps1` — exclude registry.json, SSH keepalive
- `frontend/src/pages/OperatorCenter.jsx` — Data Rooms tab
- `frontend/src/services/api.js` — `getDataroomHealthAll/One`

---

## Completed — 2026-04-17 (session 23: Hybrid Memo Pipeline + 5 Quality Enhancements)

### Platform-wide content improvements (morning)
- [x] **Entity extractor overhauled** — ~80 patterns across all 7 types (was ~20). Added COUNTERPARTY (35 institutions incl. Goldman/HSBC/Deloitte/insurance companies), THRESHOLD (11 patterns), flexible natural-language METRIC patterns. Confidence A/B differentiation. Real-text test extracts 11 entities vs ~1 before.
- [x] **Mind seeding** — Master Mind 7→26 entries (+preferences, IC norms, cross-company patterns, writing style), SILQ 0→14 entries, Aajil 0→14 entries, Ejari 0→11 entries. Platform total: 40→98 mind entries.
- [x] **Framework updates** — FRAMEWORK_INDEX: added Aajil row, updated Klaim/SILQ fn/test counts. ANALYSIS_FRAMEWORK: Section 21 (Intelligence System) added, Section 3 expanded with Ejari/Tamara/Aajil asset class subsections, stale mind path fixed.
- [x] **Ejari methodology expanded** — 2→12 sections covering all dashboard tabs with L1-L5 hierarchy tagging.
- [x] **Klaim methodology** — added CDR/CCR (L3) and Facility-Mode PD (L5) — 2 previously undocumented tabs now registered.
- [x] **Klaim memo cleanup** — deleted failed stub `84e15708-cf3` (9 of 12 sections empty).

### Dormant feature activation
- [x] **TAPE_INGESTED event payload** — was `metrics: {}` (killed entity extraction, compilation, thesis drift). Now extracts 11 metrics from DataFrame with column guards for Klaim + SILQ.
- [x] **DataChat feedback pipeline** — thumbs-down with no correction now records negative signal as finding in CompanyMind (was silently dropped due to `if original and corrected` guard).
- [x] **Graph-aware scoring** — `query_text` now passed to `build_mind_context()` from chat endpoints. Layers 2 + 4 use KnowledgeGraph scoring when user question provided.
- [x] **MemoBuilder agent save** — SSE endpoint now runs the full pipeline + calls `MemoStorage.save()` + emits `saved` event with `memo_id` (was fire-and-forget with no persistence).
- [x] **Entities in AI prompts** — `entities.jsonl` added to `_FILES` in company_mind.py + included in `_TASK_RELEVANCE` for commentary/executive_summary/chat/memo/research_report/default.
- [x] **Dead code removal** — `extract_insights` import removed from main.py. `searchKnowledge` dead api.js export removed.

### UI bug fixes
- [x] **--accent-gold CSS aliases** — 142 broken references across 30 files were falling through to transparent (CSS variable never defined). Added `--accent-gold/teal/red/blue` aliases in tokens.css. Continue/Generate/New Memo buttons now visible.
- [x] **MemoBuilder "0 sections" bug** — backend returns template metadata without sections array; frontend now merges with FALLBACK_TEMPLATES to hydrate sections.
- [x] **Agent tool name dots** — Anthropic API rejects dots in tool names (`analytics.get_par_analysis`). `to_api_schema()` translates dots→underscores on way out; `get_handler()` matches both forms on way in.
- [x] **Analytics Bridge multi-company** — `'Purchase value'` KeyError for non-Klaim memos. Added `is_aajil` flag + Aajil-specific branches in all 5 builders (portfolio_analytics, credit_quality, concentration, stress, covenants).
- [x] **Analytics Bridge aux sheets** — `_load_data()` now returns aux sheets for Aajil multi-sheet xlsx (Payments, DPD Cohorts, Collections). Collection Rate went from 0.9% → 87.3% (matches CLAUDE.md).
- [x] **Tool description labels** — `_TOOL_DESCRIPTIONS` was keyed by short names; Claude sends back underscored full names. New `_describe_tool()` helper strips module prefixes.

### Hybrid 6-stage memo generation pipeline (afternoon)
- [x] **`core/ai_client.py`** — central Anthropic client factory with retry/backoff (max_retries=3, SDK exponential backoff), tier routing, prompt caching helpers, cost estimation. Five tiers: auto (Haiku), structured (Sonnet), research (Sonnet), judgment (Opus 4.7), polish (Opus 4.7). Env overrides via `LAITH_MODEL_*`. Fallback chains (Opus 4.7 → 4.6 → 4.20250514) on NotFoundError.
- [x] **`core/memo/generator.py` full refactor** — 6-stage pipeline:
  - Stage 1: Context assembly (no API calls)
  - Stage 2: 9 structured sections in parallel via ThreadPoolExecutor (cap `LAITH_PARALLEL_SECTIONS=3`)
  - Stage 3: 1 auto section (Haiku)
  - Stage 4: Short-burst agent research packs for 2 judgment sections (Sonnet, 5-turn cap)
  - Stage 5: Judgment synthesis (Opus 4.7) — sequential, with research packs
  - Stage 5.5: Citation validation pass (Sonnet) — flags unverifiable citations
  - Stage 6: Whole-memo polish pass (Opus 4.7) — preserves metrics/citations, resolves contradictions
- [x] **`core/memo/agent_research.py`** — short-burst agent session runner. Returns structured JSON research pack per judgment section (key_metrics, quotes, contradictions, recommended_stance, supporting_evidence). Lenient parser with 3-strategy fallback. `format_pack_for_prompt()` + `record_memo_thesis_to_mind()` helpers.
- [x] **Memo storage sidecar** — `_research_packs` → `research_packs.json`, `_citation_issues` → `citation_issues.json`. Transient fields stripped from `v{N}.json`. Sidecar only written on first save (immutable audit trail).
- [x] **Hybrid metadata in meta.json** — generation_mode, polished, models_used, total_tokens_in/out, cost_usd_estimate.
- [x] **Central client adoption** — migrated 8 direct `messages.create` call sites: 5 in backend/main.py (commentary, exec-summary, tab-insight, 2 chat endpoints), core/legal_extractor.py (Sonnet/Opus split preserved), core/research/query_engine.py, core/reporter.py. All inherit retry/backoff.
- [x] **Extended prompt caching** — tool definitions now cached via `cache_last_tool()` in agent runtime (both `run()` and `stream()`).
- [x] **Agent runtime uses central client** — `_get_client()` routes through `core.ai_client.get_client()` for retry config.
- [x] **memo_writer model switch** — claude-opus-4-6 → claude-sonnet-4-6 (4× rate limit headroom, 5× cheaper for agent research).

### 5 Quality Enhancements (session 23 extended)
- [x] **#1 analytics.get_metric_trend tool** — cross-snapshot time series for research packs. 19 supported metrics, iterates available snapshots (cap 12 most recent), tolerates Aajil aux, handles summary-only types gracefully. Registered as tool #42.
- [x] **#2 Citation validation pass** — `MemoGenerator._validate_citations()` runs Sonnet against all memo citations + data room excerpts. Returns structured `_citation_issues` list fed to polish pass. SSE emits `citation_audit_start`/`citation_audit_done` events.
- [x] **#3 Research pack sidecar storage** — `MemoStorage.save()` extracts `_research_packs` and `_citation_issues`, writes to separate JSON sidecars (immutable on first save).
- [x] **#4 Thesis recording to Company Mind** — `record_memo_thesis_to_mind()` called from both memo save paths (agent SSE + legacy). Writes agent-recommended stance + supporting metrics to CompanyMind findings with `source_docs: ["memo:{id}"]` provenance.
- [x] **#5 Contradiction handling in polish** — polish prompt surfaces every contradiction from research packs with explicit resolve/flag rules ("prefer tape data over data room narrative"). Citation issues also surfaced for qualify-or-remove.

### Tests + verification
- [x] **60 new tests** — tests/test_ai_client.py (18), tests/test_memo_agent_research.py (15), tests/test_memo_pipeline.py (8), tests/test_memo_enhancements.py (19)
- [x] **All tests pass** — 416 total (356 original + 60 new, up from 356 at session start). Updated `test_total_tool_count` from 41→42.

---

## Completed — 2026-04-16 (session 22: Dataroom filepath cross-platform fix)

- [x] **Fix document view "Source file not found"** — view endpoint now resolves relative paths against project root and normalizes separators
- [x] **Cross-platform filepath normalization** — `_normalize_filepath()` in engine.py, applied to registry reads, disk scan comparisons, removal detection, new record storage
- [x] **All 3 companies fixed** — Klaim (relative backslash), Tamara (relative backslash), Aajil (absolute Windows path) — all affected by same bug
- [x] **Re-ingest matching fix** — path comparison now normalized, prevents unnecessary re-processing when ingesting from Linux vs Windows

---

## Completed — 2026-04-16 (session 22b: NotebookLM Removal)

- [x] **Delete NLM files** — notebooklm_bridge.py, synthesizer.py, test_notebooklm_bridge.py, 3 notebooklm_state.json
- [x] **Simplify dual_engine.py** — rewritten as Claude-only wrapper (374→112 lines)
- [x] **Remove NLM endpoints** — 4 endpoints deleted from main.py, operator health probe removed
- [x] **Clean frontend** — ResearchChat.jsx rewritten (760→290 lines), DocumentLibrary NLM strip removed, 3 API functions removed
- [x] **Remove notebooklm-py dependency** — removed from requirements.txt
- [x] **Clean all docs** — CLAUDE.md, ANALYSIS_FRAMEWORK.md, FRAMEWORK_INDEX.md, lessons.md, todo.md, eod.md
- [x] **Verify** — 287 tests pass, zero "notebooklm" references in codebase, net -2,748 lines

---

## Completed — 2026-04-15 (session 21: Tamara Data Room + Credit Memo)

- [x] **Tamara data room ingested** — 134 files from `data/Tamara/dataroom/`, 4,076 chunks, 1,744 pages, 9 document types classified
- [x] **Document classification** — vintage matrices (51 files) confirmed as whole-book data, not facility-specific; HSBC reports + legal DD identified as facility-specific
- [x] **Placeholder Tamara memo deleted** — removed `reports/memos/Tamara_KSA/0ae5cbe3-095/`
- [x] **Tamara Credit Memo v2 generated** — `f3af2d4e-b88`, 12 AI sections (~55K chars), 45 data room citations, covers both KSA + UAE
- [x] **EOD process improved** — Step 1b added to check for untracked data artifacts (registry.json, mind entries, memos)
- [x] **Recovered lost session 19 work** — found registry.json in `nifty-chebyshev` worktree, confirmed all code changes were already merged (0 unique commits)
- [x] **All data artifacts committed** — registry.json, memo files committed to main (prevents worktree cleanup loss)
- [x] **Production data sync pipeline** — `scripts/sync-data.ps1` (laptop → server via scp), `deploy.sh` auto-ingest (detects missing chunks), EOD auto-detects registry changes
- [x] **Deploy.sh hardened** — auto `--no-cache` when backend/core code changes, dataroom auto-ingest via Python import (bypasses HTTP auth), /health endpoint added
- [x] **docker-compose.yml** — data volume changed from read-only to read-write (ingest needs to write chunks)
- [x] **Production datarooms synced and ingested** — Tamara (268 files), Klaim (152), Aajil (26)
- [x] **Repayment Lifecycle tab** — ETL parser, enrichment, dashboard (KPI cards + bar chart + pie), KSA 18 tabs, UAE 14 tabs
- [x] **Customer Behavior tab** — repeat customer analysis, default rate by engagement tier, pie chart composition
- [x] **Tamara JSON snapshots regenerated** — KSA: 40 repayment + 40 behavior rows, UAE: 18 + 20 rows
- [x] **Credit Memo updated** — portfolio_analytics (7.7K chars) and credit_quality (5.3K chars) regenerated with lifecycle/behavior data

---

## Completed — 2026-04-15 (session 20b: Platform-Wide Enhancement Sprint — 17 items across 4 phases)

**Phase 1 — Quick Wins:**
- [x] **CSV tape classifier fix** — added text-preview rule in `classifier.py` for loan column headers → PORTFOLIO_TAPE
- [x] **Data room refresh default path** — `POST /dataroom/refresh` now defaults to `data/{company}/dataroom/`
- [x] **Amendment memo template** — 9-section `amendment_memo` added to `templates.py`
- [x] **PV-adjusted LGD** — `_compute_pv_adjusted_lgd()` discounts recoveries by time-to-recovery (8% annual), integrated into EL output
- [x] **Shared components** — VintageHeatmap + CovenantTriggerCard extracted from TamaraDashboard to shared components

**Phase 2 — Intelligence System:**
- [x] **6 slash commands** — /morning, /thesis, /drift, /learn, /emerge, /know
- [x] **Graph-aware mind context** — `build_mind_context()` accepts `query_text`, uses KnowledgeGraph for Layers 2+4
- [x] **ThesisTracker frontend** — 8th tab in OperatorCenter (company selector, conviction gauge, pillar cards, drift alerts, change log)

**Phase 3 — Tamara P1:**
- [x] **Trigger trends heatmap** — new `trigger-trends` tab (CSS grid, x=months, y=triggers, color=status)
- [x] **Payment waterfall** — new `facility-waterfall` tab (horizontal bar chart + detail table from HSBC data)
- [x] **Dilution time-series** — enhanced dilution tab with vintage line chart
- [x] **Seed Tamara Company Mind** — 6 findings + 4 data quality + 1 IC feedback + relations at company level

**Phase 4 — Platform Capabilities:**
- [x] **3 research report builders** — Klaim, SILQ, Ejari dedicated builders + dispatch + TOC in research_report.py
- [x] **Report template customization** — `section_order` + `excluded_sections` params; tape data now loaded for reports
- [x] **Self-service onboarding** — `backend/onboarding.py` (validate + create org/product/API key), `Onboarding.jsx` (4-step form), route `/onboard`
- [x] **Facility-mode PD** — `compute_facility_pd()` Markov chain (DPD bucket transitions, forward PD), endpoint `/charts/facility-pd`

**Path migration audit:**
- [x] Tamara mind files moved from product-level to company-level (`data/Tamara/mind/`) per parallel branch structural change
- [x] All code verified: no hardcoded product-level mind/legal paths in changes

---

## Completed — 2026-04-15 (session 20a: Directory restructure — legal/ and mind/ to company level)

- [x] **Move legal/ to company level** — `data/{company}/legal/` (was `data/{company}/{product}/legal/`). `get_legal_dir()` updated, `'legal'` added to `_NON_PRODUCT_DIRS`.
- [x] **Move mind/ to company level** — `data/{company}/mind/` (was `data/{company}/{product}/mind/`). Updated 13 source files + 1 test: CompanyMind, ThesisTracker, listeners, intelligence, kb_query, master_mind, briefing, graph, compiler, operator, backend/intelligence.
- [x] **Klaim files moved** — `data/klaim/UAE_healthcare/legal/` → `data/klaim/legal/`, `data/klaim/UAE_healthcare/mind/` → `data/klaim/mind/`
- [x] **306 tests passing** — all green after changes

---

## Completed — 2026-04-15 (session 19 continued: Aajil Phase B — Live Tape Analytics)

**Phase B — Live tape analytics from real xlsx (1,245 deals):**
- [x] **Multi-sheet loader** — `load_aajil_snapshot()` reads Deals + Payments + DPD Cohorts + Collections
- [x] **11 compute functions** — summary, traction, delinquency, collections, cohorts, concentration, underwriting, yield, loss_waterfall, customer_segments, seasonality
- [x] **Validation module** — `validate_aajil_tape()` with 13 checks
- [x] **38 new tests** (306 total) — all passing
- [x] **Backend wiring** — `AAJIL_CHART_MAP`, generic chart endpoint, tape-aware /summary, AI context builder
- [x] **Dashboard refactored** — all tabs fetch from chart endpoints, real charts for Traction/Delinquency/Collections/Cohort/Concentration/Yield/Loss Waterfall
- [x] **Dataroom ingested** — 13 new files (financials, tax returns, budget, debt overview)

**Cascade Debt alignment (metric mapping):**
- [x] **Volume = Principal Amount** (not Bill Notional) — all 9 functions updated, now matches Cascade within 0.1%
- [x] **Collection rate = Realised / Principal** (was Realised / (R+Recv)) — now 87.3% (was 80.6%)
- [x] **MoM growth = +32.36%** — exact match with Cascade (was -74.8% due to partial month)
- [x] **Balance = per-vintage outstanding** (was cumulative, incorrect)
- [x] **Delinquency bucketing** — fixed fractional overdue values (round to nearest int)

**Key tape findings:**
- ALL 19 write-offs are Bullet deals (zero EMI write-offs)
- EMI adoption ramp: 0% (2022) → 88% (2026) — structural shift reducing default risk
- Yield stabilized at ~10% since 2024Q2
- Loss concentrated in 5 vintages (2023Q3-2024Q3), gross loss rate 1.18%
- Top customer = 9.5% of volume, HHI = 0.0205 (well diversified)

---

## Completed — 2026-04-14 (session 19: Aajil Onboarding + Cascade Debt Intelligence)

**Aajil — New portfolio company onboarded (SME raw materials trade credit, KSA):**
- [x] **Cascade Debt platform research** — explored entire app.cascadedebt.com: Analytics (Traction, Delinquency, Collection, Cohort), Analytics Pro (Weekly Collection Rates), Administration. Mapped all features, filters, and data model.
- [x] **Investor deck analysis** — read 47-page Aajil pitch deck, extracted all KPIs, underwriting criteria, trust score system, financial thresholds, collections process
- [x] **Directory structure + config** — `data/Aajil/KSA/config.json` (analysis_type: "aajil", 13 tabs, dpd_thresholds: [7,30,60,90])
- [x] **Data extraction script** — `scripts/prepare_aajil_data.py` produces 14-section JSON snapshot
- [x] **Analysis module** — `core/analysis_aajil.py` (parser + enrichment + `get_aajil_summary()`)
- [x] **Static methodology** — `data/Aajil/KSA/methodology.json` (11 L1-L5 sections for SME trade credit)
- [x] **Backend wiring** — `/aajil-summary` endpoint, `/summary` routing, `/methodology` routing, `/date-range` routing, AI executive summary context builder (`_build_aajil_full_context`), section guidance
- [x] **Dashboard** — `frontend/src/pages/AajilDashboard.jsx` (29KB, 13 tabs: Overview, Traction, Delinquency, Collections, Cohort Analysis, Concentration, Underwriting, Trust & Collections, Customer Segments, Yield & Margins, Loss Waterfall, Covenants, Data Notes)
- [x] **Frontend routing** — `TapeAnalytics.jsx` aajil branch, `api.js` getAajilSummary, Home.jsx country metadata, DataChat + ResearchChat suggested questions
- [x] **GrowthStats component** — Cascade-inspired MoM/QoQ/YoY growth rates (inline in AajilDashboard, reusable pattern)

**Cascade Debt learnings documented:**
- [x] DPD 7 threshold as early warning (implemented via config.json dpd_thresholds)
- [x] Traction dual view (Volume + Balance) — built as Aajil tab
- [x] Vintage Analysis toggles (Loan/Borrower, With/Without Cure) — documented for Phase B
- [x] Weekly Collection Rates (Total vs Principal) — documented for Phase B
- [x] "Display by" global segmentation — documented for future

**Verification:** 268 tests passing, all 3 backend endpoints working (companies, summary, aajil-summary, methodology)

---

## Completed — 2026-04-14 (session 18: Bug fixes)

**MemoEditor blank on mobile:**
- [x] **Fix flex-direction on mobile** — main layout container defaulted to `flex-direction: row`, causing horizontal section tabs and content panel to lay side-by-side on mobile. Content got squeezed to 0 width and clipped by `overflow: hidden`. Fixed by adding `flexDirection: isMobile ? 'column' : 'row'`.

**Memo section edit/regenerate crash:**
- [x] **Fix missing arguments in update_section calls** — both PATCH (edit) and POST (regenerate) endpoints called `_memo_storage.update_section(memo_id, section_key, content)` but method requires `(company, product, memo_id, section_key, content)`. TypeError on any attempt to edit or regenerate a section. Fixed at `backend/main.py:3802` and `:3842`.

---

## Completed — 2026-04-14 (session 17 continued: April tape + platform enhancements)

- [x] **April 14 tape assessment** — 357 deals (active-only extract), 5 new columns incl Expected collection days + Collection days so far. Moved to staging/ pending Klaim scope confirmation.
- [x] **Direct DPD in compute_par()** — when Expected collection days available, computes exact DPD per deal (replaces shortfall proxy). Falls back to proxy for older tapes.
- [x] **DSO Operational enhancement** — per-deal `true_dso - expected_collection_days` when available
- [x] **Paid vs Due covenant temporal filtering** — filters to deals with expected payment date in period
- [x] **Concern list updated** — expected payment date gap marked PARTIALLY_ADDRESSED, payer gap still OPEN
- [x] **Data room cleanup** — refreshed registry (87→76 docs, 11 pruned), search index rebuilt
- [x] **Document Library enhancements** — category filters, colored badges, sort, breadcrumbs, file viewing endpoint, text length

---

## Completed — 2026-04-13 (session 17: Klaim Data Room + Memo Exercise)

End-to-end validation of the full analysis pipeline — Legal Analysis, Data Room, Intelligence System events, and Memo Engine.

**Validation:**
- [x] **Legal Analysis tabs** — all 8 render with rich extracted data from 4 facility PDFs
- [x] **Account Debtor validation** — confirmed: tape Group column = 143 healthcare providers (sellers), NOT insurance companies (payers). 0/13 approved Account Debtors found. MRPA concentration limit (d) unenforceable.
- [x] **Consecutive breach history** — `annotate_covenant_eod()` + `covenant_history.json` already working, verified EoD status annotations

**Data Room Ingestion:**
- [x] **Klaim data room** — 23 new files ingested from OneDrive (facility agreements, pitch decks, corporate docs, SPV filings). Total: 28 docs, 492 chunks, 320 pages
- [x] **DOCUMENT_INGESTED events** — fired, entity extraction ran, compilation log + entities.jsonl populated
- [x] **Document Library** — renders with full stats (28 docs, 320 pages, 492 chunks)

**Memo Engine:**
- [x] **Klaim Credit Memo** — 12 AI-generated sections with mixed sources (analytics + data room). Full 5-layer context pipeline working. MemoEditor renders with section TOC, Regenerate/Edit buttons, PDF export
- [x] **Tamara Credit Memo** — 11/12 AI sections generated. Exec summary correctly flagged insufficient data. Covenant section bug fixed (list vs dict format)

**Bug Fixes:**
- [x] **`covenant_history.json` breaking loader** — added to `_EXCLUDE` set in `core/loader.py` (also `facility_params.json`, `debtor_validation.json`)
- [x] **Analytics bridge covenant format** — added `isinstance()` check for list vs dict triggers in `core/memo/analytics_bridge.py`

**Lessons:**
- Non-data JSON files in product dirs must be excluded from snapshot discovery
- Analytics bridge must handle both dict and list covenant formats (company-type polymorphism)

---

## Completed — 2026-04-13 (session 16: Intelligence System Integration)

Wired the Intelligence System (built in session 13) into the live application — 8 files modified, 1 new file, 263 tests passing.

**Phase 1: Backend Event Wiring**
- [x] **Register listeners at startup** — `register_all_listeners()` in `lifespan()`, 4 event handlers active
- [x] **Fire TAPE_INGESTED on first load** — dedup set per (company, product, snapshot) in `_load()`
- [x] **Fire DOCUMENT_INGESTED** — in `core/dataroom/engine.py` `_ingest_single_file()` after parse/chunk
- [x] **Fire MEMO_EDITED with AI version** — captures old content before update for learning engine
- [x] **Add Layer 5 thesis context** — `build_mind_context()` now 5-layer (was 4), all AI outputs thesis-aware

**Phase 2: API Endpoints (10 new)**
- [x] **Create `backend/intelligence.py`** — thesis CRUD, drift check, briefing, KB search, learning, chat feedback
- [x] **Register intelligence router** in `backend/main.py`
- [x] **Add 6 intelligence commands** to operator COMMANDS list
- [x] **Add 9 API functions** in `frontend/src/services/api.js`

**Phase 3: Frontend**
- [x] **Briefing tab in OperatorCenter** — priority cards, thesis alerts, since-last-session, recommendations, learning summary
- [x] **Learning tab in OperatorCenter** — correction frequency, auto-rules, codification candidates
- [x] **DataChat feedback buttons** — thumbs up/down on AI responses, fires CORRECTION_RECORDED

---

## Completed — 2026-04-13 (session 15: Document Library bugfix)

- [x] **Fix blank Document Library page** — `stats.by_type` entries are objects `{count, chunks, pages}` but frontend treated them as plain numbers, crashing the React render. Fixed to extract `.count` from each entry.

---

## Completed — 2026-04-13 (session 14: UI collision audit + fixes)

Fixed absolute-vs-flow positioning collisions across the platform:

- [x] **KpiCard: trend badge overlapping label text** — added `paddingRight: 52` on label when trend or stale badge is present, preventing text from running under the badge on all cards
- [x] **KpiCard: stale badge vs trend badge overlap** — stale "TAPE DATE" badge now stacks below trend badge (`top: 30` when trend present) instead of occupying the same corner
- [x] **TamaraDashboard: L1/L2/L3 threshold label overlap** — labels now stagger vertically (`top: -24`) when adjacent thresholds are within 8% of maxVal
- [x] **Covenants: notification tooltip viewport overflow** — added `maxWidth: 260` + `textOverflow: ellipsis` to prevent `whiteSpace: nowrap` from extending beyond viewport
- [x] **Platform-wide audit** — verified FacilityParamsPanel (already safe), Navbar/MemoEditor dropdowns (acceptable popover pattern), CovenantCard threshold markers (already clamped)

---

## Completed — 2026-04-12 (session 13: Intelligence System — Second Brain)

**Inspired by Claude+Obsidian "second brain" pattern (Defileo viral post).**

Built the complete Laith Intelligence System across 7 phases:

- [x] **Phase 0: Foundation Layer** — `core/mind/schema.py` (KnowledgeNode + Relation dataclasses with backward-compatible JSONL storage), `core/mind/relation_index.py` (bidirectional adjacency list), `core/mind/event_bus.py` (lightweight sync pub/sub). Upgraded `master_mind.py` and `company_mind.py` writers with graph metadata + event publishing.
- [x] **Phase 1: Knowledge Graph** — `core/mind/graph.py` (graph-aware query engine with recency/category/graph bonus scoring, BFS neighborhood traversal, contradiction detection, staleness detection, compaction)
- [x] **Phase 2: Incremental Compilation Engine** — `core/mind/entity_extractor.py` (regex-based extraction of COVENANT, METRIC, RISK_FLAG, COUNTERPARTY, DATE_EVENT, THRESHOLD, FACILITY_TERM from text + tape metrics), `core/mind/compiler.py` (one-input-many-updates: create/supersede/reinforce/contradict pipeline with compilation reports, cross-document discrepancy detection)
- [x] **Phase 3: Closed-Loop Learning** — `core/mind/learning.py` (LearningEngine: correction analysis → auto-classify tone_shift/threshold_override/data_caveat/factual_error/etc → generate natural-language rules, pattern extraction from 3+ similar corrections → codification candidates, correction frequency tracking)
- [x] **Phase 4: Thesis Tracker & Drift Detection** — `core/mind/thesis.py` (InvestmentThesis + ThesisPillar + DriftAlert dataclasses, automatic drift check against live metrics, conviction score 0-100, status transitions holding→weakening→broken, versioned thesis log, AI context injection Layer 5)
- [x] **Phase 5: Proactive Intelligence** — `core/mind/intelligence.py` (cross-company pattern detection: metric trends, risk convergence, covenant pressure), `core/mind/briefing.py` (morning briefing generator with urgency-scored priority actions, thesis alerts, learning summary), `core/mind/analyst.py` (persistent analyst context store)
- [x] **Phase 6: Session Tracker** — `core/mind/session.py` (tracks tapes/docs/corrections/rules per session, delta computation for morning briefings)
- [x] **Phase 7: Queryable Knowledge Base** — `core/mind/kb_decomposer.py` (parse lessons.md + CLAUDE.md into linked KnowledgeNodes), `core/mind/kb_query.py` (unified search across mind + lessons + decisions + entities)
- [x] **Event Listeners** — `core/mind/listeners.py` (wires TAPE_INGESTED → compilation + thesis drift, DOCUMENT_INGESTED → entity extraction + compilation, MEMO_EDITED → learning rule generation, CORRECTION_RECORDED → analysis)
- [x] **6 Slash Commands** — `/morning` (briefing), `/thesis` (tracker), `/drift` (check all), `/learn` (review), `/emerge` (patterns), `/know` (KB query)
- [x] **93 new tests** — 42 foundation + 51 system, all passing alongside 134+22 existing = 249 total

---

## Completed — 2026-04-11 (session 11: Red Team Review + Fix All 28 Findings)
- [x] **Red Team Mode 6 — first adversarial review** — Full codebase audit covering 6 sections: Data Integrity, Calculation Verification, Business Logic Stress Test, UX Trust, AI Commentary Risks, Failure Mode Catalogue. Found 8 critical, 14 warning, 6 improvement findings. Report: `reports/deep-work/2026-04-11-red-team-report.md`.
- [x] **Fix C-4: Path traversal in legal upload** — `backend/legal.py` now sanitizes filenames with `os.path.basename()`, rejects dotfiles.
- [x] **Fix C-1: Previous snapshot index inverted** — `backend/main.py` BB movement attribution + covenant trend were comparing against NEXT snapshot instead of PREVIOUS. Changed `+1` → `-1` with `>= 0` guard.
- [x] **Fix B-1: Weighted avg discount double-multiplied** — `core/analysis.py` `compute_returns_analysis()` had extra `* mult` in weighted discount formula. Removed.
- [x] **Fix C-2: Covenant Collection Ratio uses cumulative data** — `core/portfolio.py` renamed to "Collection Ratio (cumulative)", marked `partial: True`, added note explaining single-tape limitation.
- [x] **Fix E-1: AI silent exception swallowing** — `backend/main.py` `_build_klaim_full_context()` had 22 `try/except: pass` blocks. All now track errors in `data_gaps[]` and append a DATA GAPS section to AI context.
- [x] **Fix C-3: PAR benchmark non-deterministic** — `core/analysis.py` `_build_empirical_benchmark()` now accepts `snapshot_date` param instead of using `pd.Timestamp.now()`.
- [x] **Fix D-1: Race condition on snapshot switch** — `CompanyContext.jsx` summary fetch now uses `AbortController` to cancel stale requests.
- [x] **Fix C-5: CF_TEAM empty string auth bypass** — `backend/cf_auth.py` now strips whitespace and logs warning when CF_TEAM is set but empty.
- [x] **Fix A-1: filter_by_date() mutation** — `core/analysis.py` now copies DataFrame before mutating `Deal date` column.
- [x] **Fix B-2: Revenue inf on zero PV** — `core/analysis.py` guarded with `np.where` + `.replace([np.inf, -np.inf], 0)`.
- [x] **Fix B-3: CDR > 100% for young vintages** — Skip vintages < 3 months old in `compute_cdr_ccr()`.
- [x] **Fix E-3: AI cache serves wrong currency** — Currency added to `_ai_cache_key()` and all callers updated.
- [x] **Fix C-7: Cache not invalidated on file replace** — File mtime added to AI cache key.
- [x] **Fix C-8: Bulk ops partial commit** — `backend/integration.py` now uses `db.begin_nested()` savepoints per item.
- [x] **Fix D-2: TabInsight stale across snapshots** — Added `useEffect` to clear on snapshot/currency change.
- [x] **Fix D-3: AICommentary not cleared on back-nav** — Added `useEffect` in CompanyContext to clear `aiCache` on snapshot change.
- [x] **Fix D-4: Tamara missing read-only badge** — Added matching badge in `TamaraDashboard.jsx`.
- [x] **Fix D-5: No data source indicator** — `PortfolioAnalytics.jsx` now shows "Live Data" or "Tape Fallback" badge.
- [x] **Fix A-4: Non-deterministic snapshot sort** — Secondary sort by filename in `loader.py`.
- [x] **Fix A-5: Sheet selection heuristic** — Prefer named data sheets, skip summary/glossary sheets.
- [x] **Fix C-10: EoD non-consecutive validation** — Validates 15-45 day gap between periods.
- [x] **Fix C-12: Amendment covenant dedup** — Prefers later `extracted_at` timestamp.
- [x] **Fix I-1: N+1 queries in db_loader** — Pre-aggregates payments in single query.
- [x] **Fix I-2: Unbounded caches** — `_BoundedCache` with max 10 entries.
- [x] **Fix I-5: fmt_m NaN crash** — NaN/inf guard added.
- [x] **Fix I-6: Seasonality avg includes zeros** — Filters non-zero months.
- [x] **Fix misc** — `_safe()` inf guard (SILQ), `_dpd()` missing column warning, migration.py input mutation, DataChat empty response, Tamara percentage edge case.
- [x] **All 156 tests passing** after fixes.

---

## Completed — 2026-04-11 (session 10: Authentication + RBAC)
- [x] **Cloudflare Access JWT authentication** — Backend reads `CF_Authorization` cookie / `Cf-Access-Jwt-Assertion` header, verifies RS256 JWT against Cloudflare public keys (`amwalcp.cloudflareaccess.com/cdn-cgi/access/certs`). Auto-provisions users on first login. Admin bootstrap via `ADMIN_EMAIL` env var.
- [x] **User model + migration** — `User` table (email, name, role, is_active, timestamps) in `core/models.py`. Alembic migration `b2f3a8c91d45`.
- [x] **Auth middleware** — `CloudflareAuthMiddleware` in `backend/cf_auth.py`. Skips `/auth/*`, `/api/integration/*`, OPTIONS. Dev mode (no `CF_TEAM`) passes all requests through.
- [x] **Auth API routes** — `backend/auth_routes.py`: `/auth/me`, `/auth/logout-url`, `/auth/users` CRUD (admin-only). Pre-provision users with roles before they log in.
- [x] **Frontend AuthContext** — `AuthContext.jsx` calls `/auth/me` on mount, provides `user`, `isAdmin`, `logout`. `ProtectedRoute.jsx` guards all routes.
- [x] **Navbar user menu** — Replaced hardcoded "Sharif Eid" with `UserMenu` dropdown: initials avatar, email, role badge (gold ADMIN / blue VIEWER), "Manage Users" link (admin-only), "Log out" button.
- [x] **User Management page** — `/admin/users` with user table, invite form, inline role editing, deactivate/reactivate. Admin-only route guard.
- [x] **Cloudflare Access branding** — Configured login page: dark navy background (`#121C27`), lion logo (via Imgur), "Laith Analytics" name, "Sign in to access Laith Analytics" header.
- [x] **Docker + Nginx** — `/auth` proxy location in nginx.conf, `withCredentials: true` on Axios, env vars (`CF_TEAM`, `CF_APP_AUD`, `ADMIN_EMAIL`) in `.env.production`.
- [x] **docker-compose.yml env var fix** — Removed `${CF_TEAM:-}` from `environment` section (was overriding `env_file` values with empty strings).
- [x] **Deployed and verified** — Login flow works: Cloudflare OTP → app shows user name + admin badge + manage users link.

---

## Completed — 2026-04-11 (session 9: Research Chat per-company suggestions)
- [x] **Make Research Chat suggestions context-aware** — `SUGGESTED_QUESTIONS` in `ResearchChat.jsx` was a flat array of Tamara-specific questions shown to all companies. Converted to a map keyed by `analysisType` (matching the DataChat.jsx pattern). Now shows tailored suggestions for klaim, silq, ejari_summary, and tamara_summary. Added a generic `default` fallback for future companies.

---

## Completed — 2026-04-11 (session 8: Landing Page + Operator Center Bug Fixes)
- [x] **Fix `_master_mind` appearing as company card on landing page** — `get_companies()` in `core/loader.py` listed all directories in `data/` without filtering internal directories. Added `not d.startswith('_')` filter so `_master_mind` (fund-level Living Mind storage) is excluded from the company list. Fixes landing page, `/aggregate-stats`, and `/operator/status` (which had its own redundant filter).
- [x] **Fix blank Operator Command Center page** — `OperatorCenter.jsx` silently swallowed API failures (`catch` only logged to console), leaving `status` as `null` and rendering empty content with no user feedback. Added `error` state with red error message and Retry button when the backend is unreachable.
- [x] **Fix Nginx missing proxy for `/operator` endpoint** — Root cause of Command Center showing empty content on production: `docker/nginx.conf` had no `location /operator` block. Requests to `/operator/status` hit the SPA fallback (served `index.html` instead of JSON). Added proxy rules for `/operator`, `/memo-templates`, `/mind`.

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
- [x] **Phase 2: Research Intelligence** — Claude RAG queries
  - `core/research/` — ClaudeQueryEngine, DualResearchEngine, extractors
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
  - .gitignore: dataroom chunks/index, mind JSONL excluded
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
