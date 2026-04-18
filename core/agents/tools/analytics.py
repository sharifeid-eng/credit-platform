"""
Analytics Tools — wrap core compute functions for agent use.

Each tool loads its own data, calls the compute function, and returns
a human-readable text string. The agent never sees raw dicts.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.agents.tools import registry
from core.agents.tools._helpers import (
    detect_analysis_type,
    format_number,
    get_currency,
    load_aajil_tape,
    load_silq_tape,
    load_tape,
    safe_get,
)

logger = logging.getLogger(__name__)


# ── Helper: route to correct compute module ──────────────────────────────

def _compute_for_type(analysis_type: str, func_name: str, *args, **kwargs):
    """Dispatch to the correct company-specific compute function."""
    if analysis_type == "silq":
        import core.analysis_silq as mod
    elif analysis_type == "aajil":
        import core.analysis_aajil as mod
    else:
        import core.analysis as mod

    fn = getattr(mod, func_name, None)
    if fn is None:
        return None
    return fn(*args, **kwargs)


# ── Tool implementations ─────────────────────────────────────────────────

def _get_portfolio_summary(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)

    if at in ("ejari_summary", "tamara_summary"):
        # Pre-computed summaries
        if at == "ejari_summary":
            from core.analysis_ejari import parse_ejari_workbook
            from core.loader import get_snapshots
            snaps = get_snapshots(company, product)
            if not snaps:
                return "No snapshots available for this company."
            data = parse_ejari_workbook(snaps[-1]["filepath"])
            overview = data.get("portfolio_overview", {})
            return f"Ejari Portfolio Overview:\n" + "\n".join(
                f"  {k}: {v}" for k, v in overview.items() if not isinstance(v, (list, dict))
            )
        else:
            from core.analysis_tamara import parse_tamara_snapshot
            from core.loader import get_snapshots
            snaps = get_snapshots(company, product)
            if not snaps:
                return "No snapshots available for this company."
            data = parse_tamara_snapshot(snaps[-1]["filepath"])
            kpis = data.get("kpis", {})
            return f"Tamara Portfolio Overview:\n" + "\n".join(
                f"  {k}: {v}" for k, v in list(kpis.items())[:20]
            )

    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
    elif at == "aajil":
        df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)

    config, disp, mult = get_currency(company, product, currency)

    if at == "silq":
        from core.analysis_silq import compute_silq_summary
        s = compute_silq_summary(df, mult, ref_date=as_of_date or sel.get("date"))
    elif at == "aajil":
        from core.analysis_aajil import compute_aajil_summary
        s = compute_aajil_summary(df, mult)
    else:
        from core.analysis import compute_summary
        s = compute_summary(df, config, disp, sel.get("date", ""), as_of_date)

    # Format as readable text
    lines = [f"Portfolio Summary for {company}/{product} (snapshot: {sel.get('filename', 'latest')}, currency: {disp})"]
    for k, v in s.items():
        if isinstance(v, dict):
            lines.append(f"  {k}:")
            for k2, v2 in v.items():
                lines.append(f"    {k2}: {v2}")
        elif isinstance(v, (int, float)):
            lines.append(f"  {k}: {format_number(v)}")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _get_par_analysis(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at not in ("klaim", "silq"):
        return f"PAR analysis not available for analysis_type={at}"

    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)

    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_par
    result = compute_par(df, mult, as_of_date=as_of_date or sel.get("date"))

    if not result.get("available"):
        return "PAR analysis not available for this tape (missing required columns)."

    lines = [f"Portfolio at Risk (PAR) — {company}/{product}"]
    lines.append(f"  Method: {result.get('method', 'unknown')}")

    for level in ["par_30", "par_60", "par_90"]:
        data = result.get(level, {})
        if data:
            pct = format_number(data.get("balance_pct"), is_pct=True)
            bal = format_number(data.get("balance"), is_currency=True, currency=disp)
            cnt = data.get("count", 0)
            lines.append(f"  {level.upper()}: {pct} ({bal} at risk, {cnt} deals)")

    lines.append(f"  Total active outstanding: {format_number(result.get('total_active_outstanding'), is_currency=True, currency=disp)}")
    lines.append(f"  Total active deals: {result.get('total_active_count', 0)}")
    return "\n".join(lines)


def _get_cohort_analysis(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_cohorts
        result = compute_silq_cohorts(df, mult)
    elif at == "aajil":
        df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_aajil import compute_aajil_cohorts
        result = compute_aajil_cohorts(df, mult)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis import compute_cohorts
        # Klaim's compute_cohorts returns a bare list; other branches return dicts
        result = {"cohorts": compute_cohorts(df, mult)}

    cohorts = result.get("cohorts", [])
    if not cohorts:
        return "No cohort data available."

    lines = [f"Vintage Cohort Analysis — {company}/{product} ({len(cohorts)} vintages)"]
    for c in cohorts[:12]:  # Show up to 12 vintages
        # Klaim uses 'month'/'total_deals'; SILQ/Aajil use 'vintage'/'deals' or 'Vintage'/'Deals'
        vintage = c.get("vintage", c.get("Vintage", c.get("month", "?")))
        deals = c.get("deals", c.get("Deals", c.get("total_deals", 0)))
        coll_rate = format_number(c.get("collection_rate", c.get("Collection Rate")), is_pct=True)
        denial_rate = format_number(c.get("denial_rate", c.get("Denial Rate")), is_pct=True)
        lines.append(f"  {vintage}: {deals} deals, collection {coll_rate}, denial {denial_rate}")

    return "\n".join(lines)


def _get_dso_analysis(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)

    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_dso
    result = compute_dso(df, mult, as_of_date=as_of_date or sel.get("date"))

    if not result.get("available"):
        return "DSO analysis not available for this tape."

    lines = [f"Days Sales Outstanding — {company}/{product}"]
    lines.append(f"  DSO Capital (weighted): {result.get('weighted_dso', 'N/A'):.0f} days")
    lines.append(f"  DSO Capital (median): {result.get('median_dso', 'N/A'):.0f} days")
    lines.append(f"  DSO Capital (P95): {result.get('p95_dso', 'N/A'):.0f} days")

    if result.get("dso_operational_weighted"):
        lines.append(f"  DSO Operational (weighted): {result['dso_operational_weighted']:.0f} days")
        lines.append(f"  DSO Operational (median): {result.get('dso_operational_median', 'N/A')}")

    return "\n".join(lines)


def _get_concentration(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_concentration
        result = compute_silq_concentration(df, mult)
    elif at == "aajil":
        df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_aajil import compute_aajil_concentration
        result = compute_aajil_concentration(df, mult)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis import compute_concentration
        result = compute_concentration(df, mult)

    lines = [f"Concentration Analysis — {company}/{product}"]

    # HHI
    hhi = result.get("hhi", {})
    if hhi:
        lines.append(f"  HHI (Group): {hhi.get('group', 'N/A')}")
        lines.append(f"  HHI (Product): {hhi.get('product', 'N/A')}")
        lines.append(f"  HHI Classification: {hhi.get('classification', 'N/A')}")

    # Top groups
    groups = result.get("group", result.get("groups", []))
    if groups:
        lines.append(f"  Top providers ({len(groups)} total):")
        for g in groups[:10]:
            name = g.get("Group", g.get("name", "?"))
            share = format_number(g.get("share", g.get("pct")), is_pct=True)
            lines.append(f"    {name}: {share}")

    return "\n".join(lines)


def _get_returns_analysis(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at != "klaim":
        return f"Returns analysis not available for analysis_type={at}. Only available for Klaim."

    df, sel = load_tape(company, product, snapshot, as_of_date)
    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_returns_analysis
    result = compute_returns_analysis(df, mult)

    s = result.get("summary", {})
    lines = [f"Returns Analysis — {company}/{product}"]
    lines.append(f"  Realised Margin: {format_number(s.get('realised_margin'), is_pct=True)}")
    lines.append(f"  Capital Recovery: {format_number(s.get('capital_recovery'), is_pct=True)}")
    lines.append(f"  Avg Discount: {format_number(s.get('avg_discount'), is_pct=True)}")

    if s.get("has_irr"):
        lines.append(f"  Avg Expected IRR: {format_number(s.get('avg_expected_irr'), is_pct=True)}")
        lines.append(f"  Avg Actual IRR: {format_number(s.get('avg_actual_irr'), is_pct=True)}")

    # Discount bands
    bands = result.get("discount_bands", [])
    if bands:
        lines.append(f"  Discount bands ({len(bands)}):")
        for b in bands[:5]:
            lines.append(f"    {b.get('band', '?')}: margin {format_number(b.get('margin'), is_pct=True)}, {b.get('deals', 0)} deals")

    return "\n".join(lines)


def _get_collection_velocity(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_collections
        result = compute_silq_collections(df, mult)
    elif at == "aajil":
        df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_aajil import compute_aajil_collections
        result = compute_aajil_collections(df, mult)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis import compute_collection_velocity
        result = compute_collection_velocity(df, mult, as_of_date=as_of_date or sel.get("date"))

    monthly = result.get("monthly", [])
    lines = [f"Collection Velocity — {company}/{product}"]
    if monthly:
        lines.append(f"  Monthly data ({len(monthly)} months):")
        for m in monthly[-6:]:  # Last 6 months
            month = m.get("Month", m.get("month", "?"))
            rate = format_number(m.get("collection_rate", m.get("rate")), is_pct=True)
            lines.append(f"    {month}: {rate}")

    lines.append(f"  Avg collection days: {result.get('avg_days', 'N/A')}")
    lines.append(f"  Median collection days: {result.get('median_days', 'N/A')}")
    return "\n".join(lines)


def _get_covenants(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)

    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_covenants
        result = compute_silq_covenants(df, mult, ref_date=as_of_date or sel.get("date"))
    elif at == "klaim":
        df, sel = load_tape(company, product, snapshot, as_of_date)
        config, disp, mult = get_currency(company, product, currency)
        from core.portfolio import compute_klaim_covenants
        result = compute_klaim_covenants(df, mult, ref_date=as_of_date or sel.get("date"))
    elif at == "aajil":
        df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_aajil import compute_aajil_covenants
        result = compute_aajil_covenants(df, mult)
    else:
        return f"Covenants not available for analysis_type={at}"

    covenants = result.get("covenants", [])
    lines = [f"Covenant Compliance — {company}/{product}"]
    for cov in covenants:
        name = cov.get("name", "?")
        actual = cov.get("actual", "?")
        threshold = cov.get("threshold", "?")
        compliant = cov.get("compliant", False)
        status = "PASS" if compliant else "BREACH"
        lines.append(f"  {name}: {actual} vs {threshold} [{status}]")

    return "\n".join(lines)


def _get_group_performance(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at not in ("klaim",):
        return f"Group performance not available for analysis_type={at}"

    df, sel = load_tape(company, product, snapshot, as_of_date)
    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_group_performance
    result = compute_group_performance(df, mult)

    groups = result.get("groups", [])
    lines = [f"Provider Performance — {company}/{product} ({len(groups)} providers)"]
    for g in groups[:15]:
        name = g.get("Group", "?")
        deals = g.get("deals", 0)
        coll = format_number(g.get("collection_rate"), is_pct=True)
        denial = format_number(g.get("denial_rate"), is_pct=True)
        dso = g.get("dso", "N/A")
        lines.append(f"  {name}: {deals} deals, coll {coll}, denial {denial}, DSO {dso}")

    return "\n".join(lines)


def _get_loss_waterfall(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)

    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_cohort_loss_waterfall
        result = compute_silq_cohort_loss_waterfall(df, mult)
    elif at == "aajil":
        df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_aajil import compute_aajil_loss_waterfall
        result = compute_aajil_loss_waterfall(df, mult)
    elif at == "klaim":
        df, sel = load_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis import compute_cohort_loss_waterfall
        result = compute_cohort_loss_waterfall(df, mult)
    else:
        return f"Loss waterfall not available for analysis_type={at}"

    vintages = result.get("vintages", [])
    lines = [f"Loss Waterfall — {company}/{product}"]
    totals = result.get("totals", {})
    if totals:
        lines.append(f"  Portfolio totals:")
        lines.append(f"    Originated: {format_number(totals.get('originated'), is_currency=True, currency=disp)}")
        lines.append(f"    Gross Default: {format_number(totals.get('gross_default'), is_currency=True, currency=disp)}")
        lines.append(f"    Recovery: {format_number(totals.get('recovery'), is_currency=True, currency=disp)}")
        lines.append(f"    Net Loss: {format_number(totals.get('net_loss'), is_currency=True, currency=disp)}")
        lines.append(f"    Default Rate: {format_number(totals.get('default_rate'), is_pct=True)}")
        lines.append(f"    Net Loss Rate: {format_number(totals.get('net_loss_rate'), is_pct=True)}")

    if vintages:
        lines.append(f"  Per-vintage ({len(vintages)} vintages):")
        for v in vintages[:10]:
            vint = v.get("vintage", "?")
            default_rate = format_number(v.get("default_rate"), is_pct=True)
            net_loss_rate = format_number(v.get("net_loss_rate"), is_pct=True)
            lines.append(f"    {vint}: default {default_rate}, net loss {net_loss_rate}")

    return "\n".join(lines)


def _get_segment_analysis(
    company: str, product: str,
    dimension: str = "product",
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at not in ("klaim",):
        return f"Segment analysis not available for analysis_type={at}"

    df, sel = load_tape(company, product, snapshot, as_of_date)
    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_segment_analysis
    result = compute_segment_analysis(df, mult, segment_by=dimension)

    segments = result.get("segments", [])
    lines = [f"Segment Analysis ({dimension}) — {company}/{product}"]
    for s in segments[:10]:
        name = s.get("segment", "?")
        deals = s.get("deals", 0)
        coll = format_number(s.get("collection_rate"), is_pct=True)
        lines.append(f"  {name}: {deals} deals, collection {coll}")

    return "\n".join(lines)


def _get_stress_test(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at not in ("klaim",):
        return f"Stress test not available for analysis_type={at}"

    df, sel = load_tape(company, product, snapshot, as_of_date)
    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_stress_test
    result = compute_stress_test(df, mult)

    scenarios = result.get("scenarios", [])
    lines = [f"Stress Test — {company}/{product}"]
    lines.append(f"  Base collection rate: {format_number(result.get('base_collection_rate'), is_pct=True)}")
    for s in scenarios:
        lines.append(f"  Scenario: {s.get('name', '?')}")
        lines.append(f"    Impact: {format_number(s.get('impact'), is_currency=True, currency=disp)}")
        lines.append(f"    Adjusted rate: {format_number(s.get('adjusted_rate'), is_pct=True)}")

    return "\n".join(lines)


def _get_deployment(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
    elif at == "aajil":
        df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)

    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_deployment
    result = compute_deployment(df, mult)

    monthly = result.get("monthly", [])
    lines = [f"Deployment History — {company}/{product}"]
    for m in monthly[-12:]:
        month = m.get("Month", "?")
        total = format_number(m.get("total", m.get("Total")), is_currency=True, currency=disp)
        deals = m.get("deals", m.get("Deals", 0))
        lines.append(f"  {month}: {total} ({deals} deals)")

    return "\n".join(lines)


def _get_denial_trend(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at not in ("klaim",):
        return f"Denial trend not available for analysis_type={at}"

    df, sel = load_tape(company, product, snapshot, as_of_date)
    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_denial_trend
    result = compute_denial_trend(df, mult)

    monthly = result.get("monthly", [])
    lines = [f"Denial Trend — {company}/{product}"]
    for m in monthly[-12:]:
        month = m.get("Month", "?")
        rate = format_number(m.get("denial_rate"), is_pct=True)
        lines.append(f"  {month}: {rate}")

    return "\n".join(lines)


def _get_dtfc_analysis(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    df, sel = load_tape(company, product, snapshot, as_of_date)
    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_dtfc
    result = compute_dtfc(df, mult, as_of_date=as_of_date or sel.get("date"))

    if not result.get("available"):
        return "DTFC not available for this tape."

    lines = [f"Days to First Cash — {company}/{product}"]
    lines.append(f"  Method: {result.get('method', 'unknown')}")
    lines.append(f"  Median DTFC: {result.get('median_dtfc', 'N/A'):.0f} days")
    lines.append(f"  P90 DTFC: {result.get('p90_dtfc', 'N/A'):.0f} days")
    return "\n".join(lines)


def _get_ageing_breakdown(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)
    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
    else:
        df, sel = load_tape(company, product, snapshot, as_of_date)

    _, disp, mult = get_currency(company, product, currency)

    from core.analysis import compute_ageing
    result = compute_ageing(df, mult)

    lines = [f"Portfolio Ageing — {company}/{product}"]
    lines.append(f"  Total outstanding: {format_number(result.get('total_outstanding'), is_currency=True, currency=disp)}")

    health = result.get("health_summary", [])
    if health:
        lines.append("  Health summary:")
        for h in health:
            status = h.get("status", "?")
            pct = format_number(h.get("percentage"), is_pct=True)
            val = format_number(h.get("value"), is_currency=True, currency=disp)
            lines.append(f"    {status}: {pct} ({val})")

    buckets = result.get("ageing_buckets", [])
    if buckets:
        lines.append("  Ageing buckets:")
        for b in buckets:
            bucket = b.get("bucket", "?")
            outstanding = format_number(b.get("outstanding"), is_currency=True, currency=disp)
            lines.append(f"    {bucket}: {outstanding}")

    return "\n".join(lines)


def _get_underwriting_drift(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)

    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_underwriting_drift
        result = compute_silq_underwriting_drift(df, mult)
    elif at == "klaim":
        df, sel = load_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis import compute_underwriting_drift
        result = compute_underwriting_drift(df, mult)
    else:
        return f"Underwriting drift not available for analysis_type={at}"

    vintages = result.get("vintages", [])
    lines = [f"Underwriting Drift — {company}/{product}"]
    for v in vintages[-8:]:
        vint = v.get("vintage", "?")
        flags = v.get("flags", [])
        flag_str = ", ".join(flags) if flags else "none"
        lines.append(f"  {vint}: flags=[{flag_str}]")

    return "\n".join(lines)


def _get_cdr_ccr(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    at = detect_analysis_type(company, product)

    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_cdr_ccr
        result = compute_silq_cdr_ccr(df, mult)
    elif at == "klaim":
        df, sel = load_tape(company, product, snapshot, as_of_date)
        _, disp, mult = get_currency(company, product, currency)
        from core.analysis import compute_cdr_ccr
        result = compute_cdr_ccr(df, mult)
    else:
        return f"CDR/CCR not available for analysis_type={at}"

    lines = [f"CDR/CCR Analysis — {company}/{product}"]
    lines.append(f"  Portfolio CDR: {format_number(result.get('portfolio_cdr'), is_pct=True)}")
    lines.append(f"  Portfolio CCR: {format_number(result.get('portfolio_ccr'), is_pct=True)}")
    lines.append(f"  Net Spread: {format_number(result.get('net_spread'), is_pct=True)}")
    return "\n".join(lines)


# ── Trend tool (cross-snapshot time series) ───────────────────────────────

# Metrics that can be extracted from a per-snapshot summary dict, regardless
# of analysis type. The key is the summary field name.
_TREND_METRICS = {
    "collection_rate": "collection rate (%)",
    "denial_rate": "denial rate (%)",
    "pending_rate": "pending rate (%)",
    "total_deals": "total deals count",
    "total_purchase_value": "total originated face value",
    "active_deals": "active deal count",
    "completed_deals": "completed deal count",
    "total_outstanding": "outstanding balance",
    "par30": "PAR 30+",
    "par60": "PAR 60+",
    "par90": "PAR 90+",
    "delinquency_rate": "delinquency rate (%)",
    "hhi_customer": "customer HHI",
    "hhi_group": "group/provider HHI",
    "total_customers": "total customer count",
    "total_written_off": "cumulative write-offs",
    "written_off_count": "write-off deal count",
    "avg_tenure": "average tenure",
    "avg_discount": "average discount (%)",
}


def _get_metric_trend(
    company: str, product: str,
    metric: str,
    max_snapshots: int = 12,
) -> str:
    """Build a cross-snapshot time series for a single metric.

    Iterates available snapshots (up to `max_snapshots`, latest first),
    computes the per-snapshot summary for each, extracts the named metric,
    and returns a compact human-readable trend table.

    Unknown metrics return a helpful list of valid options.
    """
    if metric not in _TREND_METRICS:
        return (
            f"Unknown metric '{metric}'. Valid metrics:\n"
            + ", ".join(sorted(_TREND_METRICS.keys()))
        )

    try:
        from core.loader import get_snapshots
        snaps = get_snapshots(company, product)
    except Exception as e:
        return f"No snapshots available: {e}"

    if not snaps:
        return f"No snapshots found for {company}/{product}."

    # Snapshots are typically in chronological order already; take most recent N
    snaps_to_use = snaps[-max_snapshots:] if len(snaps) > max_snapshots else snaps

    at = detect_analysis_type(company, product)

    # Summary-only types don't have tape data to iterate — return a note
    if at in ("ejari_summary", "tamara_summary"):
        return (
            f"{company}/{product} uses pre-computed summaries "
            f"(analysis_type={at}); time-series trends require raw tape snapshots. "
            f"Use analytics.get_portfolio_summary to see the latest available figures."
        )

    config, disp, mult = get_currency(company, product, None)

    series = []
    for snap in snaps_to_use:
        try:
            snap_fn = snap.get("filename")
            if at == "silq":
                df, sel, _ = load_silq_tape(company, product, snap_fn, None)
                from core.analysis_silq import compute_silq_summary
                s = compute_silq_summary(df, mult, ref_date=sel.get("date"))
            elif at == "aajil":
                df, sel, aux = load_aajil_tape(company, product, snap_fn, None)
                from core.analysis_aajil import compute_aajil_summary
                s = compute_aajil_summary(df, mult, aux=aux)
            else:
                df, sel = load_tape(company, product, snap_fn, None)
                from core.analysis import compute_summary
                s = compute_summary(df, config, disp, sel.get("date", ""), None)

            # Aajil summary returns some rates as decimals — normalize
            value = s.get(metric)
            if value is None:
                continue
            series.append({
                "snapshot": snap_fn,
                "date": snap.get("date") or sel.get("date", ""),
                "value": value,
            })
        except Exception as e:
            logger.debug("Trend: snapshot %s failed: %s", snap.get("filename"), e)
            continue

    if not series:
        return f"Metric '{metric}' could not be computed across any available snapshot."

    # Build output
    lines = [f"Trend of {metric} ({_TREND_METRICS[metric]}) for {company}/{product}:"]
    lines.append(f"Snapshots analysed: {len(series)} (of {len(snaps_to_use)} attempted)\n")
    lines.append(f"{'Date':<12}  {'Value':>16}  {'Change':>10}")
    lines.append("-" * 44)
    prev_value = None
    for point in series:
        val = point["value"]
        try:
            val_str = f"{float(val):,.2f}"
        except (TypeError, ValueError):
            val_str = str(val)
        if prev_value is not None and isinstance(val, (int, float)) and isinstance(prev_value, (int, float)) and prev_value != 0:
            change_pct = (float(val) - float(prev_value)) / abs(float(prev_value)) * 100
            change_str = f"{change_pct:+.1f}%"
        else:
            change_str = "—"
        lines.append(f"{point['date']:<12}  {val_str:>16}  {change_str:>10}")
        prev_value = val

    # Summary
    if len(series) >= 2 and all(isinstance(p["value"], (int, float)) for p in series):
        first = series[0]["value"]
        last = series[-1]["value"]
        if first != 0:
            total_change = (last - first) / abs(first) * 100
            lines.append(
                f"\nTotal change over {len(series)} snapshots: {total_change:+.1f}% "
                f"(from {first:.2f} to {last:.2f})"
            )

    return "\n".join(lines)


_TREND_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string", "description": "Company name"},
        "product": {"type": "string", "description": "Product name"},
        "metric": {
            "type": "string",
            "description": (
                "Metric to trend. Valid options: "
                + ", ".join(sorted(_TREND_METRICS.keys()))
            ),
            "enum": sorted(_TREND_METRICS.keys()),
        },
        "max_snapshots": {
            "type": "integer",
            "description": "Max number of snapshots to include (default 12, most recent first).",
            "default": 12,
        },
    },
    "required": ["company", "product", "metric"],
}


# ── Common tool schema ───────────────────────────────────────────────────

_COMMON_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string", "description": "Company name (e.g., 'klaim', 'SILQ', 'Aajil')"},
        "product": {"type": "string", "description": "Product name (e.g., 'UAE_healthcare', 'KSA')"},
        "snapshot": {"type": "string", "description": "Snapshot filename (optional, defaults to latest)"},
        "currency": {"type": "string", "description": "Display currency: reported currency or 'USD' (optional)"},
        "as_of_date": {"type": "string", "description": "As-of date filter YYYY-MM-DD (optional)"},
    },
    "required": ["company", "product"],
}

_SEGMENT_SCHEMA = {
    "type": "object",
    "properties": {
        **_COMMON_SCHEMA["properties"],
        "dimension": {"type": "string", "description": "Segment dimension: 'product', 'provider_size', 'deal_size', or 'new_repeat'", "enum": ["product", "provider_size", "deal_size", "new_repeat"]},
    },
    "required": ["company", "product"],
}


# ── Registration ─────────────────────────────────────────────────────────

_TOOLS = [
    ("analytics.get_portfolio_summary", "Get portfolio-level KPIs: total deals, face value, collection/denial rates, active/completed counts.", _COMMON_SCHEMA, _get_portfolio_summary),
    ("analytics.get_par_analysis", "Get Portfolio at Risk (PAR) analysis: PAR30/60/90 balance and count, method used, active outstanding.", _COMMON_SCHEMA, _get_par_analysis),
    ("analytics.get_cohort_analysis", "Get vintage cohort table: per-vintage deal counts, collection rates, denial rates, loss metrics.", _COMMON_SCHEMA, _get_cohort_analysis),
    ("analytics.get_dso_analysis", "Get Days Sales Outstanding: weighted/median/P95 DSO Capital and Operational variants.", _COMMON_SCHEMA, _get_dso_analysis),
    ("analytics.get_dtfc_analysis", "Get Days to First Cash: median and P90 leading indicator.", _COMMON_SCHEMA, _get_dtfc_analysis),
    ("analytics.get_ageing_breakdown", "Get portfolio ageing: health summary (Healthy/Watch/Delayed/Poor), ageing buckets, outstanding by status.", _COMMON_SCHEMA, _get_ageing_breakdown),
    ("analytics.get_concentration", "Get concentration risk: HHI index, top providers by share, product mix.", _COMMON_SCHEMA, _get_concentration),
    ("analytics.get_returns_analysis", "Get returns: realised margin, capital recovery, discount bands, new vs repeat, IRR if available.", _COMMON_SCHEMA, _get_returns_analysis),
    ("analytics.get_collection_velocity", "Get collection velocity: monthly collection rates, avg/median days, forecast rate.", _COMMON_SCHEMA, _get_collection_velocity),
    ("analytics.get_denial_trend", "Get denial trend: monthly denial rates over time.", _COMMON_SCHEMA, _get_denial_trend),
    ("analytics.get_deployment", "Get deployment history: monthly origination volume and deal counts.", _COMMON_SCHEMA, _get_deployment),
    ("analytics.get_group_performance", "Get per-provider performance: collection rate, denial rate, DSO per healthcare provider.", _COMMON_SCHEMA, _get_group_performance),
    ("analytics.get_stress_test", "Get stress test: shock scenarios on top provider concentration.", _COMMON_SCHEMA, _get_stress_test),
    ("analytics.get_covenants", "Get covenant compliance: each covenant name, actual value, threshold, pass/breach status.", _COMMON_SCHEMA, _get_covenants),
    ("analytics.get_cdr_ccr", "Get Conditional Default Rate and Conditional Collection Rate by vintage.", _COMMON_SCHEMA, _get_cdr_ccr),
    ("analytics.get_segment_analysis", "Get segment analysis by dimension: per-segment deal counts, collection rates, volume.", _SEGMENT_SCHEMA, _get_segment_analysis),
    ("analytics.get_underwriting_drift", "Get underwriting drift: per-vintage quality metrics and drift flags.", _COMMON_SCHEMA, _get_underwriting_drift),
    ("analytics.get_loss_waterfall", "Get loss waterfall: per-vintage Originated → Gross Default → Recovery → Net Loss.", _COMMON_SCHEMA, _get_loss_waterfall),
    ("analytics.get_metric_trend", "Get a cross-snapshot time series for a single metric (e.g., collection_rate across the last N tapes). Useful for spotting trends in judgment sections. Only works for companies with raw tape snapshots (not ejari_summary or tamara_summary).", _TREND_SCHEMA, _get_metric_trend),
]

for name, desc, schema, handler in _TOOLS:
    registry.register(name, desc, schema, handler)
