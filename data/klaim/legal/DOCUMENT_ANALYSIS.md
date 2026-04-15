# Klaim Facility — Legal Document Analysis
**Date:** 2026-04-07
**Documents reviewed:**
1. Master Murabaha Agreement (MMA) — 130 pages, dated 10 February 2026
2. Master Receivables Purchase Agreement (MRPA) — 60 pages, dated 10 February 2026

## 1. Facility Overview

| Field | Value | Source |
|-------|-------|--------|
| **Facility Type** | Shariah-compliant Murabaha (revolving) | MMA, page 1 |
| **Facility Limit** | USD 15,000,000 | MRPA: Maximum Credit Limit |
| **Currency** | AED (eligibility requirement) | MRPA: Eligibility Criteria (b)(i) |
| **Effective Date** | 10 February 2026 | Both documents |
| **Governing Law** | ADGM Courts (Abu Dhabi Global Markets) | MMA, Article 34-35 |
| **Parties** | Klaim Receivable Purchase SPV 4 Limited (Company), Klaim Holdings Limited (Parent), ACP Shariah Financing Fund L.P. (Financier/Servicer), Klaim Kapital Technologies Limited (Seller/Sub-Servicer) | MMA Schedule 1; MRPA page 1 |

## 2. Borrowing Base Formula

**BB = (Adjusted Pool Balance + Cash Collateral) x Advance Rate (90%)**

Where **Adjusted Pool Balance** = OPB of Eligible Receivables, reduced by:
- (a) OPB of Eligible Receivables breaching **Concentration Limits**
- (b) OPB where payment **91+ days unpaid** after Invoice Date
- (c) All **Dilutions** (defective services, cancellations, setoffs)
- (d) OPB subject to **Dispute or Adverse Claim**

**Cash Collateral** = principal collections in Collection Account (net of accrued Murabaha Profit), subject to first-ranking security.

**BB Calculation Dates:** 1st and 15th Business Day of each month (and daily during a Deficiency Remedy Period).

**BB Holiday Period:** First 5 months from agreement date (until ~10 July 2026) — no BB cure obligation.

## 3. Eligibility Criteria

### From MRPA — Eligible Receivable requirements:
| # | Criterion | Value/Requirement |
|---|-----------|-------------------|
| 1 | Currency | AED only |
| 2 | Single receivable size | OPB <= **0.5%** of aggregate Eligible OPB |
| 3 | Per-debtor credit limit | <= **USD 15,000,000** |
| 4 | Services rendered | Yes |
| 5 | First-ranking security | Duly perfected |
| 6 | No prior sale/disposal | Clean |
| 7 | Debtor is Eligible Debtor | On approved list or Investment Agent approved |
| 8 | Debtor incorporated in UAE | Yes |
| 9 | Free assignment | No further consent needed |
| 10 | Arm's length | Full market value |
| 11 | No disputes/adverse claims | Clean |
| 12 | Standard form claim | Per Customer's standard |

### From MMA — Ineligibility deductions:
| Deduction | Threshold | Source |
|-----------|-----------|--------|
| **Aging** | Unpaid **91+ days** after Invoice Date | MMA Art. 20 (Adjusted Pool Balance (b)) |
| **Concentration breaches** | See Section 4 below | MMA Art. 20 (Adjusted Pool Balance (a)) |
| **Dilutions** | All dilutions deducted | MMA Art. 20 (Adjusted Pool Balance (c)) |
| **Disputes** | All disputed amounts | MMA Art. 20 (Adjusted Pool Balance (d)) |

## 4. Concentration Limits

| Limit | Threshold | Source |
|-------|-----------|--------|
| Single Eligible Receivable | **10%** of aggregate Eligible OPB | MRPA Conc. Limits (a) |
| Top 10 Largest Eligible Receivables | **50%** of aggregate Eligible OPB | MRPA Conc. Limits (b) |
| Single Customer (originator via KKT) | **10%** of aggregate Eligible OPB | MRPA Conc. Limits (c) |
| Single Non-Eligible Debtor | **10%** of aggregate Eligible OPB | MRPA Conc. Limits (d) |
| Extended Age Receivables (70-90 days) | **5%** of aggregate Eligible OPB | MRPA Conc. Limits (e) |

