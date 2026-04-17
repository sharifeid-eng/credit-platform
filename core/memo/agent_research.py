"""
Agent Research Packs — short-burst agent sessions that investigate a memo
section and return a structured JSON research pack.

Used by the memo pipeline to inform judgment sections (Executive Summary,
Investment Thesis, Recommendation) with evidence gathered across analytics,
the data room, and institutional memory.

Why short-burst:
- Standard agent sessions accumulate conversation across turns, blowing rate
  limits quickly. A 5-turn hard cap keeps each call under ~10K input tokens.
- Research output is structured JSON (not prose), so the call doesn't need
  many turns — agent pulls 3-4 tools, synthesizes, returns.
- Each section gets its own fresh session — no conversation leakage.

Pack schema:
  {
    "key_metrics": [{"label", "value", "source", "significance"}],
    "quotes":      [{"text", "source_doc", "page_or_section"}],
    "contradictions": [{"description", "section_a", "section_b", "severity"}],
    "recommended_stance": "Invest" | "Conditional Invest" | "Pass" | "Monitor",
    "supporting_evidence": [str],
  }
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Empty pack returned on any unrecoverable error — memo still generates,
# just without the research-backed enrichment for that section.
EMPTY_PACK: Dict[str, Any] = {
    "key_metrics": [],
    "quotes": [],
    "contradictions": [],
    "recommended_stance": "Monitor",
    "supporting_evidence": [],
}


def _build_prompt(
    company: str,
    product: str,
    section_key: str,
    section_title: str,
    section_guidance: str,
    body_so_far: List[Dict[str, Any]],
    mind_ctx: str,
) -> str:
    """Construct the research-pack prompt for a given section."""
    body_summary_lines = []
    for s in body_so_far:
        title = s.get("title", s.get("key", "?"))
        content = (s.get("content") or "")[:400]
        body_summary_lines.append(f"### {title}\n{content}")
    body_summary = "\n\n".join(body_summary_lines) if body_summary_lines else "(no body sections drafted yet)"

    mind_block = f"\n\nINSTITUTIONAL CONTEXT:\n{mind_ctx}\n" if mind_ctx else ""

    return f"""[Context: company={company}, product={product}, section={section_key}]

You are preparing a research pack for the "{section_title}" section of an IC memo.

Section guidance:
{section_guidance or '(no specific guidance)'}

Body sections already drafted:
{body_summary}{mind_block}

