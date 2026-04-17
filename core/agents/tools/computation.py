"""
Computation Tool — safe pandas expression evaluator.

Allows the agent to run ad-hoc computations on tape data within
a restricted namespace. No file I/O, no imports beyond numpy/pandas.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.agents.tools import registry

logger = logging.getLogger(__name__)

# Allowlist of safe functions/attributes the agent can use
_SAFE_BUILTINS = {
    "len", "min", "max", "sum", "abs", "round", "sorted", "list",
    "int", "float", "str", "bool", "dict", "set", "tuple", "zip", "enumerate",
    "range", "True", "False", "None",
}


def _run_computation(
    company: str,
    product: str,
    expression: str,
    description: str = "",
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> str:
    """Evaluate a pandas expression on a loaded tape in a restricted namespace."""
    import numpy as np
    import pandas as pd
    from core.agents.tools._helpers import detect_analysis_type, load_tape, load_silq_tape, load_aajil_tape

    # Block dangerous patterns
    dangerous = ["import ", "exec(", "eval(", "open(", "__", "os.", "sys.", "subprocess", "shutil"]
    expr_lower = expression.lower()
    for d in dangerous:
        if d in expr_lower:
            return f"Blocked: expression contains unsafe pattern '{d}'"

    at = detect_analysis_type(company, product)
    try:
        if at == "silq":
            df, sel, _ = load_silq_tape(company, product, snapshot, as_of_date)
        elif at == "aajil":
            df, sel, _ = load_aajil_tape(company, product, snapshot, as_of_date)
        else:
            df, sel = load_tape(company, product, snapshot, as_of_date)
    except Exception as e:
        return f"Failed to load tape: {e}"

    # Build restricted namespace
    namespace = {
        "df": df,
        "pd": pd,
        "np": np,
        # Safe builtins
        "len": len, "min": min, "max": max, "sum": sum, "abs": abs,
        "round": round, "sorted": sorted, "list": list,
        "int": int, "float": float, "str": str, "bool": bool,
    }

    try:
        result = eval(expression, {"__builtins__": {}}, namespace)

        # Format result
        if isinstance(result, pd.DataFrame):
            if len(result) > 20:
                text = result.head(20).to_string() + f"\n\n... ({len(result)} rows total)"
            else:
                text = result.to_string()
        elif isinstance(result, pd.Series):
            if len(result) > 20:
                text = result.head(20).to_string() + f"\n\n... ({len(result)} items total)"
            else:
                text = result.to_string()
        elif isinstance(result, (int, float)):
            text = f"{result:,.4f}" if isinstance(result, float) else f"{result:,}"
        else:
            text = str(result)

        desc_line = f" ({description})" if description else ""
        return f"Computation result{desc_line}:\n{text}"

    except SyntaxError as e:
        return f"Syntax error in expression: {e}"
    except Exception as e:
        return f"Computation error: {type(e).__name__}: {e}"


# ── Registration ─────────────────────────────────────────────────────────

registry.register(
    "computation.run",
    "Run a pandas expression on the loaded tape data. Use for ad-hoc analysis that isn't covered by other tools. "
    "Available variables: df (the tape DataFrame), pd (pandas), np (numpy). "
    "Examples: df.groupby('Product')['Purchase value'].sum(), df[df['Status']=='Executed'].shape[0], "
    "df['Collected till date'].sum() / df['Purchase value'].sum()",
    {
        "type": "object",
        "properties": {
            "company": {"type": "string", "description": "Company name"},
            "product": {"type": "string", "description": "Product name"},
            "expression": {"type": "string", "description": "Pandas expression to evaluate (e.g., df.groupby('Product')['Purchase value'].sum())"},
            "description": {"type": "string", "description": "Brief description of what you're computing"},
            "snapshot": {"type": "string", "description": "Snapshot filename (optional)"},
            "as_of_date": {"type": "string", "description": "As-of date filter (optional)"},
        },
        "required": ["company", "product", "expression"],
    },
    _run_computation,
)
