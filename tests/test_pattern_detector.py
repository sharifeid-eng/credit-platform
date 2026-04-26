"""
Recurring channel pattern detection tests.

Covers `core/mind/pattern_detector.py`:
- Detection per company: thresholds, classification, cadence, idempotency
- Cross-company emergent patterns: only surface (≥2 companies, same combo)
- Mind integration: writes to Company Mind via the new generic record() API
- Auto-fire safety: detector failures must NEVER raise out of the wrapper

All tests use the shared `isolated_data_dir` fixture from conftest.py so
fabricated company names don't leak empty folders into real data/.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from core.mind.pattern_detector import (
    EmergentPattern,
    RecurringPattern,
    auto_fire_after_ingest,
    detect_emergent_asset_class_patterns,
    detect_recurring_patterns,
    write_fund_wide_stats,
    write_patterns_to_company_mind,
)


# ── Test helpers ──────────────────────────────────────────────────────────


def _make_registry_entry(
    *,
    doc_id: str,
    document_type: str,
    filename: str,
    ingested_at: str,
    sha256: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "doc_id": doc_id,
        "document_type": document_type,
        "filename": filename,
        "filepath": f"/tmp/{filename}",
        "ingested_at": ingested_at,
        "sha256": sha256 or f"sha256_{doc_id}",
        "chunk_count": 1,
        "page_count": 1,
        "text_length": 100,
    }


def _seed_dataroom(
    data_dir: Path,
    company: str,
    entries: List[Dict[str, Any]],
    *,
    asset_class: str = "bnpl",
    add_hook: bool = False,
    product: str = "KSA",
) -> Path:
    """Materialize a registry.json + config.json + (optional) post-ingest hook."""
    dr = data_dir / company / "dataroom"
    dr.mkdir(parents=True, exist_ok=True)
    registry = {e["doc_id"]: e for e in entries}
    (dr / "registry.json").write_text(json.dumps(registry, indent=2))

    # Always seed a config.json so asset_class resolves
    prod_dir = data_dir / company / product
    prod_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "currency": "USD",
        "company": company,
        "product": product,
        "analysis_type": "test_type",
        "asset_class": asset_class,
    }
    (prod_dir / "config.json").write_text(json.dumps(cfg, indent=2))

    if add_hook:
        (dr / ".post-ingest.sh").write_text("#!/bin/bash\necho hook\n")
    return dr


def _make_scripts_dir(tmp_path: Path, parsers: List[str] = None) -> Path:
    """Create an empty scripts dir with optional parser stubs."""
    sd = tmp_path / "scripts"
    sd.mkdir(parents=True, exist_ok=True)
    for name in (parsers or []):
        (sd / name).write_text("# stub parser\n")
    return sd


def _ts(days_ago: int) -> str:
    """ISO timestamp `days_ago` days before now (UTC)."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# ── Detection: thresholds + classification ───────────────────────────────


