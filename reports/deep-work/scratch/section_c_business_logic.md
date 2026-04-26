# Section C: Business Logic Stress Test

**Files analyzed:** 9 (core/portfolio.py, core/analysis.py, core/analysis_silq.py, core/analysis_aajil.py, backend/main.py, core/db_loader.py, core/legal_compliance.py, core/legal_extractor.py, core/mind/pattern_detector.py)
**Findings:** Critical 8 | Warning 13 | Improvement 7
**Date:** 2026-04-26

---

## Findings

### CRITICAL Finding 1: Klaim Collection Ratio + Paid vs Due silently include loss deals (separation principle leak — covenant numerator/denominator both inflated)

- **File:** `core/portfolio.py:1282-1290` (Collection Ratio) and `1334-1340` (Paid vs Due proxy branch); also `1326-1330` direct branch
- **Trigger:** Snapshot has any deals with `Status='Executed'` AND `Denied by insurance > 50% of Purchase value` (i.e. `denial_dominant_active` zombies — every Klaim tape has these per the Apr 15 audit).
- **Impact:** Both covenant ratios filter on `Status == 'Executed'` ONLY — they do NOT exclude loss-subset deals via `separate_portfolio()`. The denominator is total face value of all live deals (including denial-dominated active), and the numerator is collections on those same deals. A bad-debt deal (e.g. PV 100K, denied 90K, collected 5K) drags BOTH numerator (+5K) and denominator (+100K) — net effect: covenant ratio reads LOWER than the clean book. On Apr 15 this could mean the analyst sees Coll Ratio 27% (already a borderline number against 25% threshold) when the clean book actually clears 35%. The COVENANT BREACH SIGNAL itself is correct (you'd rather report low), but the COMPLIANCE PATH for analyst remediation is wrong: they cannot fix this by collecting harder on clean book, since the loss-subset is structurally non-recoverable. **More dangerous in the inverse direction**: as more deals enter denial-dominant status, the ratio drifts down deterministically — analysts may attribute it to "collections slowing" when it's actually "more denial-dominant active deals accumulating". The Framework §17 doctrine explicitly says covenant population is `total_originated` for Coll Ratio (this matches), but `separate_portfolio()` exists specifically to provide a clean dual-view — and it's not invoked here.
- **Fix:** Compute both `coll_ratio` (covenant-binding, current population) AND `coll_ratio_clean` (clean-book dual). Surface both in the covenant breakdown so analysts can attribute breach to "rising loss tail" vs "live book degradation". Mirror the same dual on Paid vs Due. Walker test: `tests/test_population_discipline_meta_audit.py` should check that every covenant `current` field has a `_clean` companion.

---

### CRITICAL Finding 2: PAR / Lifetime PAR reconciliation gap — lifetime_par denominator uses ALL deals (incl. completed-loss), but numerator only includes ACTIVE — produces sub-additive arithmetic that can deceive

- **File:** `core/analysis.py:1734-1735, 1789-1795, 1867-1873`
- **Trigger:** Any snapshot with Klaim deals where `Status == 'Completed'` AND `Denied > 50% PV`. Apr 15 has hundreds.
- **Impact:** Lifetime PAR is computed as `par30_amt / total_originated * 100` where:
  - `par30_amt` = outstanding-on-deals-with-est_dpd>30 from ACTIVE pool only (line 1779: `active.loc[mask, 'outstanding']`)
  - `total_originated` = `df['Purchase value'].sum()` — INCLUDES completed deals (line 1735)
  
  So a deal that defaulted, was denied 100% (outstanding=0), and got marked Completed contributes 0 to numerator but ITS PV to denominator. **Lifetime PAR is artificially LOW** because the lifetime denominator includes successful AND failed history while the numerator only tracks open exposure. A portfolio that books $100M, collects $80M cleanly, has $5M open behind schedule, and has $15M denied/written off would report Lifetime PAR30 = $5M/$100M = 5%. But the true "lifetime risk realized rate" should add the $15M that DID become loss → 20% if the goal is "what % of lifetime origination has gone or is going bad". Per CLAUDE.md session 36: "Lifetime is the IC view; lifetime captures what active hides". This is not what session-36 doctrine claims — lifetime PAR as currently coded captures only the still-open at-risk subset, NOT realized history. Recovery/Net Loss in compute_cohort_loss_waterfall serves the realized-history role, but they're presented as separate metrics with no clear additive reconciliation. An IC reading `Lifetime PAR30 = 3.6%` and `Net Loss Rate = 12%` may not realize they are non-overlapping subsets of the same lifetime-originated denominator.
- **Fix:** Reconcile in code: assert `lifetime_par + net_loss_rate <= cumulative_at_risk_rate`. Add a `lifetime_realized_loss_rate` field that's `(net_loss + lifetime_par)/total_originated`. Tooltip on the lifetime PAR card should disclose: "Open at-risk only; see Net Loss Rate for realized losses". Walker test: ensure every dual-view metric documents what's IN versus OUT of each population.

---

### CRITICAL Finding 3: `_match_snapshot` date-only fallback returns the FIRST date match deterministically — but `len(date_matches) == 1` check passes silently when same-day tape + live exist, and `_load()` doesn't dispatch live snapshots (filesystem-only, DB-only paths diverge)

- **File:** `backend/main.py:276-304` (`_match_snapshot` filesystem path) + `core/db_loader.py:180-224` (`resolve_snapshot` DB path)
- **Trigger:** Two collisions:
  1. **Filesystem `_match_snapshot`** is used by Tape Analytics. It only knows about filesystem snapshots. If a `live-2026-04-15` snapshot exists ONLY in DB but not as a file, calling `_load()` with snapshot=`'2026-04-15'` matches whichever filesystem snapshot has that date — analyst expects "live data", silently gets tape.
  2. **DB `resolve_snapshot`** falls through to `order_by(Snapshot.ingested_at.desc()).limit(1)` on date-match (line 221). If a tape snapshot AND a live snapshot were ingested on the same day, "last write wins" — but this is documented as deliberate (CLAUDE.md). HOWEVER: if frontend Tape Analytics calls `/snapshots` (DB-driven) and gets a live snapshot in the dropdown, then opens a chart endpoint that goes through `_load()` (filesystem), the live snapshot doesn't exist on disk and `_match_snapshot` raises 400 — broken UX, possibly silent on a cached page where stale options remain.
- **Impact:** Cross-pipe contamination: Tape Analytics charts (filesystem) and Portfolio Analytics covenants (DB) can diverge in which snapshot they target for the same user-visible "snapshot dropdown selection". The IC sees a number on Tape Analytics that contradicts the same number on Portfolio Analytics — and there's no clear cue. Worse: cached AI commentary keys on `snapshot` filename (filesystem name), so the AI summarizes a different data slice than the visible dashboard.
- **Fix:** Single source of truth for snapshot listing. Either (a) DB-only `/snapshots` AND switch `_load` to DB-only (matches Session 31 spirit), or (b) sync both representations and reject mismatched `snapshot` parameters. Add an integration test: pick a snapshot in dropdown → assert ALL endpoints (tape charts + portfolio + AI cache key) resolve to the same `(source, taken_at, name)` triple.

---

### CRITICAL Finding 4: Klaim covenant Coll Ratio + Paid vs Due use Python operator-precedence bug — falls back to `True` literal that pandas treats as KeyError when `Status` column missing

- **File:** `core/portfolio.py:1284-1287`, `1328-1330`, `1334-1336`
- **Trigger:** A Klaim DataFrame loaded without a `Status` column. Possible if (a) the tape file is malformed, (b) the DB loader returns an empty DF with no Status column, or (c) some future refactor adds an `analysis_type` that reuses `compute_klaim_covenants` on a column-light DF.
- **Impact:** The expression
  ```python
  period_deals = df[
      (df['Deal date'] <= period_end) &
      (df['Status'] == 'Executed') if 'Status' in df.columns else True
  ]
  ```
  Python parses as: `df[ ((mask1) & (mask2)) if 'Status' in df.columns else True ]`. When `Status` is missing, this evaluates to `df[True]` — pandas sees `True` (a bool) and tries `df.__getitem__(True)`, raising a `KeyError: True` (bool not in columns).
- **Fix:** Use parentheses explicitly:
  ```python
  if 'Status' in df.columns:
      period_deals = df[(df['Deal date'] <= period_end) & (df['Status'] == 'Executed')]
  else:
      period_deals = df[df['Deal date'] <= period_end]
  ```
- **Before/after snippet:**
  ```python
  # BEFORE — ambiguous precedence, raises on missing Status
  period_deals = df[
      (df['Deal date'] <= period_end) &
      (df['Status'] == 'Executed') if 'Status' in df.columns else True
  ]

  # AFTER — explicit branching
  date_mask = df['Deal date'] <= period_end
  if 'Status' in df.columns:
      period_deals = df[date_mask & (df['Status'] == 'Executed')]
  else:
      period_deals = df[date_mask]
  ```

---

### CRITICAL Finding 5: `annotate_covenant_eod` two-consecutive-breaches rule treats `prev_period == current_period` as `is_consecutive=True` (gap=0), enabling EoD on stale-history double-write

- **File:** `core/portfolio.py:1467-1488`
- **Trigger:** A regenerated covenant computation in the SAME period writes a new history record without dedup-by-period. The covenant history file has dedup by `date` (test_date_str), but `period` and `date` can differ (period is calendar month start–end, date is test_date), so an analyst running the covenant endpoint twice on the same calendar day with a paramter tweak gets BOTH records dedup'd by date — but if `period` is calendar month and date moves between months mid-eval, ordering can produce `prev_period == current_period`.
- **Impact:** With `gap_days = 0`, `is_consecutive = (15 <= 0 <= 45)` evaluates False — actually NOT triggered. So this specific case is safe BUT…
  
  **Worse**: `prev_records[0].get('period', '')` returns string (calendar period like `'2026-04-01 – 2026-04-30'`). `pd.Timestamp(prev_period)` will RAISE on this string, hit the `except Exception` at line 1476, and set `is_consecutive = True`. So **any covenant history record where `period` is a date-range string instead of a parseable date causes the consecutive-breach rule to fire WITHOUT a real consecutive check**.
  
  Looking at line 1093: `period_str = f'{period_start.strftime("%Y-%m-%d")} – {period_end.strftime("%Y-%m-%d")}'`. The Klaim Coll Ratio + PVD covenants WRITE this string format to history (line 1299 `'period': period_str`). On the NEXT eval, `pd.Timestamp(prev_period)` raises ValueError → `except` → `is_consecutive = True` → if both compliant=False, EoD triggers.
- **Fix:** Don't try to parse `period` strings — write a separate `period_start_date` field to history (machine-parseable) and key `is_consecutive` off that. Don't use `except Exception: is_consecutive = True` as a default — fail closed (`is_consecutive = False` so EoD doesn't trigger on parsing failure). Add regression test: write a history record with non-parseable `period`, assert EoD does NOT trigger on next eval.

---

### CRITICAL Finding 6: `is_snapshot_mutable` UTC-day check creates write-window race at the date boundary

- **File:** `core/db_loader.py:79-91`
- **Trigger:** Integration API receives a write request at exactly UTC midnight ± seconds (e.g. 23:59:58 → request starts on day N, by the time `today = datetime.now(timezone.utc).date()` is called, it's day N+1).
- **Impact:** The Integration API call path:
  1. POST /invoices/bulk arrives at 23:59:59 UTC
  2. `get_or_create_live_snapshot(db, product, as_of=None)` creates `live-2026-04-15` (still day N)
  3. Write loop iterates 5,000 invoices (takes 30 seconds, crosses midnight)
  4. Mid-loop, time is now 00:00:30 UTC day N+1
  5. Subsequent `is_snapshot_mutable(snap)` checks (in PATCH handlers) compare `snap.taken_at == 2026-04-15` to `today == 2026-04-16` → returns False
  6. PATCH/DELETE handlers return 409 Conflict despite this being the SAME logical "today's live snapshot" the analyst is mid-editing.
  
  More dangerous: the SECOND write of bulk request lands AFTER midnight in the SAME live snapshot (snapshot already created), but a CONCURRENT bulk request starting at 00:00:01 UTC creates `live-2026-04-16` and tries to write the same `(snapshot_id, invoice_number)` keys — but the unique constraint is on `(snapshot_id, invoice_number)`, so this would succeed (different snapshots) and the same invoice_number would exist in BOTH snapshots with different state. The next-day analyst querying `/invoices` for the latest snapshot gets the day-N+1 version — but anyone querying day N gets the half-finished bulk write.
- **Fix:** Read `today` ONCE at the start of a bulk request and pin it for the duration. Or: lock the snapshot key via SELECT FOR UPDATE during the operation. Document the rule explicitly: "snapshot-of-the-day is decided at the FIRST write, not by clock; subsequent writes within the same logical batch land in the same snapshot regardless of clock crossing".

---

### CRITICAL Finding 7: `compute_par` Option C empirical benchmark threshold of 50 completed deals is non-deterministic and can flip method on snapshot edge — same-snapshot, different-call, different-method

- **File:** `core/analysis.py:1680-1688, 1832-1834`
- **Trigger:** A snapshot with completed-deal count near the 50-deal cutoff. Apr 15 has plenty, but earlier tapes (Sep 2025, Dec 2025) have fewer than 50 completed for some asset classes. As completed deals accumulate, the SAME snapshot can flip from `method='derived'` → `method='direct'` if the threshold is crossed — but the trigger is the COMPLETED FILTER (`df[df['Status'] == 'Completed']`), which depends on the as_of_date filtering.
- **Impact:** Multi-step deterministic risk:
  1. `_build_empirical_benchmark(completed_df)` requires `len(completed_df) >= 50` (line 1680).
  2. After dropping rows with NaN `coll_pct`, requires `len(cdf) >= 50` again (line 1687).
  3. Needs `>= 3` valid buckets (line 1705).
  4. Each bucket requires `mask.sum() >= 10` (line 1701).
  
  Two API calls in a row with the SAME snapshot but DIFFERENT `as_of_date` parameters: caller 1 with `as_of_date=None` gets `method=derived` (50+ completed), caller 2 with `as_of_date=2025-12-01` filters df to a smaller subset (only deals before 2025-12-01) and gets 49 completed → falls back to `'available': False`. Analysts switching the as-of date toggle in the UI would see PAR cards appear/disappear mid-session, and the AI cache key (which DOES include as_of_date) would generate different cached entries — but the disclosed `method` value isn't part of the cache key, so a cached entry from when the threshold was crossed could be served on a tape that no longer crosses it.
  
  Worse: the cohort `if mask.sum() >= 10` rule operates per cumulative bucket. If a 30d bucket has 9 deals at one snapshot and 11 at the next, the BUCKET LIST changes — the per-deal `_expected_pct` lookup returns different values. PAR rates drift up or down by significant percentages with no underlying portfolio change.
- **Fix:** Pin the benchmark to the snapshot date, not the filtered df. Compute it ONCE per snapshot (cached), don't recompute on each as_of_date filter. Disclose the cutoff (e.g., "Method: derived, n=52 completed, vintage_count=5") so analysts can see when it's near the threshold. Add `method` and `n_completed` to the AI cache key.

---

### CRITICAL Finding 8: `compute_klaim_borrowing_base` payer concentration uses `Group` column when no `Payer` exists — but `compute_klaim_concentration_limits` `payer_compliant` is keyed on `worst_payer_pct` only, not on `breaches[]` count

- **File:** `core/portfolio.py:984-989` and `997-1015`
- **Trigger:** Klaim Apr 15 tape — `Payer` column not on tape, falls back to `Group`. Single Payer concentration limit (10%).
- **Impact:** The code computes `worst_payer_pct` from the SINGLE largest payer (line 982-984): `worst_payer_pct = float(payer_pcts.max())`. Then `payer_compliant = bool(worst_payer_pct <= payer_threshold)` — purely based on the max. Separately, `breaches[]` collects ALL groups exceeding threshold. **If two distinct payers both exceed 10% but neither is largest in some weird sort case, payer_compliant would be set on max ONLY — but `breaches[]` count may suggest otherwise**. The actual code reads `payer_compliant = bool(worst_payer_pct <= payer_threshold)` — this is correct because `max <= threshold` implies all <= threshold. Wait, that's actually fine if max is single-payer max…
  
  **The real bug**: `conc_adjustment` is summed across all breaching payers (line 988), but the `compliant` flag only considers the worst. If 5 different payers are at 11-12% each, conc_adjustment is sizeable (sum of 5 excess amounts), `payer_compliant = False`, breaches has 5 entries — UI looks consistent. But the **executive summary AI** reads `compliant=False` AND a list of breaches — and may report "1 breaching payer" (taking the worst) when there are actually 5.
  
  Compounding: when `payer_col == 'Group'` (proxy mode, Apr 15), the payer concentration is 100% structurally wrong. Klaim has 144 distinct Groups (providers) but only ~13 actual insurance payers (paying entities). Group-as-proxy-for-Payer wildly understates concentration: the largest insurance payer (e.g. DAMAN) might cover 30% of the book across 50 Groups, but no individual Group exceeds 5%. The "Single Payer 10% limit" appears compliant under proxy mode when the TRUE limit is breached. **This is a covenant-leakage scenario**: the facility document declares a 10% single-PAYER limit; the platform reports compliance against single-GROUP — same name, different metric — and analysts may sign a compliance certificate based on it.
- **Fix:** When `payer_col == 'Group'` (proxy mode), MARK the limit `partial=True` and `compliant=None` (unknown) rather than computing a misleading number. The `confidence='B'` flag is set but the binary `compliant` boolean still reports a value the UI consumes — that is the leakage. Per CLAUDE.md/lessons.md "Account Debtor validation: CRITICAL DATA GAP — tape has no payer column" — the platform already KNOWS the data gap exists; the code just doesn't gate `compliant` on it.

---

### WARNING Finding 9: SILQ `compute_silq_covenants` Collection Ratio includes Closed-and-DEFAULTED loans in the maturing population — covenant looks better than it should

- **File:** `core/analysis_silq.py:880-897` and `core/portfolio.py:412-431`
- **Trigger:** SILQ tape with loans where `Status='Closed'` AND `Outstanding > 0` (charge-off / partial recovery) maturing in the period.
- **Impact:** Filter is `mask = (df[C_REPAY_DEADLINE] >= month_start) & (df[C_REPAY_DEADLINE] <= month_end)` — no Status filter. Doctrine in the docstring says "specific_filter(maturing in period)" includes ALL statuses to avoid bias toward delinquent-dominated months. **But a loan with `Status='Closed'` AND `Outstanding > 0` is a CHARGE-OFF — including it in the maturing pool's repaid/collectable doesn't bias toward delinquent — it MASKS the delinquent**. Numerator: `repaid` (Amt_Repaid, e.g. 50% recovery). Denominator: `collectable` (full original face). Ratio: 0.5 — that's a defaulted loan dragging the covenant ratio down (correct) BUT a separate issue: when a defaulted-but-closed loan COMPLETES outside the period, the denominator dropped, making the ratio look BETTER on subsequent periods. The covenant is reading "how much of period-maturing got repaid" — if some matured and went to charge-off in PRIOR periods, they no longer count. This is fine in steady state but creates a forward-deteriorating signal: as more bad debt closes (outstanding written off), the historical Coll Ratio APPEARS to improve.
- **Fix:** Add `loss_subset_excluded=True` flag to the result dict. Provide a parallel `coll_ratio_strict` that also excludes loans with closed-with-balance status. Document the asymmetry: rising loss tail moves Coll Ratio UP (because losses leave the maturing pool) while Klaim's analogous covenant moves DOWN.

---

### WARNING Finding 10: Klaim PAR proxy-shortfall `est_dpd` formula `deal_age × shortfall_ratio` produces nonsensical DPD when shortfall_ratio > 1

- **File:** `core/analysis.py:1762-1771`
- **Trigger:** Klaim deal where `Expected till date` is mis-recorded as 0 or near-0, but `Collected till date > 0`. `shortfall = (expected - collected).clip(lower=0)` = 0 → ratio = 0 → est_dpd = 0 → deal NOT in PAR. BUT inverse: deal where `Expected > Purchase value` (data error) means `shortfall_ratio = shortfall / pv`, where `pv = Purchase value` — could exceed 1 if Expected was set to gross revenue rather than PV. Then `est_dpd = deal_age * 1.5` = unrealistic 540 days for a 1-year-old deal.
- **Impact:** PAR30/60/90 thresholds get crossed for deals that are mathematically not 30+ days late — Apr 15's "Expected till date" column has known data quality issues (CLAUDE.md mentions). The proxy method is `confidence='B'`, so the analyst is technically warned, but the magnitude of error isn't captured in confidence — a single bad data row inflates PAR30 by an entire deal's outstanding.
- **Fix:** Cap `shortfall_ratio` at `[0, 1]` after the division: `active['shortfall_ratio'] = active['shortfall_ratio'].clip(0, 1)`. Validate `shortfall <= pv` and emit a `data_quality` warning when violated. Add regression test with `Expected till date > Purchase value` row, assert PAR doesn't blow up.

---

### WARNING Finding 11: `_klaim_outstanding` uses `.clip(lower=0)` — over-collected/over-denied deals (PV - coll - denied < 0) silently coerce to 0, distorting WAL Active denominator

- **File:** `core/portfolio.py:623-628`
- **Trigger:** Apr 15 has at least one deal where over-collection has been recorded (CLAUDE.md notes "Over-Collection check fires on 1 deal"). Also: `Denied + Collected > Purchase value` due to data entry quirks (refunds, adjustments).
- **Impact:** WAL Active = PV-weighted average of age, weighted by `outstanding`. When a deal's outstanding is clipped to 0, it drops out of the weighting — but its age might be young (day 30 of a 60-day deal where collected = full PV but pending denial returned later). Stripping the deal from active WAL when `outstanding=0` shifts the weighted average toward older deals → WAL Active reads HIGHER than it should. On a single deal this is rounding error; on a portfolio with 1% over-collection cases, WAL drifts up by 1-3 days. Covenant threshold 70d is right at this edge.
- **Fix:** Don't silently clip negative outstanding to 0 for weighting; either (a) include with weight=epsilon, (b) flag as data anomaly, or (c) use absolute outstanding so the row participates. Better: emit a `data_quality.outstanding_clipped` count in the methodology log so analysts see the magnitude.

---

### WARNING Finding 12: Recovery rate per vintage in `compute_cohort_loss_waterfall` uses `recovery / gross_default` — but recovery includes Provisions which are NOT actual recovery cash

- **File:** `core/analysis.py:2150-2165`
- **Trigger:** Klaim deals with `Provisions` column populated (provision-against-loss bookkeeping entries).
- **Impact:** `recovery = coll_on_default + prov_on_default` (line 2152). Provisions are accounting entries — they're an expectation of future loss, NOT recovered cash. Adding them to "recovery" inflates the recovery_rate. A deal with denied=100, collected=0, provisions=50 reports recovery_rate = 50/100 = 50%. The IC reads 50% recovery on losses. The truth: 0% recovered, 50% provisioned (i.e., expected to loss but not yet realized). This is the difference between IFRS accounting and economic recovery.
- **Fix:** Split into `cash_recovery` and `provision_recovery` separately. `recovery_rate_cash` (Confidence A) and `recovery_rate_total_incl_provisions` (Confidence B with disclosure). The IC needs cash recovery for credit decisions; provisions are accounting, not behavior.

---

### WARNING Finding 13: `compute_par` lifetime denominator includes deals that NEVER entered the active pool (i.e., Cancelled, Bad Status), no Status filter on `df['Purchase value'].sum()`

- **File:** `core/analysis.py:1735`
- **Trigger:** Tape has deals with statuses outside `'Executed' | 'Completed'` (e.g. `'Cancelled'`, `'Pending'`, ``''``).
- **Impact:** `total_originated = float(df['Purchase value'].sum() * mult)` includes ALL deals regardless of status. If Klaim has cancelled deals on tape (rare but possible), those PVs flow into the lifetime denominator, suppressing the lifetime PAR rate. The "lifetime IC view" should be on deals that ACTUALLY originated — not on every row that hit the tape.
- **Fix:** Filter `total_originated` to `Status ∈ {'Executed', 'Completed'}` (the universe of actually originated deals). Document the choice in methodology.

---

### WARNING Finding 14: Multi-doc legal merge `dict_fields` field — `primary` (credit_agreement) wins on key-by-key basis, but uses falsy check `if k not in base or not base[k]` — empty string `''` is treated as missing

- **File:** `core/legal_compliance.py:106-115`
- **Trigger:** Two documents extract the same `facility_terms` key — primary has `'governing_law': ''` (extracted but blank), secondary has `'governing_law': 'UAE'`. The `not base[k]` check evaluates `not ''` = True, so secondary wins.
- **Impact:** This is intentional fallback logic, BUT: a deliberately-blank field in primary gets overwritten by an inferior secondary value. If extraction primary said "deliberately blank — see schedule X" (via empty string), that signal is lost. More dangerous: `0` value gets overwritten too (`not 0 == True`) — a primary doc declaring `cash_ratio_limit: 0` (no minimum) gets clobbered by a secondary that hardcoded `3.0`.
- **Fix:** Use `if k not in base or base[k] is None:` (only None counts as "missing"). Add merge audit log: log every field that gets overwritten so analysts can review the merge diff.

---

### WARNING Finding 15: `compute_klaim_borrowing_base` denial_pct check uses `.replace(0, 1)` to avoid div-by-zero — silently treats PV=0 deals as 0% denied, including them in eligible

- **File:** `core/portfolio.py:776-778`
- **Trigger:** A deal with `Purchase value == 0` (cancelled, zero-valued, or data-entry zero).
- **Impact:** `denied_pct = active['Denied by insurance'].fillna(0) / active['Purchase value'].replace(0, 1)`. PV=0 row: denied_pct = denied/1 = full denied amount. If denied=$50 (data quality issue), denied_pct = 50, mask = 50 > 0.5 = True, the row is flagged as `inelig_denied` — but its outstanding is also `_klaim_outstanding(active)` = `(0 - collected - denied).clip(lower=0)` = 0. So it adds 0 to inelig_denied amount. Net effect: noise. **However**: if denied=0 too, denied_pct = 0, deal looks eligible — it falls through to the eligibility pool with 0 outstanding. Net effect: also noise.
  
  Worse: `replace(0, 1)` is a magic number. The correct guard is `replace(0, np.nan)` and then handle NaN explicitly. The current pattern obscures the data anomaly.
- **Fix:** Use `np.where(pv > 0, denied / pv, 0)` and add a `data_quality.zero_pv_count` to the methodology log.

---

### WARNING Finding 16: Pattern detector `auto_fire_after_ingest` swallows ALL exceptions including KeyboardInterrupt

- **File:** `core/mind/pattern_detector.py:583-594`
- **Trigger:** Operator presses Ctrl-C during a long ingest while pattern detection runs.
- **Impact:** `except Exception as e` is correct — won't swallow KeyboardInterrupt (which inherits from BaseException, not Exception). So this is actually fine. **However**: the same `try/except Exception` pattern in the `auto_fire_after_ingest` masks ALL data corruption issues (corrupted registry.json, race-write to recurring_channels.jsonl). Failures are logged via `logger.warning` only — no metric, no operator alert, no exit code.
- **Fix:** Increment a counter `pattern_detector.failures` in the master mind stats file. Emit an event to the operator command center if 3+ consecutive auto-fire failures occur. Don't silently degrade.

---

### WARNING Finding 17: `compute_silq_covenants` Repayment at Term threshold of 95% with a window — when zero qualifying loans, `compliant=True` (vacuous truth)

- **File:** `core/analysis_silq.py:954` and `core/portfolio.py:487`
- **Trigger:** SILQ snapshot where the 3-6 month maturity window contains zero loans (e.g., a brand-new product just launched in the last 3 months).
- **Impact:** `compliant=bool(rat_ratio >= 0.95) if rat_available else True`. When `rat_available=False`, `compliant=True`. The compliance certificate would mark this covenant as PASSING. An IC reading the certificate sees "Repayment at Term: PASS" and assumes the metric is meaningfully testing — when actually it's vacuously true.
- **Fix:** `compliant=None` when not available (matches Pythonic convention of None for unknown). UI shows "N/A" with explanation. Compliance certificate explicitly excludes "covenants without sufficient data" from the pass count.

---

### WARNING Finding 18: `compute_klaim_covenants` BB Holiday Period check uses string-defaulted `agreement_date` (`'2026-02-10'`) — without `facility_params` set, holiday is hardcoded to a real date

- **File:** `core/portfolio.py:1407-1413`
- **Trigger:** Any covenant computation without `agreement_date` in `facility_params`.
- **Impact:** Default agreement date is hardcoded to 2026-02-10 (Klaim's actual MMA date). For ANOTHER company on Klaim asset class, BB Holiday would erroneously activate. Currently SILQ/Tamara/Aajil/Ejari don't go through `compute_klaim_covenants`, so safe. **But**: a future Klaim-style company onboarded with `_load_facility_params` returning `{}` (no legal docs ingested yet) would inherit Klaim's holiday dates. The compute function should fail closed (no holiday) rather than fail with a real-but-wrong date.
- **Fix:** Default `agreement_date_str = facility_params.get('agreement_date')` (None default). When None, set `bb_holiday_active = False, bb_holiday_end = None` directly. Don't carry hardcoded company-specific dates as fallback.

---

### WARNING Finding 19: AI cache key normalizes as_of_date but doesn't include analysis_type — Klaim/SILQ products with same name in different orgs collide

- **File:** `backend/main.py:397-426`
- **Trigger:** Two products named `'KSA'` under different companies (e.g., `silq/KSA` and `aajil/KSA` — both use `analysis_type` distinct, but the cache key `f"{endpoint}|{company}|{product}|{snapshot}|{...}"` does include company name. Safe.
  
  **Real issue:** as_of_date and snapshot_date in cache key normalization. The check `if as_of_date and snapshot_date and as_of_date < snapshot_date: norm_aod = as_of_date` means BACKDATED views get a different cache key than future views — but `_check_backdated` raises HTTP 400 for backdated AI calls. So backdated entries are never written. **However**: if `_check_backdated` is bypassed (e.g., via the `executive_summary_stream` endpoint which uses different code paths), the backdated cache entry IS created — and gets served to subsequent on-snapshot calls because the on-snapshot call ALSO computes `norm_aod=''` regardless of input.
- **Fix:** Always include the analysis_type AND a hash of facility_params in the cache key. When facility params change (analyst edits in the panel), the AI commentary citing those values is stale.

---

### WARNING Finding 20: PAR endpoint `Pending insurance response` mask in covenant 3/4 is `(age_active > 90) & (pending > 0)` — deals with full denial (pending=0) AND old age are NOT counted as PAR

- **File:** `core/portfolio.py:1217-1221, 1247-1250`
- **Trigger:** Klaim deal aged > 90 days, denied 100%, `Pending insurance response` = 0 (because the insurance call has fully resolved as denial).
- **Impact:** The override branch `if 'Pending insurance response' in active.columns` REPLACES the basic `age > 30` mask with `(age > 90) & (pending > 0)`. A deal that's 200 days old, 100% denied, pending=0 is NOT in PAR30 — it's in `inelig_denied` instead (via BB). But for the COVENANT view (which doesn't go through BB), the analyst sees "PAR30 = X%" without realizing the most-distressed deals (fully denied) are silently excluded. The covenant compares against a 7% threshold; if 5% of book is "behind schedule with pending", and 8% of book is "fully denied old", PAR30 reads 5%, compliant — but realised credit risk is 13%.
- **Fix:** PAR30/60 covenants should be the UNION of "behind schedule with pending" AND "denial-dominant active" (those are by definition past-due since denial is the past-due trigger for Klaim). Currently denial-dominant is filtered out; the covenant under-reports.

---

### WARNING Finding 21: SILQ `_dpd` clips DPD to 0 for `Status == 'Closed'` deals — including Closed-with-Outstanding (charge-off) treated as 0 DPD in covenant flow

- **File:** `core/analysis_silq.py:60-62`
- **Trigger:** SILQ tape has `Status='Closed'` AND `Outstanding > 0` (charge-off booked but balance not collected).
- **Impact:** `compute_silq_covenants` filters `active = df[df[C_STATUS] != 'Closed']` (line 813), so closed-with-balance loans don't reach PAR30/PAR90 numerator anyway — but the LOSS SUBSET they belong to is OUT of the covenant view entirely. As losses accumulate, they leave the PAR ratio (denominator drops). PAR30 looks healthier as the book degrades.
- **Fix:** PAR should be computed against the WIDER active+stuck pool (using `separate_silq_portfolio`'s clean_df + loss_df union). Disclose "PAR uses live-active denominator; written-off loans excluded — see Loss Waterfall for charge-off cumulative".

---

### IMPROVEMENT Finding 22: Covenant history append-only, but no audit of "method changed since last write" event itself

- **File:** `backend/main.py:3907-3934` and `core/portfolio.py:1467-1488`
- **Improvement:** When `method_changed_vs_prior` is set, the history record gets the new method but doesn't carry a `method_change_event` flag. An auditor reviewing the history sees method `proxy` for periods 1-3 then `direct` for periods 4-6 with no signal that an EoD chain was broken by the change. Suggest writing a sidecar `_method_changes.jsonl` per company with `(date, covenant, prev_method, new_method, broke_chain)` for the auditor.

---

### IMPROVEMENT Finding 23: `_klaim_outstanding` doesn't validate that `Collected + Denied <= Purchase value` — silently sets outstanding=0 on identity violation

- **File:** `core/portfolio.py:623-628`
- **Improvement:** Add a `validation_score = (collected + denied - pv) / pv` Series and aggregate to a `data_quality.identity_violations` count. Apr 15 has known violations (1 over-collection deal, plus pending/denial timing). Surface this in methodology log.

---

### IMPROVEMENT Finding 24: `compute_klaim_concentration_limits` Top-10 uses `outstanding.nlargest(10)` — pulls top-10 individual deals, NOT top-10 borrowers (Group)

- **File:** `core/portfolio.py:917-919`
- **Improvement:** "Top-10 Receivables Concentration" semantically should be top-10 deals (per receivable). But the limit is meant to catch concentration risk, where 10 deals from the SAME group are still 1 borrower. Either (a) rename to "Top-10 Deal Concentration" to clarify, or (b) compute top-10 by Group/Customer. Currently the metric can read 30% on top-10 deals and 70% on top-10 customers — not the same thing.

---

### IMPROVEMENT Finding 25: Pattern detector parser-detection word overlap heuristic vulnerable to multi-word collisions

- **File:** `core/mind/pattern_detector.py:179-203`
- **Improvement:** `parser_path.stem.lower()` overlap counting can return false positives. `ingest_klaim_credit_policy.py` (when it exists) would match `document_type='credit_agreement'` (overlap on "credit") with `needed_overlap=2` for two-word doc_type, but only one word matches → returns False. Now it works. **But**: `ingest_silq_silq_silq.py` would erroneously match anything with "silq" in name. Use a regex with word boundaries (`\b`).

---

### IMPROVEMENT Finding 26: `_match_snapshot` extension-strip silently treats a `.txt` snapshot as a `.csv` (only specific extensions stripped)

- **File:** `backend/main.py:_strip_snapshot_ext`
- **Improvement:** `_SNAPSHOT_EXTS` lists known extensions; unknown extensions don't get stripped. If a snapshot file is `2026-04-15.weird`, comparing against DB-side name `2026-04-15` fails. Modest improvement: also try matching against the file stem (everything before the LAST `.`).

---

### IMPROVEMENT Finding 27: SILQ Coll Ratio 3M average doesn't weight by maturing volume — 3 months at 5%, 50%, 95% = 50% (avg) vs 50.6% (volume-weighted with $1M, $10M, $1M)

- **File:** `core/analysis_silq.py:893-898` and `core/portfolio.py:431`
- **Improvement:** Simple-mean of ratios is a known biased estimator of the true period ratio. The covenant likely intends "3 months of collection performance averaged" but volume-weighting matches IFRS expectation. Document the choice; consider adding `coll_ratio_volume_weighted` for transparency. Apr 15 has 4 SILQ tapes — easy to compare.

---

### IMPROVEMENT Finding 28: `compute_silq_operational_wal` clips age to `[0, elapsed]` — a closed loan extended past original maturity gets close_age=elapsed (correct), but loses the "extended past contract" signal

- **File:** `core/analysis_silq.py:1505-1508`
- **Improvement:** Track and emit `extension_count` (loans where `close_age > original_term`), since extensions are themselves a credit signal — add to methodology log.

---

## Themes / patterns observed

1. **`if 'X' in df.columns else True` pattern is precarious** — used in 4+ places in `core/portfolio.py`. It works for the common path but breaks under edge conditions. Replace with explicit if/else branching across the codebase (Critical 4).

2. **Loss-subset leakage into period-based covenants** — Coll Ratio (Klaim AND SILQ) and Paid vs Due both filter on Status without invoking `separate_*_portfolio()`. The §17 doctrine acknowledges this in some places but not all (Critical 1, Warning 9, Warning 21). Walker test should enforce: every covenant function lists which loss-handling primitive it calls (or declares it deliberately omits).

3. **Empirical-benchmark thresholds (50, 10) without disclosure** — Method-flipping based on row counts (PAR Option C). Once a tape crosses 50 completed deals, a fundamentally different methodology runs. AI cache doesn't include the method, so analysts get inconsistent rates across cache hits/misses (Critical 7).

4. **Fail-open defaults in `try/except`** — `is_consecutive=True` on parse fail (Critical 5), `compliant=True` on no-data (Warning 17), `auto_fire_after_ingest` swallows everything (Warning 16). Pattern: when uncertain, fail CLOSED (compliant=False or unknown=None) for credit risk.

5. **Currency conversion inconsistencies** — `compute_silq_covenants` `_dpd` calls don't apply mult; ratios computed on RAW outstanding then ratio'd. Numerator+denominator both unaffected. But absolute SAR amounts in PAR breakdown require explicit `* mult` — and not always done at the same point. Risk of double-multiply has been audited but the call-site discipline is fragile.

6. **Timezone-naive datetime usage** — `datetime.now()`, `pd.Timestamp.now()` everywhere. UTC vs local-time race at midnight (Critical 6). `is_snapshot_mutable` uses UTC; `_klaim_deal_age_days` uses naive normalize(). Consistent UTC-everywhere would prevent edge-case skew.

---

## Appendix — Noted intentional decisions (downgraded from findings)

These looked like bugs but are documented as deliberate per CLAUDE.md / ANALYSIS_FRAMEWORK.md / lessons.md:

1. **Lifetime PAR is primary, Active is context (session 36)** — UI flip was intentional; not a bug. (My Critical 2 stands but is about reconciliation arithmetic, not the primacy choice.)

2. **WAL Path A OR Path B compliance per MMA 18.3** — Dual-path covenant evaluation is correct and intentional. CovenantCard rendering for Path B is the documented fix from session 31 prerequisite.

3. **Last-write-wins on same-day snapshot collision (`resolve_snapshot` ORDER BY ingested_at DESC)** — Documented in CLAUDE.md "Same-day tape + live collision" section. Analysts are advised to use the Tape Analytics dropdown for unambiguous selection.

4. **`method_changed_vs_prior` short-circuits two-consecutive chain (session 30)** — Intentional. Method changes break methodology comparability. My Critical 5 is about a SEPARATE bug in the date-parse fallback when the period field is a date-range string.

5. **Active WAL keys covenant compliance, NOT Total WAL (session 30)** — Total WAL is for IC monitoring; Active WAL drives compliance. Correct and intentional.

6. **`filter_by_date()` only filters DEAL SELECTION, not balance columns** — Documented as Framework §15. Backdated views show stale balances. My critical findings don't violate this.

7. **Backdated AI calls return 400** — `_check_backdated` enforces this at the AI endpoint layer. Raw chart endpoints DO serve potentially-stale data on backdated views, but the doctrine is "balance reflects snapshot date" and Framework §15 is the disclosure mechanism.

8. **Pattern detector never auto-writes to Asset Class Mind** — Trust boundary by design. Operator promotes via UI.

9. **`Actual IRR for owner` excluded from analysis** — Garbage data, documented exclusion.

10. **Klaim payer concentration uses Group as proxy** — Documented as Confidence B, `proxy_column='Group'`. (My Critical 8 stands because the `compliant` boolean reports a misleading value despite the confidence flag.)

11. **`compute_klaim_stress_test` runs on FULL book** — Has explicit `separation_note` field saying "Runs on full book (intentional): facility exposure view". Correct disclosure.

---

## TL;DR — Top 5 most important findings

1. **CRITICAL 4** — Operator-precedence bug in `compute_klaim_covenants` Coll Ratio + PVD (`core/portfolio.py:1284-1287`) raises `KeyError: True` when `Status` column missing. Defensive code path is broken.

2. **CRITICAL 5** — `annotate_covenant_eod` `pd.Timestamp(prev_period)` raises on date-range string (which is what `compute_klaim_covenants` writes to history at line 1093/3920) and the bare `except Exception: is_consecutive = True` fails OPEN, triggering EoD on every parse failure. Real EoD risk.

3. **CRITICAL 1** — Klaim Coll Ratio + PVD silently include loss-subset deals; covenant doesn't run `separate_portfolio()`. As loss tail grows, covenant deteriorates deterministically — analysts attribute to "live book" when it's "loss accumulation" (`core/portfolio.py:1284-1290, 1334-1340`).

4. **CRITICAL 8** — Klaim Single Payer concentration computed against `Group` (143 distinct providers) when the facility document uses Payer (~13 insurance companies). `compliant=True` reported on a structurally wrong proxy. Compliance certificate would carry false-pass on a 10% binding limit. Code already KNOWS the data gap (sets confidence='B', proxy_column='Group') but doesn't gate the boolean compliant flag (`core/portfolio.py:984-1015`).

5. **CRITICAL 7** — `compute_par` Option-C empirical method threshold (50 completed deals, 3 buckets, 10/bucket) is non-deterministic across as_of_date filters. Same snapshot, different filter → different method → different rate. AI cache doesn't include method, so cached entry from one threshold-state gets served when the other state is current (`core/analysis.py:1680-1705, 1832`).
