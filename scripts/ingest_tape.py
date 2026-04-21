"""Ingest a tape file (CSV/Excel) as a DB snapshot.

Each tape file becomes one Snapshot row + N Invoice rows (+ their Payment rows).
Every column that is NOT part of the core relational schema is preserved in
`Invoice.extra_data` as a JSONB payload, KEYED BY THE ORIGINAL TAPE COLUMN NAME.
This means when a new analytical column is added to a tape (e.g. Apr 15's
`Expected collection days`, `Collection days so far`, `Provider`), it flows
through to DB and back into the DataFrame automatically — no schema migration,
no db_loader change required.

Usage:
    # Ingest one file:
    python scripts/ingest_tape.py --company klaim --product UAE_healthcare \\
        --file 2026-04-15_uae_healthcare.csv

    # Ingest every tape file for a product:
    python scripts/ingest_tape.py --company klaim --product UAE_healthcare --all

    # Ingest every tape file for every product:
    python scripts/ingest_tape.py --all

    # Dry run (no writes):
    python scripts/ingest_tape.py --all --dry-run

    # Force re-ingest (deletes existing snapshot + its invoices/payments):
    python scripts/ingest_tape.py --company klaim --product UAE_healthcare \\
        --file 2026-04-15_uae_healthcare.csv --force

Idempotency: a snapshot is keyed by (product_id, name). The name is the tape
filename without its extension. Re-running without --force is a no-op for any
snapshot that already exists; --force deletes and re-creates it.
"""
import argparse
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine, SessionLocal, Base
from core.models import Organization, Product, Snapshot, Invoice, Payment, FacilityConfig
from core.loader import get_companies, get_products, get_snapshots, load_snapshot
from core.config import load_config

try:
    from core.loader import load_silq_snapshot
except ImportError:
    load_silq_snapshot = None


# Core relational columns — NOT duplicated in extra_data.
_KLAIM_CORE_COLS = {
    'Deal ID', 'Purchase value', 'Status', 'Group', 'Payer', 'Deal date',
    # Duplicates / computed: these are reconstructed by the loader from payments,
    # so we strip them from extra_data to avoid stale shadow copies.
    'Collected till date',
}
_SILQ_CORE_COLS = {
    'Deal ID', 'Disbursed_Amount (SAR)', 'Loan_Status', 'Shop_ID',
    'Disbursement_Date', 'Repayment_Deadline',
    # Reconstructed from payments
    'Amt_Repaid',
}


def main():
    ap = argparse.ArgumentParser(description="Ingest tape file(s) as DB snapshot(s).")
    ap.add_argument('--company', help='Company name (e.g. klaim)')
    ap.add_argument('--product', help='Product name (e.g. UAE_healthcare)')
    ap.add_argument('--file', help='Specific tape filename (default: all tapes for product)')
    ap.add_argument('--all', action='store_true', help='Ingest all tapes for all companies/products')
    ap.add_argument('--dry-run', action='store_true', help='Report what would be ingested without writing')
    ap.add_argument('--force', action='store_true', help='Delete + recreate an existing snapshot')
    args = ap.parse_args()

    if engine is None:
        print("ERROR: DATABASE_URL not set. Cannot ingest.", file=sys.stderr)
        sys.exit(1)

    # Ensure schema is up to date before any writes.
    if not args.dry_run:
        Base.metadata.create_all(engine)

    # Decide scope
    if args.all and not args.company:
        scope = _all_scope()
    elif args.company and args.product:
        if args.file:
            scope = [(args.company, args.product, [args.file])]
        else:
            tapes = [s['filename'] for s in get_snapshots(args.company, args.product)]
            scope = [(args.company, args.product, tapes)]
    else:
        ap.error("provide either --all, or --company + --product [+ --file]")
        return

    db = SessionLocal() if not args.dry_run else None
    try:
        total_snaps, total_rows = 0, 0
        for company, product, tape_files in scope:
            for tape_file in tape_files:
                n_snap, n_rows = _ingest_one(
                    db, company, product, tape_file,
                    dry_run=args.dry_run, force=args.force,
                )
                total_snaps += n_snap
                total_rows += n_rows
        if not args.dry_run:
            db.commit()
        print(f"\nDone. Snapshots created/updated: {total_snaps}. Rows written: {total_rows}.")
    except Exception:
        if db is not None:
            db.rollback()
        raise
    finally:
        if db is not None:
            db.close()


def _all_scope():
    """Every (company, product, tape_files) across the platform."""
    out = []
    for company in get_companies():
        co = company['name'] if isinstance(company, dict) else company
        for product in get_products(co):
            pname = product['name'] if isinstance(product, dict) else product
            tapes = [s['filename'] for s in get_snapshots(co, pname)]
            if tapes:
                out.append((co, pname, tapes))
    return out


