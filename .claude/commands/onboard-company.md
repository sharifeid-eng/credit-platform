# Onboard New Company / Product

You are onboarding a new company or product into the Laith credit analytics platform. This is the most critical workflow in the project — it determines how every metric, dashboard, and AI prompt will behave for this company.

**You MUST follow the Analysis Framework (`core/ANALYSIS_FRAMEWORK.md`) as the authoritative reference for all analytical decisions.** Read it before starting if you haven't already this session.

---

## Phase 0 — Discovery & Classification

Before writing any code, answer these questions by asking the user. Collect ALL answers before proceeding.

### Company Identity
1. **Company name** (as it will appear in navigation and URLs)
2. **Product name** (e.g., "UAE_healthcare", "KSA", "RNPL")
3. **One-line description** (e.g., "Medical insurance claims factoring")
4. **Reported currency** (AED, USD, EUR, GBP, SAR, KWD)

### Asset Class Classification
5. **What is being financed?** (receivables, consumer loans, trade finance, rental payments, invoices, etc.)
6. **Who is the obligor?** (insurance company, consumer borrower, tenant, corporate, etc.)
7. **What constitutes a default/loss event?** (claim denial, DPD threshold, charge-off, non-payment)
8. **What is the recovery path?** (resubmission, collections, legal, restructuring)

### Delinquency Clock (Framework Section 7 — The Three Clocks)
9. **Which clock drives delinquency?**
   - **Contractual DPD** — borrower has a due date, delinquency = past due (SILQ-like)
   - **Operational Delay** — no borrower due date, delinquency = behind expected timeline (Klaim-like)
   - **Hybrid** — some products have due dates, others don't
   - **Pre-computed** — delinquency already computed in source data (Ejari-like)

### Data Format
10. **Raw loan tape or pre-computed summary?**
    - **Raw tape** → standard analysis pipeline (like Klaim/SILQ)
    - **Pre-computed workbook** → read-only summary dashboard (like Ejari)
11. **File format?** (CSV, Excel/XLSX, ODS)
12. **Does a facility agreement exist?** (determines Portfolio Analytics tabs)

### Analysis Type Decision (Framework Section 11 — Reuse or Create?)
13. **Is this asset class identical to an existing one?**
    - If YES → reuse existing `analysis_type` (e.g., another receivables factorer uses `"klaim"`)
    - If NO → new `analysis_type` needed (name it after the asset class, not the company)

---

## Phase 1 — Data Inspection

Once the user provides the tape file(s):

1. **Create the data directory:** `data/{company}/{product}/`
2. **Copy/move tape files** into the directory with proper naming: `YYYY-MM-DD_description.csv`
3. **Inspect the tape thoroughly:**
   - Load the file with pandas
   - Print: shape, column names, dtypes, first 5 rows, null counts
   - Identify key columns and map them to the framework's expected fields:

| Framework Concept | Column to Find | Required? |
|---|---|---|
| Deal/loan ID | Unique identifier | Yes |
| Origination date | Deal date, disbursement date | Yes |
| Face value | Purchase value, loan amount, principal | Yes |
| Funded amount | Purchase price, disbursed amount | Yes |
| Status | Active/Completed/Closed | Yes |
| Collected amount | Collected till date, total collected | Yes |
| Loss/denial/default amount | Denied, charged-off, written-off | For L3/L4 |
| Pending amount | Pending response, outstanding | For L3 |
| Counterparty/group | Provider, merchant, borrower group | For concentration |
| Product type | Sub-product classification | For segmentation |
| Expected amounts | Expected total, expected till date | For pacing |
| Due date / repayment deadline | Contract due date | For DPD clock |
| Collection curves | Expected/Actual at 30d intervals | For DSO/DTFC |
| Discount / rate | Discount rate, interest rate | For returns |
| Fee columns | Setup fee, other fee | For revenue |

4. **Identify what's available vs missing** — this determines which tabs are enabled (graceful degradation)
5. **Check for data quality issues** — duplicates, nulls in critical fields, negative values, date anomalies

