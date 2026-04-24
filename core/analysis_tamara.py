"""
Tamara BNPL — Data Parser & Enrichment
========================================
Reads pre-processed JSON snapshots (produced by scripts/prepare_tamara_data.py)
and enriches with presentation-layer fields (colors, statuses, derived KPIs).

Usage:
    from core.analysis_tamara import parse_tamara_data
    data = parse_tamara_data('/path/to/2026-04-09_tamara_ksa.json')

Quarterly investor pack
-----------------------
If ``data/Tamara/investor_packs/YYYY-MM-DD_investor_pack.json`` files exist
(produced by ``scripts/ingest_tamara_investor_pack.py``) the latest one is
loaded and merged into the output under the ``quarterly_pack`` key. Enrichment
computes MoM deltas and budget-variance summaries from that data. Empty /
missing ``investor_packs`` folder is a no-op — nothing breaks.
"""

import glob
import json
import os


def parse_tamara_data(filepath):
    """Load and enrich a pre-processed Tamara JSON snapshot.

    Args:
        filepath: Path to JSON file produced by prepare_tamara_data.py

    Returns:
        dict with all sections enriched for dashboard rendering
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Enrich sections
    _enrich_overview(data)
    _enrich_covenant_status(data)
    _enrich_vintage_heatmap(data)
    _enrich_deloitte_summary(data)
    _enrich_hsbc_summary(data)
    _enrich_repayment_behavior(data)
    _enrich_quarterly_pack(data, filepath)

    # Thesis summary (Layer 5 — read-only; drift mutation happens on pack ingest, not here)
    thesis_summary = _load_thesis_summary(company='Tamara')
    if thesis_summary:
        data['thesis_summary'] = thesis_summary

    return data


def _enrich_overview(data):
    """Compute headline KPI summary from available data."""
    overview = {}

    # From Deloitte FDD
    fdd = data.get('deloitte_fdd', {})
    if fdd.get('dpd_timeseries'):
        latest = fdd['dpd_timeseries'][-1]
        overview['total_pending'] = latest.get('total_pending', 0)
        overview['total_written_off'] = latest.get('total_written_off', 0)
        overview['latest_date'] = fdd.get('latest_date', '')
        overview['months_of_data'] = len(fdd['dpd_timeseries'])

        # DPD distribution for latest month
        dpd = latest.get('dpd_distribution', {})
        total = sum(v for v in dpd.values() if v)
        if total > 0:
            not_late = dpd.get('Not Late', 0) or 0
            overview['current_rate'] = round((1 - not_late / total) * 100, 2)

    # Product breakdown
    if fdd.get('product_breakdown'):
        overview['product_breakdown'] = fdd['product_breakdown']

    # Customer breakdown
    if fdd.get('customer_breakdown'):
        overview['customer_breakdown'] = fdd['customer_breakdown']

    # From company overview (static)
    co = data.get('company_overview', {})
    overview['registered_users'] = co.get('registered_users', 0)
    overview['merchants'] = co.get('merchants', 0)
    overview['valuation'] = co.get('valuation', 0)
    overview['employees'] = co.get('employees', 0)

    # From facility terms
    ft = data.get('facility_terms', {})
    overview['facility_limit'] = ft.get('total_limit', 0)
    overview['max_advance_rate'] = ft.get('max_advance_rate', 0)

    # Vintage count
    vp = data.get('vintage_performance', {})
    default_portfolio = vp.get('default', {}).get('portfolio', [])
    overview['vintage_count'] = len(default_portfolio)

    data['overview'] = overview


def _enrich_covenant_status(data):
    """Add compliance status and headroom to covenant data."""
    ft = data.get('facility_terms', {})
    triggers = ft.get('triggers', {})
    hsbc = data.get('hsbc_reports', [])

    if not hsbc or not triggers:
        data['covenant_status'] = {'available': False}
        return

    # Get latest report's trigger values
    latest_report = hsbc[-1] if hsbc else {}
    trigger_rows = latest_report.get('triggers', [])

    covenant_results = []
    for trigger_key, trigger_def in triggers.items():
        # Find matching row in HSBC data
        metric_name = trigger_def.get('metric', '')
        l1 = trigger_def.get('l1', 0)
        l2 = trigger_def.get('l2', 0)
        l3 = trigger_def.get('l3', 0)

        # Try to find current value from trigger rows
        current_value = None
        for row in trigger_rows:
            label = row.get('label', '').lower()
            if trigger_key in label or metric_name.lower()[:10] in label:
                # Try to extract numeric value
                for v in row.get('values', []):
                    try:
                        pct = float(v.replace('%', '').replace(',', '').strip())
                        if 0 <= pct <= 100:
                            current_value = pct / 100
                            break
                    except (ValueError, AttributeError):
                        pass

        status = 'unknown'
        headroom = None
        if current_value is not None:
            if current_value < l1:
                status = 'compliant'
                headroom = round((l1 - current_value) * 100, 2)
            elif current_value < l2:
                status = 'l1_breach'
                headroom = round((l2 - current_value) * 100, 2)
            elif current_value < l3:
                status = 'l2_breach'
                headroom = round((l3 - current_value) * 100, 2)
            else:
                status = 'l3_breach'
                headroom = 0

        covenant_results.append({
            'name': trigger_key,
            'metric': metric_name,
            'current_value': round(current_value * 100, 2) if current_value else None,
            'l1_threshold': round(l1 * 100, 2),
            'l2_threshold': round(l2 * 100, 2),
            'l3_threshold': round(l3 * 100, 2),
            'status': status,
            'headroom_pct': headroom,
        })

    data['covenant_status'] = {
        'available': True,
        'triggers': covenant_results,
        'report_count': len(hsbc),
        'latest_report_date': latest_report.get('report_date', ''),
    }


def _enrich_vintage_heatmap(data):
    """Pre-compute heatmap color values for vintage matrices.

    UNCERTAIN 1 audit resolution: percentile bounds (p25/p75) are computed
    across ALL vintage-MOB cells regardless of seasoning. This is the right
    behaviour for an IC-view heatmap ("where does this vintage sit against
    the long-run average"). It is NOT the right behaviour for a "is this
    vintage worse than its same-age peers" view — mature vintages dominate
    the distribution.
    Resolution: keep the flat percentile scale as the primary surface
    (matches HSBC investor report semantics) + emit `_color_scale_note`
    documenting the interpretation, and include cell-count so the analyst
    can judge sample size. An age-normalised variant would require
    per-MOB percentile computation — deferred to a separate task (no
    consumer today).
    """
    vp = data.get('vintage_performance', {})

    for metric in ['default', 'delinquency', 'dilution']:
        metric_data = vp.get(metric, {})
        portfolio = metric_data.get('portfolio', [])
        if not portfolio:
            continue

        # Collect all values for color scale
        all_values = []
        for record in portfolio:
            for k, v in record.items():
                if k != 'vintage' and v is not None:
                    all_values.append(v)

        if not all_values:
            continue

        # Compute percentile bounds for color mapping
        sorted_vals = sorted(all_values)
        p25 = sorted_vals[len(sorted_vals) // 4] if len(sorted_vals) >= 4 else 0
        p75 = sorted_vals[3 * len(sorted_vals) // 4] if len(sorted_vals) >= 4 else max(sorted_vals)

        vp[metric]['_color_scale'] = {
            'min': round(min(all_values), 6),
            'max': round(max(all_values), 6),
            'p25': round(p25, 6),
            'p75': round(p75, 6),
            'count': len(all_values),
            'scale_type': 'flat_percentile_all_vintages',
            'note': (
                'Percentile scale computed across all vintage × MOB cells. '
                'Appropriate for "where does this vintage sit against the '
                'long-run average" (IC view). For "is this vintage worse '
                'than its same-age peers", an age-normalised scale would be '
                'needed — not currently emitted. Framework §17 UNCERTAIN 1.'
            ),
        }


def _enrich_deloitte_summary(data):
    """Add summary statistics from Deloitte FDD data."""
    fdd = data.get('deloitte_fdd', {})
    ts = fdd.get('dpd_timeseries', [])

    if len(ts) < 2:
        return

    summary = {
        'date_range': f"{ts[0].get('date', '')} to {ts[-1].get('date', '')}",
        'months': len(ts),
    }

    # Trend: total pending over time
    pending_trend = []
    writeoff_trend = []
    for entry in ts:
        pending_trend.append({
            'date': entry.get('date', ''),
            'amount': entry.get('total_pending', 0),
        })
        writeoff_trend.append({
            'date': entry.get('date', ''),
            'amount': entry.get('total_written_off', 0),
        })

    summary['pending_trend'] = pending_trend
    summary['writeoff_trend'] = writeoff_trend

    # Latest DPD distribution
    latest = ts[-1]
    dpd = latest.get('dpd_distribution', {})
    total = sum(v for v in dpd.values() if v)
    if total > 0:
        summary['dpd_pct'] = {
            bucket: round(amount / total * 100, 2)
            for bucket, amount in dpd.items()
            if amount
        }

    fdd['summary'] = summary


def _enrich_hsbc_summary(data):
    """Aggregate key metrics across all HSBC reports for time series."""
    reports = data.get('hsbc_reports', [])
    if not reports:
        return

    # Sort by date
    reports.sort(key=lambda r: r.get('report_date', '') or '')

    # Extract concentration limit compliance across reports
    concentration_timeseries = []
    for report in reports:
        date = report.get('report_date', '')
        limits = report.get('concentration_limits', [])
        concentration_timeseries.append({
            'date': date,
            'limits_count': len(limits),
        })

    data['hsbc_summary'] = {
        'report_count': len(reports),
        'date_range': f"{reports[0].get('report_date', '')} to {reports[-1].get('report_date', '')}",
        'concentration_timeseries': concentration_timeseries,
    }


def _enrich_repayment_behavior(data):
    """Compute summary metrics from repayment lifecycle and customer behavior."""
    latest = 'Q1 2026'
    prev = 'Q4 2025'

    # ── Repayment lifecycle summary ──
    rep = data.get('repayment_lifecycle', {})
    rep_bal = rep.get('balance', [])
    if rep_bal:
        current_by_stage = {}
        default_by_stage = {}
        total_by_stage = {}
        for r in rep_bal:
            stage = r.get('installments_left', '?')
            val = r.get(latest, 0) or 0
            total_by_stage[stage] = total_by_stage.get(stage, 0) + val
            if r['dpd_bucket'] == 'Current':
                current_by_stage[stage] = current_by_stage.get(stage, 0) + val
            elif 'Default' in r['dpd_bucket']:
                default_by_stage[stage] = default_by_stage.get(stage, 0) + val

        # Build stage breakdown for charts — use actual keys from data
        all_stages = sorted(total_by_stage.keys(),
                            key=lambda s: (0 if s == '1' else 1 if '2' in s else 2 if '4' in s else 3))
        stages = []
        for stage in all_stages:
            total = total_by_stage.get(stage, 0)
            if total > 0:
                stages.append({
                    'stage': stage,
                    'total_pct': round(total * 100, 2),
                    'current_pct': round((current_by_stage.get(stage, 0) / total) * 100, 1),
                    'default_pct': round((default_by_stage.get(stage, 0) / total) * 100, 2),
                })

        near_maturity = total_by_stage.get('1', 0)
        early_stage = total_by_stage.get('7+', 0)

        data['repayment_summary'] = {
            'near_maturity_pct': round(near_maturity * 100, 1),
            'early_stage_pct': round(early_stage * 100, 1),
            'stages': stages,
            'quarters': ['Q4 2023', 'Q4 2024', 'Q4 2025', 'Q1 2026'],
        }

        # Quarterly time series by stage (for stacked bar)
        quarterly_series = []
        for q in ['Q4 2023', 'Q4 2024', 'Q4 2025', 'Q1 2026']:
            point = {'quarter': q}
            for stage in all_stages:
                current = sum(r.get(q, 0) or 0 for r in rep_bal
                              if r.get('installments_left') == stage and r['dpd_bucket'] == 'Current')
                delinquent = sum(r.get(q, 0) or 0 for r in rep_bal
                                if r.get('installments_left') == stage and r['dpd_bucket'] != 'Current')
                point[f'{stage}_current'] = round(current * 100, 2)
                point[f'{stage}_delinquent'] = round(delinquent * 100, 2)
            quarterly_series.append(point)
        data['repayment_summary']['quarterly'] = quarterly_series

    # ── Customer behavior summary ──
    beh = data.get('customer_behavior', {})
    beh_bal = beh.get('balance', [])
    if beh_bal:
        current_by_tier = {}
        default_by_tier = {}
        total_by_tier = {}
        for r in beh_bal:
            tier = r.get('lifetime_transactions', '?')
            val = r.get(latest, 0) or 0
            total_by_tier[tier] = total_by_tier.get(tier, 0) + val
            if r['dpd_bucket'] == 'Current':
                current_by_tier[tier] = current_by_tier.get(tier, 0) + val
            elif 'Default' in r['dpd_bucket']:
                default_by_tier[tier] = default_by_tier.get(tier, 0) + val

        all_tiers = sorted(total_by_tier.keys(),
                           key=lambda t: (0 if t == '1' else 1 if '2' in t else 2 if '4' in t else 3))
        tiers = []
        for tier in all_tiers:
            total = total_by_tier.get(tier, 0)
            if total > 0:
                tiers.append({
                    'tier': tier,
                    'total_pct': round(total * 100, 2),
                    'current_pct': round((current_by_tier.get(tier, 0) / total) * 100, 1),
                    'default_pct': round((default_by_tier.get(tier, 0) / total) * 100, 2),
                })

        repeat_pct = total_by_tier.get('>5', 0)
        new_default = default_by_tier.get('1', 0)
        new_total = total_by_tier.get('1', 0)
        repeat_default = default_by_tier.get('>5', 0)
        repeat_total = total_by_tier.get('>5', 0)

        data['behavior_summary'] = {
            'repeat_balance_pct': round(repeat_pct * 100, 1),
            'new_default_rate': round((new_default / new_total * 100), 2) if new_total > 0 else 0,
            'repeat_default_rate': round((repeat_default / repeat_total * 100), 2) if repeat_total > 0 else 0,
            'tiers': tiers,
            'quarters': ['Q4 2023', 'Q4 2024', 'Q4 2025', 'Q1 2026'],
        }

        # Quarterly time series by tier
        quarterly_series = []
        for q in ['Q4 2023', 'Q4 2024', 'Q4 2025', 'Q1 2026']:
            point = {'quarter': q}
            for tier in all_tiers:
                current = sum(r.get(q, 0) or 0 for r in beh_bal
                              if r.get('lifetime_transactions') == tier and r['dpd_bucket'] == 'Current')
                delinquent = sum(r.get(q, 0) or 0 for r in beh_bal
                                if r.get('lifetime_transactions') == tier and r['dpd_bucket'] != 'Current')
                safe_tier = tier.replace('>', 'gt')
                point[f'{safe_tier}_current'] = round(current * 100, 2)
                point[f'{safe_tier}_delinquent'] = round(delinquent * 100, 2)
            quarterly_series.append(point)
        data['behavior_summary']['quarterly'] = quarterly_series


# ── Quarterly Investor Pack enrichment ────────────────────────────────────────
# Loads the most recent file from ``data/Tamara/investor_packs/`` (produced by
# ``scripts/ingest_tamara_investor_pack.py``) and merges a curated slice into
# the dashboard payload under the ``quarterly_pack`` key. This is the recurring
# data channel for Tamara going forward — replaces the one-off prepare_tamara_data
# ETL as the primary refresh loop. Missing folder/files are a no-op.

# Line items to pull for headline MoM/QoQ comparison. Sourced from the
# consolidated FS sheet (2.1 FS Cons) — these are the canonical names after
# the Excel template is parsed. Labels match the investor pack verbatim.
_FS_HEADLINE_ITEMS = [
    'Total GMV',
    'Total Operating Revenue',
    'Contribution Margin',
    'EBTDA',
    'Profit before Tax',
    'Statutory Net Profit / (Loss)',
    'Statutory Contribution Margin',
    'Cash',
    'Net AR',
    'Total Assets',
    'Debt',
    'ECL Provisions',
    'Coverage Ratio',
]

_KPI_HEADLINE_ITEMS = [
    '# Annual active customers',
    '# Monthly active customers',
    '# Annual active merchants',
    '# of orders',
    'Approval rates (Updated logic)',
    'Conversion Rates',
    'AOV',
    'LTV / CAC',
    'CAC per customer',
    'Churn Rate (1 - Retention Rate)',
    'Profit Bearing GMV',
    'FTE Headcount',
]


def _find_latest_investor_pack(snapshot_filepath):
    """
    Locate the newest investor pack JSON under ``data/Tamara/investor_packs/``.

    ``snapshot_filepath`` is e.g. ``/path/to/data/Tamara/KSA/2026-04-09_tamara_ksa.json`` —
    we walk up to the ``Tamara/`` root and look for an ``investor_packs/`` sibling.

    Returns the absolute path of the latest pack JSON (by filename-date sort)
    or None if the folder is missing/empty.
    """
    try:
        ksa_or_uae_dir = os.path.dirname(os.path.abspath(snapshot_filepath))
        tamara_root = os.path.dirname(ksa_or_uae_dir)
        packs_dir = os.path.join(tamara_root, 'investor_packs')
        if not os.path.isdir(packs_dir):
            return None
        candidates = sorted(glob.glob(os.path.join(packs_dir, '*_investor_pack.json')))
        return candidates[-1] if candidates else None
    except Exception:  # noqa: BLE001
        # Any path mishap = no pack. Don't break the main pipeline.
        return None


def _mom_delta(series_dict, months_sorted):
    """
    Compute month-over-month delta from a {YYYY-MM: value} dict.

    Returns {latest, latest_month, prior, prior_month, abs_delta, pct_delta}.
    - Empty months list → all fields None (no data).
    - Single-month series → latest populated, prior/deltas None.
    - 2+ months → full comparison; non-numeric or None values leave deltas None.

    Callers decide how to render missing values.
    """
    out = {
        'latest': None,
        'latest_month': None,
        'prior': None,
        'prior_month': None,
        'abs_delta': None,
        'pct_delta': None,
    }
    if not months_sorted:
        return out

    latest_key = months_sorted[-1]
    out['latest'] = series_dict.get(latest_key)
    out['latest_month'] = latest_key

    if len(months_sorted) < 2:
        return out

    prior_key = months_sorted[-2]
    out['prior'] = series_dict.get(prior_key)
    out['prior_month'] = prior_key

    latest_val = out['latest']
    prior_val = out['prior']
    # Treat bool as non-numeric here — otherwise True + 1 = 2 etc. (avoid subtle bugs)
    latest_is_num = isinstance(latest_val, (int, float)) and not isinstance(latest_val, bool)
    prior_is_num = isinstance(prior_val, (int, float)) and not isinstance(prior_val, bool)
    if latest_is_num and prior_is_num:
        out['abs_delta'] = round(latest_val - prior_val, 6)
        if prior_val != 0:
            out['pct_delta'] = round((latest_val - prior_val) / prior_val, 6)

    return out


def _build_headline_deltas(section_block, wanted_labels):
    """
    Given a parsed pack section (KPIs or FS for one country) and a list of
    desired labels, build {label: mom_delta_dict} for each that has a series.
    """
    out = {}
    months = section_block.get('months') or []
    line_items = section_block.get('line_items') or {}
    for label in wanted_labels:
        series = line_items.get(label)
        # Skip section-header stubs ({'_section_header': True}) and empty rows
        if not isinstance(series, dict) or series.get('_section_header'):
            continue
        out[label] = _mom_delta(series, months)
    return out


def _summarise_budget_variance(budget_block):
    """
    Extract the YTD vs budget variance summary from the Performance v Budget block.

    The sheet stores Actuals, Budget (Base Case), and Variance sections side by
    side. We pluck the YTD totals + % and a monthly variance for each core metric.
    """
    items = budget_block.get('line_items') or {}
    summary = {}
    # Metrics the analyst cares about most
    for metric in ('Total GMV', 'Total Operating Revenue', 'Total Transaction Costs',
                   'Contribution Margin / NTM', 'Total Operating Expenses', 'EBTDA'):
        row = items.get(metric)
        if not isinstance(row, dict):
            continue

        # Each row is {section_label: {col_key: value}}. Flatten and extract.
        entry = {}
        for section, col_map in row.items():
            if not isinstance(col_map, dict):
                continue
            section_lower = (section or '').lower()
            ytd = col_map.get('YTD')
            if 'actual' in section_lower and ytd is not None:
                entry['actual_ytd'] = ytd
            elif 'budget' in section_lower and 'variance' not in section_lower and ytd is not None:
                entry['budget_ytd'] = ytd
            # The variance section exposes "Monthly Budget Variance (%)", "YTD Budget Variance (%)"
            # as literal column KEYS (not datetime). Pluck those.
            for key, val in col_map.items():
                if not isinstance(key, str):
                    continue
                key_lower = key.lower()
                if 'ytd' in key_lower and 'variance' in key_lower and '%' in key_lower:
                    entry['ytd_variance_pct'] = val
                elif 'monthly' in key_lower and 'variance' in key_lower and '%' in key_lower:
                    entry['monthly_variance_pct'] = val

        if entry:
            summary[metric] = entry
    return summary


def build_thesis_metrics_from_pack(pack):
    """Flatten a parsed investor pack into a {metric_key: float} dict suitable
    for ``ThesisTracker.check_drift(...)``.

    Returns a dict with keys like:
      - cons_statutory_net_profit, cons_ebtda_latest, cons_contribution_margin_pct
      - cons_ecl_coverage_pct, cons_ltv_cac, cons_churn_rate
      - ytd_gmv_vs_budget_pct, ytd_revenue_vs_budget_pct, ytd_ebtda_vs_budget_pct
      - cons_profit_bearing_gmv_pct   (derived: Profit Bearing GMV / Total GMV)

    Values are raw floats (not percentages of 100). Missing data → key omitted.
    Callers pass the enriched ``quarterly_pack`` dict (not the raw JSON on disk).
    """
    metrics = {}
    if not pack:
        return metrics

    fs_cons = (pack.get('headline_fs') or {}).get('cons') or {}

    def _latest(key):
        entry = fs_cons.get(key) or {}
        val = entry.get('latest')
        return val if isinstance(val, (int, float)) else None

    cons_gmv = _latest('Total GMV')
    cons_revenue = _latest('Total Operating Revenue')
    cons_cm_usd = _latest('Contribution Margin')
    cons_ebtda = _latest('EBTDA')
    cons_net_profit = _latest('Statutory Net Profit / (Loss)')
    cons_cash = _latest('Cash')
    cons_net_ar = _latest('Net AR')
    cons_debt = _latest('Debt')
    cons_coverage = _latest('Coverage Ratio')

    if cons_gmv is not None:
        metrics['cons_gmv_latest'] = cons_gmv
    if cons_revenue is not None:
        metrics['cons_revenue_latest'] = cons_revenue
    if cons_cm_usd is not None:
        metrics['cons_contribution_margin_usd'] = cons_cm_usd
    if cons_ebtda is not None:
        metrics['cons_ebtda_latest'] = cons_ebtda
    if cons_net_profit is not None:
        metrics['cons_statutory_net_profit'] = cons_net_profit
    if cons_cash is not None:
        metrics['cons_cash'] = cons_cash
    if cons_net_ar is not None:
        metrics['cons_net_ar'] = cons_net_ar
    if cons_debt is not None:
        metrics['cons_debt'] = cons_debt
    if cons_coverage is not None:
        metrics['cons_ecl_coverage_pct'] = cons_coverage

    # Derived: Contribution Margin % of GMV
    if cons_cm_usd is not None and cons_gmv and cons_gmv != 0:
        metrics['cons_contribution_margin_pct'] = cons_cm_usd / cons_gmv

    kpi_cons = (pack.get('headline_kpis') or {}).get('cons') or {}

    def _kpi_latest(key):
        entry = kpi_cons.get(key) or {}
        val = entry.get('latest')
        return val if isinstance(val, (int, float)) else None

    ltv_cac = _kpi_latest('LTV / CAC')
    churn = _kpi_latest('Churn Rate (1 - Retention Rate)')
    aov = _kpi_latest('AOV')
    active_cust = _kpi_latest('# Annual active customers')
    active_merch = _kpi_latest('# Annual active merchants')
    pbg = _kpi_latest('Profit Bearing GMV')

    if ltv_cac is not None:
        metrics['cons_ltv_cac'] = ltv_cac
    if churn is not None:
        metrics['cons_churn_rate'] = churn
    if aov is not None:
        metrics['cons_aov'] = aov
    if active_cust is not None:
        metrics['cons_active_customers'] = active_cust
    if active_merch is not None:
        metrics['cons_active_merchants'] = active_merch

    # Derived: BNPL+ / Profit Bearing GMV share of total GMV
    if pbg is not None and cons_gmv and cons_gmv != 0:
        metrics['cons_profit_bearing_gmv_pct'] = pbg / cons_gmv

    # Budget variance (YTD %)
    bvs = pack.get('budget_variance_summary') or {}
    budget_map = {
        'Total GMV': 'ytd_gmv_vs_budget_pct',
        'Total Operating Revenue': 'ytd_revenue_vs_budget_pct',
        'Contribution Margin / NTM': 'ytd_contribution_margin_vs_budget_pct',
        'EBTDA': 'ytd_ebtda_vs_budget_pct',
        'Total Operating Expenses': 'ytd_opex_vs_budget_pct',
    }
    for metric_label, key in budget_map.items():
        entry = bvs.get(metric_label) or {}
        v = entry.get('ytd_variance_pct')
        if isinstance(v, (int, float)):
            metrics[key] = v

    return metrics


def _load_thesis_summary(company='Tamara'):
    """Load current thesis summary for the frontend (read-only, no drift check).

    Returns a small dict {conviction_score, status, pillars: [...]} or None.
    Soft-imports ThesisTracker to avoid circular import risk.
    """
    try:
        from core.mind.thesis import ThesisTracker
    except Exception:  # noqa: BLE001
        return None
    try:
        tracker = ThesisTracker(company=company, product='all')
        thesis = tracker.load()
        if not thesis:
            return None
        return {
            'title': thesis.title,
            'status': thesis.status,
            'conviction_score': thesis.conviction_score,
            'pillars': [
                {
                    'id': p.id,
                    'claim': p.claim,
                    'status': p.status,
                    'metric_key': p.metric_key,
                    'threshold': p.threshold,
                    'direction': p.direction,
                    'last_value': p.last_value,
                    'last_checked': p.last_checked,
                    'conviction_score': p.conviction_score,
                }
                for p in thesis.pillars
            ],
            'weakening_count': len(thesis.weakening_pillars),
            'broken_count': len(thesis.broken_pillars),
        }
    except Exception:  # noqa: BLE001
        return None


def _enrich_quarterly_pack(data, snapshot_filepath):
    """
    Merge the latest investor pack (if present) into ``data['quarterly_pack']``.
    Safe no-op when no pack is found.
    """
    pack_path = _find_latest_investor_pack(snapshot_filepath)
    if not pack_path:
        return

    try:
        with open(pack_path, 'r', encoding='utf-8') as f:
            pack = json.load(f)
    except Exception as exc:  # noqa: BLE001
        # Malformed pack → don't break the dashboard, surface a note instead.
        data['quarterly_pack'] = {
            '_error': f'Failed to load investor pack: {exc}',
            'source_file': os.path.basename(pack_path),
        }
        return

    meta = pack.get('meta', {}) or {}
    kpis = pack.get('kpis', {}) or {}
    financials = pack.get('financials', {}) or {}
    budget_block = pack.get('budget_variance', {}) or {}

    enriched = {
        'meta': meta,
        'source_file': os.path.basename(pack_path),
        'pack_date': meta.get('pack_date'),
        'data_range': meta.get('data_range', {}),
        'headline_fs': {
            country: _build_headline_deltas(financials.get(country, {}), _FS_HEADLINE_ITEMS)
            for country in ('cons', 'ksa', 'uae')
        },
        'headline_kpis': {
            country: _build_headline_deltas(kpis.get(country, {}), _KPI_HEADLINE_ITEMS)
            for country in ('cons', 'ksa', 'uae')
        },
        'budget_variance_summary': _summarise_budget_variance(budget_block),
        # Pass through raw section data for future tabs (frontend can slice as needed)
        'raw': {
            'kpis': kpis,
            'financials': financials,
            'budget_variance': budget_block,
        },
    }
    data['quarterly_pack'] = enriched


def get_tamara_summary_kpis(data):
    """Extract headline KPIs for the /summary endpoint.

    Returns dict matching the canonical field names expected by the frontend.

    IMPORTANT: Tamara has no raw loan tape, so metrics differ from Klaim/SILQ:
    - total_purchase_value = outstanding AR (point-in-time), NOT total originated
    - total_deals = number of HSBC monthly reports (data points), NOT loan count
    - face_value_label = "Outstanding AR" (not "Face Value") for display purposes
    The frontend should check `face_value_label` to show the right label on cards.

    P1-7 audit: Tamara has no `total_originated` concept. The Deloitte FDD +
    HSBC reports deliver outstanding balances and DPD distributions by month;
    the vintage heatmaps cover defaults/delinquency/dilution rates but NOT
    origination volume. For Framework §17 L1 (Size & Composition), this is a
    structural data-room limitation — not a platform bug. The dict therefore
    carries `population: snapshot_date_state` and `confidence: A` tags so the
    frontend can disclose this to the analyst. Total originated volume is not
    recoverable from the current data room.
    """
    overview = data.get('overview', {})
    fdd = data.get('deloitte_fdd', {})
    ft = data.get('facility_terms', {})
    co = data.get('company_overview', {})
    hsbc = data.get('hsbc_reports', [])

    total_pending = overview.get('total_pending', 0) or 0

    # Use HSBC report count as "data points" (more meaningful than vintage count)
    data_points = len(hsbc) or overview.get('months_of_data', 0) or overview.get('vintage_count', 0)

    return {
        'total_purchase_value': total_pending,
        'total_deals': data_points,
        'collection_rate': 0,
        'denial_rate': 0,
        'analysis_type': 'tamara_summary',
        'facility_limit': ft.get('total_limit', 0),
        'registered_users': overview.get('registered_users', 0),
        'merchants': overview.get('merchants', 0),
        # Tamara-specific: tells the frontend to use different labels
        'face_value_label': 'Outstanding AR',
        'deals_label': 'Reports',
        # P1-7 audit: Framework §17 population declaration.
        # Tamara data room does not carry lifetime originated volume —
        # outstanding AR is a point-in-time snapshot, not a rate.
        'total_purchase_value_population': 'snapshot_date_state',
        'total_purchase_value_confidence': 'A',
        'structural_data_limitation': (
            'Tamara data room delivers outstanding balances + DPD distributions '
            'per reporting month; total_originated volume is not recoverable '
            'from current sources. See Framework §17 Population Discipline.'
        ),
    }
