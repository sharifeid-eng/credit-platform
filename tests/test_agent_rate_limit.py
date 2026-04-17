"""
Tests for Agent Rate Limiting.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agents.rate_limit import AgentRateLimiter


def _mock_request(email="test@example.com"):
    """Create a mock request with user email."""
    req = MagicMock()
    req.state.user.email = email
    req.client.host = "127.0.0.1"
    return req


class TestSessionLimits:
    def test_allows_within_limit(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        for _ in range(5):
            assert limiter.check_session_limit(req) is None

    def test_blocks_over_limit(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        with patch("core.agents.rate_limit.MAX_SESSIONS_PER_USER_PER_HOUR", 3):
            limiter2 = AgentRateLimiter()
            for _ in range(3):
                assert limiter2.check_session_limit(req) is None
            assert limiter2.check_session_limit(req) is not None

    def test_resets_after_hour(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        # Fill up the bucket
        with patch("core.agents.rate_limit.MAX_SESSIONS_PER_USER_PER_HOUR", 2):
            limiter2 = AgentRateLimiter()
            limiter2.check_session_limit(req)
            limiter2.check_session_limit(req)
            assert limiter2.check_session_limit(req) is not None

            # Simulate hour passing
            limiter2._users["test@example.com"].hour_start = time.time() - 3601
            assert limiter2.check_session_limit(req) is None


class TestConcurrentLimits:
    def test_allows_within_limit(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        assert limiter.check_concurrent_limit(req) is None

    def test_blocks_over_limit(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        with patch("core.agents.rate_limit.MAX_CONCURRENT_STREAMS_PER_USER", 2):
            limiter2 = AgentRateLimiter()
            limiter2.stream_started(req)
            limiter2.stream_started(req)
            assert limiter2.check_concurrent_limit(req) is not None

    def test_allows_after_stream_ends(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        with patch("core.agents.rate_limit.MAX_CONCURRENT_STREAMS_PER_USER", 1):
            limiter2 = AgentRateLimiter()
            limiter2.stream_started(req)
            assert limiter2.check_concurrent_limit(req) is not None
            limiter2.stream_ended(req)
            assert limiter2.check_concurrent_limit(req) is None


class TestTokenLimits:
    def test_allows_within_budget(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        assert limiter.check_token_limit(req) is None

    @patch("core.agents.rate_limit.MAX_TOKENS_PER_USER_PER_DAY", 100)
    def test_blocks_over_budget(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        # First call initializes the bucket (resets day_start)
        limiter.check_token_limit(req)
        limiter.record_tokens(req, 50)
        assert limiter.check_token_limit(req) is None
        limiter.record_tokens(req, 60)
        assert limiter.check_token_limit(req) is not None

    @patch("core.agents.rate_limit.MAX_TOKENS_PER_USER_PER_DAY", 100)
    def test_resets_after_day(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        # Initialize bucket
        limiter.check_token_limit(req)
        limiter.record_tokens(req, 200)
        assert limiter.check_token_limit(req) is not None
        # Simulate day passing
        limiter._users["test@example.com"].day_start = time.time() - 86401
        assert limiter.check_token_limit(req) is None


class TestComplianceCooldown:
    def test_first_run_allowed(self):
        limiter = AgentRateLimiter()
        assert limiter.check_compliance_cooldown("klaim", "UAE_healthcare") is None

    def test_second_run_blocked(self):
        limiter = AgentRateLimiter()
        limiter.record_compliance_run("klaim", "UAE_healthcare")
        assert limiter.check_compliance_cooldown("klaim", "UAE_healthcare") is not None

    def test_force_overrides_cooldown(self):
        limiter = AgentRateLimiter()
        limiter.record_compliance_run("klaim", "UAE_healthcare")
        assert limiter.check_compliance_cooldown("klaim", "UAE_healthcare", force=True) is None

    def test_different_company_not_affected(self):
        limiter = AgentRateLimiter()
        limiter.record_compliance_run("klaim", "UAE_healthcare")
        assert limiter.check_compliance_cooldown("SILQ", "KSA") is None


class TestUserStats:
    def test_returns_stats(self):
        limiter = AgentRateLimiter()
        req = _mock_request()
        limiter.check_session_limit(req)
        limiter.record_tokens(req, 500)

        stats = limiter.get_user_stats(req)
        assert stats["user"] == "test@example.com"
        assert stats["sessions_this_hour"] == 1
        assert stats["tokens_today"] == 500
        assert "limits" in stats


class TestUserKeyExtraction:
    def test_uses_email_when_available(self):
        limiter = AgentRateLimiter()
        req = _mock_request("analyst@fund.com")
        key = limiter._get_user_key(req)
        assert key == "analyst@fund.com"

    def test_falls_back_to_ip(self):
        limiter = AgentRateLimiter()
        req = MagicMock()
        req.state = MagicMock(spec=[])  # No .user attribute
        req.client.host = "192.168.1.1"
        key = limiter._get_user_key(req)
        assert key == "192.168.1.1"

    def test_different_users_independent(self):
        limiter = AgentRateLimiter()
        req1 = _mock_request("user1@test.com")
        req2 = _mock_request("user2@test.com")
        limiter.record_tokens(req1, 1000)
        stats2 = limiter.get_user_stats(req2)
        assert stats2["tokens_today"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
