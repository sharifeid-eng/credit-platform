"""SQLAlchemy ORM models for the Laith credit platform.

8 tables supporting Phase 2A (database), Phase 2B (integration API), Phase 3 (auth),
and Phase 4 (snapshots — DB as authoritative, snapshotted source of truth):
- users: platform users with email + role (admin/viewer)
- organizations: portfolio companies (Klaim, SILQ, etc.)
- products: products within each company
- snapshots: point-in-time views of a product's book. Created by tape ingest
  (source='tape', one per uploaded CSV/Excel file) or rolling daily by the
  Integration API (source='live', `live-YYYY-MM-DD`).
- invoices: the receivables pool. Every row belongs to exactly one snapshot;
  the same invoice_number can appear in many snapshots (different state each).
- payments: payment activity (ADVANCE/PARTIAL/FINAL), tagged with the snapshot
  they were observed in (duplicates invoice.snapshot_id for efficient querying).
- bank_statements: cash position verification, optionally tagged with a snapshot.
- facility_config: per-facility lending terms (JSONB). Singleton per product,
  snapshot-independent.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, Date, ForeignKey, Numeric,
    Text, Index, Boolean, Integer, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from core.database import Base


def _utcnow_naive() -> datetime:
    """Naive-UTC default for DateTime columns (no timezone=True).

    Replaces the deprecated `datetime.utcnow`. Strips tzinfo so values match
    the existing naive DB schema — avoids a column-wide aware-migration.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # 'admin' or 'viewer'
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_utcnow_naive)
    last_login_at = Column(DateTime, nullable=True)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    api_key_hash = Column(String(255), nullable=True)  # Phase 2B
    created_at = Column(DateTime, default=_utcnow_naive)

    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    currency = Column(String(3), nullable=False)        # ISO 4217: AED, SAR, USD
    analysis_type = Column(String(50), nullable=False)  # "klaim" or "silq"
    facility_limit = Column(Numeric(18, 2), nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)

    organization = relationship("Organization", back_populates="products")
    snapshots = relationship("Snapshot", back_populates="product", cascade="all, delete-orphan")
    facility_config = relationship("FacilityConfig", back_populates="product", uselist=False,
                                   cascade="all, delete-orphan")


class Snapshot(Base):
    """Point-in-time view of a product's book.

    A snapshot is created by either:
    (a) Tape ingest — `scripts/ingest_tape.py` reads a CSV/Excel file, creates one
        snapshot with source='tape', name = filename-without-extension,
        taken_at = date parsed from filename.
    (b) Integration API live push — rolling daily. First push of a UTC day creates
        `live-YYYY-MM-DD` (source='live'); subsequent same-day writes UPSERT within
        that snapshot; next day's first push creates a new snapshot, prior day
        becomes frozen history.

    Invoices, payments, and (optionally) bank statements belong to exactly one
    snapshot. Dashboard reads filter by snapshot_id so the same invoice can appear
    in many snapshots with different state (balance, status) at each point in time.
    """
    __tablename__ = "snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    name = Column(String(255), nullable=False)           # "2026-04-15_uae_healthcare" or "live-2026-04-21"
    source = Column(String(20), nullable=False)          # 'tape' | 'live' | 'manual'
    taken_at = Column(Date, nullable=False)              # Asset-date the snapshot represents
    ingested_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    row_count = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)

    product = relationship("Product", back_populates="snapshots")
    invoices = relationship("Invoice", back_populates="snapshot", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="snapshot", cascade="all, delete-orphan")
    bank_statements = relationship("BankStatement", back_populates="snapshot")

    __table_args__ = (
        UniqueConstraint("product_id", "name", name="uq_snapshots_product_name"),
        Index("ix_snapshots_product_taken_at", "product_id", "taken_at"),
        Index("ix_snapshots_source", "source"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=False)
    invoice_number = Column(String(255), nullable=False)
    amount_due = Column(Numeric(18, 2), nullable=False)      # Face value / purchase value
    currency = Column(String(3), nullable=False)
    status = Column(String(50), nullable=False)               # Executed, Completed, draft, sent, paid, denied
    customer_name = Column(String(500), nullable=True)        # Maps to "Group" (Klaim) or shop_id (SILQ)
    payer_name = Column(String(500), nullable=True)           # Insurer (Klaim) or counterparty (SILQ)
    invoice_date = Column(Date, nullable=True)                # "Deal date" (Klaim) or "Disbursement_Date" (SILQ)
    due_date = Column(Date, nullable=True)
    extra_data = Column(JSONB, nullable=True)                 # Every non-core tape column lands here — read back in db_loader
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    snapshot = relationship("Snapshot", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("snapshot_id", "invoice_number", name="uq_invoices_snapshot_invoice_number"),
        Index("ix_invoices_org_product", "org_id", "product_id"),
        Index("ix_invoices_snapshot_id", "snapshot_id"),
        Index("ix_invoices_invoice_date", "invoice_date"),
        Index("ix_invoices_status", "status"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=False)
    payment_type = Column(String(50), nullable=False)   # ADVANCE, PARTIAL, FINAL
    payment_amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    payment_date = Column(Date, nullable=True)
    transaction_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)

    invoice = relationship("Invoice", back_populates="payments")
    snapshot = relationship("Snapshot", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_invoice_id", "invoice_id"),
        Index("ix_payments_snapshot_id", "snapshot_id"),
        Index("ix_payments_payment_date", "payment_date"),
    )


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=True)  # Optional — bank statements are time-series, not strictly snapshot-scoped
    balance = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    account_type = Column(String(50), nullable=True)    # cash-account, collection, savings
    statement_date = Column(Date, nullable=False)
    file_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive)

    snapshot = relationship("Snapshot", back_populates="bank_statements")

    __table_args__ = (
        Index("ix_bank_statements_org", "org_id"),
        Index("ix_bank_statements_snapshot_id", "snapshot_id"),
        Index("ix_bank_statements_statement_date", "statement_date"),
    )


class FacilityConfig(Base):
    __tablename__ = "facility_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), unique=True, nullable=False)
    facility_limit = Column(Numeric(18, 2), nullable=True)
    advance_rates = Column(JSONB, nullable=True)          # {"UAE": 0.90} per facility agreement
    concentration_limits = Column(JSONB, nullable=True)   # [{name, threshold, ...}]
    covenants = Column(JSONB, nullable=True)              # [{name, threshold, operator, ...}]
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    product = relationship("Product", back_populates="facility_config")
