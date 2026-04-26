# Section A + B: Data Integrity & Calculation Verification

**Files analyzed:** 12 (analysis.py, analysis_silq.py, analysis_aajil.py, analysis_tamara.py, analysis_ejari.py, portfolio.py, loader.py, db_loader.py, migration.py, validation.py, validation_silq.py, validation_aajil.py)
**Findings:** Critical 9 | Warning 17 | Improvement 9 (35 total)
**Date:** 2026-04-26

---

## Findings

### 🔴 CRITICAL Finding 1: BB payer-concentration adjustment double-counts ineligible exposure
- **File:** `core/portfolio.py:787-793` (`compute_klaim_borrowing_base`)
- **Trigger:** Any Klaim payer (Group) whose total active outstanding exceeds 10% of *eligible* A/R, while a portion of that payer's exposure is already deducted as ineligible (deals > 91 days, or denied > 50% of PV).
- **Impact:** `payer_out` is computed by summing `_out` (full active outstanding) for every active deal regardless of eligibility. The compliance ratio is then `amount / eligible`, where `eligible = total_ar − (ineligible_age + ineligible_denied)`. So the numerator is the payer's *full* exposure but the denominator is the post-deduction pool — a mathematical mismatch that inflates the apparent concentration. **The deductions then double-count**: ineligible deals are first stripped from `eligible` and then a second time as part of `excess = amount − eligible × 0.10`. A payer with $5M total outstanding (of which $3M ineligible-by-age) on a $30M eligible book would be flagged as 16.7% concentration when the correct measure is $2M / $30M = 6.7%. This understates BB and could falsely suppress draws.
- **Fix:** Compute `payer_eligible = active_eligible.groupby('Group')['_out'].sum()` *after* applying the ineligibility masks (age, denial), then test `payer_eligible / eligible > threshold`. Excess should be `payer_eligible − eligible × threshold`.
- **Snippet:**
```python
# Current (buggy):
payer_out = active.groupby('Group')['_out'].sum()      # full outstanding
for payer, amount in payer_out.items():
    if amount / eligible > payer_threshold:            # asymmetric ratio
        excess = amount - eligible * payer_threshold
        conc_adj += excess
```
```python
# Fix:
elig_mask = (age <= max_age_days) & (denied_pct <= 0.5)
elig_payer_out = active.loc[elig_mask].groupby('Group')['_out'].sum()
for payer, amount in elig_payer_out.items():
    if amount / eligible > payer_threshold:
        conc_adj += amount - eligible * payer_threshold
```

---

### 🔴 CRITICAL Finding 2: `migration.py` cure-rate matrix Cartesian-explodes on duplicate IDs
- **File:** `core/migration.py:90-94` (`compute_roll_rates`)
- **Trigger:** Same `Deal ID` appears more than once in either snapshot (the platform documents this as a possible Klaim "denial-reopen pattern" — Status reverses from Completed → Executed, sometimes also a duplicate row).
- **Impact:** `merged = old[[id_col, ...]].merge(new[[id_col, ...]], on=id_col, suffixes=('_old', '_new'))` performs an inner merge with no `validate=` argument or de-dup. If `old` has two rows with the same ID (1×N) and `new` has three (M×K), the merge produces N×K rows for that ID — every transition for that deal is counted N×K times. Counts in the transition matrix and cure rates are inflated, often dramatically. The reported `total_matched_deals` would also exceed the count of distinct IDs.
- **Fix:** Either (a) `merged = ... merge(..., validate='one_to_one')` to fail loudly on duplicates, or (b) `old_dedup = old.drop_duplicates(subset=id_col, keep='last')` (and same for new) before merging — use `keep='last'` to track the most recent state. Decision should be documented.

---

### 🔴 CRITICAL Finding 3: Klaim `compute_klaim_covenants` PAR30 fallback flags any active deal >30 days old as at-risk
- **File:** `core/portfolio.py:1207-1214`
- **Trigger:** `Pending insurance response` column is NOT present on the tape (any pre-Apr-2026 tape, or any future Klaim-shaped product without that column).
- **Impact:** Without `Pending`, the function uses `par30_amount = float(outstanding[age_active > 30].sum())`. For Klaim healthcare receivables, normal collection cycles routinely run 30-90 days. **Almost the entire active book becomes "PAR30"**, and the covenant (≤7%) appears to be in catastrophic breach. The value is also reported with `confidence='B'` and `method='age_pending'` even though the Pending guard is not active — so the IC sees a confidence-B PAR30 reading that has no relationship to actual delinquency.
- **Fix:** When `Pending insurance response` is absent, return `available=False` for the covenant (graceful degradation), or use the `Expected till date` shortfall proxy already implemented in `compute_par()`. Do NOT silently fall through to age-only.
- **Snippet:**
```python
# Current:
par30_amount = float(outstanding[age_active > 30].sum()) if total_ar > 0 else 0
if 'Pending insurance response' in active.columns:
    pending = active['Pending insurance response'].fillna(0) * mult
    overdue_mask = (age_active > 90) & (pending > 0)
    par30_amount = float(outstanding[overdue_mask].sum())   # override
# But the unconditional pre-override sum is what gets used if column absent.
```

---

