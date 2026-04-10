"""Captures platform analytical output as research-ready documents.

Every time analytics are computed, the results can be snapshotted into the
document registry alongside data room files -- making them searchable, citable,
and comparable across time periods.

Usage::

    engine = AnalyticsSnapshotEngine()
    docs = engine.snapshot_tape_analytics(
        company="klaim", product="UAE_healthcare",
        snapshot_filename="2026-03-03_uae_healthcare.csv",
        summary=summary_dict,
        par=par_dict,
        cohort=cohort_dict,
    )
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Analytics document types (inline -- no external classifier.py dependency)
# ---------------------------------------------------------------------------

class AnalyticsDocType:
    """Document type constants for analytics snapshots."""

    # Tape analytics tabs
    TAPE_SUMMARY = "tape_summary"
    TAPE_PAR = "tape_par"
    TAPE_DSO = "tape_dso"
    TAPE_COHORT = "tape_cohort"
    TAPE_LOSS_WATERFALL = "tape_loss_waterfall"
    TAPE_COLLECTION_VELOCITY = "tape_collection_velocity"
    TAPE_CONCENTRATION = "tape_concentration"
    TAPE_RETURNS = "tape_returns"
    TAPE_RISK_MIGRATION = "tape_risk_migration"
    TAPE_DEPLOYMENT = "tape_deployment"
    TAPE_DENIAL_TREND = "tape_denial_trend"
    TAPE_AGEING = "tape_ageing"
    TAPE_REVENUE = "tape_revenue"
    TAPE_RECOVERY = "tape_recovery"
    TAPE_COLLECTIONS_TIMING = "tape_collections_timing"
    TAPE_UNDERWRITING_DRIFT = "tape_underwriting_drift"
    TAPE_SEGMENT_ANALYSIS = "tape_segment_analysis"
    TAPE_SEASONALITY = "tape_seasonality"
    TAPE_CDR_CCR = "tape_cdr_ccr"

    # Portfolio analytics
    PORTFOLIO_BORROWING_BASE = "portfolio_borrowing_base"
    PORTFOLIO_CONCENTRATION = "portfolio_concentration"
    PORTFOLIO_COVENANTS = "portfolio_covenants"
    PORTFOLIO_FACILITY_PARAMS = "portfolio_facility_params"

    # AI outputs
    AI_EXECUTIVE_SUMMARY = "ai_executive_summary"
    AI_COMMENTARY = "ai_commentary"
    AI_TAB_INSIGHT = "ai_tab_insight"


# Mapping from kwarg name to doc type for tape analytics
_TAPE_TAB_MAP: dict[str, str] = {
    "summary": AnalyticsDocType.TAPE_SUMMARY,
    "par": AnalyticsDocType.TAPE_PAR,
    "dso": AnalyticsDocType.TAPE_DSO,
    "cohort": AnalyticsDocType.TAPE_COHORT,
    "loss_waterfall": AnalyticsDocType.TAPE_LOSS_WATERFALL,
    "collection_velocity": AnalyticsDocType.TAPE_COLLECTION_VELOCITY,
    "concentration": AnalyticsDocType.TAPE_CONCENTRATION,
    "returns": AnalyticsDocType.TAPE_RETURNS,
    "risk_migration": AnalyticsDocType.TAPE_RISK_MIGRATION,
}

# Mapping from kwarg name to doc type for portfolio analytics
_PORTFOLIO_TAB_MAP: dict[str, str] = {
    "borrowing_base": AnalyticsDocType.PORTFOLIO_BORROWING_BASE,
    "concentration_limits": AnalyticsDocType.PORTFOLIO_CONCENTRATION,
    "covenants": AnalyticsDocType.PORTFOLIO_COVENANTS,
    "facility_params": AnalyticsDocType.PORTFOLIO_FACILITY_PARAMS,
}

# AI output type string to doc type
_AI_TYPE_MAP: dict[str, str] = {
    "executive_summary": AnalyticsDocType.AI_EXECUTIVE_SUMMARY,
    "commentary": AnalyticsDocType.AI_COMMENTARY,
    "tab_insight": AnalyticsDocType.AI_TAB_INSIGHT,
}


# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------

def _make_serialisable(obj: Any) -> Any:
    """Recursively convert numpy/pandas types to plain Python for JSON.

    Handles: np.int64, np.float64, np.bool_, np.ndarray, pd.Timestamp,
    pd.NaT, float('nan'), float('inf'), and nested dicts/lists.
    """
    # Import lazily so the module works even without numpy/pandas installed.
    try:
        import numpy as np
        _np = True
    except ImportError:
        _np = False

    try:
        import pandas as pd
        _pd = True
    except ImportError:
        _pd = False

    if obj is None:
        return None

    # numpy scalars
    if _np:
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            v = float(obj)
            if np.isnan(v) or np.isinf(v):
                return None
            return v
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [_make_serialisable(x) for x in obj.tolist()]

    # pandas types
    if _pd:
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat() if not pd.isna(obj) else None
        if obj is pd.NaT:
            return None

    # plain float edge cases
    if isinstance(obj, float):
        if obj != obj or obj == float("inf") or obj == float("-inf"):
            return None
        return obj

    if isinstance(obj, dict):
        return {str(k): _make_serialisable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_make_serialisable(x) for x in obj]

    # datetime
    if isinstance(obj, datetime):
        return obj.isoformat()

    # Anything JSON-native passes through
    if isinstance(obj, (str, int, bool)):
        return obj

    # Last resort: stringify
    return str(obj)


def _extract_snapshot_date(snapshot_filename: str) -> Optional[str]:
    """Extract YYYY-MM-DD date from a snapshot filename."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", snapshot_filename or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Formatters: analytics dict -> human-readable text
