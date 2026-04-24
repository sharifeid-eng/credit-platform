# Session 35 — Systematic Rethink of §17 Implementation
# 2026-04-24

User feedback after session 34: the SILQ PAR dual view was missed.
Specifically, Aajil got a dual-PAR P1 item but SILQ wasn't flagged
despite having the same structural gap. User asked for a thorough
rethink to find what else was missed.

This document is the audit output from that rethink.

---

## Phase 0 — The intended principles (explicit, not assumed)

Session 34 declared Framework §17 "Population Discipline & the
Tape-vs-Portfolio Duality". Stripped to essentials, here's what it
was trying to establish:

### Principle 1 — Every metric declares a population

Every compute function output that carries a rate/ratio/share must
state which population its denominator measures (one of 7 standard
codes: `total_originated`, `active_outstanding`, `active_pv`,
`completed_only`, `clean_book`, `loss_subset`, `zombie_subset`).

**Coverage rule:** EVERY rate-returning metric, not just covenants
and limits.

### Principle 2 — Every metric declares confidence

Every metric carries an A/B/C grade (Framework §10): A observed,
B inferred, C derived. The `method_to_confidence()` helper maps
common method tags to grades.

**Coverage rule:** EVERY rate-returning metric, not just covenants
and limits.

### Principle 3 — Dual views when a metric serves two questions

When the same conceptual metric answers two different analytical
questions (e.g., PAR on active vs lifetime; cohort collection rate
blended vs clean; HHI total vs clean), BOTH views are exposed with
their respective population tags.

**Coverage rule:** applied consistently across asset classes. If
company A has metric X with a dual, companies B/C/D should also
have it (unless structurally exempt).

### Principle 4 — Tape-vs-Portfolio duality

Covenant-facing metrics (Portfolio Analytics) use the facility-
document population (typically `active_outstanding`), unfiltered.
Learning metrics (Tape Analytics) prefer `clean_book` (stale-
filtered) to answer "how does the product behave?" rather than
"what's the current exposure?".

### Principle 5 — Primitives consistent across asset classes

Every live-tape asset class has the same set of §17 primitives:
- `separate_{type}_portfolio()` — splits clean vs loss
- `classify_{type}_deal_stale()` — 3-category stale classifier
- `compute_{type}_operational_wal()` — clean-book PV-weighted age
- `compute_{type}_methodology_log()` — audit trail

### Principle 6 — Discipline enforcement via meta-tests

Documented rules drift without automated walkers. Every platform-
wide rule needs a test that iterates the relevant surface and
asserts compliance.

### Principle 7 — Frontend disclosure renders the population + confidence

When analysts look at a number on the dashboard, they should see
(or be able to see) the grade and population. Not hidden in
tooltips so deep no one reads them — surfaced enough that a
reader can tell "this metric is A observed" from "this metric is
C derived" at a glance.

### Principle 8 — AI outputs cite population + confidence

Memo prompts + exec summary prompts + chat responses should cite
population + confidence on headline metrics. Bridge functions
must transmit these fields to the prompt or the model can't cite
them.

### Principle 9 — Methodology pages document the dual-view catalogue

Every asset class's methodology page lists which metrics have
dual views and which populations each uses. Future analysts
onboarding to a company read the methodology page and understand
the §17 compliance of each metric.

### Principle 10 — Principle propagation is discipline, not afterthought

When a gap is fixed on company A, the same fix is proactively
applied to companies B, C, D — OR each company is explicitly
declared exempt with a documented reason. No implicit "company X
has it, others don't because we didn't think of it".

---

## Phase 1 — Build the meta-walker tool (gap surfacer)

Tool: `tests/test_population_discipline_meta_audit.py`. Pytest
test that imports every compute_* function, calls it on a minimal
synthetic tape, walks the returned dict, and reports:

- Rate-like fields without population tags → FAIL (hard rule)
- Rate-like fields without confidence tags → FAIL (hard rule)
- Metrics present on company A with dual but missing dual on B → WARN
  (soft — legitimate asymmetry is possible)
- Non-standard population codes → FAIL (frozen taxonomy)

Rate-like field heuristics: name ends in `_rate`, `_pct`, `_ratio`,
equals `par30`/`par60`/`par90`/`hhi`, or has fractional value
between 0 and 2 and isn't a count/tenure/days field.

The walker runs as a pytest that prints the full gap list in its
failure message. It doesn't block CI until gaps are resolved — starts
as a "soft" checker emitting warnings, graduates to hard failures
as each gap is closed.

---

## Phase 2 — Gap enumeration (populated by running the walker)

The walker output drives this section. Gaps grouped by severity:

**Hard failures (missing population/confidence tags on rate fields):**
- TBD (populated after walker runs)

