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

### Ejari — Rent Now Pay Later (RNPL, KSA)
**What is financed:** Tenant rent payments advanced to landlords
**Obligor:** Tenants (consumer borrowers)
**Default event:** DPD-based delinquency, write-off
**Data pattern:** Pre-computed ODS workbook (no raw loan tape). 12 analysis tabs parsed from 13 sheets.

Key differences from raw tape analytics:
- Read-only summary — all metrics pre-computed by Ejari's internal team
- No live computation; `analysis_type: "ejari_summary"` bypasses tape loading entirely
- DPD buckets and roll rates provided directly in the workbook
- Write-off cohort (32 loans) isolated in a dedicated sheet — clean separation principle applied at source
- Najiz (Saudi legal enforcement) recovery tracked as a separate process
- `hide_portfolio_tabs: true` — no facility agreement, no portfolio monitoring

### Tamara — Buy Now Pay Later (BNPL, KSA & UAE)
**What is financed:** Consumer instalment purchases (BNPL Pi2-6 up to SAR 5K, BNPL+ Pi4-24 up to SAR 20K via Murabaha)
**Obligor:** Consumer borrowers
**Default event:** DPD > 120 (covenant trigger), write-off at DPD 90
**Data pattern:** Data room ingestion (~100 source files). Two geographies: KSA (SAR, 14 tabs) and UAE (AED, 10 tabs).

Key differences from single-tape analytics:
- No raw loan tape — data synthesized from vintage cohort matrices, HSBC investor reports, Deloitte FDD, financial models
- ETL script (`scripts/prepare_tamara_data.py`) runs once offline; runtime parser loads JSON snapshot
- Vintage performance tracked via MOB (Months on Book) cohort matrices — default, delinquency, dilution views
- HSBC investor reports provide covenant trigger levels (L1/L2/L3 tiered thresholds)
- Securitisation context: KSA $2.375B (Goldman, Citi, Apollo), UAE $131M (Goldman)
- Two-product structure maps to geography, not product type

### Aajil — SME Trade Credit (Raw Materials, KSA)
**What is financed:** Raw materials purchased by SMEs on trade credit terms
**Obligor:** SME buyers (Manufacturers, Contractors, Wholesale Traders)
**Default event:** DPD 60+ (contractual delinquency)
**Data pattern:** Multi-sheet xlsx tape (1,245 deals across 7 sheets: Deals, Payments, DPD Cohorts, Collections).

Key differences from consumer lending:
- Two deal structures: EMI (equal monthly instalments, 51%) and Bullet (lump-sum at maturity, 49%)
- ALL 19 write-offs are Bullet deals — structural insight: EMI shift reduces default risk
- Three customer types with distinct risk profiles: Manufacturer, Contractor, Wholesale Trader
- Trust score system measures customer reliability based on payment history
- Concentration risk at customer level (227 customers, top-15 drive bulk of volume)
- Industry-level segmentation meaningful (unlike consumer BNPL where borrowers are homogeneous)
- Uses Cascade Debt (app.cascadedebt.com) as external reporting platform — dashboard metrics aligned

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

---

## 12. Compute Function Registry

This section is **auto-generated** from the metric registry. Run `python scripts/sync_framework_registry.py` to update.


### Klaim

| Section | Level | Tab | Denominator | Confidence | Required Columns |
|---------|-------|-----|-------------|------------|------------------|
| Portfolio Overview Metrics | L1 | overview | total | A | Deal date, Status, Purchase value, Purchase price, ... |
| Collection Performance | L2 | actual-vs-expected | total | A | Deal date, Purchase value, Collected till date, Expected total |
| Collection Analysis | L2 | collection | total | A | Deal date, Purchase value, Collected till date, Status |
| Cash-Flow-Weighted Duration | L2 | overview | total | B | Deal date, Purchase value |
| Health Classification | L3 | ageing | active | A | Deal date, Status, Purchase value, Collected till date, ... |
| Portfolio at Risk (PAR) | L3 | overview | active | B | Status, Purchase value, Collected till date, Denied by insurance |
| Cohort Analysis | -- | cohort-analysis | total | A | Deal date, Purchase value, Purchase price, Collected till date, ... |
| Returns Analysis | L4 | returns | completed | A | Purchase value, Purchase price, Collected till date, Status |
| Denial Funnel | L4 | denial-trend | total | A | Purchase value, Collected till date, Pending insurance response, Denied by insurance, ... |
| Loss Waterfall | L4 | loss-waterfall | total | A | Deal date, Purchase value, Denied by insurance, Collected till date |
| Stress Testing | L5 | risk-migration | total | B | Group, Purchase value, Collected till date |
| Forward-Looking Signals | L5 | overview | active | B | Deal date, Collected till date |
| Expected Loss Model | L4 | risk-migration | active | B | Status, Purchase value, Collected till date, Denied by insurance |
| Roll-Rate Migration | L3 | risk-migration | active | B | Deal date, Status |
| Advanced Analytics | -- | collections-timing | total | A | Deal date, Purchase value |
| CDR / CCR | L3 | cdr-ccr | total | A | Deal date, Purchase value, Collected till date |
| Facility-Mode PD | L5 | facility-pd | active | B | Deal date, Status, Purchase value |
| Data Quality Validation | -- | data-integrity | -- | -- |  |

