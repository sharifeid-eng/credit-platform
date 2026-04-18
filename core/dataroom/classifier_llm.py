"""
LLM classification fallback for data room documents.

Invoked by ``classify_document()`` only when the rule-based classifier returns
``DocumentType.OTHER``. Uses the Haiku tier via ``core.ai_client.complete()``
— cheap (~$0.001/doc), fast, and accurate enough that ~27/40 SILQ files
incorrectly labelled "other" by filename regex should come back classified.

Design constraints:
- **sha256-keyed cache** at ``data/{company}/dataroom/.classification_cache.json``.
  The SAME file never triggers a second LLM call, even across ingests and
  companies. Re-running ``dataroom_ctl classify --only-other`` is free.
- **No hard dependency** on ``core.ai_client``. Import is lazy so the rule-based
  classifier still works on environments without the AI client wired in.
- **Strict JSON output.** We ask Haiku for ``{doc_type, confidence, reasoning}``.
  Parse failures → return ``None`` so the caller can treat as "unknown".
- **Enum discipline.** We send the list of valid ``DocumentType`` values in the
  prompt and validate the response against them in the caller.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .classifier import DocumentType

logger = logging.getLogger("laith.dataroom.classifier_llm")

# One system prompt, one user template. Haiku is fast enough that we don't
# need multi-turn or tool-use for a simple classification task.
_SYSTEM_PROMPT = """You are a document classifier for a private credit fund's data room.

Given a filename, a short text preview, and (for spreadsheets) a list of sheet names,
pick the single best document_type from the provided enum.

Return STRICT JSON only — no prose, no markdown fences. Schema:
  {"doc_type": "<enum_value>", "confidence": 0.0-1.0, "reasoning": "<one sentence>"}

- confidence < 0.6 means you're genuinely uncertain; the caller will mark the
  doc as 'unknown' rather than forcing a guess.
- If nothing fits, return "other" with low confidence."""


def _cache_path(data_root: str, company: str) -> Path:
    d = Path(data_root) / company / "dataroom"
    d.mkdir(parents=True, exist_ok=True)
    return d / ".classification_cache.json"


def _load_cache(data_root: str, company: str) -> dict:
    p = _cache_path(data_root, company)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(data_root: str, company: str, cache: dict) -> None:
    p = _cache_path(data_root, company)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
    except OSError as e:
        logger.warning("[classifier_llm] Failed to write cache: %s", e)


def _build_user_prompt(filepath: str, text_preview: str, sheet_names: list) -> str:
    """Compose the Haiku user message.

    Kept compact: filename + ~1500 chars of text + up to 10 sheet names.
    """
    parts = [f"Filename: {Path(filepath).name}"]

    # Include parent directory as context (data rooms often encode intent in folders)
    parents = list(Path(filepath).parents)
    if len(parents) >= 2:
        parts.append(f"Parent folder: {parents[0].name}")

    if sheet_names:
        parts.append("Excel sheet names: " + ", ".join(str(s) for s in sheet_names[:10]))

    if text_preview:
        parts.append("Text preview:\n" + text_preview[:1500])

    parts.append("")
    parts.append("Valid document_type enum values:")
    parts.append(", ".join(sorted(dt.value for dt in DocumentType)))

    return "\n\n".join(parts)


def classify_with_llm(
    filepath: str,
    text_preview: str = "",
    sheet_names: list | None = None,
    sha256: str = "",
    data_root: str = "",
    company: str = "",
) -> dict | None:
    """Call Haiku to classify a document the rule-based system missed.

    Args:
        filepath: Full path to the document (filename + parents drive classification hints).
        text_preview: First ~1500 characters of extracted text. Empty string if unavailable.
        sheet_names: Excel sheet names (empty for non-spreadsheet files).
        sha256: File hash — used as cache key. Empty string disables caching.
        data_root: Platform data/ root. Empty string disables caching.
        company: Company identifier for per-company cache.

    Returns:
        ``{"doc_type", "confidence", "reasoning", "source": "llm_cache" | "llm"}``
        or ``None`` on any failure (caller treats as "keep as 'other'").
    """
    sheet_names = sheet_names or []

    # Cache check
    cache = {}
    if sha256 and data_root and company:
        cache = _load_cache(data_root, company)
        if sha256 in cache:
            entry = dict(cache[sha256])
            entry["source"] = "llm_cache"
            return entry

    # Lazy import — keep this module importable even if ai_client isn't wired
    try:
        from core.ai_client import complete
    except ImportError:
        logger.warning("[classifier_llm] core.ai_client not available — cannot run LLM fallback")
        return None

    user_prompt = _build_user_prompt(filepath, text_preview, sheet_names)

    try:
        response = complete(
            tier="auto",
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=200,
        )
    except Exception as e:
        logger.warning("[classifier_llm] Haiku call failed: %s", e)
        return None

    # Extract text from response — ai_client.complete is expected to return
    # an Anthropic Message. We read .content[0].text but tolerate a plain
    # string (some wrappers return text directly).
    raw_text = None
    if isinstance(response, str):
        raw_text = response
    else:
        try:
            raw_text = response.content[0].text
        except (AttributeError, IndexError, TypeError):
            logger.warning("[classifier_llm] Unexpected response shape from complete()")
            return None

    # Parse JSON — tolerate stray markdown fences just in case.
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        # Strip ```json ... ``` fences
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("[classifier_llm] Non-JSON response: %r", raw_text[:200])
        return None

    doc_type = parsed.get("doc_type")
    confidence = float(parsed.get("confidence", 0.0) or 0.0)
    reasoning = parsed.get("reasoning", "")

    if not doc_type:
        return None

    result = {
        "doc_type": doc_type,
        "confidence": confidence,
        "reasoning": reasoning[:500],
        "source": "llm",
    }

    # Write-through cache
    if sha256 and data_root and company:
        cache[sha256] = {k: v for k, v in result.items() if k != "source"}
        _save_cache(data_root, company, cache)

    return result
