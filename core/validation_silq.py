"""
SILQ-specific data quality validation checks for BNPL/RBF loan tapes.
"""

import pandas as pd
import numpy as np
from datetime import datetime


def validate_silq_tape(df):
    """Run SILQ-specific data quality checks. Returns {critical, warnings, info, passed, total_rows}."""
    critical = []
    warnings = []
    info = []
    n = len(df)

    # 1. Duplicate Deal IDs
    if 'Deal ID' in df.columns:
        dupes = df['Deal ID'].dropna().duplicated()
        n_dupes = int(dupes.sum())
        if n_dupes > 0:
            critical.append(f'{n_dupes} duplicate Deal IDs found')
        else:
            info.append('No duplicate Deal IDs')

    # 2. Negative amounts
    amount_cols = {
        'Disbursed_Amount (SAR)': 'disbursed amounts',
        'Outstanding_Amount (SAR)': 'outstanding amounts',
        'Overdue_Amount (SAR)': 'overdue amounts',
        'Amt_Repaid': 'repaid amounts',
        'Total_Collectable_Amount (SAR)': 'collectable amounts',
        'Margin Collected': 'margin amounts',
        'Principal Collected': 'principal amounts',
    }
    for col, label in amount_cols.items():
        if col in df.columns:
            neg = (df[col] < 0).sum()
            if neg > 0:
                warnings.append(f'{int(neg)} negative {label}')

    # 3. Outstanding > Disbursed (warning, not critical — outstanding includes accrued margin)
    if 'Outstanding_Amount (SAR)' in df.columns and 'Disbursed_Amount (SAR)' in df.columns:
        bad = (df['Outstanding_Amount (SAR)'] > df['Disbursed_Amount (SAR)'] * 1.5).sum()
        if bad > 0:
            warnings.append(f'{int(bad)} loans where outstanding > 150% of disbursed')

    # 4. Overdue > Outstanding
    if 'Overdue_Amount (SAR)' in df.columns and 'Outstanding_Amount (SAR)' in df.columns:
        bad = (df['Overdue_Amount (SAR)'] > df['Outstanding_Amount (SAR)'] + 0.01).sum()
        if bad > 0:
            warnings.append(f'{int(bad)} loans where overdue > outstanding')

    # 5. Amt_Repaid > Total_Collectable (overcollection)
    if 'Amt_Repaid' in df.columns and 'Total_Collectable_Amount (SAR)' in df.columns:
        bad = (df['Amt_Repaid'] > df['Total_Collectable_Amount (SAR)'] + 0.01).sum()
        if bad > 0:
            warnings.append(f'{int(bad)} loans where repaid > collectable (overcollection)')

    # 6. Missing Shop_ID
    if 'Shop_ID' in df.columns:
        missing = df['Shop_ID'].isna().sum()
        if missing > 0:
            warnings.append(f'{int(missing)} loans missing Shop_ID')
        else:
            info.append(f'{int(df["Shop_ID"].nunique())} unique shops')

    # 7. Missing Disbursement_Date
    if 'Disbursement_Date' in df.columns:
        missing = df['Disbursement_Date'].isna().sum()
        if missing > 0:
            critical.append(f'{int(missing)} loans missing Disbursement_Date')

    # 8. Future disbursement dates
    if 'Disbursement_Date' in df.columns:
        today = pd.Timestamp.now().normalize()
        future = (df['Disbursement_Date'] > today).sum()
        if future > 0:
            warnings.append(f'{int(future)} loans with future disbursement dates')

    # 9. Tenure issues
    if 'Tenure' in df.columns:
        bad_tenure = ((df['Tenure'] <= 0) | df['Tenure'].isna()).sum()
        if bad_tenure > 0:
            warnings.append(f'{int(bad_tenure)} loans with zero/negative/missing tenure')

    # 10. Closed loans with outstanding > 0
    if 'Loan_Status' in df.columns and 'Outstanding_Amount (SAR)' in df.columns:
        closed = df[df['Loan_Status'] == 'Closed']
        bad = (closed['Outstanding_Amount (SAR)'] > 0.01).sum()
        if bad > 0:
            warnings.append(f'{int(bad)} closed loans with outstanding > 0')

    # 11. Status distribution (info)
    if 'Loan_Status' in df.columns:
        dist = df['Loan_Status'].value_counts()
        for status, count in dist.items():
            info.append(f'{status}: {int(count)} loans ({count/n*100:.1f}%)')

    # 12. Product distribution (info)
    if 'Product' in df.columns:
        dist = df['Product'].value_counts()
        for prod, count in dist.items():
            info.append(f'{prod}: {int(count)} loans')

    # 13. Multi-sheet source info
    if '_source_sheet' in df.columns:
        sheet_dist = df['_source_sheet'].value_counts()
        info.append(f'Multi-sheet tape: {len(sheet_dist)} data sheet(s) loaded')
        for sheet, count in sheet_dist.items():
            info.append(f'  Sheet "{sheet}": {int(count)} loans')

    # 14. Cross-sheet Deal ID uniqueness
    if '_source_sheet' in df.columns and 'Deal ID' in df.columns:
        cross = df.groupby('Deal ID')['_source_sheet'].nunique()
        cross_dupes = int((cross > 1).sum())
        if cross_dupes > 0:
            critical.append(f'{cross_dupes} Deal IDs appear in multiple sheets')
        else:
            info.append('No cross-sheet Deal ID overlaps')

    passed = len(critical) == 0
    return {
        'critical': critical,
        'warnings': warnings,
        'info': info,
        'passed': passed,
        'total_rows': n,
    }
