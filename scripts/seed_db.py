"""Seed the database with existing tape data for validation.

Reads the latest tape CSV/Excel for each company/product and inserts
the data as Invoice + Payment records. This allows validating that
the DB-sourced portfolio analytics match the tape-sourced results.

Usage:
    cd credit-platform
    python scripts/seed_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from datetime import datetime
import pandas as pd
from sqlalchemy import text

from core.database import engine, SessionLocal, Base
from core.models import Organization, Product, Invoice, Payment, FacilityConfig
from core.loader import get_companies, get_products, get_snapshots, load_snapshot
from core.config import load_config

try:
    from core.loader import load_silq_snapshot
except ImportError:
    load_silq_snapshot = None


def seed():
    if engine is None:
        print("ERROR: DATABASE_URL not set in .env. Cannot seed.")
        sys.exit(1)

    # Create all tables (safe if already exist)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        _seed_all(db)
        db.commit()
        print("\nSeed complete.")
    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        db.close()


def _seed_all(db):
    companies = get_companies()
    print(f"Found {len(companies)} companies: {companies}")

    for company_name in companies:
        # Handle company names that may be dicts
        co = company_name['name'] if isinstance(company_name, dict) else company_name

        # Create or get Organization
        org = db.query(Organization).filter_by(name=co).first()
        if not org:
            org = Organization(id=uuid.uuid4(), name=co)
            db.add(org)
            db.flush()
            print(f"  Created organization: {co}")
        else:
            print(f"  Organization exists: {co}")

        products = get_products(co)
        for product_name in products:
            pname = product_name['name'] if isinstance(product_name, dict) else product_name
            _seed_product(db, org, co, pname)


def _seed_product(db, org, company, product_name):
    config = load_config(company, product_name) or {}
    analysis_type = config.get('analysis_type', 'klaim')
    currency = config.get('currency', 'USD')

    # Create or get Product
    prod = db.query(Product).filter_by(org_id=org.id, name=product_name).first()
    if not prod:
        prod = Product(
            id=uuid.uuid4(),
            org_id=org.id,
            name=product_name,
            currency=currency,
            analysis_type=analysis_type,
        )
        db.add(prod)
        db.flush()
        print(f"    Created product: {product_name} ({analysis_type}, {currency})")
    else:
        # Clear existing invoices for re-seed
        existing = db.query(Invoice).filter_by(product_id=prod.id).count()
        if existing > 0:
            print(f"    Product {product_name} already has {existing} invoices. Skipping.")
            return

    # Get latest snapshot
    snapshots = get_snapshots(company, product_name)
    if not snapshots:
        print(f"    No snapshots found for {product_name}. Skipping.")
        return

    latest = snapshots[-1]
    print(f"    Loading snapshot: {latest['filename']}")

    # Load tape data
    if analysis_type == 'silq' and load_silq_snapshot:
        df, _ = load_silq_snapshot(latest['filepath'])
        _seed_silq_invoices(db, org, prod, df)
    else:
        df = load_snapshot(latest['filepath'])
        _seed_klaim_invoices(db, org, prod, df)

    # Create default FacilityConfig
    if not db.query(FacilityConfig).filter_by(product_id=prod.id).first():
        fc = FacilityConfig(
            id=uuid.uuid4(),
            product_id=prod.id,
            advance_rates=config.get('advance_rates', {"default": 0.90}),
            covenants=config.get('covenants', []),
        )
        db.add(fc)
        print(f"    Created facility config")


def _seed_klaim_invoices(db, org, prod, df):
    """Seed Klaim tape rows as Invoice + Payment records."""
    count = 0
    for idx, row in df.iterrows():
        inv_id = uuid.uuid4()
        meta = {}

        # Extract optional columns into metadata
        for col, key in [
            ('Discount', 'discount'),
            ('Gross revenue', 'gross_revenue'),
            ('Setup fee', 'setup_fee'),
            ('Other fee', 'other_fee'),
            ('Adjustments', 'adjustments'),
            ('Provisions', 'provisions'),
            ('Denied by insurance', 'denied'),
            ('Pending insurance response', 'pending'),
            ('Expected total', 'expected_total'),
            ('New business', 'new_business'),
            ('Claim count', 'claim_count'),
            ('Product', 'product_type'),
        ]:
            if col in df.columns:
                val = row[col]
                if pd.notna(val):
                    meta[key] = float(val) if isinstance(val, (int, float)) else str(val)

        # Purchase price (may differ from face value)
        if 'Purchase price' in df.columns and pd.notna(row.get('Purchase price')):
            meta['purchase_price'] = float(row['Purchase price'])

        inv = Invoice(
            id=inv_id,
            org_id=org.id,
            product_id=prod.id,
            invoice_number=str(row.get('Deal ID', row.get('invoice_number', f'INV-{idx:06d}'))),
            amount_due=float(row.get('Purchase value', 0) or 0),
            currency=prod.currency,
            status=str(row.get('Status', 'Executed')),
            customer_name=str(row.get('Group', '')) if pd.notna(row.get('Group')) else None,
            payer_name=str(row.get('Payer', '')) if pd.notna(row.get('Payer')) else None,
            invoice_date=pd.to_datetime(row.get('Deal date'), errors='coerce'),
            due_date=None,
            extra_data=meta if meta else None,
        )
        db.add(inv)

        # Create payment record if collected > 0
        collected = float(row.get('Collected till date', 0) or 0)
        if collected > 0:
            pay = Payment(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                payment_type='PARTIAL',
                payment_amount=collected,
                currency=prod.currency,
                payment_date=pd.to_datetime(row.get('Deal date'), errors='coerce'),
            )
            db.add(pay)

        count += 1
        if count % 1000 == 0:
            db.flush()
            print(f"      ... {count} invoices")

    db.flush()
    print(f"    Seeded {count} Klaim invoices")


def _seed_silq_invoices(db, org, prod, df):
    """Seed SILQ tape rows as Invoice + Payment records."""
    count = 0
    for idx, row in df.iterrows():
        inv_id = uuid.uuid4()
        meta = {}

        # SILQ-specific metadata
        for col, key in [
            ('Shop_ID', 'shop_id'),
            ('Product', 'product_type'),
            ('Tenure', 'tenure'),
            ('Loan_Age', 'loan_age'),
            ('Outstanding_Amount (SAR)', 'outstanding'),
            ('Overdue_Amount (SAR)', 'overdue'),
            ('Total_Collectable_Amount (SAR)', 'collectable'),
            ('Margin Collected', 'margin_collected'),
            ('Principal Collected', 'principal_collected'),
            ('Shop_Credit_Limit (SAR)', 'shop_credit_limit'),
        ]:
            if col in df.columns:
                val = row[col]
                if pd.notna(val):
                    meta[key] = float(val) if isinstance(val, (int, float)) else str(val)

        # Last collection date
        if 'Last_Collection_Date' in df.columns and pd.notna(row.get('Last_Collection_Date')):
            meta['last_collection_date'] = str(row['Last_Collection_Date'])[:10]

        inv = Invoice(
            id=inv_id,
            org_id=org.id,
            product_id=prod.id,
            invoice_number=str(row.get('Deal ID', f'SILQ-{idx:06d}')),
            amount_due=float(row.get('Disbursed_Amount (SAR)', 0) or 0),
            currency=prod.currency,
            status=str(row.get('Loan_Status', 'Current')),
            customer_name=str(row.get('Shop_ID', '')) if pd.notna(row.get('Shop_ID')) else None,
            invoice_date=pd.to_datetime(row.get('Disbursement_Date'), errors='coerce'),
            due_date=pd.to_datetime(row.get('Repayment_Deadline'), errors='coerce') if pd.notna(row.get('Repayment_Deadline')) else None,
            extra_data=meta if meta else None,
        )
        db.add(inv)

        # Create payment record if repaid > 0
        repaid = float(row.get('Amt_Repaid', 0) or 0)
        if repaid > 0:
            pay = Payment(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                payment_type='PARTIAL',
                payment_amount=repaid,
                currency=prod.currency,
                payment_date=pd.to_datetime(row.get('Last_Collection_Date'), errors='coerce') if pd.notna(row.get('Last_Collection_Date')) else None,
            )
            db.add(pay)

        count += 1
        if count % 500 == 0:
            db.flush()
            print(f"      ... {count} invoices")

    db.flush()
    print(f"    Seeded {count} SILQ invoices")


if __name__ == '__main__':
    seed()