## 5. Advance Rates

| Category | Rate | Source |
|----------|------|--------|
| **Default (all eligible)** | **90%** | MMA Art. 20 / Definitions |

**Note:** No separate UAE vs Non-UAE rate in documents. All eligible debtors MUST be UAE-incorporated (MRPA Eligible Debtor (c)). The Non-UAE rate in our platform (85%) appears to be from an earlier version or a different interpretation — all receivables in this facility must be from UAE payers.

## 6. Financial Covenants

| Covenant | Threshold | Direction | Frequency | EoD Trigger | Source |
|----------|-----------|-----------|-----------|-------------|--------|
| **PAR30** | **7%** | <= | Monthly | Single breach NOT an EoD (18.3(i)) | MMA 18.2(b)(i) |
| **PAR60** | **5%** | <= | Monthly | Single breach IS an EoD | MMA 18.2(b)(ii) |
| **Collection Ratio** | **25%** | >= | Monthly (per Collection Period) | **2 consecutive** breaches required (18.3(ii)) | MMA 18.2(c) |
| **Paid vs Due** | **95%** | >= | Monthly | **2 consecutive** breaches required (18.3(iii)) | MMA 18.2(d) |
| **Cash Balance (Company)** | **3.0x** | >= | Cash / max(last month burn, 3M avg burn) | Single breach is EoD | MMA 18.2(a) |
| **Cash Balance (Parent)** | **3.0x** | >= | Same formula as Company, consolidated | Single breach is EoD | MMA 18.2(e) |

### Covenant definitions:
- **PAR30** = OPB with instalment **>30 days past due** / OPB of all Eligible Receivables (excl. written-off)
- **PAR60** = OPB with instalment **>60 days past due** / OPB of all Eligible Receivables (excl. written-off)
- **Collection Ratio** = Collections received in period / OPB at **start** of period
- **Paid vs Due** = Collections on receivables due in period / Receivables that became due in period
- **Cash Balance** = Cash / max(last month Net Cash Burn, 3M avg Net Cash Burn)

## 7. Weighted Average Life Test

| Parameter | Value | Source |
|-----------|-------|--------|
| WAL threshold | **70 days** | MMA Art. 21.1 |
| Extended age carve-out | Age 70-90 days, max **5%** of Eligible OPB | MMA Art. 21.2 |
| WAL formula | Sum(OPB_i x Age_i) / Total OPB (all receivables + Repaid Amounts) | MMA Art. 21.1 |
| Age definition | Days since **claim submission date** (Repaid Amounts = zero days) | MRPA Exhibit A |

## 8. Events of Default (MMA Article 22)

| Event | Cure Period | Severity |
|-------|------------|----------|
| Non-payment | 5 Business Days (if accidental/technical) | Payment |
| Financial covenant breach | Per Section 18.3 rules above | Covenant |
| Other obligation breach | 15 Business Days (if curable) | Covenant |
| Misrepresentation | None | Covenant |
| Cross-default (>USD 500K) | None | Cross-default |
| Insolvency | None | MAC |
| Insolvency proceedings | None | MAC |
| Creditors' process (>USD 500K) | 15 Business Days | Operational |
| Unlawfulness/invalidity | None | Operational |
| Cessation of business | None | Operational |
| Change of management | 30 days | Operational |
| Change in ownership | None | MAC |
| Audit qualification | None | Operational |
| Expropriation (>USD 250K) | None | MAC |
| Litigation (>USD 500K) | None | Operational |
| Material adverse change | None | MAC |
| BB Deficiency not cured | 15 Business Days (Remedy Period) | Covenant |

## 9. Reporting Requirements (MMA Article 17)

