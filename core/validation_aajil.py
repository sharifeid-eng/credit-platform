"""
Aajil SME Trade Credit — Tape Validation
==========================================
Single-tape data quality checks for Aajil loan tapes.

Usage:
    from core.validation_aajil import validate_aajil_tape
    result = validate_aajil_tape(df)
"""

import pandas as pd
import numpy as np


def validate_aajil_tape(df):
    """Run Aajil-specific data quality checks.

    Returns dict with keys: critical, warnings, info, passed, total_rows
    """
    critical = []
    warnings = []
    info = []
    n = len(df)

    # ── Critical checks ──────────────────────────────────────────────
    # 1. Duplicate Transaction IDs
    dupes = df['Transaction ID'].dropna().duplicated()
    if dupes.any():
        critical.append(f"{dupes.sum()} duplicate Transaction IDs found")

    # 2. Missing Transaction IDs
    missing_id = df['Transaction ID'].isna().sum()
    if missing_id > 0:
        critical.append(f"{missing_id} rows with missing Transaction ID")

    # 3. Missing Invoice Date
    missing_date = df['Invoice Date'].isna().sum()
    if missing_date > 0:
        critical.append(f"{missing_date} rows with missing Invoice Date")

    # ── Warning checks ───────────────────────────────────────────────
    # 4. Negative Bill Notional
    neg_bill = (df['Bill Notional'].fillna(0) < 0).sum()
    if neg_bill > 0:
        warnings.append(f"{neg_bill} deals with negative Bill Notional")

    # 5. Negative Realised Amount
    neg_real = (df['Realised Amount'].fillna(0) < 0).sum()
    if neg_real > 0:
        warnings.append(f"{neg_real} deals with negative Realised Amount")

    # 6. Sale Overdue > Sale Total
    if 'Sale Overdue Amount' in df.columns and 'Sale Total' in df.columns:
        overdue_exceeds = (df['Sale Overdue Amount'].fillna(0) > df['Sale Total'].fillna(0) * 1.01).sum()
        if overdue_exceeds > 0:
            warnings.append(f"{overdue_exceeds} deals where Sale Overdue Amount > Sale Total")

    # 7. Paid installments > Total installments
    if 'Paid No of Installments' in df.columns and 'Total No. of Installments' in df.columns:
        paid_gt_total = (df['Paid No of Installments'].fillna(0) > df['Total No. of Installments'].fillna(0)).sum()
        if paid_gt_total > 0:
            warnings.append(f"{paid_gt_total} deals where Paid installments > Total installments")

    # 8. Future Invoice Dates
    today = pd.Timestamp.now().normalize()
    future = (df['Invoice Date'].dropna() > today).sum()
    if future > 0:
        warnings.append(f"{future} deals with Invoice Date in the future")

    # 9. Deal Tenure <= 0
    if 'Deal Tenure' in df.columns:
        bad_tenure = (df['Deal Tenure'].dropna() <= 0).sum()
        if bad_tenure > 0:
            warnings.append(f"{bad_tenure} deals with Deal Tenure <= 0")

    # 10. Written Off with Receivable > 0
    wo = df[df['Realised Status'] == 'Written Off']
    if len(wo) > 0:
        wo_with_recv = (wo['Receivable Amount'].fillna(0) > 0).sum()
        if wo_with_recv > 0:
            warnings.append(f"{wo_with_recv} Written Off deals still have Receivable Amount > 0")

    # ── Info checks ──────────────────────────────────────────────────
    # Status distribution
    status_dist = df['Realised Status'].value_counts().to_dict()
    info.append(f"Status distribution: {status_dist}")

    # Deal Type distribution
    dt_dist = df['Deal Type'].value_counts().to_dict()
    info.append(f"Deal Type distribution: {dt_dist}")

    # Date range
    min_date = df['Invoice Date'].min()
    max_date = df['Invoice Date'].max()
    info.append(f"Date range: {min_date:%Y-%m-%d} to {max_date:%Y-%m-%d}")

    # Customer Industry coverage
    if 'Customer Industry' in df.columns:
        missing_ind = df['Customer Industry'].isna().sum()
        pct = missing_ind / n * 100
        info.append(f"Customer Industry: {pct:.1f}% missing ({missing_ind}/{n})")

    # Unique customers
    info.append(f"Unique customers: {df['Unique Customer Code'].nunique()}")

    # Amount ranges
    info.append(f"Bill Notional: SAR {df['Bill Notional'].min():,.0f} to SAR {df['Bill Notional'].max():,.0f}")
    info.append(f"Deal Tenure: {df['Deal Tenure'].dropna().min():.0f} to {df['Deal Tenure'].dropna().max():.0f} months")

    passed = len(critical) == 0
    return {
        'critical': critical,
        'warnings': warnings,
        'info': info,
        'passed': passed,
        'total_rows': n,
    }
