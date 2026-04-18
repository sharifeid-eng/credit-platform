"""
Central Anthropic API client — model tier routing, retry/backoff, prompt caching.

All AI calls across the platform should go through `complete()` or `get_client()`
here instead of instantiating `anthropic.Anthropic()` directly. This ensures:

- Consistent retry/backoff on RateLimitError (SDK built-in, max_retries=3)
- Tier-based model selection (auto/structured/research/judgment/polish)
- Per-tier env var overrides (LAITH_MODEL_*)
- Structured logging of token usage + cache hits
- Graceful fallback when a preferred model ID isn't available

Tiers:
  auto       → Haiku 4     : trivial, templated content (appendix, data sources)
  structured → Sonnet 4.6  : analytics / data-room sections (portfolio, covenants)
  research   → Sonnet 4.6  : short-burst agent research packs
  judgment   → Opus 4.7    : exec summary, investment thesis, recommendation
  polish     → Opus 4.7    : final whole-memo coherence pass

Opus 4.7 falls back to 4.6 automatically if the model ID isn't recognised.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

import anthropic

logger = logging.getLogger(__name__)

# ── Model tier resolution ────────────────────────────────────────────────────

# Preferred model IDs per tier. If the primary is unavailable, fall through
# the fallback list until we find one that works.
_MODEL_FALLBACK_CHAINS: Dict[str, List[str]] = {
    "auto":       ["claude-haiku-4-5", "claude-haiku-4", "claude-haiku-3-5-20241022"],
    "structured": ["claude-sonnet-4-6", "claude-sonnet-4-20250514"],
    "research":   ["claude-sonnet-4-6", "claude-sonnet-4-20250514"],
    "judgment":   ["claude-opus-4-7", "claude-opus-4-6", "claude-opus-4-20250514"],
    "polish":     ["claude-opus-4-7", "claude-opus-4-6", "claude-opus-4-20250514"],
}

# Env var mapping per tier — user can override any tier globally
_TIER_ENV_VARS = {
    "auto":       "LAITH_MODEL_AUTO",
    "structured": "LAITH_MODEL_STRUCTURED",
    "research":   "LAITH_MODEL_RESEARCH",
    "judgment":   "LAITH_MODEL_JUDGMENT",
    "polish":     "LAITH_MODEL_POLISH",
}

# Resolved model IDs cached after first successful use per tier
_RESOLVED_MODELS: Dict[str, str] = {}

# Tiers whose underlying models reject the `temperature` kwarg (Opus 4.7-era
# models deprecated it). `complete()` silently strips temperature for these
# tiers so callers can keep passing it without hitting 400 errors.
_STRIPS_TEMPERATURE_TIERS = {"polish", "judgment"}


def get_model(tier: str) -> str:
    """Resolve a tier name to an actual model ID.

    Checks env var override first, then walks the fallback chain.
    Caches the result per tier after first resolution.

    Unknown tiers fall back to 'structured'.
    """
    tier = tier.lower()
    if tier not in _MODEL_FALLBACK_CHAINS:
        logger.warning("Unknown model tier '%s', falling back to 'structured'", tier)
        tier = "structured"

    if tier in _RESOLVED_MODELS:
        return _RESOLVED_MODELS[tier]

    # Env var override wins
    env_var = _TIER_ENV_VARS.get(tier)
    if env_var:
        override = os.getenv(env_var)
        if override:
            _RESOLVED_MODELS[tier] = override
            logger.info("Tier '%s' -> '%s' (from %s)", tier, override, env_var)
            return override

    # Use primary from fallback chain; actual availability check happens
    # at call time via AnthropicNotFoundError catch. First primary is our best guess.
    chain = _MODEL_FALLBACK_CHAINS[tier]
    primary = chain[0]
    _RESOLVED_MODELS[tier] = primary
    logger.debug("Tier '%s' -> '%s' (primary)", tier, primary)
    return primary


def _mark_unavailable(tier: str, model_id: str) -> Optional[str]:
    """Advance a tier's resolved model to the next fallback after a 404/NotFound.

    Returns the new model ID, or None if chain exhausted.
    """
    chain = _MODEL_FALLBACK_CHAINS.get(tier, [])
    try:
        idx = chain.index(model_id)
    except ValueError:
        return None
    for candidate in chain[idx + 1:]:
        _RESOLVED_MODELS[tier] = candidate
        logger.warning("Model '%s' unavailable for tier '%s'; falling back to '%s'",
                       model_id, tier, candidate)
        return candidate
    return None


# ── Client singleton ────────────────────────────────────────────────────────

_CLIENT_SINGLETON: Optional[anthropic.Anthropic] = None


def _load_api_key() -> Optional[str]:
    """Load ANTHROPIC_API_KEY with dotenv override (worktrees don't inherit it)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


def get_client() -> anthropic.Anthropic:
    """Return a process-singleton Anthropic client with retry configured.

    `max_retries` is read from LAITH_AI_MAX_RETRIES (default 3). The SDK
    handles exponential backoff automatically on 429 / 529 / 503.
    """
    global _CLIENT_SINGLETON
    if _CLIENT_SINGLETON is not None:
        return _CLIENT_SINGLETON

    api_key = _load_api_key()
    max_retries = int(os.getenv("LAITH_AI_MAX_RETRIES", "3"))
    _CLIENT_SINGLETON = anthropic.Anthropic(
        api_key=api_key,
        max_retries=max_retries,
    )
    logger.info("Anthropic client initialized (max_retries=%d)", max_retries)
    return _CLIENT_SINGLETON


def reset_client_for_tests() -> None:
    """Reset singleton. Used by test fixtures that need a fresh client."""
    global _CLIENT_SINGLETON
    _CLIENT_SINGLETON = None
    _RESOLVED_MODELS.clear()


# ── Prompt caching helpers ──────────────────────────────────────────────────

def system_with_cache(text: str) -> List[Dict[str, Any]]:
    """Wrap a system prompt string as a cache-eligible content block list."""
    return [{
        "type": "text",
        "text": text,
        "cache_control": {"type": "ephemeral"},
    }]


def cache_last_tool(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mark the last tool with cache_control so the whole tools prefix caches.

    Anthropic honors a cache breakpoint on the tools param: marking the last
    tool causes the entire tool schema block to be cached. Returns a new list;
    does not mutate the input.
    """
    if not tools:
        return tools
    out = [dict(t) for t in tools]
    # Anthropic cache_control on a tool goes alongside its schema
    out[-1] = {**out[-1], "cache_control": {"type": "ephemeral"}}
    return out


# ── Completion wrapper ──────────────────────────────────────────────────────

def complete(
    *,
    tier: str,
    system: Union[str, List[Dict[str, Any]]],
    messages: List[Dict[str, Any]],
    max_tokens: int = 2000,
    temperature: float = 0.3,
    tools: Optional[List[Dict[str, Any]]] = None,
    cache_tools: bool = False,
    log_prefix: str = "",
    **extra: Any,
) -> anthropic.types.Message:
    """Send a messages.create call for the given tier with retry + logging.

    Returns the raw SDK Message object (caller inspects .content, .usage, etc).

    Args:
        tier: Model tier — "auto" | "structured" | "research" | "judgment" | "polish"
        system: System prompt as string or content block list (use system_with_cache)
        messages: Anthropic message list
        max_tokens: Max output tokens
        temperature: Sampling temperature
        tools: Optional list of tool schemas
        cache_tools: If True, add cache_control to last tool (cache the schema prefix)
        log_prefix: Optional string prefixed to the "AI call" log line for traceability
        **extra: Passed through to messages.create

    Raises:
        anthropic.APIError on non-retryable errors (SDK already retried 429/529).
    """
    client = get_client()
    model = get_model(tier)

    # Auto-wrap bare string system prompts with cache control — cheap win.
    # Empty strings are dropped entirely (some call sites have no system prompt).
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    # Some tiers route to models that reject `temperature` (Opus 4.7-era).
    # Strip silently rather than 400ing — deterministic output isn't meaningful
    # on those models anyway. Preserves legacy callers that always pass it.
    if tier.lower() in _STRIPS_TEMPERATURE_TIERS:
        logger.debug("Stripping temperature kwarg for tier '%s' (model rejects it)", tier)
    else:
        kwargs["temperature"] = temperature
    if isinstance(system, str):
        if system.strip():
            kwargs["system"] = system_with_cache(system)
    elif system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = cache_last_tool(tools) if cache_tools else tools
    kwargs.update(extra)

    start = time.time()
    try:
        resp = client.messages.create(**kwargs)
    except anthropic.NotFoundError as e:
        # Model not available — walk the fallback chain
        new_model = _mark_unavailable(tier, model)
        if new_model is None:
            logger.error("No available models for tier '%s' (all fallbacks exhausted)", tier)
            raise
        kwargs["model"] = new_model
        resp = client.messages.create(**kwargs)
        model = new_model

    elapsed = time.time() - start
    usage = resp.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_created = getattr(usage, "cache_creation_input_tokens", 0) or 0

    logger.info(
        "%sAI call [tier=%s model=%s] in=%d out=%d cache_read=%d cache_created=%d elapsed=%.1fs",
        (log_prefix + " ") if log_prefix else "",
        tier, model,
        usage.input_tokens, usage.output_tokens,
        cache_read, cache_created, elapsed,
    )

    # Attach resolved metadata to resp for callers that want to record it
    try:
        resp._laith_metadata = {
            "tier": tier,
            "model": model,
            "elapsed_s": elapsed,
            "cache_read_tokens": cache_read,
            "cache_created_tokens": cache_created,
        }
    except Exception:
        pass  # Pydantic models may be frozen — non-fatal

    return resp


# ── Cost estimation (rough guidance, not billing) ───────────────────────────

# USD per 1M tokens (input, output). Cache hits priced at 10% of input.
# Update when pricing changes; these are estimates for logging only.
_PRICE_PER_M_TOKENS = {
    "claude-haiku-4-5":           (0.80, 4.00),
    "claude-haiku-4":             (0.80, 4.00),
    "claude-haiku-3-5-20241022":  (1.00, 5.00),
    "claude-sonnet-4-6":          (3.00, 15.00),
    "claude-sonnet-4-20250514":   (3.00, 15.00),
    "claude-opus-4-6":            (15.00, 75.00),
    "claude-opus-4-7":            (15.00, 75.00),
    "claude-opus-4-20250514":     (15.00, 75.00),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int,
                  cache_read_tokens: int = 0) -> float:
    """Rough USD cost estimate for a call. Cache reads priced at 10% of input."""
    prices = _PRICE_PER_M_TOKENS.get(model, (3.00, 15.00))  # default sonnet pricing
    in_price, out_price = prices
    billable_input = max(input_tokens - cache_read_tokens, 0)
    cache_cost = cache_read_tokens * in_price * 0.10 / 1_000_000
    input_cost = billable_input * in_price / 1_000_000
    output_cost = output_tokens * out_price / 1_000_000
    return round(input_cost + output_cost + cache_cost, 4)
