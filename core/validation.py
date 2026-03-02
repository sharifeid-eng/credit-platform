"""
core/validation.py
Single-tape data quality checks — duplicate detection, date sanity,
negative amounts, null checks, logical consistency.
Pure computation — no FastAPI, no I/O.
"""
import pandas as pd
import numpy as np


def validate_tape(df):
    """
    Run comprehensive data quality checks on a single loan tape.
    Returns categorized findings: critical, warning, info.
    """
    critical = []
    warnings = []
    info = []

    total_rows = len(df)
    info.append({
        'check': 'Row Count',
        'detail': f'{total_rows:,} deals in tape',
    })

    # ── 1. Duplicate ID detection ──
    id_col = None
    for candidate in ['ID', 'Id', 'id', 'Reference']:
        if candidate in df.columns:
            id_col = candidate
            break

    if id_col:
        dupes = df[df.duplicated(subset=[id_col], keep=False)]
        dupe_count = len(dupes)
        unique_dupe_ids = dupes[id_col].nunique()
        if dupe_count > 0:
            critical.append({
                'check': 'Duplicate IDs',
                'detail': f'{dupe_count} rows with duplicate {id_col} ({unique_dupe_ids} unique IDs)',
                'sample': list(dupes[id_col].unique()[:5]),
            })
        else:
            info.append({
                'check': 'Duplicate IDs',
                'detail': f'No duplicate {id_col} values found',
            })
    else:
        warnings.append({
            'check': 'No ID Column',
            'detail': 'No ID column found — cannot check for duplicates',
        })

    # ── 2. Date sanity checks ──
    if 'Deal date' in df.columns:
        dates = pd.to_datetime(df['Deal date'], errors='coerce')
        null_dates = dates.isna().sum()
        if null_dates > 0:
            warnings.append({
                'check': 'Null Deal Dates',
                'detail': f'{null_dates} deals have null or unparseable Deal date',
            })

        valid_dates = dates.dropna()
        if len(valid_dates):
            future_dates = valid_dates[valid_dates > pd.Timestamp.now()]
            if len(future_dates):
                critical.append({
                    'check': 'Future Deal Dates',
                    'detail': f'{len(future_dates)} deals have Deal date in the future',
                })

            old_dates = valid_dates[valid_dates < pd.Timestamp('2018-01-01')]
            if len(old_dates):
                warnings.append({
                    'check': 'Very Old Deal Dates',
                    'detail': f'{len(old_dates)} deals have Deal date before 2018',
                })

            info.append({
                'check': 'Date Range',
                'detail': f'Deal dates span {valid_dates.min().strftime("%Y-%m-%d")} to {valid_dates.max().strftime("%Y-%m-%d")}',
            })

    # ── 3. Negative amount detection ──
    amount_cols = ['Purchase value', 'Purchase price', 'Collected till date',
                   'Denied by insurance', 'Pending insurance response',
                   'Gross revenue', 'Setup fee', 'Other fee']
    for col in amount_cols:
        if col in df.columns:
            numeric = pd.to_numeric(df[col], errors='coerce')
            negatives = numeric[numeric < 0]
            if len(negatives) > 0:
                warnings.append({
                    'check': f'Negative {col}',
                    'detail': f'{len(negatives)} deals have negative {col} (min: {negatives.min():,.2f})',
                })

    # ── 4. Null / missing critical fields ──
    critical_cols = ['Purchase value', 'Purchase price', 'Status',
                     'Collected till date', 'Denied by insurance']
    for col in critical_cols:
        if col in df.columns:
            nulls = df[col].isna().sum()
            if nulls > 0:
                warnings.append({
                    'check': f'Null {col}',
                    'detail': f'{nulls} deals have null {col}',
                })
        else:
            critical.append({
                'check': f'Missing Column: {col}',
                'detail': f'Required column {col} not found in tape',
            })

    # ── 5. Collected > Purchase value anomalies ──
    if 'Collected till date' in df.columns and 'Purchase value' in df.columns:
        over_collected = df[
            pd.to_numeric(df['Collected till date'], errors='coerce') >
            pd.to_numeric(df['Purchase value'], errors='coerce') * 1.5
        ]
        if len(over_collected):
            warnings.append({
                'check': 'Over-Collection',
                'detail': f'{len(over_collected)} deals have Collected > 150% of Purchase value',
            })

    # ── 6. Status vs collection consistency ──
    if 'Status' in df.columns and 'Collected till date' in df.columns:
        completed_zero = df[
            (df['Status'] == 'Completed') &
            (pd.to_numeric(df['Collected till date'], errors='coerce') == 0)
        ]
        if len(completed_zero):
            warnings.append({
                'check': 'Completed with Zero Collection',
                'detail': f'{len(completed_zero)} deals marked Completed but have 0 collected',
            })

    # ── 7. Discount range check ──
    if 'Discount' in df.columns:
        disc = pd.to_numeric(df['Discount'], errors='coerce').dropna()
        if len(disc):
            if disc.max() > 1:
                warnings.append({
                    'check': 'Discount > 100%',
                    'detail': f'{len(disc[disc > 1])} deals have Discount > 100% (max: {disc.max():.2%})',
                })
            if disc.min() < 0:
                warnings.append({
                    'check': 'Negative Discount',
                    'detail': f'{len(disc[disc < 0])} deals have negative Discount',
                })

    # ── 8. Status value check ──
    if 'Status' in df.columns:
        valid_statuses = {'Executed', 'Completed'}
        actual = set(df['Status'].dropna().unique())
        unexpected = actual - valid_statuses
        if unexpected:
            warnings.append({
                'check': 'Unexpected Status Values',
                'detail': f'Found unexpected status values: {unexpected}',
            })

        status_counts = df['Status'].value_counts().to_dict()
        info.append({
            'check': 'Status Distribution',
            'detail': f'Status breakdown: {status_counts}',
        })

    # ── 9. Column completeness summary ──
    col_completeness = {}
    for col in df.columns:
        non_null = df[col].notna().sum()
        col_completeness[col] = round(non_null / total_rows * 100, 1)

    low_completeness = {k: v for k, v in col_completeness.items() if v < 90}
    if low_completeness:
        warnings.append({
            'check': 'Low Column Completeness',
            'detail': f'{len(low_completeness)} columns have <90% completeness: {low_completeness}',
        })

    return {
        'critical':  critical,
        'warnings':  warnings,
        'info':      info,
        'passed':    len(critical) == 0,
        'total_rows': total_rows,
        'column_completeness': col_completeness,
    }
