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

## 6. Metric Definitions Reference

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

### Collection Rate
**Formula:** Collected till date / Purchase Value
**Scope:** Monthly (for trend), cumulative (for total)
**Denominator:** Purchase Value (face value), not Purchase Price (funded amount)

### HHI (Herfindahl-Hirschman Index)
**Formula:** Sum of (market share)^2 across all groups/products
**Interpretation:** < 1,500 = unconcentrated, 1,500-2,500 = moderate, > 2,500 = highly concentrated
**Time Series:** Computed across multiple snapshots to detect concentration trends

### Expected Loss (EL)
**Formula:** PD x LGD x EAD
**PD (Probability of Default):** % of completed deals with denial/charge-off rate > threshold (Klaim: >1% denial; SILQ: DPD > 90)
**LGD (Loss Given Default):** (Denied - Provisions - Recovery) / Denied for defaulted deals
**EAD (Exposure at Default):** Outstanding amount on active deals