### 🔴 CRITICAL Finding 4: `compute_returns_analysis` `weighted_avg_discount` produces nonsensical value when discount is in fractions but treated as percentage
- **File:** `core/analysis.py:696`
- **Trigger:** Always — every Klaim tape stores `Discount` as a fraction (0.04 = 4%, per CLAUDE.md "values range 1%–41%, concentrated at 4–7%").
- **Impact:** The formula is `(df['Discount'] * df['Purchase value']).sum() / df['Purchase value'].sum() * 100`. Distributively this equals `weighted_avg_discount_fraction × 100` — fine. But on line 695 immediately above, `avg_discount` is `float(df['Discount'].mean()) * 100` (raw mean × 100). Both are in % units. **However**: if any vintage where the column has been mis-imported as already-percent (e.g., 5.0 instead of 0.05) leaks through, the weighted average silently produces 500%, while the unweighted mean would produce 5%. There's no upper bound check on the output. The `validation.py` "Discount > 100%" check (line 144) catches `disc > 1` but only emits a warning — `compute_returns_analysis` doesn't refuse to run. IC sees nonsense weighted discount.
- **Fix:** Either (a) coerce + clip Discount to `[0, 1]` at the top of the function with a logged exclusion count, or (b) emit a `data_gaps[]` flag if `df['Discount'].max() > 1` and skip the weighted computation.

---

### 🔴 CRITICAL Finding 5: `_compute_pv_adjusted_lgd` uses `deal_dates.max()` as snapshot proxy — produces zero-year-to-recovery on every defaulted deal in the latest vintage
- **File:** `core/analysis.py:1231-1240`
- **Trigger:** Always when at least one defaulted deal sits in the latest vintage month.
- **Impact:** The function computes `snapshot_date = deal_dates.max()` (line 1232) on the *defaulted-only* subset, then `years_to_recovery = ((snapshot_date - deal_dates).dt.days / 365.25).clip(lower=0.01)`. Every defaulted deal whose `Deal date == max(defaulted deal dates)` gets `years_to_recovery = 0` clipped to `0.01`, yielding a discount factor near 1 — recoveries are NOT discounted. Deals with later actual recovery activity but earlier deal dates get OVER-discounted. The result `lgd_pv_adjusted` is a meaningless mix of "almost-not-discounted" and "over-discounted" depending on each deal's age relative to the latest defaulted vintage. IC sees a precise-looking PV-adjusted LGD that doesn't reflect actual time-to-recovery.
- **Fix:** Pass the snapshot date explicitly as a parameter (the caller `compute_expected_loss` already has access to `as_of_date`), or use `pd.Timestamp.now()` as the upper bound. Do NOT derive snapshot date from a subset of the data.
- **Snippet:**
```python
# Current (line 1232):
snapshot_date = deal_dates.max()
# years 0 for the most recent defaulted deal; over-discounts older ones.
```
```python
# Fix:
def _compute_pv_adjusted_lgd(completed, mult, has_prov, as_of_date=None, annual_rate=0.08):
    snapshot_date = pd.Timestamp(as_of_date) if as_of_date else pd.Timestamp.now()
    ...
```

---

### 🔴 CRITICAL Finding 6: `_klaim_wal_total` uses `_klaim_deal_age_days` with `pd.Timestamp.now()` default when `ref_date` is None
- **File:** `core/portfolio.py:631-639` + 712 + 1147
- **Trigger:** Caller passes `ref_date=None` to `compute_klaim_covenants` (any backdated view, any test, any background recompute).
- **Impact:** `_klaim_deal_age_days` uses `pd.Timestamp.now().normalize()` when `ref_date is None`. This is also where Active WAL is computed (line 1147: `wal_active = float(np.average(age, weights=outstanding))`). On a 2026-03-03 snapshot, evaluating WAL "as of None" computes age vs current calendar day — making the historic snapshot's WAL appear to drift upward each day until the test passes again. The covenant compliance decision (Path A: WAL ≤ 70d) is therefore non-deterministic across days. Same bug in `compute_klaim_borrowing_base` (line 772) for ineligibility-age determination — yesterday's BB is different from today's BB on the same snapshot.
- **Fix:** When `ref_date is None`, fall back to the snapshot's `taken_at` date (passed in from the caller) rather than `Timestamp.now()`. The Snapshot ORM record carries this. Per CLAUDE.md session 31, this is exactly the bug class snapshot-dimensioning was meant to eliminate; the helper still has the legacy default.

---

### 🔴 CRITICAL Finding 7: Compute functions silently drop NaN-Group rows from concentration but include them in denominator
- **File:** `core/analysis.py:600-612`, `615-627`, `compute_concentration`
- **Trigger:** Any deal with `Group` (or `Provider`) = NaN — common when a tape has missing or unmapped counterparty.
- **Impact:** `df.groupby('Group')` drops NaN by default. Group shares are computed against `total = df['Purchase value'].sum() * mult` (which INCLUDES the NaN-Group rows). So the per-group `percentage` column does NOT sum to 100% on tapes with missing-Group rows. HHI is also understated — the unattributed PV is silently treated as zero concentration when in reality it could be a single hidden counterparty. The bug compounds in `compute_klaim_concentration_limits` line 942 (`active.groupby('Group')`) — if the largest counterparty's rows are NaN, the test passes when it shouldn't.
- **Fix:** Either (a) `df.groupby('Group', dropna=False)` and surface NaN as an explicit "Unknown" bucket so IC sees the gap, or (b) report a `null_group_count` and `null_group_pv` field in the result so consumers can subtract from total.

---

