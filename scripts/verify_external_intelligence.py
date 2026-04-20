"""Self-contained verification of the External Intelligence stack.

Runs every backend Python path shipped in Commits 2 and 3 against throwaway
temp directories so no real data is touched. Prints a pass/fail report.

Usage:
    python scripts/verify_external_intelligence.py

What it covers:
    AssetClassMind   — record / list / context assembly
    PendingReview    — CRUD, status filtering, all three promotion targets
    promote_entry    — Company -> AssetClass, AssetClass -> Master, provenance
    build_mind_context() — Layer 2.5 actually lands in the 6-layer output
    web_search tool  — registered, callable signature matches spec

Does NOT exercise:
    - Live Claude API calls (web_search handler is tested with a mocked client)
    - Any HTTP endpoint (these are pure-module tests)
    - Frontend rendering
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Test harness ─────────────────────────────────────────────────────────────

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    """Decorator: run a test, capture result. Each check returns True/False."""
    def wrap(fn):
        try:
            ok = fn()
            _RESULTS.append((name, bool(ok), "" if ok else "returned False"))
        except AssertionError as e:
            _RESULTS.append((name, False, f"assertion: {e}"))
        except Exception as e:
            tb = traceback.format_exc().splitlines()[-1]
            _RESULTS.append((name, False, f"{type(e).__name__}: {e} ({tb})"))
        return fn
    return wrap


@contextmanager
def _temp_project_root():
    """Monkey-patch _PROJECT_ROOT + _BASE_DIR + _DEFAULT_PATH in every module
    that has a hardcoded data-dir reference, pointing them at a temp dir.

    Yields the temp data dir as a Path.
    """
    with tempfile.TemporaryDirectory(prefix="laith_verify_") as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        patches = []
        targets = [
            ("core.mind.company_mind", "_PROJECT_ROOT", tmp_path),
            ("core.mind.master_mind",  "_PROJECT_ROOT", tmp_path),
            ("core.mind.asset_class_mind", "_PROJECT_ROOT", tmp_path),
            ("core.mind.asset_class_mind", "_BASE_DIR", data_dir / "_asset_class_mind"),
            ("core.external.pending_review", "_PROJECT_ROOT", tmp_path),
            ("core.external.pending_review", "_DEFAULT_PATH",
             data_dir / "_pending_review" / "queue.jsonl"),
            ("core.mind.promotion", "_PROJECT_ROOT", tmp_path),
        ]
        for mod_name, attr, val in targets:
            p = mock.patch(f"{mod_name}.{attr}", val)
            p.start()
            patches.append(p)

        try:
            yield data_dir
        finally:
            for p in patches:
                p.stop()


# ── Tests ────────────────────────────────────────────────────────────────────

@check("01. AssetClassMind — record + list round-trip")
def t_asset_class_basic():
    with _temp_project_root() as data:
        from core.mind.asset_class_mind import AssetClassMind
        m = AssetClassMind("bnpl")
        e = m.record(
            category="benchmarks",
            content="Median BNPL 30+ DPD in emerging markets: 4-6%",
            source="manual",
        )
        assert e.id, "entry must have id"
        assert e.metadata.get("analysis_type") == "bnpl"
        listed = m.list_entries()
        assert len(listed) == 1
        assert listed[0].content.startswith("Median BNPL")
        return True


@check("02. AssetClassMind — get_context_for_prompt returns formatted text")
def t_asset_class_context():
    with _temp_project_root():
        from core.mind.asset_class_mind import AssetClassMind
        m = AssetClassMind("healthcare_receivables")
        m.record("benchmarks", "Typical payer denial rate: 8-12%")
        m.record("peer_comparison", "Klaim competitors include Progressify and Afya")
        ctx = m.get_context_for_prompt("executive_summary")
        assert ctx.entry_count == 2, f"expected 2, got {ctx.entry_count}"
        assert "healthcare_receivables" in ctx.formatted
        assert "Typical payer" in ctx.formatted
        assert "benchmarks" in ctx.formatted
        return True


@check("03. AssetClassMind — rejects unknown category")
def t_asset_class_bad_category():
    with _temp_project_root():
        from core.mind.asset_class_mind import AssetClassMind
        m = AssetClassMind("bnpl")
        try:
            m.record("not_a_real_category", "should fail")
        except ValueError as e:
            assert "Unknown category" in str(e)
            return True
        return False  # should have raised


@check("04. PendingReviewQueue — add + list pending + counts")
def t_pending_crud():
    with _temp_project_root():
        from core.external.pending_review import PendingReviewQueue, TargetScope
        q = PendingReviewQueue()
        assert q.list() == []  # empty initially
        e1 = q.add(
            source="web_search", target_scope=TargetScope.ASSET_CLASS,
            target_key="bnpl", category="external_research",
            title="Test finding", content="Body text",
            citations=[{"url": "https://x.test", "title": "T", "snippet": "s"}],
            query="What is X?",
        )
        assert e1.status == "pending"
        listed = q.list()
        assert len(listed) == 1 and listed[0].id == e1.id
        counts = q.counts()
        assert counts["pending"] == 1
        assert counts["approved"] == 0
        return True


@check("05. PendingReviewQueue — validates target_scope / target_key pairing")
def t_pending_validation():
    with _temp_project_root():
        from core.external.pending_review import PendingReviewQueue, TargetScope
        q = PendingReviewQueue()
        # company without target_key should raise
        try:
            q.add(source="w", target_scope=TargetScope.COMPANY, target_key=None,
                  category="findings", title="t", content="c")
        except ValueError:
            pass
        else:
            return False

        # master WITH target_key should raise
        try:
            q.add(source="w", target_scope=TargetScope.MASTER, target_key="bnpl",
                  category="sector_context", title="t", content="c")
        except ValueError:
            pass
        else:
            return False
        return True


@check("06. PendingReviewQueue.approve — asset_class target promotes cleanly")
def t_approve_to_asset_class():
    with _temp_project_root():
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

        # Verify it landed in the asset class mind
        mind = AssetClassMind("bnpl")
        entries = mind.list_entries()
        assert len(entries) == 1
        assert entries[0].id == updated.promoted_entry_id
        assert entries[0].metadata.get("source") == "web_search"
        assert entries[0].metadata.get("citations")
        return True


@check("07. PendingReviewQueue.approve — master target promotes cleanly")
def t_approve_to_master():
    with _temp_project_root():
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

        # Verify MasterMind has it
        mm = MasterMind()
        # Use the private _read_entries for verification
        sector_entries = mm._read_entries("sector_context")
        assert len(sector_entries) >= 1
        assert any("SAMA" in e.content for e in sector_entries)
        return True


@check("08. PendingReviewQueue.reject — retains entry for audit")
def t_reject_retains():
    with _temp_project_root():
        from core.external.pending_review import PendingReviewQueue, TargetScope

        q = PendingReviewQueue()
        entry = q.add(
            source="web_search", target_scope=TargetScope.MASTER, target_key=None,
            category="framework_evolution", title="bad", content="bad",
        )
        q.reject(entry.id, review_note="not credible")
        rejected = q.list(status="rejected")
        assert len(rejected) == 1
        assert rejected[0].id == entry.id
        assert rejected[0].review_note == "not credible"

        # Counts reflect it
        c = q.counts()
        assert c["rejected"] == 1
        assert c["pending"] == 0
        return True


@check("09. promote_entry — Company -> Asset Class with full provenance")
def t_promote_company_to_asset_class():
    with _temp_project_root():
        from core.mind.company_mind import CompanyMind
        from core.mind.asset_class_mind import AssetClassMind
        from core.mind.promotion import promote_entry

        # Seed a company mind entry
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

        # Verify target has entry with promoted_from
        acm = AssetClassMind("healthcare_receivables")
        entries = acm.list_entries()
        assert len(entries) == 1
        promoted = entries[0]
        pf = promoted.metadata.get("promoted_from", {})
        assert pf.get("scope") == "company"
        assert pf.get("key") == "klaim"
        assert pf.get("entry_id") == source.id

        # Verify source has promoted_to record + promoted flag
        import json as _json
        with open(cm._jsonl_path("findings"), "r") as f:
            d = _json.loads(f.readline())
        assert d["promoted"] is True
        promoted_to = d["metadata"].get("promoted_to", [])
        assert len(promoted_to) == 1
        assert promoted_to[0]["scope"] == "asset_class"
        assert promoted_to[0]["key"] == "healthcare_receivables"
        return True


@check("10. promote_entry — Asset Class -> Master with provenance chain")
def t_promote_asset_class_to_master():
    with _temp_project_root():
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
        assert any("BNPL regulators" in e.content for e in entries)
        # Find the promoted one
        promoted = next(e for e in entries if "BNPL regulators" in e.content)
        pf = promoted.metadata.get("promoted_from", {})
        assert pf.get("scope") == "asset_class"
        assert pf.get("key") == "bnpl"
        return True


@check("11. promote_entry — Asset Class -> Asset Class is forbidden")
def t_promote_asset_class_illegal():
    with _temp_project_root():
        from core.mind.asset_class_mind import AssetClassMind
        from core.mind.promotion import promote_entry

        acm = AssetClassMind("bnpl")
        source = acm.record("benchmarks", "test")

        try:
            promote_entry(
                source_scope="asset_class", source_key="bnpl",
                entry_id=source.id,
                target_scope="asset_class", target_key="pos_lending",
                target_category="benchmarks",
            )
        except ValueError as e:
            assert "only be promoted to master" in str(e)
            return True
        return False


@check("12. promote_entry — rejects invalid target_category for scope")
def t_promote_bad_category():
    with _temp_project_root():
        from core.mind.company_mind import CompanyMind
        from core.mind.promotion import promote_entry

        cm = CompanyMind("klaim", "UAE_healthcare")
        cm._ensure_dirs()
        src = cm.record_research_finding("x")

        # 'findings' is a CompanyMind category but NOT a valid AssetClassMind
        # target — should raise
        try:
            promote_entry(
                source_scope="company", source_key="klaim",
                source_product="UAE_healthcare", entry_id=src.id,
                target_scope="asset_class", target_key="bnpl",
                target_category="findings",  # <-- invalid for asset_class
            )
        except ValueError as e:
            assert "Invalid target_category" in str(e)
            return True
        return False


@check("13. build_mind_context — Layer 2.5 lands when asset class populated")
def t_layered_context_with_asset_class():
    # Import modules BEFORE the patch context so mock.patch can resolve them
    import core.config  # noqa
    import core.loader  # noqa

    with _temp_project_root() as data:
        # Seed company config with analysis_type = healthcare_receivables
        co_dir = data / "klaim" / "UAE_healthcare"
        co_dir.mkdir(parents=True)
        (co_dir / "config.json").write_text(json.dumps({
            "analysis_type": "healthcare_receivables",
            "currency": "AED",
        }))

        # Patch core.config paths too
        with mock.patch.object(core.config, "DATA_DIR", str(data)), \
             mock.patch.object(core.loader, "DATA_DIR", str(data)):
            from core.mind.asset_class_mind import AssetClassMind
            from core.mind import build_mind_context

            acm = AssetClassMind("healthcare_receivables")
            acm.record(
                "benchmarks",
                "Median PAR 30+ across healthcare factoring: 3-5%",
            )

            ctx = build_mind_context(
                "klaim", "UAE_healthcare",
                task_type="executive_summary",
            )
            # Layer 2.5 should be non-empty
            assert ctx.asset_class, f"expected asset_class layer, got empty"
            assert "Median PAR" in ctx.asset_class
            # And the formatted output includes it
            assert "Median PAR" in ctx.formatted
            assert "healthcare_receivables" in ctx.asset_class
            return True


@check("14. web_search tool — registered with correct schema")
def t_web_search_registered():
    # Import just the external tool module (not register_all_tools — that
    # imports analytics.py which needs pandas). Module-level register call
    # fires on import.
    from core.agents.tools import registry
    import core.agents.tools.external  # noqa: F401
    spec = registry.get("external.web_search")
    assert spec is not None, "external.web_search not registered"
    assert "query" in spec.input_schema["properties"]
    assert "target_scope" in spec.input_schema["properties"]
    assert "category" in spec.input_schema["properties"]
    required = spec.input_schema.get("required", [])
    assert "query" in required
    return True


@check("15. web_search handler — writes pending entry when Claude returns results")
def t_web_search_handler_mocked():
    import core.ai_client  # noqa — must import before mock.patch.object

    with _temp_project_root():
        from core.external.pending_review import PendingReviewQueue
        # Import the private handler directly
        from core.agents.tools.external import _web_search

        # Mock ai_client.complete to return a fake response with citations
        class FakeCitation:
            def __init__(self, url, title):
                self.type = "web_search_result"
                self.url = url
                self.title = title
                self.page_age = None

        class FakeToolResult:
            def __init__(self):
                self.type = "web_search_tool_result"
                self.content = [
                    FakeCitation("https://fake.example/1", "Fake result 1"),
                    FakeCitation("https://fake.example/2", "Fake result 2"),
                ]

        class FakeTextBlock:
            def __init__(self, text):
                self.type = "text"
                self.text = text

        class FakeResp:
            content = [FakeToolResult(), FakeTextBlock("Synthesised answer text")]

        with mock.patch.object(core.ai_client, "complete", return_value=FakeResp()):
            out = _web_search(
                query="Test BNPL defaults",
                target_scope="asset_class",
                target_key="bnpl",
                category="external_research",
            )
        assert "pending" in out.lower() or "queued" in out.lower(), \
            f"handler output doesn't mention pending review: {out}"

        q = PendingReviewQueue()
        entries = q.list()
        assert len(entries) == 1
        e = entries[0]
        assert e.source == "web_search"
        assert e.target_scope == "asset_class"
        assert e.target_key == "bnpl"
        assert len(e.citations) == 2
        assert e.citations[0]["url"] == "https://fake.example/1"
        return True


@check("16. web_search handler — rejects invalid category for scope")
def t_web_search_handler_bad_category():
    with _temp_project_root():
        from core.agents.tools.external import _web_search
        out = _web_search(
            query="x",
            target_scope="company",
            target_key="klaim",
            category="benchmarks",  # valid for asset_class, NOT company
        )
        assert "Invalid category" in out
        return True


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Running External Intelligence verification...")
    print("=" * 72)

    # Execute all @check-decorated functions (they registered into _RESULTS on import)
    # Nothing to do here — decoration IS execution for our harness.

    width = max(len(n) for n, _, _ in _RESULTS) + 2
    passed = 0
    failed = 0
    for name, ok, msg in _RESULTS:
        status = "\033[32mPASS\033[0m" if ok else "\033[31mFAIL\033[0m"
        print(f"  {status}  {name.ljust(width)} {msg}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("=" * 72)
    print(f"  {passed} passed, {failed} failed, {len(_RESULTS)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
