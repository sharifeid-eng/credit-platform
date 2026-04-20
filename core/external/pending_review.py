"""Pending Review Queue for external-origin knowledge.

Anything pulled from outside the platform (web search, future news/RSS/API
pollers) lands HERE first — never directly in Company / Asset Class / Master
Mind. An analyst approves or rejects each entry. Approval promotes the
entry to its declared target scope with full citation provenance.

Storage: data/_pending_review/queue.jsonl — append-only, status updated in
place by rewriting the file when an entry is approved/rejected (same
pattern as CompanyMind promotion).

Schema (one JSON object per line):
    {
      "id":             uuid4 str,
      "timestamp":      ISO-8601 UTC creation time,
      "source":         "web_search" | "rss" | "manual" | "agent" | ...,
      "target_scope":   "company" | "asset_class" | "master",
      "target_key":     company name (if company) | analysis_type (if asset_class) | null (if master),
      "category":       category to use when promoting (e.g. "external_research",
                        "sector_context", "benchmarks")
      "title":          short one-line summary (for review UI)
      "content":        the full content that would land in the target mind
      "citations":      [{"url": str, "title": str, "snippet": str, "retrieved_at": str}]
      "query":          (optional) the question that produced this result — useful audit trail
      "status":         "pending" | "approved" | "rejected"
      "reviewed_by":    null | email / identifier
      "reviewed_at":    null | ISO-8601
      "review_note":    null | free text from reviewer
      "promoted_entry_id": null | MindEntry id after approval
    }
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PATH = _PROJECT_ROOT / "data" / "_pending_review" / "queue.jsonl"


class TargetScope(str, Enum):
    COMPANY = "company"
    ASSET_CLASS = "asset_class"
    MASTER = "master"


_VALID_STATUSES = {"pending", "approved", "rejected"}


@dataclass
class PendingEntry:
    id: str
    timestamp: str
    source: str
    target_scope: str     # TargetScope value
    target_key: Optional[str]
    category: str
    title: str
    content: str
    citations: List[Dict[str, str]] = field(default_factory=list)
    query: Optional[str] = None
    status: str = "pending"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None
    promoted_entry_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "source": self.source,
            "target_scope": self.target_scope,
            "target_key": self.target_key,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "citations": self.citations,
            "query": self.query,
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "review_note": self.review_note,
            "promoted_entry_id": self.promoted_entry_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> PendingEntry:
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            timestamp=d.get("timestamp", datetime.now(timezone.utc).isoformat()),
            source=d.get("source", "manual"),
            target_scope=d.get("target_scope", TargetScope.COMPANY.value),
            target_key=d.get("target_key"),
            category=d.get("category", "external_research"),
            title=d.get("title", ""),
            content=d.get("content", ""),
            citations=d.get("citations", []),
            query=d.get("query"),
            status=d.get("status", "pending"),
            reviewed_by=d.get("reviewed_by"),
            reviewed_at=d.get("reviewed_at"),
            review_note=d.get("review_note"),
            promoted_entry_id=d.get("promoted_entry_id"),
        )


class PendingReviewQueue:
    """File-backed queue of entries awaiting analyst approval."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else _DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load_all(self) -> List[PendingEntry]:
        if not self.path.exists():
            return []
        entries: List[PendingEntry] = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(PendingEntry.from_dict(json.loads(line)))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError as e:
            logger.warning("PendingReviewQueue._load_all failed: %s", e)
            return []
        return entries

    def _rewrite_all(self, entries: List[PendingEntry]) -> None:
        tmp = self.path.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
        tmp.replace(self.path)

    # ── Write ────────────────────────────────────────────────────────────────

    def add(
        self,
        *,
        source: str,
        target_scope: TargetScope,
        target_key: Optional[str],
        category: str,
        title: str,
        content: str,
        citations: Optional[List[Dict[str, str]]] = None,
        query: Optional[str] = None,
    ) -> PendingEntry:
        """Create a new pending entry and append to disk."""
        # Validate target_scope / target_key consistency
        scope = TargetScope(target_scope) if isinstance(target_scope, str) else target_scope
        if scope == TargetScope.COMPANY and not target_key:
            raise ValueError("target_scope=company requires target_key (company name)")
        if scope == TargetScope.ASSET_CLASS and not target_key:
            raise ValueError("target_scope=asset_class requires target_key (analysis_type)")
        if scope == TargetScope.MASTER and target_key is not None:
            raise ValueError("target_scope=master must have target_key=None")

        entry = PendingEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            target_scope=scope.value,
            target_key=target_key,
            category=category,
            title=title,
            content=content,
            citations=citations or [],
            query=query,
        )
        # Append-only
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry

    # ── Read ─────────────────────────────────────────────────────────────────

    def list(
        self,
        status: Optional[str] = "pending",
        target_scope: Optional[str] = None,
        target_key: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[PendingEntry]:
        """List entries, newest first. Pass status=None to get all statuses."""
        entries = self._load_all()
        if status is not None:
            entries = [e for e in entries if e.status == status]
        if target_scope is not None:
            entries = [e for e in entries if e.target_scope == target_scope]
        if target_key is not None:
            entries = [e for e in entries if e.target_key == target_key]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        if limit is not None:
            entries = entries[:limit]
        return entries

    def get(self, entry_id: str) -> Optional[PendingEntry]:
        for e in self._load_all():
            if e.id == entry_id:
                return e
        return None

    def counts(self) -> Dict[str, int]:
        """Count entries by status."""
        entries = self._load_all()
        out = {"pending": 0, "approved": 0, "rejected": 0, "total": len(entries)}
        for e in entries:
            if e.status in out:
                out[e.status] += 1
        return out

    # ── Approve / Reject ─────────────────────────────────────────────────────

    def approve(
        self,
        entry_id: str,
        reviewed_by: Optional[str] = None,
        review_note: Optional[str] = None,
    ) -> PendingEntry:
        """Mark entry approved and promote it to its target mind.

        Returns the updated PendingEntry with promoted_entry_id set.
        Raises ValueError if not found or not in 'pending' status.
        """
        entries = self._load_all()
        target = next((e for e in entries if e.id == entry_id), None)
        if target is None:
            raise ValueError(f"Pending entry not found: {entry_id}")
        if target.status != "pending":
            raise ValueError(f"Entry {entry_id} is not pending (status={target.status})")

        promoted_id = self._promote_to_target(target)

        target.status = "approved"
        target.reviewed_by = reviewed_by
        target.reviewed_at = datetime.now(timezone.utc).isoformat()
        target.review_note = review_note
        target.promoted_entry_id = promoted_id

        self._rewrite_all(entries)
        return target

    def reject(
        self,
        entry_id: str,
        reviewed_by: Optional[str] = None,
        review_note: Optional[str] = None,
    ) -> PendingEntry:
        """Mark entry rejected. Retained in queue for audit trail."""
        entries = self._load_all()
        target = next((e for e in entries if e.id == entry_id), None)
        if target is None:
            raise ValueError(f"Pending entry not found: {entry_id}")
        if target.status != "pending":
            raise ValueError(f"Entry {entry_id} is not pending (status={target.status})")

        target.status = "rejected"
        target.reviewed_by = reviewed_by
        target.reviewed_at = datetime.now(timezone.utc).isoformat()
        target.review_note = review_note
        self._rewrite_all(entries)
        return target

    def _promote_to_target(self, entry: PendingEntry) -> str:
        """Write the approved entry to its target mind store. Returns promoted entry id."""
        metadata: Dict[str, Any] = {
            "source": entry.source,
            "citations": entry.citations,
            "pending_review_id": entry.id,
        }
        if entry.query:
            metadata["query"] = entry.query

        scope = entry.target_scope

        if scope == TargetScope.COMPANY.value:
            from core.mind.company_mind import CompanyMind, _make_entry as _make_company_entry  # noqa
            # target_key is the company name; product is not carried through pending review —
            # promote to the company's default first product's mind dir if we can infer, else
            # fall back to the company-level mind dir directly.
            company = entry.target_key or ""
            mind = CompanyMind(company=company, product="")
            from core.mind.company_mind import MindEntry, _make_entry
            mind_entry = _make_entry(entry.category, entry.content, metadata)
            # CompanyMind uses per-category files; this category must be in _FILES
            # or the record_* methods. For external_research, use the findings category.
            # We bypass the typed record_* methods and write directly via the same
            # mechanism (CompanyMind._jsonl_path + append).
            try:
                # findings is the closest existing category for external knowledge
                cat = entry.category if entry.category in _company_valid_cats() else "findings"
                path = mind._jsonl_path(cat)
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(mind_entry.to_dict(), ensure_ascii=False) + "\n")
                return mind_entry.id
            except Exception as e:
                logger.error("Failed to promote to CompanyMind for %s: %s", company, e)
                raise

        if scope == TargetScope.ASSET_CLASS.value:
            from core.mind.asset_class_mind import AssetClassMind
            mind = AssetClassMind(analysis_type=entry.target_key or "")
            new_entry = mind.record(
                category=entry.category,
                content=entry.content,
                metadata=metadata,
                source=entry.source,
            )
            return new_entry.id

        if scope == TargetScope.MASTER.value:
            from core.mind.master_mind import MasterMind
            master = MasterMind()
            new_entry = master.record(
                category=entry.category,
                content=entry.content,
                metadata=metadata,
            )
            return new_entry.id

        raise ValueError(f"Unknown target_scope: {scope}")


def _company_valid_cats() -> set:
    """Lazy-import the CompanyMind _FILES keys."""
    from core.mind.company_mind import _FILES
    return set(_FILES.keys())


__all__ = ["PendingReviewQueue", "PendingEntry", "TargetScope"]