Your task: investigate using the available tools and return a structured JSON research pack.
You have a 5-turn hard cap — be efficient. Prioritise in this order:
1. Pull the most relevant analytics section (one tool call).
2. Search the data room for 2-3 key quotes supporting or contradicting the analytics.
3. Pull mind context for any accumulated knowledge on this section.
4. Identify 0-3 contradictions between body sections (only if they exist — don't invent them).
5. Recommend a stance consistent with the evidence.

Return ONLY a JSON object in this exact shape (no prose around it):

```json
{{
  "key_metrics": [
    {{"label": "Collection Rate", "value": "87.3%", "source": "tape analytics", "significance": "Top quartile for SME trade credit"}}
  ],
  "quotes": [
    {{"text": "direct quote from a doc", "source_doc": "filename.pdf", "page_or_section": "p.12"}}
  ],
  "contradictions": [
    {{"description": "what conflicts", "section_a": "Portfolio Analytics", "section_b": "Concentration Risk", "severity": "low|medium|high"}}
  ],
  "recommended_stance": "Invest",
  "supporting_evidence": [
    "one-line bullet summarising the strongest supporting data point",
    "another"
  ]
}}
```

Recommended stance MUST be one of: "Invest", "Conditional Invest", "Pass", "Monitor".

If you cannot find supporting evidence, return empty arrays for those fields
rather than inventing data. Do not wrap the JSON in markdown code fences
other than the one shown. Your output must parse as strict JSON."""


def _parse_pack(text: str) -> Dict[str, Any]:
    """Lenient JSON parser for the agent's research pack output.

    Strategy:
    1. Try strict json.loads
    2. Extract markdown-fenced JSON block
    3. Find the largest {...} substring and try that
    4. Return EMPTY_PACK on failure
    """
    if not text:
        return dict(EMPTY_PACK)

    # Strategy 1: strict parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return _normalize_pack(obj)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract from code fence
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            obj = json.loads(fence.group(1))
            if isinstance(obj, dict):
                return _normalize_pack(obj)
        except json.JSONDecodeError:
            pass

    # Strategy 3: brute force — find largest balanced {...}
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        candidate = text[start:end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return _normalize_pack(obj)
        except json.JSONDecodeError:
            pass

    logger.warning("Research pack JSON parse failed; returning empty pack")
    return dict(EMPTY_PACK)


def _normalize_pack(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure every expected field is present, typed, and reasonable."""
    out = dict(EMPTY_PACK)
    if isinstance(obj.get("key_metrics"), list):
        out["key_metrics"] = [m for m in obj["key_metrics"] if isinstance(m, dict)][:10]
    if isinstance(obj.get("quotes"), list):
        out["quotes"] = [q for q in obj["quotes"] if isinstance(q, dict)][:10]
    if isinstance(obj.get("contradictions"), list):
        out["contradictions"] = [c for c in obj["contradictions"] if isinstance(c, dict)][:5]
    stance = obj.get("recommended_stance")
    if stance in ("Invest", "Conditional Invest", "Pass", "Monitor"):
        out["recommended_stance"] = stance
    if isinstance(obj.get("supporting_evidence"), list):
        out["supporting_evidence"] = [str(s) for s in obj["supporting_evidence"] if s][:8]
    return out


def generate_research_pack(
    *,
    company: str,
    product: str,
    section_key: str,
    section_title: str,
    section_guidance: str = "",
    body_so_far: Optional[List[Dict[str, Any]]] = None,
    mind_ctx: str = "",
    max_turns: int = 5,
) -> Dict[str, Any]:
    """Run a short-burst agent session and return the parsed research pack.

    Args:
        company, product: scope
        section_key, section_title, section_guidance: the judgment section
        body_so_far: already-drafted body sections (list of {key, title, content, ...})
        mind_ctx: pre-assembled 5-layer mind context string
        max_turns: hard cap on agent turns (default 5)

    Returns:
        A normalized research pack dict. Never raises — errors return EMPTY_PACK.
    """
    body_so_far = body_so_far or []
    prompt = _build_prompt(
        company=company,
        product=product,
        section_key=section_key,
        section_title=section_title,
        section_guidance=section_guidance,
        body_so_far=body_so_far,
        mind_ctx=mind_ctx,
    )

    try:
        # Reuse the existing sync bridge + agent framework — memo_writer has
        # the right tool whitelist (analytics, dataroom, mind, memo, portfolio).
        # We cap max_turns to keep each call short.
        from core.agents.internal import _run_agent_sync
        text = _run_agent_sync(
            "memo_writer",
            prompt,
            metadata={
                "company": company,
                "product": product,
                "type": "research_pack",
                "section": section_key,
            },
            max_turns=max_turns,
        )
    except Exception as e:
        logger.warning("Research pack agent failed for %s/%s section=%s: %s",
                       company, product, section_key, e)
        return dict(EMPTY_PACK)

    pack = _parse_pack(text)
    logger.info("Research pack [%s/%s/%s] metrics=%d quotes=%d contradictions=%d stance=%s",
                company, product, section_key,
                len(pack["key_metrics"]), len(pack["quotes"]),
                len(pack["contradictions"]), pack["recommended_stance"])
    return pack


def record_memo_thesis_to_mind(memo: Dict[str, Any],
                               research_packs: Optional[Dict[str, Dict[str, Any]]] = None) -> Optional[str]:
    """Write the memo's thesis signals into the Company Mind.

    For each judgment section that had a research pack with a
    `recommended_stance`, creates a `findings` entry in the Company Mind
    with metadata linking back to the memo. Future memos will see these
    entries in Layer 4 of their AI context and can flag drift vs. prior
    recommendations.

    Called after the memo is saved by MemoStorage, so this is best-effort
    and must not raise — it's enriching institutional memory, not
    blocking persistence.

    Args:
        memo: the saved memo object
        research_packs: explicit packs dict (keyed by section_key). If not
            supplied, falls back to memo['_research_packs']. Callers that
            save via MemoStorage should capture packs BEFORE save strips
            them from the memo object, then pass them here.

    Returns the mind entry id if one was recorded, else None.
    """
    try:
        from core.mind.company_mind import CompanyMind
    except Exception as e:
        logger.warning("record_memo_thesis_to_mind: CompanyMind unavailable: %s", e)
        return None

    company = memo.get("company", "")
    product = memo.get("product", "")
    memo_id = memo.get("id", "")
    if not (company and product and memo_id):
        return None

    packs = research_packs if research_packs is not None else (memo.get("_research_packs") or {})
    if not packs:
        return None

    stances = []
    for section_key, pack in packs.items():
        stance = (pack.get("recommended_stance") or "").strip()
        if stance in ("Invest", "Conditional Invest", "Pass", "Monitor"):
            stances.append({
                "section_key": section_key,
                "stance": stance,
                "key_metrics": pack.get("key_metrics", [])[:5],
                "supporting_evidence": pack.get("supporting_evidence", [])[:3],
            })

    if not stances:
        return None

    # Prefer the stance from the most "thesis-y" section in priority order.
    # Iterate priority keys — first match wins. Falls back to the first
    # stance if none of the priority sections are present.
    priority = ("investment_thesis", "recommendation", "exec_summary")
    headline = next(
        (s for key in priority for s in stances if s["section_key"] == key),
        stances[0],
    )

    title = memo.get("title") or f"Memo {memo_id}"
    finding_text = (
        f"Memo thesis — {title}: agent-recommended stance "
        f"'{headline['stance']}' (from {headline['section_key']}). "
        f"Key supporting metrics: "
        + "; ".join(
            f"{m.get('label')}: {m.get('value')}"
            for m in headline["key_metrics"] if isinstance(m, dict)
        )
    )

    try:
        cm = CompanyMind(company, product)
        entry = cm.record_research_finding(
            finding=finding_text,
            confidence="medium",
            source_docs=[f"memo:{memo_id}"],
        )
        logger.info("Recorded memo thesis to CompanyMind: %s/%s -> %s (stance=%s)",
                    company, product, entry.id, headline["stance"])
        return entry.id
    except Exception as e:
        logger.warning("record_memo_thesis_to_mind failed: %s", e)
        return None


def format_pack_for_prompt(pack: Dict[str, Any]) -> str:
    """Render a research pack as a human-readable block for injection into
    the final synthesis prompt. Returns empty string if pack has no content."""
    if not any(pack.get(k) for k in ("key_metrics", "quotes", "contradictions", "supporting_evidence")):
        return ""

    lines = ["## Research Pack"]

    if pack.get("key_metrics"):
        lines.append("\n### Key Metrics")
        for m in pack["key_metrics"]:
            label = m.get("label", "?")
            value = m.get("value", "?")
            sig = m.get("significance", "")
            src = m.get("source", "")
            parts = [f"- **{label}**: {value}"]
            if sig:
                parts.append(f"— {sig}")
            if src:
                parts.append(f"({src})")
            lines.append(" ".join(parts))

    if pack.get("quotes"):
        lines.append("\n### Supporting Quotes")
        for q in pack["quotes"]:
            text = q.get("text", "")
            src = q.get("source_doc", "?")
            where = q.get("page_or_section", "")
            cite = f"{src} {where}".strip()
            lines.append(f'- "{text}" — *{cite}*')

    if pack.get("contradictions"):
        lines.append("\n### Contradictions Detected")
        for c in pack["contradictions"]:
            desc = c.get("description", "")
            a = c.get("section_a", "?")
            b = c.get("section_b", "?")
            sev = c.get("severity", "medium")
            lines.append(f"- [{sev.upper()}] {desc} (between *{a}* and *{b}*)")

    if pack.get("supporting_evidence"):
        lines.append("\n### Supporting Evidence")
        for e in pack["supporting_evidence"]:
            lines.append(f"- {e}")

    stance = pack.get("recommended_stance")
    if stance:
        lines.append(f"\n**Agent-recommended stance:** {stance}")

    return "\n".join(lines)
