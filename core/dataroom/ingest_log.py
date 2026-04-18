"""
Data Room Ingest Manifest Writer.

Appends structured JSONL entries to ``data/{company}/dataroom/ingest_log.jsonl``
every time ``ingest()`` or ``refresh()`` runs. Each line captures counts,
duration, parser warnings, index status, and classifier fallback use — giving
operators an auditable trail that `activity_log.jsonl` can't (it's a single
line per ingest with free-text only).

Consumed by:
- ``DataRoomEngine.audit()`` — reports last ingest timestamp + counts.
- ``scripts/dataroom_ctl.py audit`` — CLI health output.
- ``/dataroom/health`` endpoint — operator center surface.

Design constraints:
- Append-only JSONL (never rewrite). Keeps history for trend analysis.
- Zero dependencies — pure stdlib.
- One entry per ingest/refresh call. Partial failures captured as ``errors``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("laith.dataroom.ingest_log")


def _log_path(data_root: Path, company: str) -> Path:
    """Path to the append-only manifest file for a company."""
    d = data_root / company / "dataroom"
    d.mkdir(parents=True, exist_ok=True)
    return d / "ingest_log.jsonl"


def record_ingest(
    data_root: Path,
    company: str,
    product: str,
    action: str,
    started_at: datetime,
    result: dict[str, Any],
    extras: dict[str, Any] | None = None,
) -> None:
    """Append one ingest manifest entry.

    Args:
        data_root: Root data directory (Path).
        company: Company identifier (e.g. "SILQ").
        product: Product identifier (e.g. "KSA") — may be empty for company-level ops.
        action: One of "ingest", "refresh", "rebuild-index", "classify".
        started_at: Timestamp when the operation began.
        result: The dict returned by the engine call (contains counts).
        extras: Optional additional fields to merge (e.g. classifier stats).
    """
    duration_s = (datetime.now() - started_at).total_seconds()

    entry = {
        "ts": datetime.now().isoformat()[:19],
        "action": action,
        "company": company,
        "product": product or "",
        "duration_s": round(duration_s, 2),
        "files_seen": result.get("total_files", result.get("files_seen", 0)),
        "added": result.get("added", result.get("ingested", 0)),
        "updated": result.get("updated", 0),
        "skipped": result.get("skipped", 0),
        "unchanged": result.get("unchanged", 0),
        "orphans_dropped": result.get("orphans_dropped", 0),
        "removed": result.get("removed", 0),
        "errors": len(result.get("errors", [])) if isinstance(result.get("errors"), list) else 0,
    }

    if extras:
        entry.update(extras)

    # Capture a summary of errors (without dumping the entire list) so operators
    # can scan the log without reading individual chunks.
    errs = result.get("errors") or []
    if isinstance(errs, list) and errs:
        entry["error_samples"] = [
            {"file": e.get("file", "?"), "error": str(e.get("error", ""))[:200]}
            for e in errs[:3]
        ]

    try:
        path = _log_path(data_root, company)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError as e:
        # Never block an ingest on logging failure
        logger.warning(
            "[ingest_log] Failed to write manifest for %s (%s): %s",
            company, action, e,
        )


def read_manifest(data_root: Path, company: str, limit: int = 50) -> list[dict]:
    """Read the last N manifest entries (newest-first).

    Args:
        data_root: Root data directory.
        company: Company identifier.
        limit: Max entries to return (default 50).

    Returns:
        List of manifest dicts, newest first.
    """
    path = _log_path(data_root, company)
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []

    entries: list[dict] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # Skip corrupted line, don't break reader

    entries.reverse()
    return entries


def last_ingest(data_root: Path, company: str) -> dict | None:
    """Return the most recent successful (errors=0) manifest entry, or None.

    Used by audit() to answer "when was the last clean ingest?".
    """
    entries = read_manifest(data_root, company, limit=100)
    for entry in entries:
        if entry.get("errors", 0) == 0 and entry.get("action") in ("ingest", "refresh"):
            return entry
    return None
