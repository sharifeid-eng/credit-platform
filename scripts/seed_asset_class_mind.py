"""Seed Asset Class Mind with conservative starter entries.

D4 from session 27. Each of the 5 asset classes starts empty; without
seed content, Layer 2.5 is effectively dark on day one. This script
drops 2-3 methodology_note / typical_terms entries per asset class,
drawn ONLY from facts already committed to CLAUDE.md or the platform's
own methodology files — nothing fabricated, no peer benchmarks we can't
cite.

Each seed is tagged with `source: "seed:platform_docs"` so analysts can
see these are starter scaffolding, not analyst-curated knowledge. They
are expected to be refined or replaced as real IC work accumulates.

Idempotent: seeds are skipped if the asset class already has ANY
entries. Re-run any time without duplicating; analyst approvals from
elsewhere (pending_review → approve) are never overwritten.

Usage:
    python scripts/seed_asset_class_mind.py
    python scripts/seed_asset_class_mind.py --force    # re-seed empty classes
    python scripts/seed_asset_class_mind.py --dry-run  # print, don't write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Seed content ─────────────────────────────────────────────────────────────
#
# Every entry MUST be sourced from something already in the repo (CLAUDE.md,
# methodology_*.py, ANALYSIS_FRAMEWORK.md, config.json). No outside claims,
# no benchmark numbers we can't cite back to a file.
#
# Categories used:
#   - methodology_note  : how the platform computes / interprets this class
#   - typical_terms     : commonly-seen facility or product structures
#   - sector_context    : market context drawn from platform content
#
# We deliberately avoid `benchmarks` — any "typical X%" value that isn't
# measured from our own tapes should come from a cited external source via
# the pending-review queue, not a seed script.

_SEEDS: Dict[str, List[Dict[str, Any]]] = {
    "bnpl": [
        {
            "category": "typical_terms",
            "content": (
                "BNPL product tenor spectrum (observed at Tamara): "
                "standard BNPL runs Pi2-Pi6 (2-6 instalments) with typical "
                "ticket sizes up to SAR 5,000, interest-free for the borrower "
                "and merchant-funded. BNPL+ extends tenor to Pi4-Pi24 (4-24 "
                "instalments) at ticket sizes SAR 5,000-20,000 and charges a "
                "Murabaha profit rate in the 21-40% APR range, borrower-paid. "
                "The two products have different underwriting, credit-loss, "
                "and revenue economics — analyse separately where the tape "
                "supports it."
            ),
        },
        {
            "category": "methodology_note",
            "content": (
                "Dilution vs credit loss separation for BNPL: in short-tenor "
                "consumer instalment lending, dilution (refunds, merchant "
                "cancellations, chargebacks) is materially non-zero and "
                "behaves like non-credit shrinkage in the receivable pool. "
                "Treat it as a separate line from DPD-driven default — don't "
                "fold it into gross loss rate. See ANALYSIS_FRAMEWORK.md "
                "Section 9 on dilution framing."
            ),
        },
        {
            "category": "sector_context",
            "content": (
                "BNPL facility structures in MENA (observed from Tamara "
                "investor reporting): KSA-only SPV c.USD 2.375B across 5 "
                "tranches (Goldman, Citi, Apollo / Atlas, Morgan Stanley); "
                "UAE-only SPV c.USD 131M across 2 tranches (Goldman). "
                "KSA and UAE portfolios are legally ring-fenced into "
                "geography-specific SPVs — treat them as independent credit "
                "stories when modelling concentration, covenants, or "
                "dilution."
            ),
        },
    ],

    "pos_lending": [
        {
            "category": "typical_terms",
            "content": (
                "POS lending sub-products (observed at SILQ): "
                "(1) BNPL — consumer instalment at checkout. "
                "(2) RBF (Revenue-Based Financing) — merchant repays as a "
                "percentage of daily receipts, variable tenor. "
                "(3) RCL (Revolving Credit Line) — merchant draws against a "
                "committed facility, repays on demand. "
                "Each has different tenor, repayment cadence, and loss "
                "dynamics — don't blend them in a single cohort table."
            ),
        },
        {
            "category": "methodology_note",
            "content": (
                "Tenor-based cohort analysis matters more for POS lending "
                "than for long-dated credit: the portfolio turns over in "
                "months, so a 12-month vintage window can hide rapid "
                "deterioration in the most recent 2-3 months. Always cut "
                "cohorts by month of origination AND report collection "
                "curves at 30/60/90-day intervals from origination."
            ),
        },
        {
            "category": "sector_context",
            "content": (
                "KSA POS lending regulatory frame: SAMA (Saudi Arabian "
                "Monetary Authority) supervises BNPL and similar POS credit "
                "products. Licensing rules have been tightening since 2023; "
                "any research on SILQ-like operators should check SAMA "
                "guidance on origination and collections practices before "
                "importing benchmarks from unregulated markets."
            ),
        },
    ],

    "rnpl": [
        {
            "category": "typical_terms",
            "content": (
                "RNPL (Rent Now Pay Later) — instalment financing for "
                "tenants to pay annual rent monthly or quarterly. Typical "
                "tenor: 12 months, matching the KSA lease cycle. Recovery "
                "path on default: Najiz (KSA digital legal portal) "
                "eviction + debt-collection pipeline — structurally "
                "different from unsecured consumer credit, because the "
                "landlord's cooperation is often the binding constraint."
            ),
        },
        {
            "category": "methodology_note",
            "content": (
                "For RNPL, credit-quality metrics should be reported "
                "separately by cohort AND by product vintage, because "
                "underwriting and partner-landlord onboarding both evolve "
                "over time. Ejari's dashboard pattern (13-sheet ODS "
                "workbook with dedicated Najiz & Legal and Write-offs & "
                "Fraud sections) is the reference structure — recoveries "
                "are slow and process-heavy, so isolate fraud/anomaly "
                "losses from legitimate credit events when categorising."
            ),
        },
    ],

    "sme_trade_credit": [
        {
            "category": "typical_terms",
            "content": (
                "SME raw-materials trade credit (observed at Aajil): "
                "deals fall into two structural buckets — EMI (equal "
                "monthly instalment, amortising) and Bullet (single "
                "repayment at maturity). Bullet deals are riskier in "
                "practice: at Aajil, 100% of observed write-offs (19 of 19) "
                "came from Bullet deals; EMI write-off count was zero over "
                "the same window. Treat the two as distinct risk classes "
                "even when they sit in the same portfolio."
            ),
        },
        {
            "category": "methodology_note",
            "content": (
                "Customer-type segmentation for SME trade credit: split by "
                "Manufacturer / Contractor / Wholesale Trader. These cohorts "
                "have materially different working-capital cycles and "
                "collateral profiles, and should be reported as separate "
                "concentration buckets (HHI + top-N) rather than pooled. "
                "Industry sector concentration is a secondary cut; customer "
                "type is the primary one."
            ),
        },
        {
            "category": "methodology_note",
            "content": (
                "External reporting-platform alignment: Aajil relies on "
                "Cascade Debt (app.cascadedebt.com) as the investor-reporting "
                "system of record. When validating tape analytics against "
                "Cascade, reconcile on Principal Amount (not outstanding) "
                "for volume and use the realised/principal ratio for "
                "headline collection rate. Small drift (<0.5%) is expected "
                "from rounding and cut-off timing."
            ),
        },
    ],

    # healthcare_receivables already has 3 analyst-approved web_search
    # entries from the session-27 smoke test — seeding one more methodology
    # note to document the payer-tape schema gap that was discovered during
    # the Klaim data-room review.
    "healthcare_receivables": [
        {
            "category": "methodology_note",
            "content": (
                "Account-debtor concentration is structurally unobservable "
                "in healthcare-receivables factoring tapes that don't carry "
                "a payer column: the analyst sees the provider/clinic "
                "group but not which insurance company is on the hook. "
                "Covenants that cap exposure to any single non-eligible "
                "debtor (common in MMA-style facilities) cannot be "
                "validated from tape alone — flag this as a data gap when "
                "evaluating compliance. See Klaim debtor_validation.json "
                "for the observed pattern (143 providers in tape vs 13 "
                "approved insurance payers)."
            ),
        },
    ],
}


def _has_seed_entries(analysis_type: str) -> bool:
    """Return True if any platform-seeded entries exist for this class."""
    from core.mind.asset_class_mind import AssetClassMind

    mind = AssetClassMind(analysis_type)
    existing = mind.list_entries()
    return any(
        (e.metadata or {}).get("source") == "seed:platform_docs"
        for e in existing
    )


def seed_asset_class(
    analysis_type: str,
    entries: List[Dict[str, Any]],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Seed one asset class. Returns the number of entries written."""
    from core.mind.asset_class_mind import AssetClassMind

    if not force and _has_seed_entries(analysis_type):
        print(f"  {analysis_type}: already seeded, skipping "
              f"(use --force to re-seed)")
        return 0

    if dry_run:
        print(f"  {analysis_type}: would write {len(entries)} entries")
        for e in entries:
            print(f"    [{e['category']}] {e['content'][:80]}...")
        return 0

    mind = AssetClassMind(analysis_type)
    written = 0
    for e in entries:
        mind.record(
            category=e["category"],
            content=e["content"],
            metadata={"source": "seed:platform_docs"},
        )
        written += 1
    print(f"  {analysis_type}: wrote {written} entries")
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true",
                        help="Re-seed classes that already have seeded entries")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be written, don't actually write")
    parser.add_argument("--only", metavar="ASSET_CLASS",
                        help="Only seed this one asset class")
    args = parser.parse_args()

    targets = [args.only] if args.only else list(_SEEDS.keys())

    print("Seeding Asset Class Mind (D4)")
    print("=" * 60)

    total_written = 0
    for asset_class in targets:
        if asset_class not in _SEEDS:
            print(f"  {asset_class}: no seed content defined, skipping")
            continue
        total_written += seed_asset_class(
            asset_class, _SEEDS[asset_class],
            force=args.force, dry_run=args.dry_run,
        )

    print("=" * 60)
    action = "Would write" if args.dry_run else "Wrote"
    print(f"{action} {total_written} entries across {len(targets)} asset classes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
