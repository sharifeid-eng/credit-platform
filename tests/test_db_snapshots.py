"""DB snapshot layer regression tests (Session 31).

Pins the invariants introduced by the "snapshots as first-class dimension" work:
- Tape ingest creates one Snapshot row per file.
- `extra_data` JSONB round-trips every non-core tape column under its
  original name — new analytical columns flow through DB automatically.
- `resolve_snapshot` handles name / filename-with-extension / ISO-date / None.
- `load_klaim_from_db` produces a DataFrame semantically identical to the
  one produced by `core.loader.load_snapshot` on the same tape file
  (subject to payment-aggregation float precision).
- Snapshots are isolated: Apr 15's computed WAL is unaffected by Mar 3's.
- Live snapshot helper creates today's `live-YYYY-MM-DD` on demand, is
  idempotent across concurrent calls, and `is_snapshot_mutable` enforces
  the only-today-accepts-writes rule.

All tests run against the live DB configured by `DATABASE_URL`. Ingest_tape
has already been run so the tape snapshots exist.
"""
import datetime as dt
import os
import uuid
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import select

from core.database import SessionLocal, engine
from core.db_loader import (
    get_or_create_live_snapshot,
    is_snapshot_mutable,
    list_snapshots,
    load_from_db,
    load_klaim_from_db,
    resolve_snapshot,
    get_product_record,
)
from core.loader import load_snapshot
from core.models import Invoice, Organization, Payment, Product, Snapshot


pytestmark = pytest.mark.skipif(engine is None, reason="DATABASE_URL not configured")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def klaim_product(db):
    prod = get_product_record(db, "klaim", "UAE_healthcare")
    if prod is None:
        pytest.skip("Klaim/UAE_healthcare not seeded")
    return prod


# ── Ingest round-trip ─────────────────────────────────────────────────────────

class TestIngestRoundTrip:
    """Verify scripts/ingest_tape.py produces a snapshot with all columns preserved."""

    def test_tape_snapshots_exist_for_klaim(self, db, klaim_product):
        snaps = db.execute(
            select(Snapshot).where(
                Snapshot.product_id == klaim_product.id,
                Snapshot.source == 'tape',
            )
        ).scalars().all()
        assert len(snaps) >= 5, (
            f"Expected 5+ Klaim tape snapshots, found {len(snaps)}. "
            f"Run `python scripts/ingest_tape.py --company klaim --product UAE_healthcare --all`."
        )

    def test_apr15_snapshot_has_8080_invoices(self, db, klaim_product):
        snap = db.execute(
            select(Snapshot).where(
                Snapshot.product_id == klaim_product.id,
                Snapshot.name == '2026-04-15_uae_healthcare',
            )
        ).scalar_one_or_none()
        if snap is None:
            pytest.skip("Apr 15 snapshot not ingested")
        row_count = db.execute(
            select(Invoice).where(Invoice.snapshot_id == snap.id)
        ).scalars().all()
        assert len(row_count) == 8080
        assert snap.row_count == 8080
        assert snap.taken_at == date(2026, 4, 15)

    def test_apr15_extra_data_carries_all_new_columns(self, db, klaim_product):
        """The raison d'être of Session 31: new tape columns must flow through DB."""
        snap = db.execute(
            select(Snapshot).where(
                Snapshot.product_id == klaim_product.id,
                Snapshot.name == '2026-04-15_uae_healthcare',
            )
        ).scalar_one_or_none()
        if snap is None:
            pytest.skip("Apr 15 snapshot not ingested")
        sample = db.execute(
            select(Invoice).where(Invoice.snapshot_id == snap.id).limit(1)
        ).scalar_one()

        assert sample.extra_data is not None
        assert 'Expected collection days' in sample.extra_data, (
            "Expected collection days must be in extra_data — this is the column "
            "that fixes wal_total=n/a and enables direct-DPD PAR on Apr 15"
        )
        assert 'Collection days so far' in sample.extra_data, (
            "Collection days so far must be in extra_data — close-date proxy for wal_total"
        )
        assert 'Provider' in sample.extra_data, (
            "Provider must be in extra_data — drives branch-level concentration on Apr 15"
        )

    def test_mar3_extra_data_lacks_apr15_only_columns(self, db, klaim_product):
        """Mar 3 tape predates the new columns — they must NOT appear in its extra_data."""
        snap = db.execute(
            select(Snapshot).where(
                Snapshot.product_id == klaim_product.id,
                Snapshot.name == '2026-03-03_uae_healthcare',
            )
        ).scalar_one_or_none()
        if snap is None:
            pytest.skip("Mar 3 snapshot not ingested")
        sample = db.execute(
            select(Invoice).where(Invoice.snapshot_id == snap.id).limit(1)
        ).scalar_one()

        assert sample.extra_data is not None
        # Mar 3 has Expected IRR + Actual IRR (added in Mar)
        assert 'Expected IRR' in sample.extra_data
        # But NOT the Apr 15 additions
        assert 'Expected collection days' not in sample.extra_data
        assert 'Collection days so far' not in sample.extra_data
        assert 'Provider' not in sample.extra_data


