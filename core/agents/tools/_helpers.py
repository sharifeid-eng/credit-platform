"""
Shared helpers for agent tools.

Wraps core data loading patterns so each tool is self-contained.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Data root
_DATA_DIR = Path("data")


def load_tape(
    company: str,
    product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load a tape snapshot, optionally filtered by date.

    Returns:
        (df, sel) where sel = {filename, filepath, date}
    """
    from core.loader import get_snapshots, load_snapshot
    from core.analysis import filter_by_date

    snaps = get_snapshots(company, product)
    if not snaps:
        raise ValueError(f"No snapshots found for {company}/{product}")

    # Select snapshot
    sel = snaps[-1]  # default: latest
    if snapshot:
        for s in snaps:
            if s["filename"] == snapshot or s.get("date") == snapshot:
                sel = s
                break

    df = load_snapshot(sel["filepath"])
    if as_of_date:
        df = filter_by_date(df, as_of_date)

    return df, sel


def load_silq_tape(
    company: str,
    product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any], Optional[str]]:
    """Load a SILQ multi-sheet tape.

    Returns:
        (df, sel, commentary_text)
    """
    from core.loader import get_snapshots, load_silq_snapshot
    from core.analysis import filter_by_date

    snaps = get_snapshots(company, product)
    if not snaps:
        raise ValueError(f"No snapshots found for {company}/{product}")

    sel = snaps[-1]
    if snapshot:
        for s in snaps:
            if s["filename"] == snapshot or s.get("date") == snapshot:
                sel = s
                break

    df, commentary = load_silq_snapshot(sel["filepath"])
    if as_of_date:
        df = filter_by_date(df, as_of_date)

    return df, sel, commentary


def load_aajil_tape(
    company: str,
    product: str,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
    """Load an Aajil multi-sheet tape.

    Returns:
        (df, sel, aux_data)
    """
    from core.loader import get_snapshots, load_aajil_snapshot
    from core.analysis import filter_by_date

    snaps = get_snapshots(company, product)
    if not snaps:
        raise ValueError(f"No snapshots found for {company}/{product}")

    sel = snaps[-1]
    if snapshot:
        for s in snaps:
            if s["filename"] == snapshot or s.get("date") == snapshot:
                sel = s
                break

    df, aux = load_aajil_snapshot(sel["filepath"])
    if as_of_date:
        df = filter_by_date(df, as_of_date)

    return df, sel, aux


def get_currency(
    company: str,
    product: str,
    requested: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], str, float]:
    """Resolve currency and compute multiplier.

    Returns:
        (config, display_currency, multiplier)
    """
    from core.config import load_config
    from core.analysis import apply_multiplier

    config = load_config(company, product)
    display = requested or (config.get("currency", "USD") if config else "USD")
    mult = apply_multiplier(config, display)
    return config, display, mult


def detect_analysis_type(company: str, product: str) -> str:
    """Detect the analysis type for a company/product."""
    from core.config import load_config

    config = load_config(company, product)
    if config:
        return config.get("analysis_type", "klaim")
    return "klaim"


def format_dict(d: Any, max_depth: int = 2, _depth: int = 0) -> str:
    """Format a dict/value as readable text for agent consumption."""
    if _depth >= max_depth:
        return str(d)

    if isinstance(d, dict):
        lines = []
        for k, v in d.items():
            formatted_v = format_dict(v, max_depth, _depth + 1)
            lines.append(f"  {'  ' * _depth}{k}: {formatted_v}")
        return "\n".join(lines)
    elif isinstance(d, list):
        if not d:
            return "[]"
        if len(d) <= 5:
            items = [format_dict(item, max_depth, _depth + 1) for item in d]
            return "\n".join(f"  {'  ' * _depth}- {item}" for item in items)
        # Truncate long lists
        items = [format_dict(item, max_depth, _depth + 1) for item in d[:5]]
        return "\n".join(f"  {'  ' * _depth}- {item}" for item in items) + f"\n  {'  ' * _depth}... ({len(d)} total)"
    elif isinstance(d, float):
        if abs(d) >= 1_000_000:
            return f"{d:,.0f}"
        elif abs(d) < 0.01 and d != 0:
            return f"{d:.4f}"
        else:
            return f"{d:,.2f}"
    else:
        return str(d)


def format_number(v: Any, is_pct: bool = False, is_currency: bool = False, currency: str = "") -> str:
    """Format a number for human reading."""
    if v is None:
        return "N/A"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)

    if is_pct:
        return f"{v * 100:.1f}%" if abs(v) < 1 else f"{v:.1f}%"
    elif is_currency:
        if abs(v) >= 1_000_000:
            return f"{currency} {v / 1_000_000:,.1f}M"
        elif abs(v) >= 1_000:
            return f"{currency} {v / 1_000:,.0f}K"
        return f"{currency} {v:,.0f}"
    elif abs(v) >= 1_000_000:
        return f"{v:,.0f}"
    elif abs(v) < 0.01 and v != 0:
        return f"{v:.4f}"
    return f"{v:,.2f}"


def safe_get(d: dict, *keys, default=None):
    """Safely traverse nested dicts."""
    current = d
    for k in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(k, default)
    return current
