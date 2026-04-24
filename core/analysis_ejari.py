"""
core/analysis_ejari.py
Parse the Ejari ODS summary workbook into structured JSON for display.
No computation — this is a read-only data renderer.
"""
import pandas as pd
import numpy as np


def _clean(val):
    """Convert numpy/pandas types to JSON-serializable Python types."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, pd.Timestamp):
        return val.strftime('%Y-%m-%d')
    return str(val) if not isinstance(val, (int, float, str, bool)) else val


def _sheet_to_records(df):
    """Convert a DataFrame to list of dicts with cleaned values."""
    records = []
    for _, row in df.iterrows():
        records.append({str(k): _clean(v) for k, v in row.items()})
    return records


def parse_ejari_workbook(filepath):
    """Parse the Ejari ODS summary workbook into structured sections.

    Returns a dict with one key per sheet, each containing structured data
    ready for frontend rendering.

    ── Framework §17 exemption ────────────────────────────────────────────
    Ejari is an `ejari_summary` analysis_type — the ODS workbook is
    PRE-COMPUTED by the data provider. Every rate, PAR bucket, collection
    metric, etc. arrives already aggregated; this parser only reshapes them
    for the frontend. The §17 "population discipline" rules (total_originated
    vs active_outstanding vs clean_book etc.) apply to functions that
    COMPUTE rates from a raw tape — they do not apply here because we
    never touch individual loans.

    What the upstream provider's populations are (e.g., whether PAR 30+ is
    over active pool or lifetime) is documented in the workbook's own
    Notes sheet and surfaced in `core/methodology_ejari.py`. If that
    convention ever needs to change, the fix lives upstream (request a
    different aggregation) not here.

    For the same reason, the meta-audit walker in
    `tests/test_population_discipline_meta_audit.py` does not include
    Ejari functions in its rotation — no `_ejari_functions()` entry
    exists, intentionally.
    """
    xls = pd.ExcelFile(filepath, engine='odf')
    result = {}

    # ── Portfolio Overview ────────────────────────────────────────────────
    if 'Portfolio_Overview' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Portfolio_Overview', header=None)
        overview = {'report_date': None, 'key_metrics': {}, 'dpd_distribution': []}

        for _, row in df.iterrows():
            vals = [_clean(row.iloc[i]) if i < len(row) else None for i in range(6)]
            if vals[1] == 'Report_Date' and vals[2]:
                overview['report_date'] = vals[2]
            # Key metrics
            for label, keys in [
                ('Total Contracts', 'total_contracts'),
                ('Active Loans', 'active_loans'),
                ('Matured / Closed Loans', 'matured_loans'),
                ('Total Originated (USD)', 'total_originated'),
                ('Total Funded (USD)', 'total_funded'),
                ('Outstanding Principal (USD)', 'outstanding_principal'),
                ('Outstanding Fee (USD)', 'outstanding_fee'),
                ('Total Collections (USD)', 'total_collections'),
                ('PAR 30+', 'par30'),
                ('PAR 60+', 'par60'),
                ('PAR 90+', 'par90'),
                ('PAR 180+', 'par180'),
            ]:
                if vals[1] == label and vals[2] is not None:
                    overview['key_metrics'][keys] = _clean(vals[2])

            # DPD distribution rows
            if vals[1] and vals[1] not in ('DPD Bucket', 'Metric', 'Key Metrics',
                                            'DPD Distribution (Active Loans)', 'TOTAL',
                                            'Report_Date', None) and vals[2] is not None:
                if vals[1] in ('Current', '1-30', '31-60', '61-90', '91-120',
                               '121-180', '181-365', '365+', 'Current_At Date'):
                    overview['dpd_distribution'].append({
                        'bucket': str(vals[1]),
                        'loans': _clean(vals[2]),
                        'outstanding': _clean(vals[3]),
                        'pct_loans': _clean(vals[4]),
                        'pct_outstanding': _clean(vals[5]),
                    })

        result['portfolio_overview'] = overview

    # ── Monthly Cohort ────────────────────────────────────────────────────
    if 'Monthly_Cohort' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Monthly_Cohort', header=None)
        cohorts = []
        header_row = None
        for i, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(16)]
            if vals[0] == 'Vintage' or vals[1] == 'Cohort':
                header_row = i
                continue
            if header_row is not None and vals[1] and vals[1] != 'TOTAL' and vals[2] is not None:
                cohorts.append({
                    'vintage': str(vals[0]) if vals[0] else '',
                    'cohort': str(vals[1]),
                    'loans': _clean(vals[2]),
                    'active': _clean(vals[3]),
                    'originated': _clean(vals[4]),
                    'funded': _clean(vals[5]),
                    'outstanding': _clean(vals[6]),
                    'collections': _clean(vals[7]),
                    'coll_pct': _clean(vals[8]),
                    'par30': _clean(vals[9]),
                    'par60': _clean(vals[10]),
                    'par90': _clean(vals[11]),
                    'par180': _clean(vals[12]),
                    'avg_simah': _clean(vals[13]),
                    'avg_salary': _clean(vals[14]),
                    'avg_ticket': _clean(vals[15]),
                })
            elif vals[1] == 'TOTAL':
                cohorts.append({
                    'vintage': '', 'cohort': 'TOTAL',
                    'loans': _clean(vals[2]), 'active': _clean(vals[3]),
                    'originated': _clean(vals[4]), 'funded': _clean(vals[5]),
                    'outstanding': _clean(vals[6]), 'collections': _clean(vals[7]),
                    'coll_pct': _clean(vals[8]),
                    'par30': None, 'par60': None, 'par90': None, 'par180': None,
                    'avg_simah': None, 'avg_salary': None, 'avg_ticket': None,
                })
        result['monthly_cohort'] = cohorts

    # ── Cohort Loss Waterfall ─────────────────────────────────────────────
    if 'Cohort_Loss_Waterfall' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Cohort_Loss_Waterfall', header=None)
        waterfall = []
        parsing = False
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(12)]
            if vals[0] == 'Cohort' and vals[1] == 'Vint':
                parsing = True
                continue
            if parsing and vals[0] and vals[0] != 'TOTAL':
                waterfall.append({
                    'cohort': str(vals[0]),
                    'vintage': str(vals[1]) if vals[1] else '',
                    'disbursed': _clean(vals[2]),
                    'gross_default': _clean(vals[3]),
                    'default_rate': _clean(vals[4]),
                    'fraud_amount': _clean(vals[5]),
                    'non_fraud_default': _clean(vals[6]),
                    'recovery': _clean(vals[7]),
                    'net_loss': _clean(vals[8]),
                    'net_loss_rate': _clean(vals[9]),
                    'fraud_pct': _clean(vals[10]),
                    'recovery_rate_ex_fraud': _clean(vals[11]),
                })
            elif parsing and vals[0] == 'TOTAL':
                waterfall.append({
                    'cohort': 'TOTAL', 'vintage': '',
                    'disbursed': _clean(vals[2]), 'gross_default': _clean(vals[3]),
                    'default_rate': _clean(vals[4]), 'fraud_amount': _clean(vals[5]),
                    'non_fraud_default': _clean(vals[6]), 'recovery': _clean(vals[7]),
                    'net_loss': _clean(vals[8]), 'net_loss_rate': _clean(vals[9]),
                    'fraud_pct': _clean(vals[10]), 'recovery_rate_ex_fraud': _clean(vals[11]),
                })
                break
        result['cohort_loss_waterfall'] = waterfall

    # ── Roll Rates ────────────────────────────────────────────────────────
    if 'Roll_Rates' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Roll_Rates', header=None)
        roll_rates = []
        parsing = False
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(11)]
            if vals[0] == 'DPD Bucket':
                parsing = True
                continue
            if parsing and vals[0]:
                roll_rates.append({
                    'bucket': str(vals[0]),
                    'loans': _clean(vals[1]),
                    'outstanding': _clean(vals[2]),
                    'pct_outstanding': _clean(vals[3]),
                    'avg_dpd': _clean(vals[4]),
                    'avg_days_since_pay': _clean(vals[5]),
                    'pct_paying_30d': _clean(vals[6]),
                    'pct_paying_60d': _clean(vals[7]),
                    'pct_no_pay_90d': _clean(vals[8]),
                    'implied_cure_rate': _clean(vals[9]),
                    'implied_roll_rate': _clean(vals[10]),
                })
        result['roll_rates'] = roll_rates

    # ── Historical Performance ────────────────────────────────────────────
    if 'Historical_Performance' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Historical_Performance', header=None)
        perf = []
        parsing = False
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(12)]
            if vals[0] == 'Vintage' and vals[1] == 'Period':
                parsing = True
                continue
            if vals[0] == 'Cumulative Curves':
                break
            if parsing and vals[0] and vals[0] not in ('NaN', 'None', ''):
                perf.append({
                    'vintage': str(vals[0]),
                    'period': str(vals[1]) if vals[1] else '',
                    'disbursed': _clean(vals[2]),
                    'default_90dpd': _clean(vals[3]),
                    'fraud': _clean(vals[4]),
                    'non_fraud_default': _clean(vals[5]),
                    'recovery': _clean(vals[6]),
                    'recovery_rate': _clean(vals[7]),
                    'recovery_rate_ex_fraud': _clean(vals[8]),
                    'gross_default_pct': _clean(vals[9]),
                    'net_default_pct': _clean(vals[10]),
                    'lgd': _clean(vals[11]),
                })
        result['historical_performance'] = perf

    # ── Segment Analysis ──────────────────────────────────────────────────
    if 'Segment_Analysis' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Segment_Analysis', header=None)
        segments = {}
        current_section = None
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(10)]
            # Section headers
            for section_name, key in [
                ('By Use Case', 'use_case'), ('By Employment Sector', 'employment'),
                ('By Region', 'region'), ('By Gender', 'gender'),
                ('By Marital Status', 'marital'), ('By Payment Scheme', 'payment_scheme'),
            ]:
                if vals[0] == section_name:
                    current_section = key
                    segments[key] = []
                    break
            if vals[0] == 'Segment' and current_section:
                continue  # header row
            if current_section and vals[0] and vals[1] is not None and vals[0] != 'Segment':
                segments[current_section].append({
                    'segment': str(vals[0]),
                    'loans': _clean(vals[1]),
                    'active': _clean(vals[2]),
                    'originated': _clean(vals[3]),
                    'outstanding': _clean(vals[4]),
                    'coll_pct': _clean(vals[5]),
                    'par30': _clean(vals[6]),
                    'par90': _clean(vals[7]),
                    'avg_simah': _clean(vals[8]),
                    'avg_salary': _clean(vals[9]),
                })
        result['segment_analysis'] = segments

    # ── Credit Quality Trends ─────────────────────────────────────────────
    if 'Credit_Quality_Trends' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Credit_Quality_Trends', header=None)
        trends = []
        parsing = False
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(13)]
            if vals[0] == 'Cohort' and vals[1] == 'Vint':
                parsing = True
                continue
            if parsing and vals[0] and vals[2] is not None:
                trends.append({
                    'cohort': str(vals[0]),
                    'vintage': str(vals[1]) if vals[1] else '',
                    'loans': _clean(vals[2]),
                    'avg_simah': _clean(vals[3]),
                    'med_simah': _clean(vals[4]),
                    'avg_salary': _clean(vals[5]),
                    'med_salary': _clean(vals[6]),
                    'avg_ticket': _clean(vals[7]),
                    'avg_dbr': _clean(vals[8]),
                    'pct_govt': _clean(vals[9]),
                    'pct_female': _clean(vals[10]),
                    'pct_married': _clean(vals[11]),
                    'avg_term': _clean(vals[12]),
                })
        result['credit_quality_trends'] = trends

    # ── Collections by Month ──────────────────────────────────────────────
    if 'Collections_by_Month' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Collections_by_Month', header=None)
        coll_month = []
        parsing = False
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(15)]
            if vals[0] == 'Month' and vals[1] == 'Total Due':
                parsing = True
                continue
            if parsing and vals[0] and vals[0] != 'TOTAL':
                coll_month.append({
                    'month': str(vals[0]),
                    'total_due': _clean(vals[1]),
                    'total_paid': _clean(vals[2]),
                    'coll_pct': _clean(vals[4]),
                    'early': _clean(vals[5]),
                    '0_15d': _clean(vals[6]),
                    '15_30d': _clean(vals[7]),
                    '30_45d': _clean(vals[8]),
                    '45_60d': _clean(vals[9]),
                    '60_90d': _clean(vals[10]),
                    '90_120d': _clean(vals[11]),
                    '120_150d': _clean(vals[12]),
                    '150_180d': _clean(vals[13]),
                    '180_plus': _clean(vals[14]),
                })
        result['collections_by_month'] = coll_month

    # ── Collections by Origination ────────────────────────────────────────
    if 'Collections_by_Origination' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Collections_by_Origination', header=None)
        coll_orig = []
        parsing = False
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(15)]
            if vals[0] == 'Month' and vals[1] == 'Total Due':
                parsing = True
                continue
            if parsing and vals[0] and vals[0] != 'TOTAL':
                coll_orig.append({
                    'month': str(vals[0]),
                    'total_due': _clean(vals[1]),
                    'total_paid': _clean(vals[2]),
                    'coll_pct': _clean(vals[3]),
                    'early': _clean(vals[4]),
                    '0_15d': _clean(vals[5]),
                    '15_30d': _clean(vals[6]),
                    '30_45d': _clean(vals[7]),
                    '45_60d': _clean(vals[8]),
                    '60_90d': _clean(vals[9]),
                    '90_120d': _clean(vals[10]),
                    '120_150d': _clean(vals[11]),
                    '150_180d': _clean(vals[12]),
                    '180_plus': _clean(vals[13]),
                    'fraud': str(vals[14]) if vals[14] else '',
                })
        result['collections_by_origination'] = coll_orig

    # ── Najiz & Legal ─────────────────────────────────────────────────────
    if 'Najiz_&_Legal' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Najiz_&_Legal', header=None)
        najiz = []
        parsing = False
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(12)]
            if vals[0] == 'Vintage' and vals[1] == '# Cases':
                parsing = True
                continue
            if parsing and vals[0] and vals[0] != 'TOTAL':
                najiz.append({
                    'vintage': str(vals[0]),
                    'cases': _clean(vals[1]),
                    'executions': _clean(vals[2]),
                    'exec_rate': _clean(vals[3]),
                    'exec_value': _clean(vals[4]),
                    'recovery': _clean(vals[5]),
                    'rec_exec_rate': _clean(vals[6]),
                    'avg_rec_case': _clean(vals[7]),
                    'fraud_writeoff': _clean(vals[8]),
                    'fraud_recovery': _clean(vals[9]),
                    'fraud_recovery_rate': _clean(vals[10]),
                })
            elif parsing and vals[0] == 'TOTAL':
                najiz.append({
                    'vintage': 'TOTAL',
                    'cases': _clean(vals[1]), 'executions': _clean(vals[2]),
                    'exec_rate': _clean(vals[3]), 'exec_value': _clean(vals[4]),
                    'recovery': _clean(vals[5]), 'rec_exec_rate': _clean(vals[6]),
                    'avg_rec_case': _clean(vals[7]), 'fraud_writeoff': _clean(vals[8]),
                    'fraud_recovery': _clean(vals[9]), 'fraud_recovery_rate': _clean(vals[10]),
                })
                break
        result['najiz_legal'] = najiz

    # ── Write-offs & Fraud ────────────────────────────────────────────────
    if 'Write-offs_&_Fraud' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Write-offs_&_Fraud', header=None)
        wo = {'summary': {}, 'by_reason': [], 'by_cohort': []}
        section = None
        for _, row in df.iterrows():
            vals = [_clean(row.iloc[j]) if j < len(row) else None for j in range(11)]
            if vals[0] == 'Write-off Summary':
                section = 'summary'
                continue
            if vals[0] == 'By Reason Code':
                section = 'reason'
                continue
            if vals[0] == 'Write-offs by Monthly Cohort':
                section = 'cohort'
                continue
            if vals[0] == 'Loan-Level Detail':
                break

            if section == 'summary' and vals[0] == 'Metric':
                continue
            if section == 'summary' and vals[0] and vals[1]:
                wo['summary'][str(vals[0])] = {
                    'all': _clean(vals[1]),
                    'fraud': _clean(vals[2]),
                    'credit': _clean(vals[3]),
                }
            if section == 'reason' and vals[0] == 'Reason Code':
                continue
            if section == 'reason' and vals[0] and vals[1] is not None and vals[0] != 'TOTAL':
                wo['by_reason'].append({
                    'reason': str(vals[0]),
                    'loans': _clean(vals[1]),
                    'orig_principal': _clean(vals[2]),
                    'os_principal': _clean(vals[3]),
                    'os_fee': _clean(vals[4]),
                    'total_os': _clean(vals[5]),
                    'pct_wo': _clean(vals[6]),
                    'type': str(vals[7]) if vals[7] else '',
                })
            if section == 'cohort' and vals[0] == 'Cohort':
                continue
            if section == 'cohort' and vals[0] and vals[1] is not None:
                wo['by_cohort'].append({
                    'cohort': str(vals[0]),
                    'vintage': str(vals[1]) if vals[1] else '',
                    'wo_count': _clean(vals[2]),
                    'fraud_count': _clean(vals[3]),
                    'credit_count': _clean(vals[4]),
                    'wo_os': _clean(vals[5]),
                    'fraud_os': _clean(vals[6]),
                    'credit_os': _clean(vals[7]),
                })

        result['writeoffs_fraud'] = wo

    # ── Data Notes ────────────────────────────────────────────────────────
    if 'Data_Notes' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='Data_Notes', header=None)
        notes = []
        for _, row in df.iterrows():
            val = _clean(row.iloc[0])
            if val and val != 'None':
                notes.append(str(val))
        result['data_notes'] = notes

    return result