### 🔴 CRITICAL Finding 8: `compute_klaim_covenants` Paid vs Due `period_deals` filter has wrong operator precedence
- **File:** `core/portfolio.py:1328-1331` and 1334-1337
- **Trigger:** Any call to `compute_klaim_covenants` with `Status` column on the tape.
- **Impact:** The expression is:
```python
period_deals = df_pvd[
    (df_pvd['_exp_pay_date'] <= period_end) &
    (df_pvd['Status'] == 'Executed') if 'Status' in df_pvd.columns else True
]
```
Python evaluates this as `df_pvd[ A if 'Status' in df_pvd.columns else True ]` where A is `(df_pvd['_exp_pay_date'] <= period_end) & (df_pvd['Status'] == 'Executed')`. The `if/else` ternary binds OUTSIDE the bitwise expression — so when the column is missing, the result is `df_pvd[True]` (boolean scalar), which raises `TypeError` or returns an empty result depending on pandas version. When the column IS present, the filter works but ONLY by accident. The same bug is repeated in the cumulative-method branch (line 1284-1287). It also corrupts the Collection Ratio covenant (lines 1283-1287). The covenants `current` value silently goes to 0 → reported as breach.
- **Fix:** Wrap the bitwise expression in parens before the ternary: `period_deals = df_pvd[((df_pvd['_exp_pay_date'] <= period_end) & (df_pvd['Status'] == 'Executed')) if 'Status' in df_pvd.columns else (df_pvd['_exp_pay_date'] <= period_end)]`.

---

### 🔴 CRITICAL Finding 9: `compute_silq_concentration` `shop_util['util_pct']` divides outstanding by limit, then clips `>100%` away
- **File:** `core/analysis_silq.py:447`
- **Trigger:** Any shop where current outstanding genuinely exceeds its credit limit (a real over-utilisation event — extension, rollover, late payment).
- **Impact:** `(shop_util['outstanding'] / shop_util['limit'] * 100).clip(0, 100)`. Clipping at 100 hides the most concerning data points: a shop with `outstanding = 2 × limit` should jump out as a 200% utilisation breach but appears as exactly 100%. The displayed top-15 is sorted by `util_pct` so all over-limit shops bunch at the top tied at 100% — IC cannot distinguish the worst offender. Concentration limits / borrowing-base eligibility checks downstream may also be silently masked.
- **Fix:** Remove the `.clip(0, 100)` and let the value range freely. Cap the *display* (in JSX) if necessary but keep the data honest.

---

### 🟡 WARNING Finding 10: `filter_by_date` silently drops rows with NaT `Deal date`
- **File:** `core/analysis.py:36-46`
- **Trigger:** Any tape row with unparseable / missing `Deal date`. With `errors='coerce'`, malformed dates become `NaT`.
- **Impact:** `df['Deal date'] <= pd.to_datetime(as_of_date)` — `NaT` comparisons are False, so rows are silently dropped from the as-of view. There's no `affected_rows` count surfaced. If the missing-date rows have material PV, `total_purchase_value` shrinks without explanation. Validation flags null dates as a warning, but if user opens "as of Mar 31, 2026" view, they see fewer deals than the filename-snapshot view.
- **Fix:** Emit a `dropped_rows_invalid_date` count in any compute function consuming `filter_by_date`, OR keep NaT rows when `as_of_date` is None (the function already does this) but add an explicit gap report when `as_of_date` is provided AND NaT rows exist.

---

### 🟡 WARNING Finding 11: `compute_summary` `avg_discount` does not coerce non-numeric values
- **File:** `core/analysis.py:111`
- **Trigger:** Tape `Discount` column contains string values (e.g., "5%", "5.0", or empty strings).
- **Impact:** `float(df['Discount'].mean())` — pandas `.mean()` coerces if the column is already numeric, but if the column is dtype `object` (string), `.mean()` raises a `TypeError`. The endpoint then 500s. The companion line 695 in `compute_returns_analysis` has the same exposure (`float(df['Discount'].mean()) * 100`). Compare `compute_concentration` which DOES wrap in `pd.to_numeric(..., errors='coerce')` — inconsistent.
- **Fix:** Apply `pd.to_numeric(df['Discount'], errors='coerce').mean()` everywhere, matching the most defensive call site.

---

### 🟡 WARNING Finding 12: `compute_loss_categorization` removes-and-reuses `remaining` mask without ensuring exclusivity
- **File:** `core/analysis.py:2602-2621`
- **Trigger:** Any tape where the "provider issue" rule (Group denial rate > 3× avg) and the "small denial < 5000 × mult" rule overlap.
- **Impact:** The function classifies as `Provider Issue` first (line 2603-2606), then uses `remaining = defaulted[~provider_mask]` and applies the small-denial rule on `remaining`. **But** the `provider_mask` is computed ONCE on `defaulted` and never re-applied; once `remaining = remaining[~small_mask]` runs, the categories are exclusive — fine. The bug is that the third bucket's `denied_amt` may still be in different units: `defaulted['denied_amt'] = den[defaulted_mask].values` uses `.values` (positional alignment), but `remaining = defaulted[~provider_mask]` re-indexes. If anywhere along the way the index gets reset (e.g., user passes a df with non-monotonic index), `.values` may misalign. Low risk but worth noting.
- **Fix:** Use `defaulted = df[defaulted_mask].copy().reset_index(drop=True)` and assign columns by position once at the top.

---

