"""
Finding #3 regression tests: Layer 2.5 (Asset Class Mind) must be keyed by
the semantic `asset_class` config field, not the company-specific
`analysis_type`.

Background: during the session-27 smoke test, Klaim's `analysis_type` was
"klaim" but the agent wrote pending entries to
`data/_asset_class_mind/healthcare_receivables.jsonl`. `build_mind_context`
resolved `analysis_type` to "klaim" and looked for "klaim.jsonl" which
doesn't exist → Layer 2.5 silently returned empty for every real company.
Fix: prefer `cfg.get("asset_class")` over `cfg.get("analysis_type")`.

These tests pin the resolution precedence so nobody regresses it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.mind import build_mind_context
from core.mind.asset_class_mind import AssetClassMind


@pytest.fixture
def isolated_asset_class_dir(tmp_path, monkeypatch):
    """Redirect AssetClassMind storage to a tmp dir so tests don't touch
    the real data/_asset_class_mind/ jsonl files."""
    ac_dir = tmp_path / "_asset_class_mind"
    ac_dir.mkdir()
    monkeypatch.setattr(
        "core.mind.asset_class_mind._BASE_DIR", ac_dir
    )
    return ac_dir


@pytest.fixture
def stub_config(monkeypatch):
    """Patch core.config.load_config to return a dict we control."""
    captured = {}

    def _fake_loader(company, product):
        return captured.get((company, product), {})

    monkeypatch.setattr("core.config.load_config", _fake_loader)
    return captured


def _seed_ac_entry(ac_dir: Path, key: str, content: str = "stub benchmark") -> None:
    """Write one benchmark entry to the asset_class jsonl.

    The `isolated_asset_class_dir` fixture monkeypatches the module-level
    `_BASE_DIR`, so plain `AssetClassMind(key)` already targets the tmp
    directory — both this seed helper AND `build_mind_context`'s internal
    instance resolve to the same place.
    """
    ac_mind = AssetClassMind(key)
    assert ac_mind.base_dir == ac_dir, (
        "Fixture didn't redirect _BASE_DIR — test would write to real data/."
    )
    ac_mind.record(category="benchmarks", content=content, metadata={"source": "test"})


class TestAssetClassResolution:
    def test_asset_class_field_takes_precedence(
        self, isolated_asset_class_dir, stub_config
    ):
        """When config.json has both `asset_class` and `analysis_type`, the
        semantic `asset_class` key wins."""
        _seed_ac_entry(isolated_asset_class_dir, "healthcare_receivables")

        stub_config[("klaim", "UAE_healthcare")] = {
            "analysis_type": "klaim",
            "asset_class": "healthcare_receivables",
        }

        ctx = build_mind_context("klaim", "UAE_healthcare", "executive_summary")
        assert len(ctx.asset_class) > 0, (
            "Layer 2.5 returned empty even though asset_class='healthcare_receivables' "
            "is set in config. Resolution is probably still hitting analysis_type first."
        )
        assert "stub benchmark" in ctx.asset_class

    def test_falls_back_to_analysis_type_for_legacy_configs(
        self, isolated_asset_class_dir, stub_config
    ):
        """If a config.json has only `analysis_type` (no `asset_class`), we
        still resolve using analysis_type for backwards compatibility. This
        means OLD-style configs that happen to match an asset-class file
        will still work; new configs are expected to add `asset_class`."""
        _seed_ac_entry(isolated_asset_class_dir, "legacy_type")

        stub_config[("legacy_co", "legacy_prod")] = {
            "analysis_type": "legacy_type",
            # no asset_class — this is the pre-fix shape
        }

        ctx = build_mind_context("legacy_co", "legacy_prod", "executive_summary")
        assert len(ctx.asset_class) > 0, (
            "Legacy configs without asset_class should fall back to analysis_type."
        )

    def test_explicit_override_beats_config(
        self, isolated_asset_class_dir, stub_config
    ):
        """Caller-supplied analysis_type argument should still beat whatever's
        in config, to preserve the original override semantics."""
        _seed_ac_entry(isolated_asset_class_dir, "override_key")

        stub_config[("anyco", "anyprod")] = {
            "analysis_type": "wrong_one",
            "asset_class": "also_wrong",
        }

        ctx = build_mind_context(
            "anyco", "anyprod", "executive_summary",
            analysis_type="override_key",
        )
        assert len(ctx.asset_class) > 0

    def test_missing_config_returns_empty_layer(
        self, isolated_asset_class_dir, stub_config
    ):
        """A company with no matching config + no matching asset-class file
        should give an empty Layer 2.5, not crash."""
        # No stub_config entry → load_config returns {} → both keys None

        ctx = build_mind_context("ghost", "noproduct", "executive_summary")
        assert ctx.asset_class == ""
        assert ctx.total_entries >= 0  # didn't crash, no asset-class rows

    def test_shipped_configs_have_asset_class_field(self):
        """All shipped data/{co}/{product}/config.json files should declare
        `asset_class` so Layer 2.5 works out of the box for every company."""
        import os

        project_root = Path(__file__).resolve().parents[1]
        data_dir = project_root / "data"

        missing: list[str] = []
        for config_path in data_dir.glob("*/*/config.json"):
            # Skip non-company dirs
            if config_path.parent.parent.name.startswith("_"):
                continue
            try:
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if "asset_class" not in cfg:
                rel = config_path.relative_to(project_root)
                missing.append(str(rel))

        assert not missing, (
            f"These shipped configs are missing the `asset_class` field, "
            f"meaning their Layer 2.5 falls back to `analysis_type` "
            f"(usually the company shortname, which won't match any "
            f"data/_asset_class_mind/*.jsonl file):\n  " + "\n  ".join(missing)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
