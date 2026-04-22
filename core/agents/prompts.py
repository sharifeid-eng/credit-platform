"""Shared prompt builders for internal agent invocations.

Keeping prompts in one place prevents drift between sync and SSE call sites.
Historically the Executive Summary prompt lived in two places — sync in
core/agents/internal.py and stream in backend/main.py — and the two fell
out of sync (the sync path had no JSON contract for months, producing the
"Agent Summary" cached fallback on every call). Any future changes to the
prompt should land here so both paths see them.
"""
from __future__ import annotations

from typing import Optional


# ── Executive Summary ────────────────────────────────────────────────────────

# Default hierarchy-level section guidance. Company-specific overrides live
# in the `_EXEC_SUMMARY_SECTION_GUIDANCE` map in backend/main.py and
# core/agents/internal.py (duplicate for historical reasons; consolidate if a
# third caller appears).
_DEFAULT_SECTION_GUIDANCE = (
    "1. Portfolio Overview — size, growth, composition\n"
    "2. Cash Conversion — collection performance, DSO, velocity\n"
    "3. Credit Quality — PAR, delinquency, health distribution\n"
    "4. Loss Economics — default rates, recovery, net loss, margins\n"
    "5. Concentration & Segments — provider risk, product mix\n"
    "6. Forward Signals — leading indicators, covenant headroom, drift\n"
    "7. Bottom Line — overall assessment with specific recommendations"
)


def build_executive_summary_prompt(
    company: str,
    product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
    section_guidance: Optional[str] = None,
) -> str:
    """Build the Executive Summary prompt used by both sync and SSE endpoints.

    The prompt encodes five binding disciplines on top of the JSON output
    contract — each one addresses a specific class of failure we've seen in
    production (see commit history on backend/main.py:_parse_agent_exec_summary_response
    and the 2026-04-22 Aajil review):

    1. Arithmetic discipline — derived numbers (net, gross, residuals) must
       reconcile. Catches "gross write-off 4.2M, recoveries 0.9M, net 3.4M"
       style arithmetic drift.

    2. Compute-don't-estimate — if a number is tool-computable, compute it.
       Never use "estimated >60%" when the underlying categories are
       enumerable via a tool call.

    3. Section discipline — produce exactly the sections the guidance names,
       in order. Catches agents that silently substitute sections (e.g.
       swapping "Cohorts" for "Loss Attribution") to avoid calling tools.

    4. Findings discipline — ranked findings are credit/portfolio observations.
       Tool-coverage gaps and undefined theses go into the separate
       `analytics_coverage` callout, not the findings list.

    5. Severity calibration — rough RAG thresholds for common metrics so the
       agent doesn't label a 16.9% recovery rate as "Warning" when it should
       be "Critical".
    """
    guidance = section_guidance or _DEFAULT_SECTION_GUIDANCE

    ctx_line = (
        f"[Context: company={company}, product={product}"
        + (f", snapshot={snapshot}" if snapshot else "")
        + (f", currency={currency}" if currency else "")
        + (f", as_of_date={as_of_date}" if as_of_date else "")
        + "]"
    )

    return (
        f"{ctx_line}\n\n"
        "Generate a comprehensive executive summary for this portfolio company. "
        "For each section, pull the relevant analytics data via tools and search the "
        "data room for supporting evidence. Cross-reference with the investment thesis "
        "if one exists.\n\n"
        f"Sections: {guidance}\n\n"
        "Return your output as a JSON object (no prose outside the JSON, no markdown fences):\n"
        "{\n"
        '  "narrative": {\n'
        '    "sections": [ {"title": "...", "content": "paragraphs separated by \\n\\n", '
        '"conclusion": "...", '
        '"metrics": [{"label": "...", "value": "...", "assessment": "healthy|acceptable|warning|critical|monitor"}]} ],\n'
        '    "summary_table": [ {"metric": "...", "value": "...", '
        '"assessment": "Healthy|Acceptable|Warning|Critical|Monitor"} ],\n'
        '    "bottom_line": "..."\n'
        "  },\n"
        '  "analytics_coverage": "(OPTIONAL) 1-3 sentence callout naming major unavailable analytics '
        '(PAR/DSO/covenants/drift/stress-test/etc.) and their impact on IC monitoring. Include undefined '
        'investment thesis status here if applicable. OMIT this field entirely if all analytics are '
        'available and a thesis is defined — never include empty or placeholder text.",\n'
        '  "findings": [ {"rank": 1, "severity": "critical|warning|positive", '
        '"title": "...", "explanation": "...", "data_points": ["..."], "tab": "tab-slug"} ]\n'
        "}\n\n"
        "OUTPUT RULES:\n"
        "- Every claim must cite a specific number obtained from a tool call.\n"
        "- 6-10 narrative sections, 5-10 findings ranked by business impact.\n"
        "- Plain prose in all text fields — no markdown syntax (no **bold**, no | tables |, no --- separators).\n"
        "- Professional IC tone. Start your response with `{` — no preamble, no fences, no closing prose.\n"
        "\n"
        "ARITHMETIC DISCIPLINE:\n"
        "- Every derived number must reconcile. If you cite net and gross figures, show the bridge "
        "(e.g. gross write-off − recoveries = net loss) and verify the arithmetic holds to the last digit.\n"
        "- If a total splits into categories (e.g. product mix, industry mix), the category sum must equal "
        "the total. If there's a residual, state it explicitly ('1 deal unclassified').\n"
        "- When both completed-only and portfolio-wide versions of a metric exist (collection rate / GLR / "
        "realised amount), state the denominator for each and reconcile the two figures explicitly — do "
        "not cite both without explaining the difference.\n"
        "\n"
        "COMPUTE, DON'T ESTIMATE:\n"
        "- If a number is computable from the tools available, call the tool and report the exact value.\n"
        "- Never use 'estimated', 'approximately', 'likely exceeds', or similar hedging as a substitute "
        "for computation.\n"
        "- If you need an aggregate that spans multiple categories (e.g. 'total construction materials "
        "exposure' summing steel + concrete + cables + etc.), list the component categories explicitly "
        "and sum them. Show your work.\n"
        "\n"
        "SECTION DISCIPLINE:\n"
        "- Produce exactly the sections named in the Sections guidance, in order. Do NOT substitute, "
        "merge, rename, or reorder. If the guidance names 'Cohorts' and you produce 'Loss Attribution' "
        "instead, the output is non-conforming.\n"
        "- If a section's data requires a specific tool (e.g. Cohorts → analytics.get_cohort_analysis), "
        "call that tool. If the tool is unavailable for this analysis type, produce a brief section "
        "acknowledging the gap and include it in the `analytics_coverage` callout.\n"
        "\n"
        "FINDINGS DISCIPLINE:\n"
        "- Findings must be observations about the portfolio itself — credit quality, concentration, "
        "loss trends, pricing, segment performance, vintage behavior.\n"
        "- Do NOT file findings about missing tools, unavailable analytics, undefined investment theses, "
        "or platform limitations. Those belong in the `analytics_coverage` callout.\n"
        "- Severity calibration (rough thresholds — adjust for asset class, but don't be lenient):\n"
        "  • Recovery rate <30% on defaults → Critical (secured facilities should recover 40%+)\n"
        "  • PAR 90+ or PAR 3+ installment >5% with rising trend → Critical; stable/falling → Warning\n"
        "  • Single-name concentration >10% → Warning; >15% → Critical\n"
        "  • Sector concentration >50% in a single industry group → Warning; >70% → Critical\n"
        "  • Cumulative net loss rate >5% of originated → Critical\n"
        "  • Covenant breach (any) → Critical\n"
    )
