# Weekend Deep Work — Token Utilisation Protocol

> **Usage:** In Claude Code, tell Claude which mode(s) to execute:
> `"Read WEEKEND_DEEP_WORK.md and execute MODE 3 (Architecture Review) against this codebase."`
>
> Or run the full combo:
> `"Read WEEKEND_DEEP_WORK.md and execute COMBO MODE."`

-----

## How This Works

This document defines **7 deep-work modes** designed for long, unattended Claude Code sessions. Each mode is self-contained with its own objective, scope, methodology, and output format. They are designed to run for extended periods — think overnight or over a weekend — consuming remaining weekly tokens on high-value analytical work.

-----

## Agent Rules

1. You are operating in **deep work mode**. Take your time. Be thorough, not fast.
2. Walk through every relevant file. Do not skip files or make assumptions.
3. Think step by step. Reason about what you find before writing conclusions.
4. Produce all output as **markdown report files** in the designated output directory — do NOT make code changes unless explicitly told to.
5. Structure reports so they are actionable: findings should be ranked by severity/impact and include specific file paths and line numbers.
6. If a mode asks you to generate code (e.g. tests), place generated code in a clearly labelled staging directory — never overwrite existing files.
7. At the end of every report, include a **TL;DR** section with the top 5 most important findings or recommendations.
8. When suggesting a fix for a **Critical** or **High** severity finding, provide a **before-and-after code snippet** in the report to illustrate the change, but keep the actual implementation in the `/staging/` directory.
9. **State-Save Rule:** Maintain a `progress.json` manifest in `/reports/deep-work/` (see below). After finishing each Mode, log: Mode Completed, Files Analyzed count, and Key Findings count. If a session is interrupted, resume from the last log entry.
10. **Two-Pass Rule:** Before deep-diving into any mode, perform a quick "File Map" pass — build a summary of the project's dependency graph. Use this map to prioritise analysis order: core engine files before auxiliary UI components, data layer before presentation layer.

### Progress Manifest (`/reports/deep-work/progress.json`)

Maintained across sessions. Structure:

```json
{
  "sessions": [
    {
      "date": "2026-04-10",
      "branch": "main",
      "modes_completed": ["MODE 1", "MODE 6"],
      "modes_partial": [],
      "findings_summary": {
        "MODE 1": { "critical": 2, "high": 5, "medium": 12, "low": 8 },
        "MODE 6": { "critical": 1, "high": 3, "medium": 7, "low": 4 }
      },
      "files_analyzed": 87,
      "report_files": [
        "reports/deep-work/2026-04-10-codebase-health.md",
        "reports/deep-work/2026-04-10-red-team-report.md"
      ]
    }
  ]
}
```

If resuming after an interruption, Claude reads this file first and picks up where the last session left off.

-----

## Recommended Frequency

Not every mode needs to run every week. Use this tiered schedule:

| Frequency | Modes | Trigger / Rationale |
|---|---|---|
| **Every session** | `/eod` slash command | Tests, .env check, commit, push — already built in |
| **Weekly (light)** | Mode 6 (Red Team) scoped to recent changes | Highest ROI — catches financial logic errors early |
| **Bi-weekly** | Mode 1 (Health Audit) + Mode 2 (Test Gen) | Keeps debt from accumulating, grows coverage |
| **Monthly / after major feature** | Mode 3 (Architecture Review) | After onboarding a new company or adding a pillar |
| **Monthly** | Mode 7 (Regression Validation) | Closes the loop on prior findings |
| **Quarterly** | Full Combo | Comprehensive baseline reset |

-----

## Two-Pass File Analysis Strategy

Before starting any mode, build the dependency map. For this project, the priority order is:

