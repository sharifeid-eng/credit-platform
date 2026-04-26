# Mode 6 — Red Team / Adversarial Review

**Date:** 2026-04-26
**Branch:** `claude/goofy-colden-59f980`
**Methodology:** `WEEKEND_DEEP_WORK.md` Mode 6
**Files analyzed:** 59 (12 core compute + 9 business logic + 20 frontend + 18 AI/agent)

## Aggregate severity counts

| Section | Critical | Warning | Improvement | Total |
|---|---:|---:|---:|---:|
| A+B Data Integrity & Calculation Verification | 9 | 17 | 9 | 35 |
| C   Business Logic Stress Test | 8 | 13 | 7 | 28 |
| D   UX Trust Audit | 7 | 13 | 8 | 28 |
| E   AI Commentary & Agent Runtime | 9 | 17 | 8 | 34 |
| **Totals** | **33** | **60** | **32** | **125** |

Detailed findings live in section files:
- [`scratch/section_ab_compute_integrity.md`](scratch/section_ab_compute_integrity.md)
- [`scratch/section_c_business_logic.md`](scratch/section_c_business_logic.md)
- [`scratch/section_d_ux_trust.md`](scratch/section_d_ux_trust.md)
- [`scratch/section_e_ai_runtime.md`](scratch/section_e_ai_runtime.md)

---

## Executive summary

The platform's recent §17 Population Discipline rollout (sessions 34-36) and snapshot-dimensioned DB (session 31) added strong analytical scaffolding — but the rollout exposed a recurring pattern: **safety-critical defaults fail OPEN rather than closed**, and **silent fallbacks mask data quality issues from the analyst**. 33 Critical findings cluster around five themes: covenant leakage, fragile pandas patterns, non-deterministic time defaults, cross-context contamination in AI prompts, and §17 disclosure coverage gaps. None are exotic — most are exactly the kind of edge case an IC member could hit in a normal session.

The good news: the discipline added by sessions 34-36 (`separate_*_portfolio`, `classify_*_deal_stale`, `compute_*_operational_wal` primitives) is mostly correct in isolation. The problems are at the **integration points** — covenants that don't invoke the new primitives, AI cache keys that don't invalidate on the new dimensions, frontend cards that don't surface the new disclosure fields. All fixable; most fixes are < 20 lines each.

---

## TL;DR — Top 5 most important findings (cross-section)

