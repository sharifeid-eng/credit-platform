"""Tests for core.ai_client — model tier routing, caching helpers, retry wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from core import ai_client


@pytest.fixture(autouse=True)
def reset_client_state():
    """Ensure each test starts with a clean client + resolved-model cache."""
    ai_client.reset_client_for_tests()
    yield
    ai_client.reset_client_for_tests()


# ── Tier resolution ─────────────────────────────────────────────────────────

class TestGetModel:
    def test_all_tiers_return_strings(self):
        for tier in ("auto", "structured", "research", "judgment", "polish"):
            model = ai_client.get_model(tier)
            assert isinstance(model, str)
            assert model  # non-empty

    def test_unknown_tier_falls_back_to_structured(self):
        unknown = ai_client.get_model("totally-made-up")
        structured = ai_client.get_model("structured")
        assert unknown == structured

    def test_tier_is_case_insensitive(self):
        assert ai_client.get_model("STRUCTURED") == ai_client.get_model("structured")
        assert ai_client.get_model("Judgment") == ai_client.get_model("judgment")

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("LAITH_MODEL_JUDGMENT", "my-custom-opus")
        ai_client.reset_client_for_tests()  # flush cache after env change
        assert ai_client.get_model("judgment") == "my-custom-opus"

    def test_resolved_model_is_cached(self):
        a = ai_client.get_model("polish")
        b = ai_client.get_model("polish")
        assert a == b

    def test_mark_unavailable_advances_chain(self):
        first = ai_client.get_model("judgment")
        new_model = ai_client._mark_unavailable("judgment", first)
        assert new_model is not None
        assert new_model != first
        # Subsequent get_model returns the new one
        assert ai_client.get_model("judgment") == new_model

    def test_mark_unavailable_returns_none_when_exhausted(self):
        tier = "judgment"
        # Walk the whole chain
        model = ai_client.get_model(tier)
        while True:
            next_model = ai_client._mark_unavailable(tier, model)
            if next_model is None:
                break
            model = next_model
        # Now exhausted — one more mark_unavailable returns None
        assert ai_client._mark_unavailable(tier, model) is None


# ── Caching helpers ─────────────────────────────────────────────────────────

class TestCacheHelpers:
    def test_system_with_cache_wraps_string(self):
        out = ai_client.system_with_cache("hello")
        assert isinstance(out, list)
        assert out[0]["type"] == "text"
        assert out[0]["text"] == "hello"
        assert out[0]["cache_control"] == {"type": "ephemeral"}

    def test_cache_last_tool_marks_only_last(self):
        tools = [{"name": "a", "input_schema": {}},
                 {"name": "b", "input_schema": {}}]
        out = ai_client.cache_last_tool(tools)
        assert "cache_control" not in out[0]
        assert out[-1]["cache_control"] == {"type": "ephemeral"}
        # Original list untouched
        assert "cache_control" not in tools[-1]

    def test_cache_last_tool_empty_list(self):
        assert ai_client.cache_last_tool([]) == []


# ── Cost estimation ─────────────────────────────────────────────────────────

class TestCostEstimate:
    def test_zero_tokens_zero_cost(self):
        assert ai_client.estimate_cost("claude-sonnet-4-6", 0, 0) == 0.0

    def test_cache_read_discount(self):
        # No cache
        full = ai_client.estimate_cost("claude-sonnet-4-6", 10000, 0)
        # 100% cache hit — should be much cheaper
        cached = ai_client.estimate_cost("claude-sonnet-4-6", 10000, 0, cache_read_tokens=10000)
        assert cached < full
        assert cached > 0  # still pays 10% of input price on cache

    def test_unknown_model_uses_sonnet_default(self):
        cost = ai_client.estimate_cost("unknown-model-xyz", 1_000_000, 1_000_000)
        # Should not throw; should match sonnet pricing (3 + 15 = 18)
        assert cost == pytest.approx(18.0, abs=0.01)


# ── complete() wrapper (mocked) ─────────────────────────────────────────────

class TestComplete:
    def _fake_response(self, input_tokens=100, output_tokens=50, cache_read=0):
        """Build a mock Anthropic response object."""
        resp = MagicMock()
        resp.content = [MagicMock(text="hello world")]
        resp.usage = MagicMock(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=0,
        )
        return resp

    def test_drops_empty_system_string(self):
        """Empty system should not be sent to API (Anthropic rejects it)."""
        fake_client = MagicMock()
        fake_client.messages.create.return_value = self._fake_response()
        with patch("core.ai_client.get_client", return_value=fake_client):
            ai_client.complete(
                tier="structured", system="",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            )
        kwargs = fake_client.messages.create.call_args.kwargs
        assert "system" not in kwargs

    def test_wraps_string_system_with_cache_control(self):
        fake_client = MagicMock()
        fake_client.messages.create.return_value = self._fake_response()
        with patch("core.ai_client.get_client", return_value=fake_client):
            ai_client.complete(
                tier="structured", system="You are a helper.",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            )
        kwargs = fake_client.messages.create.call_args.kwargs
        assert kwargs["system"][0]["text"] == "You are a helper."
        assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_passes_through_tier_model(self):
        fake_client = MagicMock()
        fake_client.messages.create.return_value = self._fake_response()
        with patch("core.ai_client.get_client", return_value=fake_client):
            ai_client.complete(
                tier="polish", system="",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            )
        kwargs = fake_client.messages.create.call_args.kwargs
        assert kwargs["model"] == ai_client.get_model("polish")

    def test_falls_back_on_notfound_error(self):
        """If first model returns NotFoundError, client should retry with next in chain."""
        import anthropic
        fake_client = MagicMock()
        good_response = self._fake_response()
        fake_client.messages.create.side_effect = [
            anthropic.NotFoundError(
                message="not found",
                response=MagicMock(status_code=404),
                body=None,
            ),
            good_response,
        ]
        with patch("core.ai_client.get_client", return_value=fake_client):
            resp = ai_client.complete(
                tier="judgment", system="",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            )
        assert resp is good_response
        assert fake_client.messages.create.call_count == 2
        # Second call used a different model
        first_model = fake_client.messages.create.call_args_list[0].kwargs["model"]
        second_model = fake_client.messages.create.call_args_list[1].kwargs["model"]
        assert first_model != second_model

    def test_strips_temperature_for_polish_tier(self):
        """Polish tier routes to Opus 4.7 which rejects `temperature`; strip silently."""
        fake_client = MagicMock()
        fake_client.messages.create.return_value = self._fake_response()
        with patch("core.ai_client.get_client", return_value=fake_client):
            ai_client.complete(
                tier="polish", system="",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.5,
            )
        kwargs = fake_client.messages.create.call_args.kwargs
        assert "temperature" not in kwargs, (
            "Polish tier must not pass `temperature` — Opus 4.7 rejects it"
        )

    def test_strips_temperature_for_judgment_tier(self):
        """Judgment tier uses the same Opus chain as polish."""
        fake_client = MagicMock()
        fake_client.messages.create.return_value = self._fake_response()
        with patch("core.ai_client.get_client", return_value=fake_client):
            ai_client.complete(
                tier="judgment", system="",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.5,
            )
        kwargs = fake_client.messages.create.call_args.kwargs
        assert "temperature" not in kwargs

    def test_keeps_temperature_for_structured_tier(self):
        """Sonnet still accepts temperature — don't strip it."""
        fake_client = MagicMock()
        fake_client.messages.create.return_value = self._fake_response()
        with patch("core.ai_client.get_client", return_value=fake_client):
            ai_client.complete(
                tier="structured", system="",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                temperature=0.1,
            )
        kwargs = fake_client.messages.create.call_args.kwargs
        assert kwargs.get("temperature") == 0.1

    def test_attaches_metadata(self):
        fake_client = MagicMock()
        fake_client.messages.create.return_value = self._fake_response(
            input_tokens=500, output_tokens=200, cache_read=100,
        )
        with patch("core.ai_client.get_client", return_value=fake_client):
            resp = ai_client.complete(
                tier="structured", system="",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
            )
        meta = getattr(resp, "_laith_metadata", None)
        assert meta is not None
        assert meta["tier"] == "structured"
        assert meta["cache_read_tokens"] == 100
        assert meta["elapsed_s"] >= 0
