"""Database query helpers that return DataFrames compatible with core/analysis.py.

This is the bridge between PostgreSQL and the existing computation engine.
Queries the DB, returns DataFrames with the same column names that
core/portfolio.py, core/analysis.py, and core/analysis_silq.py expect.
Zero changes needed to any analysis function.
"""
import pandas as pd
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from core.models import Organization, Product, Invoice, Payment, FacilityConfig


# ── Query helpers ────────────────────────────────────────────────────────────

def has_db_data(db, company: str, product: str) -> bool:
    """Check if the DB has any invoices for this company/product."""
    if db is None:
        return False
    stmt = (
        select(func.count(Invoice.id))
        .join(Product, Invoice.product_id == Product.id)
        .join(Organization, Product.org_id == Organization.id)
        .where(Organization.name == company, Product.name == product)
    )
    count = db.execute(stmt).scalar()
    return (count or 0) > 0


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


def get_facility_config(db, company: str, product: str) -> dict:
    """Load facility config from DB, or return empty dict."""
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


# ── DataFrame loaders ────────────────────────────────────────────────────────

def load_klaim_from_db(db, company: str, product: str) -> pd.DataFrame:
    """Query invoices + payments for a Klaim product, return DataFrame
    with column names matching the tape format expected by core/analysis.py
    and core/portfolio.py (Klaim functions).

    Tape columns produced:
        Deal date, Status, Purchase value, Purchase price, Discount,
        Collected till date, Denied by insurance, Pending insurance response,
        Expected total, Group, Product, New business, Gross revenue,
        Setup fee, Other fee, Adjustments, Provisions
    """
    _, prod = get_org_and_product(db, company, product)
    if not prod:
        return pd.DataFrame()

    # Query all invoices for this product
    stmt = (
        select(Invoice)
        .where(Invoice.product_id == prod.id)
        .order_by(Invoice.invoice_date)
    )
    invoices = db.execute(stmt).scalars().all()
    if not invoices:
        return pd.DataFrame()

    # Pre-aggregate payments for all invoices in a single query (avoids N+1)
    inv_ids = [inv.id for inv in invoices]
    pay_totals = {}
    if inv_ids:
        pay_stmt = (
            select(Payment.invoice_id, func.coalesce(func.sum(Payment.payment_amount), 0))
            .where(Payment.invoice_id.in_(inv_ids))
            .group_by(Payment.invoice_id)
        )
        pay_totals = dict(db.execute(pay_stmt).all())

    # Build rows
    rows = []
    for inv in invoices:
        meta = inv.extra_data or {}
        collected = float(pay_totals.get(inv.id, 0))

        rows.append({
            'Deal date': pd.to_datetime(inv.invoice_date),
            'Status': inv.status,
            'Purchase value': float(inv.amount_due),
            'Purchase price': float(meta.get('purchase_price', inv.amount_due)),
            'Discount': float(meta.get('discount', 0)),
            'Collected till date': collected,
            'Denied by insurance': float(meta.get('denied', 0)),
            'Pending insurance response': float(meta.get('pending', 0)),
            'Expected total': float(meta.get('expected_total', inv.amount_due)),
            'Group': inv.customer_name or '',
            'Product': meta.get('product_type', ''),
            'New business': meta.get('new_business', ''),
            'Gross revenue': float(meta.get('gross_revenue', 0)),
            'Setup fee': float(meta.get('setup_fee', 0)),
            'Other fee': float(meta.get('other_fee', 0)),
            'Adjustments': float(meta.get('adjustments', 0)),
            'Provisions': float(meta.get('provisions', 0)),
            'Claim count': int(meta.get('claim_count', 1)),
        })

    df = pd.DataFrame(rows)
    df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
    return df


def load_silq_from_db(db, company: str, product: str) -> pd.DataFrame:
    """Query invoices + payments for a SILQ product, return DataFrame
    with column names matching the tape format expected by core/analysis_silq.py
    and core/portfolio.py (SILQ functions).

    Tape columns produced (matching analysis_silq.py constants):
        Deal ID, Shop_ID, Product, Loan_Status,
        Disbursement_Date, Repayment_Deadline, Last_Collection_Date,
        Disbursed_Amount (SAR), Outstanding_Amount (SAR),
        Overdue_Amount (SAR), Total_Collectable_Amount (SAR),
        Amt_Repaid, Margin Collected, Principal Collected,
        Tenure, Loan_Age, Shop_Credit_Limit (SAR)
    """
    _, prod = get_org_and_product(db, company, product)
    if not prod:
        return pd.DataFrame()

    stmt = (
        select(Invoice)
        .where(Invoice.product_id == prod.id)
        .order_by(Invoice.invoice_date)
    )
    invoices = db.execute(stmt).scalars().all()
    if not invoices:
        return pd.DataFrame()

    rows = []
    for inv in invoices:
        meta = inv.extra_data or {}

        # Aggregate payments
        pay_stmt = (
            select(
                func.coalesce(func.sum(Payment.payment_amount), 0)
            ).where(Payment.invoice_id == inv.id)
        )
        repaid = float(db.execute(pay_stmt).scalar() or 0)

        rows.append({
            'Deal ID': inv.invoice_number,
            'Shop_ID': inv.customer_name or meta.get('shop_id', ''),
            'Product': meta.get('product_type', ''),
            'Loan_Status': inv.status,
            'Disbursement_Date': pd.to_datetime(inv.invoice_date),
            'Repayment_Deadline': pd.to_datetime(inv.due_date) if inv.due_date else pd.NaT,
            'Last_Collection_Date': pd.to_datetime(meta.get('last_collection_date')) if meta.get('last_collection_date') else pd.NaT,
            'Disbursed_Amount (SAR)': float(inv.amount_due),
            'Outstanding_Amount (SAR)': float(meta.get('outstanding', inv.amount_due)) - repaid,
            'Overdue_Amount (SAR)': float(meta.get('overdue', 0)),
            'Total_Collectable_Amount (SAR)': float(meta.get('collectable', inv.amount_due)),
            'Amt_Repaid': repaid,
            'Margin Collected': float(meta.get('margin_collected', 0)),
            'Principal Collected': float(meta.get('principal_collected', 0)),
            'Tenure': int(meta.get('tenure', 0)),
            'Loan_Age': int(meta.get('loan_age', 0)),
            'Shop_Credit_Limit (SAR)': float(meta.get('shop_credit_limit', 0)),
        })

    df = pd.DataFrame(rows)
    for col in ('Disbursement_Date', 'Repayment_Deadline', 'Last_Collection_Date'):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def load_from_db(db, company: str, product: str) -> pd.DataFrame:
    """Load invoices as a tape-compatible DataFrame.
    Auto-dispatches to Klaim or SILQ loader based on product.analysis_type.
    """
    prod = get_product_record(db, company, product)
    if not prod:
        return pd.DataFrame()

    if prod.analysis_type == 'silq':
        return load_silq_from_db(db, company, product)
    else:
        return load_klaim_from_db(db, company, product)
