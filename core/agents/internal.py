"""
Internal Agent Invocations — agent-powered alternatives for existing AI features.

These functions run agent sessions internally (not user-facing) to generate
commentary, tab insights, and executive summaries. Results are cached using
the existing AI cache infrastructure.

Usage from main.py:
    from core.agents.internal import generate_agent_commentary

    result = await generate_agent_commentary(company, product, snapshot, currency, as_of_date)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _run_agent_sync(
    agent_name: str,
    prompt: str,
    metadata: dict,
    max_turns: int = None,
    max_tokens_per_response: int = None,
) -> str:
    """Run an agent synchronously (blocking). Returns the text response.

    Used for internal agent invocations where we need the result
    before returning the HTTP response (cached endpoints).

    ``max_tokens_per_response`` overrides the agent config default (typically
    2000). Long-form structured output like the Executive Summary JSON
    (~6-10 sections + 5-10 findings) easily overflows 2000 tokens mid-string,
    producing unparseable responses — callers emitting large JSON should
    bump this to 8000-16000.
    """
    from core.agents.config import load_agent_config
    from core.agents.runtime import AgentRunner
    from core.agents.session import AgentSession
    from core.agents.tools import build_tools_for_agent

    tool_specs = build_tools_for_agent(agent_name)
    config = load_agent_config(agent_name, tool_specs=tool_specs)
    if max_turns is not None:
        config.max_turns = max_turns
    if max_tokens_per_response is not None:
        config.max_tokens_per_response = max_tokens_per_response

    session = AgentSession.create(agent_name, metadata=metadata)
    runner = AgentRunner(config)

    # Run the async agent in a sync context.
    # On Python 3.12+, asyncio.get_event_loop() raises RuntimeError in non-main
    # threads with no loop set. The memo pipeline runs research packs in a
    # ThreadPoolExecutor, so we must handle the missing-loop case explicitly.
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        if loop.is_running():
            # We're inside an async context (FastAPI) — run in a separate pool
            # thread with its own fresh loop via asyncio.run().
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, runner.run(prompt, session))
                result = future.result(timeout=120)
        else:
            result = loop.run_until_complete(runner.run(prompt, session))
    except RuntimeError:
        # Fallback: spin up a fresh run (e.g. loop closed mid-call)
        result = asyncio.run(runner.run(prompt, session))

    # Clean up session (internal invocations don't need persistence)
    session.delete()

    return result.text


def generate_agent_commentary(
    company: str,
    product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    """Generate portfolio commentary using the analyst agent.

    The agent dynamically pulls summary, collection velocity, ageing, and
    any anomalies via tools — deciding what matters rather than receiving
    a pre-digested context dump.

    Returns: commentary text string.
    """
    prompt = (
        f"[Context: company={company}, product={product}"
        + (f", snapshot={snapshot}" if snapshot else "")
        + (f", currency={currency}" if currency else "")
        + (f", as_of_date={as_of_date}" if as_of_date else "")
        + "]\n\n"
        "Write a concise portfolio commentary in 3 sections:\n"
        "1. PORTFOLIO HEALTH (2-3 sentences) — overall collection performance and trends.\n"
        "2. KEY OBSERVATIONS (3-4 bullets) — most important data points for an investment committee.\n"
        "3. WATCH ITEMS (2-3 bullets) — areas that warrant monitoring. Be direct about concerns.\n\n"
        "Pull the portfolio summary, collection velocity, and ageing data first. "
        "If any metrics look anomalous, investigate further. "
        "Professional tone, suitable for an investment committee memo. Be specific and data-driven."
    )

    return _run_agent_sync(
        "analyst",
        prompt,
        metadata={"company": company, "product": product, "type": "commentary"},
        max_turns=5,  # Commentary is focused — 5 turns max
    )


def generate_agent_tab_insight(
    company: str,
    product: str,
    tab: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    """Generate a single-tab AI insight using the analyst agent.

    Returns: insight text string (2-3 sentences max).
    """
    # Map tab slugs to tool calls
    tab_tool_hints = {
        "overview": "get_portfolio_summary",
        "actual-vs-expected": "get_collection_velocity",
        "deployment": "get_deployment",
        "collection": "get_collection_velocity",
        "denial-trend": "get_denial_trend",
        "ageing": "get_ageing_breakdown",
        "revenue": "get_returns_analysis",
        "portfolio-tab": "get_concentration",
        "cohort-analysis": "get_cohort_analysis",
        "returns": "get_returns_analysis",
        "risk-migration": "get_covenants",
        "loss-waterfall": "get_loss_waterfall",
        "recovery-analysis": "get_loss_waterfall",
        "collections-timing": "get_collection_velocity",
        "underwriting-drift": "get_underwriting_drift",
        "segment-analysis": "get_segment_analysis",
        "seasonality": "get_deployment",
        "cdr-ccr": "get_cdr_ccr",
    }

    tool_hint = tab_tool_hints.get(tab, "get_portfolio_summary")

    prompt = (
        f"[Context: company={company}, product={product}"
        + (f", snapshot={snapshot}" if snapshot else "")
        + (f", currency={currency}" if currency else "")
        + "]\n\n"
        f"You are looking at the '{tab}' analysis tab. "
        f"Pull the relevant data (hint: {tool_hint} is a good starting tool) "
        f"and write a 2-3 sentence insight about what the data shows. "
        f"Focus on the single most important takeaway for an analyst. "
        f"Be specific with numbers. Keep it under 100 words."
    )

    return _run_agent_sync(
        "analyst",
        prompt,
        metadata={"company": company, "product": product, "type": "tab_insight", "tab": tab},
        max_turns=3,  # Tab insight is very focused
    )


def generate_agent_executive_summary(
    company: str,
    product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
    section_guidance: Optional[str] = None,
) -> str:
    """Generate a full executive summary using the analyst agent.

    This is the highest-value upgrade. The agent systematically:
    1. Pulls portfolio summary
    2. Checks each L1-L5 metric category
    3. Identifies anomalies/red flags
    4. Cross-references with thesis
    5. Searches data room for supporting evidence
    6. Writes structured narrative + findings

    Returns: full executive summary text.
    """
    from core.agents.prompts import build_executive_summary_prompt
    prompt = build_executive_summary_prompt(
        company=company,
        product=product,
        snapshot=snapshot,
        currency=currency,
        as_of_date=as_of_date,
        section_guidance=section_guidance,
    )

    return _run_agent_sync(
        "analyst",
        prompt,
        metadata={"company": company, "product": product, "type": "executive_summary"},
        max_turns=20,  # Executive summary needs many tool calls
        max_tokens_per_response=16000,  # Structured JSON with 6-10 sections + findings
    )


def generate_agent_section_regen(
    company: str,
    product: str,
    memo_id: str,
    section_key: str,
    instruction: Optional[str] = None,
) -> str:
    """Regenerate a single memo section using the memo_writer agent.

    Returns: regenerated content text.
    """
    instruction_text = instruction or "Regenerate this section with fresh data and analysis."

    prompt = (
        f"[Context: company={company}, product={product}, memo_id={memo_id}]\n\n"
        f"Regenerate section '{section_key}'. {instruction_text}\n\n"
        "Pull fresh analytics and search the data room for supporting evidence. "
        "Write the section content directly — no JSON wrapping. "
        "Professional IC-ready tone. Cite specific metrics."
    )

    return _run_agent_sync(
        "memo_writer",
        prompt,
        metadata={"company": company, "product": product, "type": "section_regen"},
        max_turns=10,
    )


def generate_agent_chat(
    company: str,
    product: str,
    question: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    """Answer a data chat question using the analyst agent.

    Returns: answer text string.
    """
    prompt = (
        f"[Context: company={company}, product={product}"
        + (f", snapshot={snapshot}" if snapshot else "")
        + (f", currency={currency}" if currency else "")
        + (f", as_of_date={as_of_date}" if as_of_date else "")
        + "]\n\n"
        f"{question}"
    )

    return _run_agent_sync(
        "analyst",
        prompt,
        metadata={"company": company, "product": product, "type": "chat"},
        max_turns=10,
    )
