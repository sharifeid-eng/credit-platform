"""
Analytics Bridge — pulls live tape/portfolio analytics into memo sections.

Self-contained module that loads its own data directly from the filesystem,
independent of the FastAPI web server. This allows memo generation to run
as a standalone process (CLI, background job, or API endpoint).

Supports all analysis types:
  - klaim: Healthcare receivables (raw tape)
  - silq: POS lending (raw tape)
  - ejari_summary: Rent Now Pay Later (ODS workbook)
  - tamara_summary: BNPL data room (JSON snapshot)
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from core.config import load_config
from core.loader import get_companies, get_products, get_snapshots, load_snapshot
from core.analysis import (
    apply_multiplier,
    filter_by_date,
    fmt_m,
    compute_summary,
    compute_deployment,
    compute_concentration,
    compute_hhi,
    compute_par,
    compute_stress_test,
    compute_expected_loss,
    compute_cohort_loss_waterfall,
    compute_underwriting_drift,
)

logger = logging.getLogger(__name__)

# Project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _safe(v):
    """Convert to JSON-safe Python type."""
    if v is None:
        return None
    try:
        import numpy as np
        if isinstance(v, float) and np.isnan(v):
            return None
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return round(float(v), 6)
    except ImportError:
        pass
    if isinstance(v, pd.Timestamp):
        return v.isoformat()[:10]
    return v


def _fmt_pct(v):
    """Format a percentage value."""
    if v is None:
        return "--"
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return "--"


def _fmt_money(v, ccy="USD"):
    """Format a monetary value with currency prefix."""
    if v is None:
        return "--"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "--"
    if abs(n) >= 1e9:
        return f"{ccy} {n/1e9:,.1f}B"
    if abs(n) >= 1e6:
        return f"{ccy} {n/1e6:,.1f}M"
    if abs(n) >= 1e3:
        return f"{ccy} {n/1e3:,.0f}K"
    return f"{ccy} {n:,.0f}"


class AnalyticsBridge:
    """Pulls live analytics from tape/portfolio endpoints into memo sections.

    Self-contained: loads data directly from the filesystem using core/loader.py.
    No dependency on FastAPI or backend/main.py.
    """

    def __init__(self):
        """Initialize the bridge. No external dependencies needed."""
        self._snapshot_cache = {}

    # ── Data loading ────────────────────────────────────────────────────────

    def _load_data(self, company: str, product: str,
                   snapshot: Optional[str] = None) -> tuple:
        """Load tape data for a company/product.

        Returns (df, config, snapshot_filename, snapshot_date, aux) where
        `aux` is a dict of auxiliary DataFrames for multi-sheet formats
        (Aajil has Payments, DPD Cohorts, Collections sheets). For tape
        types without auxiliary sheets, aux is None.

        Returns (None, None, None, None, None) if data is unavailable.
        """
        cache_key = (company, product, snapshot)
        if cache_key in self._snapshot_cache:
            return self._snapshot_cache[cache_key]

        try:
            config = load_config(company, product)
            if not config:
                logger.warning("No config for %s/%s", company, product)
                return None, None, None, None, None

            analysis_type = config.get("analysis_type", "")

            # Summary-only types (Ejari, Tamara) do not have raw tapes
            if analysis_type in ("ejari_summary", "tamara_summary"):
                result = (None, config, None, None, None)
                self._snapshot_cache[cache_key] = result
                return result

            snapshots = get_snapshots(company, product)
            if not snapshots:
                logger.warning("No snapshots for %s/%s", company, product)
                return None, config, None, None, None

            # Pick the requested snapshot or the latest
            if snapshot:
                snap = next(
                    (s for s in snapshots if s["filename"] == snapshot),
                    snapshots[-1],
                )
            else:
                snap = snapshots[-1]

            aux = None

            # SILQ uses a special loader
            if analysis_type == "silq" or company.lower() == "silq":
                from core.loader import load_silq_snapshot
                df, _commentary = load_silq_snapshot(snap["filepath"])
            elif (analysis_type == "aajil" or company.lower() == "aajil") \
                    and snap["filepath"].endswith((".xlsx", ".xls")):
                # Aajil tape is a multi-sheet xlsx — load all auxiliary sheets
                # (Payments, DPD Cohorts, Collections) so compute functions
                # can use them. JSON snapshots fall through to None below.
                from core.loader import load_aajil_snapshot
                df, aux = load_aajil_snapshot(snap["filepath"])
            else:
                df = load_snapshot(snap["filepath"])

            result = (df, config, snap["filename"], snap.get("date"), aux)
            self._snapshot_cache[cache_key] = result
            return result

        except Exception as e:
            logger.error("Failed to load data for %s/%s: %s", company, product, e)
            return None, None, None, None, None

    def _load_summary_data(self, company: str, product: str) -> Optional[dict]:
        """Load pre-computed summary data for Ejari/Tamara types."""
        try:
            config = load_config(company, product)
            if not config:
                return None

            analysis_type = config.get("analysis_type", "")

            if analysis_type == "ejari_summary":
                from core.analysis_ejari import parse_ejari_workbook
                snapshots = get_snapshots(company, product)
                if not snapshots:
                    return None
                return parse_ejari_workbook(snapshots[-1]["filepath"])

            if analysis_type == "tamara_summary":
                from core.analysis_tamara import parse_tamara_data
                snapshots = get_snapshots(company, product)
                if not snapshots:
                    return None
                return parse_tamara_data(snapshots[-1]["filepath"])

            return None
        except Exception as e:
            logger.error("Failed to load summary data for %s/%s: %s",
                         company, product, e)
            return None

    # ── Section context builders ────────────────────────────────────────────

    def get_section_context(self, company: str, product: str,
                            section_key: str,
                            snapshot: Optional[str] = None,
                            currency: Optional[str] = None) -> dict:
        """Return structured analytics context for a memo section.

        Maps section keys to relevant compute functions. Returns a dict with:
          - metrics: list of {label, value, assessment} dicts
          - text: pre-formatted narrative paragraph
          - charts_data: raw data dict for reference
          - available: whether analytics data was found

        Handles gracefully when data is unavailable.
        """
        df, config, snap_fn, snap_date, aux = self._load_data(
            company, product, snapshot
        )

        analysis_type = config.get("analysis_type", "") if config else ""
        reported_ccy = config.get("currency", "USD") if config else "USD"
        display_ccy = currency or reported_ccy

        # For summary-only types, delegate to the summary builder
        if analysis_type in ("ejari_summary", "tamara_summary"):
            return self._get_summary_section_context(
                company, product, section_key, analysis_type
            )

        # If no DataFrame, return empty context
        if df is None:
            return {
                "metrics": [],
                "text": f"No tape data available for {company}/{product}.",
                "charts_data": {},
                "available": False,
            }

        mult = apply_multiplier(config, display_ccy)
        is_silq = analysis_type == "silq" or company.lower() == "silq"
        is_aajil = analysis_type == "aajil" or company.lower() == "aajil"

        # Dispatch to the appropriate section builder
        builder_map = {
            "portfolio_analytics": self._build_portfolio_analytics,
            "portfolio_performance": self._build_portfolio_analytics,
            "portfolio_analysis": self._build_portfolio_analytics,
            "portfolio_overview": self._build_portfolio_analytics,
            "credit_quality": self._build_credit_quality,
            "concentration_risk": self._build_concentration,
            "concentration_update": self._build_concentration,
            "stress_scenarios": self._build_stress,
            "covenant_analysis": self._build_covenants,
            "covenant_compliance": self._build_covenants,
            "risk_assessment": self._build_credit_quality,
            "risk_dashboard": self._build_credit_quality,
        }

        builder = builder_map.get(section_key)
        if builder is None:
            return {
                "metrics": [],
                "text": "",
                "charts_data": {},
                "available": True,
            }

        try:
            return builder(
                df, config, mult, display_ccy, snap_date,
                is_silq=is_silq, is_aajil=is_aajil, aux=aux,
                company=company, product=product,
            )
        except Exception as e:
            logger.error("Analytics bridge error for section '%s': %s",
                         section_key, e)
            return {
                "metrics": [],
                "text": f"Error computing analytics for {section_key}: {e}",
                "charts_data": {},
                "available": False,
            }

    def _get_summary_section_context(self, company: str, product: str,
                                     section_key: str,
                                     analysis_type: str) -> dict:
        """Build section context from pre-computed summary data (Ejari/Tamara)."""
        data = self._load_summary_data(company, product)
        if not data:
            return {
                "metrics": [],
                "text": f"No summary data available for {company}/{product}.",
                "charts_data": {},
                "available": False,
            }

        metrics = []
        text_parts = []

        if analysis_type == "tamara_summary":
            overview = data.get("overview", {})
            covenant = data.get("covenant_status", {})
            vp = data.get("vintage_performance", {})

            if section_key in ("portfolio_analytics", "portfolio_performance",
                               "portfolio_analysis", "portfolio_overview"):
                for key, label in [
                    ("total_outstanding_ar", "Outstanding AR"),
                    ("total_merchants", "Merchants"),
                    ("total_users", "Users"),
                    ("weighted_avg_dpd", "Weighted Avg DPD"),
                ]:
                    val = overview.get(key)
                    if val is not None:
                        metrics.append({"label": label, "value": str(val),
                                        "assessment": "neutral"})
                text_parts.append(
                    f"Tamara {product} portfolio overview with "
                    f"{len(overview)} key metrics available."
                )

            elif section_key in ("credit_quality", "risk_assessment",
                                 "risk_dashboard"):
                dpd = overview.get("weighted_avg_dpd")
                if dpd is not None:
                    assessment = "healthy" if float(dpd) < 30 else "warning"
                    metrics.append({"label": "Weighted Avg DPD",
                                    "value": f"{dpd} days",
                                    "assessment": assessment})
                text_parts.append(
                    "Credit quality assessment based on DPD metrics "
                    "and vintage cohort analysis."
                )

            elif section_key in ("covenant_analysis", "covenant_compliance"):
                triggers = covenant.get("triggers", {})
                if isinstance(triggers, dict):
                    for trigger_name, trigger_data in triggers.items():
                        if isinstance(trigger_data, dict):
                            status = trigger_data.get("status", "unknown")
                            metrics.append({
                                "label": trigger_name,
                                "value": status,
                                "assessment": (
                                    "healthy" if status == "compliant"
                                    else "warning"
                                ),
                            })
                elif isinstance(triggers, list):
                    for t in triggers:
                        name = t.get("name", t.get("trigger", "?"))
                        status = t.get("status", "unknown")
                        metrics.append({
                            "label": name,
                            "value": status,
                            "assessment": (
                                "healthy" if status in ("compliant", "holding")
                                else "warning"
                            ),
                        })
                text_parts.append(
                    f"Covenant compliance based on {len(triggers)} triggers."
                )

            elif section_key in ("concentration_risk", "concentration_update"):
                text_parts.append(
                    "Concentration analysis based on data room sources."
                )

        elif analysis_type == "ejari_summary":
            overview = data.get("portfolio_overview", {})
            kpis = overview.get("kpis", [])
            for kpi in kpis[:8]:
                if isinstance(kpi, dict):
                    metrics.append({
                        "label": kpi.get("label", ""),
                        "value": str(kpi.get("value", "")),
                        "assessment": "neutral",
                    })
            text_parts.append(
                f"Ejari portfolio overview with {len(kpis)} KPIs."
            )

        return {
            "metrics": metrics,
            "text": " ".join(text_parts) if text_parts else "",
            "charts_data": data,
            "available": True,
        }

    # ── Individual section builders (tape-based) ────────────────────────────

    def _build_portfolio_analytics(self, df, config, mult, ccy, snap_date,
                                   is_silq=False, is_aajil=False, **kw) -> dict:
        """Build portfolio analytics / performance section."""
        metrics = []
        charts_data = {}

        if is_silq:
            from core.analysis_silq import compute_silq_summary
            summary = compute_silq_summary(df, mult)
            charts_data["summary"] = summary
            metrics.extend([
                {"label": "Total Disbursed",
                 "value": _fmt_money(summary.get("total_disbursed"), ccy),
                 "assessment": "neutral"},
                {"label": "Total Deals",
                 "value": f"{summary.get('total_deals', 0):,}",
                 "assessment": "neutral"},
                {"label": "Collection Rate",
                 "value": _fmt_pct(summary.get("collection_rate")),
                 "assessment": (
                     "healthy" if (summary.get("collection_rate") or 0) > 80
                     else "warning"
                 )},
                {"label": "Delinquency Rate",
                 "value": _fmt_pct(summary.get("delinquency_rate")),
                 "assessment": (
                     "healthy" if (summary.get("delinquency_rate") or 0) < 10
                     else "warning"
                 )},
            ])
        elif is_aajil:
            from core.analysis_aajil import compute_aajil_summary
            aux = kw.get("aux")
            summary = compute_aajil_summary(df, mult, aux=aux)
            charts_data["summary"] = summary
            # Aajil returns rates as decimals (0.87), bridge expects percent (87)
            collection_pct = (summary.get("collection_rate") or 0) * 100
            metrics.extend([
                {"label": "GMV (Principal)",
                 "value": _fmt_money(summary.get("total_principal"), ccy),
                 "assessment": "neutral"},
                {"label": "Credit Transactions",
                 "value": f"{summary.get('total_deals', 0):,}",
                 "assessment": "neutral"},
                {"label": "Total Customers",
                 "value": f"{summary.get('total_customers', 0):,}",
                 "assessment": "neutral"},
                {"label": "Collection Rate",
                 "value": _fmt_pct(collection_pct),
                 "assessment": (
                     "healthy" if collection_pct > 80 else "warning"
                 )},
                {"label": "Outstanding",
                 "value": _fmt_money(summary.get("total_receivable"), ccy),
                 "assessment": "neutral"},
                {"label": "Written Off",
                 "value": f"{summary.get('written_off_count', 0):,} deals "
                          f"({_fmt_money(summary.get('total_written_off'), ccy)})",
                 "assessment": (
                     "healthy" if (summary.get('written_off_count') or 0) == 0
                     else "warning"
                 )},
            ])
        else:
            summary = compute_summary(
                df, config, ccy, snap_date, None
            )
            charts_data["summary"] = summary

            deploy = compute_deployment(df, mult)
            charts_data["deployment"] = deploy

            metrics.extend([
                {"label": "Face Value",
                 "value": _fmt_money(summary.get("total_purchase_value"), ccy),
                 "assessment": "neutral"},
                {"label": "Total Deals",
                 "value": f"{summary.get('total_deals', 0):,}",
                 "assessment": "neutral"},
                {"label": "Collection Rate",
                 "value": _fmt_pct(summary.get("collection_rate")),
                 "assessment": (
                     "healthy" if (summary.get("collection_rate") or 0) > 80
                     else "warning"
                 )},
                {"label": "Denial Rate",
                 "value": _fmt_pct(summary.get("denial_rate")),
                 "assessment": (
                     "healthy" if (summary.get("denial_rate") or 0) < 5
                     else "warning"
                 )},
                {"label": "Active Deals",
                 "value": f"{summary.get('active_deals', 0):,}",
                 "assessment": "neutral"},
                {"label": "Completed Deals",
                 "value": f"{summary.get('completed_deals', 0):,}",
                 "assessment": "neutral"},
            ])

        text = self.format_as_memo_block(
            {"metrics": metrics}, style="narrative"
        )
        return {
            "metrics": metrics,
            "text": text,
            "charts_data": charts_data,
            "available": True,
        }

    def _build_credit_quality(self, df, config, mult, ccy, snap_date,
                              is_silq=False, is_aajil=False, **kw) -> dict:
        """Build credit quality / risk section."""
        metrics = []
        charts_data = {}

        aux = kw.get("aux")

        # PAR / Delinquency
        if is_aajil:
            try:
                from core.analysis_aajil import compute_aajil_delinquency
                delq = compute_aajil_delinquency(df, mult, aux=aux)
                charts_data["delinquency"] = delq
                active_bal = delq.get("total_active_balance") or 0
                for bucket in delq.get("buckets", []):
                    # Aajil uses 'bucket' (label) and 'balance' (amount),
                    # no per-bucket pct — derive it from balance / active_bal.
                    label = bucket.get("bucket", "")
                    balance = bucket.get("balance", 0)
                    if not label or "Current" in label or active_bal == 0:
                        continue
                    pct = balance / active_bal * 100
                    metrics.append({
                        "label": label,
                        "value": _fmt_pct(pct),
                        "assessment": (
                            "healthy" if pct < 5
                            else "warning" if pct < 15
                            else "critical"
                        ),
                    })
            except Exception as e:
                logger.warning("Aajil delinquency computation failed: %s", e)
        elif not is_silq:
            try:
                par = compute_par(df, mult)
                charts_data["par"] = par
                if par.get("available"):
                    for bucket in ["par_30", "par_60", "par_90"]:
                        data = par.get(bucket, {})
                        pct = data.get("balance_pct", 0)
                        label = bucket.upper().replace("_", " ")
                        metrics.append({
                            "label": label,
                            "value": _fmt_pct(pct),
                            "assessment": (
                                "healthy" if pct < 5
                                else "warning" if pct < 15
                                else "critical"
                            ),
                        })
            except Exception as e:
                logger.warning("PAR computation failed: %s", e)

        # Loss waterfall
        try:
            if is_silq:
                from core.analysis_silq import compute_silq_cohort_loss_waterfall
                lw = compute_silq_cohort_loss_waterfall(df, mult)
            elif is_aajil:
                from core.analysis_aajil import compute_aajil_loss_waterfall
                lw = compute_aajil_loss_waterfall(df, mult, aux=aux)
            else:
                lw = compute_cohort_loss_waterfall(df, mult)
            charts_data["loss_waterfall"] = lw
            totals = lw.get("totals", {})
            if totals:
                net_loss_rate = totals.get("net_loss_rate", 0)
                metrics.append({
                    "label": "Net Loss Rate",
                    "value": _fmt_pct(net_loss_rate),
                    "assessment": (
                        "healthy" if (net_loss_rate or 0) < 2
                        else "warning" if (net_loss_rate or 0) < 5
                        else "critical"
                    ),
                })
                recovery_rate = totals.get("recovery_rate", 0)
                metrics.append({
                    "label": "Recovery Rate",
                    "value": _fmt_pct(recovery_rate),
                    "assessment": (
                        "healthy" if (recovery_rate or 0) > 50
                        else "warning"
                    ),
                })
        except Exception as e:
            logger.warning("Loss waterfall computation failed: %s", e)

        # Underwriting drift
        try:
            if is_silq:
                from core.analysis_silq import compute_silq_underwriting_drift
                drift = compute_silq_underwriting_drift(df, mult)
            elif is_aajil:
                from core.analysis_aajil import compute_aajil_underwriting
                drift = compute_aajil_underwriting(df, mult, aux=aux)
            else:
                drift = compute_underwriting_drift(df, mult)
            charts_data["underwriting_drift"] = drift
            vintages = drift.get("vintages", [])
            flagged = sum(1 for v in vintages if v.get("flags"))
            if vintages:
                metrics.append({
                    "label": "Vintages Flagged (Drift)",
                    "value": f"{flagged}/{len(vintages)}",
                    "assessment": (
                        "healthy" if flagged == 0
                        else "warning" if flagged <= 2
                        else "critical"
                    ),
                })
        except Exception as e:
            logger.warning("Underwriting drift computation failed: %s", e)

        text = self.format_as_memo_block(
            {"metrics": metrics}, style="narrative"
        )
        return {
            "metrics": metrics,
            "text": text,
            "charts_data": charts_data,
            "available": True,
        }

    def _build_concentration(self, df, config, mult, ccy, snap_date,
                             is_silq=False, is_aajil=False, **kw) -> dict:
        """Build concentration risk section."""
        metrics = []
        charts_data = {}

        try:
            if is_silq:
                from core.analysis_silq import compute_silq_concentration
                conc = compute_silq_concentration(df, mult)
            elif is_aajil:
                from core.analysis_aajil import compute_aajil_concentration
                conc = compute_aajil_concentration(df, mult, aux=kw.get("aux"))
            else:
                conc = compute_concentration(df, mult)
            charts_data["concentration"] = conc

            # HHI — Aajil returns flat `hhi_customer` (0-10000 scale).
            # Klaim/SILQ return `hhi: {hhi, classification}` dict.
            if is_aajil:
                hhi_val = conc.get("hhi_customer")
                if hhi_val is not None:
                    metrics.append({
                        "label": "HHI (Customer)",
                        "value": f"{hhi_val:,.0f}",
                        "assessment": (
                            "healthy" if hhi_val < 1500
                            else "warning" if hhi_val < 2500
                            else "critical"
                        ),
                    })
                # Top5/Top10 share are decimals (0-1); convert to percent
                t5 = (conc.get("top5_share") or 0) * 100
                t10 = (conc.get("top10_share") or 0) * 100
                if t5:
                    metrics.append({
                        "label": "Top 5 Customers",
                        "value": _fmt_pct(t5),
                        "assessment": (
                            "healthy" if t5 < 30
                            else "warning" if t5 < 50
                            else "critical"
                        ),
                    })
                if t10:
                    metrics.append({
                        "label": "Top 10 Customers",
                        "value": _fmt_pct(t10),
                        "assessment": (
                            "healthy" if t10 < 50
                            else "warning" if t10 < 70
                            else "critical"
                        ),
                    })
                top_customers = conc.get("top_customers", [])
                if top_customers:
                    top = top_customers[0]
                    top_pct = (top.get("share") or 0) * 100
                    metrics.append({
                        "label": "Top Customer",
                        "value": f"Customer {top.get('customer_id', '?')} "
                                 f"({_fmt_pct(top_pct)})",
                        "assessment": (
                            "healthy" if top_pct < 15
                            else "warning" if top_pct < 25
                            else "critical"
                        ),
                    })
            else:
                hhi_data = conc.get("hhi", {})
                hhi_val = hhi_data.get("hhi")
                if hhi_val is not None:
                    metrics.append({
                        "label": "HHI (Group)",
                        "value": f"{hhi_val:,.0f}",
                        "assessment": (
                            "healthy" if hhi_val < 1500
                            else "warning" if hhi_val < 2500
                            else "critical"
                        ),
                    })
                    classification = hhi_data.get("classification", "")
                    metrics.append({
                        "label": "Concentration",
                        "value": classification,
                        "assessment": (
                            "healthy" if classification == "unconcentrated"
                            else "warning" if classification == "moderate"
                            else "critical"
                        ),
                    })

                # Top groups (Klaim/SILQ)
                groups = conc.get("group", conc.get("shops", []))
                if groups:
                    top = groups[0] if groups else {}
                    top_name = top.get("group", top.get("shop", ""))
                    top_pct = top.get("percentage", top.get("pct", 0))
                    metrics.append({
                        "label": "Top Counterparty",
                        "value": f"{top_name} ({_fmt_pct(top_pct)})",
                        "assessment": (
                            "healthy" if (top_pct or 0) < 15
                            else "warning" if (top_pct or 0) < 25
                            else "critical"
                        ),
                    })
        except Exception as e:
            logger.warning("Concentration computation failed: %s", e)

        text = self.format_as_memo_block(
            {"metrics": metrics}, style="narrative"
        )
        return {
            "metrics": metrics,
            "text": text,
            "charts_data": charts_data,
            "available": True,
        }

    def _build_stress(self, df, config, mult, ccy, snap_date,
                      is_silq=False, is_aajil=False, **kw) -> dict:
        """Build stress scenarios section."""
        metrics = []
        charts_data = {}

        if is_silq:
            # SILQ does not have a dedicated stress test function;
            # use delinquency + covenants as proxy
            return {
                "metrics": [],
                "text": "Stress scenario analytics not available for SILQ. "
                        "Use delinquency and covenant data for risk assessment.",
                "charts_data": {},
                "available": False,
            }

        if is_aajil:
            # Aajil does not have a dedicated stress test;
            # concentration + loss waterfall carry the risk lens
            return {
                "metrics": [],
                "text": "Stress scenario analytics not available for Aajil. "
                        "Use concentration and loss waterfall data for risk assessment.",
                "charts_data": {},
                "available": False,
            }

        try:
            stress = compute_stress_test(df, mult)
            charts_data["stress_test"] = stress

            base_rate = stress.get("base_collection_rate", 0)
            metrics.append({
                "label": "Base Collection Rate",
                "value": _fmt_pct(base_rate),
                "assessment": "neutral",
            })

            scenarios = stress.get("scenarios", [])
            for sc in scenarios:
                name = sc.get("scenario", "")
                impact = sc.get("impact_pct", 0)
                metrics.append({
                    "label": f"Stress: {name}",
                    "value": _fmt_pct(impact),
                    "assessment": (
                        "healthy" if abs(impact or 0) < 3
                        else "warning" if abs(impact or 0) < 10
                        else "critical"
                    ),
                })
        except Exception as e:
            logger.warning("Stress test computation failed: %s", e)

        try:
            el = compute_expected_loss(df, mult)
            charts_data["expected_loss"] = el

            portfolio = el.get("portfolio", {})
            el_rate = portfolio.get("el_rate", 0)
            metrics.append({
                "label": "Expected Loss Rate",
                "value": _fmt_pct(el_rate),
                "assessment": (
                    "healthy" if (el_rate or 0) < 2
                    else "warning" if (el_rate or 0) < 5
                    else "critical"
                ),
            })
        except Exception as e:
            logger.warning("Expected loss computation failed: %s", e)

        text = self.format_as_memo_block(
            {"metrics": metrics}, style="narrative"
        )
        return {
            "metrics": metrics,
            "text": text,
            "charts_data": charts_data,
            "available": True,
        }

    def _build_covenants(self, df, config, mult, ccy, snap_date,
                         is_silq=False, is_aajil=False, **kw) -> dict:
        """Build covenant analysis section."""
        metrics = []
        charts_data = {}

        if is_aajil:
            # No facility covenants defined for Aajil yet (pre-facility stage)
            return {
                "metrics": [],
                "text": "No facility covenants defined for Aajil. "
                        "Covenant framework pending facility finalisation.",
                "charts_data": {},
                "available": False,
            }

        try:
            from core.portfolio import compute_covenants
            cov = compute_covenants(df, mult)
            charts_data["covenants"] = cov

            covenants = cov.get("covenants", [])
            compliant_count = sum(
                1 for c in covenants if c.get("status") == "compliant"
            )
            total = len(covenants)
            metrics.append({
                "label": "Covenant Compliance",
                "value": f"{compliant_count}/{total} compliant",
                "assessment": (
                    "healthy" if compliant_count == total
                    else "warning" if compliant_count > total * 0.5
                    else "critical"
                ),
            })

            for cov_item in covenants:
                name = cov_item.get("name", "")
                status = cov_item.get("status", "unknown")
                actual = cov_item.get("actual")
                threshold = cov_item.get("threshold")
                value_str = f"{actual}" if actual is not None else "--"
                if threshold is not None:
                    value_str += f" (threshold: {threshold})"
                metrics.append({
                    "label": name,
                    "value": value_str,
                    "assessment": (
                        "healthy" if status == "compliant" else "critical"
                    ),
                })
        except Exception as e:
            logger.warning("Covenant computation failed: %s", e)

        text = self.format_as_memo_block(
            {"metrics": metrics}, style="narrative"
        )
        return {
            "metrics": metrics,
            "text": text,
            "charts_data": charts_data,
            "available": True,
        }

    # ── Cross-company context (quarterly reviews) ───────────────────────────

    def get_cross_company_context(self, section_key: str) -> dict:
        """Pull analytics from ALL companies for quarterly review sections.

        Returns a dict keyed by company/product with analytics per section.
        """
        results = {}

        try:
            companies = get_companies()
        except Exception as e:
            logger.error("Failed to list companies: %s", e)
            return {"companies": {}, "available": False}

        for company in companies:
            try:
                products = get_products(company)
            except Exception:
                continue

            for product in products:
                key = f"{company}/{product}"
                ctx = self.get_section_context(
                    company, product, section_key
                )
                results[key] = ctx

        return {
            "companies": results,
            "available": bool(results),
            "company_count": len(results),
        }

    # ── Formatting ──────────────────────────────────────────────────────────

    def format_as_memo_block(self, context: dict,
                             style: str = "narrative") -> str:
        """Format analytics context into memo-ready text blocks.

        Styles:
          - narrative: flowing paragraph with inline metrics
          - bullet: bullet-point list of metrics
          - table: markdown-style table
        """
        metrics = context.get("metrics", [])
        if not metrics:
            return ""

        if style == "bullet":
            lines = []
            for m in metrics:
                assessment = m.get("assessment", "")
                marker = {
                    "healthy": "[OK]",
                    "warning": "[!]",
                    "critical": "[!!]",
                }.get(assessment, "[-]")
                lines.append(
                    f"  {marker} {m['label']}: {m['value']}"
                )
            return "\n".join(lines)

        if style == "table":
            header = "| Metric | Value | Assessment |"
            sep = "|--------|-------|------------|"
            rows = []
            for m in metrics:
                rows.append(
                    f"| {m['label']} | {m['value']} | "
                    f"{m.get('assessment', '')} |"
                )
            return "\n".join([header, sep] + rows)

        # Default: narrative
        parts = []
        for m in metrics:
            parts.append(f"{m['label']}: {m['value']}")
        if parts:
            return "Key metrics: " + "; ".join(parts) + "."
        return ""