### SILQ

| Section | Level | Tab | Denominator | Confidence | Required Columns |
|---------|-------|-----|-------------|------------|------------------|
| Portfolio Overview | L1 | overview | total | A | Agreement_ID, Disbursed_Amount (SAR), Outstanding_Amount (SAR), Status, ... |
| Delinquency & PAR | L3 | delinquency | active | A | Repayment_Deadline, Outstanding_Amount (SAR), Status |
| Collections | L2 | collections | total | A | Disbursement_Date, Amt_Repaid (SAR), Total_Collectable_Amount (SAR) |
| Concentration | L1 | concentration | total | A | Shop_Name, Disbursed_Amount (SAR), Outstanding_Amount (SAR) |
| Cohort Analysis | -- | cohort-analysis | total | A | Disbursement_Date, Disbursed_Amount (SAR), Amt_Repaid (SAR), Outstanding_Amount (SAR) |
| Yield & Margins | L4 | yield-margins | completed | A | Disbursed_Amount (SAR), Margin Collected (SAR), Status |
| Tenure Analysis | -- | tenure | total | A | Tenure_Days, Disbursed_Amount (SAR), Status |
| Covenant Monitoring | L5 | covenants | eligible | A | Repayment_Deadline, Outstanding_Amount (SAR), Amt_Repaid (SAR), Status |
| Seasonality | L5 | seasonality | total | A | Disbursement_Date, Disbursed_Amount (SAR) |
| Loss Waterfall | L4 | loss-waterfall | total | A | Disbursement_Date, Disbursed_Amount (SAR), Repayment_Deadline, Amt_Repaid (SAR) |
| Underwriting Drift | L5 | underwriting-drift | total | A | Disbursement_Date, Disbursed_Amount (SAR), Tenure_Days, Product |
| CDR / CCR | L4 | cdr-ccr | total | A | Disbursement_Date, Disbursed_Amount (SAR), Repayment_Deadline, Amt_Repaid (SAR) |

---

## 13. Column-to-Feature Dependency Map

When a tape is loaded, the available columns determine which features are enabled. This map drives graceful degradation.

### Universal Required Columns (all analysis_types)
- **Deal/Loan ID** — unique identifier
- **Origination date** — vintage construction, deployment charts
- **Face value** — all monetary metrics
- **Status** — active vs completed segmentation

### Feature Activation by Column Presence

| Column(s) | Features Enabled |
|-----------|-----------------|
| Collected amount | Collection rate, DSO, Revenue, Cohorts, Returns |
| Denied/Default amount | Denial trend, Loss waterfall, PAR, EL model, CDR/CCR |
| Pending amount | Denial funnel, Actual vs Expected |
| Expected till date | PAR (primary method), Pacing, Expected rate line |
| Collection curves (Expected/Actual at 30d intervals) | DSO (curve-based), DTFC (curve-based), Collections timing, Collection speed in cohorts |
| Funded amount (Purchase price) | Returns, Capital recovery, Margins |
| Discount / Interest rate | Returns (discount bands), Underwriting drift |
| Group / Counterparty | Concentration, HHI, Group performance, Stress test, Loss categorization |
| Product type | Deployment by product, Segment analysis |
| New business flag | New vs repeat in Deployment, Returns, Segments |
| Owner / SPV | Owner breakdown in Portfolio tab |
| Fee columns | Revenue (fee income component) |
| Due date / Repayment deadline | PAR (contractual DPD), DPD buckets |
| DPD column | Delinquency tab, PAR (direct), Roll rates |
| VAT columns | VAT summary in Revenue |

### Graceful Degradation Pattern
```python
# Every compute function that depends on optional columns MUST follow this pattern:
def compute_feature(df, mult, as_of_date=None):
    if 'required_column' not in df.columns:
        return {'available': False}
    # ... compute ...
    return {'available': True, ...data...}
```

Frontend checks: `if (!data.available) return null;` — section hidden entirely.

---

## 14. Asset Class Decision Tree

When onboarding a new company, walk through this decision tree to classify the asset class and determine the analytical approach.