# ── Snapshot resolution ───────────────────────────────────────────────────────

class TestResolveSnapshot:

    def test_resolve_by_exact_name(self, db):
        snap = resolve_snapshot(db, "klaim", "UAE_healthcare", "2026-04-15_uae_healthcare")
        assert snap is not None
        assert snap.name == "2026-04-15_uae_healthcare"

    def test_resolve_strips_csv_extension(self, db):
        snap = resolve_snapshot(db, "klaim", "UAE_healthcare", "2026-04-15_uae_healthcare.csv")
        assert snap is not None
        assert snap.name == "2026-04-15_uae_healthcare"

    def test_resolve_strips_xlsx_extension(self, db):
        snap = resolve_snapshot(db, "klaim", "UAE_healthcare", "2025-12-08_uae_healthcare.xlsx")
        # Worktree may or may not have the Dec 8 xlsx ingested; either outcome is valid
        if snap is not None:
            assert snap.name == "2025-12-08_uae_healthcare"

    def test_resolve_by_iso_date(self, db):
        snap = resolve_snapshot(db, "klaim", "UAE_healthcare", "2026-04-15")
        assert snap is not None
        assert snap.taken_at == date(2026, 4, 15)

    def test_resolve_none_returns_latest(self, db):
        snap = resolve_snapshot(db, "klaim", "UAE_healthcare", None)
        assert snap is not None
        # Latest should be Apr 15 (the newest tape ingested)
        assert snap.taken_at == date(2026, 4, 15)

    def test_resolve_unknown_returns_none(self, db):
        assert resolve_snapshot(db, "klaim", "UAE_healthcare", "does-not-exist") is None

    def test_resolve_unknown_company(self, db):
        assert resolve_snapshot(db, "ghost-co", "UAE_healthcare", "2026-04-15") is None


class TestListSnapshots:

    def test_klaim_snapshots_ordered_oldest_first(self, db):
        snaps = list_snapshots(db, "klaim", "UAE_healthcare")
        assert len(snaps) >= 2
        # taken_at strictly non-decreasing
        dates = [s['date'] for s in snaps]
        assert dates == sorted(dates), f"Expected oldest-first, got {dates}"

    def test_snapshot_shape_includes_source_and_row_count(self, db):
        snaps = list_snapshots(db, "klaim", "UAE_healthcare")
        assert len(snaps) >= 1
        s = snaps[0]
        assert 'source' in s
        assert 'row_count' in s
        assert s['source'] in ('tape', 'live', 'manual')


# ── DataFrame round-trip ──────────────────────────────────────────────────────

