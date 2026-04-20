"""Framework Codification Hook (D6).

Surfaces Master Mind entries tagged `framework_evolution` that haven't
yet been codified into `core/ANALYSIS_FRAMEWORK.md`, and provides a
mark-codified operation so `/extend-framework` can close the loop.

The knowledge flow this enables:

    Company Mind (position-level note)
       ↓ promote_entry
    Asset Class Mind (cross-company pattern)
       ↓ promote_entry(target_scope='master', target_category='framework_evolution')
    Master Mind framework_evolution.jsonl
       ↓ [hook this module exposes]
    /extend-framework slash command
       ↓
    core/ANALYSIS_FRAMEWORK.md section added/amended
       ↓ mark_codified(entry_id, commit_sha)
    Loop closed: entry.metadata.codified_in_framework = True

The `framework_evolution` master-mind category was created in session 17
but until now had no surface beyond the raw JSONL file. Analysts had no
queue to work from when running `/extend-framework`; this module is
that queue.

Design notes:
  - This module is pure I/O over `data/_master_mind/framework_evolution.jsonl`.
    It does not call out to git, LLMs, or the Framework document —
    that's the `/extend-framework` command's job.
  - `codified_in_framework` + `codification_commit` fields in entry
    metadata are the source of truth. The function rewrites the JSONL
    with updated metadata on codification (same atomic-write pattern as
    the rest of MasterMind).
  - Not wired into any automatic AI context — codified lessons flow
    into the Framework document itself (Layer 1), and the raw entries
    remain in Layer 2 for analyst review until codification.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core.mind.master_mind import MasterMind, _FILES as _MASTER_FILES

logger = logging.getLogger(__name__)

_CATEGORY = "framework_evolution"


def _jsonl_path() -> Path:
    """Resolve the current framework_evolution.jsonl path.

    Uses MasterMind() to honour whatever _PROJECT_ROOT / _BASE_DIR
    monkeypatching the caller has applied (test isolation).
    """
    mm = MasterMind()
    return mm.base_dir / _MASTER_FILES[_CATEGORY]


def get_codification_candidates(
    *,
    include_codified: bool = False,
    limit: Optional[int] = None,
) -> List[Dict]:
    """Return framework_evolution entries, newest first.

    Args:
        include_codified: When True, returns all entries (codified +
            pending). Default False returns only entries that still
            need to be codified into the Framework document.
        limit: Optional cap on number of entries returned.

    Returns:
        List of entry dicts, each with keys:
            id, timestamp, category, content, source, metadata,
            codified_in_framework, codification_commit,
            promoted_from (if promoted up the stack)
    """
    path = _jsonl_path()
    if not path.exists():
        return []

    results: List[Dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "get_codification_candidates: bad JSONL line skipped: %s", e
                    )
                    continue
                meta = d.get("metadata") or {}
                codified = bool(meta.get("codified_in_framework", False))
                if not include_codified and codified:
                    continue
                results.append({
                    "id": d.get("id"),
                    "timestamp": d.get("timestamp"),
                    "category": d.get("category", _CATEGORY),
                    "content": d.get("content", ""),
                    "source": meta.get("source", "unknown"),
                    "metadata": meta,
                    "codified_in_framework": codified,
                    "codification_commit": meta.get("codification_commit", ""),
                    "promoted_from": meta.get("promoted_from"),
                })
    except OSError as e:
        logger.warning("get_codification_candidates: read failed %s: %s", path, e)
        return []

    results.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    if limit:
        results = results[:limit]
    return results


def mark_codified(
    entry_id: str,
    *,
    commit_sha: Optional[str] = None,
    framework_section: Optional[str] = None,
    codified_by: Optional[str] = None,
) -> Dict:
    """Mark a framework_evolution entry as codified.

    Updates metadata in-place:
        codified_in_framework: True
        codification_commit:   commit_sha or ""
        codification_section:  framework_section or ""
        codified_at:           UTC timestamp
        codified_by:           codified_by or ""

    The entry itself is never deleted — codified entries remain in the
    JSONL for audit. Filter with `include_codified=False` to hide them
    from the live queue.

    Args:
        entry_id: The mind entry's `id` field (UUID).
        commit_sha: Optional git commit that introduced the Framework
            change. Useful for traceability.
        framework_section: Optional identifier of the ANALYSIS_FRAMEWORK.md
            section the entry was codified into (e.g. "Section 16").
        codified_by: Optional analyst email / name for audit.

    Returns:
        The updated entry dict.

    Raises:
        ValueError: If no entry with the given id exists.
        OSError: If the file cannot be rewritten.
    """
    path = _jsonl_path()
    if not path.exists():
        raise ValueError(f"framework_evolution.jsonl not found at {path}")

    updated_entry: Optional[Dict] = None
    lines_out: List[str] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                # Preserve corrupt lines untouched rather than silently dropping
                lines_out.append(raw)
                continue
            if d.get("id") == entry_id:
                meta = d.setdefault("metadata", {})
                meta["codified_in_framework"] = True
                meta["codification_commit"] = commit_sha or ""
                meta["codification_section"] = framework_section or ""
                meta["codified_at"] = now_iso
                meta["codified_by"] = codified_by or ""
                updated_entry = d
                lines_out.append(json.dumps(d, ensure_ascii=False))
            else:
                lines_out.append(raw)

    if updated_entry is None:
        raise ValueError(f"No framework_evolution entry with id={entry_id}")

    # Atomic rewrite: write to .tmp, fsync, rename.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines_out) + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass  # Not all filesystems support fsync — not fatal
    os.replace(tmp_path, path)

    logger.info(
        "framework_codification: entry %s marked codified (commit=%s, section=%s)",
        entry_id, commit_sha or "?", framework_section or "?",
    )
    return updated_entry


def codification_counts() -> Dict[str, int]:
    """Quick tally for OperatorCenter / briefing surfaces."""
    all_entries = get_codification_candidates(include_codified=True)
    total = len(all_entries)
    codified = sum(1 for e in all_entries if e["codified_in_framework"])
    return {
        "total": total,
        "codified": codified,
        "pending": total - codified,
    }


__all__ = [
    "get_codification_candidates",
    "mark_codified",
    "codification_counts",
]