```
START
  │
  ├─ Is the data a raw loan tape (CSV/Excel)?
  │   │
  │   ├─ YES → Standard analysis pipeline
  │   │   │
  │   │   ├─ Does the obligor have contractual payment dates?
  │   │   │   ├─ YES → Clock = Contractual DPD (like SILQ)
  │   │   │   │   └─ PAR computable from DPD column directly
  │   │   │   │
  │   │   │   └─ NO → Does the tape have expected collection timelines?
  │   │   │       ├─ YES → Clock = Operational Delay (like Klaim)
  │   │   │       │   └─ PAR from Expected till date shortfall
  │   │   │       │
  │   │   │       └─ NO → Clock = Origination Age only
  │   │   │           └─ PAR from empirical benchmarks (Option C) or hidden
  │   │   │
  │   │   ├─ Is this a factoring/receivables product?
  │   │   │   ├─ YES → Loss = denial/dilution (Klaim pattern)
  │   │   │   │   └─ Dilution framework applies (Section 9)
  │   │   │   │
  │   │   │   └─ NO → Is this consumer/commercial lending?
  │   │   │       ├─ YES → Loss = DPD > threshold / charge-off (SILQ pattern)
  │   │   │       │
  │   │   │       └─ NO → Define loss event for this asset class
  │   │   │
  │   │   └─ Does a facility agreement govern this portfolio?
  │   │       ├─ YES → Portfolio Analytics enabled
  │   │       │   └─ Define: advance rates, concentration limits, covenants
  │   │       │
  │   │       └─ NO → Tape Analytics only
  │   │           └─ Set hide_portfolio_tabs: false (can still compute tape-based portfolio metrics)
  │   │
  │   └─ NO → Pre-computed workbook (ODS/Excel)
  │       └─ analysis_type = "{type}_summary"
  │           ├─ hide_portfolio_tabs: true
  │           ├─ Build parser (like analysis_ejari.py)
  │           └─ Build dedicated dashboard component
  │
  └─ END
```

---

## 15. As-of-Date Filtering & Data Integrity

### The Core Limitation

Loan tapes are **point-in-time snapshots**. Every balance column (`Collected till date`, `Denied by insurance`, `Pending insurance response`, `Outstanding`) reflects the state as of the **tape snapshot date**, not any arbitrary as-of date.

When `filter_by_date(df, as_of_date)` is applied:
- **What it does:** Filters deals by `Deal date <= as_of_date` (origination date)
- **What it does NOT do:** Adjust collection, denial, or outstanding amounts to reflect what they were on the as-of date

### Metric Classification

| Category | Metrics | Safe for Backdated? |
|----------|---------|---------------------|
| **Deal Selection** | Deal count, originated volume, deployment, vintage composition, cohort membership | YES |
| **Balance-Dependent** | Collection rate, denial rate, outstanding, margins, revenue (realized/unrealized), PAR, ageing health, CDR/CCR | NO — reflects tape date |
| **Time-Based** | Days outstanding, deal age, DSO (when curve-based) | YES |
| **Derived** | HHI (if based on originated volume), concentration by deal count | YES |

### Enforcement Rules

1. **Visual flagging:** Every KPI card that depends on balance columns must show a `TAPE DATE` badge and dim its value when `as_of_date < snapshot_date`. Implemented via the `stale` prop on `KpiCard`.
2. **AI analysis blocked:** All AI endpoints (`ai-commentary`, `ai-executive-summary`, `ai-tab-insight`) return HTTP 400 when `as_of_date < snapshot_date`. The AI cannot distinguish safe from unsafe metrics and would present inflated numbers as fact.
3. **Banner warning:** `BackdatedBanner` component shows a persistent (dismissible) warning classifying metrics as ACCURATE vs TAPE DATE.
4. **No estimation:** Do not attempt to estimate historical balances from current data. The exception would be collection curves (30-day interval columns) which could theoretically reconstruct historical states, but this is not implemented and would only work on tapes with curve columns.

### For New Companies

When onboarding a new company, verify that `filter_by_date` only filters deal selection. If the new asset class has a way to reconstruct historical balances (e.g., transaction-level payment history), document it here and consider implementing date-aware metric adjustment.

---

## 16. Living Mind Architecture

The Living Mind is the platform's institutional memory system. It captures analyst preferences, corrections, IC feedback, and cross-company patterns — then feeds them into every AI prompt so that Claude never repeats a corrected mistake and progressively aligns with the fund's analytical voice.

### Two-Tier Structure

| Tier | Scope | Location | Purpose |
|------|-------|----------|---------|
| **Master Mind** | Fund-level | `data/_master_mind/` | Cross-company preferences, IC norms, writing style, framework evolution |
| **Company Mind** | Per-position | `data/{co}/mind/` | Position-specific corrections, findings, memo edits, data quality notes |

Both tiers use **append-only JSONL** files (one JSON object per line). This format is audit-friendly, git-trackable, and supports incremental reads without parsing the entire history.

### Master Mind Categories