class TestLoadFromDB:
    """DB-loaded DataFrame should match direct tape load (modulo float precision
    on payments aggregated from one PARTIAL row each)."""

    def test_apr15_load_returns_8080_rows(self, db):
        df = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                 snapshot_id=_snap_id(db, "2026-04-15_uae_healthcare"))
        assert len(df) == 8080

    def test_apr15_has_new_columns_as_df_columns(self, db):
        df = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                 snapshot_id=_snap_id(db, "2026-04-15_uae_healthcare"))
        for col in ('Expected collection days', 'Collection days so far', 'Provider'):
            assert col in df.columns, (
                f"{col!r} missing from DB-loaded DataFrame — extra_data spread-back broken"
            )

    def test_apr15_db_matches_tape_on_active_totals(self, db):
        db_df = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                    snapshot_id=_snap_id(db, "2026-04-15_uae_healthcare"))
        tape_path = _tape_path("klaim", "UAE_healthcare", "2026-04-15_uae_healthcare.csv")
        if not os.path.exists(tape_path):
            pytest.skip("Apr 15 tape not present on disk")
        tape_df = load_snapshot(tape_path)

        assert len(db_df) == len(tape_df)

        # Status distribution identical
        assert db_df['Status'].value_counts().to_dict() == tape_df['Status'].value_counts().to_dict()

        # Active active-pool totals within $1,500 (allow PARTIAL-payment float drift)
        db_act = db_df[db_df['Status'] == 'Executed']
        tape_act = tape_df[tape_df['Status'] == 'Executed']
        assert abs(db_act['Purchase value'].sum() - tape_act['Purchase value'].sum()) < 1
        coll_diff = abs(db_act['Collected till date'].sum() - tape_act['Collected till date'].sum())
        assert coll_diff < 1500, f"Collected aggregate diverged by {coll_diff:.2f}"

    def test_load_from_db_dispatches_by_analysis_type(self, db):
        klaim_df = load_from_db(db, "klaim", "UAE_healthcare")
        silq_df = load_from_db(db, "SILQ", "KSA")
        # Klaim has "Group" column; SILQ has "Shop_ID"
        assert 'Group' in klaim_df.columns
        assert 'Shop_ID' in silq_df.columns

    def test_unknown_analysis_type_returns_empty_df(self, db):
        # Ejari has analysis_type='ejari_summary' — not tape-ingested
        df = load_from_db(db, "Ejari", "RNPL")
        assert isinstance(df, pd.DataFrame)
        assert df.empty


# ── Snapshot isolation ───────────────────────────────────────────────────────

class TestSnapshotIsolation:
    """Two snapshots of the same product must produce analytically-independent
    DataFrames. This is the property the Mar 3 → Apr 15 ambiguity broke
    before Session 31."""

    def test_apr15_and_mar3_have_different_row_counts(self, db):
        apr15 = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                    snapshot_id=_snap_id(db, "2026-04-15_uae_healthcare"))
        mar3 = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                   snapshot_id=_snap_id(db, "2026-03-03_uae_healthcare"))
        assert len(apr15) == 8080
        assert len(mar3) == 7697
        assert len(apr15) != len(mar3)

    def test_apr15_wal_matches_148_mar3_wal_matches_140(self, db):
        """WAL must be computed against each snapshot's own data, not blended."""
        from core.portfolio import compute_klaim_covenants
        apr_df = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                     snapshot_id=_snap_id(db, "2026-04-15_uae_healthcare"))
        mar_df = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                     snapshot_id=_snap_id(db, "2026-03-03_uae_healthcare"))

        apr_wal = _wal(compute_klaim_covenants(apr_df, mult=1, ref_date='2026-04-15'))
        mar_wal = _wal(compute_klaim_covenants(mar_df, mult=1, ref_date='2026-03-03'))

        assert apr_wal['wal_active_days'] == pytest.approx(148, abs=1)
        assert mar_wal['wal_active_days'] == pytest.approx(140, abs=1)

    def test_apr15_wal_total_resolves_mar3_wal_total_is_none(self, db):
        """Apr 15 has Collection days so far → wal_total computes.
        Mar 3 doesn't → wal_total=None (graceful degradation)."""
        from core.portfolio import compute_klaim_covenants
        apr_df = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                     snapshot_id=_snap_id(db, "2026-04-15_uae_healthcare"))
        mar_df = load_klaim_from_db(db, "klaim", "UAE_healthcare",
                                     snapshot_id=_snap_id(db, "2026-03-03_uae_healthcare"))

        apr_wal = _wal(compute_klaim_covenants(apr_df, mult=1, ref_date='2026-04-15'))
        mar_wal = _wal(compute_klaim_covenants(mar_df, mult=1, ref_date='2026-03-03'))

        assert apr_wal['wal_total_days'] is not None
        assert apr_wal['wal_total_days'] == pytest.approx(137, abs=2)
        assert apr_wal['wal_total_method'] == 'collection_days_so_far'

        assert mar_wal['wal_total_days'] is None
        assert mar_wal['wal_total_method'] == 'unavailable'


# ── Live snapshot helper ─────────────────────────────────────────────────────

