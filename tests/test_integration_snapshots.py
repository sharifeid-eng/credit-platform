"""Integration API live-snapshot write-path regression tests (Session 31, Phase 5).

Pins the contract that:
- Integration API writes create (or same-day UPSERT into) a rolling-daily
  `live-YYYY-MM-DD` snapshot per product.
- Payments inherit their parent invoice's snapshot_id.
- Only today's live snapshot accepts writes/updates/deletes; tape snapshots
  and prior-day live snapshots return 409.
- Existing Integration API request/response contracts are preserved — no
  caller-visible breaking changes from the snapshot dimension.

All tests use FastAPI's TestClient with get_current_org overridden to a test
org. Each test cleans up rows it creates so the DB converges back to the
tape-seeded baseline.
"""
import datetime as dt
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.auth import get_current_org
from backend.main import app
from core.database import SessionLocal, engine, get_db
from core.db_loader import get_or_create_live_snapshot
from core.models import Invoice, Organization, Payment, Product, Snapshot

pytestmark = pytest.mark.skipif(engine is None, reason="DATABASE_URL not configured")


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_session():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="module")
def test_org(db_session):
    """A dedicated test org + product that tests own completely. Cleaned at end."""
    org = db_session.query(Organization).filter_by(name='__snapshot_test_org__').first()
    if org is None:
        org = Organization(id=uuid.uuid4(), name='__snapshot_test_org__')
        db_session.add(org)
        db_session.flush()
        prod = Product(
            id=uuid.uuid4(), org_id=org.id, name='test_product',
            currency='AED', analysis_type='klaim',
        )
        db_session.add(prod)
        db_session.commit()

    yield org

    # Teardown — ORM delete walks cascades (products → snapshots → invoices → payments)
    org_obj = db_session.query(Organization).filter_by(id=org.id).first()
    if org_obj is not None:
        db_session.delete(org_obj)
        db_session.commit()


@pytest.fixture
def client(test_org):
    """TestClient with get_current_org overridden to the test org."""
    def _stub_org():
        # Re-fetch on each call so the ORM instance is attached to the request's session
        db = next(get_db())
        try:
            org = db.query(Organization).filter_by(id=test_org.id).first()
            if org is not None:
                # Detach so it can be re-used across requests
                db.expunge(org)
            return org
        finally:
            db.close()

    app.dependency_overrides[get_current_org] = _stub_org
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.fixture
def clean_test_product(db_session, test_org):
    """Wipe snapshots (and their cascaded invoices + payments) for the test
    product before AND after each test. Ensures isolation."""
    def _wipe():
        prod = db_session.query(Product).filter_by(org_id=test_org.id, name='test_product').first()
        if prod is not None:
            snaps = db_session.query(Snapshot).filter_by(product_id=prod.id).all()
            for s in snaps:
                db_session.delete(s)
            db_session.commit()

    _wipe()
    yield
    _wipe()


# ── Invoice write path ───────────────────────────────────────────────────────