| Category File | What It Stores | Example Entry |
|---------------|---------------|---------------|
| `preferences.jsonl` | Formatting, terminology, display conventions | `{"rule": "Always show PAR as lifetime headline, active as subtitle"}` |
| `cross_company.jsonl` | Patterns observed across 2+ companies | `{"pattern": "BNPL portfolios season in Q4", "companies": ["SILQ", "Tamara"]}` |
| `framework_evolution.jsonl` | Changes to analytical methodology | `{"change": "Added DTFC as L5 leading indicator", "date": "2026-03-15"}` |
| `ic_norms.jsonl` | Investment committee expectations | `{"norm": "IC wants PAR 30+ below 5% for approval"}` |
| `writing_style.jsonl` | Tone and structure preferences | `{"rule": "Use 'deterioration' not 'worsening'. Quantify every claim."}` |

### Company Mind Categories

| Category File | What It Stores | Trigger |
|---------------|---------------|---------|
| `corrections.jsonl` | Metric fixes, label changes, data reinterpretations | Post-correction (automatic) |
| `memo_edits.jsonl` | Tracked changes between memo versions | Post-memo-edit (automatic) |
| `findings.jsonl` | Notable analytical observations | During executive summary generation |
| `ic_feedback.jsonl` | Comments from IC review | Manual entry via `/mind-review` |
| `data_quality.jsonl` | Column issues, outliers, exclusion decisions | During `/validate-tape` |
| `session_lessons.jsonl` | End-of-session learnings | During `/eod` |

### 4-Layer Prompt Injection

Every AI call (`_build_*_full_context()`) assembles context in this order:

```
Layer 1: Analysis Framework (non-negotiable rules from this document)
   ↓
Layer 2: Master Mind (fund-level preferences and cross-company patterns)
   ↓
Layer 3: Methodology (company-specific metric definitions and formulas)
   ↓
Layer 4: Company Mind (position-specific corrections and IC feedback)
```

Later layers override earlier ones for the same topic. A Company Mind correction like `"Tamara outstanding is AR not originated"` overrides any generic assumption from the Framework layer.

**Implementation:** `core/mind/mind_loader.py` exposes `build_mind_context(company, product)` which reads both tiers, deduplicates, and returns a formatted string block. Called by all `_build_*_full_context()` functions in `backend/main.py`.

### Knowledge Lifecycle

```
Company Mind entry (single company)
   ↓ appears in 2+ companies
Master Mind promotion (fund-level pattern)
   ↓ becomes permanent rule
Framework codification (added to ANALYSIS_FRAMEWORK.md)
```

**Consolidation:** Periodic summarization (`/mind-review`) compresses accumulated entries into higher-order patterns, archives raw entries, and promotes cross-company patterns to the Master Mind.

### When to Record

| Event | Target Tier | Mechanism |
|-------|-------------|-----------|
| Analyst corrects a metric label or formula | Company Mind → `corrections.jsonl` | Automatic on edit |
| Analyst edits a generated memo section | Company Mind → `memo_edits.jsonl` | Automatic diff capture |
| IC reviews memo and provides feedback | Company Mind → `ic_feedback.jsonl` | Manual via `/mind-review` |
| Data quality issue found during validation | Company Mind → `data_quality.jsonl` | During `/validate-tape` |
| Session ends with learnings | Company Mind → `session_lessons.jsonl` | During `/eod` |
| Pattern appears across multiple companies | Master Mind → `cross_company.jsonl` | During `/mind-review` |

---

## 17. Legal Extraction & Facility Params Binding

AI-powered extraction of facility agreement terms — the third analytical pillar alongside tape analytics and portfolio monitoring. Instead of manually keying covenant thresholds and advance rates, Claude reads the facility agreement PDF and populates the system.

### 5-Pass Extraction Pipeline

Each pass targets a specific section of the facility agreement, with Claude returning structured JSON:

| Pass | Focus | Output Schema |
|------|-------|--------------|
| 1 — Definitions | Defined terms, eligible receivable criteria, exclusion list | `FacilityTerms`, `EligibilityCriterion[]` |
| 2 — Facility & Rates | Facility size, advance rates by region/product, interest rate, fees | `AdvanceRate[]`, fee structures |
| 3 — Covenants & Concentration | Financial covenants, concentration limits, portfolio tests | `FinancialCovenant[]`, `ConcentrationLimit[]` |
| 4 — EOD & Reporting | Events of default, cure periods, reporting requirements, waterfall | `EventOfDefault[]`, `ReportingRequirement[]` |
| 5 — Risk Assessment | Structural risks, unusual provisions, comparison to market norms | `RiskFlag[]` |

### Pydantic Schemas

All extracted data validated through strict Pydantic models defined in `core/legal/schemas.py`:

- `FacilityTerms` — top-level: facility_amount, currency, maturity, revolving_period, interest_rate
- `EligibilityCriterion` — field, operator, value, description (e.g., `age_days <= 91`)
- `AdvanceRate` — region, product_type, rate, conditions
- `ConcentrationLimit` — limit_type (single_borrower, geography, product, sector), threshold, tiered_schedule
- `FinancialCovenant` — name, formula, threshold, frequency, cure_period
- `EventOfDefault` — trigger, cure_period_days, cross_default, severity
- `ReportingRequirement` — report_type, frequency, deadline_days, recipient
- `RiskFlag` — category, description, severity (high/medium/low), recommendation

