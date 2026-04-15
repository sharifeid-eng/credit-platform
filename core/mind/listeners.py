"""
Event Listeners — Wire event bus to compilation, learning, and thesis systems.

Registered at app startup. Each listener is lightweight (file I/O only,
no AI calls). Heavy processing is logged for later review.

Listener registry:
- TAPE_INGESTED → extract metrics, compile, check thesis drift
- DOCUMENT_INGESTED → extract entities, compile
- MEMO_EDITED → analyze correction, generate learning rule
- CORRECTION_RECORDED → analyze correction, generate learning rule
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_registered = False


def register_all_listeners() -> None:
    """Register all event listeners on the global event bus.

    Safe to call multiple times — guards against double registration.
    """
    global _registered
    if _registered:
        return
    _registered = True

    from core.mind.event_bus import event_bus, Events

    event_bus.subscribe(Events.TAPE_INGESTED, _on_tape_ingested)
    event_bus.subscribe(Events.DOCUMENT_INGESTED, _on_document_ingested)
    event_bus.subscribe(Events.MEMO_EDITED, _on_memo_edited)
    event_bus.subscribe(Events.CORRECTION_RECORDED, _on_correction_recorded)

    logger.info("Intelligence listeners registered: 4 handlers on event bus")


def _get_mind_dir(company: str, product: str) -> Path:
    return _PROJECT_ROOT / "data" / company / "mind"


# --------------------------------------------------------------------------
# Tape ingested → compile metrics + check thesis
# --------------------------------------------------------------------------

def _on_tape_ingested(payload: Dict[str, Any]) -> None:
    """Handle TAPE_INGESTED event.

    Payload: company, product, snapshot, metrics (dict of summary values)
    """
    company = payload.get("company", "")
    product = payload.get("product", "")
    metrics = payload.get("metrics", {})
    snapshot = payload.get("snapshot", "")

    if not company or not product or not metrics:
        return

    mind_dir = _get_mind_dir(company, product)

    # 1. Extract metric entities and compile
    try:
        from core.mind.entity_extractor import extract_entities_from_metrics
        from core.mind.compiler import KnowledgeCompiler

        entities = extract_entities_from_metrics(metrics, source_ref=snapshot)
        if entities:
            compiler = KnowledgeCompiler(mind_dir)
            report = compiler.compile(entities, snapshot, company, product)
            logger.info(
                "Tape compilation for %s/%s: %d actions from %d entities",
                company, product, report.total_actions, len(entities),
            )
    except Exception as e:
        logger.warning("Tape compilation failed for %s/%s: %s", company, product, e)

    # 2. Check thesis drift
    try:
        from core.mind.thesis import ThesisTracker

        tracker = ThesisTracker(company, product)
        thesis = tracker.load()
        if thesis:
            # Build metrics dict with keys matching pillar metric_keys
            drift_metrics = _build_drift_metrics(metrics)
            alerts = tracker.check_drift(drift_metrics)
            if alerts:
                logger.info(
                    "Thesis drift for %s/%s: %d alerts",
                    company, product, len(alerts),
                )
                for alert in alerts:
                    logger.info(
                        "  [%s] %s: %s → %s (%s)",
                        alert.severity, alert.claim,
                        alert.previous_status, alert.new_status,
                        alert.recommendation[:80],
                    )
    except Exception as e:
        logger.warning("Thesis drift check failed for %s/%s: %s", company, product, e)


def _build_drift_metrics(metrics: Dict[str, Any]) -> Dict[str, float]:
    """Normalize metric keys for thesis pillar matching."""
    result = {}
    for key, value in metrics.items():
        if value is None:
            continue
        try:
            result[key] = float(value)
        except (ValueError, TypeError):
            continue
    # Common aliases
    if "collection_rate" in result:
        result["collection_rate_pct"] = result["collection_rate"]
    return result


# --------------------------------------------------------------------------
# Document ingested → extract entities, compile
# --------------------------------------------------------------------------

def _on_document_ingested(payload: Dict[str, Any]) -> None:
    """Handle DOCUMENT_INGESTED event.

    Payload: company, product, doc_id, text, document_type, filename
    """
    company = payload.get("company", "")
    product = payload.get("product", "")
    doc_id = payload.get("doc_id", "")
    text = payload.get("text", "")

    if not company or not product or not text:
        return

    mind_dir = _get_mind_dir(company, product)

    try:
        from core.mind.entity_extractor import extract_entities_from_text
        from core.mind.compiler import KnowledgeCompiler

        entities = extract_entities_from_text(text, source_doc_id=doc_id)
        if entities:
            compiler = KnowledgeCompiler(mind_dir)
            report = compiler.compile(entities, doc_id, company, product)
            logger.info(
                "Document compilation for %s/%s (%s): %d actions from %d entities",
                company, product, doc_id, report.total_actions, len(entities),
            )
    except Exception as e:
        logger.warning("Document compilation failed for %s/%s: %s", company, product, e)


# --------------------------------------------------------------------------
# Memo edited → extract learning rule
# --------------------------------------------------------------------------

def _on_memo_edited(payload: Dict[str, Any]) -> None:
    """Handle MEMO_EDITED event.

    Payload: company, product, section_key, ai_version, analyst_version, memo_id
    """
    company = payload.get("company", "")
    product = payload.get("product", "")
    ai_version = payload.get("ai_version", "")
    analyst_version = payload.get("analyst_version", "")
    section_key = payload.get("section_key", "")

    if not ai_version or not analyst_version:
        return

    # Only analyze substantive changes
    ai_words = len(ai_version.split())
    analyst_words = len(analyst_version.split())
    if ai_words == 0:
        return
    change_ratio = abs(ai_words - analyst_words) / max(ai_words, 1)
    if change_ratio < 0.05:
        return  # trivial change

    try:
        from core.mind.learning import LearningEngine
        from core.mind.company_mind import CompanyMind

        engine = LearningEngine()
        rule = engine.analyze_correction(
            original=ai_version,
            corrected=analyst_version,
            context=f"memo section: {section_key}",
        )
        if rule:
            # Save rule as knowledge node in company mind
            node = rule.to_knowledge_node()
            mind = CompanyMind(company, product)
            mind._append_entry(
                mind._make_local_entry("corrections", rule.rule_text, {
                    "auto_generated": True,
                    "rule_category": rule.category,
                    "trigger_condition": rule.trigger_condition,
                    "_graph": {"node_type": "rule"},
                })
            )
            logger.info(
                "Learning rule generated for %s/%s: [%s] %s",
                company, product, rule.category, rule.rule_text[:100],
            )
    except Exception as e:
        logger.warning("Learning rule extraction failed: %s", e)


# --------------------------------------------------------------------------
# Correction recorded → extract learning rule
# --------------------------------------------------------------------------

def _on_correction_recorded(payload: Dict[str, Any]) -> None:
    """Handle CORRECTION_RECORDED event.

    Payload: company, product, original, corrected, reason, entry_id
    """
    company = payload.get("company", "")
    product = payload.get("product", "")
    original = payload.get("original", "")
    corrected = payload.get("corrected", "")
    reason = payload.get("reason", "")

    if not original or not corrected:
        return

    try:
        from core.mind.learning import LearningEngine

        engine = LearningEngine()
        rule = engine.analyze_correction(original, corrected, context=reason)
        if rule:
            logger.info(
                "Learning rule from correction in %s/%s: [%s] %s",
                company, product, rule.category, rule.rule_text[:100],
            )
            # Rule is logged; storage handled by the correction recording itself
    except Exception as e:
        logger.warning("Correction analysis failed: %s", e)