```
Pass 1 — Core Engines (analyse first, highest impact):
  core/analysis.py          → All Klaim computation (40+ functions)
  core/analysis_silq.py     → SILQ computation
  core/analysis_tamara.py   → Tamara parser + enrichment
  core/analysis_ejari.py    → Ejari ODS parser
  core/portfolio.py          → Portfolio analytics (borrowing base, concentration, covenants)
  core/loader.py             → File discovery, snapshot loading
  core/config.py             → Per-product configuration
  core/migration.py          → Multi-snapshot roll-rate analysis
  core/validation.py         → Data quality checks (Klaim)
  core/validation_silq.py    → Data quality checks (SILQ)

Pass 2 — API Layer (trace data flow):
  backend/main.py            → All REST endpoints
  backend/integration.py     → Inbound integration API
  backend/legal.py           → Legal analysis endpoints
  backend/auth.py            → Authentication
  backend/schemas.py         → Pydantic models

Pass 3 — Intelligence Layer:
  core/legal_extractor.py    → Multi-pass Claude extraction
  core/legal_compliance.py   → Compliance comparison
  core/legal_parser.py       → PDF parsing
  core/dataroom/engine.py    → Data room ingestion
  core/research/query_engine.py → Claude RAG
  core/memo/generator.py     → Memo AI generation
  core/mind/master_mind.py   → Fund-level memory
  core/mind/company_mind.py  → Per-company memory

Pass 4 — Frontend (presentation, lower priority for data integrity):
  frontend/src/pages/TapeAnalytics.jsx
  frontend/src/pages/PortfolioAnalytics.jsx
  frontend/src/contexts/CompanyContext.jsx
  frontend/src/components/charts/*.jsx
  frontend/src/components/portfolio/*.jsx
  frontend/src/services/api.js
```

This ensures that if context is exhausted mid-analysis, the highest-impact files have already been covered.

-----

## MODE 1: Codebase Health Audit

### Objective

Perform a comprehensive health check of the entire codebase, identifying technical debt, inconsistencies, silent failures, and maintainability risks.

### Methodology

**Step 1 — File Map (Two-Pass Rule)**
Build the dependency graph per the strategy above. Create a file inventory categorised by layer.

**Step 2 — Per-file analysis** — for each file, check for:
- Unused imports, dead code, unreachable branches
- Inconsistent error handling (some functions throw, others return null, others swallow silently)
- Functions longer than 50 lines that should be decomposed
- Magic numbers or hardcoded values that should be constants/config
- Type safety gaps (any types, missing validation, unchecked casts)
- Logging gaps (operations that could fail silently with no trace)
- Security concerns (unsanitised inputs, exposed secrets, overly permissive CORS)

**Step 3 — Cross-file analysis:**
- Naming inconsistencies (camelCase vs snake_case mixing, inconsistent terminology)
- Duplicated logic across modules that should be abstracted
- Circular or unnecessarily deep dependency chains
- Inconsistent API response shapes across endpoints

**Step 4 — Data integrity focus** (critical for this financial platform):
- Floating point arithmetic on monetary values
- Currency conversion edge cases (missing rates, stale rates, division precision)
- Date parsing assumptions (timezone handling, format inconsistencies)
- Empty/null/undefined handling in data transformation pipelines
- Off-by-one errors in date range filtering or pagination

**Step 5 — Validation Pass (Self-Audit)**
After generating initial findings:
1. Cross-reference every finding against `CLAUDE.md` and `core/ANALYSIS_FRAMEWORK.md`. If a finding is already documented as a **deliberate architectural decision**, downgrade it to "Noted — Intentional" and move it to an appendix.
2. Remove low-severity items that are standard patterns in FastAPI/Pandas/React (e.g., `pd.DataFrame` type hints, standard Recharts prop patterns).
3. For anything NOT documented in CLAUDE.md or the Framework that looks like it could be intentional, flag it as "Undocumented Decision — Needs Confirmation" rather than silently filtering it out.

The goal: the final report contains only **actionable technical debt**, not framework noise.

### Output

```
/reports/deep-work/YYYY-MM-DD-codebase-health.md
```

Organised by severity: Critical → High → Medium → Low → Appendix (Intentional Decisions). Each finding includes file path, line number, description, and suggested fix. Critical and High findings include before/after code snippets.

-----

## MODE 2: Test Generation Sprint

### Objective

Analyse the existing codebase, identify all untested or under-tested code paths, and generate a comprehensive test suite.

### Methodology

