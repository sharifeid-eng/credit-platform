"""
Intelligence System API endpoints.

Thesis management, morning briefings, knowledge search, learning engine,
and chat feedback — all wired to the core.mind modules.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from core.activity_log import log_activity

logger = logging.getLogger(__name__)

router = APIRouter(tags=["intelligence"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Thesis Endpoints ─────────────────────────────────────────────────────────

@router.get("/companies/{company}/products/{product}/thesis")
def get_thesis(company: str, product: str):
    """Load the current investment thesis for a company/product."""
    from core.mind.thesis import ThesisTracker

    tracker = ThesisTracker(company, product)
    thesis = tracker.load()
    if not thesis:
        raise HTTPException(status_code=404, detail="No thesis found")
    return thesis.to_dict()


@router.post("/companies/{company}/products/{product}/thesis")
def save_thesis(company: str, product: str, body: dict = {}):
    """Create or update an investment thesis."""
    from core.mind.thesis import ThesisTracker, InvestmentThesis

    if not body.get("title"):
        raise HTTPException(status_code=400, detail="title is required")

    # Ensure company/product match URL
    body["company"] = company
    body["product"] = product

    tracker = ThesisTracker(company, product)
    existing = tracker.load()

    thesis = InvestmentThesis.from_dict(body)
    if existing:
        thesis.version = existing.version + 1

    change_reason = body.get("change_reason", "API update")
    tracker.save(thesis, change_reason=change_reason)
    log_activity("thesis_updated", company, product, f"Thesis v{thesis.version}: {change_reason}")

    return thesis.to_dict()


@router.get("/companies/{company}/products/{product}/thesis/drift")
def check_thesis_drift(company: str, product: str):
    """Check thesis drift against latest snapshot metrics."""
    from core.mind.thesis import ThesisTracker
    from core.loader import get_snapshots, load_snapshot
    from core.analysis import compute_summary

    tracker = ThesisTracker(company, product)
    thesis = tracker.load()
    if not thesis:
        raise HTTPException(status_code=404, detail="No thesis found")

    # Load latest snapshot metrics
    snaps = get_snapshots(company, product)
    if not snaps:
        raise HTTPException(status_code=404, detail="No snapshots found")

    df = load_snapshot(snaps[-1]["filepath"])
    summary = compute_summary(df, 1.0)

    # Build metrics dict matching pillar metric_keys
    metrics = {}
    for key, val in summary.items():
        if isinstance(val, (int, float)) and val == val:  # not NaN
            metrics[key] = float(val)

    alerts = tracker.check_drift(metrics)
    return {
        "alerts": [a.to_dict() for a in alerts],
        "conviction_score": thesis.conviction_score,
        "pillars_checked": len(thesis.active_pillars),
    }


@router.get("/companies/{company}/products/{product}/thesis/log")
def get_thesis_log(company: str, product: str, limit: int = Query(50, ge=1, le=200)):
    """Get thesis change history."""
    from core.mind.thesis import ThesisTracker

    tracker = ThesisTracker(company, product)
    return {"log": tracker.get_log(limit=limit)}


# ── Briefing Endpoint ─────────────────────────────────────────────────────────

@router.get("/operator/briefing")
def get_morning_briefing():
    """Generate a morning briefing — no AI calls, pure file I/O."""
    from core.mind.briefing import generate_morning_briefing

    try:
        briefing = generate_morning_briefing()
        return briefing.to_dict()
    except Exception as e:
        logger.error("Failed to generate briefing: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Knowledge Search ──────────────────────────────────────────────────────────

@router.get("/knowledge/search")
def search_knowledge(
    q: str = Query(..., min_length=1, description="Search query"),
    company: Optional[str] = None,
    categories: Optional[str] = None,
    node_types: Optional[str] = None,
    max_results: int = Query(20, ge=1, le=100),
):
    """Search across all knowledge stores (mind, lessons, decisions, entities)."""
    from core.mind.kb_query import KnowledgeBaseQuery

    kb = KnowledgeBaseQuery()
    results = kb.search(
        query=q,
        company=company,
        categories=categories.split(",") if categories else None,
        node_types=node_types.split(",") if node_types else None,
        max_results=max_results,
    )
    return {
        "results": [r.to_dict() for r in results],
        "total": len(results),
        "query": q,
    }


# ── Learning Endpoints ────────────────────────────────────────────────────────

@router.get("/operator/learning")
def get_learning_summary():
    """List recent corrections, auto-rules, and codification candidates."""
    from core.mind.learning import LearningEngine
    from core.mind.company_mind import CompanyMind

    engine = LearningEngine()
    data_dir = _PROJECT_ROOT / "data"

    # Aggregate corrections across all companies
    all_corrections = []
    all_rules = []

    if data_dir.exists():
        for company_dir in data_dir.iterdir():
            if not company_dir.is_dir() or company_dir.name.startswith(("_", ".")):
                continue
            for product_dir in company_dir.iterdir():
                if not product_dir.is_dir():
                    continue
                mind_dir = product_dir / "mind"
                if not mind_dir.exists():
                    continue

                # Load corrections
                corrections_file = mind_dir / "corrections.jsonl"
                if corrections_file.exists():
                    try:
                        import json
                        with open(corrections_file, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    entry = json.loads(line)
                                    entry["_company"] = company_dir.name
                                    entry["_product"] = product_dir.name
                                    all_corrections.append(entry)
                    except Exception:
                        pass

                # Load rules (node_type="rule" in any JSONL)
                for jsonl in mind_dir.glob("*.jsonl"):
                    try:
                        import json
                        with open(jsonl, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    entry = json.loads(line)
                                    if entry.get("metadata", {}).get("_graph", {}).get("node_type") == "rule":
                                        entry["_company"] = company_dir.name
                                        entry["_product"] = product_dir.name
                                        all_rules.append(entry)
                    except Exception:
                        pass

    # Extract patterns
    patterns = engine.extract_patterns(all_corrections) if all_corrections else []
    freq = engine.get_correction_frequency(all_corrections) if all_corrections else {}

    # Sort corrections by timestamp (newest first)
    all_corrections.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {
        "corrections": all_corrections[:50],
        "rules": all_rules[:30],
        "patterns": [p.to_dict() for p in patterns],
        "frequency": freq,
        "total_corrections": len(all_corrections),
        "total_rules": len(all_rules),
    }


@router.get("/operator/learning/rules")
def get_learning_rules():
    """List all active learning rules across all companies."""
    import json

    data_dir = _PROJECT_ROOT / "data"
    rules = []

    if data_dir.exists():
        for company_dir in data_dir.iterdir():
            if not company_dir.is_dir() or company_dir.name.startswith(("_", ".")):
                continue
            for product_dir in company_dir.iterdir():
                if not product_dir.is_dir():
                    continue
                mind_dir = product_dir / "mind"
                if not mind_dir.exists():
                    continue

                for jsonl in mind_dir.glob("*.jsonl"):
                    try:
                        with open(jsonl, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    entry = json.loads(line)
                                    graph = entry.get("metadata", {}).get("_graph", {})
                                    if graph.get("node_type") == "rule":
                                        entry["_company"] = company_dir.name
                                        entry["_product"] = product_dir.name
                                        rules.append(entry)
                    except Exception:
                        pass

    rules.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"rules": rules[:50], "total": len(rules)}


# ── Chat Feedback ─────────────────────────────────────────────────────────────

@router.post("/companies/{company}/products/{product}/chat-feedback")
def record_chat_feedback(company: str, product: str, body: dict = {}):
    """Record thumbs up/down feedback on AI chat responses.

    Body: {
        rating: "up" | "down",
        message_index: int (optional),
        original_response: str (optional, for corrections),
        corrected_response: str (optional),
        reason: str (optional),
    }
    """
    rating = body.get("rating", "")
    if rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")

    log_activity("chat_feedback", company, product, f"Chat feedback: {rating}")

    # For thumbs-down with correction, fire CORRECTION_RECORDED
    if rating == "down":
        original = body.get("original_response", "")
        corrected = body.get("corrected_response", "")
        reason = body.get("reason", "")

        if original and corrected:
            try:
                from core.mind.event_bus import event_bus, Events
                from core.mind.company_mind import CompanyMind

                cm = CompanyMind(company, product)
                entry = cm.record_correction(
                    category="chat_feedback",
                    original=original,
                    corrected=corrected,
                    reason=reason,
                )

                event_bus.publish(Events.CORRECTION_RECORDED, {
                    "company": company,
                    "product": product,
                    "original": original,
                    "corrected": corrected,
                    "reason": reason,
                    "entry_id": entry.id if entry else "",
                })
            except Exception as e:
                logger.warning("Chat feedback correction recording failed: %s", e)
        elif reason:
            # Record reason-only feedback in company mind
            try:
                from core.mind.company_mind import CompanyMind
                cm = CompanyMind(company, product)
                cm.record_data_quality_note(
                    f"Chat feedback (negative): {reason}",
                    tape_or_doc="data_chat",
                )
            except Exception:
                pass

    return {"status": "recorded", "rating": rating}
