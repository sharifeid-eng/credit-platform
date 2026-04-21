"""Integration API router — inbound endpoints for portfolio companies.

Portfolio companies push invoices, payments, and bank statements via
these endpoints, authenticated by X-API-Key. Data lands in PostgreSQL
and is immediately available to Portfolio Analytics dashboard.

All endpoints are under /api/integration/.
"""
import uuid
import os
import base64
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db
from core.db_loader import get_or_create_live_snapshot, is_snapshot_mutable
from core.models import Organization, Product, Snapshot, Invoice, Payment, BankStatement
from backend.auth import get_current_org
from backend.schemas import (
    InvoiceCreate, InvoiceBulkCreate, InvoiceUpdate, InvoiceResponse,
    PaymentCreate, PaymentCreateWithInvoice, PaymentBulkCreate, PaymentResponse,
    BankStatementCreate, BankStatementResponse,
    PaginatedInvoices, PaginatedPayments, PaginatedBankStatements,
    BulkCreateResponse,
)

router = APIRouter(prefix="/api/integration", tags=["Integration API"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_product(db: Session, org: Organization, product_id: Optional[str] = None) -> Product:
    """Resolve which product to use. If product_id given, validate it belongs to org.
    Otherwise use org's first product."""
    if product_id:
        prod = db.query(Product).filter_by(id=product_id, org_id=org.id).first()
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found for this organization.")
        return prod
    # Default to first product
    prod = db.query(Product).filter_by(org_id=org.id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="No products configured for this organization.")
    return prod


def _get_invoice_or_404(db: Session, org: Organization, invoice_id: str) -> Invoice:
    """Get an invoice by ID, ensuring it belongs to the authenticated org."""
    try:
        inv_uuid = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format.")
    inv = db.query(Invoice).filter_by(id=inv_uuid, org_id=org.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return inv


def _upsert_invoice_in_snapshot(db: Session, *, org: Organization, prod: Product,
                                 snap: Snapshot, item) -> tuple[Invoice, bool]:
    """Create or update an invoice inside the given snapshot.

    Same-day UPSERT semantic: if `item.invoice_number` already exists in this
    snapshot, mutate that row; otherwise create new. Returns (invoice, created).
    """
    existing = db.query(Invoice).filter_by(
        snapshot_id=snap.id, invoice_number=item.invoice_number
    ).first()
    if existing is not None:
        existing.amount_due = item.amount_due
        existing.currency = item.currency_alpha3
        existing.status = item.status
        existing.customer_name = item.customer_name
        existing.payer_name = item.payer_name
        existing.invoice_date = item.invoice_date
        existing.due_date = item.due_date
        existing.extra_data = item.extra_data
        existing.updated_at = datetime.utcnow()
        return existing, False
    inv = Invoice(
        id=uuid.uuid4(),
        org_id=org.id,
        product_id=prod.id,
        snapshot_id=snap.id,
        invoice_number=item.invoice_number,
        amount_due=item.amount_due,
        currency=item.currency_alpha3,
        status=item.status,
        customer_name=item.customer_name,
        payer_name=item.payer_name,
        invoice_date=item.invoice_date,
        due_date=item.due_date,
        extra_data=item.extra_data,
    )
    db.add(inv)
    return inv, True


def _require_mutable(inv: Invoice) -> None:
    """Raise 409 if the invoice's snapshot is not today's live snapshot.

    Enforces immutability: tape snapshots are frozen IC views, prior-day
    live snapshots are frozen history. Only today's live accepts writes.
    """
    if not is_snapshot_mutable(inv.snapshot):
        src = inv.snapshot.source if inv.snapshot else 'unknown'
        taken = inv.snapshot.taken_at.isoformat() if inv.snapshot and inv.snapshot.taken_at else '?'
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invoice belongs to an immutable snapshot "
                f"(source={src}, taken_at={taken}). "
                f"Only today's live-YYYY-MM-DD snapshot accepts writes."
            ),
        )


# ── Invoice endpoints ────────────────────────────────────────────────────────

@router.get("/invoices", response_model=PaginatedInvoices)
def list_invoices(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    product_id: Optional[str] = None,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """List invoices for the authenticated organization (paginated)."""
    q = db.query(Invoice).filter(Invoice.org_id == org.id)
    if status:
        q = q.filter(Invoice.status == status.lower())
    if product_id:
        q = q.filter(Invoice.product_id == product_id)

    total = q.count()
    invoices = q.order_by(Invoice.invoice_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return PaginatedInvoices(
        invoices=[InvoiceResponse.from_orm_invoice(inv) for inv in invoices],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    body: InvoiceCreate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Create (or same-day UPSERT) an invoice.

    The invoice is tagged with today's rolling-daily live snapshot
    (`live-YYYY-MM-DD`), created on demand. If the same `invoice_number` was
    already pushed today, the existing row is updated in place — preserves
    the "one state per invoice per day" model. Tomorrow's first push of the
    same invoice_number creates a new row in the new day's snapshot (prior
    day becomes frozen history).
    """
    prod = _resolve_product(db, org, body.product_id)
    snap = get_or_create_live_snapshot(db, prod)

    inv, created = _upsert_invoice_in_snapshot(db, org=org, prod=prod, snap=snap, item=body)
    if created:
        snap.row_count = (snap.row_count or 0) + 1
    db.commit()
    db.refresh(inv)
    return InvoiceResponse.from_orm_invoice(inv)


@router.post("/invoices/bulk", response_model=BulkCreateResponse, status_code=201)
def create_invoices_bulk(
    body: InvoiceBulkCreate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Create or same-day UPSERT up to 5,000 invoices in one request.

    All items land in today's live snapshot (see create_invoice for semantics).
    Per-item failures are reported in the `errors` array; successful items
    commit together at the end.
    """
    created_count = 0
    upserted_count = 0
    errors = []

    # Resolve product + live snapshot once per distinct product_id to avoid
    # re-querying per item. The common case is one product per bulk.
    snap_cache: dict[str, Snapshot] = {}
    prod_cache: dict[str, Product] = {}

    for i, item in enumerate(body.invoices):
        try:
            with db.begin_nested():
                cache_key = str(item.product_id) if item.product_id else '__default__'
                if cache_key not in prod_cache:
                    prod_cache[cache_key] = _resolve_product(db, org, item.product_id)
                    snap_cache[cache_key] = get_or_create_live_snapshot(db, prod_cache[cache_key])
                prod = prod_cache[cache_key]
                snap = snap_cache[cache_key]
                _, is_new = _upsert_invoice_in_snapshot(db, org=org, prod=prod, snap=snap, item=item)
                if is_new:
                    snap.row_count = (snap.row_count or 0) + 1
                db.flush()
            if is_new:
                created_count += 1
            else:
                upserted_count += 1
        except HTTPException as e:
            errors.append({"index": i, "detail": e.detail})
        except Exception as e:
            errors.append({"index": i, "detail": str(e)})

    if created_count + upserted_count > 0:
        db.commit()

    return BulkCreateResponse(created=created_count + upserted_count, errors=errors)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: str,
    body: InvoiceUpdate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Partial-update an invoice. Only invoices in today's live snapshot
    are mutable; tape snapshots and prior-day live snapshots return 409.
    """
    inv = _get_invoice_or_404(db, org, invoice_id)
    _require_mutable(inv)

    update_data = body.model_dump(exclude_unset=True)
    if 'currency_alpha3' in update_data:
        update_data['currency'] = update_data.pop('currency_alpha3')

    for key, value in update_data.items():
        if hasattr(inv, key):
            setattr(inv, key, value)

    inv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(inv)
    return InvoiceResponse.from_orm_invoice(inv)


@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: str,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Delete an invoice and its payments. Only invoices in today's live
    snapshot are deletable; tape + prior-day live snapshots return 409.
    """
    inv = _get_invoice_or_404(db, org, invoice_id)
    _require_mutable(inv)
    db.delete(inv)  # cascade deletes payments
    db.commit()


# ── Payment endpoints ────────────────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/payments", response_model=PaginatedPayments)
def list_payments(
    invoice_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """List payments for a specific invoice."""
    inv = _get_invoice_or_404(db, org, invoice_id)

    q = db.query(Payment).filter(Payment.invoice_id == inv.id)
    total = q.count()
    payments = q.order_by(Payment.payment_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return PaginatedPayments(
        payments=[PaymentResponse.from_orm_payment(p) for p in payments],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    invoice_id: str,
    body: PaymentCreate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Create a payment for a specific invoice. Only invoices in today's
    live snapshot accept new payments; historical snapshots return 409.
    Payment inherits its parent invoice's snapshot_id.
    """
    inv = _get_invoice_or_404(db, org, invoice_id)
    _require_mutable(inv)

    pay = Payment(
        id=uuid.uuid4(),
        invoice_id=inv.id,
        snapshot_id=inv.snapshot_id,
        payment_type=body.payment_type,
        payment_amount=body.payment_amount,
        currency=body.currency_alpha3,
        payment_date=body.payment_date,
        transaction_id=body.transaction_id,
    )
    db.add(pay)
    db.commit()
    db.refresh(pay)
    return PaymentResponse.from_orm_payment(pay)


@router.post("/payments/bulk", response_model=BulkCreateResponse, status_code=201)
def create_payments_bulk(
    body: PaymentBulkCreate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Create up to 5,000 payments in a single request. Each payment inherits
    its parent invoice's snapshot_id; payments targeting invoices in
    immutable (tape or historical-live) snapshots are reported as errors.
    """
    created = 0
    errors = []

    for i, item in enumerate(body.payments):
        try:
            with db.begin_nested():
                inv = _get_invoice_or_404(db, org, item.invoice_id)
                _require_mutable(inv)
                pay = Payment(
                    id=uuid.uuid4(),
                    invoice_id=inv.id,
                    snapshot_id=inv.snapshot_id,
                    payment_type=item.payment_type,
                    payment_amount=item.payment_amount,
                    currency=item.currency_alpha3,
                    payment_date=item.payment_date,
                    transaction_id=item.transaction_id,
                )
                db.add(pay)
                db.flush()
            created += 1
        except HTTPException as e:
            errors.append({"index": i, "detail": e.detail})
        except Exception as e:
            errors.append({"index": i, "detail": str(e)})

    if created > 0:
        db.commit()

    return BulkCreateResponse(created=created, errors=errors)


# ── Bank Statement endpoints ─────────────────────────────────────────────────

STATEMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'bank_statements')


@router.get("/bank-statements", response_model=PaginatedBankStatements)
def list_bank_statements(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """List bank statements for the authenticated organization."""
    q = db.query(BankStatement).filter(BankStatement.org_id == org.id)
    total = q.count()
    statements = q.order_by(BankStatement.statement_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return PaginatedBankStatements(
        bank_statements=[BankStatementResponse.from_orm_statement(s) for s in statements],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/bank-statements", response_model=BankStatementResponse, status_code=201)
def create_bank_statement(
    body: BankStatementCreate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Upload a bank statement. Tagged with today's live snapshot (of the
    org's first product) for batch traceability; statements remain queryable
    by statement_date independently."""
    file_path = None
    if body.attached_file_base64:
        os.makedirs(STATEMENTS_DIR, exist_ok=True)
        filename = f"{org.name}_{body.statement_date}_{uuid.uuid4().hex[:8]}.pdf"
        file_path = os.path.join(STATEMENTS_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(base64.b64decode(body.attached_file_base64))

    prod = _resolve_product(db, org, None)
    snap = get_or_create_live_snapshot(db, prod)

    bs = BankStatement(
        id=uuid.uuid4(),
        org_id=org.id,
        snapshot_id=snap.id,
        balance=body.balance,
        currency=body.currency,
        account_type=body.account_type,
        statement_date=body.statement_date,
        file_path=file_path,
    )
    db.add(bs)
    db.commit()
    db.refresh(bs)
    return BankStatementResponse.from_orm_statement(bs)