**Step 1 — Coverage mapping:** Walk through every module and identify:
- Functions/methods with zero test coverage
- Functions with partial coverage (happy path only, no edge cases)
- Integration points between layers (API → core → data) with no integration tests
- Data transformation functions (highest priority — financial errors hide here)

**Step 2 — Test generation priorities** (in order):
- **P0 — Data integrity**: Loan tape parsing, calculations, aggregations, currency conversions, separation principle
- **P1 — API contracts**: Every endpoint returns correct shape for valid input, correct errors for invalid input
- **P2 — Edge cases**: Empty datasets, single-record datasets, missing fields, malformed inputs, tapes with only old columns
- **P3 — Business logic**: Snapshot selection, date filtering, concentration calculations, vintage cohort logic, PAR method selection, covenant breach tracking
- **P4 — UI state**: Component rendering with various data states (loading, empty, error, populated)

**Step 3 — Test quality rules:**
- Every test must have a descriptive name that reads as a specification
- Include both positive and negative cases
- Use realistic test data shaped like actual loan tape records (reference the column list in CLAUDE.md)
- Tests must be independent — no shared mutable state between tests
- Include setup/teardown comments explaining the test scenario
- Financial calculations: assert to specific decimal places matching the platform's display precision

### Output

```
/staging/tests/                                        # Generated test files
/reports/deep-work/YYYY-MM-DD-test-coverage-plan.md    # Coverage analysis report
```

The report maps every function to its test status (covered / partially covered / uncovered) and explains the rationale for test prioritisation.

-----

## MODE 3: Architecture & Refactoring Review

### Objective

Evaluate the current architecture for extensibility, maintainability, and alignment with growth direction. Produce a refactoring roadmap.

### Methodology

**Step 1 — Dependency mapping:** Trace how data flows end-to-end:
- Upload/ingestion → parsing → transformation → storage → API → frontend rendering
- Identify where modules are tightly coupled (changes in one require changes in another)
- Map which modules know about specific data providers (Klaim, SILQ, Ejari, Tamara) vs which are provider-agnostic

**Step 2 — Extensibility analysis:**
- How hard is it to add a new data provider? List every file that would need modification.
- How hard is it to add a new dashboard view or analysis type?
- How hard is it to add a new report format or export type?
- Where are the abstraction boundaries? Are they in the right places?
- Evaluate the three ingestion patterns (raw tape, pre-computed summary, data room) — is the branching clean or growing into spaghetti?

**Step 3 — Pattern consistency:**
- Are similar operations handled the same way across the codebase?
- Is there a consistent pattern for API endpoints, error responses, state management?
- Are there places where a design pattern would reduce complexity?

**Step 4 — Performance considerations:**
- Are there operations that scan full datasets when they could use indexes or caching?
- Are there synchronous operations that block the UI that could be async?
- Are there redundant computations (same calculation done in multiple places)?

**Step 5 — Refactoring roadmap:**
- Prioritised list of refactors with effort estimates (small/medium/large)
- For each: what it improves, what risks it introduces, and suggested implementation approach
- Dependency order (which refactors should come first to enable others)

### Output

```
/reports/deep-work/YYYY-MM-DD-architecture-review.md
```

Include diagrams in mermaid syntax where helpful (dependency graphs, data flow, proposed architecture).

-----

## MODE 4: Documentation Sprint

### Objective

Generate comprehensive documentation that would allow a new team member to understand the entire system quickly.

### Methodology

1. **System overview**: High-level description of what the platform does, who it's for, and how data flows.
2. **API documentation**: For every endpoint — method, path, parameters, response shape, errors, auth requirements.
3. **Data model documentation**: Every entity, fields, types, relationships, data lifecycle, snapshot model.
4. **Component documentation** (frontend): Purpose of each major component, props/state, API connections.
5. **Architecture Decision Records (ADRs)**: Infer decisions from the code, document trade-offs, flag decisions that might need revisiting.
6. **Setup & Development guide**: Prerequisites, installation, local development, tests, troubleshooting.

### Output

