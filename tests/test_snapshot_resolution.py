"""Regression tests for snapshot-identifier resolution in tape analytics.

Pins the fix for a silent data-correctness bug: the `/snapshots` endpoint
returns names WITH extension for filesystem-sourced products (ejari, tamara,
aajil) and WITHOUT extension for DB-sourced products (klaim, silq, which
since Session 31 are served from the `snapshots` table where `name` omits
the extension). The frontend echoed the string back, and the old `_load()`
attempted exact-filename match against `get_snapshots()` (filesystem, WITH
extension). On mismatch it fell through to a date match and then silently
returned `snaps[-1]` (latest). Analysts picking a non-latest DB-style name
were shown the latest tape without any error or badge change — the worst
class of bug: silent, invisible, no log warning.

The fix (in `backend/main.py`):
  - `_match_snapshot()` helper: exact filename → extension-stripped
    filename → single-date match → HTTP 400.
  - `snapshot=None` preserves the caller-has-no-preference default
    (returns latest). Any NON-empty identifier must resolve exactly or
    raise — no more silent fallback to latest.

The load-bearing test is `test_unknown_snapshot_raises_400_never_silent_latest`.
If that fails, the silent-fallback bug has been reintroduced.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.main import _match_snapshot, _strip_snapshot_ext


# Shape mirrors core.loader.get_snapshots(): {filename, filepath, date}.
# Filenames carry extensions because that is the filesystem truth; the DB
# `/snapshots` endpoint returns the same logical snapshots without them.
SNAPS = [
    {'filename': '2025-09-23_uae_healthcare.csv', 'filepath': '/d/2025-09-23_uae_healthcare.csv', 'date': '2025-09-23'},
    {'filename': '2025-12-08_uae_healthcare.xlsx', 'filepath': '/d/2025-12-08_uae_healthcare.xlsx', 'date': '2025-12-08'},
    {'filename': '2026-02-20_uae_healthcare.csv', 'filepath': '/d/2026-02-20_uae_healthcare.csv', 'date': '2026-02-20'},
    {'filename': '2026-03-03_uae_healthcare.csv', 'filepath': '/d/2026-03-03_uae_healthcare.csv', 'date': '2026-03-03'},
]


class TestStripExt:
    def test_strips_known_extensions(self):
        assert _strip_snapshot_ext('foo.csv') == 'foo'
        assert _strip_snapshot_ext('foo.xlsx') == 'foo'
        assert _strip_snapshot_ext('foo.ods') == 'foo'
        assert _strip_snapshot_ext('foo.json') == 'foo'

    def test_passes_through_when_no_known_extension(self):
        assert _strip_snapshot_ext('live-2026-04-21') == 'live-2026-04-21'
        assert _strip_snapshot_ext('2026-04-15_uae_healthcare') == '2026-04-15_uae_healthcare'
        assert _strip_snapshot_ext('weird.pdf') == 'weird.pdf'


class TestMatchSnapshot:
    """Pure-function coverage for the resolution contract."""

    # ── Tape-source baseline: names WITH extension still resolve. ─────────

    def test_tape_source_baseline_filename_with_extension_resolves(self):
        """Existing filesystem flow (ejari/tamara/aajil) must keep working."""
        sel = _match_snapshot(SNAPS, '2025-09-23_uae_healthcare.csv')
        assert sel['filename'] == '2025-09-23_uae_healthcare.csv'
        assert sel['date'] == '2025-09-23'

    def test_tape_source_baseline_xlsx_resolves(self):
        sel = _match_snapshot(SNAPS, '2025-12-08_uae_healthcare.xlsx')
        assert sel['date'] == '2025-12-08'

    # ── Primary fix: DB-style names (no extension) now resolve. ───────────

    def test_db_style_name_without_extension_resolves(self):
        """THE bug reproduction. Before the fix, this fell through to
        snaps[-1] = the March 3 tape, silently. Now it must resolve to
        the correct September 23 snapshot."""
        sel = _match_snapshot(SNAPS, '2025-09-23_uae_healthcare')
        assert sel['filename'] == '2025-09-23_uae_healthcare.csv', (
            "DB-style name stripped of .csv must resolve to the matching "
            "filesystem snapshot — not silently fall through to latest."
        )
        assert sel['date'] == '2025-09-23'

    def test_db_style_xlsx_name_without_extension_resolves(self):
        """Same contract for .xlsx-backed snapshots."""
        sel = _match_snapshot(SNAPS, '2025-12-08_uae_healthcare')
        assert sel['filename'] == '2025-12-08_uae_healthcare.xlsx'
        assert sel['date'] == '2025-12-08'

    # ── Load-bearing: unknown identifier fails loudly, NEVER silent latest.

    def test_unknown_snapshot_raises_400_never_silent_latest(self):
        """If this test regresses, the silent data-correctness bug is back.

        The contract: a non-empty snapshot identifier that does not map to
        any known filename, extension-stripped filename, or single date
        MUST raise HTTP 400. It must NOT silently return the latest
        snapshot — analysts relying on the picker would see wrong data
        with no error.
        """
        with pytest.raises(HTTPException) as ei:
            _match_snapshot(SNAPS, 'totally-fake-snapshot-name')
        assert ei.value.status_code == 400
        # Message should name the missing identifier and list alternatives
        # so the caller can self-correct without log-diving.
        assert 'totally-fake-snapshot-name' in ei.value.detail
        assert 'Available' in ei.value.detail

    def test_live_only_db_name_with_no_file_raises_400(self):
        """A DB-only live snapshot like `live-2026-04-21` has no file on
        disk. Tape-analytics `_load()` reads filesystem, so it must 400,
        not silently serve the latest tape."""
        with pytest.raises(HTTPException) as ei:
            _match_snapshot(SNAPS, 'live-2026-04-21')
        assert ei.value.status_code == 400

    # ── Preserved behaviour: None = "no preference" still returns latest. ─

    def test_none_returns_latest_preserves_caller_default(self):
        """Callers passing snapshot=None (no query param) explicitly mean
        'give me the latest'. That is NOT the silent-fallback bug — the
        bug was silent fallback on a SPECIFIED but unknown name."""
        sel = _match_snapshot(SNAPS, None)
        assert sel['filename'] == '2026-03-03_uae_healthcare.csv'

    def test_empty_string_returns_latest_same_as_none(self):
        sel = _match_snapshot(SNAPS, '')
        assert sel['filename'] == '2026-03-03_uae_healthcare.csv'

    # ── Date-based resolution (retained from pre-fix behaviour). ──────────

    def test_iso_date_resolves_when_unique(self):
        sel = _match_snapshot(SNAPS, '2025-12-08')
        assert sel['filename'] == '2025-12-08_uae_healthcare.xlsx'

    def test_ambiguous_date_raises_400(self):
        """Two files on the same date → the caller must disambiguate by
        filename. Retained from the pre-fix code."""
        dup_snaps = SNAPS + [
            {'filename': '2025-09-23_uae_healthcare_v2.csv',
             'filepath': '/d/2025-09-23_uae_healthcare_v2.csv',
             'date': '2025-09-23'},
        ]
        with pytest.raises(HTTPException) as ei:
            _match_snapshot(dup_snaps, '2025-09-23')
        assert ei.value.status_code == 400
        assert 'Ambiguous' in ei.value.detail