### 3-Tier Facility Params Merge

When computing borrowing base, concentration limits, and covenants, parameters are resolved in priority order:

```
1. Document-extracted params (from legal extraction)     ← highest priority
   ↓ override
2. Manual analyst overrides (from FacilityParamsPanel)   ← mid priority
   ↓ fallback
3. Hardcoded defaults (in core/portfolio.py)             ← lowest priority
```

**Implementation:** `core/legal/extraction.py` exposes `extraction_to_facility_params()` which maps extracted schemas to the `facility_configs` JSONB structure consumed by `core/portfolio.py`.

### Confidence Grading

| Grade | Meaning | Example |
|-------|---------|---------|
| **HIGH** | Verbatim from document, exact number/formula | `"Advance rate: 85% for UAE receivables"` |
| **MEDIUM** | Inferred from context, reasonable interpretation | `"WAL limit appears to be 70 days based on eligibility section"` |
| **LOW** | Estimated, not explicitly stated, or ambiguous | `"Cure period not specified, assumed 5 business days"` |

Each extracted field carries its confidence grade. The UI displays amber badges on MEDIUM and red badges on LOW fields, prompting analyst review.

### Caching & Storage

- Extraction runs once per document: results cached as `{filename}_extracted.json` alongside the source PDF in `data/{co}/{prod}/dataroom/`
- Re-extraction only on explicit request or when source file hash changes
- Extraction results are immutable — analyst overrides stored separately in `facility_configs`

### Klaim Facility Agreement Findings

Initial extraction from the Klaim facility agreement revealed discrepancies vs hardcoded defaults:

| Parameter | Previously Hardcoded | Extracted from Agreement |
|-----------|---------------------|-------------------------|
| Aging cutoff | 365 days | **91 days** |
| WAL limit | 60 days | **70 days** |
| Geography | UAE + international | **UAE only** (Non-UAE excluded) |
| EoD rules | Uniform | **Vary per covenant** (different cure periods) |
| Covenants | 6 | **7** (Parent Cash Balance added) |

**Reference:** `core/LEGAL_EXTRACTION_SCHEMA.md` for full field definitions and extraction prompt templates.

---

## 18. Data Room & Document Classification

Generalized data room ingestion for any company's document collection. The Tamara onboarding proved that ~100 heterogeneous files can be parsed, classified, and indexed into a searchable research corpus. This section formalizes the pattern as a platform capability.

### DataRoomEngine

`core/dataroom/engine.py` provides the `DataRoomEngine` class:

```python
engine = DataRoomEngine(company="Tamara", product="KSA")
engine.scan()       # Discover all files in data/{co}/{prod}/dataroom/
engine.parse()      # Extract text/tables from each file
engine.chunk()      # Split into ~800-token chunks
engine.index()      # Build TF-IDF search index
engine.save()       # Persist registry + index to disk
```

### Supported File Types

| Type | Library | Extraction Strategy |
|------|---------|-------------------|
| PDF | `pdfplumber` | Page-by-page text + table detection. Tables preserved as markdown. |
| Excel (.xlsx/.xls) | `pandas` | All sheets read. Numeric sheets → tables. Text-heavy sheets → paragraphs. |
| ODS | `pandas` + `odfpy` | Same as Excel. |
| CSV | `pandas` | Single table per file. |
| JSON | `json` | Structured data preserved. Nested objects flattened for search. |
| DOCX | `python-docx` | Paragraph-by-paragraph. Tables extracted separately. |

### Document Classification

`core/dataroom/classifier.py` assigns a `doc_type` to each file based on filename patterns, content heuristics, and sheet names:

| doc_type | Detection Signal | Example |
|----------|-----------------|---------|
| `facility_agreement` | "facility", "credit agreement", legal language density | `Klaim_Facility_Agreement_2024.pdf` |
| `investor_report` | "investor", "monthly report", standardized sections | `HSBC_Tamara_Monthly_Oct2025.pdf` |
| `fdd_report` | "due diligence", "FDD", "Deloitte"/"EY"/"KPMG" | `Deloitte_FDD_Tamara_2024.xlsx` |
| `financial_model` | "model", "projection", "forecast", multiple formula sheets | `Tamara_Financial_Master_2025.xlsx` |
| `vintage_cohort` | "vintage", "cohort", "MOB", matrix-shaped sheets | `KSA_Default_Vintage_Matrix.xlsx` |
| `portfolio_tape` | "tape", "loan", "receivable", row-per-deal structure | `2026-03-03_uae_healthcare.csv` |
| `legal_document` | "amendment", "waiver", "consent", "side letter" | `First_Amendment_2025.pdf` |
| `company_presentation` | "presentation", "pitch", "overview", slide-like structure | `Tamara_Investor_Deck_2025.pdf` |
| `demographics` | "demographic", "customer", "merchant", "segment" | `Portfolio_Demographics_Q4.xlsx` |
| `business_plan` | "business plan", "BP", "5-year", projection tables | `Tamara_5Y_Business_Plan.xlsx` |
| `analytics_tape` | Generated by platform tape analytics | `_analytics_tape_2026-03.json` |
| `analytics_portfolio` | Generated by platform portfolio analytics | `_analytics_portfolio_2026-03.json` |
| `analytics_ai` | Generated by platform AI summaries | `_analytics_ai_executive_2026-03.json` |
| `memo_draft` / `memo_final` | Generated by memo engine | `memo_v1_draft.json` / `memo_v3_final.json` |