```
/reports/deep-work/YYYY-MM-DD-documentation/
  ├── SYSTEM_OVERVIEW.md
  ├── API_REFERENCE.md
  ├── DATA_MODEL.md
  ├── COMPONENT_GUIDE.md
  ├── ARCHITECTURE_DECISIONS.md
  └── DEVELOPER_SETUP.md
```

-----

## MODE 5: AI Commentary & Prompt Optimisation

### Objective

Audit and improve the AI-generated analysis system — prompts, output quality, and evaluation methodology.

### Methodology

1. **Prompt inventory**: Find every prompt or template in the codebase. Document purpose, structure, and weaknesses.
2. **Prompt improvement proposals**: For each prompt, draft improved versions:
   - Version A: Optimised for precision (structured output, tighter constraints)
   - Version B: Optimised for insight depth (more analytical, nuanced)
   - Version C: Optimised for IC readability (executive-friendly, clear recommendations)
3. **Evaluation framework**: Propose a rubric for AI commentary quality (accuracy, insight depth, actionability, tone). Design test cases with known-good analysis.
4. **Context window efficiency**: Are prompts sending more data than needed? Could context be compressed? Would a two-pass approach (summary → deep dive) improve quality?
5. **Living Mind audit**: Review how the 4-layer context (Framework → Master Mind → Methodology → Company Mind) is assembled. Are layers properly filtered? Is any layer redundant or contradictory?

### Output

```
/reports/deep-work/YYYY-MM-DD-prompt-optimisation/
  ├── PROMPT_INVENTORY.md
  ├── IMPROVED_PROMPTS.md
  ├── EVAL_FRAMEWORK.md
  └── CONTEXT_EFFICIENCY.md
```

-----

## MODE 6: Red Team / Adversarial Review

### Objective

Think like a sceptical investor, a careful auditor, or a hostile user. Find every way the platform could produce misleading results, break silently, or erode trust.

### Methodology

**Section A — Data Integrity Attack Surface:**
- What happens with duplicate loan IDs? Deduplicated, double-counted, or ignored?
- What happens if a loan tape has records with future dates?
- What if amounts are negative, zero, or absurdly large?
- What if currency codes are non-standard or missing?
- What if the same loan appears across multiple snapshots with contradictory data?

**Section B — Calculation Verification:**
- Trace every financial calculation from input to display. Verify the maths.
- Check aggregation logic: do sums, averages, and weighted averages handle edge cases?
- Verify percentage calculations: are denominators ever zero? Are bases consistent?
- Check rounding: where does rounding happen and could accumulated rounding errors be material?

**Section C — Business Logic Stress Test** (financial platform-specific):
- **Covenant leakage:** Does the system correctly flag breaches when data is partial or stale? Test consecutive breach logic (`annotate_covenant_eod()`) with edge cases: exactly 2 consecutive periods, gap periods, partial data.
- **Waterfall errors:** Trace how the borrowing base waterfall applies deductions. Is the ordering correct? Are rounding decisions consistent (lender vs borrower favour)?
- **Time-travel data:** Verify how the system handles backdated records added to a snapshot already closed. The `_check_backdated()` guard blocks AI endpoints — but do raw data endpoints (`/summary`, `/charts/*`) also behave correctly with backdated as_of_date?
- **Separation Principle leakage:** Does `separate_portfolio()` consistently split clean vs loss across ALL downstream consumers, or do some endpoints bypass it?
- **PAR method consistency:** Three PAR methods (primary, Option C, fallback) — does the same snapshot always produce the same method deterministically, or could timing/ordering change the result?
- **Currency conversion compounding:** If a user toggles USD, navigates tabs, then toggles back to local — are any values double-converted? Is the multiplier applied once and only once per render?
- **Snapshot identity ambiguity:** The `_load()` matcher uses `filename` or `date` — could two tapes with the same date but different filenames cause ambiguous matching?
- **Cache key safety:** Cache keys exclude currency and normalize `as_of_date` — verify this normalization doesn't serve stale data for legitimately different queries.
- **Multi-document legal merge:** When multiple legal documents are merged, do conflicting covenant thresholds resolve correctly? Does the "primary credit_agreement wins" rule hold in all cases?