# ---------------------------------------------------------------------------

def _fmt_number(v: Any, prefix: str = "", suffix: str = "") -> str:
    """Format a number for text representation."""
    if v is None:
        return "N/A"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(v) >= 1e9:
        return f"{prefix}{v / 1e9:.2f}B{suffix}"
    if abs(v) >= 1e6:
        return f"{prefix}{v / 1e6:.1f}M{suffix}"
    if abs(v) >= 1e3:
        return f"{prefix}{v / 1e3:.0f}K{suffix}"
    return f"{prefix}{v:,.2f}{suffix}"


def _format_summary(data: dict) -> str:
    lines = [
        "Portfolio Summary",
        f"  Total Deals: {data.get('total_deals', 'N/A'):,}" if isinstance(data.get('total_deals'), (int, float)) else f"  Total Deals: {data.get('total_deals', 'N/A')}",
        f"  Face Value: {_fmt_number(data.get('total_purchase_value'))}",
        f"  Collection Rate: {data.get('collection_rate', 'N/A'):.1f}%" if isinstance(data.get('collection_rate'), (int, float)) else f"  Collection Rate: N/A",
        f"  Denial Rate: {data.get('denial_rate', 'N/A'):.1f}%" if isinstance(data.get('denial_rate'), (int, float)) else f"  Denial Rate: N/A",
        f"  Pending Rate: {data.get('pending_rate', 'N/A'):.1f}%" if isinstance(data.get('pending_rate'), (int, float)) else f"  Pending Rate: N/A",
        f"  Active Deals: {data.get('active_deals', 'N/A')}",
        f"  Completed Deals: {data.get('completed_deals', 'N/A')}",
        f"  Avg Discount: {data.get('avg_discount', 0) * 100:.2f}%" if isinstance(data.get('avg_discount'), (int, float)) and data.get('avg_discount', 0) < 1 else f"  Avg Discount: {data.get('avg_discount', 'N/A')}%",
    ]
    return "\n".join(lines)


def _format_par(data: dict) -> str:
    if not data.get("available"):
        return "PAR: Not available for this tape"
    lines = ["Portfolio at Risk (PAR)"]
    for bucket in ["par_30", "par_60", "par_90"]:
        entry = data.get(bucket, {})
        if isinstance(entry, dict):
            pct = entry.get("balance_pct", 0)
            bal = entry.get("balance", 0)
            lines.append(f"  {bucket.upper().replace('_', ' ')}: {pct:.2f}% ({_fmt_number(bal)} at risk)")
    lines.append(f"  Method: {data.get('method', 'unknown')}")
    return "\n".join(lines)


