"""
Compliance Tools — covenant checks, facility params, breach history.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from core.agents.tools import registry

logger = logging.getLogger(__name__)


def _check_all_covenants(
    company: str, product: str,
    snapshot: Optional[str] = None,
    currency: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    from core.agents.tools._helpers import detect_analysis_type, get_currency, load_tape, load_silq_tape

    at = detect_analysis_type(company, product)

    if at == "silq":
        df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        config, disp, mult = get_currency(company, product, currency)
        from core.analysis_silq import compute_silq_covenants
        result = compute_silq_covenants(df, mult, ref_date=as_of_date or sel.get("date"))
    elif at == "klaim":
        df, sel = load_tape(company, product, snapshot, as_of_date)
        config, disp, mult = get_currency(company, product, currency)
        from core.analysis import compute_klaim_covenants
        result = compute_klaim_covenants(df, mult, config, sel.get("date", ""), as_of_date)
    else:
        return f"Covenant checks not available for analysis_type={at}"

    covenants = result.get("covenants", [])
    breaches = [c for c in covenants if not c.get("compliant", True)]

    lines = [f"Full Covenant Check — {company}/{product}"]
    lines.append(f"  Snapshot: {sel.get('filename', 'latest')}")
    lines.append(f"  Total covenants: {len(covenants)}")
    lines.append(f"  Breaches: {len(breaches)}")
    lines.append("")

    for c in covenants:
        name = c.get("name", "?")
        actual = c.get("actual", "?")
        threshold = c.get("threshold", "?")
        compliant = c.get("compliant", False)
        status = "PASS" if compliant else "BREACH"
        headroom = c.get("headroom", "")
        line = f"  [{status}] {name}: actual={actual}, threshold={threshold}"
        if headroom:
            line += f", headroom={headroom}"
        lines.append(line)

    return "\n".join(lines)


def _get_facility_params(company: str, product: str) -> str:
    params_path = Path(f"data/{company}/{product}/facility_params.json")
    if not params_path.exists():
        return f"No facility parameters configured for {company}/{product}"

    try:
        params = json.loads(params_path.read_text(encoding="utf-8"))
        lines = [f"Facility Parameters — {company}/{product}:"]
        for k, v in params.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict):
                lines.append(f"  {k}:")
                for k2, v2 in v.items():
                    lines.append(f"    {k2}: {v2}")
            elif isinstance(v, list):
                lines.append(f"  {k}: [{len(v)} items]")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading facility params: {e}"


def _get_covenant_history(company: str, product: str) -> str:
    history_path = Path(f"data/{company}/{product}/covenant_history.json")
    if not history_path.exists():
        return f"No covenant history available for {company}/{product}"

    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
        lines = [f"Covenant History — {company}/{product}:"]

        if isinstance(history, dict):
            for cov_name, records in history.items():
                lines.append(f"\n  {cov_name}:")
                if isinstance(records, list):
                    for r in records[-5:]:  # Last 5 records
                        date = r.get("date", "?")
                        status = r.get("status", "?")
                        actual = r.get("actual", "?")
                        lines.append(f"    {date}: {status} (actual={actual})")

        return "\n".join(lines)
    except Exception as e:
        return f"Error reading covenant history: {e}"


# ── Registration ─────────────────────────────────────────────────────────

registry.register(
    "compliance.check_covenants",
    "Run a full covenant compliance check: computes all covenants against latest tape and reports pass/breach for each.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "snapshot": {"type": "string", "description": "Snapshot filename (optional, defaults to latest)"},
            "currency": {"type": "string", "description": "Display currency (optional)"},
            "as_of_date": {"type": "string", "description": "As-of date filter (optional)"},
        },
        "required": ["company", "product"],
    },
    _check_all_covenants,
)

registry.register(
    "compliance.get_facility_params",
    "Get facility configuration parameters: advance rates, concentration limits, covenant thresholds.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _get_facility_params,
)

registry.register(
    "compliance.get_covenant_history",
    "Get historical covenant evaluation results showing compliance trend over time.",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
        },
        "required": ["company", "product"],
    },
    _get_covenant_history,
)