### 🟡 WARNING Finding 13: SILQ `validate_silq_tape` line 19 — `dropna().duplicated()` undercounts dupes
- **File:** `core/validation_silq.py:19`
- **Trigger:** Any SILQ tape with both `NaN` Deal IDs and duplicate non-NaN Deal IDs.
- **Impact:** `df['Deal ID'].dropna().duplicated()` — `.duplicated()` (without `keep=False`) returns True only for the SECOND, THIRD, ... occurrence of each duplicate group, so a deal appearing 3 times is reported as 2 dupes. More importantly, dropping NaN BEFORE `.duplicated()` masks the case where multiple rows have NaN IDs — those are silent duplicates that wouldn't be caught at all. Validation says "no duplicates found" while real entries are missing IDs. The same flaw exists in `validation_aajil.py:27`.
- **Fix:** Use `df.duplicated(subset=['Deal ID'], keep=False).sum()` to count ALL rows in any dup group. Separately count `df['Deal ID'].isna().sum()` and surface that as a distinct warning.

---

### 🟡 WARNING Finding 14: `compute_par` Option C `_expected_pct` returns `1.0` ceiling when no benchmark — flatlines residual deals
- **File:** `core/analysis.py:1841-1845`
- **Trigger:** Any active deal whose `deal_age` exceeds the largest benchmark cutoff (720 days).
- **Impact:** `_expected_pct(age)` returns `benchmark[-1][1]` when the benchmark exhausts, or `1.0` if the entire benchmark is empty. Since `benchmark` is `None` already returns early, the `1.0` fallback only fires when `benchmark = []` — but that branch is also pre-screened (`if len(buckets) >= 3`). The risk is that mature deals (>720d) are pinned to the LATEST observed median collection rate, even if that median was based on much younger deals. PAR for those very-old active deals is then artificially low. IC may miss "long-tail" exposure.
- **Fix:** Add a sentinel: deals with `age > max(benchmark cutoff)` get assigned `expected_pct = 1.0` (i.e., should be fully collected by now) so their `pct_behind = 1.0 - coll_pct` correctly flags them as severely past due. Or return `available=False` if more than X% of the active book is past the benchmark range.

---

### 🟡 WARNING Finding 15: `compute_silq_summary` `max(total_active_out, 1)` masks divide-by-zero with a $1 denominator
- **File:** `core/analysis_silq.py:125-127`, `237`, `241-243`, `260-261`, `545`, `568`, `688-689`
- **Trigger:** A SILQ snapshot where `total_active_out` (active outstanding in raw SAR) is genuinely small but nonzero — e.g., a portfolio with only one $0.50 active loan, or a brand-new product with first-day disbursement of $0.99.
- **Impact:** `par30 = par30_amount / max(total_active_out, 1) * 100` — if `total_active_out = 0.5`, the denominator becomes `1` (a hardcoded number, not the real $0.5), so the resulting ratio is HALF the actual ratio. This is hidden by the `if total_active_out else 0` ternary (returns 0 if exactly zero), but for any value in `(0, 1)` it produces a wrong number. The pattern is repeated 6+ times in this file. SILQ tapes are SAR-denominated; sub-1-SAR active outstanding is unlikely in production but possible during rollover days.
- **Fix:** Change to `if total_active_out > 0 else 0` and use `total_active_out` (no `max(..., 1)`) as denominator.

---

### 🟡 WARNING Finding 16: `compute_aajil_concentration` line 625 crashes on non-numeric customer IDs
- **File:** `core/analysis_aajil.py:625`
- **Trigger:** Aajil tape where `Unique Customer Code` is non-numeric (e.g., "C-12345", "ACME-LTD"), or has any value that fails `int()` conversion.
- **Impact:** `'customer_id': str(int(r[C_CUSTOMER_ID])) if pd.notna(r[C_CUSTOMER_ID]) else 'Unknown'` — calls `int()` on the customer code. If the value is "ACME-LTD", `int()` raises `ValueError`, the entire `compute_aajil_concentration` 500s. CLAUDE.md says current Aajil tape uses numeric customer IDs, but ANY non-numeric code (e.g., a future SME enrolled with an alphanumeric ID) breaks the endpoint. Per defensive-coding doctrine, IC dashboards shouldn't 500 on a single bad cell.
- **Fix:** Replace with `'customer_id': str(r[C_CUSTOMER_ID]) if pd.notna(r[C_CUSTOMER_ID]) else 'Unknown'`. Drop the `int()` cast — there's no semantic reason to require numeric.

---

### 🟡 WARNING Finding 17: `_safe()` in `analysis_silq.py` collapses NaN/inf to 0 — silently corrupts metrics
- **File:** `core/analysis_silq.py:73-87`
- **Trigger:** Any compute path that produces inf (e.g., `0/0` not pre-guarded, or a runaway weighted average) or NaN (e.g., empty groupby).
- **Impact:** `_safe()` returns `0` when input is NaN or inf. This is JSON-safe, but it means "no data" and "real zero" are indistinguishable downstream. The frontend can't tell whether a 0% PAR30 is "no active loans" or "no measurement". The doctrine in CLAUDE.md says metrics should "hide gracefully, not estimate" — collapsing missingness to 0 is a form of estimation. Compare `analysis_aajil.py` `_safe()` line 60 which returns `None` for NaN/inf — better.
- **Fix:** Change SILQ `_safe()` NaN/inf branch to return `None`. Frontend then renders "—" for missing data. Run a small reconciliation test on representative data before merging.

---