def _format_dso(data: dict) -> str:
    if not data.get("available"):
        return "DSO: Not available for this tape"
    lines = [
        "Days Sales Outstanding",
        f"  Weighted DSO: {data.get('weighted_dso', 'N/A'):.0f} days" if isinstance(data.get('weighted_dso'), (int, float)) else "  Weighted DSO: N/A",
        f"  Median DSO: {data.get('median_dso', 'N/A'):.0f} days" if isinstance(data.get('median_dso'), (int, float)) else "  Median DSO: N/A",
        f"  P95 DSO: {data.get('p95_dso', 'N/A'):.0f} days" if isinstance(data.get('p95_dso'), (int, float)) else "  P95 DSO: N/A",
    ]
    return "\n".join(lines)


def _format_cohort(data: dict) -> str:
    cohorts = data.get("cohorts", [])
    if not cohorts:
        return "Cohort Analysis: No cohort data"
    lines = ["Cohort Analysis (Vintage Performance)"]
    for c in cohorts[:12]:  # Cap at 12 most recent
        vintage = c.get("vintage", "?")
        deals = c.get("deals", 0)
        coll = c.get("collection_rate", 0)
        denial = c.get("denial_rate", 0)
        lines.append(f"  {vintage}: {deals} deals, Collection {coll:.1f}%, Denial {denial:.1f}%")
    if len(cohorts) > 12:
        lines.append(f"  ... and {len(cohorts) - 12} older vintages")
    return "\n".join(lines)


def _format_loss_waterfall(data: dict) -> str:
    vintages = data.get("vintages", [])
    totals = data.get("totals", {})
    lines = ["Loss Waterfall"]
    if totals:
        lines.append(f"  Total Originated: {_fmt_number(totals.get('originated'))}")
        lines.append(f"  Gross Default: {_fmt_number(totals.get('gross_default'))} ({totals.get('default_rate', 0):.2f}%)")
        lines.append(f"  Recovery: {_fmt_number(totals.get('recovery'))} ({totals.get('recovery_rate', 0):.1f}%)")
        lines.append(f"  Net Loss: {_fmt_number(totals.get('net_loss'))} ({totals.get('net_loss_rate', 0):.2f}%)")
    for v in vintages[:8]:
        lines.append(f"  {v.get('vintage', '?')}: Default {v.get('default_rate', 0):.2f}%, Net Loss {v.get('net_loss_rate', 0):.2f}%")
    return "\n".join(lines)


def _format_collection_velocity(data: dict) -> str:
    monthly = data.get("monthly", [])
    lines = ["Collection Velocity"]
    if data.get("avg_days"):
        lines.append(f"  Average Days to Collect: {data['avg_days']:.0f}")
    if data.get("median_days"):
        lines.append(f"  Median Days to Collect: {data['median_days']:.0f}")
    for m in monthly[-6:]:  # Last 6 months
        lines.append(f"  {m.get('Month', '?')}: {m.get('rate', 0):.1f}%")
    return "\n".join(lines)


def _format_concentration(data: dict) -> str:
    lines = ["Concentration Analysis"]
    hhi = data.get("hhi", {})
    if hhi:
        lines.append(f"  HHI: {hhi.get('hhi', 0):.0f} ({hhi.get('level', 'unknown')})")
    groups = data.get("group", [])
    for g in groups[:10]:
        lines.append(f"  {g.get('Group', '?')}: {g.get('share_pct', 0):.1f}% share, Collection {g.get('collection_rate', 0):.1f}%")
    return "\n".join(lines)


def _format_returns(data: dict) -> str:
    s = data.get("summary", {})
    lines = [
        "Returns Analysis",
        f"  Realised Margin: {s.get('realised_margin', 0):.2f}%",
        f"  Capital Recovery: {s.get('capital_recovery', 0):.2f}%",
    ]
    if s.get("has_irr"):
        lines.append(f"  Avg Expected IRR: {s.get('avg_expected_irr', 0):.2f}%")
        lines.append(f"  Avg Actual IRR: {s.get('avg_actual_irr', 0):.2f}%")
    return "\n".join(lines)


