# Laith Analysis Framework

## 1. Analytical Hierarchy

Every metric in Laith maps to one of five levels. The levels form a pyramid: each builds on the one below it, and together they tell a complete story about a credit portfolio.

### Level 1 — Size & Composition
**Question:** What do we own?

Metrics at this level describe the portfolio's shape: how much capital is deployed, across how many deals, in which products, geographies, and counterparties. These are descriptive, not evaluative.

| Metric | Definition | Tape | Portfolio |
|--------|-----------|------|-----------|
| Total Deals | Count of all deals/loans in the tape | Active + Completed | Active only |
| Total Originated | Sum of Purchase Value (face value) | Lifetime | Current book |
| Total Funded | Sum of Purchase Price (capital deployed) | Lifetime | Current drawn |
| Outstanding | Purchase Value - Collected - Denied (clipped at 0) | Active deals only | Eligible pool |
| Active vs Completed | Count/value split by Status | Point-in-time | Real-time |
| Product Mix | % of originated by product type | Lifetime | Current |
| Provider/Counterparty Count | Unique groups in the book | All | Active relationships |

### Level 2 — Cash Conversion
**Question:** How fast does capital return?

This is the liquidity layer. A portfolio can have zero losses but still destroy returns if cash arrives too slowly or too unpredictably.

| Metric | Definition | Tape | Portfolio |
|--------|-----------|------|-----------|
| Collection Rate | Collected / Purchase Value | Monthly trend + cumulative | Rolling current |
| DSO (Capital) | Cash-weighted days from funding to collection | Completed deals | Current book |
| DSO (Operational) | Cash-weighted days from expected due date to collection | Where expected dates available | Current |
| Days to First Cash (DTFC) | Days from origination to first non-zero collection | Per vintage, median + P90 | N/A |
| Collection Timing Distribution | % of cash arriving in 0-15d / 15-30d / 30-60d / 60-90d / 90+ buckets | By payment month and by origination month | Current period |
| Expected vs Actual Pacing | Collected / Expected till date | Where expected column available | Where available |
| Collection Speed (Vintage) | % collected at 90d / 180d / 360d per cohort | Per vintage in Cohort table | N/A |

### Level 3 — Credit Quality
**Question:** What is deteriorating, and how fast?

This layer surfaces risk: which deals are behind, which are impaired, how severe the delinquency is, and whether it is getting better or worse.

| Metric | Definition | Tape | Portfolio |
|--------|-----------|------|-----------|
| PAR 30+ / 60+ / 90+ | Outstanding on deals past due by X+ days, as % of total active outstanding | Active outstanding denominator | Eligible outstanding denominator |
| PAR by Count | % of active deals past due by X+ days | Secondary metric | Secondary |
| Health Status | Healthy / Watch / Delayed / Poor based on days outstanding | Active deals | Active eligible |
| Roll Rates | Transition probability from bucket A to bucket B between snapshots | Requires 2+ snapshots | Cross-period |
| Cure Rates | % that move from delinquent bucket back to current within horizon h | Per delinquent bucket | Per bucket |
| Implied Cure/Roll | Behavioral signals: % with recent payment activity, avg days since last collection | Within-snapshot signal | Real-time signal |
| Underwriting Drift | Per-vintage avg deal size, discount, term, product mix | Detects origination quality changes | Current book vs historical |

### Level 4 — Loss Attribution
**Question:** Where did the dollars go?

This layer traces capital from origination through default to recovery to net loss. It answers not just "how much did we lose" but "why, and could we have recovered more?"