**Section D — UX Trust Audit:**
- Could a dashboard chart be misread? (truncated Y-axis, inconsistent scales between tabs)
- Are date ranges and "as-of" dates clearly communicated?
- Could a user compare two snapshots that aren't actually comparable?
- Are loading/error states clear enough that stale data isn't mistaken for current data?

**Section E — AI Commentary Risks:**
- Could the AI generate a confident-sounding but numerically wrong insight?
- Are there guardrails against hallucinated trends or fabricated comparisons?
- Could commentary contradict what the dashboard actually shows?
- Is the AI cache invalidated when underlying data changes (new tape for same company)?

**Section F — Failure Mode Catalogue:**
For every finding: what triggers it, what the user sees, what the actual impact is, and how to fix it.

### Output

```
/reports/deep-work/YYYY-MM-DD-red-team-report.md
```

Findings rated: 🔴 Critical (could cause wrong investment decisions) → 🟡 Warning (misleading but not dangerous) → 🔵 Improvement (hardening opportunity).

-----

## MODE 7: Regression Validation

### Objective

Close the loop on prior deep-work findings. Verify whether Critical and High severity issues from previous sessions have been addressed, and detect any regressions.

### Methodology

1. **Read prior reports**: Load the most recent `progress.json` and all referenced report files from previous sessions.
2. **Extract open findings**: Collect all Critical and High severity findings that were not marked as resolved.
3. **Verify each finding**:
   - Read the file and line number referenced in the finding.
   - Determine if the code has changed since the finding was logged.
   - If changed: verify the fix is correct and mark as **Resolved**.
   - If unchanged: mark as **Still Open** and re-assess severity (has it become more urgent due to new features built on top?).
   - If the file was deleted or refactored: trace the logic to its new location and re-evaluate.
4. **Detect new regressions**:
   - For each previously-resolved finding, verify it hasn't been re-introduced.
   - Check if new code added since the last session introduces similar patterns to previously-flagged issues.
5. **Update progress manifest**: Add a new session entry with the regression validation results.

### Output

```
/reports/deep-work/YYYY-MM-DD-regression-validation.md
```

Structure:
- **Resolved** — findings confirmed fixed, with commit/file references
- **Still Open** — findings not yet addressed, with updated severity
- **Regressed** — previously fixed issues that have returned
- **New Similar** — new code exhibiting patterns previously flagged

-----

## COMBO MODE: Full Deep Work Run

If you have substantial tokens remaining, run modes in this order:

1. **MODE 7** (Regression Validation) — if prior reports exist, close the loop first
2. **MODE 1** (Health Audit) — establishes the baseline understanding
3. **MODE 6** (Red Team) — highest-impact findings while codebase context is fresh
4. **MODE 2** (Test Generation) — informed by issues found in modes 1 and 6
5. **MODE 3** (Architecture Review) — strategic recommendations with full context
6. **MODE 5** (Prompt Optimisation) — if tokens remain
7. **MODE 4** (Documentation) — last, as it benefits from everything above

-----

## Configuration

```yaml
# Output directory
output_dir: ./reports/deep-work/

# Staging directory for generated code (tests, etc.)
staging_dir: ./staging/

# Files/directories to exclude from analysis
exclude:
  - node_modules/
  - .git/
  - dist/
  - build/
  - __pycache__/
  - .env
  - venv/
  - reports/ai_cache/

# Project-specific context files (cross-reference during Self-Audit)
context_files:
  - CLAUDE.md
  - core/ANALYSIS_FRAMEWORK.md
  - core/FRAMEWORK_INDEX.md
  - core/LEGAL_EXTRACTION_SCHEMA.md

# Focus priority (core engines first per Two-Pass Rule)
analysis_priority:
  - core/analysis.py
  - core/analysis_silq.py
  - core/portfolio.py
  - core/loader.py
  - backend/main.py
  - core/legal_extractor.py
  - core/legal_compliance.py
```

-----

## Version History

| Date | Change |
|---|---|
| 2026-04-10 | Initial version — 7 modes + combo, state-save, self-audit, two-pass, financial stress tests |