| Report | Frequency | Deadline | Source |
|--------|-----------|----------|--------|
| Compliance Certificate | Quarterly | With financial statements | MMA 17.3 |
| Annual audited financials | Annual | 120 days (180 for FY2025) | MMA 17.2 / MRPA Exhibit D (r)(i) |
| Quarterly unaudited financials | Quarterly | 30 days after quarter-end | MRPA Exhibit D (r)(ii) |
| Monthly bank statements | Monthly | 15 Business Days after month-end | MMA 17.5 |
| Borrowing Base Certificate | Semi-monthly | 1st and 15th Business Day | MMA 20.2 |
| Borrowing Base Report | Semi-monthly | With BB Certificate | MMA 20.2 |
| Management meetings | Quarterly | Within 15 days of quarter-end | MRPA Exhibit D (r)(v) |
| Default notification | Ad hoc | Promptly upon awareness | MMA 17.8 |

## 10. Approved Account Debtors (13 entities)

| Debtor | Jurisdiction | Expected Payment |
|--------|-------------|-----------------|
| Abu Dhabi National Insurance Co. | UAE | 30-120 days |
| Almadallah Healthcare Management FZ CO | UAE | 30-120 days |
| Gulf Insurance Group (Gulf) B.S.C. | UAE | 30-90 days |
| National Health Insurance Company - Daman (PJSC) | UAE | 30-120 days |
| FMC Network UAE Management Consultancy LLC (TPA) | UAE | 30-150 days |
| MedNet UAE FZ LLC | UAE | 30-120 days |
| NAS Neuron Health Services LLC | UAE | 30-150 days |
| Neuron LLC | UAE | 30-120 days |
| NEXtCARE Claims Management LLC | UAE | 30-150 days |
| National General Insurance Co. (PJSC) | UAE | 30-90 days |
| Sukoon Insurance P.J.S.C. | UAE | 30-90 days |
| American Life Insurance Company | UAE | 30-90 days |
| Emirates Group | UAE | 30-90 days |

## 11. Payment Waterfall

**Normal Operations:**
1. Agent fees and expenses
2. Accrued Murabaha profit (interest equivalent)
3. Principal repayment
4. Residual to Company/Seller

**Upon Event of Default:**
1. Agent fees and expenses
2. All outstanding principal + accrued profit
3. Breakage costs and make-whole amounts

**Deferred Payment Schedule (MMA Schedule 6):** 16 quarterly installments of ~$488K-$498K profit, plus a final balloon of $15.17M on 2030-02-01.

---

## 12. CRITICAL DISCREPANCIES: Document vs Platform Hardcodes

| Parameter | Document Value | Platform Hardcode | Status | Impact |
|-----------|---------------|-------------------|--------|--------|
| **Aging cutoff** | **91 days** | 365 days | **MAJOR DISCREPANCY** | Platform is far too lenient — should exclude 91+ day receivables from BB, not 365+ |
| **WAL threshold** | **70 days** | 60 days | **DISCREPANCY** | Platform is too strict (60d vs 70d). WAL test would fail more often than contractually required |
| **Non-UAE advance rate** | N/A (all debtors must be UAE) | 85% | **INCORRECT** | No Non-UAE rate exists — eligibility requires UAE-incorporated debtors |
| **Advance Rate** | 90% | 90% | MATCH | Correct |
| **Single receivable conc.** | 10% | 0.5% | **NEEDS CLARIFICATION** | 0.5% is the eligible receivable SIZE cap; 10% is the concentration limit. Both exist. Platform uses 0.5% which is the more conservative test. |
| **Top 10 conc.** | 50% | 50% | MATCH | Correct |
| **Single customer conc.** | 10% | 10% | MATCH | Correct |
| **Single payer conc.** | 10% (non-eligible debtor) | 10% | MATCH | Correct |
| **Extended age conc.** | 5% | 5% | MATCH | Correct |
| **PAR30** | 7% | 7% | MATCH | Correct |
| **PAR60** | 5% | 5% | MATCH | Correct |
| **Collection Ratio** | 25% | 25% | MATCH | Correct |
| **Paid vs Due** | 95% | 95% | MATCH | Correct |
| **Cash Balance** | 3.0x | 3.0 | MATCH | Correct |
| **PAR30 EoD** | Single breach NOT an EoD | Treated as EoD | **DISCREPANCY** | Platform shows breach but document allows one-off |
| **Coll/PvD EoD** | 2 consecutive breaches needed | Single breach treated as EoD | **DISCREPANCY** | Platform doesn't track consecutive breach logic |
| **BB calc frequency** | 1st and 15th of month | Continuous | **NUANCE** | Platform computes on-demand; should note contractual dates |
| **BB Holiday Period** | First 5 months (until ~Jul 2026) | Not implemented | **GAP** | Platform should suppress BB deficiency alerts before Jul 2026 |

