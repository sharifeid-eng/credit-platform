"""
Tests for core/migration.py — multi-snapshot roll-rate analysis.

Regression coverage for Mode 6 Red Team Finding #4 (Section A+B): merge of
two snapshots with duplicate Deal IDs Cartesian-explodes transition counts.
The Klaim "denial-reopen pattern" (Status reverses from Completed → Executed)
routinely produces duplicates.
"""
import sys, os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.migration import compute_roll_rates


def _make_df(rows):
    """Build a minimal Klaim-shaped DataFrame for migration tests."""
    return pd.DataFrame(rows)


class TestRollRateDuplicateIdHandling:
    """Regression: merge of two snapshots without dedup produces M*N rows for
    deals that appear M times in old and N times in new — inflating counts in
    the transition matrix. compute_roll_rates must dedup per snapshot first.
    """

    def test_duplicate_ids_in_old_snapshot_do_not_inflate_matrix_counts(self):
        """ID=2 appears twice in old, once in new. Without dedup the transition
        matrix would record 2 rows for ID=2; the unique-ID count is 1."""
        base_date = pd.Timestamp('2026-03-01')
        old_df = _make_df([
            {'Deal ID': 1, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=20)},
            {'Deal ID': 2, 'Status': 'Completed', 'Deal date': base_date - pd.Timedelta(days=50)},
            {'Deal ID': 2, 'Status': 'Executed',  'Deal date': base_date - pd.Timedelta(days=50)},  # duplicate after denial-reopen
            {'Deal ID': 3, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=80)},
        ])
        new_df = _make_df([
            {'Deal ID': 1, 'Status': 'Executed',  'Deal date': base_date - pd.Timedelta(days=20)},
            {'Deal ID': 2, 'Status': 'Executed',  'Deal date': base_date - pd.Timedelta(days=50)},
            {'Deal ID': 3, 'Status': 'Completed', 'Deal date': base_date - pd.Timedelta(days=80)},
        ])
        result = compute_roll_rates(old_df, new_df, '2026-03-01', '2026-04-01')
        total_in_matrix = sum(row['total'] for row in result['matrix'])
        # 3 unique IDs in old → matched once each → matrix totals must be 3
        assert total_in_matrix == 3, (
            f"Cartesian explosion: matrix rows sum to {total_in_matrix}, "
            f"expected 3 (unique IDs). Likely missing dedup before merge."
        )

    def test_duplicate_ids_in_both_snapshots_do_not_compound(self):
        """Worst case: ID=5 appears 3 times in old AND 2 times in new — without
        dedup the matrix would record 6 transitions for that ID."""
        base_date = pd.Timestamp('2026-03-01')
        old_df = _make_df([
            {'Deal ID': 5, 'Status': 'Executed',  'Deal date': base_date - pd.Timedelta(days=10)},
            {'Deal ID': 5, 'Status': 'Completed', 'Deal date': base_date - pd.Timedelta(days=10)},
            {'Deal ID': 5, 'Status': 'Executed',  'Deal date': base_date - pd.Timedelta(days=10)},
        ])
        new_df = _make_df([
            {'Deal ID': 5, 'Status': 'Completed', 'Deal date': base_date - pd.Timedelta(days=10)},
            {'Deal ID': 5, 'Status': 'Executed',  'Deal date': base_date - pd.Timedelta(days=10)},
        ])
        result = compute_roll_rates(old_df, new_df, '2026-03-01', '2026-04-01')
        total_in_matrix = sum(row['total'] for row in result['matrix'])
        assert total_in_matrix == 1, (
            f"Cartesian compound: matrix rows sum to {total_in_matrix}, expected 1 unique ID"
        )

    def test_dedup_count_surfaced_in_summary(self):
        """Dedup must be visible — analyst needs to know the matrix was de-duplicated
        and how many rows were dropped."""
        base_date = pd.Timestamp('2026-03-01')
        old_df = _make_df([
            {'Deal ID': 1, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=10)},
            {'Deal ID': 2, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=20)},
            {'Deal ID': 2, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=20)},
        ])
        new_df = _make_df([
            {'Deal ID': 1, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=10)},
            {'Deal ID': 2, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=20)},
        ])
        result = compute_roll_rates(old_df, new_df, '2026-03-01', '2026-04-01')
        # Dedup count exposed in summary so analyst can audit
        summary = result.get('summary', {})
        assert summary.get('old_duplicates_dropped', 0) == 1
        assert summary.get('new_duplicates_dropped', 0) == 0

    def test_no_duplicates_no_dedup(self):
        """Positive case: when neither snapshot has duplicates, matrix counts
        are unchanged and dedup counts are zero."""
        base_date = pd.Timestamp('2026-03-01')
        old_df = _make_df([
            {'Deal ID': i, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=i * 5)}
            for i in range(1, 11)
        ])
        new_df = _make_df([
            {'Deal ID': i, 'Status': 'Executed', 'Deal date': base_date - pd.Timedelta(days=i * 5)}
            for i in range(1, 11)
        ])
        result = compute_roll_rates(old_df, new_df, '2026-03-01', '2026-04-01')
        total_in_matrix = sum(row['total'] for row in result['matrix'])
        assert total_in_matrix == 10
        summary = result.get('summary', {})
        assert summary.get('old_duplicates_dropped', 0) == 0
        assert summary.get('new_duplicates_dropped', 0) == 0
