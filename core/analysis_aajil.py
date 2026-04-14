"""
Aajil SME Trade Credit — Data Parser & Enrichment
====================================================
Reads pre-processed JSON snapshots (produced by scripts/prepare_aajil_data.py)
and enriches with presentation-layer fields (colors, statuses, derived KPIs).

When the loan tape arrives from Cascade Debt, this module will be extended
with DataFrame compute functions (following the SILQ pattern).

Usage:
    from core.analysis_aajil import parse_aajil_data
    data = parse_aajil_data('/path/to/2026-04-14_aajil_ksa.json')
"""

import json


def parse_aajil_data(filepath):
    """Load and enrich a pre-processed Aajil JSON snapshot.

    Args:
        filepath: Path to JSON file produced by prepare_aajil_data.py

    Returns:
        dict with all sections enriched for dashboard rendering
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    _enrich_overview(data)
    _enrich_traction(data)
    _enrich_customer_segments(data)
    _enrich_trust_scores(data)
    _enrich_underwriting(data)

    return data


def _enrich_overview(data):
    """Compute headline KPI summary from available data."""
    co = data.get('company_overview', {})
    overview = {
        'total_customers': co.get('total_customers', 0),
        'total_transactions': co.get('total_transactions', 0),
        'aum_sar': co.get('aum_sar', 0),
        'aum_usd': co.get('aum_usd', 0),
        'gmv_sar': co.get('gmv_sar', 0),
        'gmv_usd': co.get('gmv_usd', 0),
        'avg_tenor_months': co.get('avg_tenor_months', 0),
        'dpd60_plus_rate': co.get('dpd60_plus_rate', 0),
        'pn_coverage': co.get('pn_coverage', 0),
        'employees': co.get('employees', 0),
        'credit_deployment_hours': co.get('credit_deployment_hours', 24),
        'avg_deals_per_customer': co.get('avg_deals_per_customer', 0),
    }

    # Growth rates from GMV milestones
    milestones = data.get('gmv_milestones', [])
    if len(milestones) >= 2:
        latest = milestones[-1]
        prev = milestones[-2]
        if prev['gmv_sar'] > 0:
            overview['gmv_yoy_growth'] = round(
                (latest['gmv_sar'] - prev['gmv_sar']) / prev['gmv_sar'] * 100, 1
            )

    # Customer growth rate
    cg = data.get('customer_growth', [])
    if len(cg) >= 2:
        latest_c = cg[-1]['total_customers']
        prev_c = cg[-2]['total_customers']
        if prev_c > 0:
            overview['customer_growth_pct'] = round(
                (latest_c - prev_c) / prev_c * 100, 1
            )

    data['overview'] = overview


def _enrich_traction(data):
    """Build traction (Volume + Balance) data from GMV milestones and customer growth."""
    milestones = data.get('gmv_milestones', [])

    # Volume: per-year disbursement (incremental, not cumulative)
    volume = []
    for i, m in enumerate(milestones):
        disbursed = m['gmv_sar']
        if i > 0:
            disbursed = m['gmv_sar'] - milestones[i - 1]['gmv_sar']
        volume.append({
            'year': m['year'],
            'disbursed_sar': disbursed,
            'disbursed_usd': round(disbursed * 0.2667)
        })

    # Compute growth rates
    growth_stats = {}
    if len(volume) >= 2:
        latest = volume[-1]['disbursed_sar']
        prev = volume[-2]['disbursed_sar']
        if prev > 0:
            growth_stats['yoy_pct'] = round((latest - prev) / prev * 100, 2)

    data['traction'] = {
        'volume': volume,
        'balance_sar': data.get('company_overview', {}).get('aum_sar', 0),
        'growth_stats': growth_stats,
        'note': 'Annual granularity from investor deck. Monthly data available from Cascade Debt tape.'
    }


def _enrich_customer_segments(data):
    """Enrich customer type data with display colors."""
    colors = {
        'Manufacturer': '#5B8DEF',
        'Contractor': '#C9A84C',
        'Wholesale Trader': '#2DD4BF'
    }
    for ct in data.get('customer_types', []):
        ct['color'] = colors.get(ct['type'], '#8494A7')

    # Sales channel colors
    channel_colors = {
        'Performance Marketing': '#5B8DEF',
        'Outbound Prospecting': '#C9A84C',
        'Referral Networks': '#2DD4BF',
        'Field Sales': '#F06060'
    }
    for sc in data.get('sales_channels', []):
        sc['color'] = channel_colors.get(sc['channel'], '#8494A7')


def _enrich_trust_scores(data):
    """Add display colors to trust score system."""
    score_colors = {
        5: '#2DD4BF',  # teal - green
        4: '#C9A84C',  # gold - amber
        3: '#F06060',  # red
        2: '#D32F2F',  # dark red - critical
        1: '#B71C1C',  # deepest red - critical
    }
    ts = data.get('trust_score_system', {})
    for s in ts.get('scores', []):
        s['color'] = score_colors.get(s['score'], '#8494A7')

    # Phase colors
    phase_colors = {
        'Preventive': '#2DD4BF',
        'Active': '#C9A84C',
        'Legal': '#F06060'
    }
    for p in ts.get('collections_phases', []):
        p['color'] = phase_colors.get(p['phase'], '#8494A7')


def _enrich_underwriting(data):
    """Add stage numbering and colors to underwriting stages."""
    uw = data.get('underwriting', {})
    stage_colors = ['#5B8DEF', '#2DD4BF', '#C9A84C', '#F06060']
    stages = uw.get('stages', [])
    uw['stages_enriched'] = [
        {'name': s, 'number': i + 1, 'color': stage_colors[i] if i < len(stage_colors) else '#8494A7'}
        for i, s in enumerate(stages)
    ]


def get_aajil_summary(data):
    """Return summary KPIs for the landing page card.

    Uses canonical field names expected by the frontend.
    """
    co = data.get('company_overview', {})
    return {
        'total_purchase_value': co.get('aum_sar', 0),
        'face_value_label': 'AUM (Outstanding)',
        'total_deals': co.get('total_transactions', 0),
        'deals_label': 'Credit Transactions',
        'collection_rate': 1.0 - co.get('dpd60_plus_rate', 0),
        'total_collected': co.get('gmv_sar', 0),
        'total_customers': co.get('total_customers', 0),
    }