1. **🔴 Covenant operator-precedence bug crashes Klaim covenants when `Status` column missing** — `core/portfolio.py:1284-1287, 1328-1331` (Section A+B #8, Section C #4 — same root cause). The expression `df[(mask1) & (mask2) if 'Status' in df.columns else True]` evaluates as `df[True]`, raising `KeyError: True`. Defensive fallback is broken. Single fix unblocks both.

2. **🔴 `annotate_covenant_eod` fails OPEN — triggers Event of Default on every history-parse failure** — `core/portfolio.py:1467-1488` (Section C #5). `pd.Timestamp(prev_period)` raises ValueError when period is a date-range string (which the codebase ITSELF writes at line 1093), the bare `except Exception: is_consecutive = True` fires EoD on the next breach. Real EoD-leakage risk under normal data.

3. **🔴 Klaim Coll Ratio + Paid vs Due silently include loss-subset deals — covenant deteriorates deterministically with rising loss tail** — `core/portfolio.py:1282-1290, 1334-1340` (Section C #1). Both filter on `Status` only; do NOT call `separate_portfolio()`. The §17 primitive exists for exactly this case but isn't invoked. Analyst sees "collections slowing" when reality is "loss accumulation".

4. **🔴 Klaim Single Payer compliance reports `compliant=True` against `Group` proxy — covenant certificate carries false-pass on a binding 10% limit** — `core/portfolio.py:984-1015` (Section C #8). Klaim has 144 Groups but ~13 Payers. Code knows the proxy gap (`confidence='B', proxy_column='Group'`) but the binary `compliant` boolean isn't gated on it. Compliance certificate export → false attestation risk.

5. **🔴 Tamara UAE Executive Summary pulls KSA's Company Mind — cross-product memory leak undetectable in output** — `backend/main.py:2784` and 4 sister sites (Section E #1). All 5 `_build_*_full_context()` functions hardcode their target product. UAE memos cite KSA-flavored institutional findings. Same pattern blocks any future per-product memory split.

---

## Top 10 Critical findings (full list)

In addition to the TL;DR top 5 above:

6. **🔴 AI cache key omits `snapshot_id` for `live-*` DB snapshots** — `backend/main.py:397-426` (Section E #3). Integration API mutations to today's live snapshot serve stale AI summaries until UTC midnight. PAR can move 4.2% → 7.8% while AI commentary still cites the morning's value.

7. **🔴 Citation audit returns `[]` (no issues) on JSON parse failure — INDISTINGUISHABLE from genuine "no issues"** — `core/memo/generator.py:826-831` (Section E #5). Fabricated citations slip through to polished memo because the audit's failure mode looks identical to its happy path. Fix: synthesize `_audit_failed` issue on parse error.

8. **🔴 `_klaim_wal_total` + `_klaim_deal_age_days` default to `pd.Timestamp.now()` when `ref_date` is None** — `core/portfolio.py:631-639, 712, 1147` (Section A+B #6). Same historic snapshot's WAL covenant compliance drifts day-by-day. Session 31's snapshot-dimensioned DB fixed source ambiguity; this still uses wall-clock time.

9. **🔴 `migration.py` cure-rate matrix Cartesian-explodes on duplicate IDs** — `core/migration.py:90-94` (Section A+B #2). `merge` without `validate=` argument or de-dup. Klaim's documented denial-reopen pattern routinely produces duplicates; transition counts inflated.

10. **🔴 PAR Option C empirical-method threshold (50/3/10) flips method silently as `as_of_date` filter changes** — `core/analysis.py:1680-1705, 1832` (Section C #7). Same snapshot, two different `as_of_date` queries → different method → different PAR rate. AI cache doesn't include `method` so cached entries from one threshold-state get served when current state is different.

(Plus 23 more Critical findings across all sections — see scratch files.)

---

## Cross-section themes — patterns that appear in 2+ sections

These are the highest-leverage fixes: a single architectural change closes multiple findings at once.

### Theme 1: Fail-OPEN defaults in safety-critical guards
Six findings show the same anti-pattern — when the platform encounters uncertainty, it defaults to "things are fine" rather than "data is missing":
- `is_consecutive = True` on covenant-history parse failure (Section C #5)
- `compliant = True` when no qualifying loans (Section C #17)
- Citation audit returns `[]` (no issues) on parse failure (Section E #5)
- §17 confidence treated as A-grade when fields missing (Section E #22)
- `auto_fire_after_ingest` swallows all exceptions silently (Section C #16)
- BB Holiday defaults to a real date (Klaim's MMA date) when no facility_params (Section C #18)

**Recommended pattern fix:** Adopt a project-wide convention "fail CLOSED for credit-risk surfaces, fail OPEN only for analytics surfaces, log either way." Codify in `CLAUDE.md` as a binding rule.

### Theme 2: AI cache invariants drift across recent feature additions
Three independent findings on the same `_ai_cache_key()` function:
- Section A+B #28 — `apply_multiplier()` returns 1.0 silently on unknown currency (related: cache key includes currency, but if currency is unknown the cached value uses the wrong rate forever)
- Section C #19 — Cache key normalizes `as_of_date` but doesn't include `analysis_type` or facility_params hash
- Section E #3, #31 — Cache key collapses for DB-only `live-*` snapshots; `os.path.exists(filepath)` returns False, mtime omitted
- Section D #4 — Frontend `aiCache` state in CompanyContext clears on `[snapshot]` only, NOT on `[currency]` change

**Recommended pattern fix:** Audit the full AI cache key construction post-Session-31. The DB-snapshot world needs `snapshot.ingested_at` (or `snapshot.id`) as the file-mtime equivalent. Frontend cache must mirror backend dimensions.

### Theme 3: §17 disclosure coverage holes
Four UX findings + 1 backend finding undermine the framework §17 audit trail that sessions 34-36 worked extensively to surface:
- Section D #3 — Ejari PAR cards ship NO `ConfidenceBadge`
- Section D #7 — PortfolioStatsHero renders dashes that look like real values, no §17 context
- Section D #9 + #20 — `ConfidenceBadge` uses native `title=` tooltip that breaks on touch devices (iPad-using IC members) AND has unpredictable wrap on long disclosures
- Section E #22 — Compute functions that don't yet emit confidence/population get treated as A-grade by default; silent confidence inflation
- Section A+B #24 — Klaim PAR proxy thresholds (90d/120d) not recorded in `compute_methodology_log`

**Recommended pattern fix:** Replace `ConfidenceBadge` native tooltip with a controlled component (Radix Tooltip or equivalent) that handles `onTouchStart`. Add a CI test in `test_population_discipline_meta_audit.py` that fails if any compute function the analytics_bridge consumes lacks confidence/population.

### Theme 4: Loss-subset leakage into period-based covenants
Two findings (Klaim + SILQ analogues):
- Section C #1 — Klaim Coll Ratio + PVD don't invoke `separate_portfolio()`
- Section C #9 — SILQ Coll Ratio includes `Closed`-with-`Outstanding>0` charge-off loans

**Recommended pattern fix:** Walker test: every covenant function declares which loss-handling primitive it calls (or explicitly declares it deliberately omits). The §17 primitive set is in place; it's just not consistently invoked at the covenant layer.

### Theme 5: Re-implementations of core metrics in 3-4 places
Section A+B #29 documents this directly: PAR is computed in `compute_par()` (analysis.py), `compute_klaim_covenants()` (portfolio.py), and `compute_klaim_borrowing_base()` (portfolio.py). Same tape, three potentially-different PAR readings.
- Section C #20 also shows the divergence: PAR covenant filter `(age > 90) & (pending > 0)` excludes denial-dominant active deals → covenant under-reports

**Recommended pattern fix:** Extract `_compute_par_klaim(df, mult, ref_date, threshold_days, *, method)` shared helper. Both Tape Analytics PAR and Portfolio Analytics covenant call it. Documented method tag enforces consistency. ~50 lines of refactoring; eliminates an entire class of bug.

### Theme 6: Race conditions in append-only stores
Three findings on JSONL/JSON files lacking OS-level locking:
- Section C #16 — `auto_fire_after_ingest` swallows everything
- Section E #7 — Pattern detector concurrent writes produce duplicate `pattern_id` entries
- Section E #16 — `pending_review` queue not concurrency-guarded; on Windows JSONL append is not guaranteed atomic
- Section E #25 — `write_fund_wide_stats` uses `open('w')` (non-atomic); crash mid-write corrupts JSON

**Recommended pattern fix:** Single helper `core/utils/atomic_io.py::atomic_write_json()` and `atomic_append_jsonl()` with file locks (`filelock` package, cross-platform). All Mind/queue writes route through it. ~30 lines + audit pass.

### Theme 7: Sync vs Stream divergence on AI Executive Summary
Three Section E findings (#2, #6, #26):
- Sync endpoint inlines its own JSON parser; streaming uses `_parse_agent_exec_summary_response`
- Sync NEVER returns `analytics_coverage` (session-33 contract); streaming does
- Sync makes TWO `build_mind_context` calls (race window for asset_class_sources)

**Recommended pattern fix:** Eliminate the sync inline parser. Replace lines 3115-3133 with `narrative, findings, analytics_coverage, _parsed_ok = _parse_agent_exec_summary_response(response_text)`. Single source of truth. Frontend renders identically regardless of code path.

### Theme 8: Hardcoded color thresholds vs covenant thresholds
Section D #13, #14, #28 — three independent component authors made up three different "what counts as warning" answers (1%, 1.5%, 15%) for color-coding KpiCards. None derive from facility config. The dashboard cries wolf well below the IC-relevant trigger line, eroding the alert signal.

**Recommended pattern fix:** Centralize `getColorForMetric(metric, value, facilityConfig)` helper. Backend already exposes covenant thresholds — frontend just needs to consume them.

### Theme 9: Hardcoded company/product in mind context calls
Section E #1 — five `_build_*_full_context` functions all hardcode their target. Tamara UAE → KSA leak is the worst case (different securitization facility, different defaults).

**Recommended pattern fix:** Pass `(company, product)` through every `_build_*_full_context()` signature. Add regression test: `_build_tamara_full_context('Tamara', 'UAE')` calls `build_mind_context('Tamara', 'UAE', ...)`.

### Theme 10: SSE thread offload latent regression
Section E #13 — `backend/agents.py:_stream_agent` still uses `asyncio.create_task` instead of the dedicated-thread pattern session 32 codified as binding. Memo regen, compliance check, onboarding endpoints all share the latent freeze risk.

**Recommended pattern fix:** Extract thread-offload into `core/agents/sse_helpers.py::run_agent_in_thread()`. All SSE endpoints use it. CI test imports `_stream_agent` and asserts it routes through the helper.

---

## Recommended remediation order

Optimized for blast-radius reduction with minimum churn:

### Wave 1 — Hard bugs that crash or report false numbers (do first, < 1 day)
1. **Theme 1.a** — Fix covenant operator-precedence (Section A+B #8 = Section C #4). Single edit, two findings closed.
2. **Theme 1.b** — Fix `annotate_covenant_eod` `pd.Timestamp(prev_period)` parse (Section C #5). Stop fail-OPEN to EoD.
3. **Critical #4** — Gate Klaim Single Payer `compliant` on `proxy_column='Group'` (Section C #8). Set `compliant=None` (unknown) when proxy mode active.
4. **Critical #2 (migration)** — Add `validate='one_to_one'` or de-dup to `migration.py` merge (Section A+B #2).

### Wave 2 — Loss-subset leakage + WAL/age determinism (next 1-2 days)
5. **Theme 4** — Wire `separate_klaim_portfolio()` into Coll Ratio and Paid vs Due (Section C #1). Add `_clean` companion fields. Walker test.
6. **Theme 5 / Critical #8** — Fix `_klaim_wal_total` / `_klaim_deal_age_days` to use snapshot's `taken_at` when `ref_date` None (Section A+B #6).
7. **Critical #5 (citation audit)** — Synthesize `_audit_failed` issue on JSON parse error (Section E #5). Single function change.

### Wave 3 — AI cache + cross-product mind isolation (next 2-3 days)
8. **Theme 9 / Critical #5** — Plumb `(company, product)` through all `_build_*_full_context()` (Section E #1). Tamara UAE memo correctness.
9. **Theme 2** — Audit `_ai_cache_key()` for DB-snapshot dimensions; include `snapshot.ingested_at` for live snapshots (Section E #3, #31). Add `[currency]` to frontend `aiCache` clear effect (Section D #4).
10. **Theme 7** — Replace sync exec summary inline parser with `_parse_agent_exec_summary_response` (Section E #26). Frontend renders consistently.

### Wave 4 — UX trust gaps + §17 disclosure coverage (next week)
11. **Section D #1** — Destructure `snapshotsMeta` in `SilqTabContent` and `KlaimTabContent` (TapeAnalytics.jsx:247, 366). Two-line fix; unbreaks Data Integrity tab.
12. **Theme 3** — Replace `ConfidenceBadge` native `title=` with controlled tooltip primitive. Touch-device support; consistent wrap.
13. **Section D #15** — Replace native `<select>` in Covenants.jsx with `SnapshotSelect`.
14. **Theme 8** — Centralize KpiCard color thresholds; drive from facility config not magic numbers.

### Wave 5 — Architectural hardening (later, lower urgency)
15. **Theme 5 (PAR helper)** — Extract `_compute_par_klaim()` shared helper. Eliminates Section A+B #29 + Section C #20 entire bug class.
16. **Theme 6** — `core/utils/atomic_io.py` for cross-platform atomic JSON/JSONL writes.
17. **Theme 10** — Extract `core/agents/sse_helpers.py::run_agent_in_thread()`. Refactor `_stream_agent`. CI guard.

---

## Self-audit notes (per WEEKEND_DEEP_WORK.md Step 5)

Each subagent ran the self-audit independently. Items confirmed deliberate per CLAUDE.md / `core/ANALYSIS_FRAMEWORK.md` were downgraded to per-section appendices, NOT included in the findings list:

- Lifetime-primary PAR universal (session 36) — doctrine
- WAL Path A OR Path B compliance (MMA 18.3) — doctrine
- Last-write-wins on same-day snapshot collision — documented
- Active WAL keys covenant compliance, NOT Total — doctrine
- `method_changed_vs_prior` short-circuit on covenant chains — doctrine
- Per-section polish fan-out (~11x input tokens) — intentional reliability trade-off
- SSE thread offload (session 32) — doctrine; only flagged when latent regression detected
- 5-layer mind context architecture — doctrine
- "Informed by N asset-class sources" footer wording — intentional non-per-paragraph framing
- Asset class keying by `config["asset_class"]` (session 28 #3 fix) — doctrine; flagged latent regressions only
- `filter_by_date()` only filters DEAL SELECTION — doctrine, Framework §15
- Backdated AI calls return 400 (`_check_backdated`) — doctrine; raw chart endpoints serving snapshot-balance is documented
- Pattern detector never auto-writes to Asset Class Mind — trust boundary by design
- Klaim payer concentration uses `Group` as proxy — documented as Confidence B (but `compliant` boolean leaks despite confidence flag — Section C #8 stands)
- `Actual IRR for owner` excluded — documented garbage data
- Klaim "PAR via age_pending proxy" — Confidence B (but proxy thresholds 90d/120d not in methodology log — Section A+B #24 stands)

---

## Coverage notes

**Not covered in this Mode 6 run** (out of scope per protocol):
- Test coverage gaps (that's Mode 2's job)
- Style / naming inconsistencies (Mode 1)
- Documentation completeness (Mode 4)
- Prompt quality optimization (Mode 5 — though prompt parser correctness IS covered here)
- Performance profiling (touched by Section A+B but not exhaustive)

**Files NOT read** (potentially worth a follow-up sweep):
- `core/migration.py` deeper roll-rate logic beyond the merge bug (Section A+B touched it)
- `core/legal_extractor.py` 5-pass extraction internals (Section C touched the merge logic)
- `core/dataroom/engine.py` (Session 24 hardening was extensive; flagged orphan-eviction works correctly now)
- `core/research/query_engine.py` Claude RAG internals
- All slash command + ops scripts (out of dashboard data path)

---

## TL;DR (per Rule 7)

Top 5 most important findings — see "TL;DR — Top 5 most important findings (cross-section)" above. The shortest path to closing the highest-blast-radius issues is **Wave 1** (4 fixes, single-day work), which closes 6 Critical findings via 4 narrow code changes. Wave 2 (3 fixes) closes 4 more Criticals. After Waves 1+2, 23 of 33 Critical findings remain, but they're all in Wave 3+4 — the architectural surface, not the immediate-blast-radius surface.

The platform's analytical doctrine (§17, separation principle, snapshot-dimensioned DB) is sound. Most of these findings are about **integration discipline** — making sure the new primitives are invoked everywhere they apply, and that the scaffolding around them (caches, parsers, tooltips) treats their disclosure fields as load-bearing rather than optional.