class TestLiveSnapshotHelper:

    def test_first_call_creates_live_snapshot(self, db, klaim_product):
        """get_or_create_live_snapshot creates live-YYYY-MM-DD if none exists for today."""
        # Use a future date to avoid colliding with any real live snapshot
        future = date(2099, 1, 1)
        name = f"live-{future.isoformat()}"
        db.query(Snapshot).filter_by(product_id=klaim_product.id, name=name).delete()
        db.commit()

        snap = get_or_create_live_snapshot(db, klaim_product, as_of=future)
        assert snap.source == 'live'
        assert snap.name == name
        assert snap.taken_at == future
        assert snap.product_id == klaim_product.id

        db.query(Snapshot).filter_by(id=snap.id).delete()
        db.commit()

    def test_second_call_same_day_returns_same_snapshot(self, db, klaim_product):
        future = date(2099, 1, 2)
        name = f"live-{future.isoformat()}"
        db.query(Snapshot).filter_by(product_id=klaim_product.id, name=name).delete()
        db.commit()

        a = get_or_create_live_snapshot(db, klaim_product, as_of=future)
        db.commit()
        b = get_or_create_live_snapshot(db, klaim_product, as_of=future)
        assert a.id == b.id, "Same-day calls must return the same snapshot row"

        db.query(Snapshot).filter_by(id=a.id).delete()
        db.commit()

    def test_different_days_get_different_snapshots(self, db, klaim_product):
        d1, d2 = date(2099, 2, 1), date(2099, 2, 2)
        for d in (d1, d2):
            db.query(Snapshot).filter_by(product_id=klaim_product.id, name=f"live-{d.isoformat()}").delete()
        db.commit()

        s1 = get_or_create_live_snapshot(db, klaim_product, as_of=d1)
        db.commit()
        s2 = get_or_create_live_snapshot(db, klaim_product, as_of=d2)
        db.commit()
        assert s1.id != s2.id
        assert s1.taken_at != s2.taken_at

        db.query(Snapshot).filter_by(id=s1.id).delete()
        db.query(Snapshot).filter_by(id=s2.id).delete()
        db.commit()


class TestIsSnapshotMutable:

    def test_none_snapshot_is_not_mutable(self):
        assert is_snapshot_mutable(None) is False

    def test_tape_snapshot_never_mutable(self, db):
        tape = db.execute(
            select(Snapshot).where(Snapshot.source == 'tape').limit(1)
        ).scalar_one()
        assert is_snapshot_mutable(tape) is False

    def test_today_live_is_mutable(self, db, klaim_product):
        today = dt.datetime.now(dt.timezone.utc).date()
        name = f"live-{today.isoformat()}"
        db.query(Snapshot).filter_by(product_id=klaim_product.id, name=name).delete()
        db.commit()
        snap = get_or_create_live_snapshot(db, klaim_product, as_of=today)
        db.commit()
        try:
            assert is_snapshot_mutable(snap, today=today) is True
        finally:
            db.query(Snapshot).filter_by(id=snap.id).delete()
            db.commit()

    def test_yesterday_live_is_not_mutable(self, db, klaim_product):
        """Prior-day live snapshots are frozen history. Explicit `today` arg
        isolates the test from wall-clock drift."""
        today = date(2099, 3, 10)
        yesterday = today - timedelta(days=1)
        name = f"live-{yesterday.isoformat()}"
        db.query(Snapshot).filter_by(product_id=klaim_product.id, name=name).delete()
        db.commit()
        snap = get_or_create_live_snapshot(db, klaim_product, as_of=yesterday)
        db.commit()
        try:
            assert is_snapshot_mutable(snap, today=today) is False
        finally:
            db.query(Snapshot).filter_by(id=snap.id).delete()
            db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _snap_id(db, name: str) -> uuid.UUID:
    snap = db.execute(select(Snapshot).where(Snapshot.name == name)).scalar_one_or_none()
    if snap is None:
        pytest.skip(f"Snapshot {name!r} not ingested")
    return snap.id


def _wal(covenant_result: dict) -> dict:
    return [c for c in covenant_result['covenants'] if 'life' in c['name'].lower()][0]


def _tape_path(company: str, product: str, filename: str) -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, 'data', company, product, filename)