### 🟡 WARNING Finding 18: `compute_klaim_covenants` Collection Ratio has stray `dir()` checks that always evaluate True
- **File:** `core/portfolio.py:1308-1309`, `1365-1366`
- **Trigger:** Always — at every Klaim covenant evaluation.
- **Impact:** The breakdown rows have `_safe(total_coll if 'total_coll' in dir() else 0)`. `dir()` returns the names in the *local* scope of `compute_klaim_covenants`, not where the f-string is evaluated. By the time these lines run, `total_coll` and `total_pv` may or may not be in scope depending on whether the previous `if 'Deal date' in df.columns and 'Collected till date' in df.columns` branch ran. When the branch doesn't run, `total_coll` is undefined and `'total_coll' in dir()` is False — the breakdown shows 0. **But `coll_ratio` ALSO would be 0 because of the same condition** — so the displayed values are at least consistent. The bug is silent fragility: if anyone refactors this and renames `total_coll`, the `dir()` check silently keeps reporting 0 while `coll_ratio` keeps a stale prior-iteration value.
- **Fix:** Initialise `total_coll = 0; total_pv = 0` before the if-branch, and drop the `dir()` checks entirely.

---

### 🟡 WARNING Finding 19: `compute_returns_analysis` discount-band groupby silently drops rows with `Discount > 1.0` or `Discount < 0`
- **File:** `core/analysis.py:755-760`
- **Trigger:** Any tape where validation flagged "Discount > 100%" or "Negative Discount" warnings.
- **Impact:** `pd.cut` with `bins=[0, 0.04, 0.06, 0.08, 0.10, 0.15, 1.0]` returns NaN for values outside the bins, and `groupby('discount_band', observed=True)` drops NaN buckets. Deals with bad discount values disappear entirely from the discount-band table — but they're still included in the portfolio-level `summary` (`avg_discount`, `weighted_avg_discount`). Inconsistency: portfolio totals don't reconcile with the sum of band totals. IC sees a band table that doesn't add up to portfolio totals and can't audit the discrepancy.
- **Fix:** Add an "Outside [0%, 100%]" residual band, or report a `dropped_rows` count alongside the band table.

---

### 🟡 WARNING Finding 20: `compute_underwriting_drift` `cohort['avg_discount'] = round(...)` doesn't unit-convert
- **File:** `core/analysis.py:2321-2322`
- **Trigger:** Klaim tape where Discount stored as raw fraction (typical, 0.04 = 4%).
- **Impact:** `cohort['avg_discount'] = round(float(grp['Discount'].mean()), 4)` — stores the raw FRACTIONAL value (e.g., 0.0524). The drift comparison at line 2354-2359 then computes `abs(r_disc - p_disc) / p_disc > 0.10` — relative %, ok. But the FRONTEND likely formats as `{val:.2%}`. The only risk is inconsistency: every other "discount" output in `compute_returns_analysis` multiplies by 100 (`*100`) before storing. So drift uses raw fractions while returns uses percentages. JSX components for "drift" would display 0.05 instead of 5%, or vice versa. Easy IC confusion.
- **Fix:** Pick one convention (raw or *100) and propagate consistently across all compute outputs.

---

### 🟡 WARNING Finding 21: `compute_silq_covenants` Repayment at Term covenant is missing methodology-comparable info on partial coverage
- **File:** `core/analysis_silq.py:925-965`
- **Trigger:** SILQ snapshot where `Repayment_Deadline` falls in the 3-6mo lookback window for fewer than ~10 loans.
- **Impact:** When `len(qualifying) > 0`, `rat_available = True` is set unconditionally. A covenant value computed off 1-2 loans is reported with confidence A (line 961: `'confidence': 'A'`). A 100% Repayment-at-Term reading from one loan is presented identically to one based on 100 loans — IC has no way to distinguish high-N from low-N validity. CDR/CCR has a similar issue but it has a `min_seasoning < 3 months` skip (line 3232 in analysis.py).
- **Fix:** Add a `qualifying_count` field and a `low_n_warning: bool` (e.g., n < 20). Rendering layer can show "n=3" or "Low sample" badge.

---

### 🟡 WARNING Finding 22: `compute_klaim_borrowing_base` advance-rate region split formula is mathematically wrong
- **File:** `core/portfolio.py:813-823`
- **Trigger:** Klaim portfolio where Region/Country/Currency column is present.
- **Impact:** Line 817: `r_elig = min(r_elig, eligible_after_conc * (r_elig / max(outstanding.sum(), 1)))`. The formula is meant to allocate the eligible pool back to regions in proportion to their outstanding share. **But `outstanding.sum()` here is the TOTAL active outstanding (all regions), and `r_elig` was just set to that region's outstanding sum.** So the right-hand side is `eligible_after_conc × (region_out / total_active_out)`. Then `min()` picks whichever is smaller. If `eligible_after_conc < total_active_out` (typical, due to deductions), the per-region eligible is the proportional share — fine. But the `min()` comparison is against the FULL region outstanding, which is always ≥ the proportional share. So `min()` never has any effect — dead code, but it hides a more concerning issue: regions with disproportionately-much-ineligible (e.g., one country has all the >91d deals) get the SAME pro-rata allocation as healthier regions. The displayed per-region "eligible_ar" overstates the troubled region.
- **Fix:** Compute per-region ineligibility deductions explicitly (re-apply `age > max_age_days` and denial mask within each region groupby) rather than back-allocating proportionally.

---