| Metric | Definition | Tape | Portfolio |
|--------|-----------|------|-----------|
| Gross Default Rate | Denied (or charged-off) amount / Originated, per vintage | Per vintage | Cumulative |
| Recovery Rate | Recovered post-default / Gross default | Per vintage | Per vintage |
| Net Loss Rate | (Gross default - Recovery) / Originated | Per vintage | Per vintage |
| Loss Waterfall | Originated -> Gross Default -> Recovery -> Net Loss per vintage | Full decomposition | Exposure waterfall |
| Loss Categorization | Classification of losses by inferred driver (provider issue, documentation, hardship, anomaly) | Where inferrable | Where inferrable |
| LGD (Loss Given Default) | Net loss / Gross default per defaulted deal | Completed defaults | Seasoned defaults |
| EL (Expected Loss) | PD x LGD x EAD | Portfolio-level + by vintage | Current book estimate |
| Loss Development Curves | Cumulative default/recovery rates by months since origination | Per vintage (like collection curves) | N/A (insufficient history) |
| Recovery Timing | Distribution of recovery amounts by time-since-default bucket | Post-default analysis | N/A |

### Level 5 — Forward Signals
**Question:** What is about to happen?

Leading indicators that predict deterioration before it shows up in collection rates or loss metrics.

| Metric | Definition | Tape | Portfolio |
|--------|-----------|------|-----------|
| DTFC Trend | Is time-to-first-cash lengthening for recent vintages? | Trend chart | N/A |
| Roll Rate Trajectory | Are transition rates worsening month-over-month? | Multi-snapshot comparison | Cross-period |
| Behavioral Signals | % of delinquent deals with zero recent activity | Per DPD bucket | Real-time |
| Concentration Trend (HHI) | Is HHI increasing across snapshots? | Multi-snapshot | Real-time |
| Underwriting Drift Flags | Is average deal quality (discount, size, counterparty mix) deteriorating? | Vintage comparison | Current vs historical |
| Stress Test Scenarios | Provider shock, macro shock, operational disruption | Scenario analysis | Facility trigger testing |
| Seasonality Patterns | Year-over-year comparison of origination, collection, loss by calendar month | Requires 12+ months | N/A |
| Covenant Headroom | Distance from current metrics to covenant trigger levels | N/A | Real-time monitoring |

---

## 2. Tape Analytics vs Portfolio Analytics

### Tape Analytics — The Retrospective View
**Audience:** Investment committee, fund manager, underwriting team
**Purpose:** Evaluate historical performance, identify patterns, support IC decisions
**Data source:** Point-in-time CSV/Excel snapshots (monthly loan tapes)
**Time horizon:** Entire portfolio history within the tape

Tape Analytics answers: "How has this portfolio performed?" It is backward-looking by design. Every metric is computed from a static snapshot. When multiple snapshots exist, cross-snapshot analysis (roll rates, HHI trends) becomes possible.

**Key principle:** Tape metrics should be honest about what is knowable. Metrics that require data not in the tape (e.g., PAR without expected collection dates) should be hidden, not estimated — unless a robust empirical derivation is available, in which case it must be clearly labeled as "Derived."

### Portfolio Analytics — The Monitoring View
**Audience:** Portfolio manager, facility lender, risk officer
**Purpose:** Real-time exposure monitoring, covenant compliance, borrowing base management
**Data source:** PostgreSQL database (live data from integration API), with tape fallback
**Time horizon:** Current state of the portfolio

Portfolio Analytics answers: "What is our exposure right now, and are we in compliance?" It is forward-looking by design. Every metric relates to actionable decisions: advance rates, eligibility, trigger headroom.

