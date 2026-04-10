# Analysis Framework — Quick Reference Index

This file provides a fast lookup for Claude Code commands and sessions that need to reference the framework without reading the full document.

**Full document:** `core/ANALYSIS_FRAMEWORK.md`

---

## Section Map

| # | Section | Purpose | Used By |
|---|---------|---------|---------|
| 1 | Analytical Hierarchy (L1–L5) | Metric classification pyramid | All commands |
| 2 | Tape vs Portfolio Analytics | Dual-perspective philosophy | `/onboard-company`, `/extend-framework` |
| 3 | Asset Class Adaptations | Per-asset-class rules (Klaim, SILQ, Ejari) | `/onboard-company` |
| 4 | Leading vs Lagging Indicators | Temporal classification | `/extend-framework` |
| 5 | Separation Principle | Clean vs loss portfolio | `/framework-audit` |
| 6 | Denominator Discipline | Rate/ratio denominator rules | `/framework-audit`, `/extend-framework` |
| 7 | The Three Clocks | Time measurement (Origination, DPD, Operational) | `/onboard-company` |
| 8 | Collection Rate Disambiguation | GLR/CRR/ERR/CCR variants | `/extend-framework` |
| 9 | Dilution Framework | ABL dilution vs credit loss | `/onboard-company` (factoring) |
| 10 | Metric Definitions Reference | Full metric doctrine specs | `/methodology-sync`, `/extend-framework` |
| 11 | Methodology Onboarding Guide | New company checklist | `/onboard-company` |
| 12 | Compute Function Registry | Backend function → level mapping | `/methodology-sync`, `/framework-audit` |
| 13 | Column-to-Feature Dependency | Graceful degradation map | `/add-tape`, `/validate-tape` |
| 14 | Asset Class Decision Tree | Classification flowchart | `/onboard-company` |
| 15 | As-of-Date Filtering & Data Integrity | Backdated view rules, metric classification | `/validate-tape`, `/framework-audit` |
| 16 | Living Mind Architecture | Two-tier institutional memory, prompt injection layers | `/mind-review`, `/eod`, all AI endpoints |
| 17 | Legal Extraction & Facility Params Binding | AI extraction pipeline, 3-tier params merge | `/onboard-company`, portfolio analytics |
| 18 | Data Room & Document Classification | File ingestion, chunking, TF-IDF indexing | `/onboard-company`, `/research-query` |
| 19 | Research Hub & Query Engine | Dual-engine RAG (Claude + NotebookLM), citations | `/research-query` |
| 20 | IC Memo Generation Pipeline | 4 templates, analytics bridge, versioned workflow | `/generate-memo` |

---

## Existing Companies

| Company | analysis_type | Clock | Default Event | Backend Module | Tabs | Tests |
|---------|--------------|-------|---------------|----------------|------|-------|
| Klaim | `klaim` | Operational Delay | Insurance denial | `core/analysis.py` (34 fn) | 19 | 66 |
| SILQ | `silq` | Contractual DPD | DPD > 90 | `core/analysis_silq.py` (14 fn) | 13 | 68 |
| Ejari | `ejari_summary` | Pre-computed | Pre-computed | `core/analysis_ejari.py` (parser) | 12 | 0 |
| Tamara | `tamara_summary` | Contractual DPD | DPD > 120 (covenant), WO at DPD 90 | `core/analysis_tamara.py` (ETL+parser) | 14 KSA / 10 UAE | 0 |

---

## Framework Levels — Quick Lookup

| Level | Question | Color | Key Metrics |
|-------|----------|-------|-------------|
| **L1** | What do we own? | Blue | Total deals, originated, funded, outstanding, product mix, HHI |
| **L2** | How fast does capital return? | Teal | Collection rate (GLR), DSO, DTFC, pacing, timing |
| **L3** | What is deteriorating? | Gold | PAR 30+/60+/90+, health status, roll rates, cure rates |
| **L4** | Where did the dollars go? | Red | Gross/net default, LGD, EL, recovery, margins, loss waterfall |
| **L5** | What is about to happen? | Purple | DTFC trend, underwriting drift, concentration trend, covenants |

---

## Slash Commands Available

| Command | Trigger | Purpose |
|---------|---------|---------|
| `/onboard-company` | New company/product | Full 6-phase onboarding workflow |
| `/add-tape` | New tape file for existing company | Validate, compare, integrate |
| `/validate-tape` | Data quality check | Comprehensive tape validation |
| `/framework-audit` | Periodic compliance check | Audit all companies against framework |
| `/extend-framework` | New metric/tab/capability | Propagate changes across all layers |
| `/methodology-sync` | Drift detection | Verify methodology ↔ backend alignment |
| `/company-health` | Quick diagnostic | Coverage, freshness, gaps at a glance |
| `/eod` | Session close | Tests, docs, commit, push |
| `/research-query` | Research question | Query data room + analytics via dual-engine RAG |
| `/generate-memo` | IC memo creation | Generate memo from template with analytics bridge |
| `/mind-review` | Review institutional memory | Consolidate, promote, and audit mind entries |

---

## Core Principles (non-negotiable)

1. **Graceful degradation** — hide when unavailable, never estimate without labeling
2. **Denominator discipline** — every rate declares total/active/eligible
3. **Completed-only margins** — never include active deals in margin calculations
4. **Separation principle** — loss portfolio isolated from performance metrics
5. **Confidence grading** — A (observed), B (inferred), C (derived)
6. **Three clocks** — wrong clock = false PAR and false ineligibles
7. **Asset-class-centric** — methodology organized by asset class, not company name
8. **Living Mind feeds every AI prompt** — corrections, preferences, and IC feedback injected into all AI calls via 4-layer context
9. **Legal extraction before hardcoded defaults** — facility params resolved document > manual > hardcoded
10. **Memo numbers must match dashboard numbers** — analytics bridge calls the same compute functions as charts