### 🟡 WARNING Finding 23: `compute_silq_borrowing_base` advance rate is hardcoded
- **File:** `core/analysis_silq.py:748`
- **Trigger:** Always — every SILQ portfolio analytics call.
- **Impact:** `advance_rate = 0.80` is hardcoded inside the analysis module. This contradicts CLAUDE.md's "3-tier facility params priority: document → manual → hardcoded default" — the document- and manual-level overrides cannot reach this function because it doesn't accept `facility_params`. The duplicate function `compute_borrowing_base` in `core/portfolio.py` does accept facility_params and uses `facility_params.get('advance_rate', 0.80)` correctly. So *which* function is actually wired to the SILQ endpoint determines whether facility-level overrides apply. If the endpoint dispatches to `compute_silq_borrowing_base` (analysis_silq.py), legal-extracted advance rates are ignored.
- **Fix:** Add `facility_params=None` parameter to `compute_silq_borrowing_base` and use `facility_params.get('advance_rate', 0.80)`.

---

### 🟡 WARNING Finding 24: `compute_klaim_covenants` PAR60 method tag claims `age_pending` but uses different age threshold (120d for PAR60, 90d for PAR30)
- **File:** `core/portfolio.py:1219` and `1249`
- **Trigger:** Always when `Pending insurance response` column is present.
- **Impact:** Code maps PAR30 → `age_active > 90 AND pending > 0` and PAR60 → `age_active > 120 AND pending > 0`. These thresholds are arbitrary proxies for contractual DPD that the Klaim tape doesn't carry. The MMA covenants are written against PAR30/PAR60 — but the implementation reads age_active > 90/120. The methodology log doesn't record this proxy pair as a separate adjustment (only `single_payer_proxy` and `clean_book_separation` are documented). **For an audit-traceable IC report, this should be a top-tier methodology note**: "PAR30 covenant computed on age > 90d AND non-zero pending — proxy because tape lacks contractual DPD".
- **Fix:** Add a methodology adjustment entry in `compute_methodology_log`: `type='par_proxy'`, `target_metric='PAR30/PAR60 covenants'`, `description='age + pending proxy used; tape lacks contractual DPD'`, `confidence='B'`, `proxy_thresholds={'par30_age_days': 90, 'par60_age_days': 120}`.

---

### 🟡 WARNING Finding 25: `compute_aajil_traction` `last_month_days < 25` partial-month filter is unsafe
- **File:** `core/analysis_aajil.py:233-236`
- **Trigger:** Any Aajil tape where the most-recent month has all of its deals concentrated in the first 24 days (mass disbursement event near the start of the month, e.g., promotional campaign on the 1st).
- **Impact:** The function detects "partial month" by checking `last_month_days = df_c[df_c['month'] == last_month][C_INVOICE_DATE].dt.day.max()`. If the max day is < 25, it strips that month from MoM/QoQ/YoY growth comparisons. **But this isn't actually checking whether the month is partial — it's checking whether any deals happen to fall after day 25.** If Aajil has a cluster of disbursements on Jan 1-15 (e.g., a Ramadan SME push), the entire month's volume is treated as "partial" and EXCLUDED from growth comparisons. MoM growth would be reported using prior month's volume only.
- **Fix:** Detect partial-month from snapshot date vs current calendar (`as_of_date.day < 25`), not from observed disbursement-day-max. Or use end-of-month date ranges from explicit metadata.

---

### 🟡 WARNING Finding 26: `compute_klaim_cash_duration` clip in non-monotonic curves doesn't surface count
- **File:** `core/analysis.py:2058`
- **Trigger:** Tape with curve columns that are not monotonically increasing (refunds, corrections — mentioned in CLAUDE.md as the "Klaim denial-reopen pattern").
- **Impact:** `bucket_cash = (col - prev_cum).clip(lower=0)`. Negative deltas are silently zeroed. The function note says "guard against non-monotone noise" but the count of clipped rows / total clipped value isn't reported. If 5% of book has refund-style negatives, those are lost from cash duration with no audit trail.
- **Fix:** Track `clipped_count` and `clipped_amount` and emit them in the result dict.

---

### 🔵 IMPROVEMENT Finding 27: All compute functions lack `Decimal` for currency arithmetic
- **File:** Across all `analysis*.py`, `portfolio.py` files
- **Trigger:** Cumulative rounding errors at scale. A tape with 8,000 deals running through 11 chained float multiplications per metric can accumulate cents of error.
- **Impact:** Borrowing base for an 8,000-deal book may be off by $0.10-$1.00 from a Decimal-arithmetic reference implementation. This isn't material on a $30M facility but matters for cert reproducibility — the BB number on a regulator-facing certificate has to reproduce exactly. Currently it depends on float operation order, which is not portable across Python versions/numpy versions.
- **Fix:** Migrate `compute_borrowing_base`, `compute_klaim_covenants`, `compute_concentration_limits` to use `Decimal` for the currency-bearing arithmetic. Keep float for percentages and ratios.

---

### 🔵 IMPROVEMENT Finding 28: `apply_multiplier` returns 1.0 silently when currency unknown
- **File:** `core/analysis.py:23-33`
- **Trigger:** A new product onboarded with `config.currency = "ZAR"` (or any currency not in the FX rates table).
- **Impact:** `rates.get(reported, 1.0)` — unknown currency falls back to rate=1.0, producing the displayed number as if it were USD. Off by ~17× for ZAR. No warning emitted. Would silently misstate KPIs on the landing page until someone notices.
- **Fix:** Raise `ValueError(f"Unknown currency {reported}")` if `reported` is not in rates AND `display_currency == 'USD'`. Or log a warning + flag the result with `currency_unknown=True`.

---

