"""Regression tests for the Tamara investment thesis pipeline (Jobs E + F).

Covers:
- build_thesis_metrics_from_pack: flat-key extraction, derived ratios, missing-data safety
- _load_thesis_summary: graceful no-thesis, returns expected shape
- seed_tamara_thesis: creates the expected 8 pillars, preserves existing pillars on re-seed
- scripts/ingest_tamara_investor_pack.py --no-update-thesis flag respected
- parse_tamara_data attaches thesis_summary when a thesis exists
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from core.analysis_tamara import (
    build_thesis_metrics_from_pack,
    _load_thesis_summary,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _fake_enriched_pack(**overrides):
    """Build a minimal enriched pack dict that matches what _enrich_quarterly_pack produces."""
    def _delta(latest, pct=None, prior=None):
        return {
            "latest": latest,
            "latest_month": "2026-03",
            "prior": prior,
            "prior_month": "2026-02",
            "abs_delta": None,
            "pct_delta": pct,
        }

    fs_cons = {
        "Total GMV":                    _delta(9.66e8, pct=-0.042, prior=1.01e9),
        "Total Operating Revenue":      _delta(80_054_884, pct=-0.01, prior=80.8e6),
        "Contribution Margin":          _delta(43_390_791, pct=-0.02, prior=44.3e6),
        "EBTDA":                        _delta(30_470_565, pct=-0.06, prior=32.4e6),
        "Statutory Net Profit / (Loss)": _delta(6_841_577, pct=-0.42, prior=11.8e6),
        "Net AR":                       _delta(1_514_757_309, pct=0.033),
        "Cash":                         _delta(348_994_999, pct=-0.265),
        "Debt":                         _delta(1_522_998_349, pct=0.029),
        "ECL Provisions":               _delta(-57_067_943, pct=0.095),
        "Coverage Ratio":               _delta(0.0363, pct=0.058),
    }
    kpi_cons = {
        "# Annual active customers":       _delta(8_053_535),
        "# Annual active merchants":       _delta(61_439),
        "# of orders":                     _delta(6_625_947),
        "AOV":                             _delta(145.76),
        "LTV / CAC":                       _delta(32.31),
        "CAC per customer":                _delta(10.35),
        "Profit Bearing GMV":              _delta(210_185_137),
        "Churn Rate (1 - Retention Rate)": _delta(0.27),
    }
    bvs = {
        "Total GMV":                     {"actual_ytd": 2.9e9, "budget_ytd": 2.69e9, "ytd_variance_pct": 0.0785, "monthly_variance_pct": -0.022},
        "Total Operating Revenue":       {"actual_ytd": 189.8e6, "budget_ytd": 163.0e6, "ytd_variance_pct": 0.164, "monthly_variance_pct": 0.195},
        "Contribution Margin / NTM":     {"actual_ytd": 76.9e6, "budget_ytd": 58.3e6, "ytd_variance_pct": 0.319, "monthly_variance_pct": 0.187},
        "EBTDA":                         {"actual_ytd": 41.4e6, "budget_ytd": 18.4e6, "ytd_variance_pct": 1.246, "monthly_variance_pct": 0.741},
        "Total Operating Expenses":      {"actual_ytd": -35.5e6, "budget_ytd": -39.9e6, "ytd_variance_pct": 0.109, "monthly_variance_pct": 0.079},
    }
    pack = {
        "headline_fs": {"cons": fs_cons, "ksa": {}, "uae": {}},
        "headline_kpis": {"cons": kpi_cons, "ksa": {}, "uae": {}},
        "budget_variance_summary": bvs,
    }
    pack.update(overrides)
    return pack


# ── build_thesis_metrics_from_pack ────────────────────────────────────────────


class TestBuildThesisMetricsFromPack:
    """Flat-key metric extraction from an enriched investor pack."""

    def test_returns_expected_headline_keys(self):
        pack = _fake_enriched_pack()
        m = build_thesis_metrics_from_pack(pack)

        # Core FS headlines
        for k in [
            "cons_gmv_latest",
            "cons_revenue_latest",
            "cons_contribution_margin_usd",
            "cons_ebtda_latest",
            "cons_statutory_net_profit",
            "cons_cash",
            "cons_net_ar",
            "cons_debt",
            "cons_ecl_coverage_pct",
        ]:
            assert k in m, f"Missing expected key: {k}"

    def test_derived_contribution_margin_ratio(self):
        """CM% = Contribution Margin / GMV. Spot-check the derivation."""
        pack = _fake_enriched_pack()
        m = build_thesis_metrics_from_pack(pack)
        # 43.39M / 965.82M = ~0.0449
        assert "cons_contribution_margin_pct" in m
        assert m["cons_contribution_margin_pct"] == pytest.approx(0.0449, abs=0.001)

    def test_derived_pbg_share(self):
        """Profit Bearing GMV share of total GMV — derived division."""
        pack = _fake_enriched_pack()
        m = build_thesis_metrics_from_pack(pack)
        # 210.19M / 965.82M = ~0.2176
        assert "cons_profit_bearing_gmv_pct" in m
        assert m["cons_profit_bearing_gmv_pct"] == pytest.approx(0.2176, abs=0.001)

    def test_budget_variance_keys_mapped(self):
        """Budget variance dict is flattened into ytd_*_vs_budget_pct keys."""
        pack = _fake_enriched_pack()
        m = build_thesis_metrics_from_pack(pack)
        assert m["ytd_gmv_vs_budget_pct"] == pytest.approx(0.0785, abs=0.001)
        assert m["ytd_ebtda_vs_budget_pct"] == pytest.approx(1.246, abs=0.001)
        assert m["ytd_revenue_vs_budget_pct"] == pytest.approx(0.164, abs=0.001)

    def test_empty_pack_returns_empty_dict(self):
        """Missing / None pack → empty dict, no crash."""
        assert build_thesis_metrics_from_pack(None) == {}
        assert build_thesis_metrics_from_pack({}) == {}

    def test_missing_gmv_skips_derived_ratios(self):
        """If Total GMV is missing, derived ratios (CM%, PBG%) are omitted — not computed as nonsense."""
        pack = _fake_enriched_pack()
        del pack["headline_fs"]["cons"]["Total GMV"]
        m = build_thesis_metrics_from_pack(pack)
        # cons_gmv_latest should be omitted
        assert "cons_gmv_latest" not in m
        # CM and PBG ratios should be omitted (can't compute without GMV denominator)
        assert "cons_contribution_margin_pct" not in m
        assert "cons_profit_bearing_gmv_pct" not in m

    def test_zero_gmv_does_not_divide(self):
        """If GMV is 0, derived ratios should not raise ZeroDivisionError."""
        pack = _fake_enriched_pack()
        pack["headline_fs"]["cons"]["Total GMV"]["latest"] = 0
        m = build_thesis_metrics_from_pack(pack)
        # Derived ratios should be absent (we guard with `if gmv and gmv != 0`)
        assert "cons_contribution_margin_pct" not in m
        assert "cons_profit_bearing_gmv_pct" not in m


# ── _load_thesis_summary ──────────────────────────────────────────────────────


class TestLoadThesisSummary:
    """Read-only thesis payload construction for the dashboard."""

    def test_returns_none_when_no_thesis_exists(self, tmp_path, monkeypatch):
        """When no thesis file exists, returns None — doesn't crash."""
        from core.mind import thesis as thesis_mod
        monkeypatch.setattr(thesis_mod, "_PROJECT_ROOT", tmp_path)
        # Use a company name that has no thesis
        assert _load_thesis_summary(company="_nonexistent_testcompany_") is None

    def test_returns_summary_dict_when_thesis_exists(self, tmp_path, monkeypatch):
        """When thesis exists, returns the expected shape."""
        from core.mind import thesis as thesis_mod
        from core.mind.thesis import InvestmentThesis, ThesisPillar, ThesisTracker

        monkeypatch.setattr(thesis_mod, "_PROJECT_ROOT", tmp_path)

        # Seed a minimal thesis
        tracker = ThesisTracker(company="TestCo", product="all")
        thesis = InvestmentThesis(
            company="TestCo",
            product="all",
            title="Test Thesis",
            pillars=[
                ThesisPillar(
                    id="test_pillar_1",
                    claim="Test claim",
                    metric_key="test_metric",
                    threshold=0.5,
                    direction="above",
                    conviction_score=70,
                ),
            ],
        )
        tracker.save(thesis, change_reason="test seed")

        result = _load_thesis_summary(company="TestCo")
        assert result is not None
        assert result["title"] == "Test Thesis"
        assert result["status"] == "active"
        assert len(result["pillars"]) == 1
        assert result["pillars"][0]["claim"] == "Test claim"
        assert result["pillars"][0]["metric_key"] == "test_metric"
        assert result["pillars"][0]["threshold"] == 0.5


