"""Unit tests for core.agents.prompts.build_executive_summary_prompt.

The Executive Summary prompt encodes five binding disciplines on top of the
JSON output contract. Each addresses a specific class of failure we've
reproduced (see commit history + the 2026-04-22 Aajil review):

  1. Arithmetic discipline — gross/net numbers must reconcile
  2. Compute-don't-estimate — no "estimated >60%" when categories are
     enumerable
  3. Section discipline — follow the guidance; no silent substitution
  4. Findings discipline — credit observations only; tool gaps go to
     analytics_coverage
  5. Severity calibration — 16.9% recovery should be Critical, not Warning

These tests lock those rules in so a later "prompt cleanup" can't
silently remove them. They DO NOT test agent behavior (that's the
end-to-end exec summary tests) — they test the prompt TEXT contract.
"""
from __future__ import annotations

from core.agents.prompts import build_executive_summary_prompt


class TestPromptContract:
    """The JSON output contract + start-with-{ rule that prevent markdown dumps."""

    def test_requires_json_object_output(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert '"narrative"' in prompt
        assert '"findings"' in prompt
        assert '"analytics_coverage"' in prompt
        assert "no markdown fences" in prompt

    def test_no_preamble_rule(self):
        """Start-with-{ locks the agent away from 'Here's the summary:' prefixes."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "Start your response with `{`" in prompt
        assert "no preamble" in prompt.lower()

    def test_no_markdown_in_text_fields(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "no markdown syntax" in prompt.lower()
        assert "**bold**" in prompt  # example of what NOT to use
        assert "| tables |" in prompt


class TestArithmeticDiscipline:
    def test_arithmetic_reconciliation_rule_present(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "ARITHMETIC DISCIPLINE" in prompt
        assert "reconcile" in prompt.lower()
        # Specific example that caught the Aajil net/gross drift
        assert "gross write-off" in prompt.lower() or "gross" in prompt.lower()
        assert "net" in prompt.lower()

    def test_category_residual_rule_present(self):
        """51% + 48% = 99% — agent should flag the unaccounted residual."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "category sum must equal the total" in prompt or "residual" in prompt

    def test_denominator_reconciliation_rule(self):
        """298.3M (completed) vs 332.3M (portfolio) realised — state the denominator."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "denominator" in prompt.lower()


class TestComputeDontEstimate:
    def test_no_estimation_rule_present(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "COMPUTE, DON'T ESTIMATE" in prompt
        assert "'estimated'" in prompt or '"estimated"' in prompt

    def test_show_your_work_on_aggregates(self):
        """Sum across multiple categories → list the components explicitly."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "sum them" in prompt.lower() or "show your work" in prompt.lower()


class TestSectionDiscipline:
    def test_section_discipline_rule_present(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "SECTION DISCIPLINE" in prompt
        assert "Do NOT substitute" in prompt

    def test_custom_guidance_passes_through(self):
        """Section guidance from the caller must end up in the prompt text."""
        guidance = "UniqueSectionA, UniqueSectionB, UniqueSectionC"
        prompt = build_executive_summary_prompt("co", "prod", section_guidance=guidance)
        assert "UniqueSectionA" in prompt
        assert "UniqueSectionB" in prompt
        assert "UniqueSectionC" in prompt

    def test_default_guidance_when_none_provided(self):
        """Companies without a custom section map get the L1-L5 hierarchy default."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "Portfolio Overview" in prompt
        assert "Cash Conversion" in prompt
        assert "Credit Quality" in prompt


class TestFindingsDiscipline:
    def test_findings_discipline_rule_present(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "FINDINGS DISCIPLINE" in prompt

    def test_no_platform_findings_rule(self):
        """Missing tools / undefined theses go to analytics_coverage, not findings."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "missing tools" in prompt.lower() or "unavailable analytics" in prompt.lower()
        assert "analytics_coverage" in prompt

    def test_severity_calibration_thresholds_present(self):
        """Agent was labeling 16.9% recovery as Warning instead of Critical.
        Prompt now names specific thresholds."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "Recovery rate <30%" in prompt
        assert "Critical" in prompt

    def test_single_name_concentration_threshold(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "Single-name concentration" in prompt or "single-name" in prompt.lower()

    def test_sector_concentration_threshold(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "Sector concentration" in prompt or "sector" in prompt.lower()


class TestContextLine:
    def test_context_line_includes_all_optional_fields(self):
        prompt = build_executive_summary_prompt(
            "Aajil", "KSA",
            snapshot="2026-04-13_aajil_ksa.xlsx",
            currency="SAR",
            as_of_date="2026-04-13",
        )
        assert "company=Aajil" in prompt
        assert "product=KSA" in prompt
        assert "snapshot=2026-04-13_aajil_ksa.xlsx" in prompt
        assert "currency=SAR" in prompt
        assert "as_of_date=2026-04-13" in prompt

    def test_context_line_omits_unspecified_fields(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert "company=co" in prompt
        assert "product=prod" in prompt
        assert "snapshot=" not in prompt
        assert "currency=" not in prompt


class TestAnalyticsCoverageSchema:
    def test_schema_documents_analytics_coverage_field(self):
        prompt = build_executive_summary_prompt("co", "prod")
        assert '"analytics_coverage"' in prompt
        # OPTIONAL marker so agent knows to omit when unneeded
        assert "OPTIONAL" in prompt or "optional" in prompt

    def test_schema_tells_agent_where_tool_gaps_go(self):
        """The whole point of the field — redirect the agent away from filing
        findings about missing tools."""
        prompt = build_executive_summary_prompt("co", "prod")
        assert "unavailable analytics" in prompt.lower()
        # And it should mention undefined thesis specifically since that was
        # one of the Aajil findings that belonged here, not in the ranked list
        assert "thesis" in prompt.lower()
