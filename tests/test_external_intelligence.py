"""End-to-end tests for the External Intelligence stack.

Ported from scripts/verify_external_intelligence.py (the 16-check harness
that ran standalone during session-27). Same test intent, same isolation
strategy — every test uses a tmp directory and monkeypatches the
hardcoded _PROJECT_ROOT / _BASE_DIR / _DEFAULT_PATH globals so no real
`data/` files are touched.

Covers:
    AssetClassMind   — record, list, context assembly, category validation
    PendingReview    — CRUD, status filtering, all three promotion targets
    promote_entry    — Company→AssetClass, AssetClass→Master, provenance chains
    build_mind_context() — Layer 2.5 actually lands in the 6-layer output
    web_search tool  — registered, schema shape, handler wiring (mocked Claude)

Does NOT hit live Claude or HTTP — those are smoke-tested separately.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest


# ── Fixture: isolated project root ───────────────────────────────────────


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    """Redirect every module-level data-dir constant at a tmp directory.

    Returns the data/ subdir as a Path. After the test exits, all patches
    revert automatically via monkeypatch's teardown.

    Mirrors scripts/verify_external_intelligence.py::_temp_project_root so
    ported checks keep their exact isolation semantics.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr("core.mind.company_mind._PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("core.mind.master_mind._PROJECT_ROOT", tmp_path)
    # MasterMind reads _MASTER_DIR (computed at module load time from
    # _PROJECT_ROOT), not _PROJECT_ROOT directly — patching just
    # _PROJECT_ROOT won't redirect writes. Patch both.
    monkeypatch.setattr(
        "core.mind.master_mind._MASTER_DIR",
        data_dir / "_master_mind",
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

    return data_dir


# ── Asset Class Mind ─────────────────────────────────────────────────────


class TestAssetClassMind:
    """Checks 01–03 from verify_external_intelligence.py."""

    def test_record_and_list_round_trip(self, isolated_project):
        from core.mind.asset_class_mind import AssetClassMind

        mind = AssetClassMind("bnpl")
        entry = mind.record(
            category="benchmarks",
            content="Median BNPL 30+ DPD in emerging markets: 4-6%",
            source="manual",
        )
        assert entry.id
        assert entry.metadata.get("analysis_type") == "bnpl"

        listed = mind.list_entries()
        assert len(listed) == 1
        assert listed[0].content.startswith("Median BNPL")

    def test_get_context_for_prompt_returns_formatted_text(self, isolated_project):
        from core.mind.asset_class_mind import AssetClassMind

        mind = AssetClassMind("healthcare_receivables")
        mind.record("benchmarks", "Typical payer denial rate: 8-12%")
        mind.record("peer_comparison", "Klaim competitors include Progressify and Afya")

        ctx = mind.get_context_for_prompt("executive_summary")
        assert ctx.entry_count == 2
        assert "healthcare_receivables" in ctx.formatted
        assert "Typical payer" in ctx.formatted
        assert "benchmarks" in ctx.formatted

    def test_record_rejects_unknown_category(self, isolated_project):
        from core.mind.asset_class_mind import AssetClassMind

        mind = AssetClassMind("bnpl")
        with pytest.raises(ValueError, match="Unknown category"):
            mind.record("not_a_real_category", "should fail")


# ── Pending Review Queue ─────────────────────────────────────────────────


class TestPendingReviewQueue:
    """Checks 04–08 from verify_external_intelligence.py."""

    def test_add_list_counts(self, isolated_project):
        from core.external.pending_review import PendingReviewQueue, TargetScope

        q = PendingReviewQueue()
        assert q.list() == []

        entry = q.add(
            source="web_search",
            target_scope=TargetScope.ASSET_CLASS,
            target_key="bnpl",
            category="external_research",
            title="Test finding",
            content="Body text",
            citations=[{"url": "https://x.test", "title": "T", "snippet": "s"}],
            query="What is X?",
        )
        assert entry.status == "pending"

        listed = q.list()
        assert len(listed) == 1 and listed[0].id == entry.id

        counts = q.counts()
        assert counts["pending"] == 1
        assert counts["approved"] == 0

    def test_add_validates_scope_key_pairing(self, isolated_project):
        """target_scope=company requires target_key; target_scope=master forbids it."""
        from core.external.pending_review import PendingReviewQueue, TargetScope

        q = PendingReviewQueue()

        with pytest.raises(ValueError):
            q.add(
                source="w",
                target_scope=TargetScope.COMPANY,
                target_key=None,
                category="findings",
                title="t",
                content="c",
            )

        with pytest.raises(ValueError):
            q.add(
                source="w",
                target_scope=TargetScope.MASTER,
                target_key="bnpl",
                category="sector_context",
                title="t",
                content="c",
            )

    def test_approve_to_asset_class_promotes(self, isolated_project):
        from core.external.pending_review import PendingReviewQueue, TargetScope
        from core.mind.asset_class_mind import AssetClassMind

        q = PendingReviewQueue()
        entry = q.add(
            source="web_search",
            target_scope=TargetScope.ASSET_CLASS,
            target_key="bnpl",
            category="external_research",
            title="Test",
            content="Approval should land this in bnpl mind",
            citations=[{"url": "https://x", "title": "T", "snippet": "s"}],
        )
        updated = q.approve(entry.id, reviewed_by="test@t")
        assert updated.status == "approved"
        assert updated.promoted_entry_id, "must record promoted id"

        mind = AssetClassMind("bnpl")
        entries = mind.list_entries()
        assert len(entries) == 1
        assert entries[0].id == updated.promoted_entry_id
        assert entries[0].metadata.get("source") == "web_search"
        assert entries[0].metadata.get("citations")

    def test_approve_to_master_promotes(self, isolated_project):
        from core.external.pending_review import PendingReviewQueue, TargetScope
        from core.mind.master_mind import MasterMind

        q = PendingReviewQueue()
        entry = q.add(
            source="web_search",
            target_scope=TargetScope.MASTER,
            target_key=None,
            category="sector_context",
            title="Regulatory update",
            content="SAMA published new BNPL licensing guidelines",
        )
        updated = q.approve(entry.id)
        assert updated.status == "approved"

        mm = MasterMind()
        sector_entries = mm._read_entries("sector_context")
        assert len(sector_entries) >= 1
        assert any("SAMA" in e.content for e in sector_entries)

    def test_reject_retains_entry_for_audit(self, isolated_project):
        from core.external.pending_review import PendingReviewQueue, TargetScope

        q = PendingReviewQueue()
        entry = q.add(
            source="web_search",
            target_scope=TargetScope.MASTER,
            target_key=None,
            category="framework_evolution",
            title="bad",
            content="bad",
        )
        q.reject(entry.id, review_note="not credible")

        rejected = q.list(status="rejected")
        assert len(rejected) == 1
        assert rejected[0].id == entry.id
        assert rejected[0].review_note == "not credible"

        c = q.counts()
        assert c["rejected"] == 1
        assert c["pending"] == 0


# ── promote_entry ────────────────────────────────────────────────────────


class TestPromoteEntry:
    """Checks 09–12 from verify_external_intelligence.py."""

    def test_company_to_asset_class_with_provenance(self, isolated_project):
        from core.mind.asset_class_mind import AssetClassMind
        from core.mind.company_mind import CompanyMind
        from core.mind.promotion import promote_entry

        cm = CompanyMind("klaim", "UAE_healthcare")
        cm._ensure_dirs()
        source = cm.record_research_finding(
            "Payer denial rates spike in Q3 due to fiscal-year end",
            confidence="high",
        )

        result = promote_entry(
            source_scope="company",
            source_key="klaim",
            source_product="UAE_healthcare",
            entry_id=source.id,
            target_scope="asset_class",
            target_key="healthcare_receivables",
            target_category="methodology_note",
            note="Same pattern seen across healthcare factoring portfolios",
        )
        assert result["new_entry_id"]
        assert result["target_scope"] == "asset_class"

        # Target carries promoted_from chain
        acm = AssetClassMind("healthcare_receivables")
        entries = acm.list_entries()
        assert len(entries) == 1
        pf = entries[0].metadata.get("promoted_from", {})
        assert pf.get("scope") == "company"
        assert pf.get("key") == "klaim"
        assert pf.get("entry_id") == source.id

        # Source carries promoted flag + promoted_to backlink
        with open(cm._jsonl_path("findings"), "r", encoding="utf-8") as f:
            d = json.loads(f.readline())
        assert d["promoted"] is True
        promoted_to = d["metadata"].get("promoted_to", [])
        assert len(promoted_to) == 1
        assert promoted_to[0]["scope"] == "asset_class"
        assert promoted_to[0]["key"] == "healthcare_receivables"

    def test_asset_class_to_master_with_provenance(self, isolated_project):
        from core.mind.asset_class_mind import AssetClassMind
        from core.mind.master_mind import MasterMind
        from core.mind.promotion import promote_entry

        acm = AssetClassMind("bnpl")
        source = acm.record(
            "sector_context",
            "BNPL regulators in KSA and UAE converging on similar rules",
        )

        result = promote_entry(
            source_scope="asset_class",
            source_key="bnpl",
            entry_id=source.id,
            target_scope="master",
            target_key=None,
            target_category="sector_context",
        )
        assert result["target_scope"] == "master"

        mm = MasterMind()
        entries = mm._read_entries("sector_context")
        promoted = next(e for e in entries if "BNPL regulators" in e.content)
        pf = promoted.metadata.get("promoted_from", {})
        assert pf.get("scope") == "asset_class"
        assert pf.get("key") == "bnpl"

    def test_asset_class_to_asset_class_is_forbidden(self, isolated_project):
        from core.mind.asset_class_mind import AssetClassMind
        from core.mind.promotion import promote_entry

        acm = AssetClassMind("bnpl")
        source = acm.record("benchmarks", "test")

        with pytest.raises(ValueError, match="only be promoted to master"):
            promote_entry(
                source_scope="asset_class",
                source_key="bnpl",
                entry_id=source.id,
                target_scope="asset_class",
                target_key="pos_lending",
                target_category="benchmarks",
            )

    def test_rejects_invalid_target_category(self, isolated_project):
        """'findings' is a CompanyMind category but NOT valid for AssetClassMind."""
        from core.mind.company_mind import CompanyMind
        from core.mind.promotion import promote_entry

        cm = CompanyMind("klaim", "UAE_healthcare")
        cm._ensure_dirs()
        src = cm.record_research_finding("x")

        with pytest.raises(ValueError, match="Invalid target_category"):
            promote_entry(
                source_scope="company",
                source_key="klaim",
                source_product="UAE_healthcare",
                entry_id=src.id,
                target_scope="asset_class",
                target_key="bnpl",
                target_category="findings",
            )


# ── build_mind_context end-to-end ────────────────────────────────────────


class TestBuildMindContext:
    """Check 13 from verify_external_intelligence.py."""

    def test_layer_2_5_lands_when_asset_class_populated(
        self, isolated_project, monkeypatch
    ):
        # Import modules BEFORE patching so references resolve
        import core.config  # noqa: F401
        import core.loader  # noqa: F401

        data = isolated_project
        co_dir = data / "klaim" / "UAE_healthcare"
        co_dir.mkdir(parents=True)
        co_dir.joinpath("config.json").write_text(
            json.dumps({
                "analysis_type": "klaim",
                "asset_class": "healthcare_receivables",  # Finding #3 field
                "currency": "AED",
            }),
            encoding="utf-8",
        )

        monkeypatch.setattr("core.config.DATA_DIR", str(data))
        monkeypatch.setattr("core.loader.DATA_DIR", str(data))

        from core.mind import build_mind_context
        from core.mind.asset_class_mind import AssetClassMind

        acm = AssetClassMind("healthcare_receivables")
        acm.record(
            "benchmarks",
            "Median PAR 30+ across healthcare factoring: 3-5%",
        )

        ctx = build_mind_context(
            "klaim", "UAE_healthcare",
            task_type="executive_summary",
        )
        assert ctx.asset_class, "expected asset_class layer populated"
        assert "Median PAR" in ctx.asset_class
        assert "Median PAR" in ctx.formatted
        assert "healthcare_receivables" in ctx.asset_class


# ── web_search tool ──────────────────────────────────────────────────────


class TestWebSearchTool:
    """Checks 14–16 from verify_external_intelligence.py."""

    def test_tool_registered_with_correct_schema(self):
        # Importing the module triggers the registry.register() call at the
        # bottom of core/agents/tools/external.py. We avoid register_all_tools()
        # because analytics.* imports pandas and is unrelated to this check.
        from core.agents.tools import registry
        import core.agents.tools.external  # noqa: F401

        spec = registry.get("external.web_search")
        assert spec is not None, "external.web_search not registered"
        assert "query" in spec.input_schema["properties"]
        assert "target_scope" in spec.input_schema["properties"]
        assert "category" in spec.input_schema["properties"]
        assert "query" in spec.input_schema.get("required", [])

    def test_handler_writes_pending_entry_with_mocked_claude(self, isolated_project):
        import core.ai_client  # noqa: F401 — must import before patching

        from core.agents.tools.external import _web_search
        from core.external.pending_review import PendingReviewQueue

        # Minimal stub matching the shape _extract_citations_from_response expects
        class _Cit:
            def __init__(self, url, title):
                self.type = "web_search_result"
                self.url = url
                self.title = title
                self.page_age = None

        class _ToolResult:
            type = "web_search_tool_result"
            content = [
                _Cit("https://fake.example/1", "Fake result 1"),
                _Cit("https://fake.example/2", "Fake result 2"),
            ]

        class _Text:
            type = "text"
            text = "Synthesised answer text"

        class _Resp:
            content = [_ToolResult(), _Text()]

        with mock.patch.object(core.ai_client, "complete", return_value=_Resp()):
            out = _web_search(
                query="Test BNPL defaults",
                target_scope="asset_class",
                target_key="bnpl",
                category="external_research",
            )

        assert "pending" in out.lower() or "queued" in out.lower()

        q = PendingReviewQueue()
        entries = q.list()
        assert len(entries) == 1
        e = entries[0]
        assert e.source == "web_search"
        assert e.target_scope == "asset_class"
        assert e.target_key == "bnpl"
        assert len(e.citations) == 2
        assert e.citations[0]["url"] == "https://fake.example/1"

    def test_handler_rejects_invalid_category_for_scope(self, isolated_project):
        from core.agents.tools.external import _web_search

        # 'benchmarks' is valid for asset_class but NOT for company
        out = _web_search(
            query="x",
            target_scope="company",
            target_key="klaim",
            category="benchmarks",
        )
        assert "Invalid category" in out


# ── D2: asset_class_sources population in build_mind_context ──────────────


class TestAssetClassSources:
    """D2 regression: build_mind_context() must surface citation URLs
    from Asset Class Mind entries so the DataChat UI can render them
    under AI answers.
    """

    def test_sources_populated_from_web_search_citations(
        self, isolated_project, monkeypatch
    ):
        # Config resolver needs to find the company's asset_class
        import core.config  # noqa: F401
        import core.loader  # noqa: F401

        data = isolated_project
        co_dir = data / "klaim" / "UAE_healthcare"
        co_dir.mkdir(parents=True)
        co_dir.joinpath("config.json").write_text(json.dumps({
            "analysis_type": "klaim",
            "asset_class": "healthcare_receivables",
            "currency": "AED",
        }), encoding="utf-8")
        monkeypatch.setattr("core.config.DATA_DIR", str(data))
        monkeypatch.setattr("core.loader.DATA_DIR", str(data))

        from core.mind import build_mind_context
        from core.mind.asset_class_mind import AssetClassMind

        acm = AssetClassMind("healthcare_receivables")
        acm.record(
            category="benchmarks",
            content="MENA factoring benchmark synthesis",
            metadata={
                "source": "web_search",
                "query": "MENA healthcare factoring defaults",
                "citations": [
                    {"url": "https://example.test/a", "title": "Source A", "page_age": "2024"},
                    {"url": "https://example.test/b", "title": "Source B", "page_age": ""},
                ],
            },
        )

        ctx = build_mind_context(
            "klaim", "UAE_healthcare",
            task_type="chat",
        )
        assert len(ctx.asset_class_sources) == 2
        first = ctx.asset_class_sources[0]
        assert first["url"].startswith("https://example.test/")
        assert first["source"] == "web_search"
        assert first["entry_category"] == "benchmarks"
        # The query string used to search becomes the entry_title —
        # that's the analyst-meaningful label
        assert first["entry_title"] == "MENA healthcare factoring defaults"

    def test_sources_dedupe_by_url(self, isolated_project, monkeypatch):
        import core.config  # noqa: F401
        import core.loader  # noqa: F401

        data = isolated_project
        co_dir = data / "klaim" / "UAE_healthcare"
        co_dir.mkdir(parents=True)
        co_dir.joinpath("config.json").write_text(json.dumps({
            "asset_class": "healthcare_receivables",
            "currency": "AED",
        }), encoding="utf-8")
        monkeypatch.setattr("core.config.DATA_DIR", str(data))
        monkeypatch.setattr("core.loader.DATA_DIR", str(data))

        from core.mind import build_mind_context
        from core.mind.asset_class_mind import AssetClassMind

        acm = AssetClassMind("healthcare_receivables")
        # Two entries citing the same URL — the flat sources list must
        # keep only one row (common case: multiple web_search queries
        # cite the same landing page).
        for i in range(2):
            acm.record(
                category="benchmarks",
                content=f"entry {i}",
                metadata={
                    "source": "web_search",
                    "citations": [
                        {"url": "https://example.test/shared", "title": "Shared",
                         "page_age": ""},
                    ],
                },
            )

        ctx = build_mind_context("klaim", "UAE_healthcare", task_type="chat")
        urls = [s["url"] for s in ctx.asset_class_sources]
        assert urls == ["https://example.test/shared"], (
            f"Expected deduped URL list, got {urls}"
        )

    def test_sources_empty_when_no_citations(self, isolated_project, monkeypatch):
        """Seed-style entries (source='seed:platform_docs', no citations)
        must not produce dangling source rows with empty URLs."""
        import core.config  # noqa: F401

        data = isolated_project
        co_dir = data / "klaim" / "UAE_healthcare"
        co_dir.mkdir(parents=True)
        co_dir.joinpath("config.json").write_text(json.dumps({
            "asset_class": "healthcare_receivables",
        }), encoding="utf-8")
        monkeypatch.setattr("core.config.DATA_DIR", str(data))
        monkeypatch.setattr("core.loader.DATA_DIR", str(data))

        from core.mind import build_mind_context
        from core.mind.asset_class_mind import AssetClassMind

        acm = AssetClassMind("healthcare_receivables")
        # Use `benchmarks` — in both chat + executive_summary task
        # relevance lists — so the entry actually lands in Layer 2.5.
        # The test point is "no citations → no sources", not category
        # filter behaviour.
        acm.record(
            category="benchmarks",
            content="A seeded benchmark with no external URLs",
            metadata={"source": "seed:platform_docs"},
        )

        ctx = build_mind_context("klaim", "UAE_healthcare", task_type="chat")
        assert ctx.asset_class_sources == []
        # Layer 2.5 text still populated — sources are optional
        assert "seeded benchmark" in ctx.asset_class


# ── D6: framework codification hook ───────────────────────────────────────


class TestFrameworkCodification:
    """D6 regression: master-mind `framework_evolution` entries must be
    enumerable (codification queue) and individually markable codified
    (close-the-loop flag)."""

    def _seed_entry(self, content: str, reason: str = "test fixture"):
        """Helper — write one framework_evolution entry via MasterMind.

        MasterMind.record_framework_evolution takes (change, reason, date);
        we keep the call minimal for these tests.
        """
        from core.mind.master_mind import MasterMind
        mm = MasterMind()
        return mm.record_framework_evolution(content, reason=reason)

    def test_empty_queue_returns_empty_list(self, isolated_project):
        from core.mind.framework_codification import get_codification_candidates
        assert get_codification_candidates() == []

    def test_queue_returns_pending_only_by_default(self, isolated_project):
        from core.mind.framework_codification import (
            get_codification_candidates, mark_codified,
        )
        e1 = self._seed_entry("Pending codification — new PAR definition")
        e2 = self._seed_entry("Already done — HHI methodology update")
        mark_codified(e2.id, commit_sha="abc123", framework_section="Section 4")

        pending = get_codification_candidates()
        assert len(pending) == 1
        assert pending[0]["id"] == e1.id
        assert pending[0]["codified_in_framework"] is False

        all_entries = get_codification_candidates(include_codified=True)
        assert len(all_entries) == 2

    def test_mark_codified_persists_metadata(self, isolated_project):
        from core.mind.framework_codification import (
            get_codification_candidates, mark_codified,
        )
        entry = self._seed_entry("Framework tweak — denominator discipline")
        mark_codified(
            entry.id,
            commit_sha="deadbee",
            framework_section="Section 6",
            codified_by="analyst@example",
        )

        # Re-read from disk
        codified = [
            e for e in get_codification_candidates(include_codified=True)
            if e["id"] == entry.id
        ][0]
        assert codified["codified_in_framework"] is True
        assert codified["codification_commit"] == "deadbee"
        assert codified["metadata"].get("codification_section") == "Section 6"
        assert codified["metadata"].get("codified_by") == "analyst@example"
        assert codified["metadata"].get("codified_at")  # timestamp set

    def test_mark_codified_raises_on_unknown_id(self, isolated_project):
        from core.mind.framework_codification import mark_codified
        # File doesn't exist yet — different error than "id not found"
        with pytest.raises(ValueError, match="not found"):
            mark_codified("nonexistent-id")

        # After seeding, unknown id -> "No framework_evolution entry"
        self._seed_entry("real entry")
        with pytest.raises(ValueError, match="No framework_evolution entry"):
            mark_codified("still-not-a-real-id")

    def test_counts(self, isolated_project):
        from core.mind.framework_codification import (
            codification_counts, mark_codified,
        )
        e1 = self._seed_entry("pending 1")
        e2 = self._seed_entry("pending 2")
        self._seed_entry("pending 3")
        mark_codified(e1.id, commit_sha="abc", framework_section="S1")
        mark_codified(e2.id, commit_sha="def", framework_section="S2")

        c = codification_counts()
        assert c == {"total": 3, "codified": 2, "pending": 1}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