class TestThresholdsAndClassification:
    def test_detect_returns_empty_for_company_with_no_dataroom(self, isolated_data_dir):
        """No registry → empty result, no crash."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        patterns = detect_recurring_patterns(
            "ghost_co", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns == []
        # Confirm no folder was leaked into data/
        assert not (isolated_data_dir / "ghost_co").exists()

    def test_detect_returns_empty_for_empty_registry(self, isolated_data_dir):
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(isolated_data_dir, "EmptyCo", entries=[])
        patterns = detect_recurring_patterns(
            "EmptyCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns == []

    def test_detect_groups_by_document_type(self, isolated_data_dir):
        """Different document_types form independent clusters."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "GroupCo",
            entries=[
                _make_registry_entry(doc_id=f"q{i}", document_type="quarterly_investor_pack",
                                     filename=f"pack{i}.xlsx", ingested_at=_ts(90 * i))
                for i in range(3)
            ] + [
                _make_registry_entry(doc_id=f"v{i}", document_type="vintage_cohort",
                                     filename=f"vintage{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(4)
            ],
        )
        patterns = detect_recurring_patterns(
            "GroupCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert len(patterns) == 2
        types = {p.document_type for p in patterns}
        assert types == {"quarterly_investor_pack", "vintage_cohort"}

    def test_threshold_3_files_classifies_as_candidate(self, isolated_data_dir):
        """≥3 files, no hook, no parser = CANDIDATE."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Acme",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="board_pack",
                                     filename=f"board{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            add_hook=False,
        )
        patterns = detect_recurring_patterns(
            "Acme", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert len(patterns) == 1
        p = patterns[0]
        assert p.document_type == "board_pack"
        assert p.file_count == 3
        assert p.automation_status == "CANDIDATE"
        assert p.hook_exists is False
        assert p.parser_exists is False

    def test_2_files_classifies_as_early(self, isolated_data_dir):
        """1 or 2 files = EARLY (below candidate threshold)."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "EarlyCo",
            entries=[
                _make_registry_entry(doc_id=f"e{i}", document_type="audit_report",
                                     filename=f"audit{i}.pdf", ingested_at=_ts(180 + 90 * i))
                for i in range(2)
            ],
        )
        patterns = detect_recurring_patterns(
            "EarlyCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert len(patterns) == 1
        assert patterns[0].file_count == 2
        assert patterns[0].automation_status == "EARLY"

    def test_hook_exists_classifies_as_automated_when_parser_also_exists(self, isolated_data_dir):
        """≥3 files + hook + parser = AUTOMATED."""
        scripts_dir = _make_scripts_dir(
            isolated_data_dir.parent,
            parsers=["ingest_tamara_investor_pack.py"],
        )
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"q{i}", document_type="quarterly_investor_pack",
                                     filename=f"pack{i}.xlsx", ingested_at=_ts(90 * i))
                for i in range(4)
            ],
            add_hook=True,
        )
        patterns = detect_recurring_patterns(
            "Tamara", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert len(patterns) == 1
        p = patterns[0]
        assert p.automation_status == "AUTOMATED"
        assert p.hook_exists is True
        assert p.parser_exists is True

    def test_partial_status_when_only_hook_exists(self, isolated_data_dir):
        """Hook present, parser missing = PARTIAL."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "PartialCo",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="vintage_cohort",
                                     filename=f"v{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(5)
            ],
            add_hook=True,
        )
        patterns = detect_recurring_patterns(
            "PartialCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns[0].automation_status == "PARTIAL"
        assert patterns[0].hook_exists is True
        assert patterns[0].parser_exists is False

    def test_partial_status_when_only_parser_exists(self, isolated_data_dir):
        """Parser present, hook missing = PARTIAL."""
        scripts_dir = _make_scripts_dir(
            isolated_data_dir.parent,
            parsers=["ingest_silq_pos_loans.py"],
        )
        _seed_dataroom(
            isolated_data_dir, "SILQ",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="pos_loans",
                                     filename=f"l{i}.csv", ingested_at=_ts(30 * i))
                for i in range(4)
            ],
            add_hook=False,
        )
        patterns = detect_recurring_patterns(
            "SILQ", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns[0].automation_status == "PARTIAL"
        assert patterns[0].hook_exists is False
        assert patterns[0].parser_exists is True

    def test_skip_other_and_unknown_document_types(self, isolated_data_dir):
        """Unclassified entries (other/unknown) MUST NOT form clusters."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "MixedCo",
            entries=[
                _make_registry_entry(doc_id=f"o{i}", document_type="other",
                                     filename=f"o{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(5)
            ] + [
                _make_registry_entry(doc_id=f"u{i}", document_type="unknown",
                                     filename=f"u{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(4)
            ] + [
                _make_registry_entry(doc_id=f"c{i}", document_type="kyc_compliance",
                                     filename=f"c{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
        )
        patterns = detect_recurring_patterns(
            "MixedCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        # Only the kyc_compliance cluster should form
        assert len(patterns) == 1
        assert patterns[0].document_type == "kyc_compliance"


# ── Cadence detection ────────────────────────────────────────────────────


class TestCadenceDetection:
    def test_cadence_quarterly_detection_works(self, isolated_data_dir):
        """Mean delta of ~90 days → quarterly."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "QCo",
            entries=[
                _make_registry_entry(doc_id=f"q{i}", document_type="quarterly_pack",
                                     filename=f"q{i}.xlsx", ingested_at=_ts(90 * i))
                for i in range(4)
            ],
        )
        patterns = detect_recurring_patterns(
            "QCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns[0].cadence_label == "quarterly"
        assert 80 <= patterns[0].cadence_days <= 100

    def test_cadence_monthly_detection_works(self, isolated_data_dir):
        """Mean delta of ~30 days → monthly."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "MCo",
            entries=[
                _make_registry_entry(doc_id=f"m{i}", document_type="monthly_report",
                                     filename=f"m{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(4)
            ],
        )
        patterns = detect_recurring_patterns(
            "MCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns[0].cadence_label == "monthly"
        assert 25 <= patterns[0].cadence_days <= 35

    def test_cadence_irregular_when_dates_not_uniform(self, isolated_data_dir):
        """Wildly varying deltas → irregular."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        # 5 days, 200 days, 5 days → mean ~70d which falls between buckets
        _seed_dataroom(
            isolated_data_dir, "IrrCo",
            entries=[
                _make_registry_entry(doc_id="i1", document_type="audit_report",
                                     filename="i1.pdf", ingested_at=_ts(0)),
                _make_registry_entry(doc_id="i2", document_type="audit_report",
                                     filename="i2.pdf", ingested_at=_ts(5)),
                _make_registry_entry(doc_id="i3", document_type="audit_report",
                                     filename="i3.pdf", ingested_at=_ts(205)),
                _make_registry_entry(doc_id="i4", document_type="audit_report",
                                     filename="i4.pdf", ingested_at=_ts(210)),
            ],
        )
        patterns = detect_recurring_patterns(
            "IrrCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns[0].cadence_label == "irregular"

    def test_cadence_unknown_when_single_file(self, isolated_data_dir):
        """1 file → no deltas → unknown cadence."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "OneCo",
            entries=[
                _make_registry_entry(doc_id="x", document_type="audit_report",
                                     filename="x.pdf", ingested_at=_ts(0))
            ],
        )
        patterns = detect_recurring_patterns(
            "OneCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns[0].cadence_label == "unknown"
        assert patterns[0].cadence_days is None


# ── Recommendation text ──────────────────────────────────────────────────


class TestRecommendation:
    def test_recommendation_text_for_candidate_includes_company_and_type(self, isolated_data_dir):
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Acme",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="board_pack",
                                     filename=f"b{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(4)
            ],
        )
        patterns = detect_recurring_patterns(
            "Acme", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        rec = patterns[0].recommendation
        assert "Acme" in rec
        assert "board_pack" in rec
        # Should reference the Tamara pattern as the model
        assert "tamara" in rec.lower() or "Tamara" in rec
        # Should suggest the right file paths
        assert "ingest_acme_board_pack.py" in rec
        assert "data/Acme/dataroom/.post-ingest.sh" in rec

    def test_recommendation_text_for_automated_is_distinct(self, isolated_data_dir):
        scripts_dir = _make_scripts_dir(
            isolated_data_dir.parent,
            parsers=["ingest_tamara_investor_pack.py"],
        )
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"q{i}", document_type="quarterly_investor_pack",
                                     filename=f"q{i}.xlsx", ingested_at=_ts(90 * i))
                for i in range(4)
            ],
            add_hook=True,
        )
        patterns = detect_recurring_patterns(
            "Tamara", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        rec = patterns[0].recommendation
        assert "automated" in rec.lower()
        assert "fully" in rec.lower()


# ── Parser detection heuristic ───────────────────────────────────────────


class TestParserDetectionHeuristic:
    def test_two_word_doctype_requires_two_word_overlap(self, isolated_data_dir):
        """`ingest_tamara_investor_pack.py` should NOT match `investor_report`
        (only 1 word overlap on a 2-word doc_type) — prevents Tamara's pack
        parser being credited as the report parser too.
        """
        scripts_dir = _make_scripts_dir(
            isolated_data_dir.parent,
            parsers=["ingest_tamara_investor_pack.py"],
        )
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"r{i}", document_type="investor_report",
                                     filename=f"r{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(5)
            ],
        )
        patterns = detect_recurring_patterns(
            "Tamara", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        # investor_report has 2 words, parser stem only contains "investor"
        # → 1/2 overlap, below threshold → parser_exists=False
        assert patterns[0].parser_exists is False

    def test_three_word_doctype_two_word_match_succeeds(self, isolated_data_dir):
        """`ingest_tamara_investor_pack.py` SHOULD match `quarterly_investor_pack`
        (2/3 word overlap on a 3-word doc_type).
        """
        scripts_dir = _make_scripts_dir(
            isolated_data_dir.parent,
            parsers=["ingest_tamara_investor_pack.py"],
        )
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"q{i}", document_type="quarterly_investor_pack",
                                     filename=f"q{i}.xlsx", ingested_at=_ts(90 * i))
                for i in range(3)
            ],
        )
        patterns = detect_recurring_patterns(
            "Tamara", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert patterns[0].parser_exists is True


# ── Sort order ───────────────────────────────────────────────────────────


class TestSortOrder:
    def test_candidate_sorts_before_partial_before_early_before_automated(self, isolated_data_dir):
        """Most-actionable first."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "MultiCo",
            entries=(
                # CANDIDATE (3 files, no hook, no parser)
                [_make_registry_entry(doc_id=f"c{i}", document_type="cap_table",
                                      filename=f"c{i}.xlsx", ingested_at=_ts(30 * i))
                 for i in range(3)] +
                # EARLY (2 files)
                [_make_registry_entry(doc_id=f"e{i}", document_type="audit_report",
                                      filename=f"e{i}.pdf", ingested_at=_ts(30 * i))
                 for i in range(2)]
            ),
        )
        patterns = detect_recurring_patterns(
            "MultiCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert len(patterns) == 2
        assert patterns[0].automation_status == "CANDIDATE"
        assert patterns[1].automation_status == "EARLY"


# ── Mind integration ─────────────────────────────────────────────────────


class TestMindIntegration:
    def test_company_mind_record_called_with_correct_category(self, isolated_data_dir):
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Acme",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="kyc_compliance",
                                     filename=f"k{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
        )
        patterns = detect_recurring_patterns(
            "Acme", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        n = write_patterns_to_company_mind("Acme", patterns)
        assert n == 1

        # Verify the JSONL file landed in the right category
        jsonl_path = isolated_data_dir / "Acme" / "mind" / "recurring_channels.jsonl"
        assert jsonl_path.exists()
        lines = [l for l in jsonl_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["category"] == "recurring_channels"
        assert entry["metadata"]["pattern_id"] == "Acme::kyc_compliance"
        assert entry["metadata"]["automation_status"] == "CANDIDATE"
        assert entry["metadata"]["file_count"] == 3
        assert entry["metadata"]["asset_class"] == "bnpl"

    def test_idempotent_on_repeat_detection_no_duplicate_entries(self, isolated_data_dir):
        """Calling write twice with unchanged patterns must add no new entries."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Acme",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="board_pack",
                                     filename=f"b{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
        )
        patterns = detect_recurring_patterns(
            "Acme", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        n1 = write_patterns_to_company_mind("Acme", patterns)
        n2 = write_patterns_to_company_mind("Acme", patterns)
        assert n1 == 1
        assert n2 == 0  # Nothing new on second call
        jsonl = isolated_data_dir / "Acme" / "mind" / "recurring_channels.jsonl"
        lines = [l for l in jsonl.read_text().splitlines() if l.strip()]
        assert len(lines) == 1

    def test_status_transition_creates_history_entry(self, isolated_data_dir):
        """When automation_status changes, write a NEW entry — preserving the
        prior row as historical audit trail. The new entry references the
        prior status in metadata.prior_status.
        """
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        # Pass 1: CANDIDATE (no hook, no parser)
        _seed_dataroom(
            isolated_data_dir, "Acme",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="board_pack",
                                     filename=f"b{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
        )
        p1 = detect_recurring_patterns(
            "Acme", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        write_patterns_to_company_mind("Acme", p1)

        # Pass 2: PARTIAL (analyst added the hook)
        (isolated_data_dir / "Acme" / "dataroom" / ".post-ingest.sh").write_text("#!/bin/bash\n")
        p2 = detect_recurring_patterns(
            "Acme", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        n_new = write_patterns_to_company_mind("Acme", p2)
        assert n_new == 1
        assert p2[0].automation_status == "PARTIAL"

        jsonl = isolated_data_dir / "Acme" / "mind" / "recurring_channels.jsonl"
        lines = [l for l in jsonl.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        prior, current = json.loads(lines[0]), json.loads(lines[1])
        assert prior["metadata"]["automation_status"] == "CANDIDATE"
        assert current["metadata"]["automation_status"] == "PARTIAL"
        assert current["metadata"]["prior_status"] == "CANDIDATE"

    def test_writes_to_recurring_channels_not_findings(self, isolated_data_dir):
        """Critical separation — recurring channels must NOT pollute the
        findings.jsonl that AI prompts pull from.
        """
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Acme",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="board_pack",
                                     filename=f"b{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
        )
        patterns = detect_recurring_patterns(
            "Acme", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        write_patterns_to_company_mind("Acme", patterns)

        mind_dir = isolated_data_dir / "Acme" / "mind"
        assert (mind_dir / "recurring_channels.jsonl").exists()
        # findings.jsonl should NOT have been created
        assert not (mind_dir / "findings.jsonl").exists()


# ── Emergent (cross-company) patterns ────────────────────────────────────


class TestEmergentPatterns:
    def test_emergent_pattern_requires_2_companies_minimum(self, isolated_data_dir):
        """1 company alone with a CANDIDATE pattern → no emergent."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"q{i}", document_type="quarterly_pack",
                                     filename=f"q{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
        )
        emergent = detect_emergent_asset_class_patterns(
            data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert emergent == []

    def test_emergent_pattern_groups_by_asset_class_and_document_type(self, isolated_data_dir):
        """2 BNPL companies both showing 3+ quarterly_pack files → emergent surfaces."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"t{i}", document_type="quarterly_pack",
                                     filename=f"t{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(4)
            ],
            asset_class="bnpl",
            product="KSA",
        )
        _seed_dataroom(
            isolated_data_dir, "RivalBNPL",
            entries=[
                _make_registry_entry(doc_id=f"r{i}", document_type="quarterly_pack",
                                     filename=f"r{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
            product="KSA",
        )
        emergent = detect_emergent_asset_class_patterns(
            data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert len(emergent) == 1
        e = emergent[0]
        assert e.asset_class == "bnpl"
        assert e.document_type == "quarterly_pack"
        assert sorted(e.companies) == ["RivalBNPL", "Tamara"]
        assert e.company_file_counts == {"Tamara": 4, "RivalBNPL": 3}

    def test_emergent_skips_different_asset_classes(self, isolated_data_dir):
        """Same doc_type but different asset_class → NOT emergent."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"t{i}", document_type="quarterly_pack",
                                     filename=f"t{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
        )
        _seed_dataroom(
            isolated_data_dir, "POSCo",
            entries=[
                _make_registry_entry(doc_id=f"p{i}", document_type="quarterly_pack",
                                     filename=f"p{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="pos_lending",
        )
        emergent = detect_emergent_asset_class_patterns(
            data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert emergent == []

    def test_emergent_pattern_does_not_auto_write_to_asset_class_mind(self, isolated_data_dir):
        """Critical architectural constraint — detection surfaces, never writes."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"t{i}", document_type="quarterly_pack",
                                     filename=f"t{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(4)
            ],
            asset_class="bnpl",
        )
        _seed_dataroom(
            isolated_data_dir, "RivalBNPL",
            entries=[
                _make_registry_entry(doc_id=f"r{i}", document_type="quarterly_pack",
                                     filename=f"r{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
        )
        # Snapshot the asset_class_mind dir BEFORE detection
        ac_dir = isolated_data_dir / "_asset_class_mind"
        before = list(ac_dir.glob("*.jsonl")) if ac_dir.exists() else []

        emergent = detect_emergent_asset_class_patterns(
            data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert len(emergent) == 1

        # AssetClassMind directory must NOT have been written to
        after = list(ac_dir.glob("*.jsonl")) if ac_dir.exists() else []
        assert before == after

    def test_emergent_skips_unknown_asset_class(self, isolated_data_dir):
        """Companies with no resolvable asset_class drop out of emergent."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        # Don't write a config.json — asset_class will fall back to "unknown"
        dr = isolated_data_dir / "OrphanCo" / "dataroom"
        dr.mkdir(parents=True, exist_ok=True)
        registry = {
            f"o{i}": _make_registry_entry(
                doc_id=f"o{i}", document_type="vintage_cohort",
                filename=f"o{i}.xlsx", ingested_at=_ts(30 * i),
            )
            for i in range(3)
        }
        (dr / "registry.json").write_text(json.dumps(registry))

        _seed_dataroom(
            isolated_data_dir, "RealCo",
            entries=[
                _make_registry_entry(doc_id=f"r{i}", document_type="vintage_cohort",
                                     filename=f"r{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
        )

        # Confirm OrphanCo's pattern resolves asset_class="unknown"
        orphan_patterns = detect_recurring_patterns(
            "OrphanCo", data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert orphan_patterns[0].asset_class == "unknown"

        # OrphanCo is excluded from emergent because asset_class="unknown"
        emergent = detect_emergent_asset_class_patterns(
            data_dir=isolated_data_dir, scripts_dir=scripts_dir,
        )
        assert emergent == []


# ── Fund-wide stats (rolling Master Mind file) ──────────────────────────


class TestFundWideStats:
    def test_write_fund_wide_stats_creates_rolling_file(self, isolated_data_dir):
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"t{i}", document_type="quarterly_pack",
                                     filename=f"t{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
        )
        stats = write_fund_wide_stats(data_dir=isolated_data_dir, scripts_dir=scripts_dir)
        out_path = isolated_data_dir / "_master_mind" / "recurring_channel_stats.json"
        assert out_path.exists()
        on_disk = json.loads(out_path.read_text())
        assert on_disk == stats
        assert "summary" in stats
        assert "Tamara" in stats["by_company"]

    def test_fund_wide_stats_overwrites_not_appends(self, isolated_data_dir):
        """Repeated calls produce a SINGLE file (overwritten), not history."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "Tamara",
            entries=[
                _make_registry_entry(doc_id=f"t{i}", document_type="quarterly_pack",
                                     filename=f"t{i}.xlsx", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
        )
        write_fund_wide_stats(data_dir=isolated_data_dir, scripts_dir=scripts_dir)
        write_fund_wide_stats(data_dir=isolated_data_dir, scripts_dir=scripts_dir)
        out_path = isolated_data_dir / "_master_mind" / "recurring_channel_stats.json"
        # Single file (no rotation, no .1 .2 etc)
        peers = list(out_path.parent.glob("recurring_channel_stats*"))
        assert len(peers) == 1


# ── Auto-fire safety ─────────────────────────────────────────────────────


class TestAutoFireSafety:
    def test_auto_fire_in_ingest_does_not_break_on_detector_exception(
        self, isolated_data_dir, monkeypatch,
    ):
        """If detect_recurring_patterns raises, auto_fire_after_ingest MUST
        return a dict with `error` set — never re-raise. This is the
        guarantee that pattern detection failures don't break deploy.sh.
        """
        from core.mind import pattern_detector as pd_mod

        def _boom(*args, **kwargs):
            raise RuntimeError("detector exploded")

        monkeypatch.setattr(pd_mod, "detect_recurring_patterns", _boom)

        result = auto_fire_after_ingest("Acme")
        assert isinstance(result, dict)
        assert result.get("error") == "detector exploded"
        # Did not propagate
        assert result["company"] == "Acme"

    def test_auto_fire_succeeds_when_company_has_no_dataroom(self, isolated_data_dir):
        """Empty result is success, not an error."""
        # Use isolated dir so the real Tamara dataroom can't be reached.
        result = auto_fire_after_ingest("ghost_company_xyz")
        assert "error" not in result
        assert result["patterns_detected"] == 0
        assert result["new_mind_entries"] == 0

    def test_auto_fire_writes_mind_entries_for_real_patterns(self, isolated_data_dir, monkeypatch):
        """End-to-end: auto_fire_after_ingest detects + writes mind + updates stats."""
        scripts_dir = _make_scripts_dir(isolated_data_dir.parent)
        _seed_dataroom(
            isolated_data_dir, "AutoFireCo",
            entries=[
                _make_registry_entry(doc_id=f"d{i}", document_type="audit_report",
                                     filename=f"a{i}.pdf", ingested_at=_ts(30 * i))
                for i in range(3)
            ],
            asset_class="bnpl",
        )
        # auto_fire uses default scripts_dir; patch it to our tmp scripts dir
        monkeypatch.setattr("core.mind.pattern_detector._DEFAULT_SCRIPTS_DIR", scripts_dir)
        # And data_dir
        monkeypatch.setattr("core.mind.pattern_detector._DEFAULT_DATA_DIR", isolated_data_dir)

        result = auto_fire_after_ingest("AutoFireCo")
        assert "error" not in result
        assert result["patterns_detected"] == 1
        assert result["new_mind_entries"] == 1
        assert result["fund_stats_updated"] is True


# ── Pattern dataclass round-trip ─────────────────────────────────────────


class TestDataclasses:
    def test_recurring_pattern_to_dict_round_trip(self):
        p = RecurringPattern(
            pattern_id="Acme::board_pack",
            company="Acme",
            document_type="board_pack",
            asset_class="bnpl",
            file_count=3,
            file_dates=["2026-01-01T00:00:00+00:00"],
            cadence_days=90,
            cadence_label="quarterly",
            hook_exists=False,
            parser_exists=False,
            automation_status="CANDIDATE",
            recommendation="Acme has accumulated 3 board_pack files...",
            detected_at="2026-04-26T00:00:00+00:00",
        )
        d = p.to_dict()
        assert d["pattern_id"] == "Acme::board_pack"
        assert d["automation_status"] == "CANDIDATE"
        assert d["file_count"] == 3
        # JSON-serializable
        assert json.dumps(d)

    def test_emergent_pattern_to_dict_round_trip(self):
        e = EmergentPattern(
            asset_class="bnpl",
            document_type="quarterly_pack",
            companies=["Tamara", "RivalBNPL"],
            company_file_counts={"Tamara": 4, "RivalBNPL": 3},
            detected_at="2026-04-26T00:00:00+00:00",
            suggested_text="bnpl companies typically deliver quarterly_pack...",
        )
        d = e.to_dict()
        assert d["asset_class"] == "bnpl"
        assert d["companies"] == ["Tamara", "RivalBNPL"]
        assert json.dumps(d)