def _format_risk_migration(data: dict) -> str:
    lines = ["Risk & Migration"]
    cure = data.get("cure_rates", {})
    if cure:
        lines.append(f"  Overall Cure Rate: {cure.get('overall', 0):.1f}%")
    el = data.get("expected_loss", {})
    if isinstance(el, dict) and el.get("portfolio"):
        port = el["portfolio"]
        lines.append(f"  PD: {port.get('pd', 0):.2f}%, LGD: {port.get('lgd', 0):.2f}%, EL Rate: {port.get('el_rate', 0):.4f}%")
    stress = data.get("stress_test", {})
    if isinstance(stress, dict):
        for sc in stress.get("scenarios", [])[:3]:
            lines.append(f"  Stress ({sc.get('name', '?')}): Impact {_fmt_number(sc.get('impact'))}")
    return "\n".join(lines)


def _format_borrowing_base(data: dict) -> str:
    lines = ["Borrowing Base"]
    if data.get("total_gross"):
        lines.append(f"  Gross Portfolio: {_fmt_number(data['total_gross'])}")
    if data.get("total_eligible"):
        lines.append(f"  Eligible: {_fmt_number(data['total_eligible'])}")
    if data.get("borrowing_base"):
        lines.append(f"  Borrowing Base: {_fmt_number(data['borrowing_base'])}")
    if data.get("facility_limit"):
        lines.append(f"  Facility Limit: {_fmt_number(data['facility_limit'])}")
    if data.get("utilization"):
        lines.append(f"  Utilization: {data['utilization']:.1f}%")
    return "\n".join(lines)


def _format_portfolio_concentration(data: dict) -> str:
    lines = ["Concentration Limits"]
    limits = data.get("limits", [])
    for lim in limits:
        status = "COMPLIANT" if lim.get("compliant") else "BREACH"
        lines.append(f"  {lim.get('name', '?')}: {lim.get('actual', 0):.1f}% (limit: {lim.get('limit', 0):.1f}%) [{status}]")
    return "\n".join(lines)


def _format_covenants(data: dict) -> str:
    lines = ["Covenant Compliance"]
    covs = data.get("covenants", [])
    for cov in covs:
        status = "COMPLIANT" if cov.get("compliant") else "BREACH"
        lines.append(f"  {cov.get('name', '?')}: {cov.get('actual', 'N/A')} (threshold: {cov.get('threshold', 'N/A')}) [{status}]")
    return "\n".join(lines)


def _format_generic(tab_slug: str, data: dict) -> str:
    """Fallback formatter for tabs without a specialised one."""
    lines = [f"Analytics: {tab_slug}"]
    # Pull out top-level scalar values as summary
    for k, v in data.items():
        if isinstance(v, (str, int, float, bool)) and v is not None:
            lines.append(f"  {k}: {v}")
    # Truncate to avoid huge text blobs
    if len(lines) > 30:
        lines = lines[:30]
        lines.append("  ... (truncated)")
    return "\n".join(lines)


# Tab slug -> formatter mapping
_TAB_FORMATTERS: dict[str, Any] = {
    AnalyticsDocType.TAPE_SUMMARY: _format_summary,
    AnalyticsDocType.TAPE_PAR: _format_par,
    AnalyticsDocType.TAPE_DSO: _format_dso,
    AnalyticsDocType.TAPE_COHORT: _format_cohort,
    AnalyticsDocType.TAPE_LOSS_WATERFALL: _format_loss_waterfall,
    AnalyticsDocType.TAPE_COLLECTION_VELOCITY: _format_collection_velocity,
    AnalyticsDocType.TAPE_CONCENTRATION: _format_concentration,
    AnalyticsDocType.TAPE_RETURNS: _format_returns,
    AnalyticsDocType.TAPE_RISK_MIGRATION: _format_risk_migration,
    AnalyticsDocType.PORTFOLIO_BORROWING_BASE: _format_borrowing_base,
    AnalyticsDocType.PORTFOLIO_CONCENTRATION: _format_portfolio_concentration,
    AnalyticsDocType.PORTFOLIO_COVENANTS: _format_covenants,
}


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