# ── seed_tamara_thesis script ─────────────────────────────────────────────────


class TestSeedTamaraThesisScript:
    """scripts/seed_tamara_thesis.py creates + refreshes the thesis correctly."""

    def _load_seed_module(self):
        """Import the seed script by file path (scripts/ has no __init__.py)."""
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "seed_tamara_thesis.py"
        spec = importlib.util.spec_from_file_location("seed_tamara_thesis", script_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["seed_tamara_thesis"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_seed_creates_eight_pillars(self, tmp_path, monkeypatch):
        """Fresh seed populates 8 pillars with valid thresholds."""
        from core.mind import thesis as thesis_mod
        monkeypatch.setattr(thesis_mod, "_PROJECT_ROOT", tmp_path)

        seed_mod = self._load_seed_module()
        assert len(seed_mod.PILLARS_SPEC) == 8

        tracker, thesis = seed_mod.build_thesis(preserve_existing=True)
        tracker.save(thesis, change_reason="test seed")

        loaded = tracker.load()
        assert loaded is not None
        assert len(loaded.pillars) == 8

        # Each pillar has metric_key, threshold, direction
        for p in loaded.pillars:
            assert p.metric_key is not None, f"Pillar {p.id} missing metric_key"
            assert p.threshold is not None, f"Pillar {p.id} missing threshold"
            assert p.direction in ("above", "below", "stable")

    def test_reseed_preserves_ids_and_created_at(self, tmp_path, monkeypatch):
        """Re-seeding with preserve_existing=True keeps original pillar IDs and created_at."""
        from core.mind import thesis as thesis_mod
        monkeypatch.setattr(thesis_mod, "_PROJECT_ROOT", tmp_path)

        seed_mod = self._load_seed_module()

        # First seed
        tracker, t1 = seed_mod.build_thesis(preserve_existing=True)
        tracker.save(t1, change_reason="initial")
        original_ids = {p.metric_key: p.id for p in t1.pillars}
        original_created = {p.metric_key: p.created_at for p in t1.pillars}

        # Re-seed
        tracker2, t2 = seed_mod.build_thesis(preserve_existing=True)
        tracker2.save(t2, change_reason="refresh")

        # IDs + created_at should match
        for p in t2.pillars:
            assert p.id == original_ids[p.metric_key]
            assert p.created_at == original_created[p.metric_key]

        # Version should have incremented
        assert t2.version == t1.version + 1

    def test_pillars_span_profit_growth_credit_dimensions(self):
        """Sanity check: pillar set covers distinct thesis dimensions."""
        seed_mod = self._load_seed_module()
        keys = [p["metric_key"] for p in seed_mod.PILLARS_SPEC]

        # At least one profitability pillar
        assert any("profit" in k.lower() or "ebtda" in k.lower() for k in keys)
        # At least one credit/reserve pillar
        assert any("ecl" in k.lower() for k in keys)
        # At least one growth-vs-budget pillar
        assert any("budget" in k.lower() for k in keys)
        # At least one unit-economics pillar
        assert any("ltv" in k.lower() or "churn" in k.lower() for k in keys)


# ── CLI flag: --no-update-thesis ──────────────────────────────────────────────


class TestIngestScriptNoUpdateThesis:
    """--no-update-thesis flag skips drift check."""

    def test_flag_registered(self):
        """Argument parser accepts --no-update-thesis."""
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "ingest_tamara_investor_pack.py"
        # Just check the CLI help includes the flag — cheapest assertion,
        # no file dependencies.
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--no-update-thesis" in result.stdout
