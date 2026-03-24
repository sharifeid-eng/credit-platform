"""Pydantic request/response models for the Integration API (Phase 2B).

Portfolio companies use these schemas to push invoices, payments,
and bank statements into the Laith database.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ── Invoice schemas ──────────────────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    invoice_number: str = Field(..., min_length=1, max_length=255)
    invoice_date: date
    due_date: Optional[date] = None
    amount_due: Decimal = Field(..., gt=0)
    currency_alpha3: str = Field(..., min_length=3, max_length=3)
    status: str = Field(..., min_length=1, max_length=50)
    customer_name: Optional[str] = Field(None, max_length=500)
    payer_name: Optional[str] = Field(None, max_length=500)
    product_id: Optional[str] = None  # UUID string; if omitted, uses org's first product
    extra_data: Optional[dict] = None  # Company-specific fields (JSONB)

    @field_validator('currency_alpha3')
    @classmethod
    def uppercase_currency(cls, v):
        return v.upper()

    @field_validator('status')
    @classmethod
    def lowercase_status(cls, v):
        return v.lower().strip()


class InvoiceBulkCreate(BaseModel):
    invoices: list[InvoiceCreate] = Field(..., min_length=1, max_length=5000)


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = Field(None, max_length=255)
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    amount_due: Optional[Decimal] = Field(None, gt=0)
    currency_alpha3: Optional[str] = Field(None, min_length=3, max_length=3)
    status: Optional[str] = Field(None, max_length=50)
    customer_name: Optional[str] = Field(None, max_length=500)
    payer_name: Optional[str] = Field(None, max_length=500)
    extra_data: Optional[dict] = None

    @field_validator('currency_alpha3')
    @classmethod
    def uppercase_currency(cls, v):
        if v is not None:
            return v.upper()
        return v

    @field_validator('status')
    @classmethod
    def lowercase_status(cls, v):
        if v is not None:
            return v.lower().strip()
        return v


class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    invoice_date: Optional[date]
    due_date: Optional[date]
    amount_due: float
    currency: str
    status: str
    customer_name: Optional[str]
    payer_name: Optional[str]
    extra_data: Optional[dict]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_invoice(cls, inv) -> InvoiceResponse:
        return cls(
            id=str(inv.id),
            invoice_number=inv.invoice_number,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            amount_due=float(inv.amount_due),
            currency=inv.currency,
            status=inv.status,
            customer_name=inv.customer_name,
            payer_name=inv.payer_name,
            extra_data=inv.extra_data,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
        )


# ── Payment schemas ──────────────────────────────────────────────────────────

VALID_PAYMENT_TYPES = {'ADVANCE', 'PARTIAL', 'FINAL'}


class PaymentCreate(BaseModel):
    payment_type: str = Field(..., description="ADVANCE, PARTIAL, or FINAL")
    payment_amount: Decimal = Field(..., gt=0)
    currency_alpha3: str = Field(..., min_length=3, max_length=3)
    payment_date: date
    transaction_id: Optional[str] = Field(None, max_length=255)

    @field_validator('payment_type')
    @classmethod
    def validate_payment_type(cls, v):
        v = v.upper().strip()
        if v not in VALID_PAYMENT_TYPES:
            raise ValueError(f'payment_type must be one of: {VALID_PAYMENT_TYPES}')
        return v

    @field_validator('currency_alpha3')
    @classmethod
    def uppercase_currency(cls, v):
        return v.upper()


class PaymentCreateWithInvoice(PaymentCreate):
    invoice_id: str  # UUID string


class PaymentBulkCreate(BaseModel):
    payments: list[PaymentCreateWithInvoice] = Field(..., min_length=1, max_length=5000)


class PaymentResponse(BaseModel):
    id: str
    invoice_id: str
    payment_type: str
    payment_amount: float
    currency: str
    payment_date: Optional[date]
    transaction_id: Optional[str]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_payment(cls, pay) -> PaymentResponse:
        return cls(
            id=str(pay.id),
            invoice_id=str(pay.invoice_id),
            payment_type=pay.payment_type,
            payment_amount=float(pay.payment_amount),
            currency=pay.currency,
            payment_date=pay.payment_date,
            transaction_id=pay.transaction_id,
            created_at=pay.created_at,
        )


# ── Bank Statement schemas ───────────────────────────────────────────────────

class BankStatementCreate(BaseModel):
    balance: Decimal
    currency: str = Field(..., min_length=3, max_length=3)
    account_type: Optional[str] = Field(None, max_length=50)
    statement_date: date
    attached_file_base64: Optional[str] = None  # PDF as base64

    @field_validator('currency')
    @classmethod
    def uppercase_currency(cls, v):
        return v.upper()


class BankStatementResponse(BaseModel):
    id: str
    balance: float
    currency: str
    account_type: Optional[str]
    statement_date: date
    file_path: Optional[str]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_statement(cls, bs) -> BankStatementResponse:
        return cls(
            id=str(bs.id),
            balance=float(bs.balance),
            currency=bs.currency,
            account_type=bs.account_type,
            statement_date=bs.statement_date,
            file_path=bs.file_path,
            created_at=bs.created_at,
        )


# ── Generic response wrappers ────────────────────────────────────────────────

class PaginatedInvoices(BaseModel):
    invoices: list[InvoiceResponse]
    total: int
    page: int
    per_page: int


class PaginatedPayments(BaseModel):
    payments: list[PaymentResponse]
    total: int
    page: int
    per_page: int


class PaginatedBankStatements(BaseModel):
    bank_statements: list[BankStatementResponse]
    total: int
    page: int
    per_page: int


class BulkCreateResponse(BaseModel):
    created: int
    errors: list[dict] = []
