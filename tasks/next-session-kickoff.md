# Next Session Kickoff

## Carry-over from session 36 (2026-04-24) — 8-gap Follow-up Sweep

Session 36 landed the 8 gaps identified after the session 34/35 §17 audit
work (commits `f7ef580`, `7d68c9c`, `4a43f02` on `claude/followup-8-gap-sweep`,
to be merged into `main`).

### Outstanding items

**Visual browser verification (Gap 4, partial).** Session 36 compile-verified
the frontend (vite build green, 1110 modules transformed) and data-flow
verified the PAR flip via direct API calls:
  - SILQ KSA: `par30`=7.8% (active) + `lifetime_par30`=1.45% (new headline)
  - Klaim UAE_healthcare: `par30`=36.6% + `lifetime_par30`=2.37%
  - Aajil KSA: `par_1_inst`=33.25% + `par_1_inst_lifetime`=7.0%

Full click-through verification — user should start the stack with
`.\start.ps1`, open each company Overview tab (Klaim, SILQ, Aajil), and
confirm:

  1. Credit Quality section headline shows the LIFETIME PAR (low number).
  2. Subtitle reads `{amount} at risk · Active: X.XX%`.
  3. Section sublabel reads "vs Total Disbursed (lifetime)" on SILQ /
     "vs Total Originated" on Klaim / (Aajil matches its dashboard copy).
  4. Hover the confidence badge — tooltip should mention the ACTIVE PAR
     as secondary "live book" context.
  5. Hover each newly-badged chart header (Cohort Analysis, Cohort Loss
     Waterfall, Concentration, IRR by Vintage, Monthly Returns,
     Underwriting Drift, DPD Bucket Distribution, Monthly Delinquency
     Trend) — expect an A/B/C letter pill with a short §17 tooltip.

If anything renders off, the compile passed so the fix is likely a
small copy/threshold tweak rather than a structural rework.

### Known follow-ups flagged during session 36

None escalated to its own task. The 8 gaps closed cleanly:
  - Gap 1 (analytics_bridge §17 transmission) — covered 5 non-covenant
    builders (portfolio_analytics, credit_quality, concentration, stress,
    covenants-already-had-it); smoke-tested end-to-end.
  - Gap 2 (per-row walker) — 19 additional gaps surfaced in 7 compute
    functions, all fixed in the same commit.
  - Gap 3 (ConfidenceBadge on charts) — 8 chart panels badged. Not
    exhaustive across all 30+ charts; remaining ones are lower-traffic
    and can be done opportunistically when those charts are touched.
  - Gap 5 (FRAMEWORK_INDEX.md) — section-index row + Core Principle #8
    added.
  - Gap 6 (Ejari §17 exemption) — docstring added to
    `parse_ejari_workbook`.
  - Gap 7 (this file) — you're reading the updated version.
  - Gap 8 (PAR flip) — Klaim / SILQ / Aajil UI flipped to lifetime-primary.
    Ejari (single-PAR upstream) and Tamara (DPD distribution, no dual
    cards) correctly skipped.
  - Gap 8a (§17 taxonomy revision) — codified lifetime-primary as the
    universal Credit-Quality PAR convention in §17 "Dual-view pattern
    taxonomy."

### Pattern to watch in future audits

The §17 meta-audit tests now have TWO walkers running in CI:
  - `TestMetaAuditRateFieldDisclosure` — scalar fields at dict top-level
  - `TestMetaAuditPerRowRateFieldDisclosure` — per-row fields in nested
    lists (vintages[], by_product[], transition_matrix[], etc.)

If a new compute function surfaces a gap, the walker will break that
test with a structured finding message pointing at
`(function, list_or_scalar, field_name)`. Fix pattern:
  1. Add dict-level `population` + `confidence` to the return dict (covers
     all fields by inheritance), OR
  2. Add per-field `<field>_population` + `<field>_confidence` (fine
     granularity when one dict returns fields with different populations),
     OR
  3. Add `<list_name>_population` + `<list_name>_confidence` for lists
     whose rows share a uniform population, OR
  4. Add to `_DISCLOSURE_EXEMPT` / `_ROW_DISCLOSURE_EXEMPT` with a
     documented reason (descriptive stat not bound to a §17 population,
     upstream-aggregated data, etc.).

---

## Historical kickoff — session 27 real web_search smoke (archived)

The block below was drafted at the end of session 27 (April 20, 2026) for a
real-world web_search end-to-end smoke. Most of D1-D7 have either been
implemented in later sessions or are no longer tracked as priorities. Keep
for reference; refer to `CLAUDE.md` "Known Gaps & Next Steps" for the
current state of each.

<details>
<summary>Session 27 kickoff prompt (archived)</summary>

```
TASK: Real external.web_search end-to-end smoke test + visual UI verification.

CONTEXT:
- Branch: main at 49337ca or later. Session 27 shipped the External Intelligence
  four-layer system (Commits 1a/1b/2/3 plus follow-up fixes). 428 pytest + 16/16
  verify_external_intelligence.py already green on laptop.
- The one untested path is a real Claude web_search_20250305 call. Everything
  around it (pending-review queue, asset class mind, promotion pipeline,
  Layer 2.5 AI context, analyst agent tool exposure) has been verified with
  mocks. I need you to close that last 10%.

Pre-flight, flow steps, deferred items D1-D7 — see git history for
`tasks/next-session-kickoff.md` at commit dc73f9f or earlier for the full
prompt text. Superseded by the session-36 guidance at the top of this file.
```

</details>