class TestCreateInvoice:

    def test_first_push_creates_live_snapshot(self, client, db_session, test_org, clean_test_product):
        """POST /invoices creates a live-YYYY-MM-DD snapshot and tags the invoice with it."""
        today = dt.datetime.now(dt.timezone.utc).date()

        r = client.post("/api/integration/invoices", json=_invoice_payload("I-001", amount=1000))
        assert r.status_code == 201
        inv_id = r.json()['id']

        # Verify a live snapshot was created
        prod = db_session.query(Product).filter_by(org_id=test_org.id).first()
        snaps = db_session.query(Snapshot).filter_by(product_id=prod.id).all()
        assert len(snaps) == 1
        snap = snaps[0]
        assert snap.source == 'live'
        assert snap.name == f"live-{today.isoformat()}"
        assert snap.taken_at == today

        # Invoice tagged with the snapshot
        inv = db_session.query(Invoice).filter_by(id=inv_id).first()
        assert inv.snapshot_id == snap.id

    def test_same_day_second_push_reuses_snapshot(self, client, db_session, test_org, clean_test_product):
        client.post("/api/integration/invoices", json=_invoice_payload("I-001"))
        client.post("/api/integration/invoices", json=_invoice_payload("I-002"))

        prod = db_session.query(Product).filter_by(org_id=test_org.id).first()
        snaps = db_session.query(Snapshot).filter_by(product_id=prod.id).all()
        assert len(snaps) == 1, "Same-day pushes must share one snapshot"
        assert snaps[0].row_count == 2

    def test_same_day_same_invoice_number_upserts(self, client, db_session, test_org, clean_test_product):
        """Pushing the same invoice_number twice same-day UPDATES in place."""
        r1 = client.post("/api/integration/invoices", json=_invoice_payload("I-001", amount=1000, status="executed"))
        r2 = client.post("/api/integration/invoices", json=_invoice_payload("I-001", amount=1500, status="completed"))

        assert r1.status_code == 201
        assert r2.status_code == 201
        # Same row, state updated
        assert r1.json()['id'] == r2.json()['id'], "UPSERT must return the same invoice id"

        prod = db_session.query(Product).filter_by(org_id=test_org.id).first()
        invs = db_session.query(Invoice).filter_by(product_id=prod.id).all()
        assert len(invs) == 1, "Same invoice_number same day → single row, not two"
        assert float(invs[0].amount_due) == 1500
        assert invs[0].status == 'completed'

        snap = db_session.query(Snapshot).filter_by(product_id=prod.id).first()
        assert snap.row_count == 1, "UPSERT doesn't increment row_count"

    def test_bulk_create_all_in_same_snapshot(self, client, db_session, test_org, clean_test_product):
        items = [_invoice_payload(f"I-{i:03d}") for i in range(5)]
        r = client.post("/api/integration/invoices/bulk", json={"invoices": items})
        assert r.status_code == 201
        assert r.json()['created'] == 5
        assert r.json()['errors'] == []

        prod = db_session.query(Product).filter_by(org_id=test_org.id).first()
        snaps = db_session.query(Snapshot).filter_by(product_id=prod.id).all()
        assert len(snaps) == 1
        assert snaps[0].row_count == 5

    def test_patch_live_snapshot_succeeds(self, client, db_session, test_org, clean_test_product):
        r = client.post("/api/integration/invoices", json=_invoice_payload("I-001", amount=1000))
        inv_id = r.json()['id']

        r2 = client.patch(f"/api/integration/invoices/{inv_id}", json={"amount_due": "2500"})
        assert r2.status_code == 200
        assert float(r2.json()['amount_due']) == 2500

    def test_patch_tape_snapshot_returns_409(self, client, db_session, test_org, clean_test_product):
        """Tape-snapshot invoices are immutable — PATCH must 409."""
        # Manually create a tape snapshot + invoice belonging to the test product
        prod = db_session.query(Product).filter_by(org_id=test_org.id).first()
        tape_snap = Snapshot(
            id=uuid.uuid4(), product_id=prod.id, name='2099-01-01_test_tape',
            source='tape', taken_at=date(2099, 1, 1), row_count=1,
        )
        db_session.add(tape_snap)
        db_session.flush()
        inv = Invoice(
            id=uuid.uuid4(), org_id=test_org.id, product_id=prod.id,
            snapshot_id=tape_snap.id, invoice_number='TAPE-001',
            amount_due=Decimal('1000'), currency='AED', status='executed',
        )
        db_session.add(inv)
        db_session.commit()

        r = client.patch(f"/api/integration/invoices/{inv.id}", json={"amount_due": "2000"})
        assert r.status_code == 409
        assert 'immutable snapshot' in r.json()['detail'].lower()
        assert 'tape' in r.json()['detail'].lower()

    def test_delete_tape_snapshot_returns_409(self, client, db_session, test_org, clean_test_product):
        prod = db_session.query(Product).filter_by(org_id=test_org.id).first()
        tape_snap = Snapshot(
            id=uuid.uuid4(), product_id=prod.id, name='2099-01-02_test_tape',
            source='tape', taken_at=date(2099, 1, 2), row_count=1,
        )
        db_session.add(tape_snap)
        db_session.flush()
        inv = Invoice(
            id=uuid.uuid4(), org_id=test_org.id, product_id=prod.id,
            snapshot_id=tape_snap.id, invoice_number='TAPE-002',
            amount_due=Decimal('500'), currency='AED', status='executed',
        )
        db_session.add(inv)
        db_session.commit()

        r = client.delete(f"/api/integration/invoices/{inv.id}")
        assert r.status_code == 409