## 13. Questions for Counsel

### Priority 1 — Clarifications needed for accurate platform implementation:

1. **Aging cutoff discrepancy (91 days vs 365 days):** The MMA Adjusted Pool Balance definition deducts receivables "unpaid for 91 days or more after the Invoice Date." However, Klaim's healthcare receivables often have expected payment timelines of 120-150 days (per the Account Debtor table). Does the 91-day cutoff apply from invoice date or from expected payment date? If from invoice date, this seems inconsistent with the expected payment terms of 30-150 days — many receivables would become ineligible before they're even expected to be paid. Please confirm the intended interpretation.

2. **Single receivable: two thresholds exist.** The Eligible Receivable definition caps a single receivable at 0.5% of aggregate OPB (eligibility gate), while Concentration Limits cap it at 10% (BB deduction). Are both applied? Is the 0.5% applied first (to determine eligibility) and then the 10% applied to the eligible pool (for BB deduction)? Or does only one apply in practice?

3. **"Age" definition**: MRPA defines Age as "days elapsed since the claim submission date." MMA uses "Invoice Date" for the 91-day ineligibility. Are these the same date? In healthcare factoring, the claim submission date and invoice date may differ.

4. **PAR definition basis**: MMA defines PAR as "instalment more than 30/60 days past due." For healthcare receivables, there are no formal "instalments" — the entire claim is either paid or pending. Should PAR be calculated as receivables with Age > (expected payment days + 30/60 days)? Or strictly as receivables > 30/60 days past the Invoice Date?

5. **Monthly Denial Rate**: The MRPA references a "Monthly Denial Rate Breach" as a purchase condition (1(d)(x)). The MMA should define this threshold — can you confirm it is 10% and clarify: 10% of what (new denials in the month / total OPB? or cumulative denials / total originated?)

### Priority 2 — Platform enhancement considerations:

6. **Consecutive breach logic**: The MMA allows Collection Ratio and Paid vs Due to breach once without triggering an EoD — only 2 consecutive breaches trigger. Should we implement breach streak tracking? This would require storing prior period compliance status.

7. **BB Holiday Period**: Should the platform suppress BB deficiency alerts until ~10 July 2026? Or show them as informational only?

8. **Parent Cash Balance covenant**: Do we have access to Parent (Klaim Holdings) cash position data to compute this? If not, this covenant should be marked as "requires manual input."

9. **Extended Age Receivables and WAL interaction**: The WAL test has an alternative satisfaction path via the 5% Extended Age carve-out. Should the platform implement this dual-path logic, or just show WAL and let the analyst assess?

10. **Deferred Payment Schedule**: Should the platform track the 16 quarterly profit installments and the final balloon? This could be a reporting calendar feature.

### Priority 3 — Additional documents that may be relevant:

11. **Subordinated Qard Al Hassan Agreement**: Referenced in MMA 8.3 as the mechanism for Parent to inject capital to cure BB deficiency. Having this would help model the cure waterfall.

12. **Security Agreement / Deed of Charge**: References the first-ranking security over Collection Account. May contain account control details.

13. **Aggregator Receivables Purchase Agreement**: Governs KKT's purchase of receivables from Customers (healthcare providers). May contain originator-level eligibility criteria we're not capturing.

14. **Fee Letter**: Contains the actual Murabaha profit rate (interest equivalent) which would help validate the deferred payment schedule.
