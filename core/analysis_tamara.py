"""
Tamara BNPL — Data Parser & Enrichment
========================================
Reads pre-processed JSON snapshots (produced by scripts/prepare_tamara_data.py)
and enriches with presentation-layer fields (colors, statuses, derived KPIs).

Usage:
    from core.analysis_tamara import parse_tamara_data
    data = parse_tamara_data('/path/to/2026-04-09_tamara_ksa.json')
"""

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
    """Pre-compute heatmap color values for vintage matrices."""
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


def get_tamara_summary_kpis(data):
    """Extract headline KPIs for the /summary endpoint.

    Returns dict matching the canonical field names expected by the frontend.

    IMPORTANT: Tamara has no raw loan tape, so metrics differ from Klaim/SILQ:
    - total_purchase_value = outstanding AR (point-in-time), NOT total originated
    - total_deals = number of HSBC monthly reports (data points), NOT loan count
    - face_value_label = "Outstanding AR" (not "Face Value") for display purposes
    The frontend should check `face_value_label` to show the right label on cards.
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
    }