def _ingest_one(db, company, product_name, tape_filename, *, dry_run, force):
    """Ingest a single tape file. Returns (snapshots_touched, rows_written)."""
    config = load_config(company, product_name) or {}
    analysis_type = config.get('analysis_type', 'klaim')

    # Only tape-readable analysis types for now. Ejari / Tamara / Aajil
    # use different ingestion patterns (pre-computed summaries, data rooms).
    if analysis_type not in ('klaim', 'silq'):
        print(f"  SKIP {company}/{product_name}/{tape_filename} — "
              f"analysis_type={analysis_type!r} doesn't use tape ingestion")
        return 0, 0

    # Parse date from filename prefix (YYYY-MM-DD_*)
    date_prefix = tape_filename.split('_')[0]
    try:
        taken_at = datetime.strptime(date_prefix, '%Y-%m-%d').date()
    except ValueError:
        print(f"  SKIP {tape_filename} — filename doesn't start with YYYY-MM-DD_")
        return 0, 0

    snapshot_name = os.path.splitext(tape_filename)[0]  # filename without extension

    # Resolve filepath — get_snapshots returns {filename, filepath, date}
    snaps = get_snapshots(company, product_name)
    match = next((s for s in snaps if s['filename'] == tape_filename), None)
    if not match:
        print(f"  SKIP {tape_filename} — not found under data/{company}/{product_name}/")
        return 0, 0

    print(f"\n== {company}/{product_name}/{snapshot_name} ({taken_at}) ==")
    if dry_run:
        # Just report row count and column list
        df = _load_df(match['filepath'], analysis_type)
        print(f"  DRY-RUN: {len(df)} rows, {len(df.columns)} columns. Would be ingested.")
        return 1, len(df)

    # Resolve or create Organization + Product
    org = db.query(Organization).filter_by(name=company).first()
    if not org:
        org = Organization(id=uuid.uuid4(), name=company)
        db.add(org)
        db.flush()
        print(f"  Created organization: {company}")

    prod = db.query(Product).filter_by(org_id=org.id, name=product_name).first()
    if not prod:
        prod = Product(
            id=uuid.uuid4(),
            org_id=org.id,
            name=product_name,
            currency=config.get('currency', 'USD'),
            analysis_type=analysis_type,
        )
        db.add(prod)
        db.flush()
        print(f"  Created product: {product_name}")

    # Facility config (singleton per product — independent of snapshots)
    if not db.query(FacilityConfig).filter_by(product_id=prod.id).first():
        fc = FacilityConfig(
            id=uuid.uuid4(),
            product_id=prod.id,
            advance_rates=config.get('advance_rates', {"default": 0.90}),
            covenants=config.get('covenants', []),
        )
        db.add(fc)
        print("  Created facility config")

    # Snapshot — check if exists
    existing = db.query(Snapshot).filter_by(product_id=prod.id, name=snapshot_name).first()
    if existing:
        if not force:
            print(f"  SKIP — snapshot {snapshot_name!r} already exists (use --force to re-ingest)")
            return 0, 0
        print(f"  --force: deleting existing snapshot {snapshot_name!r} + its rows")
        db.delete(existing)   # cascades to invoices + payments
        db.flush()

    # Load DataFrame
    df = _load_df(match['filepath'], analysis_type)

    # Create snapshot
    snapshot = Snapshot(
        id=uuid.uuid4(),
        product_id=prod.id,
        name=snapshot_name,
        source='tape',
        taken_at=taken_at,
        ingested_at=datetime.utcnow(),
        row_count=0,  # set after insert
        notes=f'Ingested from {tape_filename}',
    )
    db.add(snapshot)
    db.flush()

    # Bulk-insert invoices
    if analysis_type == 'klaim':
        row_count = _ingest_klaim(db, org, prod, snapshot, df)
    else:
        row_count = _ingest_silq(db, org, prod, snapshot, df)

    snapshot.row_count = row_count
    db.flush()
    print(f"  Ingested {row_count} rows into snapshot {snapshot_name!r}")
    return 1, row_count


def _load_df(filepath, analysis_type):
    if analysis_type == 'silq' and load_silq_snapshot is not None:
        df, _ = load_silq_snapshot(filepath)
    else:
        df = load_snapshot(filepath)
    return df


# ── Per-asset-class ingestion ─────────────────────────────────────────────────

