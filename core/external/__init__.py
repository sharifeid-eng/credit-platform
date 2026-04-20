"""External Intelligence — bring the outside world into the platform.

Two building blocks:
  - pending_review: queue for external-origin entries that need analyst
    approval before promoting to Company / Asset Class / Master mind
  - web_search (agent tool, wired in core/agents/tools/web_search.py):
    Claude's built-in web_search_20250305 tool, with every result landing
    in the pending_review queue (never auto-written to any Mind)

Trust model: external evidence is ALWAYS second-class until an analyst
confirms it. No auto-writes. Citations mandatory.
"""

from core.external.pending_review import (
    PendingReviewQueue,
    PendingEntry,
    TargetScope,
)

__all__ = ["PendingReviewQueue", "PendingEntry", "TargetScope"]
