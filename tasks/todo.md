# Current Task Plan
Track active work here. Claude updates this as tasks progress.

---

## Active
_(none)_

## Up Next (near-term)
- [ ] BB Movement Attribution waterfall — period-over-period decomposition of borrowing base changes
- [ ] Duplicate/anomaly detection in validation — statistical outliers, duplicate counterparty+amount+date combos, balance identity violations
- [ ] Confidence grading badges on metrics — A (observed), B (inferred), C (derived) shown in UI
- [ ] Expand per-company methodology pages — add PAR, DTFC, DSO variants, loss waterfall definitions

---

## Completed — 2026-03-31
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
- [x] ABL-grade framework expansion — 5 new sections in ANALYSIS_FRAMEWORK.md:
  - Section 6: Denominator Discipline (three denominators, confidence grading)
  - Section 7: Three Clocks (origination age, contractual DPD, operational delay)
  - Section 8: Collection Rate Disambiguation (GLR vs CRR vs ERR vs CCR)
  - Section 9: Dilution Framework (Klaim denial = ABL dilution by reason code)
  - Section 10: Metric Doctrine (expanded definitions with denominator/weighting/confidence)
- [x] CLAUDE.md roadmap updated with tiered enhancement items from ABL manual + industry research