### Chunking Strategy

- Target chunk size: ~800 tokens (~3,200 characters)
- Split boundaries: paragraph breaks, section headers, page breaks
- Tables preserved as single chunks (never split mid-table)
- Overlap: 100 tokens between consecutive chunks for continuity
- Each chunk carries metadata: `{doc_id, chunk_index, page_number, doc_type, section_title}`

### Registry & Incremental Updates

Each product maintains a registry at `data/{co}/{prod}/dataroom/registry.json`:

```json
{
  "doc_001": {
    "filename": "Klaim_Facility_Agreement_2024.pdf",
    "doc_type": "facility_agreement",
    "sha256": "a1b2c3...",
    "chunks": 47,
    "parsed_at": "2026-04-10T14:30:00Z"
  }
}
```

- **Change detection:** SHA-256 hash comparison on `refresh()` — only re-parses new or modified files
- **Removals:** Files deleted from disk are marked `"status": "removed"` in registry (never hard-deleted from index)
- **Analytics snapshots:** Platform-computed analytics (tape summary, portfolio metrics, AI narratives) are captured as JSON documents in the data room, making them searchable alongside source documents

### Exclusions

- Directories: `dataroom/`, `mind/`, `__pycache__/` excluded from recursive scan
- Files: `config.json`, `methodology.json`, `registry.json` excluded to prevent non-data files from entering the index

---

## 19. Research Hub & Query Engine

Research intelligence powered by Claude RAG, accessible through a dedicated Research page in the frontend. The Research Hub answers natural-language questions across all ingested documents, analytics snapshots, and mind entries.

### Claude RAG Pipeline

The research engine uses the platform's own data room index:

```
Query → TF-IDF retrieval (top 10 chunks) → Rerank by relevance
   ↓
Build prompt: retrieved chunks + mind context + analytics context
   ↓
Claude synthesis → answer with inline citations [Doc: filename, p.X]
```

**Implementation:** `core/research/query_engine.py` exposes the Claude RAG query. The retrieval step uses the TF-IDF index built by `DataRoomEngine`. Mind context is injected via `build_mind_context()` so that answers respect accumulated corrections and preferences.

### Insight Extraction (Rules-Based)

At document ingest time, `core/research/insight_extractor.py` runs regex-based extraction to identify key facts without AI calls:

| Pattern Type | Regex Examples | Extracted As |
|-------------|---------------|-------------|
| Metrics | `PAR\s*\d+\+?\s*[:=]\s*[\d.]+%`, `default rate.*?[\d.]+%` | `{metric, value, context}` |
| Facility amounts | `\$[\d,.]+[MBK]`, `SAR\s*[\d,.]+\s*(million|M)` | `{currency, amount, context}` |
| Covenant thresholds | `(not exceed|minimum|maximum|at least).*?[\d.]+%?` | `{covenant, threshold, direction}` |
| Maturity dates | `(maturity|expiry|termination).*?\d{4}` | `{event, date, context}` |
| Risk flags | `(material adverse|event of default|breach|downgrade)` | `{flag, severity, context}` |
| Entities | Known company/bank names, counterparty patterns | `{entity, role, context}` |

These extracted insights are stored in the registry and surfaced in the Document Library as filterable tags.

### Frontend Pages

| Page | Route | Purpose |
|------|-------|---------|
| **Research Chat** | `/company/:co/:product/research` | Natural-language queries across all documents |
| **Document Library** | `/company/:co/:product/research/documents` | Browse, filter, search ingested files with type badges and stats |

### Integration with Analytics

Research answers can cite both data room documents AND platform-computed analytics snapshots. When a query asks about "collection rate trend," the engine retrieves both the tape analytics snapshot and any investor reports discussing collections — providing a cross-referenced answer.

---

## 20. IC Memo Generation Pipeline

AI-powered investment memo generation with structured templates, analytics integration, versioned workflow, and feedback loop. The memo engine produces investment-committee-ready documents where every number matches the dashboard.