# ── Payment write path ───────────────────────────────────────────────────────

class TestPaymentSnapshotInheritance:

    def test_payment_inherits_invoice_snapshot(self, client, db_session, test_org, clean_test_product):
        """POST /invoices/{id}/payments → payment.snapshot_id = invoice.snapshot_id."""
        r = client.post("/api/integration/invoices", json=_invoice_payload("I-001", amount=1000))
        inv_id = r.json()['id']
        inv = db_session.query(Invoice).filter_by(id=inv_id).first()

        r2 = client.post(f"/api/integration/invoices/{inv_id}/payments", json={
            "payment_type": "PARTIAL",
            "payment_amount": "400",
            "currency_alpha3": "AED",
            "payment_date": dt.date.today().isoformat(),
        })
        assert r2.status_code == 201
        pay_id = r2.json()['id']
        pay = db_session.query(Payment).filter_by(id=pay_id).first()
        assert pay.snapshot_id == inv.snapshot_id

    def test_payment_on_tape_invoice_returns_409(self, client, db_session, test_org, clean_test_product):
        """Payments can't be written against invoices in a tape snapshot."""
        prod = db_session.query(Product).filter_by(org_id=test_org.id).first()
        tape_snap = Snapshot(
            id=uuid.uuid4(), product_id=prod.id, name='2099-01-03_test_tape',
            source='tape', taken_at=date(2099, 1, 3), row_count=1,
        )
        db_session.add(tape_snap)
        db_session.flush()
        inv = Invoice(
            id=uuid.uuid4(), org_id=test_org.id, product_id=prod.id,
            snapshot_id=tape_snap.id, invoice_number='TAPE-003',
            amount_due=Decimal('1000'), currency='AED', status='executed',
        )
        db_session.add(inv)
        db_session.commit()

        r = client.post(f"/api/integration/invoices/{inv.id}/payments", json={
            "payment_type": "PARTIAL",
            "payment_amount": "100",
            "currency_alpha3": "AED",
            "payment_date": dt.date.today().isoformat(),
        })
        assert r.status_code == 409


# ── Read-path compatibility ──────────────────────────────────────────────────

class TestReadPathCompat:
    """Existing GET endpoints must keep working post-snapshot."""

    def test_get_invoices_still_works(self, client, db_session, test_org, clean_test_product):
        client.post("/api/integration/invoices", json=_invoice_payload("I-001"))
        client.post("/api/integration/invoices", json=_invoice_payload("I-002"))

        r = client.get("/api/integration/invoices")
        assert r.status_code == 200
        body = r.json()
        assert body['total'] == 2
        # Response contract unchanged
        assert 'invoices' in body
        assert len(body['invoices']) == 2


# ── Helpers ──────────────────────────────────────────────────────────────────

def _invoice_payload(invoice_number: str, amount: float = 1000, status: str = "executed") -> dict:
    return {
        "invoice_number": invoice_number,
        "invoice_date": dt.date.today().isoformat(),
        "amount_due": str(amount),
        "currency_alpha3": "AED",
        "status": status,
        "customer_name": "TestCustomer",
    }
