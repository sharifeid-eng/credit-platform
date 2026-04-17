"""
Agent Rate Limiting — in-memory rate limiter for agent endpoints.

Enforces:
- Max sessions per user per hour (default 20)
- Max concurrent SSE streams per user (default 5)
- Max tokens per user per day (default 500,000)

All limits are configurable via environment variables.
In-memory tracking (resets on server restart) — suitable for single-server deployment.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Configurable limits
MAX_SESSIONS_PER_USER_PER_HOUR = int(os.getenv("AGENT_MAX_SESSIONS_PER_USER", "20"))
MAX_CONCURRENT_STREAMS_PER_USER = int(os.getenv("AGENT_MAX_CONCURRENT_STREAMS", "5"))
MAX_TOKENS_PER_USER_PER_DAY = int(os.getenv("AGENT_MAX_TOKENS_PER_DAY", "500000"))

# 6-hour cooldown for compliance agent per company (unless forced)
COMPLIANCE_COOLDOWN_SECONDS = 6 * 3600


@dataclass
class UserBucket:
    """Track rate limit state for a single user."""

    sessions_this_hour: int = 0
    hour_start: float = 0.0
    active_streams: int = 0
    tokens_today: int = 0
    day_start: float = 0.0


@dataclass
class ComplianceBucket:
    """Track compliance run cooldown per company."""

    last_run: float = 0.0


class AgentRateLimiter:
    """In-memory rate limiter for agent endpoints."""

    def __init__(self):
        self._lock = Lock()
        self._users: Dict[str, UserBucket] = defaultdict(UserBucket)
        self._compliance: Dict[str, ComplianceBucket] = defaultdict(ComplianceBucket)

    def _get_user_key(self, request) -> str:
        """Extract user identifier from request.

        Uses Cloudflare Access email if available, falls back to IP.
        """
        # Try CF Access user email from request state (set by auth middleware)
        user = getattr(request, "state", None)
        if user and hasattr(user, "user"):
            u = user.user
            if hasattr(u, "email") and u.email:
                return u.email

        # Fallback to IP
        client = getattr(request, "client", None)
        if client and hasattr(client, "host"):
            return client.host
        return "unknown"

    def check_session_limit(self, request) -> Optional[str]:
        """Check if user can start a new session. Returns error message or None."""
        key = self._get_user_key(request)
        now = time.time()

        with self._lock:
            bucket = self._users[key]

            # Reset hourly counter
            if now - bucket.hour_start > 3600:
                bucket.sessions_this_hour = 0
                bucket.hour_start = now

            if bucket.sessions_this_hour >= MAX_SESSIONS_PER_USER_PER_HOUR:
                return f"Rate limit: max {MAX_SESSIONS_PER_USER_PER_HOUR} agent sessions per hour"

            bucket.sessions_this_hour += 1
        return None

    def check_concurrent_limit(self, request) -> Optional[str]:
        """Check if user can start a new stream. Returns error message or None."""
        key = self._get_user_key(request)

        with self._lock:
            bucket = self._users[key]
            if bucket.active_streams >= MAX_CONCURRENT_STREAMS_PER_USER:
                return f"Rate limit: max {MAX_CONCURRENT_STREAMS_PER_USER} concurrent agent streams"
        return None

    def stream_started(self, request) -> None:
        """Increment active stream count."""
        key = self._get_user_key(request)
        with self._lock:
            self._users[key].active_streams += 1

    def stream_ended(self, request) -> None:
        """Decrement active stream count."""
        key = self._get_user_key(request)
        with self._lock:
            bucket = self._users[key]
            bucket.active_streams = max(0, bucket.active_streams - 1)

    def check_token_limit(self, request) -> Optional[str]:
        """Check if user has daily token budget remaining. Returns error message or None."""
        key = self._get_user_key(request)
        now = time.time()

        with self._lock:
            bucket = self._users[key]

            # Reset daily counter
            if now - bucket.day_start > 86400:
                bucket.tokens_today = 0
                bucket.day_start = now

            if bucket.tokens_today >= MAX_TOKENS_PER_USER_PER_DAY:
                return f"Rate limit: daily token budget exhausted ({MAX_TOKENS_PER_USER_PER_DAY:,} tokens/day)"
        return None

    def record_tokens(self, request, tokens: int) -> None:
        """Record token usage for a user."""
        key = self._get_user_key(request)
        with self._lock:
            self._users[key].tokens_today += tokens

    def check_compliance_cooldown(self, company: str, product: str, force: bool = False) -> Optional[str]:
        """Check compliance agent cooldown. Returns error or None."""
        if force:
            return None

        key = f"{company}/{product}"
        now = time.time()

        with self._lock:
            bucket = self._compliance[key]
            elapsed = now - bucket.last_run
            if elapsed < COMPLIANCE_COOLDOWN_SECONDS:
                remaining_min = int((COMPLIANCE_COOLDOWN_SECONDS - elapsed) / 60)
                return f"Compliance check ran {int(elapsed/60)}m ago. Cooldown: {remaining_min}m remaining. Add force=true to override."
        return None

    def record_compliance_run(self, company: str, product: str) -> None:
        """Record that a compliance check was run."""
        key = f"{company}/{product}"
        with self._lock:
            self._compliance[key].last_run = time.time()

    def get_user_stats(self, request) -> Dict:
        """Get rate limit stats for a user (for debugging/UI)."""
        key = self._get_user_key(request)
        with self._lock:
            bucket = self._users[key]
            return {
                "user": key,
                "sessions_this_hour": bucket.sessions_this_hour,
                "active_streams": bucket.active_streams,
                "tokens_today": bucket.tokens_today,
                "limits": {
                    "max_sessions_per_hour": MAX_SESSIONS_PER_USER_PER_HOUR,
                    "max_concurrent_streams": MAX_CONCURRENT_STREAMS_PER_USER,
                    "max_tokens_per_day": MAX_TOKENS_PER_USER_PER_DAY,
                },
            }


# Global singleton
rate_limiter = AgentRateLimiter()
