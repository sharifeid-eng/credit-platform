"""
Portfolio Tools — snapshot listing, config, company catalog.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.agents.tools import registry

logger = logging.getLogger(__name__)


def _list_snapshots(company: str, product: str) -> str:
    from core.loader import get_snapshots
    snaps = get_snapshots(company, product)
    if not snaps:
        return f"No snapshots found for {company}/{product}"

    lines = [f"Snapshots for {company}/{product} ({len(snaps)}):"]
    for s in snaps:
        lines.append(f"  {s['filename']} (date: {s.get('date', '?')})")
    return "\n".join(lines)


def _compare_snapshots(
    company: str, product: str,
    snapshot_old: str, snapshot_new: str,
) -> str:
    from core.loader import get_snapshots, load_snapshot
    from core.agents.tools._helpers import detect_analysis_type

    snaps = get_snapshots(company, product)
    old_sel = None
    new_sel = None
    for s in snaps:
        if s["filename"] == snapshot_old or s.get("date") == snapshot_old:
            old_sel = s
        if s["filename"] == snapshot_new or s.get("date") == snapshot_new:
            new_sel = s

    if not old_sel or not new_sel:
        return f"Could not find both snapshots. Available: {[s['filename'] for s in snaps]}"

    df_old = load_snapshot(old_sel["filepath"])
    df_new = load_snapshot(new_sel["filepath"])

    lines = [f"Snapshot Comparison: {old_sel['filename']} → {new_sel['filename']}"]
    lines.append(f"  Old: {len(df_old)} deals")
    lines.append(f"  New: {len(df_new)} deals")
    lines.append(f"  Delta: {len(df_new) - len(df_old):+d} deals")

    # Column comparison
    old_cols = set(df_old.columns)
    new_cols = set(df_new.columns)
    added = new_cols - old_cols
    removed = old_cols - new_cols
    if added:
        lines.append(f"  New columns: {', '.join(sorted(added))}")
    if removed:
        lines.append(f"  Removed columns: {', '.join(sorted(removed))}")

    return "\n".join(lines)


def _get_product_config(company: str, product: str) -> str:
    from core.config import load_config
    config = load_config(company, product)
    if not config:
        return f"No config found for {company}/{product}"

    lines = [f"Config for {company}/{product}:"]
    for k, v in config.items():
        if not isinstance(v, (dict, list)):
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _list_companies() -> str:
    from core.loader import get_companies, get_products
    companies = get_companies()
    if not companies:
        return "No companies found."

    lines = [f"Companies ({len(companies)}):"]
    for co in companies:
        products = get_products(co)
        lines.append(f"  {co}: {', '.join(products)}")
    return "\n".join(lines)


# ── Registration ─────────────────────────────────────────────────────────

registry.register(
    "portfolio.list_snapshots",
    "List all available tape snapshots for a company/product with filenames and dates.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _list_snapshots,
)

registry.register(
    "portfolio.compare_snapshots",
    "Compare two snapshots: deal count delta, new/removed columns.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "snapshot_old": {"type": "string", "description": "Older snapshot filename or date"},
            "snapshot_new": {"type": "string", "description": "Newer snapshot filename or date"},
        },
        "required": ["company", "product", "snapshot_old", "snapshot_new"],
    },
    _compare_snapshots,
)

registry.register(
    "portfolio.get_config",
    "Get product configuration: currency, description, analysis_type.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _get_product_config,
)

registry.register(
    "portfolio.list_companies",
    "List all portfolio companies and their products.",
    {"type": "object", "properties": {}},
    _list_companies,
)