def _ingest_klaim(db, org, prod, snapshot, df):
    """Klaim tape row → Invoice + optional Payment.

    `extra_data` keys use the original tape column names (e.g. 'Expected
    collection days', 'Collection days so far', 'Provider') so the loader
    round-trips them back to the DataFrame without a hand-mapping table.
    """
    count = 0
    for idx, row in df.iterrows():
        inv_id = uuid.uuid4()

        # Extra data = every column except the core relational fields.
        meta = _build_extra_data(df.columns, row, _KLAIM_CORE_COLS)

        inv = Invoice(
            id=inv_id,
            org_id=org.id,
            product_id=prod.id,
            snapshot_id=snapshot.id,
            invoice_number=_safe_str(row.get('Deal ID'), fallback=f'KLAIM-{idx:06d}'),
            amount_due=_safe_float(row.get('Purchase value'), 0),
            currency=prod.currency,
            status=_safe_str(row.get('Status'), 'Executed'),
            customer_name=_safe_str_or_none(row.get('Group')),
            payer_name=_safe_str_or_none(row.get('Payer')),
            invoice_date=_safe_date(row.get('Deal date')),
            due_date=None,
            extra_data=meta if meta else None,
        )
        db.add(inv)

        # Payment proxy: one PARTIAL payment representing Collected till date.
        collected = _safe_float(row.get('Collected till date'), 0)
        if collected > 0:
            pay = Payment(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                snapshot_id=snapshot.id,
                payment_type='PARTIAL',
                payment_amount=collected,
                currency=prod.currency,
                payment_date=_safe_date(row.get('Deal date')),
            )
            db.add(pay)

        count += 1
        if count % 1000 == 0:
            db.flush()
            print(f"      ... {count} invoices")

    db.flush()
    return count


def _ingest_silq(db, org, prod, snapshot, df):
    """SILQ tape row → Invoice + optional Payment. Same extra_data scheme."""
    count = 0
    for idx, row in df.iterrows():
        inv_id = uuid.uuid4()
        meta = _build_extra_data(df.columns, row, _SILQ_CORE_COLS)

        inv = Invoice(
            id=inv_id,
            org_id=org.id,
            product_id=prod.id,
            snapshot_id=snapshot.id,
            invoice_number=_safe_str(row.get('Deal ID'), fallback=f'SILQ-{idx:06d}'),
            amount_due=_safe_float(row.get('Disbursed_Amount (SAR)'), 0),
            currency=prod.currency,
            status=_safe_str(row.get('Loan_Status'), 'Current'),
            customer_name=_safe_str_or_none(row.get('Shop_ID')),
            invoice_date=_safe_date(row.get('Disbursement_Date')),
            due_date=_safe_date(row.get('Repayment_Deadline')),
            extra_data=meta if meta else None,
        )
        db.add(inv)

        repaid = _safe_float(row.get('Amt_Repaid'), 0)
        if repaid > 0:
            pay = Payment(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                snapshot_id=snapshot.id,
                payment_type='PARTIAL',
                payment_amount=repaid,
                currency=prod.currency,
                payment_date=_safe_date(row.get('Last_Collection_Date')),
            )
            db.add(pay)

        count += 1
        if count % 500 == 0:
            db.flush()
            print(f"      ... {count} invoices")

    db.flush()
    return count


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_extra_data(columns, row, core_cols):
    """Collect every non-core column into a JSONB-safe dict keyed by the
    original tape column name. Dates become ISO strings; NaN/None omitted."""
    meta = {}
    for col in columns:
        if col in core_cols:
            continue
        val = row[col]
        if val is None:
            continue
        # pd.isna handles both scalar NaN and NaT
        try:
            if pd.isna(val):
                continue
        except (TypeError, ValueError):
            pass

        # Normalise for JSON
        if isinstance(val, pd.Timestamp):
            meta[col] = val.date().isoformat()
        elif hasattr(val, 'item'):
            # numpy scalars (int64, float64, etc.)
            meta[col] = val.item()
        elif isinstance(val, (int, float, bool, str)):
            meta[col] = val
        else:
            meta[col] = str(val)
    return meta


def _safe_str(val, fallback=''):
    if val is None:
        return fallback
    try:
        if pd.isna(val):
            return fallback
    except (TypeError, ValueError):
        pass
    return str(val)


def _safe_str_or_none(val):
    s = _safe_str(val, fallback='')
    return s or None


def _safe_float(val, fallback=0.0):
    if val is None:
        return float(fallback)
    try:
        if pd.isna(val):
            return float(fallback)
    except (TypeError, ValueError):
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(fallback)


def _safe_date(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    ts = pd.to_datetime(val, errors='coerce')
    if pd.isna(ts):
        return None
    return ts.date()


if __name__ == '__main__':
    main()
