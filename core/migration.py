"""
core/migration.py
Multi-snapshot analysis: roll-rate migration matrices, cure rates, transition probabilities.
Pure computation — no FastAPI, no I/O.
"""
import pandas as pd
import numpy as np


MIGRATION_BUCKETS = [
    ('0-30',    0,   30),
    ('31-60',   31,  60),
    ('61-90',   61,  90),
    ('91-180',  91,  180),
    ('180+',    181, 99999),
]

BUCKET_ORDER = ['Paid', '0-30', '31-60', '61-90', '91-180', '180+']


def _assign_bucket(days, status):
    """Assign an aging bucket based on days outstanding and status."""
    if status == 'Completed':
        return 'Paid'
    if pd.isna(days):
        return '180+'
    for label, lo, hi in MIGRATION_BUCKETS:
        if lo <= days <= hi:
            return label
    return '180+'


def compute_roll_rates(old_df, new_df, as_of_old, as_of_new):
    """
    Build transition probability matrix from two snapshots.

    For each deal present in both snapshots:
    1. Compute aging bucket at each snapshot date
    2. Build transition matrix: P[bucket_old → bucket_new]
    3. Compute cure rates (% moving from aged → paid/current)

    Returns: transition matrix, cure rates, deal-level transitions.
    """
    old_date = pd.Timestamp(as_of_old)
    new_date = pd.Timestamp(as_of_new)

    # Find ID column — handle name mismatches across tapes
    id_candidates = ['ID', 'Id', 'id', 'Deal ID', 'Deal Id', 'deal_id', 'Reference']

    # First try exact match
    id_col = None
    for candidate in id_candidates:
        if candidate in old_df.columns and candidate in new_df.columns:
            id_col = candidate
            break

    # If no exact match, try renaming common variants to a shared name
    if not id_col:
        old_id = next((c for c in id_candidates if c in old_df.columns), None)
        new_id = next((c for c in id_candidates if c in new_df.columns), None)
        if old_id and new_id:
            # Rename both to a common key
            id_col = '_merge_id'
            old_df = old_df.copy()
            new_df = new_df.copy()
            old_df[id_col] = old_df[old_id]
            new_df[id_col] = new_df[new_id]

    if not id_col:
        return {
            'matrix': [],
            'cure_rates': {},
            'summary': {'error': 'No common ID column found between snapshots'},
        }

    # Compute aging bucket for each deal in each snapshot (copy first to avoid mutating inputs)
    old = old_df.copy()
    if 'Deal date' in old.columns:
        old['Deal date'] = pd.to_datetime(old['Deal date'], errors='coerce', format='mixed')
    old['days_old'] = (old_date - old['Deal date']).dt.days
    old['bucket_old'] = old.apply(lambda r: _assign_bucket(r['days_old'], r['Status']), axis=1)

    new = new_df.copy()
    if 'Deal date' in new.columns:
        new['Deal date'] = pd.to_datetime(new['Deal date'], errors='coerce', format='mixed')
    new['days_new'] = (new_date - new['Deal date']).dt.days
    new['bucket_new'] = new.apply(lambda r: _assign_bucket(r['days_new'], r['Status']), axis=1)

    # Merge on ID
    merged = old[[id_col, 'bucket_old', 'Status']].merge(
        new[[id_col, 'bucket_new', 'Status']],
        on=id_col,
        suffixes=('_old', '_new'),
    )

    if merged.empty:
        return {
            'matrix': [],
            'cure_rates': {},
            'summary': {'error': 'No matching deals found between snapshots'},
        }

    # Build transition matrix
    matrix_rows = []
    for from_bucket in BUCKET_ORDER:
        from_deals = merged[merged['bucket_old'] == from_bucket]
        total = len(from_deals)
        if total == 0:
            continue

        row = {'from_bucket': from_bucket, 'total': total}
        for to_bucket in BUCKET_ORDER:
            to_deals = from_deals[from_deals['bucket_new'] == to_bucket]
            count = len(to_deals)
            row[f'to_{to_bucket}'] = count
            row[f'pct_{to_bucket}'] = round(count / total * 100, 1) if total else 0

        matrix_rows.append(row)

    # Compute cure rates (% moving from delinquent to Paid or improved bucket)
    cure_rates = {}
    delinquent_buckets = ['61-90', '91-180', '180+']
    for bucket in delinquent_buckets:
        delinquent = merged[merged['bucket_old'] == bucket]
        total = len(delinquent)
        if total == 0:
            cure_rates[bucket] = {'total': 0, 'cured': 0, 'cure_rate': 0}
            continue

        # Cured = moved to Paid or improved (lower) bucket
        bucket_idx = BUCKET_ORDER.index(bucket)
        cured = delinquent[delinquent['bucket_new'].apply(
            lambda b: BUCKET_ORDER.index(b) < bucket_idx if b in BUCKET_ORDER else False
        )]
        cure_rates[bucket] = {
            'total':     int(total),
            'cured':     int(len(cured)),
            'cure_rate': round(len(cured) / total * 100, 1),
        }

    # Summary stats
    total_deals = len(merged)
    improved = len(merged[merged.apply(
        lambda r: BUCKET_ORDER.index(r['bucket_new']) < BUCKET_ORDER.index(r['bucket_old'])
        if r['bucket_old'] in BUCKET_ORDER and r['bucket_new'] in BUCKET_ORDER else False,
        axis=1
    )])
    worsened = len(merged[merged.apply(
        lambda r: BUCKET_ORDER.index(r['bucket_new']) > BUCKET_ORDER.index(r['bucket_old'])
        if r['bucket_old'] in BUCKET_ORDER and r['bucket_new'] in BUCKET_ORDER else False,
        axis=1
    )])
    stable = total_deals - improved - worsened

    return {
        'matrix': matrix_rows,
        'cure_rates': cure_rates,
        'summary': {
            'total_matched_deals': total_deals,
            'improved':            int(improved),
            'stable':              int(stable),
            'worsened':            int(worsened),
            'improved_pct':        round(improved / total_deals * 100, 1) if total_deals else 0,
            'worsened_pct':        round(worsened / total_deals * 100, 1) if total_deals else 0,
            'old_snapshot':        as_of_old,
            'new_snapshot':        as_of_new,
        },
    }
