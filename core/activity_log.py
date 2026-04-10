"""
Activity Log — Centralized event logging for the Laith credit platform.

Records all significant platform actions to a single JSONL file for
operator visibility. Import and call log_activity() from any endpoint.

Storage: reports/activity_log.jsonl (append-only)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_PATH = _PROJECT_ROOT / "reports" / "activity_log.jsonl"

# Action types
TAPE_LOADED = "tape_loaded"
AI_COMMENTARY = "ai_commentary"
AI_EXECUTIVE_SUMMARY = "ai_executive_summary"
AI_TAB_INSIGHT = "ai_tab_insight"
AI_CHAT = "ai_chat"
LEGAL_UPLOAD = "legal_upload"
LEGAL_EXTRACTION = "legal_extraction"
DATAROOM_INGEST = "dataroom_ingest"
MEMO_GENERATED = "memo_generated"
MEMO_EXPORTED = "memo_exported"
REPORT_GENERATED = "report_generated"
RESEARCH_QUERY = "research_query"
MIND_ENTRY_RECORDED = "mind_entry_recorded"
COMPLIANCE_CERT = "compliance_cert"
BREACH_NOTIFICATION = "breach_notification"
FACILITY_PARAMS_SAVED = "facility_params_saved"
OPERATOR_TODO = "operator_todo"


def log_activity(
    action: str,
    company: Optional[str] = None,
    product: Optional[str] = None,
    detail: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append an activity event to the central log.

    Args:
        action: Action type constant (e.g., TAPE_LOADED, AI_COMMENTARY)
        company: Company name (optional for fund-level actions)
        product: Product name (optional)
        detail: Human-readable description
        metadata: Additional structured data

    Returns:
        The logged event dict.
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "company": company,
        "product": product,
        "detail": detail,
        "metadata": metadata or {},
    }

    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("activity_log: failed to write event: %s", e)

    return event


def read_activity_log(limit: int = 50, company: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read recent activity events, newest first.

    Args:
        limit: Max events to return.
        company: Filter to a specific company (optional).

    Returns:
        List of event dicts, sorted by timestamp descending.
    """
    if not _LOG_PATH.exists():
        return []

    events = []
    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if company and event.get("company") != company:
                        continue
                    events.append(event)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.warning("activity_log: failed to read: %s", e)

    # Return newest first, limited
    events.reverse()
    return events[:limit]