**Key principle:** Portfolio metrics must be conservative. When in doubt, report the more cautious figure. PAR should use eligible outstanding (what we're lending against), not total outstanding.

### How the Same Metric Differs

| Metric | Tape Interpretation | Portfolio Interpretation |
|--------|-------------------|------------------------|
| PAR 30+ | "4.6% of active outstanding is behind schedule" — signals book quality | "4.6% of eligible pool is impaired" — affects advance rate |
| Collection Rate | "This vintage collected 95% in 6 months" — evaluates vintage quality | "Rolling 30-day collection rate is 97%" — monitors cash flow |
| HHI | "Concentration is 850 — moderate" — informs diversification strategy | "Concentration limit breached at 12% single-name" — triggers action |
| Outstanding | PV - Collected - Denied for all active | Eligible outstanding after all exclusions |

---

## 3. Asset Class Adaptations

### Klaim — Healthcare Receivables (Insurance Claims Factoring)
**What is financed:** Insurance claims purchased at a discount from healthcare providers
**Obligor:** Insurance companies (not patients)
**Default event:** Insurance denial of the claim
**Recovery path:** Resubmission, appeal, partial collection after initial denial

Key differences from consumer lending:
- No DPD in the traditional sense — insurance companies process claims on their own timeline
- "Delinquency" = collection behind expected timeline, not a missed payment
- Loss driver = insurance denial, not borrower inability to pay
- Recovery = resubmission/appeal success, not debt collection
- Counterparty risk = healthcare provider (Group), not borrower
- Expected collection dates available on Mar 2026+ tapes via curve columns

**PAR calculation:** Requires Expected till date or empirical benchmarks from completed deals

### SILQ — POS Lending (Point-of-Sale Consumer Loans, KSA)
**What is financed:** Consumer purchases at point of sale (BNPL, RBF, RCL products)
**Obligor:** Consumer borrowers
**Default event:** Loan delinquency (DPD-based), charge-off
**Recovery path:** Collections, legal enforcement

Key differences from receivables factoring:
- Traditional DPD available — borrowers have contractual repayment schedules
- Loss driver = consumer credit risk (inability/unwillingness to pay)
- Recovery = standard debt collection, Najiz/legal process
- Counterparty risk = merchant/shop (not insurance company)
- PAR directly computable from DPD columns

---

## 4. Leading vs Lagging Indicators

### Lagging Indicators (confirm what already happened)
- Collection rate (cash already arrived or didn't)
- Net loss rate (losses already materialized)
- Completed deal margins (deals already closed)
- Cumulative denial/charge-off amounts

### Coincident Indicators (show what is happening now)
- PAR 30+/60+/90+ (current delinquency state)
- Health status distribution (current portfolio composition)
- Outstanding by bucket (current exposure profile)
- HHI (current concentration)

### Leading Indicators (predict what will happen)
- **DTFC trend** — if time-to-first-cash is lengthening, future collection rates will drop
- **Roll rate trajectory** — if cure rates are falling and roll rates rising, PAR will worsen
- **Behavioral signals** — deals in delinquent buckets with zero recent activity are more likely to default
- **Underwriting drift** — lower discounts, larger deal sizes, or changing product mix precede future losses
- **Concentration trend** — rising HHI suggests growing tail risk
- **Seasonality deviations** — performance worse than seasonal norms signals a structural shift

### How the AI Commentary Should Use This
When generating portfolio commentary, the AI should:
1. Start with lagging indicators (what happened)
2. Contextualize with coincident indicators (current state)
3. Flag leading indicator signals (what to watch)
4. Never present a leading indicator as a confirmed outcome
5. Always compare current metrics to historical baselines and trends

---

## 5. The Separation Principle

Performance metrics should not be contaminated by fully resolved loss events. The platform implements a separation principle:

### Clean Portfolio (Performance Metrics)
- Active deals + normally completed deals
- Excludes deals where Denied > 50% of Purchase Value (Klaim) or charged-off (SILQ)
- Used for: Collection rate, Revenue, Ageing, Deployment, most KPIs
- Represents the "healthy book" that is still generating returns

### Loss Portfolio (Loss Analysis)
- Deals where Denied > 50% of Purchase Value (Klaim) or charged-off loans (SILQ)
- Analyzed separately in: Loss Waterfall, Recovery Analysis, Loss Categorization
- Represents deals that have effectively failed

### Why This Matters
Without separation, a few large fully-denied deals can distort portfolio-level collection rates and margins. The Ejari analysis framework demonstrates this principle: 32 write-off loans are excluded from ALL performance sheets and analyzed in a dedicated section. This prevents a small number of losses from making a healthy portfolio look worse than it is.

The platform provides a "Clean Portfolio / Full Portfolio" toggle so analysts can see both views. The default is the full (combined) view for backward compatibility.

---

## 6. Denominator Discipline

The most common failure mode in quantitative ABL analysis is denominator confusion. Analysts compute "performance" on a portfolio basis, while the facility is governed by eligible collateral and contractual exclusions. Every metric in Laith must declare its denominator explicitly.

### The Three Denominators

Every metric that expresses a rate, ratio, or percentage must state which base it uses:

| Denominator | Definition | When to Use |
|-------------|-----------|-------------|
| **Total** | All deals in the tape/database, regardless of status or eligibility | Lifetime analysis, IC reporting, portfolio-level summaries |
| **Active** | Deals with Status ≠ Completed/Closed (still outstanding) | Tape Analytics: PAR, health, ageing, outstanding-based metrics |
| **Eligible** | Active deals passing all eligibility predicates (age, documentation, concentration, dispute status) | Portfolio Analytics: borrowing base, advance rates, covenant denominators |

**Rule:** If a metric's denominator is "total" but the facility uses "eligible," your monitoring will fail at the worst time. Laith defaults to the most conservative denominator appropriate to the context (active for Tape, eligible for Portfolio).

### Denominator Examples

| Metric | Tape Denominator | Portfolio Denominator | Why They Differ |
|--------|-----------------|----------------------|-----------------|
| PAR 30+ | Active outstanding | Eligible outstanding | Tape measures book quality; Portfolio measures what the lender is exposed to |
| Collection Rate | Purchase Value (face) of deals in period | Collectable amount of eligible pool | Tape measures vintage performance; Portfolio measures current cash conversion |
| Margin | Completed deals only (not active) | Completed eligible deals | Active deals are still collecting — including them understates margin |
| HHI | All groups by originated value | Eligible groups by advanceable value | Tape shows historical concentration; Portfolio shows current facility exposure |
| Denial/Default Rate | Purchase Value of completed deals (denominator) | Eligible outstanding (denominator) | Tape = lifetime rate; Portfolio = current impairment |

### Confidence Grading

Every metric should carry an implicit confidence grade based on data quality:

| Grade | Meaning | Example |
|-------|---------|---------|
| **A — Observed** | Computed from directly observed, validated data | Collection rate from actual cash received |
| **B — Inferred** | Reconstructed from balance changes or cross-snapshot comparison | Roll rates from two snapshots; DSO from balance proxy |
| **C — Derived** | Estimated from empirical patterns or models | PAR from empirical benchmarks (Option C); EL model output |

Laith's existing "graceful degradation" pattern (hide when unavailable, label as "Derived" when estimated) is the implementation of this grading. When adding new metrics, always classify: is this A, B, or C?

---

## 7. The Three Clocks

A single time clock will misclassify delinquency for entire asset classes. Laith supports three clocks, and every time-based metric must declare which clock it uses.

### Clock Definitions

| Clock | Formula | Asset Classes | Use For |
|-------|---------|---------------|---------|
| **Origination Age** (seasoning) | `today - origination_date` | All | Vintage analysis, cohort construction, seasoning curves |
| **Contractual Delinquency** (DPD) | `max(0, today - contract_due_date)` | SILQ (consumer lending) | PAR, DPD buckets, roll rates, covenant tests |
| **Operational Delay** (OD) | `max(0, today - expected_collection_date)` | Klaim (insurance claims) | PAR, health status, collection pacing |

### Design Principle

If an asset's "due" is operational (insurer adjudication, invoice approval cycle), delinquency states must be based on Operational Delay, not DPD. Forcing contractual DPD on operational-resolution assets produces false PAR and false ineligibles.

**Current implementation:**
- Klaim uses Operational Delay (via `Expected till date` column) or empirical benchmarks when expected dates unavailable
- SILQ uses Contractual DPD (via `Repayment_Deadline` column)
- Ejari (read-only) — clocks are pre-computed in the ODS workbook

When onboarding a new asset class, the first analytical decision is: **which clock drives delinquency?**

---

## 8. Collection Rate Disambiguation

A single "collection rate" is a pitfall. Different definitions answer different questions, and using the wrong one hides liquidity stress.

### Collection Rate Variants

| Variant | Formula | Question It Answers | Laith Implementation |
|---------|---------|--------------------|--------------------|
| **Gross Liquidation Rate (GLR)** | All cash collected / Face value (Purchase Value) | "What fraction of face value has been converted to cash?" | **This is what Laith reports as "Collection Rate"** |
| **Capital Recovery Rate (CRR)** | Principal collected / Funded amount (Purchase Price) | "How much of our deployed capital came back?" | Reported as "Capital Recovery" in Returns tab |
| **Economic Recovery Rate (ERR)** | PV of cash collected (discounted) / Funded amount | "What is the time-value-adjusted return on capital?" | Not currently implemented |
| **Conditional Collection Rate (CCR)** | Cash collected in month / Outstanding at start of month | "What is the current monthly run-rate of collections?" | Not currently implemented — cumulative rates only |

### Why This Matters

- GLR can look healthy (90%+) while CRR reveals capital erosion (if deals were purchased at a premium)
- Cumulative GLR masks deterioration — if recent months are collecting at 60% but lifetime is 90%, the cumulative rate hides the problem
- ERR penalizes slow collections even if ultimate recovery is high — relevant for capital allocation decisions
- CCR (conditional monthly rate) strips out vintage effects and shows current portfolio behavior

**Current Laith approach:** GLR is the primary metric, CRR appears in Returns. This is appropriate for IC reporting. The manual recommends documenting which rate is displayed and ensuring analysts understand the distinction.

---

## 9. Dilution Framework

In ABL terminology, "dilution" is any non-credit reduction in receivable value: returns, allowances, credit memos, denials, chargebacks, pricing adjustments. This is distinct from credit loss (inability to pay).

### Mapping to Laith's Asset Classes

| ABL Concept | Klaim Equivalent | SILQ Equivalent |
|-------------|-----------------|-----------------|
| Dilution | Insurance denial (full or partial) | N/A (consumer lending has no dilution) |
| Dilution by reason code | Loss Categorization: provider_issue, coding_error, documentation | N/A |
| Credit loss | Denial after appeal exhaustion | DPD > 90 / charge-off |
| Non-credit leakage | Partial denials, documentation rejections | Late fees, penalties |

### Why This Reframing Matters

For Klaim (receivables factoring), most "losses" are actually dilution — the insurance company denies the claim, not because the claim is uncollectible, but because of documentation, coding, or coverage issues. This has two implications:

1. **Dilution is partially controllable** — better documentation, coding accuracy, and provider selection reduce dilution. Credit loss is not controllable post-origination.
2. **Dilution reserve in borrowing base** — the facility should hold a dilution reserve based on historical dilution rates by reason code, separate from a credit loss reserve. Laith's Loss Categorization already provides the reason-code breakdown needed to compute this.

### Dilution Rate

**Formula:** Sum of denied/returned amounts / Sum of face value (gross receivables)
**Decomposition:** By reason code (provider_issue, coding_error, documentation, credit/underwriting)
**Borrowing base impact:** Dilution reserve = historical dilution rate × current eligible pool

---

## 10. Metric Definitions Reference

### PAR (Portfolio at Risk)
**Formula:** PAR X+ = Sum of Outstanding on deals past due by X+ days / Total Active Outstanding
**Denominator (Tape):** All active deals' outstanding (PV - Collected - Denied)
**Denominator (Portfolio):** Eligible outstanding in the borrowing base
**Method (Primary):** Uses Expected till date to determine days past due
**Method (Derived):** Builds empirical expected collection curve from completed deals; measures active deals against it. Requires minimum 50 completed deals. Clearly labeled as "Derived from historical patterns."
**Fallback:** Hidden when neither method is viable
**Note:** Lifetime impairment rates (defaults / total originated) appear in the Loss Waterfall, not as PAR.

### DSO (Days Sales Outstanding)
**DSO Capital:** Cash-weighted average days from Deal date (funding) to collection. Measures how long capital is deployed.
**DSO Operational:** Cash-weighted average days from expected due date to actual collection. Measures operational delay beyond expected timeline.
**Method:** Curve-based interpolation when collection curve columns available; deal-age-based for completed deals otherwise.

### DTFC (Days to First Cash)
**Formula:** Median and P90 of days from Deal date to first non-zero collection
**Method:** Uses collection curve columns (first non-zero Actual in X days) when available; otherwise uses deal age of completed deals with positive collections
**Purpose:** Leading indicator — deterioration in DTFC precedes collection rate decline

### Collection Rate (GLR)
**Formula:** Collected till date / Purchase Value
**Numerator:** All cash collected (principal + margin + fees)
**Denominator:** Purchase Value (face value), not Purchase Price (funded amount)
**Weighting:** Face-weighted (each deal weighted by its PV)
**Scope:** Monthly (for trend), cumulative (for total)
**Inclusion:** All deals in period (active + completed). Completed-only variant used for vintage analysis.
**Confidence:** A (observed cash)
**See also:** Section 8 (Collection Rate Disambiguation) for CRR, ERR, CCR variants.

### HHI (Herfindahl-Hirschman Index)
**Formula:** Sum of (market share)^2 across all groups/products
**Numerator:** Per-group share squared
**Denominator:** Total originated value (Tape) or total eligible advances (Portfolio)
**Weighting:** Value-weighted (by originated or eligible amount)
**Interpretation:** < 1,500 = unconcentrated, 1,500-2,500 = moderate, > 2,500 = highly concentrated
**Time Series:** Computed across multiple snapshots to detect concentration trends
**Confidence:** A (observed data)

### Expected Loss (EL)
**Formula:** PD x LGD x EAD
**PD (Probability of Default):** % of completed deals with denial/charge-off rate > threshold (Klaim: >1% denial; SILQ: DPD > 90)
**LGD (Loss Given Default):** (Denied - Provisions - Recovery) / Denied for defaulted deals. Currently undiscounted — PV-adjusted LGD (discounting recoveries to default date) is a planned enhancement.
**EAD (Exposure at Default):** Outstanding amount on active deals
**Confidence:** B-C (PD inferred from completed deals; LGD from observed outcomes; EAD = current balance)

### Metric Doctrine Summary

Every metric in Laith should be documentable in this format:

| Field | What to Declare |
|-------|----------------|
| **Formula** | Mathematical expression |
| **Numerator** | What is being measured |
| **Denominator** | What base it is expressed against (total / active / eligible / completed) |
| **Weighting** | Count-weighted, balance-weighted, face-weighted, cash-weighted, or PV-weighted |
| **Inclusion/Exclusion** | Which deals are in vs out (status filter, eligibility filter, date filter) |
| **Clock** | Which of the three clocks drives time-based calculations |
| **Confidence** | A (observed), B (inferred/reconstructed), C (derived/estimated) |

This doctrine table is the "contract" for analytics. When adding a new metric, fill every field. When debugging a metric discrepancy, check the denominator and inclusion rules first — they are the most common source of error.

---

## 11. Methodology Onboarding Guide

Every company/product in Laith has a Methodology page — a bespoke reference document defining how each metric is computed, what it means, and why it matters for that asset class. This section formalizes the pattern for building methodology when onboarding a new company.

### Principle: Asset-Class-Centric, Not Company-Centric

Methodology is organized by **asset class** (receivables factoring, POS lending, RNPL, trade finance, etc.), not by company name. Two companies in the same asset class share the same methodology template and analysis module. The `analysis_type` field in `config.json` determines which methodology renders.

### Decision Tree: Reuse or Create?

1. **Is the new company's asset class identical to an existing one?**
   - Yes → Set `analysis_type` to the existing type (e.g., `"klaim"` for another receivables factorer). Methodology page is inherited automatically.
   - No → Create a new `analysis_type`, a new backend analysis module (`core/analysis_{type}.py`), and a new methodology content block in `Methodology.jsx`.

2. **Is the new company a read-only summary (no raw tape)?**
   - Yes → Use `analysis_type: "{type}_summary"`, build a dedicated dashboard component (like `EjariDashboard.jsx`), set `hide_portfolio_tabs: true`. Methodology is optional — can be inline in the dashboard or omitted.

### Hierarchy-to-Methodology Mapping

Every methodology page must cover all 5 levels of the analytical hierarchy. Each level requires specific sections with metric definitions.

| Level | Question | Required Methodology Sections | What to Define |
|-------|----------|-------------------------------|----------------|
| **L1 — Size & Composition** | What do we own? | Portfolio Overview | What constitutes "a deal", key size metrics (originated, funded, outstanding), product types, counterparty structure |
| **L2 — Cash Conversion** | How fast does capital return? | Collection Performance, Collection Analysis | Collection rate formula + denominator, DSO variant (capital vs operational), timing distribution, expected vs actual pacing |
| **L3 — Credit Quality** | What is deteriorating? | Health/Delinquency, Risk Migration | Distress signal definition (DPD vs denial vs default), PAR computation method, health classification thresholds, roll-rate mechanics |
| **L4 — Loss Attribution** | Where did the dollars go? | Loss Analysis, Returns/Yield, Expected Loss | Loss event definition (what counts as default), recovery path, margin structure, EL model parameters (PD/LGD/EAD thresholds) |
| **L5 — Forward Signals** | What is about to happen? | Stress Testing, Covenants | At least one leading indicator, covenant thresholds if facility exists, stress scenario design |

### Cross-Cutting Sections (Required for Every Asset Class)

These sections appear in every methodology regardless of asset class:

| Section | Purpose |
|---------|---------|
| **Product Types** | Define each product in the portfolio — mechanics, pricing, origination channel, how margin is structured |
| **Cohort Analysis** | How vintages are constructed (by deal date, disbursement date, etc.), what columns the cohort table shows |
| **Data Caveats** | Limitations of the tape data — backward-date filtering, balance columns vs as-of-date, column availability |
| **Currency Conversion** | Reported currency, FX rate source, toggle behavior |
| **Data Quality Validation** | What checks are run, critical vs warning thresholds |

### Existing Asset Class Reference

| Asset Class | analysis_type | Methodology Sections | Backend Module |
|-------------|--------------|---------------------|----------------|
| Healthcare Receivables | `klaim` | Overview, Collection Perf, Collection Analysis, Health, Cohort, Returns, Denial Funnel, Stress Testing, Expected Loss, Roll-Rate Migration, Data Quality, Currency | `core/analysis.py` |
| POS Lending | `silq` | Overview, Delinquency & PAR, Collections, Concentration, Cohort, Yield & Margins, Tenure, Covenants, Product Types, Data Caveats, Currency | `core/analysis_silq.py` |
| RNPL (read-only) | `ejari_summary` | _(no methodology page — read-only dashboard)_ | `core/analysis_ejari.py` |

### Template for New Asset Class Methodology

When building methodology for a new asset class, fill this template:

```
Level 1 — Size & Composition
  □ Define "a deal" for this asset class
  □ Key volume metrics: originated, funded, outstanding formula
  □ Product types with descriptions
  □ Counterparty/obligor structure

Level 2 — Cash Conversion
  □ Collection rate: formula, denominator, monthly vs cumulative
  □ DSO variant: which dates are available? Capital vs Operational?
  □ Collection timing: are collection curve columns available?
  □ Expected vs actual pacing: is there an expected timeline?

Level 3 — Credit Quality
  □ Distress signal: DPD (lending), denial (factoring), or other?
  □ PAR method: direct DPD, expected-date shortfall, or empirical?
  □ Health classification: what thresholds define Healthy/Watch/Delayed/Poor?
  □ Roll rates: what buckets are meaningful?

Level 4 — Loss Attribution
  □ Default definition: what constitutes a loss event?
  □ Recovery path: how are losses recovered (collections, legal, resubmission)?
  □ Margin structure: how is revenue earned and tracked?
  □ EL parameters: PD threshold, LGD methodology, EAD basis

Level 5 — Forward Signals
  □ Leading indicator: which signal is most predictive for this asset class?
  □ Covenant monitoring: does a facility agreement exist?
  □ Stress scenarios: what concentration/macro shocks are relevant?

Cross-Cutting
  □ Product types documented with mechanics and pricing
  □ Cohort construction method defined
  □ Data limitations and caveats documented
  □ Currency and FX behavior specified
  □ Validation checks listed
```
