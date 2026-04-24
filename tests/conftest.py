"""Shared test fixtures for the Laith credit platform test suite.

Any test that instantiates `CompanyMind`, `MasterMind`, `AssetClassMind`,
`ThesisTracker`, `DataRoomEngine`, or calls `build_mind_context` with a
fabricated company/product name should accept the `isolated_data_dir`
fixture — those constructors `mkdir(parents=True, exist_ok=True)` as a
side effect, so without isolation they leak empty folders into real
`data/`.

Tests that legitimately read real `data/` (e.g. shipped config.json
audits) should NOT include this fixture.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """Redirect every module-level data-dir constant at a tmp directory.

    Returns the `data/` subdir as a Path. Teardown is automatic via
    monkeypatch. Mirrors `test_external_intelligence.isolated_project`
    plus `ThesisTracker` and `DataRoomEngine` coverage (both spun up
    transitively by `build_mind_context` / agent tool handlers).
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr("core.mind.company_mind._PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("core.mind.master_mind._PROJECT_ROOT", tmp_path)
    # MasterMind reads _MASTER_DIR (computed at module load from
    # _PROJECT_ROOT), not _PROJECT_ROOT directly — patch both.
    monkeypatch.setattr(
        "core.mind.master_mind._MASTER_DIR", data_dir / "_master_mind"
    )
    monkeypatch.setattr("core.mind.asset_class_mind._PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        "core.mind.asset_class_mind._BASE_DIR",
        data_dir / "_asset_class_mind",
    )
    monkeypatch.setattr("core.external.pending_review._PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        "core.external.pending_review._DEFAULT_PATH",
        data_dir / "_pending_review" / "queue.jsonl",
    )
    monkeypatch.setattr("core.mind.promotion._PROJECT_ROOT", tmp_path)
    # ThesisTracker has its own _PROJECT_ROOT and is spun up transitively
    # by build_mind_context's Layer 5 assembly.
    monkeypatch.setattr("core.mind.thesis._PROJECT_ROOT", tmp_path)

    # DataRoomEngine() with no arg computes its default data_root inside
    # __init__ via Path(__file__).resolve()... — can't be patched at the
    # module level. Wrap __init__ so the no-arg path lands in tmp.
    from core.dataroom.engine import DataRoomEngine

    _orig_init = DataRoomEngine.__init__

    def _patched_init(self, data_root=None):
        if data_root is None:
            data_root = str(data_dir)
        _orig_init(self, data_root)

    monkeypatch.setattr(DataRoomEngine, "__init__", _patched_init)

    return data_dir