**Dual-view asymmetry warnings (one company has, another doesn't):**
- TBD

**Structural findings (pattern issues beyond individual metrics):**
- TBD

---

## Phase 3 — Fixes (implementation plan)

One commit per thematic gap cluster. No "one massive fix commit".

---

## Phase 4 — Meta-tests added this session

1. **Top-level dict walker** — asserts every compute_* return dict
   with rate fields declares population + confidence. Graduates from
   warn-only (phase 1) to hard failures as gaps close.

2. **Same-pattern propagation checker** — for each dual-view metric
   that exists on company A, asserts the same dual exists on
   companies B, C, D unless A, B are tagged in an explicit
   `EXEMPT_PROPAGATION` map (with reason).

3. **Taxonomy freshness checker** — if Framework §17 codifies a new
   population code, the test suite must see it in `_ALLOWED_POPULATIONS`
   before the code can be used in compute outputs. Forces explicit
   vote-in of new vocabulary.

---

## Phase 5 — Framework + methodology + close-out doc updates

Based on what the walker finds, Framework §17 may need a new
subsection on "principle propagation" + "dual-view pattern taxonomy"
(single-primary+context vs parallel-equal vs N-way).

---

## Outcome tally

### What the walker found (Phase 2)

**45 rate-like fields lacked §17 disclosure across the platform:**

**Klaim — 17 gaps fixed:**
- `compute_summary.denial_rate`, `pending_rate` — now dict-level disclosed
- `compute_returns_analysis.completed_loss_rate` — completed_only disclosed
- `compute_denial_funnel.recovery_rate` — loss_subset disclosed
- `compute_par.par30/60/90` + `lifetime_par*` — dict-level + field-level disclosed for BOTH direct and derived branches
- `compute_cohort_loss_waterfall.totals.gross_default_rate/net_loss_rate/recovery_rate` — disclosed
- `compute_cdr_ccr.portfolio.cdr/ccr/net_spread` — disclosed (also had test-fixture exception, fixed)
- `compute_klaim_stale_exposure.stale_pv_share` — zombie_subset disclosed

**SILQ — 17 gaps fixed:**
- `compute_silq_summary.overdue_rate`, `hhi_shop`, `lifetime_par*` — all disclosed
- `compute_silq_delinquency.par30/60/90` + NEW lifetime dual — disclosed (the Delinquency tab gap that my SILQ summary fix hadn't covered)
- `compute_silq_yield.margin_rate/realised_margin_rate` — disclosed
- `compute_silq_cohort_loss_waterfall.totals.*` + `compute_silq_cdr_ccr.portfolio.*` — disclosed
- `compute_silq_borrowing_base.advance_rate` — exempt (facility parameter, not analytical rate)

**Aajil — 11 gaps fixed:**
- `compute_aajil_summary.write_off_rate`, `avg_*_yield` — partially exempt (yields are descriptive stats, covered by compute_aajil_yield.yield_confidence) / disclosed as needed
- `compute_aajil_concentration.hhi_customer`, `top5/10_share`, `industry_unknown_pct` — disclosed / exempt
- `compute_aajil_loss_waterfall.gross_loss_rate` — disclosed

**Plus 5 semantic propagation additions caught via new test (not walker):**
- `compute_aajil_summary.collection_rate` now carries 3-population dual (matches P1-4 pattern established in compute_aajil_collections)
- `compute_silq_delinquency` now has PAR lifetime + absolute amounts (matches the SILQ summary fix from earlier this session)

### Meta-tests added

1. **TestMetaAuditRateFieldDisclosure** — walks every compute_* function's
   top-level dict, flags any rate-like field without §17 disclosure.
   Currently passing 0 gaps; future regressions fail with the
   function+field name in the error message.

2. **TestMetaAuditDualPropagation** — asserts specific duals exist on
   every applicable asset class (PAR lifetime, HHI clean, collections
   realised, operational WAL, methodology_log, summary-collection-rate
   dual). 6 tests.

3. **TestMetaAuditTaxonomyFreshness** — emitted population codes must
   be pre-approved in `_ALLOWED_POPULATIONS_PREFIX`. Forces explicit
   vocabulary vote-in.

### Framework §17 additions

- **Principle propagation discipline** subsection (4 rules): platform-wide
  dual-view rollout, summary-mirror-compute rule, primitive-completeness
  for live-tape asset classes, read-only exemption declaration.
- **Dual-view pattern taxonomy** subsection: 3 patterns codified
  (single-primary+context, parallel-equal, N-way) with when-to-use
  guidance. Prevents future pattern-mismatch confusion when onboarding.

### Test count

- Before session 35: 772 passing
- After session 35 (so far): 780 passing
- Zero regressions at every commit
- Zero warnings

### Lessons captured

New lessons for `tasks/lessons.md`:

1. **Build walkers before eyeballing audits.** 45 gaps surfaced via the
   meta-walker that I couldn't have enumerated by hand. The SILQ PAR
   miss would have been one line in the walker's output. Every future
   platform-wide audit should start with a walker pass that lists gaps,
   not with a manual pre-audit.

2. **Summary fns must mirror compute fns on dual-view surfaces.** If
   `compute_X_collections` has a realised/clean dual, `compute_X_summary`
   must expose the same dual — otherwise the overview card can't show
   the population-honest view. The walker caught this on Aajil; test
   `test_summary_collection_rate_dual_consistency` pins it.

3. **Three dual-view patterns, not one.** Single-primary (lending),
   parallel-equal (factoring), N-way (yield). Picking the wrong pattern
   for the asset class creates analyst confusion. Now codified in
   Framework §17 pattern taxonomy.

### Onboarding implications

For a new asset class onboarding:
1. Declare the asset-class economics (lending / factoring / yield-style).
2. Pick the dual-view pattern that matches.
3. Implement the full §17 primitive set (4 helpers).
4. Run the meta-audit — every new compute fn gets walked automatically.
5. Add a propagation test entry naming any duals that must exist.

This is now enforceable by tests — onboarding without §17 compliance
fails the meta-audit suite.
