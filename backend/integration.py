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
from core.models import Organization, Product, Invoice, Payment, BankStatement
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
    """Create a single invoice."""
    prod = _resolve_product(db, org, body.product_id)

    inv = Invoice(
        id=uuid.uuid4(),
        org_id=org.id,
        product_id=prod.id,
        invoice_number=body.invoice_number,
        amount_due=body.amount_due,
        currency=body.currency_alpha3,
        status=body.status,
        customer_name=body.customer_name,
        payer_name=body.payer_name,
        invoice_date=body.invoice_date,
        due_date=body.due_date,
        extra_data=body.extra_data,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return InvoiceResponse.from_orm_invoice(inv)


@router.post("/invoices/bulk", response_model=BulkCreateResponse, status_code=201)
def create_invoices_bulk(
    body: InvoiceBulkCreate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Create up to 5,000 invoices in a single request."""
    created = 0
    errors = []

    for i, item in enumerate(body.invoices):
        try:
            with db.begin_nested():  # savepoint — rollback only this item on failure
                prod = _resolve_product(db, org, item.product_id)
                inv = Invoice(
                    id=uuid.uuid4(),
                    org_id=org.id,
                    product_id=prod.id,
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
                db.flush()
            created += 1
        except Exception as e:
            errors.append({"index": i, "detail": str(e)})

    if created > 0:
        db.commit()

    return BulkCreateResponse(created=created, errors=errors)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: str,
    body: InvoiceUpdate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Update an invoice (partial update)."""
    inv = _get_invoice_or_404(db, org, invoice_id)

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
    """Delete an invoice and its associated payments."""
    inv = _get_invoice_or_404(db, org, invoice_id)
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
    """Create a payment for a specific invoice."""
    inv = _get_invoice_or_404(db, org, invoice_id)

    pay = Payment(
        id=uuid.uuid4(),
        invoice_id=inv.id,
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
    """Create up to 5,000 payments in a single request."""
    created = 0
    errors = []

    for i, item in enumerate(body.payments):
        try:
            with db.begin_nested():  # savepoint — rollback only this item on failure
                inv = _get_invoice_or_404(db, org, item.invoice_id)
                pay = Payment(
                    id=uuid.uuid4(),
                    invoice_id=inv.id,
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
    """Upload a bank statement."""
    file_path = None
    if body.attached_file_base64:
        os.makedirs(STATEMENTS_DIR, exist_ok=True)
        filename = f"{org.name}_{body.statement_date}_{uuid.uuid4().hex[:8]}.pdf"
        file_path = os.path.join(STATEMENTS_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(base64.b64decode(body.attached_file_base64))

    bs = BankStatement(
        id=uuid.uuid4(),
        org_id=org.id,
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
