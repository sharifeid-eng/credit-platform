"""Database query helpers that return snapshot-scoped DataFrames.

Bridges PostgreSQL and the existing computation engine. Every query is
snapshot-filtered: one snapshot = one point-in-time view of the book. The
same invoice_number can exist in many snapshots with different state at each.

Key design: `Invoice.extra_data` (JSONB) carries every non-core tape column
keyed by the ORIGINAL tape column name. On read, those keys are spread back
onto the DataFrame as columns with the exact same names. New analytical
columns added to a tape flow through the DB automatically — no schema
migration, no loader-mapping change. See scripts/ingest_tape.py for the
write side.

Snapshot resolution:
- `load_from_db(db, co, prod)` with no `snapshot_id` → latest by taken_at.
- `load_from_db(db, co, prod, snapshot_id=...)` → that exact snapshot.
- `load_from_db(db, co, prod, snapshot_name=...)` → by unique (product_id, name).
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.models import Organization, Product, Snapshot, Invoice, Payment, FacilityConfig


# ── Live snapshot helpers (Integration API write path) ──────────────────────

def get_or_create_live_snapshot(db, product: Product, as_of: Optional[date] = None) -> Snapshot:
    """Return today's rolling-daily live snapshot for a product, creating if needed.

    `as_of` defaults to UTC today. Each UTC day gets one `live-YYYY-MM-DD`
    snapshot per product. Same-day Integration API writes all land in that
    snapshot; next-day writes create a new snapshot (prior day is then frozen
    history).

    Idempotent: concurrent first-push-of-the-day collisions are resolved by the
    unique (product_id, name) constraint — the loser re-reads and returns the
    winner's row. Caller must commit or let FastAPI's db dependency commit.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc).date()
    name = f"live-{as_of.isoformat()}"

    existing = db.execute(
        select(Snapshot).where(Snapshot.product_id == product.id, Snapshot.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    snap = Snapshot(
        id=uuid.uuid4(),
        product_id=product.id,
        name=name,
        source='live',
        taken_at=as_of,
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
        row_count=0,
        notes='Rolling daily live snapshot, populated by Integration API writes.',
    )
    db.add(snap)
    try:
        db.flush()
    except Exception:
        # Concurrent create — someone else won the race. Re-read and return theirs.
        db.rollback()
        existing = db.execute(
            select(Snapshot).where(Snapshot.product_id == product.id, Snapshot.name == name)
        ).scalar_one_or_none()
        if existing is None:
            raise
        return existing
    return snap


def is_snapshot_mutable(snapshot: Snapshot, today: Optional[date] = None) -> bool:
    """A snapshot is mutable only when it's the current UTC day's live snapshot.

    This enforces the Integration API's immutability rule: tape snapshots are
    read-only (they represent a frozen book state from a specific upload);
    prior days' live snapshots are read-only (they represent that day's end
    state); only today's live snapshot accepts writes/updates/deletes.
    """
    if snapshot is None or snapshot.source != 'live':
        return False
    if today is None:
        today = datetime.now(timezone.utc).date()
    return snapshot.taken_at == today


# ── Product/org helpers ──────────────────────────────────────────────────────

def get_product_record(db, company: str, product: str):
    """Get the Product ORM object, or None."""
    if db is None:
        return None
    stmt = (
        select(Product)
        .join(Organization, Product.org_id == Organization.id)
        .where(Organization.name == company, Product.name == product)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_org_and_product(db, company: str, product: str):
    """Get (Organization, Product) tuple or (None, None)."""
    if db is None:
        return None, None
    stmt = (
        select(Organization, Product)
        .join(Product, Product.org_id == Organization.id)
        .where(Organization.name == company, Product.name == product)
    )
    row = db.execute(stmt).first()
    if row:
        return row[0], row[1]
    return None, None


def get_facility_config(db, company: str, product: str) -> dict:
    """Load facility config from DB, or return empty dict.

    Facility config is per-product (singleton), snapshot-independent.
    """
    if db is None:
        return {}
    prod = get_product_record(db, company, product)
    if not prod or not prod.facility_config:
        return {}
    fc = prod.facility_config
    result = {}
    if fc.facility_limit is not None:
        result['facility_limit'] = float(fc.facility_limit)
    if fc.advance_rates:
        result['advance_rates'] = fc.advance_rates
    if fc.concentration_limits:
        result['concentration_limits'] = fc.concentration_limits
    if fc.covenants:
        result['covenants'] = fc.covenants
    return result


# ── Snapshot helpers ─────────────────────────────────────────────────────────

def list_snapshots(db, company: str, product: str) -> list[dict]:
    """Return all snapshots for a product, oldest first.

    Shape matches what the /snapshots endpoint historically returned from the
    filesystem, plus `source` and `row_count`. Frontend back-compat: `filename`
    and `date` fields preserved.
    """
    if db is None:
        return []
    prod = get_product_record(db, company, product)
    if prod is None:
        return []
    stmt = (
        select(Snapshot)
        .where(Snapshot.product_id == prod.id)
        .order_by(Snapshot.taken_at, Snapshot.ingested_at)
    )
    snaps = db.execute(stmt).scalars().all()
    return [
        {
            'id': str(s.id),
            'filename': s.name,       # Back-compat: old endpoint returned filename
            'name': s.name,
            'date': s.taken_at.isoformat() if s.taken_at else None,
            'source': s.source,
            'row_count': s.row_count,
            'ingested_at': s.ingested_at.isoformat() if s.ingested_at else None,
        }
        for s in snaps
    ]


def resolve_snapshot(db, company: str, product: str,
                     snapshot: Optional[str] = None) -> Optional[Snapshot]:
    """Resolve a `snapshot` query param to a Snapshot ORM row.

    `snapshot` can be:
      - None → latest snapshot by taken_at
      - a snapshot name (e.g. "2026-04-15_uae_healthcare")
      - a filename with extension (e.g. "2026-04-15_uae_healthcare.csv") — stripped
      - an ISO date (e.g. "2026-04-15") — matched against taken_at
    Returns None if no snapshot exists for the product.
    """
    if db is None:
        return None
    prod = get_product_record(db, company, product)
    if prod is None:
        return None

    base = select(Snapshot).where(Snapshot.product_id == prod.id)

    if snapshot is None:
        # Latest snapshot
        stmt = base.order_by(Snapshot.taken_at.desc(), Snapshot.ingested_at.desc()).limit(1)
        return db.execute(stmt).scalar_one_or_none()

    # Strip extension if user passed a filename
    name_candidate = snapshot
    for ext in ('.csv', '.xlsx', '.ods', '.json'):
        if name_candidate.endswith(ext):
            name_candidate = name_candidate[: -len(ext)]
            break

    # Try exact name match
    stmt = base.where(Snapshot.name == name_candidate).limit(1)
    hit = db.execute(stmt).scalar_one_or_none()
    if hit:
        return hit

    # Try ISO-date match against taken_at
    try:
        import datetime as _dt
        d = _dt.date.fromisoformat(snapshot)
        stmt = base.where(Snapshot.taken_at == d).order_by(Snapshot.ingested_at.desc()).limit(1)
        return db.execute(stmt).scalar_one_or_none()
    except ValueError:
        return None


# ── DataFrame loaders ────────────────────────────────────────────────────────

# Tape columns reconstructed from payments (not stored in extra_data).
_KLAIM_PAYMENT_DERIVED = 'Collected till date'
_SILQ_PAYMENT_DERIVED = 'Amt_Repaid'


def load_klaim_from_db(db, company: str, product: str,
                       snapshot_id=None) -> pd.DataFrame:
    """Query a Klaim product's invoices + payments for one snapshot.

    If snapshot_id is None, uses the latest snapshot by taken_at.
    Returns a DataFrame with tape-compatible column names. Every `extra_data`
    key from the ingest script round-trips back as a DataFrame column with
    its original name (e.g. 'Expected collection days', 'Collection days so
    far', 'Provider'). Unknown snapshots or empty products return empty DataFrame.
    """
    snap = _resolve_or_latest(db, company, product, snapshot_id)
    if snap is None:
        return pd.DataFrame()

    invoices = db.execute(
        select(Invoice).where(Invoice.snapshot_id == snap.id).order_by(Invoice.invoice_date)
    ).scalars().all()
    if not invoices:
        return pd.DataFrame()

    # Aggregate payments per invoice in one query (avoid N+1)
    inv_ids = [inv.id for inv in invoices]
    pay_totals = dict(db.execute(
        select(Payment.invoice_id, func.coalesce(func.sum(Payment.payment_amount), 0))
        .where(Payment.invoice_id.in_(inv_ids))
        .group_by(Payment.invoice_id)
    ).all())

    rows = []
    for inv in invoices:
        row = {
            'Deal date': inv.invoice_date,
            'Status': inv.status,
            'Purchase value': float(inv.amount_due) if inv.amount_due is not None else 0.0,
            'Group': inv.customer_name or '',
            'Payer': inv.payer_name or '',
            'Deal ID': inv.invoice_number,
            _KLAIM_PAYMENT_DERIVED: float(pay_totals.get(inv.id, 0)),
        }
        if inv.extra_data:
            # Spread every extra_data key back under its original tape column name.
            # Skip any core/reconstructed columns if somehow present (shouldn't be).
            for k, v in inv.extra_data.items():
                if k not in row:
                    row[k] = v
        rows.append(row)

    df = pd.DataFrame(rows)
    df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce', format='mixed')
    return df


def load_silq_from_db(db, company: str, product: str,
                      snapshot_id=None) -> pd.DataFrame:
    """Query a SILQ product's invoices + payments for one snapshot.

    Same extra_data round-trip as Klaim. SILQ-specific core columns use their
    native tape names: Deal ID, Shop_ID, Loan_Status, Disbursement_Date,
    Repayment_Deadline, Disbursed_Amount (SAR), Amt_Repaid.
    """
    snap = _resolve_or_latest(db, company, product, snapshot_id)
    if snap is None:
        return pd.DataFrame()

    invoices = db.execute(
        select(Invoice).where(Invoice.snapshot_id == snap.id).order_by(Invoice.invoice_date)
    ).scalars().all()
    if not invoices:
        return pd.DataFrame()

    inv_ids = [inv.id for inv in invoices]
    pay_totals = dict(db.execute(
        select(Payment.invoice_id, func.coalesce(func.sum(Payment.payment_amount), 0))
        .where(Payment.invoice_id.in_(inv_ids))
        .group_by(Payment.invoice_id)
    ).all())

    rows = []
    for inv in invoices:
        row = {
            'Deal ID': inv.invoice_number,
            'Shop_ID': inv.customer_name or '',
            'Loan_Status': inv.status,
            'Disbursement_Date': inv.invoice_date,
            'Repayment_Deadline': inv.due_date,
            'Disbursed_Amount (SAR)': float(inv.amount_due) if inv.amount_due is not None else 0.0,
            _SILQ_PAYMENT_DERIVED: float(pay_totals.get(inv.id, 0)),
        }
        if inv.extra_data:
            for k, v in inv.extra_data.items():
                if k not in row:
                    row[k] = v
        rows.append(row)

    df = pd.DataFrame(rows)
    # Coerce known date columns back to datetime
    for col in ('Disbursement_Date', 'Repayment_Deadline', 'Last_Collection_Date'):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def load_from_db(db, company: str, product: str,
                 snapshot_id=None) -> pd.DataFrame:
    """Load a snapshot as a tape-compatible DataFrame.

    Dispatches to the Klaim or SILQ loader based on product.analysis_type.
    Returns empty DataFrame if product is unknown, has no snapshots, or
    analysis_type isn't a tape-ingested type.
    """
    prod = get_product_record(db, company, product)
    if not prod:
        return pd.DataFrame()

    if prod.analysis_type == 'silq':
        return load_silq_from_db(db, company, product, snapshot_id=snapshot_id)
    elif prod.analysis_type == 'klaim':
        return load_klaim_from_db(db, company, product, snapshot_id=snapshot_id)
    else:
        # ejari_summary / tamara_summary / aajil — non-tape ingestion paths
        return pd.DataFrame()


def _resolve_or_latest(db, company, product, snapshot_id):
    """Return the Snapshot row matching snapshot_id, or latest if None.

    snapshot_id may be a UUID object, a UUID string, or None.
    """
    if snapshot_id is not None:
        return db.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id)
        ).scalar_one_or_none()
    return resolve_snapshot(db, company, product, snapshot=None)
