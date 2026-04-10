"""
Seed the MasterMind with institutional knowledge extracted from:
  - CLAUDE.md (architectural decisions, analytical design decisions, data caveats)
  - core/ANALYSIS_FRAMEWORK.md (core principles, framework evolution)
  - tasks/lessons.md (accumulated lessons learned)

Run once to populate data/_master_mind/ with initial entries.
Idempotent: clears existing JSONL files before seeding to avoid duplicates.
"""

import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.mind.master_mind import MasterMind

def main():
    mind = MasterMind()

    # Clear existing JSONL files to make this idempotent
    for jsonl_file in mind.base_dir.glob("*.jsonl"):
        jsonl_file.write_text("", encoding="utf-8")
    print(f"Cleared existing JSONL files in {mind.base_dir}")

    # ── 1. Analytical Preferences (from CLAUDE.md architectural decisions) ──

    preferences = [
        # Denominator discipline
        ("PAR denominator: active outstanding for Tape Analytics, eligible outstanding for Portfolio Analytics. "
         "Lifetime rates live in Loss Waterfall as Gross/Net Default Rate -- different metric, different location.",
         "CLAUDE.md analytical design decisions"),

        ("Completed-only metrics for margins and returns. Never include active deals in margin calculations. "
         "Outstanding-based metrics for ageing and health (not face value).",
         "CLAUDE.md analytical design decisions"),

        ("Separation principle: clean portfolio (active + normal completed) used for performance metrics; "
         "loss portfolio (denial >50% PV for Klaim, charged-off for SILQ) isolated for attribution analysis.",
         "CLAUDE.md analytical design decisions"),

        ("Denominator discipline: every metric that expresses a rate, ratio, or percentage must declare "
         "whether its base is total, active, or eligible. See ANALYSIS_FRAMEWORK.md Section 6.",
         "CLAUDE.md analytical design decisions"),

        ("Three clocks: origination age, contractual DPD, operational delay. When onboarding a new asset class, "
         "the first analytical decision is which clock drives delinquency.",
         "CLAUDE.md analytical design decisions"),

        ("Collection rate = GLR (all cash collected / face value). CRR (capital recovery = principal collected / funded) "
         "shown separately in Returns tab. Never conflate the two.",
         "CLAUDE.md analytical design decisions"),

        ("PAR without contractual benchmarks: hide (graceful degradation), not estimate. "
         "Exception: Option C (empirical curves from 50+ completed deals) with explicit 'Derived' labeling.",
         "CLAUDE.md analytical design decisions"),

        # Data caveats
        ("Actual IRR for owner column in Mar 2026 Klaim tape has garbage data (mean ~2.56e44). "
         "Excluded from all analysis.",
         "CLAUDE.md data caveats"),

        ("filter_by_date() only filters deal selection by origination date. It does NOT adjust balance columns "
         "(collected, denied, outstanding). These always reflect the tape snapshot date.",
         "CLAUDE.md architectural decisions"),

        ("AI endpoints blocked on backdated views (as_of_date < snapshot_date). Balance metrics would be misleading "
         "(inflated collection rates, understated outstanding).",
         "CLAUDE.md architectural decisions"),

        ("Collection curves aggregate view removed from dashboard because it blends vintages at different life stages, "
         "making it misleading for IC audiences. Per-vintage collection speed in Cohort table instead.",
         "CLAUDE.md architectural decisions"),

        ("Column availability drives feature visibility. Features gracefully degrade (hidden, not estimated) on older tapes. "
         "Frontend checks .available flag and hides sections entirely -- no estimates, no placeholders.",
         "CLAUDE.md architectural decisions"),

        ("Confidence grading: A (observed from validated data), B (inferred from balance changes or cross-snapshot), "
         "C (derived from empirical patterns or models). Always classify new metrics.",
         "ANALYSIS_FRAMEWORK.md Section 6"),

        ("Always show PAR trend direction, not just current level. "
         "PAR 30+ is a key IC metric -- display with balance amount at risk and trend arrow.",
         "klaim_session_2026-03"),

        # From lessons.md
        ("Summary field names must be canonical across all companies: total_purchase_value, total_deals, "
         "total_collected, collection_rate. Domain-specific names (e.g. total_disbursed) must also return the canonical alias.",
         "lessons.md 2026-04-07"),

        ("When a metric has different semantic meaning across companies (e.g. Tamara's total_purchase_value is "
         "outstanding AR not originated), pass label overrides and exclude from aggregate stats.",
         "lessons.md 2026-04-09"),

        ("Never derive CSS grid column count from async data that loads incrementally. Use fixed column count "
         "(e.g. repeat(5, 1fr)) so layout is stable from first render.",
         "lessons.md 2026-04-01"),

        ("Data preparation scripts must log every extraction attempt with success/failure and row counts. "
         "Distinguish 'data not available' (no source) from 'data extraction failed' (parser error).",
         "lessons.md 2026-04-09"),
    ]

    for content, source in preferences:
        mind.record_analytical_preference(content, source=source)
    print(f"Seeded {len(preferences)} analytical preferences")

    # ── 2. IC Norms ──

    ic_norms = [
        ("PAR 30+ above 5% triggers watchlist discussion at IC.", "credit_quality"),
        ("All memos must have an explicit stress scenario section -- IC expects to see "
         "downside analysis, not just base case.", "reporting"),
        ("Concentration risk (HHI) must be flagged when above moderate threshold (1,500). "
         "Single-name concentration above 10% requires IC disclosure.", "concentration"),
        ("Every executive summary must end with a bottom line containing specific diligence items "
         "for IC to act on -- not vague recommendations.", "reporting"),
        ("Covenant headroom below 20% of trigger level should be flagged as 'approaching breach' "
         "with projected breach date when trend is available.", "covenants"),
        ("Net loss rate above 3% for consumer lending or 5% for factoring is a critical finding.", "credit_quality"),
        ("Recovery rate below 30% post-default warrants a deep dive into loss categorization.", "credit_quality"),
        ("Tape Analytics is retrospective (IC-ready analysis). Portfolio Analytics is live monitoring "
         "(facility-grade). Never mix the two audiences in a single view.", "reporting"),
        ("When PAR is derived from empirical benchmarks (Option C), it must be explicitly labeled "
         "'Derived from historical patterns' -- IC needs to know the confidence level.", "credit_quality"),
        ("Assessment badges follow a 5-level scale: Healthy, Acceptable, Warning, Critical, Monitor. "
         "Use consistently across all companies and reports.", "reporting"),
    ]

    for content, category in ic_norms:
        mind.record_ic_norm(content, category=category)
    print(f"Seeded {len(ic_norms)} IC norms")

    # ── 3. Framework Evolution ──

    framework_evolutions = [
        ("Added 5-level analytical hierarchy (L1 Size, L2 Cash Conversion, L3 Credit Quality, "
         "L4 Loss Attribution, L5 Forward Signals). All metrics must map to exactly one level.",
         "Need a systematic way to organize 40+ metrics. IC kept asking 'what level of concern is this?' "
         "The hierarchy provides a natural escalation path.",
         "2026-04-06"),

        ("Added Denominator Discipline section (Section 6). Three denominators: total, active, eligible.",
         "PAR was being computed with inconsistent denominators across Tape and Portfolio views. "
         "Active PAR 30+ showed 46% (alarming) while Lifetime was 3.6% (sensible). "
         "Active outstanding was only 8% of total originated, inflating the ratio.",
         "2026-04-01"),

        ("Added Three Clocks section (Section 7). Origination age, contractual DPD, operational delay.",
         "SILQ onboarding revealed that forcing contractual DPD on Klaim (insurance claims) produced "
         "false PAR readings. Insurance companies process claims on their own timeline -- "
         "delinquency is operational delay, not a missed payment.",
         "2026-04-06"),

        ("Added Collection Rate Disambiguation (Section 8). GLR vs CRR vs ERR vs CCR.",
         "Analyst confusion between collection rate (GLR) and capital recovery (CRR). "
         "GLR can look healthy (90%+) while CRR reveals capital erosion if deals purchased at premium.",
         "2026-04-06"),

        ("Added Separation Principle (Section 5). Clean portfolio vs loss portfolio.",
         "A few large fully-denied Klaim deals distorted portfolio-level collection rates and margins. "
         "Ejari framework demonstrated the principle: 32 write-off loans excluded from all performance sheets.",
         "2026-04-05"),

        ("Added CDR/CCR conditional rates. Annualized by vintage age to strip out maturity effects.",
         "Cumulative default rates unfairly penalize older vintages that have had more time to accumulate defaults. "
         "Conditional monthly rates normalize by exposure period.",
         "2026-04-08"),

        ("Added Compute Function Registry (Section 12) and Column-to-Feature Dependency Map (Section 13).",
         "Framework slash commands needed a machine-readable registry to verify coverage. "
         "Manual cross-referencing was error-prone during audits.",
         "2026-04-06"),

        ("Established data room ingestion as third pattern: ETL script -> JSON -> parser -> dashboard.",
         "Tamara had ~100 files across PDF, Excel, and mixed formats. Neither tape nor ODS workbook pattern fit. "
         "The three-layer architecture (ETL once, serve fast) solved the performance problem.",
         "2026-04-09"),

        ("Added graceful degradation as a core principle. Hide when unavailable, never estimate without labeling.",
         "Mar 2026 tape added 35 new columns. Features that depend on these columns must check availability "
         "and return available:False on older tapes. Frontend hides sections entirely.",
         "2026-04-01"),
    ]

    for change, reason, date in framework_evolutions:
        mind.record_framework_evolution(change, reason=reason, date=date)
    print(f"Seeded {len(framework_evolutions)} framework evolution entries")

    # ── 4. Cross-Company Patterns ──

    cross_company_patterns = [
        ("Healthcare factoring (Klaim) uses operational delay clock, not contractual DPD. "
         "Insurance companies process claims on their own timeline. 'Delinquency' = collection behind "
         "expected timeline, not a missed payment.",
         ["Klaim"],
         "Klaim onboarding: PAR requires Expected till date or empirical benchmarks"),

        ("POS lending (SILQ) uses contractual DPD clock with Repayment_Deadline column. "
         "Three product types: BNPL, RBF, RCL (Revolving Credit Line). "
         "Consumer credit risk drives defaults, not operational delays.",
         ["SILQ"],
         "SILQ onboarding: standard DPD-based PAR computation"),

        ("BNPL (Tamara) uses mixed DPD -- 120 days for covenant triggers, 90 days for write-off. "
         "Two geographies (KSA/UAE) with separate securitization facilities. "
         "Saudi Arabia's first fintech unicorn ($1B valuation, 20M+ users).",
         ["Tamara"],
         "Tamara onboarding: data room ingestion from ~100 source files"),

        ("Ejari RNPL is a pre-computed summary -- no raw loan tape, parse ODS workbook only. "
         "12 structured sections extracted once, rendered as read-only dashboard.",
         ["Ejari"],
         "Ejari onboarding: analysis_type=ejari_summary bypasses tape loading"),

        ("KSA-based companies (Tamara, SILQ) both operate in SAR. "
         "UAE-based companies (Klaim, Tamara UAE) operate in AED. "
         "Currency normalization to USD required for cross-company aggregation.",
         ["Tamara", "SILQ", "Klaim"],
         "Currency system: per-product config.json with FX normalization"),

        ("All companies benefit from the same 5-level analytical hierarchy (L1-L5), "
         "but the specific metrics at each level are asset-class-dependent. "
         "Overview page follows consistent section structure: Main KPIs -> Credit Quality -> Leading Indicators.",
         ["Klaim", "SILQ", "Ejari", "Tamara"],
         "Overview standardization: bespoke KPIs within consistent sections"),

        ("Separation principle applies across all asset classes but with different default definitions: "
         "Klaim = denial >50% of PV, SILQ = charged-off loans, Tamara = DPD >90 days write-off, "
         "Ejari = 32 identified write-off loans.",
         ["Klaim", "SILQ", "Ejari", "Tamara"],
         "Each asset class has its own loss event definition"),

        ("Data ingestion pattern determines dashboard complexity: "
         "raw tape (Klaim, SILQ) = full live computation; "
         "pre-computed summary (Ejari) = parse-and-render; "
         "data room ingestion (Tamara) = ETL -> JSON -> enriched render.",
         ["Klaim", "SILQ", "Ejari", "Tamara"],
         "Three data ingestion patterns now supported"),
    ]

    for pattern, companies, evidence in cross_company_patterns:
        mind.record_cross_company_pattern(pattern, companies=companies, evidence=evidence)
    print(f"Seeded {len(cross_company_patterns)} cross-company patterns")

    # ── 5. Writing Style ──

    writing_styles = [
        ("AI executive summaries use 3-5 sentence bottom lines with specific diligence items. "
         "Never end with vague recommendations like 'further analysis needed'.",
         "memo_edits"),

        ("Assessment badges follow a 5-level scale: Healthy, Acceptable, Warning, Critical, Monitor. "
         "Each badge maps to a color (green, blue, amber, red, grey).",
         "executive_summary_design"),

        ("Each narrative section should be 2-4 paragraphs with specific numbers -- no vague statements. "
         "Always cite the exact metric value, not 'approximately' or 'around'.",
         "memo_edits"),

        ("Tab insights should be concise one-paragraph analyses (3-5 sentences). "
         "Lead with the most important finding, then context, then implication.",
         "tab_insight_design"),

        ("Use basis points (bps) for spreads and small rate differences. "
         "Use percentages for rates above 1%. Use absolute currency amounts for balances.",
         "analyst_convention"),

        ("When comparing vintages, always state the direction and magnitude of change. "
         "'Mar 2026 vintage collection rate of 92.3% is 340bps above the Dec 2025 vintage (88.9%).'",
         "memo_edits"),

        ("Leading indicators must never be presented as confirmed outcomes. "
         "Use hedging language: 'signals potential', 'may indicate', 'warrants monitoring'.",
         "ANALYSIS_FRAMEWORK.md Section 4"),

        ("AI commentary should follow lagging -> coincident -> leading indicator flow. "
         "Start with what happened, contextualize with current state, flag forward signals.",
         "ANALYSIS_FRAMEWORK.md Section 4"),

        ("Company-specific section guidance for executive summaries: "
         "Klaim (7 sections: Portfolio -> Cohort -> Collection -> Denial -> Recovery -> Concentration -> Forward), "
         "SILQ (6 sections: Portfolio -> Delinquency -> Collections -> Cohorts -> Concentration -> Yield), "
         "Ejari (9 sections: Portfolio -> Cohorts -> Loss -> Roll Rates -> Historical -> Segment -> Credit -> Legal -> Write-offs).",
         "executive_summary_design"),

        ("Never describe a collection rate above 90% as 'concerning' or below 80% as 'acceptable' "
         "without asset-class context. Factoring (Klaim) targets 95%+, BNPL (SILQ/Tamara) tolerates 85-90%.",
         "analyst_convention"),
    ]

    for content, source in writing_styles:
        mind.record_writing_style(content, source=source)
    print(f"Seeded {len(writing_styles)} writing style entries")

    # ── 6. Onboarding Briefs ──

    # Factoring (from Klaim lessons)
    factoring_brief = """# Onboarding Brief: Healthcare Receivables Factoring

*Lessons extracted from Klaim (UAE healthcare claims factoring) onboarding.*

## Asset Class Characteristics
- **What is financed:** Insurance claims purchased at a discount from healthcare providers
- **Obligor:** Insurance companies (not patients)
- **Default event:** Insurance denial of the claim
- **Recovery path:** Resubmission, appeal, partial collection after initial denial
- **Counterparty risk:** Healthcare provider (Group), not borrower

## Clock Selection
- **Use Operational Delay clock**, not contractual DPD
- Insurance companies process claims on their own timeline
- "Delinquency" = collection behind expected timeline, not a missed payment
- PAR requires Expected till date column or empirical benchmarks from completed deals

## Key Metrics
- **Collection Rate = GLR** (all cash collected / face value)
- Capital Recovery (CRR) shown separately in Returns tab
- **Denial = the loss event** (not default in the traditional sense)
- Denial by insurance > 50% of Purchase Value = loss deal (Separation Principle)
- Provisions and denied amounts tracked separately

## Data Caveats
- Discount column values range 1-41%, concentrated at 4-7%
- Actual IRR for owner column may contain garbage data -- always validate before use
- Collection curve columns (Expected/Actual at 30d intervals) only available on newer tapes
- filter_by_date() only filters deal selection, NOT balance columns

## PAR Computation
- Primary method: Expected till date shortfall-based estimated DPD
- Option C: Empirical benchmarks from 50+ completed deals (labeled "Derived")
- Fallback: available=False (hide, don't estimate)
- Dual denominator: Active PAR (monitoring) and Lifetime PAR (IC headline)

## Lessons Learned
- Always check if summary endpoint passes through all KPI builder fields
- ODS numbers may be comma-formatted strings -- strip commas before conversion
- loader.py file extension broadening can catch config.json -- add exclusion list
"""
    (mind.base_dir / "onboarding" / "factoring.md").write_text(factoring_brief, encoding="utf-8")
    print("Wrote onboarding/factoring.md")

    # BNPL (from Tamara + SILQ lessons)
    bnpl_brief = """# Onboarding Brief: BNPL / POS Lending

*Lessons extracted from Tamara (KSA/UAE BNPL) and SILQ (KSA POS lending) onboarding.*

## Asset Class Characteristics
- **What is financed:** Consumer purchases at point of sale (BNPL, RBF, RCL products)
- **Obligor:** Consumer borrowers
- **Default event:** Loan delinquency (DPD-based), charge-off
- **Recovery path:** Collections, legal enforcement (Najiz process in KSA)
- **Counterparty risk:** Merchant/shop (not insurance company)

## Clock Selection
- **Use Contractual DPD clock** (days past due from repayment deadline)
- SILQ: DPD from Repayment_Deadline column
- Tamara: Mixed DPD -- 120 days for covenant triggers, 90 days for write-off
- Standard DPD buckets: 30+, 60+, 90+, 120+

## Key Metrics
- **PAR directly computable** from DPD columns (unlike factoring)
- Vintage cohort analysis is critical -- BNPL portfolios season quickly
- Covenant triggers typically reference DPD >120 days and dilution rates
- CDR/CCR (conditional rates) strip out maturity effects for fair vintage comparison

## Data Patterns
- SILQ: Multi-sheet Excel workbooks, three product types (BNPL, RBF, RCL)
- Tamara: Data room ingestion (~100 files: vintage cohorts, FDD, investor reports, financial models)
- SILQ loader returns (df, commentary_text) tuple -- always unpack
- Tamara uses ETL -> JSON -> parser pattern (never parse PDFs at runtime)

## Multi-Product Considerations
- SILQ has 3 product types in single tape (Loan_Type column mapped to Product)
- Tamara has 2 geographies (KSA/UAE) as separate products with separate securitization facilities
- KSA companies (SILQ, Tamara KSA) operate in SAR
- Landing page needs carousel for multi-product companies

## Securitization Context
- Tamara KSA: $2.375B (Goldman, Citi, Atlas/Apollo, Morgan Stanley)
- Tamara UAE: $131M (Goldman)
- Covenant compliance monitoring is critical for securitized portfolios
- Trigger levels: L1 (monitoring), L2 (notification), L3 (action required)

## Lessons Learned
- Vintage cohort matrices from external sources need flexible header detection (search first 5 rows)
- HSBC PDF table parsing requires pdfplumber (not PyPDF) for structured tables
- AI Executive Summary context must be wired before marking company "onboarded"
- Showcase tabs should lead with charts (5-6 high-impact visualizations), not tables
- Unicode arrows in print statements crash on Windows cp1252 -- use ASCII equivalents
"""
    (mind.base_dir / "onboarding" / "bnpl.md").write_text(bnpl_brief, encoding="utf-8")
    print("Wrote onboarding/bnpl.md")

    # RNPL (from Ejari lessons)
    rnpl_brief = """# Onboarding Brief: Rent Now Pay Later (RNPL)

*Lessons extracted from Ejari (KSA rent payment financing) onboarding.*

## Asset Class Characteristics
- **What is financed:** Rent payments on behalf of tenants
- **Obligor:** Tenants (consumers)
- **Default event:** DPD-based, with Najiz/legal recovery process
- **Recovery path:** Legal enforcement, Najiz courts (KSA), debt collection
- **Data format:** Pre-computed ODS workbook (no raw loan tape)

## Pre-Computed Summary Pattern
- **analysis_type: "ejari_summary"** bypasses all tape loading and computation
- Single ODS workbook with 13 sheets of pre-computed analysis
- Parser (analysis_ejari.py) reads ODS once, extracts 12 structured sections
- Dashboard (EjariDashboard.jsx) renders parsed data as read-only tabs
- Cached parsing -- ODS parsed once per session

## When to Use This Pattern
- Company provides analysis output, not raw data
- No loan-level tape available for live computation
- Data arrives as a formatted workbook with multiple analysis sheets
- Quick onboarding needed without building a full analysis pipeline

## Dashboard Structure
- 12 tabs: Portfolio Overview, Monthly Cohorts, Cohort Loss Waterfall, Roll Rates,
  Historical Performance, Collections by Month/Origination, Segment Analysis (6 dims),
  Credit Quality Trends, Najiz & Legal, Write-offs & Fraud, Data Notes
- Uses shared KpiCard and ChartPanel components for visual consistency
- DataTable component for ODS tabular data (Ejari-specific)

## Configuration
- hide_portfolio_tabs: true (suppresses Portfolio Analytics in sidebar)
- Sidebar header shows "Analysis" instead of "Tape Analytics"
- Executive Summary always visible (decoupled from hide_portfolio_tabs)
- methodology.json stored as static file in data directory

## Data Parsing Caveats
- ODS numbers are comma-formatted strings ('1,348') -- strip commas before int/float conversion
- odfpy package required in venv for ODS file support
- config.json and methodology.json must be excluded from get_snapshots() discovery
- ODS file must follow YYYY-MM-DD_ naming convention for snapshot date extraction

## Separation Principle
- Ejari demonstrates clean separation: 32 write-off loans excluded from ALL performance sheets
- Write-offs analyzed in dedicated section, preventing contamination of healthy portfolio metrics
- This pattern was generalized to the platform-wide Separation Principle

## Lessons Learned
- load_snapshot() is wrong for ODS -- dispatch to correct loader per analysis_type
- Silent failures from wrong loader swallowed by bare except:pass -- always log errors
- Cache fingerprint must include schema version to avoid serving stale data
"""
    (mind.base_dir / "onboarding" / "rnpl.md").write_text(rnpl_brief, encoding="utf-8")
    print("Wrote onboarding/rnpl.md")

    # ── 7. Run consolidation to generate style guide and consolidated.json ──

    report = mind.consolidate()
    print(f"\nConsolidation complete:")
    for cat, info in report["categories"].items():
        print(f"  {cat}: {info['total_entries']} entries ({info['unique_entries']} unique)")
    print(f"  Cross-company patterns found: {len(report['new_patterns'])}")

    # ── 8. Verify ──

    print(f"\n--- Verification ---")
    total = 0
    for jsonl_file in sorted(mind.base_dir.glob("*.jsonl")):
        lines = [l for l in jsonl_file.read_text(encoding="utf-8").strip().split("\n") if l.strip()]
        total += len(lines)
        print(f"  {jsonl_file.name}: {len(lines)} entries")
    print(f"  Total JSONL entries: {total}")

    onboarding_dir = mind.base_dir / "onboarding"
    briefs = list(onboarding_dir.glob("*.md"))
    print(f"  Onboarding briefs: {len(briefs)} ({', '.join(b.name for b in briefs)})")

    style_guide = mind.base_dir / "style_guide.md"
    if style_guide.exists():
        print(f"  Style guide: generated ({len(style_guide.read_text(encoding='utf-8'))} chars)")

    consolidated = mind.base_dir / "consolidated.json"
    if consolidated.exists():
        print(f"  Consolidated report: generated")

    # Test context retrieval
    ctx = mind.get_context_for_prompt("executive_summary", company="Klaim")
    print(f"\n--- Context Test (executive_summary for Klaim) ---")
    print(f"  Entries returned: {ctx.entry_count}")
    print(f"  Categories: {ctx.categories_included}")
    print(f"  Formatted length: {len(ctx.formatted)} chars")

    print("\nMasterMind seeding complete.")


if __name__ == "__main__":
    main()
