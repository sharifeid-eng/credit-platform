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
        dates = pd.to_datetime(df['Deal date'], errors='coerce', format='mixed')
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

    # ── 9. Duplicate counterparty + amount + date combos ──
    combo_cols = [c for c in ['Group', 'Purchase value', 'Deal date'] if c in df.columns]
    if len(combo_cols) == 3:
        combo_dupes = df[df.duplicated(subset=combo_cols, keep=False)]
        if len(combo_dupes) > 0:
            unique_combos = combo_dupes.groupby(combo_cols).size().reset_index(name='count')
            warnings.append({
                'check': 'Duplicate Counterparty+Amount+Date',
                'detail': (
                    f'{len(combo_dupes)} rows share the same Group + Purchase value + Deal date '
                    f'({len(unique_combos)} unique combinations). Possible double-entry.'
                ),
                'sample': unique_combos.head(3).to_dict(orient='records'),
            })

    # ── 10. Identical amount concentration ──
    if 'Purchase value' in df.columns:
        pv = pd.to_numeric(df['Purchase value'], errors='coerce').dropna()
        if len(pv) > 0:
            val_counts = pv.value_counts()
            top_val = val_counts.index[0]
            top_count = int(val_counts.iloc[0])
            top_pct = top_count / len(pv) * 100
            if top_pct > 5 and top_count > 10:
                warnings.append({
                    'check': 'Identical Amount Concentration',
                    'detail': (
                        f'{top_count} deals ({top_pct:.1f}%) share the same Purchase value of '
                        f'{top_val:,.2f}. May indicate templated or copy-paste entries.'
                    ),
                })

    # ── 11. Deal size outliers (IQR method, 3×IQR fence) ──
    if 'Purchase value' in df.columns:
        pv = pd.to_numeric(df['Purchase value'], errors='coerce').dropna()
        if len(pv) >= 20:
            q1, q3 = pv.quantile(0.25), pv.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                upper = q3 + 3 * iqr
                lower = max(q1 - 3 * iqr, 0)
                outliers = pv[(pv > upper) | (pv < lower)]
                if len(outliers) > 0:
                    warnings.append({
                        'check': 'Deal Size Outliers',
                        'detail': (
                            f'{len(outliers)} deals have Purchase value outside 3×IQR bounds '
                            f'[{lower:,.0f} – {upper:,.0f}]. '
                            f'Max outlier: {outliers.max():,.0f}.'
                        ),
                    })

    # ── 12. Discount outliers (IQR method) ──
    if 'Discount' in df.columns:
        disc = pd.to_numeric(df['Discount'], errors='coerce').dropna()
        disc = disc[(disc >= 0) & (disc <= 1)]
        if len(disc) >= 20:
            q1, q3 = disc.quantile(0.25), disc.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                upper = q3 + 3 * iqr
                lower = max(q1 - 3 * iqr, 0)
                outliers = disc[(disc > upper) | (disc < lower)]
                if len(outliers) > 0:
                    warnings.append({
                        'check': 'Discount Outliers',
                        'detail': (
                            f'{len(outliers)} deals have Discount outside 3×IQR bounds '
                            f'[{lower:.1%} – {upper:.1%}]. '
                            f'Max outlier: {outliers.max():.1%}.'
                        ),
                    })

    # ── 13. Balance identity violations ──
    # Klaim accounting identity (empirically verified):
    #   Paid by insurance + Denied by insurance + Pending insurance response ≡ Purchase value
    # `Collected till date` legitimately exceeds `Paid by insurance` because Collected includes
    # VAT reimbursement and fees received on top of the claim principal — it is NOT part of the
    # three-way identity. Only flag when Paid column is available; gracefully skip otherwise.
    bal_cols = {
        'paid':    'Paid by insurance',
        'denied':  'Denied by insurance',
        'pending': 'Pending insurance response',
        'pv':      'Purchase value',
    }
    if all(c in df.columns for c in bal_cols.values()):
        nums = {k: pd.to_numeric(df[v], errors='coerce').fillna(0) for k, v in bal_cols.items()}
        total_src = nums['paid'] + nums['denied'] + nums['pending']
        tolerance = nums['pv'].abs() * 0.01
        violations = df[((total_src - nums['pv']).abs() > tolerance) & (nums['pv'] > 0)]
        if len(violations) > 0:
            warnings.append({
                'check': 'Balance Identity Violations',
                'detail': (
                    f'{len(violations)} deals where |Paid + Denied + Pending − Purchase value| '
                    f'> 1% of Purchase value. Possible data inconsistency.'
                ),
            })

    # ── 14. Column completeness summary ──
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