### 🔵 IMPROVEMENT Finding 29: Re-implemented PAR / DPD logic in 4 places (Klaim portfolio.py, Klaim analysis.py, SILQ analysis_silq.py, Aajil analysis_aajil.py) drifts subtly
- **File:** `core/portfolio.py:1207-1214`, `core/analysis.py:1773-1787`, `core/analysis_silq.py:122-127`, `core/analysis_aajil.py:323-325`
- **Trigger:** Routine maintenance — fixing a bug in one location while another silently retains the old behavior.
- **Impact:** The `compute_par()` (analysis.py) uses `(active['est_dpd'] >= threshold_days) & (active['outstanding'] > 0) & (active['shortfall'] > 0)`. The covenant `compute_klaim_covenants` (portfolio.py) uses `(age_active > threshold) & (pending > 0)`. The two will diverge under realistic tape conditions — same Klaim tape can produce two different PAR30 readings depending on which endpoint serves it.
- **Fix:** Extract a shared `_compute_par_klaim(df, mult, ref_date, threshold_days, *, method)` helper. Both `compute_par` (Tape Analytics) and `compute_klaim_covenants` (Portfolio Analytics) call it. Documented method tag enforces consistency.

---

### 🔵 IMPROVEMENT Finding 30: `compute_seasonality` line 2557-2559 averages "non-zero months only" silently
- **File:** `core/analysis.py:2556-2559`
- **Trigger:** Tape with a vintage history that started mid-year (the documented use case in the comment).
- **Impact:** `all_nonzero = [...if origination[mm-1].get(str(y), 0) > 0]` — the seasonal index uses only non-zero (year, month) cells as the average baseline. This is doctrine but it means a year with a single mid-July launch contributes one cell to the baseline. If 2024 = 50K total in just July and 2025 = 60K total spread evenly across 12 months, the seasonal index for July 2024 = 50K / ((50K+60K)/13) ≈ 5.9 — wildly inflated. IC sees July as massively seasonal when it's really an artifact of the launch month.
- **Fix:** Compute seasonal index per-year and average across years, or require at least 3 years of full-month data before reporting a seasonal index. Currently `len(years) < 1` is the only gate.

---

### 🔵 IMPROVEMENT Finding 31: `compute_summary` doesn't validate `total_purchase_value > 0` before computing rate denominators
- **File:** `core/analysis.py:131-134`
- **Trigger:** Empty tape or all-zero PV tape.
- **Impact:** The pattern `float(total_collected / total_purchase * 100) if total_purchase else 0` is OK for the 0-case. But `float(total_purchase)` on a NaN scalar (sum-of-empty-or-all-NaN) returns NaN, and the ternary is False for NaN as well — so the rate goes to 0. Frontend sees "Collection Rate 0%" instead of "—". Pattern repeats across many functions.
- **Fix:** Pre-check `if pd.isna(total_purchase) or total_purchase <= 0: return {...; 'available': False}`.

---

### 🔵 IMPROVEMENT Finding 32: `compute_klaim_covenants` `period_start = ref_date.replace(day=1)` doesn't handle tz-aware ref_date
- **File:** `core/portfolio.py:1091`
- **Trigger:** `ref_date` constructed with timezone (e.g., a `datetime.utcnow().replace(tzinfo=...)` upstream).
- **Impact:** `Timestamp.replace(day=1)` works on tz-naive but on tz-aware Timestamps may shift the date depending on local-time offset (Asia/Riyadh vs UTC). For a Saudi product evaluated near midnight, the period boundary could land on the wrong calendar day, including or excluding maturity that night's loans incorrectly.
- **Fix:** Add `ref_date = ref_date.tz_localize(None) if ref_date.tzinfo else ref_date` early. Or document that callers must pass tz-naive dates.

---

### 🔵 IMPROVEMENT Finding 33: `compute_collection_velocity` line 219 fallback to `(today - Deal date)` when curve-DSO returns NaN doesn't differentiate methods in output
- **File:** `core/analysis.py:215-221`
- **Trigger:** Mixed tape where some completed deals have curves and some don't (e.g., older completed deals from before curve columns were added).
- **Impact:** The function reports `'curve_based': has_curves` (line 276) — a single flag. But each individual `days_to_collect` value silently mixes curve-derived and elapsed-from-deal-date methods. The downstream weighted DSO is then a hybrid. IC has no way to see which fraction of completed deals contributed via which method.
- **Fix:** Add `'curve_method_count'` and `'fallback_method_count'` in result dict; flag deal-level rows with `_method` column.

---

### 🔵 IMPROVEMENT Finding 34: `validate_aajil_tape` line 95 `f"{min_date:%Y-%m-%d}"` crashes on NaT
- **File:** `core/validation_aajil.py:93-95`
- **Trigger:** Aajil tape where every `Invoice Date` is missing/unparseable.
- **Impact:** `min_date = df['Invoice Date'].min()` returns `NaT`. The f-string `f"Date range: {min_date:%Y-%m-%d}"` then raises `ValueError: NaTType does not support strftime`. The validation endpoint 500s instead of returning critical findings. Same risk in `compute_summary` line 117-119 (`valid.min().strftime(...)`).
- **Fix:** Guard with `if pd.notna(min_date): info.append(...)` or `min_date.strftime("%Y-%m-%d") if pd.notna(min_date) else "N/A"`.

---