class AnalyticsSnapshotEngine:
    """Snapshots platform analytics into the document registry.

    Documents are stored in the same ``registry.json`` that the data room
    engine uses, so analytics become first-class searchable, citable records
    alongside raw data room files.
    """

    def __init__(self, base_dir: str | Path | None = None):
        """Initialise the engine.

        Args:
            base_dir: Project root.  Auto-detected from module location if
                omitted (assumes ``core/dataroom/analytics_snapshot.py``).
        """
        if base_dir is not None:
            self.base_dir = Path(base_dir)
        else:
            # __file__ = .../core/dataroom/analytics_snapshot.py  -> go up 3 levels
            self.base_dir = Path(__file__).resolve().parent.parent.parent

    # ------------------------------------------------------------------
    # Public: tape analytics
    # ------------------------------------------------------------------

    def snapshot_tape_analytics(
        self,
        company: str,
        product: str,
        snapshot_filename: str,
        summary: dict | None = None,
        par: dict | None = None,
        dso: dict | None = None,
        cohort: dict | None = None,
        loss_waterfall: dict | None = None,
        collection_velocity: dict | None = None,
        concentration: dict | None = None,
        returns: dict | None = None,
        risk_migration: dict | None = None,
        additional_tabs: dict[str, dict] | None = None,
    ) -> list[dict]:
        """Capture tape analytics outputs as documents.

        Each non-None kwarg becomes a separate document in the registry.
        Accepts pre-computed results -- the caller passes them; this module
        never re-computes.

        Args:
            company: Company slug (e.g. ``"klaim"``).
            product: Product slug (e.g. ``"UAE_healthcare"``).
            snapshot_filename: Tape filename (e.g. ``"2026-03-03_uae_healthcare.csv"``).
            summary .. risk_migration: Pre-computed analytics dicts.
            additional_tabs: Mapping of ``{doc_type: data}`` for any extra tabs
                not covered by the explicit kwargs (deployment, denial_trend,
                ageing, revenue, etc.).

        Returns:
            List of document record dicts that were stored/updated.
        """
        snapshot_date = _extract_snapshot_date(snapshot_filename)
        stored: list[dict] = []

        # Named tabs from kwargs
        tabs: dict[str, dict | None] = {
            "summary": summary,
            "par": par,
            "dso": dso,
            "cohort": cohort,
            "loss_waterfall": loss_waterfall,
            "collection_velocity": collection_velocity,
            "concentration": concentration,
            "returns": returns,
            "risk_migration": risk_migration,
        }

        for kwarg_name, data in tabs.items():
            if data is None:
                continue
            doc_type = _TAPE_TAB_MAP[kwarg_name]
            doc = self._build_document(
                company=company,
                product=product,
                doc_type=doc_type,
                data=data,
                snapshot_filename=snapshot_filename,
                snapshot_date=snapshot_date,
            )
            stored.append(self._store_document(company, product, doc))

        # Additional tabs (arbitrary doc_type -> data)
        if additional_tabs:
            for doc_type, data in additional_tabs.items():
                if data is None:
                    continue
                doc = self._build_document(
                    company=company,
                    product=product,
                    doc_type=doc_type,
                    data=data,
                    snapshot_filename=snapshot_filename,
                    snapshot_date=snapshot_date,
                )
                stored.append(self._store_document(company, product, doc))

        return stored

    # ------------------------------------------------------------------
    # Public: portfolio analytics
    # ------------------------------------------------------------------

    def snapshot_portfolio_analytics(
        self,
        company: str,
        product: str,
        borrowing_base: dict | None = None,
        concentration_limits: dict | None = None,
        covenants: dict | None = None,
        facility_params: dict | None = None,
    ) -> list[dict]:
        """Capture portfolio analytics outputs as documents.

        Args:
            company: Company slug.
            product: Product slug.
            borrowing_base .. facility_params: Pre-computed portfolio analytics dicts.

        Returns:
            List of document record dicts stored/updated.
        """
        now_str = datetime.utcnow().strftime("%Y-%m-%d")
        stored: list[dict] = []

        tabs = {
            "borrowing_base": borrowing_base,
            "concentration_limits": concentration_limits,
            "covenants": covenants,
            "facility_params": facility_params,
        }

        for kwarg_name, data in tabs.items():
            if data is None:
                continue
            doc_type = _PORTFOLIO_TAB_MAP[kwarg_name]
            doc = self._build_document(
                company=company,
                product=product,
                doc_type=doc_type,
                data=data,
                snapshot_filename=None,
                snapshot_date=now_str,
            )
            stored.append(self._store_document(company, product, doc))

        return stored

    # ------------------------------------------------------------------
    # Public: AI outputs
    # ------------------------------------------------------------------

    def snapshot_ai_output(
        self,
        company: str,
        product: str,
        output_type: str,
        content: dict,
        snapshot_filename: str | None = None,
        tab_slug: str | None = None,
    ) -> dict:
        """Capture an AI-generated output as a document.

        AI outputs are high-value: they contain the AI's prior reasoning.
        When generating a new memo the system can reference previous conclusions,
        ensuring consistency and building on prior analysis.

        Args:
            company: Company slug.
            product: Product slug.
            output_type: One of ``"executive_summary"``, ``"commentary"``,
                ``"tab_insight"``.
            content: The AI response dict/text.
            snapshot_filename: Source tape filename (optional).
            tab_slug: For tab insights, which tab the insight is about.

        Returns:
            Document record dict that was stored.
        """
        snapshot_date = _extract_snapshot_date(snapshot_filename) if snapshot_filename else None
        doc_type = _AI_TYPE_MAP.get(output_type, f"ai_{output_type}")

        # Build a descriptive filename
        parts = [doc_type]
        if tab_slug:
            parts.append(tab_slug)
        if snapshot_date:
            parts.append(snapshot_date)
        filename = "_".join(parts) + ".json"

        text = self._format_ai_output_as_text(output_type, content, tab_slug)
        safe_content = _make_serialisable(content)

        doc: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "filename": filename,
            "doc_type": doc_type,
            "snapshot_date": snapshot_date or datetime.utcnow().strftime("%Y-%m-%d"),
            "snapshot_filename": snapshot_filename,
            "tab_slug": tab_slug,
            "text_representation": text,
            "parsed_at": datetime.utcnow().isoformat(),
            "source": "platform_ai",
        }

        return self._store_document(company, product, doc, content=safe_content)

    # ------------------------------------------------------------------
    # Public: timeline queries
    # ------------------------------------------------------------------

    def get_analytics_timeline(
        self,
        company: str,
        product: str,
        doc_type: str | None = None,
    ) -> list[dict]:
        """Return all analytics snapshots over time.

        Enables trend analysis across memos -- e.g.
        "PAR improved from 4.2% (Jan snapshot) to 3.6% (Mar snapshot)".

        Args:
            company: Company slug.
            product: Product slug.
            doc_type: Optional filter (e.g. ``"tape_par"``).

        Returns:
            List of ``{snapshot_date, doc_type, doc_id, filename, key_metrics}``
            sorted ascending by ``snapshot_date``.
        """
        registry = self._load_registry(company, product)
        analytics_prefix = (
            "tape_", "portfolio_", "ai_executive", "ai_commentary", "ai_tab"
        )

        results: list[dict] = []
        for doc_id, doc in registry.items():
            dtype = doc.get("doc_type", "")
            if not any(dtype.startswith(p) for p in analytics_prefix):
                continue
            if doc_type and dtype != doc_type:
                continue

            # Extract a few key metrics from stored content for quick comparison
            key_metrics = self._extract_key_metrics(company, product, doc)

            results.append({
                "snapshot_date": doc.get("snapshot_date"),
                "doc_type": dtype,
                "doc_id": doc["id"],
                "filename": doc.get("filename"),
                "key_metrics": key_metrics,
            })

        results.sort(key=lambda r: r.get("snapshot_date") or "")
        return results

    # ------------------------------------------------------------------
    # Internal: document building & storage
    # ------------------------------------------------------------------

    def _build_document(
        self,
        company: str,
        product: str,
        doc_type: str,
        data: dict,
        snapshot_filename: str | None,
        snapshot_date: str | None,
    ) -> dict[str, Any]:
        """Build a document record dict ready for storage."""
        # Build descriptive filename
        parts = [doc_type]
        if snapshot_date:
            parts.append(snapshot_date)
        filename = "_".join(parts) + ".json"

        text = self._format_analytics_as_text(doc_type, data, snapshot_date)

        return {
            "id": str(uuid.uuid4()),
            "filename": filename,
            "doc_type": doc_type,
            "snapshot_date": snapshot_date or datetime.utcnow().strftime("%Y-%m-%d"),
            "snapshot_filename": snapshot_filename,
            "text_representation": text,
            "parsed_at": datetime.utcnow().isoformat(),
            "source": "platform_analytics",
        }

    def _store_document(
        self,
        company: str,
        product: str,
        doc: dict,
        content: Any | None = None,
    ) -> dict:
        """Store a document record in the registry and save its content.

        De-duplicates: if a document with the same ``doc_type`` and
        ``snapshot_date`` already exists, it is updated in place rather
        than duplicated.

        Args:
            company: Company slug.
            product: Product slug.
            doc: Document record dict (id, filename, doc_type, ...).
            content: If provided, this raw dict is saved as the content JSON.
                If ``None``, the ``text_representation`` from ``doc`` is used.

        Returns:
            The stored document record (may have a recycled ``id`` on update).
        """
        dataroom_dir = self._dataroom_dir(company, product)
        analytics_dir = dataroom_dir / "analytics"
        analytics_dir.mkdir(parents=True, exist_ok=True)

        # --- Resolve content to store ---
        if content is None:
            # No raw content passed -- store the text representation
            safe_content = {"text": doc.get("text_representation", "")}
        else:
            safe_content = _make_serialisable(content)

        # --- De-duplicate against existing registry (dict format) ---
        registry = self._load_registry(company, product)
        existing_id: str | None = None
        for doc_id, existing in registry.items():
            if (
                existing.get("doc_type") == doc["doc_type"]
                and existing.get("snapshot_date") == doc.get("snapshot_date")
                and existing.get("tab_slug", None) == doc.get("tab_slug", None)
            ):
                existing_id = doc_id
                break

        if existing_id is not None:
            # Update in place: keep old id, update content + metadata
            doc["id"] = existing_id
            doc["doc_id"] = existing_id
            registry[existing_id] = doc
        else:
            doc_id = doc.get("id") or doc.get("doc_id") or str(uuid.uuid4())[:12]
            doc["doc_id"] = doc_id
            doc["id"] = doc_id
            registry[doc_id] = doc

        # --- Write content JSON ---
        content_path = analytics_dir / f"{doc['id']}.json"
        doc["content_path"] = str(content_path.relative_to(self.base_dir))
        with open(content_path, "w", encoding="utf-8") as f:
            json.dump(safe_content, f, indent=2, ensure_ascii=False, default=str)

        # --- Write registry ---
        self._save_registry(company, product, registry)

        return doc

    # ------------------------------------------------------------------
    # Internal: text formatting
    # ------------------------------------------------------------------

    def _format_analytics_as_text(
        self,
        doc_type: str,
        data: dict,
        snapshot_date: str | None = None,
    ) -> str:
        """Convert analytics dict to searchable text representation.

        Uses specialised formatters for known tab types; falls back to a
        generic key-value dump for unknown types.
        """
        header = f"({snapshot_date} snapshot)" if snapshot_date else ""

        formatter = _TAB_FORMATTERS.get(doc_type)
        if formatter is not None:
            body = formatter(data)
        else:
            body = _format_generic(doc_type, data)

        return f"{body} {header}".strip()

    def _format_ai_output_as_text(
        self,
        output_type: str,
        content: Any,
        tab_slug: str | None = None,
    ) -> str:
        """Convert AI output dict to searchable text.

        For executive summaries: extracts narrative sections + findings.
        For commentary: extracts the commentary text.
        For tab insights: extracts the insight text.
        """
        if isinstance(content, str):
            return content

        if not isinstance(content, dict):
            return str(content)

        lines: list[str] = []

        if output_type == "executive_summary":
            lines.append("AI Executive Summary")
            # New format: narrative + findings
            narrative = content.get("narrative", {})
            if isinstance(narrative, dict):
                for section in narrative.get("sections", []):
                    title = section.get("title", "Section")
                    lines.append(f"\n  --- {title} ---")
                    for para in section.get("paragraphs", []):
                        if isinstance(para, str):
                            lines.append(f"  {para[:200]}")
                bottom = narrative.get("bottom_line", "")
                if bottom:
                    lines.append(f"\n  BOTTOM LINE: {bottom[:300]}")

            findings = content.get("findings", [])
            if isinstance(findings, list):
                # Could be old format (list of findings directly)
                if findings and isinstance(findings[0], dict):
                    lines.append("\n  KEY FINDINGS:")
                    for f in findings[:10]:
                        sev = f.get("severity", "info")
                        title = f.get("title", "")
                        lines.append(f"  [{sev.upper()}] {title}")
                elif findings and isinstance(findings[0], str):
                    lines.append("\n  KEY FINDINGS:")
                    for f in findings[:10]:
                        lines.append(f"  - {f[:200]}")

        elif output_type == "commentary":
            lines.append("AI Portfolio Commentary")
            commentary = content.get("commentary", content.get("text", ""))
            if isinstance(commentary, str):
                lines.append(f"  {commentary[:500]}")

        elif output_type == "tab_insight":
            tab_label = tab_slug or "unknown"
            lines.append(f"AI Tab Insight: {tab_label}")
            insight = content.get("insight", content.get("text", ""))
            if isinstance(insight, str):
                lines.append(f"  {insight[:500]}")

        else:
            lines.append(f"AI Output ({output_type})")
            for k, v in content.items():
                if isinstance(v, str):
                    lines.append(f"  {k}: {v[:200]}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal: key metric extraction for timeline
    # ------------------------------------------------------------------

    def _extract_key_metrics(
        self,
        company: str,
        product: str,
        doc: dict,
    ) -> dict:
        """Extract a handful of key metrics from a stored analytics document.

        Reads the content JSON file and pulls out the most important numbers
        for quick timeline comparison. Returns an empty dict if the file
        cannot be read.
        """
        content_path = doc.get("content_path")
        if not content_path:
            return {}

        full_path = self.base_dir / content_path
        if not full_path.exists():
            return {}

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

        doc_type = doc.get("doc_type", "")
        metrics: dict[str, Any] = {}

        if doc_type == AnalyticsDocType.TAPE_SUMMARY:
            for key in ("collection_rate", "denial_rate", "total_deals", "total_purchase_value"):
                if key in data:
                    metrics[key] = data[key]

        elif doc_type == AnalyticsDocType.TAPE_PAR:
            if data.get("available"):
                for bucket in ("par_30", "par_60", "par_90"):
                    entry = data.get(bucket, {})
                    if isinstance(entry, dict):
                        metrics[f"{bucket}_pct"] = entry.get("balance_pct")

        elif doc_type == AnalyticsDocType.TAPE_DSO:
            if data.get("available"):
                metrics["weighted_dso"] = data.get("weighted_dso")
                metrics["median_dso"] = data.get("median_dso")

        elif doc_type == AnalyticsDocType.PORTFOLIO_BORROWING_BASE:
            metrics["borrowing_base"] = data.get("borrowing_base")
            metrics["utilization"] = data.get("utilization")

        elif doc_type == AnalyticsDocType.PORTFOLIO_COVENANTS:
            covs = data.get("covenants", [])
            breaches = sum(1 for c in covs if not c.get("compliant", True))
            metrics["total_covenants"] = len(covs)
            metrics["breaches"] = breaches

        return {k: v for k, v in metrics.items() if v is not None}

    # ------------------------------------------------------------------
    # Internal: registry I/O
    # ------------------------------------------------------------------

    def _dataroom_dir(self, company: str, product: str) -> Path:
        """Return the dataroom directory for a company/product."""
        return self.base_dir / "data" / company / product / "dataroom"

    def _registry_path(self, company: str, product: str) -> Path:
        return self._dataroom_dir(company, product) / "registry.json"

    def _load_registry(self, company: str, product: str) -> dict:
        """Load the document registry as dict keyed by doc_id.

        Matches DataRoomEngine format: {doc_id: {record...}, ...}
        Handles migration from old list format if encountered.
        """
        path = self._registry_path(company, product)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            # Migrate from old list format
            if isinstance(data, list):
                migrated = {}
                for item in data:
                    doc_id = item.get("id") or item.get("doc_id") or str(uuid.uuid4())[:12]
                    item["doc_id"] = doc_id
                    migrated[doc_id] = item
                return migrated
            return {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_registry(self, company: str, product: str, registry: dict) -> None:
        """Persist the registry to disk as dict keyed by doc_id."""
        path = self._registry_path(company, product)
        path.parent.mkdir(parents=True, exist_ok=True)
        safe = _make_serialisable(registry)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(safe, f, indent=2, ensure_ascii=False, default=str)
