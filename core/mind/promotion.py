"""
Mind Promotion — move entries up the layer stack with provenance.

The promotion chain mirrors the 6-layer context assembly in reverse:

    Company Mind   →   Asset Class Mind   →   Master Mind
      (per-company      (per-analysis_type    (fund-level)
       corrections /     benchmarks, peer
       findings)         comparison, sector
                         context)

Rules:
  - Source entry stays in place (never moved). A COPY is written to the
    target with metadata.promoted_from pointing back to (scope, key, id).
    Analysts can always see the provenance chain.
  - target_category must be valid for the target scope — see _TARGET_CATEGORIES.
  - Promoting to Asset Class requires target_key (the analysis_type).
  - Promoting to Master requires target_key=None.
  - Source entry's metadata is preserved and extended with a
    "promoted_to": [{"scope","key","id","at"}, ...] list so we can trace
    every downstream copy.
  - The source entry's `promoted` flag is set to True after any promotion.
    (A re-promote simply appends another entry to `promoted_to`.)

This module does NOT auto-promote — it's always an analyst action
(explicit button click or agent tool call).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.mind.asset_class_mind import AssetClassMind
from core.mind.company_mind import CompanyMind, MindEntry, _FILES as _COMPANY_FILES
from core.mind.master_mind import MasterMind, _FILES as _MASTER_FILES

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# Valid target categories per destination — narrow on purpose so promoted
# content lands in the right slot.
_TARGET_CATEGORIES = {
    "asset_class": {
        "benchmarks", "typical_terms", "external_research",
        "sector_context", "peer_comparison", "methodology_note",
    },
    "master": set(_MASTER_FILES.keys()),
}


# ── Helpers: locate + read source entry ──────────────────────────────────────

def _find_company_entry(company: str, product: str, entry_id: str) -> Optional[Tuple[MindEntry, Path, str]]:
    """Walk every JSONL file under the company mind dir to locate an entry.

    Returns (entry, file_path, category) or None.
    """
    mind = CompanyMind(company, product)
    for cat in _COMPANY_FILES.keys():
        path = mind._jsonl_path(cat)
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if d.get("id") == entry_id:
                        return MindEntry.from_dict(d), path, cat
        except OSError as e:
            logger.warning("_find_company_entry read failed on %s: %s", path, e)
    return None


def _find_asset_class_entry(analysis_type: str, entry_id: str) -> Optional[Tuple[MindEntry, Path, str]]:
    mind = AssetClassMind(analysis_type)
    path = mind.file_path
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("id") == entry_id:
                    entry = MindEntry.from_dict(d)
                    return entry, path, entry.category
    except OSError as e:
        logger.warning("_find_asset_class_entry read failed: %s", e)
    return None


# ── Helpers: mark source as promoted ─────────────────────────────────────────

def _rewrite_with_promoted_flag(
    source_path: Path,
    entry_id: str,
    promoted_record: Dict[str, Any],
) -> None:
    """Rewrite the source JSONL file, setting promoted=True and appending
    the new destination to metadata.promoted_to on the matched entry.
    """
    if not source_path.exists():
        return
    lines_out: List[str] = []
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    d = json.loads(stripped)
                except json.JSONDecodeError:
                    lines_out.append(line.rstrip("\n"))
                    continue
                if d.get("id") == entry_id:
                    d["promoted"] = True
                    md = d.setdefault("metadata", {})
                    if not isinstance(md, dict):
                        md = {}
                        d["metadata"] = md
                    promoted_to = md.setdefault("promoted_to", [])
                    if isinstance(promoted_to, list):
                        promoted_to.append(promoted_record)
                lines_out.append(json.dumps(d, ensure_ascii=False))
    except OSError as e:
        logger.error("_rewrite_with_promoted_flag read failed: %s", e)
        return

    tmp = source_path.with_suffix(source_path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + ("\n" if lines_out else ""))
    tmp.replace(source_path)


# ── Public API ───────────────────────────────────────────────────────────────

def promote_entry(
    *,
    source_scope: str,           # "company" | "asset_class"
    source_key: str,             # company name | analysis_type
    source_product: str = "",    # product name (only used if source_scope=company)
    entry_id: str,
    target_scope: str,           # "asset_class" | "master"
    target_key: Optional[str],   # analysis_type if target_scope=asset_class, else None
    target_category: str,
    note: Optional[str] = None,  # optional analyst note attached to the promotion
) -> Dict[str, Any]:
    """Promote a mind entry up the stack. Raises ValueError on bad inputs.

    Returns a dict describing the new entry + provenance chain.
    """
    # ── Validate target ──────────────────────────────────────────────────────
    if target_scope not in _TARGET_CATEGORIES:
        raise ValueError(
            f"target_scope must be one of {sorted(_TARGET_CATEGORIES.keys())}, got '{target_scope}'"
        )
    if target_category not in _TARGET_CATEGORIES[target_scope]:
        raise ValueError(
            f"Invalid target_category '{target_category}' for target_scope='{target_scope}'. "
            f"Allowed: {sorted(_TARGET_CATEGORIES[target_scope])}."
        )
    if target_scope == "asset_class" and not target_key:
        raise ValueError("target_scope=asset_class requires target_key (analysis_type)")
    if target_scope == "master" and target_key is not None:
        raise ValueError("target_scope=master must have target_key=None")

    # ── Validate source + load entry ─────────────────────────────────────────
    if source_scope == "company":
        if not source_key:
            raise ValueError("source_scope=company requires source_key (company name)")
        located = _find_company_entry(source_key, source_product, entry_id)
        if not located:
            raise ValueError(
                f"Company mind entry not found: company={source_key}, product={source_product}, id={entry_id}"
            )
        source_entry, source_path, source_category = located
    elif source_scope == "asset_class":
        if not source_key:
            raise ValueError("source_scope=asset_class requires source_key (analysis_type)")
        located = _find_asset_class_entry(source_key, entry_id)
        if not located:
            raise ValueError(
                f"Asset class mind entry not found: analysis_type={source_key}, id={entry_id}"
            )
        source_entry, source_path, source_category = located
        # Master is the only valid target from asset_class
        if target_scope != "master":
            raise ValueError("Entries from asset_class can only be promoted to master")
    else:
        raise ValueError(
            f"source_scope must be 'company' or 'asset_class', got '{source_scope}'"
        )

    # ── Assemble target metadata (preserve + extend) ─────────────────────────
    target_metadata: Dict[str, Any] = {}
    if isinstance(source_entry.metadata, dict):
        # Deep-ish copy — only the top level matters here
        target_metadata.update(source_entry.metadata)
    # Drop any old promoted_to list (belongs to the SOURCE, not the copy)
    target_metadata.pop("promoted_to", None)
    target_metadata["promoted_from"] = {
        "scope": source_scope,
        "key": source_key,
        "product": source_product if source_scope == "company" else None,
        "entry_id": source_entry.id,
        "original_category": source_category,
        "original_timestamp": source_entry.timestamp,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
    if note:
        target_metadata["promotion_note"] = note

    # ── Write to target mind ─────────────────────────────────────────────────
    if target_scope == "asset_class":
        target_mind = AssetClassMind(target_key)
        new_entry = target_mind.record(
            category=target_category,
            content=source_entry.content,
            metadata=target_metadata,
            source=f"promoted_from_{source_scope}",
        )
        new_entry_id = new_entry.id
    else:  # master
        master = MasterMind()
        new_entry = master.record(
            category=target_category,
            content=source_entry.content,
            metadata=target_metadata,
        )
        new_entry_id = new_entry.id

    # ── Update source: mark promoted, append to promoted_to ──────────────────
    _rewrite_with_promoted_flag(
        source_path,
        source_entry.id,
        {
            "scope": target_scope,
            "key": target_key,
            "category": target_category,
            "new_entry_id": new_entry_id,
            "at": datetime.now(timezone.utc).isoformat(),
        },
    )

    logger.info(
        "Promoted %s entry %s -> %s/%s (category=%s, new_id=%s)",
        source_scope, source_entry.id[:8],
        target_scope, target_key or "", target_category, new_entry_id[:8],
    )

    return {
        "source_scope": source_scope,
        "source_key": source_key,
        "source_entry_id": source_entry.id,
        "target_scope": target_scope,
        "target_key": target_key,
        "target_category": target_category,
        "new_entry_id": new_entry_id,
        "content": source_entry.content,
        "promoted_at": target_metadata["promoted_from"]["promoted_at"],
    }


__all__ = ["promote_entry"]