---

## Phase 2 — Configuration

### 2a. Create `config.json`

Generate `data/{company}/{product}/config.json` with:

```json
{
  "currency": "{from discovery}",
  "description": "{from discovery}",
  "company": "{company}",
  "product": "{product}",
  "usd_rate": {from FALLBACK_RATES},
  "analysis_type": "{reused or new}",
  "face_value_column": "{column name for originated/funded value — e.g. Purchase value, Principal Amount, Disbursed_Amount (SAR)}",
  "tabs": [
    // Build tab list based on data availability — see Phase 3
  ]
}
```

If read-only summary: add `"hide_portfolio_tabs": true`
**Required:** `face_value_column` must be set — it drives the landing page "Face Value Analyzed" aggregate stat.

### 2b. Determine Tab Configuration

Map available columns to tabs using this decision matrix:

| Tab | Required Columns | Framework Level |
|---|---|---|
| Overview | ID, date, face value, funded, status, collected | L1 |
| Deployment | Date, face value (+ product type for by-product) | L1 |
| Collection | Date, face value, collected | L2 |
| Collections Timing | Collection curve columns (Expected/Actual at intervals) | L2 |
| Actual vs Expected | Expected total, expected till date, collected | L2 |
| Denial/Default Trend | Denied/charged-off amount | L3 |
| Ageing | Status, date, face value, collected, denied | L3 |
| Cohort Analysis | Date, face value, collected, denied | L2/L3 |
| Revenue | Face value, funded, collected, fees | L4 |
| Portfolio (Concentration) | Group/counterparty, face value | L1 |
| Returns | Funded, collected, discount, face value | L4 |
| Loss Waterfall | Date, face value, denied/defaulted, collected | L4 |
| Recovery Analysis | Denied/defaulted deals, collected amounts | L4 |
| Risk & Migration | Status across 2+ snapshots | L3 |
| Underwriting Drift | Date, face value, discount, product type | L5 |
| Segment Analysis | Product type, group, face value, collected | L1/L4 |
| Seasonality | Date, face value (12+ months of data) | L5 |
| CDR / CCR | Date, face value, denied/defaulted, collected | L4/L5 |
| Data Integrity | Any 2 snapshots | Cross-cutting |

Only include tabs whose required columns exist in the tape. Add the tab to `config.json` only if the data supports it.

---

## Phase 3 — Backend (if new analysis_type)

If reusing an existing `analysis_type`, skip this phase.

### 3a. Create `core/analysis_{type}.py`

Follow the established pattern from `core/analysis_silq.py`:
- Import pandas, numpy, logging
- Each compute function: `compute_{type}_{metric}(df, mult=1, ref_date=None) -> dict`
- Pure functions — no I/O, no FastAPI dependencies
- Return `{'available': False}` when required columns are missing (graceful degradation)
- Apply currency multiplier via `mult` parameter

**Minimum required functions** (one per framework level):
- L1: `compute_{type}_summary()` — KPI overview
- L2: `compute_{type}_collections()` — collection performance
- L3: `compute_{type}_delinquency()` — credit quality / PAR
- L4: `compute_{type}_cohorts()` — vintage analysis
- Additional functions as data allows

### 3b. Create `core/validation_{type}.py`

Follow `core/validation_silq.py` pattern:
- `validate_{type}(df) -> dict` with `critical`, `warnings`, `info`, `passed` fields
- Check: duplicates, null critical fields, negative values, date sanity, logical consistency

### 3c. Wire into `backend/main.py`

- Add chart routing for new analysis_type in the dynamic endpoint pattern
- Map tab slugs to compute functions
- Ensure `/summary`, `/charts/*`, `/validate` endpoints handle the new type

### 3d. Create tests

Follow `tests/test_analysis_silq.py` pattern:
- One test per compute function
- Test with realistic mock DataFrames
- Test graceful degradation (missing columns)
- Test edge cases (empty df, single row, all nulls)

