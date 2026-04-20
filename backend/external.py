"""External Intelligence API — pending review + asset class mind endpoints.

Routes (all under /api/):
  GET    /api/pending-review              list pending entries
  GET    /api/pending-review/counts       status counts
  GET    /api/pending-review/{id}         get one entry
  POST   /api/pending-review              create (agent-only — usually via web_search tool)
  POST   /api/pending-review/{id}/approve promote to target mind
  POST   /api/pending-review/{id}/reject  mark rejected (retains in queue for audit)

  GET    /api/asset-class-mind            list all populated asset classes
  GET    /api/asset-class-mind/{analysis_type}            list entries
  POST   /api/asset-class-mind/{analysis_type}/entries    record manual entry
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.activity_log import log_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["external"])


# ── Pydantic request models ──────────────────────────────────────────────────

class PendingReviewCreate(BaseModel):
    source: str = "manual"
    target_scope: str  # "company" | "asset_class" | "master"
    target_key: Optional[str] = None
    category: str
    title: str
    content: str
    citations: List[Dict[str, str]] = []
    query: Optional[str] = None


class ReviewDecision(BaseModel):
    reviewed_by: Optional[str] = None
    review_note: Optional[str] = None


class AssetClassEntryCreate(BaseModel):
    category: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


# ── Pending Review ───────────────────────────────────────────────────────────

@router.get("/pending-review")
def list_pending_review(
    status: Optional[str] = Query("pending"),
    target_scope: Optional[str] = None,
    target_key: Optional[str] = None,
    limit: Optional[int] = Query(None, ge=1, le=500),
):
    """List pending review entries. Default = pending-only, newest first."""
    from core.external.pending_review import PendingReviewQueue

    queue = PendingReviewQueue()
    # Pass status=None to return all statuses
    status_filter = None if status == "all" else status
    entries = queue.list(
        status=status_filter,
        target_scope=target_scope,
        target_key=target_key,
        limit=limit,
    )
    return {
        "entries": [e.to_dict() for e in entries],
        "total": len(entries),
        "counts": queue.counts(),
    }


@router.get("/pending-review/counts")
def pending_review_counts():
    """Status count breakdown."""
    from core.external.pending_review import PendingReviewQueue
    return PendingReviewQueue().counts()


@router.get("/pending-review/{entry_id}")
def get_pending_entry(entry_id: str):
    from core.external.pending_review import PendingReviewQueue

    entry = PendingReviewQueue().get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Pending entry not found")
    return entry.to_dict()


@router.post("/pending-review")
def create_pending_entry(body: PendingReviewCreate):
    """Create a pending-review entry manually.

    Usually the web_search agent tool produces these automatically. This
    endpoint exists for manual insertion (e.g. analyst paste-in from a
    report) and for testing.
    """
    from core.external.pending_review import PendingReviewQueue, TargetScope

    try:
        queue = PendingReviewQueue()
        entry = queue.add(
            source=body.source,
            target_scope=TargetScope(body.target_scope),
            target_key=body.target_key,
            category=body.category,
            title=body.title,
            content=body.content,
            citations=body.citations,
            query=body.query,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_activity("pending_review_created", None, None,
                 f"{body.target_scope}/{body.target_key or ''} · {body.category} · {body.title[:80]}")
    return entry.to_dict()


@router.post("/pending-review/{entry_id}/approve")
def approve_pending_entry(entry_id: str, body: ReviewDecision):
    """Approve: promotes the entry to its target mind store."""
    from core.external.pending_review import PendingReviewQueue

    try:
        queue = PendingReviewQueue()
        updated = queue.approve(
            entry_id,
            reviewed_by=body.reviewed_by,
            review_note=body.review_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Approval failed")
        raise HTTPException(status_code=500, detail=f"Approval failed: {e}")

    log_activity("pending_review_approved", None, None,
                 f"{updated.target_scope}/{updated.target_key or ''} · {updated.title[:80]}")
    return updated.to_dict()


@router.post("/pending-review/{entry_id}/reject")
def reject_pending_entry(entry_id: str, body: ReviewDecision):
    from core.external.pending_review import PendingReviewQueue

    try:
        queue = PendingReviewQueue()
        updated = queue.reject(
            entry_id,
            reviewed_by=body.reviewed_by,
            review_note=body.review_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_activity("pending_review_rejected", None, None,
                 f"{updated.target_scope}/{updated.target_key or ''} · {updated.title[:80]}")
    return updated.to_dict()


# ── Asset Class Mind ─────────────────────────────────────────────────────────

@router.get("/asset-class-mind")
def list_asset_classes():
    """List every asset class that has a non-empty JSONL file."""
    from core.mind.asset_class_mind import list_all_asset_classes

    classes = list_all_asset_classes()
    return {"asset_classes": classes, "total": len(classes)}


@router.get("/asset-class-mind/{analysis_type}")
def list_asset_class_entries(
    analysis_type: str,
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """List entries for a specific asset class, newest first."""
    from core.mind.asset_class_mind import AssetClassMind

    try:
        mind = AssetClassMind(analysis_type)
        entries = mind.list_entries(category=category, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "analysis_type": analysis_type,
        "entries": [e.to_dict() for e in entries],
        "total": len(entries),
    }


@router.post("/asset-class-mind/{analysis_type}/entries")
def create_asset_class_entry(analysis_type: str, body: AssetClassEntryCreate):
    """Manually record an asset class mind entry.

    Bypasses the pending-review queue — for analyst-authored entries that
    don't need external-source approval. External-origin entries should
    always flow through pending-review.
    """
    from core.mind.asset_class_mind import AssetClassMind

    try:
        mind = AssetClassMind(analysis_type)
        entry = mind.record(
            category=body.category,
            content=body.content,
            metadata=body.metadata,
            source="manual",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_activity("asset_class_mind_recorded", None, None,
                 f"{analysis_type} · {body.category}")
    return entry.to_dict()