### 4 Templates

| Template | Sections | Typical Length | When Used |
|----------|----------|---------------|-----------|
| **Credit Memo** | 12 sections | 15–25 pages | New investment / facility approval |
| **Due Diligence Report** | 9 sections | 10–18 pages | Pre-investment deep-dive |
| **Monthly Monitoring Update** | 6 sections | 4–8 pages | Recurring portfolio update |
| **Quarterly Review** | 5 sections | 6–12 pages | Quarterly IC presentation |

### Section Source Types

Each section in a template declares its data source:

| Source Type | Origin | Example |
|-------------|--------|---------|
| `DATAROOM` | From ingested data room documents via RAG | Company background, facility terms, market context |
| `ANALYTICS` | From tape/portfolio compute functions | Portfolio metrics, cohort tables, PAR, collection rates |
| `AI_NARRATIVE` | From prior AI summaries (executive summary, tab insights) | Synthesized commentary, trend analysis |
| `MIXED` | Cross-references documents + analytics | Credit quality section citing both data and facility terms |
| `MANUAL` | Analyst writes or dictates | Investment thesis, recommendation, custom commentary |
| `AUTO` | Auto-generated appendix (data tables, methodology notes) | Appendix: metric definitions, data sources, caveats |

### Analytics Bridge

`core/research/analytics_bridge.py` maps memo sections to backend compute functions:

| Memo Section | Compute Functions | Data |
|-------------|-------------------|------|
| Portfolio Overview | `compute_summary()` | KPIs, deal counts, originated volume |
| Credit Quality | `compute_par()`, `compute_cohort_loss_waterfall()` | PAR 30+/60+/90+, default rates, loss waterfall |
| Collections & Liquidity | `compute_collection_velocity()`, `compute_dso()`, `compute_dtfc()` | Collection rate, DSO, DTFC, timing distribution |
| Concentration | `compute_concentration()`, `compute_hhi_for_snapshot()` | HHI, top exposures, group performance |
| Vintage Performance | `compute_cohort()`, `compute_vintage_loss_curves()` | Cohort table, loss curves, collection speed |
| Covenant Compliance | `compute_covenants()`, `compute_borrowing_base()` | Covenant status, borrowing base, headroom |
| Risk Assessment | `compute_expected_loss()`, `compute_stress_test()` | EL model, stress scenarios, roll rates |

**Critical rule:** Every number in the memo MUST match the dashboard. The analytics bridge calls the same compute functions that power the charts — no separate calculation path.

### AI Section Generation

Each section is generated sequentially by Claude:

```
For each section in template:
  1. Gather source data (DATAROOM chunks + ANALYTICS results + prior sections)
  2. Build prompt: section instructions + source data + mind context + prior sections (for narrative coherence)
  3. Claude generates section text with inline metric citations
  4. Validate: check that cited numbers match analytics bridge output
  5. Store section in memo version
```

**Narrative coherence:** Each section prompt includes the full text of all prior sections, so Claude maintains a consistent analytical thread throughout the memo. The mind context ensures the writing style matches IC expectations.

### Versioning & Status Workflow

Memos are stored as immutable versions in `reports/memos/{co}_{prod}/{memo_id}/`:

```
reports/memos/klaim_UAE_healthcare/memo_20260410/
├── v1.json          # First draft
├── v2.json          # After analyst edits
├── v3.json          # Final version
├── v3_final.pdf     # Exported PDF
└── metadata.json    # Status, template, created_at, author
```

**Status workflow:**

```
draft → review → final → archived
  ↑       │
  └───────┘  (revisions send back to draft)
```

- **draft:** Being generated or edited. Analyst can regenerate individual sections.
- **review:** Submitted for IC review. Read-only except for comments.
- **final:** Approved by IC. PDF exported with no DRAFT watermark. Locked.
- **archived:** Superseded by a newer memo. Retained for audit trail.

### PDF Export

Dark-themed ReportLab output matching the existing `core/research_report.py` styling:

- Navy background, gold section headers, teal/red metric highlighting
- Cover page with LAITH branding, memo title, date, status badge
- Table of contents with page numbers
- `DRAFT` watermark on non-final versions (diagonal, semi-transparent)
- Page headers (company name + memo type) and footers (page number + generation date)

### Feedback Loop

Every analyst edit to a generated memo section is captured:

```
1. Analyst edits Section 3 text in MemoEditor
2. Diff computed: original AI text vs edited text
3. Diff stored in Company Mind → memo_edits.jsonl
4. Next memo generation for this company incorporates edit patterns
5. If similar edits appear across 2+ companies → Master Mind promotion
```

This creates a self-improving cycle: the first memo for a new company may need heavy editing, but subsequent memos converge toward the analyst's preferred style and emphasis.

### Frontend Components