---

## Phase 4 — Frontend (if new analysis_type)

If reusing an existing `analysis_type`, skip this phase — existing chart components will work.

### 4a. Chart Components (if needed)

- If the asset class has unique visualization needs, create components in `frontend/src/components/charts/{type}/`
- Reuse existing components (`KpiCard`, `ChartPanel`, `CohortTable`, etc.) wherever possible
- Follow Framer Motion animation patterns (stagger, fade-in, hover effects)

### 4b. Methodology Sections

Add to `frontend/src/pages/Methodology.jsx`:
1. Create `{TYPE}_SECTIONS` array with sections covering all 5 framework levels
2. Add `level` tags (L1–L5) to each section
3. Use existing reusable components: `<Section>`, `<Subsection>`, `<Metric>`, `<Table>`, `<Note>`
4. Add conditional branch: `const SECTIONS = is{Type} ? {TYPE}_SECTIONS : ...`

### 4c. Sidebar Configuration

If the tab structure differs significantly from Klaim/SILQ, update `Sidebar.jsx` to handle the new tab set. The sidebar reads from `config.tabs` — usually no changes needed.

---

## Phase 5 — Verification Checklist

Run through this checklist before marking onboarding complete:

### Data Integrity
- [ ] Tape loads without errors
- [ ] All expected columns mapped
- [ ] Validation checks pass (or known issues documented)
- [ ] `config.json` is valid JSON with all required fields

### Framework Compliance (all 5 levels)
- [ ] **L1 — Size & Composition:** Summary KPIs compute correctly
- [ ] **L2 — Cash Conversion:** Collection rate formula matches framework definition (GLR)
- [ ] **L3 — Credit Quality:** Correct delinquency clock selected and implemented
- [ ] **L4 — Loss Attribution:** Default definition documented and consistent
- [ ] **L5 — Forward Signals:** At least one leading indicator available (or gracefully hidden)

### Denominator Discipline (Framework Section 6)
- [ ] Every rate metric declares its denominator (total/active/eligible)
- [ ] PAR uses active outstanding (Tape) or eligible outstanding (Portfolio)
- [ ] Margins computed on completed deals only

### Separation Principle (Framework Section 5)
- [ ] Loss deals identified and separable from clean portfolio
- [ ] Performance metrics use clean portfolio when separation is active

### Confidence Grading (Framework Section 6)
- [ ] Each metric classified as A (observed), B (inferred), or C (derived)
- [ ] Derived metrics labeled in UI

### UI Verification
- [ ] All tabs render without errors
- [ ] Graceful degradation: missing-column tabs are hidden, not broken
- [ ] Currency toggle works (local ↔ USD)
- [ ] Snapshot switching reloads all data
- [ ] AI commentary generates successfully
- [ ] Methodology page renders correctly for this company

### Tests
- [ ] All new compute functions have unit tests
- [ ] `pytest tests/ -q` passes
- [ ] Integration test: full tab render cycle works

---

## Phase 6 — Documentation

After verification:

1. **Update `CLAUDE.md`:**
   - Add company to "Current portfolio companies" section
   - Update "What's Working" section
   - Add any new architectural decisions

2. **Update `core/ANALYSIS_FRAMEWORK.md`:**
   - Add the new asset class to Section 3 (Asset Class Adaptations)
   - Add to Section 11 (Existing Asset Class Reference table)

3. **Commit and push** — use `/eod` for full session close

---

## Quick Reference: Existing Patterns

| Company | analysis_type | Clock | Default Event | Backend Module | Tabs |
|---|---|---|---|---|---|
| Klaim | `klaim` | Operational Delay | Insurance denial | `core/analysis.py` (34 functions) | 19 |
| SILQ | `silq` | Contractual DPD | DPD > 90 / charge-off | `core/analysis_silq.py` (14 functions) | 13 |
| Ejari | `ejari_summary` | Pre-computed | Pre-computed | `core/analysis_ejari.py` (parser only) | 12 |