### 🔵 IMPROVEMENT Finding 35: `compute_silq_underwriting_drift` z-score uses biased standard deviation (population, not sample)
- **File:** `core/analysis_silq.py:1230`
- **Trigger:** Always — every SILQ underwriting drift call.
- **Impact:** `std = (sum((x - mean)**2 for x in prior_vals) / len(prior_vals)) ** 0.5`. This is the population standard deviation (ddof=0). With small samples (the function uses ≥3 prior vintages), this UNDER-estimates the true population sigma. Z-scores are inflated, drift flags fire more aggressively than they should. With 6 prior vintages, biased σ ≈ √(5/6) × unbiased σ ≈ 91% — a 1.0 z-score threshold becomes effectively ~0.91 against unbiased σ.
- **Fix:** Use `len(prior_vals) - 1` as denominator (sample std). Or import `statistics.stdev`.

---

## Themes / patterns observed

1. **Pattern: silent unit/scale/format-incompatible inputs**. Discount as fraction vs %, customer ID as int vs string, date as Timestamp vs string — multiple compute functions call `int()`, `float()`, `.strftime()` without `pd.notna()` or `pd.to_numeric(..., errors='coerce')` guards. Consistent with the CLAUDE.md "graceful degradation, not estimation" doctrine but not consistently applied.

2. **Pattern: `if total_xxx else 0` ternaries hide upstream NaN/empty cases**. Used 50+ times across compute_summary, cohorts, concentration, par, etc. The intent is divide-by-zero protection but the side effect is that real-zero, NaN, and "empty df" all collapse to the same downstream value (0), which IC reads as a fact rather than as missing data.

3. **Pattern: ref_date defaulting to `pd.Timestamp.now()` makes computations non-deterministic**. Klaim's WAL, BB, covenant module all have this latent issue — backdated views of historic snapshots will produce different results on different days. Session 31's snapshot-dimensioned DB fixed the snapshot-source issue but not the ref-date issue (the Snapshot record's `taken_at` IS the right default, but helpers don't reach for it).

4. **Pattern: Concentration / groupby(non-NaN-aware) with denominators that DO include NaN rows**. HHI, top-N, percentage all have this asymmetry. Acceptable when missingness is rare; potentially material when a tape has 5%+ unmapped Group/Provider/Customer.

5. **Pattern: Re-implementations of the same metric (PAR, WAL, DPD) in 3-4 places**. Klaim PAR is computed in compute_par (analysis.py), compute_klaim_covenants (portfolio.py), and compute_klaim_borrowing_base (portfolio.py) — each with subtly different proxy logic. Drift is inevitable. Extracting a shared `_compute_par_klaim` helper would eliminate this entire class of bug.

---

## Appendix — Noted intentional decisions (not bugs)

These look suspicious but are documented as deliberate in CLAUDE.md / ANALYSIS_FRAMEWORK.md / per-function docstrings:

- **`compute_loss_triangle` is largely redundant with `compute_vintage_loss_curves`**. Documented as P2-1 audit, kept for backward compat.
- **`Actual IRR for owner` column is NOT actively excluded — it's just never read by any compute function.** Methodology log documents the column exists; the docstring claim that it's "excluded from all analysis" is technically true (zero readers), even though no explicit filter fires. Not a bug.
- **Klaim "PAR" via age_pending proxy + Confidence B** is doctrine. CLAUDE.md and ANALYSIS_FRAMEWORK.md §17 explicitly mark it Confidence B and document the proxy reason (no contractual DPD column on Klaim tape). The threshold-pair (30d→90d, 60d→120d) IS undocumented in methodology log though — Finding #24 above flags it.
- **SILQ Collection Ratio uses `specific_filter(maturing in period)` including all statuses** (incl. Closed). Documented as P0-1 audit; doctrine is that a closed-paid-in-full loan that matured in-period MUST contribute to the denominator.
- **Status reversals Completed → Executed** are downgraded from CRITICAL to WARNING in `validation.py` per CLAUDE.md session 30 — Klaim "denial-reopen pattern" is known and expected.
- **`compute_dso` returns `available: False` when curves are missing** (line 919) — documented graceful degradation, not a bug.
- **`stress_test` runs on full book (intentional, full facility-exposure view)** — documented in line 1130-1135 as the lender's exposure perspective.
- **`compute_summary` `_safe()` collapse to None** in `analysis_aajil.py` and 0 in `analysis_silq.py` is inconsistent — flagged as Finding #17, not a doctrine.
- **`compute_par` Active vs Lifetime denominator pattern** is Framework §17 doctrine.
- **Currency multiplier applied at display time** (only on output, not at compute) is documented architectural decision — not double-applied.

---

## TL;DR — Top 5 most important findings

1. **🔴 Critical Finding 1** — BB payer-concentration adjustment double-counts ineligible exposure (`core/portfolio.py:787-793`). Inflates payer concentration ratio against the wrong denominator; understates BB.
2. **🔴 Critical Finding 8** — Klaim covenant Paid vs Due uses operator-precedence-broken ternary filter (`core/portfolio.py:1328-1331`). Either crashes when Status column missing or returns 0%, silently triggering breach.
3. **🔴 Critical Finding 6** — `_klaim_wal_total` and `_klaim_deal_age_days` default to `pd.Timestamp.now()` when ref_date is None (`core/portfolio.py:631-639` + 1147). Same snapshot's covenant compliance drifts day-by-day.
4. **🔴 Critical Finding 2** — `migration.py` cure-rate matrix Cartesian-explodes on duplicate IDs (`core/migration.py:90-94`). Inflates transition counts, misleads IC on roll rates.
5. **🔴 Critical Finding 3** — Klaim `compute_klaim_covenants` PAR30 fallback flags every active deal >30 days as at-risk (`core/portfolio.py:1207-1214`). On any tape without `Pending insurance response` column, PAR30 explodes to ~80%+ — false breach.