| Component | Purpose |
|-----------|---------|
| `MemoBuilder` | 4-step wizard: select template → choose sections → configure sources → generate |
| `MemoEditor` | Section navigation panel + rich text editor + regenerate button per section |
| `MemoArchive` | History of all memos with status filters, search, and version comparison |

---

## 21. Intelligence System & Knowledge Graph

Self-learning institutional memory built in 7 phases. The system captures corrections, extracts entities, detects patterns across companies, and feeds accumulated knowledge into every AI prompt.

### 7-Phase Architecture

| Phase | Module | Purpose |
|-------|--------|---------|
| **0 — Foundation** | `core/mind/schema.py`, `relation_index.py`, `event_bus.py` | KnowledgeNode + Relation dataclasses, bidirectional adjacency list, sync pub/sub |
| **1 — Knowledge Graph** | `core/mind/graph.py` | Graph-aware query engine with recency/category/graph bonus scoring, supersession exclusion |
| **2 — Incremental Compilation** | `core/mind/entity_extractor.py`, `compiler.py` | Regex extraction of 7 entity types, one-input-many-updates pipeline, cross-document discrepancy detection |
| **3 — Closed-Loop Learning** | `core/mind/learning.py` | Auto-classifies corrections, generates rules as KnowledgeNodes, pattern extraction from 3+ similar corrections |
| **4 — Thesis Tracker** | `core/mind/thesis.py` | Per-company investment thesis with measurable pillars, auto-drift detection (holding/weakening/broken) |
| **5 — Proactive Intelligence** | `core/mind/intelligence.py`, `briefing.py`, `analyst.py` | Cross-company pattern detection, morning briefings, persistent analyst context |
| **6 — Queryable KB** | `core/mind/kb_decomposer.py`, `kb_query.py` | Decomposes lessons.md + CLAUDE.md into linked nodes, unified search across all knowledge stores |

### Storage & Schema

JSONL-first — no database dependency. Each scope (master, per-company) maintains its own set of JSONL files. KnowledgeNode extends MindEntry via composition: graph metadata stored in `metadata["_graph"]` subkey for backward compatibility. Lazy upgrade on read via `upgrade_entry()` — no batch migration needed. RelationIndex is a separate `relations.json` per scope (bidirectional adjacency list).

### Event-Driven Wiring

Four events fire from live endpoints and propagate through the event bus to registered listeners:

| Event | Trigger | Listeners |
|-------|---------|-----------|
| `TAPE_INGESTED` | New tape loaded (deduped per session) | Metric compilation, thesis drift check |
| `DOCUMENT_INGESTED` | Data room file parsed | Entity extraction, knowledge compilation |
| `MEMO_EDITED` | Analyst edits AI-generated section | Learning rule generation (with old content for diff) |
| `CORRECTION_RECORDED` | DataChat thumbs-down or explicit correction | Correction analysis, auto-rule creation |

Event bus is synchronous and in-process. `disable()` method available for test isolation.

### Entity Types

`core/mind/entity_extractor.py` uses regex-based extraction (no ML) to identify 7 entity types from text and tape metrics:

| Entity Type | Examples |
|-------------|---------|
| `COVENANT` | PAR 30+ < 7%, Collection Ratio > 85% |
| `METRIC` | Collection rate 94.2%, HHI 1,850 |
| `RISK_FLAG` | Concentration breach, PAR threshold exceeded |
| `COUNTERPARTY` | Goldman Sachs, HSBC, Deloitte |
| `DATE_EVENT` | Maturity date, facility renewal, IC review |
| `THRESHOLD` | Advance rate 85%, aging cutoff 91 days |
| `FACILITY_TERM` | Facility limit $20M, revolving period 2 years |

One document typically produces 10-15 knowledge updates via the compilation pipeline.

### 5-Layer AI Context

Every AI call assembles context in priority order (later layers override earlier for the same topic):

```
Layer 1: Analysis Framework (codified rules from this document)
Layer 2: Master Mind (fund-level preferences, cross-company patterns)
Layer 3: Methodology (company-specific metric definitions and formulas)
Layer 4: Company Mind (position-specific corrections and IC feedback)
Layer 5: Thesis (investment thesis pillars, drift alerts, conviction score)
```

Layer 5 was added by the Intelligence System. When no thesis exists for a company, Layer 5 is an empty string (backward-compatible). `build_mind_context()` in `core/mind/` assembles all 5 layers.

### Knowledge Lifecycle

```
Fast correction (single company, single session)
   ↓ accumulates
Consolidation (Company Mind — corrections, findings, rules)
   ↓ appears in 2+ companies
Master Mind promotion (fund-level pattern)
   ↓ becomes permanent rule
Framework codification (added to ANALYSIS_FRAMEWORK.md)
```

Learning rules auto-generated when the same correction type appears 3+ times. Codification candidates surfaced in the Operator Center Learning tab. Rules have `last_triggered` and `trigger_count` metadata for decay tracking.
