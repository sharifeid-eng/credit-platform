#!/usr/bin/env python3
"""
Seed Tamara Investment Thesis
===============================
Creates ``data/Tamara/mind/thesis.json`` with an initial pillar set tied to
metric_keys that the quarterly investor pack pipeline produces (via
``build_thesis_metrics_from_pack`` in ``core/analysis_tamara.py``).

Run once to initialize. Idempotent: re-running DOES reset the pillar set
but preserves `created_at` on existing pillars. The thesis_log.jsonl keeps
an immutable trail of every save.

Usage:
    python scripts/seed_tamara_thesis.py [--force]
"""

import argparse
import sys
import uuid
from pathlib import Path

# Ensure project root on path for core imports when running as a script
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.mind.thesis import InvestmentThesis, ThesisPillar, ThesisTracker  # noqa: E402


# Pillar specification — 8 pillars spanning profitability, credit discipline,
# growth, and unit economics. Each pillar points at a metric_key emitted by
# core.analysis_tamara.build_thesis_metrics_from_pack().
PILLARS_SPEC = [
    {
        "claim": "Tamara maintains statutory profitability (IFRS net profit > $0 monthly).",
        "metric_key": "cons_statutory_net_profit",
        "threshold": 0.0,
        "direction": "above",
        "conviction_score": 75,
        "notes": "IFRS Net Profit turned positive in 2025 and has compounded. Drop below 0 = thesis regression.",
    },
    {
        "claim": "Contribution margin (Mgmt view) stays ≥ 3.5% of GMV.",
        "metric_key": "cons_contribution_margin_pct",
        "threshold": 0.035,
        "direction": "above",
        "conviction_score": 70,
        "notes": "CM% captures unit-economic health. Mar-26 was 4.49%. Drop below 3.5% signals pricing or loss erosion.",
    },
    {
        "claim": "EBTDA stays positive every month.",
        "metric_key": "cons_ebtda_latest",
        "threshold": 0.0,
        "direction": "above",
        "conviction_score": 70,
        "notes": "Operating leverage has been intact at meaningful positive EBTDA in every quarter since H2 2025.",
    },
    {
        "claim": "GMV YTD is within 5% of base-case budget (actual >= 95% of budget).",
        "metric_key": "ytd_gmv_vs_budget_pct",
        "threshold": -0.05,
        "direction": "above",
        "conviction_score": 65,
        "notes": "Q1-2026 was +7.9% above budget. A slip to -5% triggers weakening; -10% is structural concern.",
    },
    {
        "claim": "Operating revenue YTD is within 10% of budget (actual >= 90% of budget).",
        "metric_key": "ytd_revenue_vs_budget_pct",
        "threshold": -0.10,
        "direction": "above",
        "conviction_score": 65,
        "notes": "Revenue growth has exceeded budget in Q1-2026 by 16%. Falling short signals take-rate or volume miss.",
    },
    {
        "claim": "ECL coverage ratio stays ≥ 2.5% of gross AR (reserve adequacy).",
        "metric_key": "cons_ecl_coverage_pct",
        "threshold": 0.025,
        "direction": "above",
        "conviction_score": 60,
        "notes": "Currently 3.63%. Below 2.5% on an expanding AR book implies under-reserving relative to realized loss curves.",
    },
    {
        "claim": "LTV/CAC ratio stays ≥ 8x (long-run unit economics intact).",
        "metric_key": "cons_ltv_cac",
        "threshold": 8.0,
        "direction": "above",
        "conviction_score": 65,
        "notes": "Mar-26 at 32x — very strong. Below 8x would signal CAC inflation or retention erosion; below 5x is thesis-breaking.",
    },
    {
        "claim": "Profit Bearing GMV (BNPL+ Murabaha) share of total GMV ≥ 15%.",
        "metric_key": "cons_profit_bearing_gmv_pct",
        "threshold": 0.15,
        "direction": "above",
        "conviction_score": 55,
        "notes": "BNPL+ is the new revenue-per-GMV lever. Share ~22% at Mar-26. Drop below 15% signals growth engine stall.",
    },
]


def build_thesis(preserve_existing=True):
    """Construct an InvestmentThesis. If an existing thesis is on disk and
    ``preserve_existing`` is True, preserve each pillar's created_at so the
    log shows continuity — only thresholds/claims/conviction_scores get
    refreshed on re-seed."""
    tracker = ThesisTracker(company="Tamara", product="all")
    existing = tracker.load()
    existing_by_key = {}
    if existing and preserve_existing:
        for p in existing.pillars:
            if p.metric_key:
                existing_by_key[p.metric_key] = p

    pillars = []
    for spec in PILLARS_SPEC:
        prior = existing_by_key.get(spec["metric_key"])
        pillar_id = prior.id if prior else f"tamara_{spec['metric_key']}_{uuid.uuid4().hex[:6]}"
        created_at = prior.created_at if prior else ""
        pillars.append(
            ThesisPillar(
                id=pillar_id,
                claim=spec["claim"],
                metric_key=spec["metric_key"],
                threshold=spec["threshold"],
                direction=spec["direction"],
                conviction_score=spec["conviction_score"],
                created_at=created_at,
                last_checked=(prior.last_checked if prior else ""),
                last_value=(prior.last_value if prior else None),
                status=(prior.status if prior else "holding"),
                notes=spec["notes"],
            )
        )

    thesis = InvestmentThesis(
        company="Tamara",
        product="all",
        title="Tamara BNPL — Credit + Profitability Thesis (2026)",
        pillars=pillars,
        status="active",
        created_at=(existing.created_at if existing else ""),
        version=((existing.version if existing else 0) + 1),
    )
    return tracker, thesis


def main():
    parser = argparse.ArgumentParser(description="Seed or refresh the Tamara investment thesis.")
    parser.add_argument("--force", action="store_true",
                        help="Force-overwrite existing pillars, DISCARDING prior created_at and status.")
    args = parser.parse_args()

    tracker, thesis = build_thesis(preserve_existing=not args.force)
    action = "refresh" if tracker.load() else "seed"
    tracker.save(thesis, change_reason=f"Tamara thesis {action}: {len(thesis.pillars)} pillars")

    print(f"[thesis] {action}: {len(thesis.pillars)} pillars written to {tracker._thesis_path}", file=sys.stderr)
    for p in thesis.pillars:
        direction_word = {"above": ">=", "below": "<=", "stable": "~="}[p.direction]
        print(f"  [{p.status:>13}] {p.metric_key:<35} {direction_word} {p.threshold}  (conv={p.conviction_score})", file=sys.stderr)
    print(f"[thesis] version: {thesis.version}  conviction: {thesis.conviction_score}/100", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
