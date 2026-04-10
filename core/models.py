"""SQLAlchemy ORM models for the Laith credit platform.

6 tables supporting Phase 2A (database) and Phase 2B (integration API):
- organizations: portfolio companies (Klaim, SILQ, etc.)
- products: products within each company
- invoices: the receivables pool (core table)
- payments: payment activity (ADVANCE/PARTIAL/FINAL)
- bank_statements: cash position verification
- facility_config: per-facility lending terms (JSONB)
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Date, ForeignKey, Numeric,
    Text, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    api_key_hash = Column(String(255), nullable=True)  # Phase 2B
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    currency = Column(String(3), nullable=False)        # ISO 4217: AED, SAR, USD
    analysis_type = Column(String(50), nullable=False)  # "klaim" or "silq"
    facility_limit = Column(Numeric(18, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="products")
    invoices = relationship("Invoice", back_populates="product", cascade="all, delete-orphan")
    facility_config = relationship("FacilityConfig", back_populates="product", uselist=False,
                                   cascade="all, delete-orphan")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    invoice_number = Column(String(255), nullable=False)
    amount_due = Column(Numeric(18, 2), nullable=False)      # Face value / purchase value
    currency = Column(String(3), nullable=False)
    status = Column(String(50), nullable=False)               # Executed, Completed, draft, sent, paid, denied
    customer_name = Column(String(500), nullable=True)        # Maps to "Group" (Klaim) or shop_id (SILQ)
    payer_name = Column(String(500), nullable=True)           # Insurer (Klaim) or counterparty (SILQ)
    invoice_date = Column(Date, nullable=True)                # "Deal date" (Klaim) or "Disbursement_Date" (SILQ)
    due_date = Column(Date, nullable=True)
    extra_data = Column(JSONB, nullable=True)                   # Company-specific fields (see db_loader.py)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_invoices_org_product", "org_id", "product_id"),
        Index("ix_invoices_invoice_date", "invoice_date"),
        Index("ix_invoices_status", "status"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    payment_type = Column(String(50), nullable=False)   # ADVANCE, PARTIAL, FINAL
    payment_amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    payment_date = Column(Date, nullable=True)
    transaction_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_invoice_id", "invoice_id"),
        Index("ix_payments_payment_date", "payment_date"),
    )


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    balance = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    account_type = Column(String(50), nullable=True)    # cash-account, collection, savings
    statement_date = Column(Date, nullable=False)
    file_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FacilityConfig(Base):
    __tablename__ = "facility_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), unique=True, nullable=False)
    facility_limit = Column(Numeric(18, 2), nullable=True)
    advance_rates = Column(JSONB, nullable=True)          # {"UAE": 0.90} per facility agreement
    concentration_limits = Column(JSONB, nullable=True)   # [{name, threshold, ...}]
    covenants = Column(JSONB, nullable=True)              # [{name, threshold, operator, ...}]
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="facility_config")
