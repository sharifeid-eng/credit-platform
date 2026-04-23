from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import sys, os, json, re, subprocess, tempfile, pandas as pd
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.loader import get_companies, get_products, get_snapshots, load_snapshot, load_silq_snapshot
from core.config import load_config, SUPPORTED_CURRENCIES
from core.activity_log import log_activity, AI_COMMENTARY, AI_EXECUTIVE_SUMMARY, AI_TAB_INSIGHT, AI_CHAT, REPORT_GENERATED, COMPLIANCE_CERT, BREACH_NOTIFICATION, FACILITY_PARAMS_SAVED, DATAROOM_INGEST, MEMO_GENERATED, MEMO_EXPORTED, MIND_ENTRY_RECORDED, RESEARCH_QUERY, LEGAL_UPLOAD
from core.analysis import (
    compute_summary, compute_deployment, compute_deployment_by_product,
    compute_collection_velocity,
    compute_denial_trend, compute_cohorts, compute_actual_vs_expected,
    compute_ageing, compute_revenue, compute_concentration,
    compute_returns_analysis, apply_multiplier, filter_by_date,
    compute_dso, compute_hhi, compute_denial_funnel,
    compute_stress_test, compute_expected_loss, compute_loss_triangle,
    compute_group_performance,
    compute_collection_curves, compute_owner_breakdown, compute_vat_summary,
    compute_par, compute_dtfc,
    compute_cohort_loss_waterfall, compute_recovery_analysis,
    compute_vintage_loss_curves, compute_underwriting_drift,
    compute_segment_analysis, compute_collections_timing,
    compute_seasonality, compute_loss_categorization,
    compute_methodology_log, compute_hhi_for_snapshot,
    compute_cdr_ccr,
)
from core.migration import compute_roll_rates
from core.validation import validate_tape
from core.consistency import run_consistency_check
from core.reporter import generate_ai_analysis, save_pdf_report
from core.analysis_ejari import parse_ejari_workbook
from core.analysis_tamara import parse_tamara_data, get_tamara_summary_kpis
from core.analysis_aajil import (
    parse_aajil_data, get_aajil_summary,
    compute_aajil_summary, compute_aajil_traction, compute_aajil_delinquency,
    compute_aajil_collections, compute_aajil_cohorts, compute_aajil_concentration,
    compute_aajil_underwriting, compute_aajil_yield, compute_aajil_loss_waterfall,
    compute_aajil_customer_segments, compute_aajil_seasonality,
    filter_aajil_by_date,
)
from core.loader import load_aajil_snapshot
from core.validation_aajil import validate_aajil_tape
from core.analysis_silq import (
    compute_silq_summary, compute_silq_delinquency, compute_silq_collections,
    compute_silq_concentration, compute_silq_cohorts, compute_silq_yield,
    compute_silq_tenure, compute_silq_borrowing_base, compute_silq_covenants,
    compute_silq_seasonality, compute_silq_cohort_loss_waterfall, compute_silq_underwriting_drift,
    compute_silq_cdr_ccr,
    filter_silq_by_date,
)
from core.validation_silq import validate_silq_tape
from core.metric_registry import get_methodology, get_registry
from core.methodology_klaim import register_klaim_methodology
from core.methodology_silq import register_silq_methodology

# Register all methodology metadata at import time
register_klaim_methodology()
register_silq_methodology()
from core.portfolio import (
    compute_borrowing_base as portfolio_borrowing_base,
    compute_concentration_limits as portfolio_concentration_limits,
    compute_covenants as portfolio_covenants,
    compute_portfolio_flow,
    compute_klaim_borrowing_base,
    compute_klaim_concentration_limits,
    compute_klaim_covenants,
    annotate_covenant_eod,
)
from core.database import engine, get_db
from core.db_loader import (
    load_from_db, resolve_snapshot, list_snapshots,
    get_facility_config as db_facility_config,
)
from backend.integration import router as integration_router
from core.dataroom.engine import DataRoomEngine
from core.dataroom.analytics_snapshot import AnalyticsSnapshotEngine
from core.mind import MasterMind, CompanyMind, build_mind_context
from core.research.dual_engine import DualResearchEngine
from core.memo.templates import MEMO_TEMPLATES, get_template, list_templates
from core.memo.generator import MemoGenerator
from core.memo.storage import MemoStorage
from core.memo.pdf_export import export_memo_pdf
from fastapi import Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager


import logging
logger = logging.getLogger("laith")


# Optional runtime dependencies whose absence causes SILENT feature degradation.
# When any of these is missing, the platform still starts — but a feature
# (PDF text, DOCX parsing, TF-IDF search, legal extraction) becomes a no-op
# with only a deep-in-the-call-stack fallback. The probe below fails LOUDLY at
# startup and persists the result to data/_platform_health.json so the operator
# center and /dataroom/health can surface it without requiring a restart.
_OPTIONAL_DEPS = [
    ("pdfplumber", "Data room PDF text + table extraction"),
    ("docx", "Data room DOCX parsing (python-docx)"),
    ("sklearn.feature_extraction.text", "TF-IDF search index (scikit-learn)"),
    ("pymupdf4llm", "Legal PDF → markdown conversion"),
    ("fitz", "Legal PDF page extraction (pymupdf)"),
]


def _probe_optional_deps() -> dict:
    """Import-check every optional runtime dependency, log + persist result.

    Returns the health dict (also written to data/_platform_health.json).
    """
    import importlib
    from pathlib import Path as _Path

    present: list[dict] = []
    missing: list[dict] = []
    for mod_name, purpose in _OPTIONAL_DEPS:
        try:
            importlib.import_module(mod_name)
            present.append({"module": mod_name, "purpose": purpose})
        except ImportError as e:
            logger.error(
                "[startup] MISSING OPTIONAL DEPENDENCY: %s — %s (feature will silently degrade). ImportError: %s",
                mod_name, purpose, e,
            )
            missing.append({"module": mod_name, "purpose": purpose, "error": str(e)})

    health = {
        "checked_at": datetime.now().isoformat()[:19],
        "present": present,
        "missing": missing,
        "status": "ok" if not missing else "degraded",
    }

    try:
        data_root = _Path(__file__).resolve().parent.parent / "data"
        data_root.mkdir(parents=True, exist_ok=True)
        with open(data_root / "_platform_health.json", "w", encoding="utf-8") as f:
            json.dump(health, f, indent=2)
    except OSError as e:
        logger.warning("[startup] Could not write _platform_health.json: %s", e)

    if missing:
        logger.error(
            "[startup] %d optional dependency/dependencies missing — feature loss. "
            "Install via `pip install -r backend/requirements.txt` inside the backend container.",
            len(missing),
        )
    else:
        logger.info("[startup] All %d optional runtime dependencies present.", len(present))

    return health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Probe optional runtime dependencies FIRST so missing packages are loud
    # in the startup log even if DB/listener/tool registration fails later.
    _probe_optional_deps()

    if engine:
        try:
            from sqlalchemy import text as sa_text
            with engine.connect() as conn:
                conn.execute(sa_text("SELECT 1"))
            logger.info("Database connected.")
            # Bootstrap first admin user if users table is empty
            from backend.cf_auth import bootstrap_admin
            bootstrap_admin()
        except Exception as e:
            logger.warning("Database connection failed: %s. Running in tape-only mode.", e)
    else:
        logger.info("No DATABASE_URL configured. Running in tape-only mode.")

    # Register Intelligence System event listeners
    from core.mind.listeners import register_all_listeners
    register_all_listeners()

    # Register agent tools
    try:
        from core.agents.tools import register_all_tools
        register_all_tools()
        logger.info("Agent tools registered.")
    except Exception as e:
        logger.warning("Agent tool registration failed: %s. Agents unavailable.", e)

    yield


app = FastAPI(title="ACP Private Credit API", lifespan=lifespan)
app.include_router(integration_router)

from backend.legal import router as legal_router
app.include_router(legal_router)

from backend.operator import router as operator_router
app.include_router(operator_router)

from backend.auth_routes import router as auth_router
app.include_router(auth_router)

from backend.intelligence import router as intelligence_router
app.include_router(intelligence_router)

from backend.external import router as external_router
app.include_router(external_router)

from backend.agents import router as agents_router
app.include_router(agents_router, prefix="/agents", tags=["agents"])


@app.get("/health")
async def health_check():
    """Unauthenticated health check for deploy scripts and monitoring."""
    return {"status": "ok"}

from backend.onboarding import router as onboarding_router
app.include_router(onboarding_router)

# Auth middleware — must be added BEFORE CORSMiddleware (Starlette processes
# middleware in reverse order, so CORS runs first, then auth)
from backend.cf_auth import CloudflareAuthMiddleware
app.add_middleware(CloudflareAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_tape_events_fired: set = set()


def _validate_path_param(value: str, name: str):
    """Reject path traversal attempts in company/product parameters."""
    if value and ('..' in value or '/' in value or '\\' in value or '\x00' in value):
        raise HTTPException(status_code=400, detail=f"Invalid {name}: '{value}'")


# Tape loading cache — avoids parsing the same file 25x per page load
from collections import OrderedDict as _OrderedDict

class _TapeCache(_OrderedDict):
    """LRU cache for loaded tape DataFrames (max 10 entries)."""
    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > 10:
            self.popitem(last=False)

_tape_cache = _TapeCache()


_SNAPSHOT_EXTS = ('.csv', '.xlsx', '.ods', '.json')


def _strip_snapshot_ext(name: str) -> str:
    for ext in _SNAPSHOT_EXTS:
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _match_snapshot(snaps, snapshot):
    """Resolve a snapshot identifier against the filesystem snapshot list.

    `snapshot=None` preserves the caller-has-no-preference default: return
    latest. Any non-empty identifier must resolve exactly — filename, then
    extension-stripped filename (the DB `/snapshots` endpoint returns names
    without extension while filesystem names carry one), then single-date
    match. A non-matching identifier raises HTTP 400. NEVER silently falls
    back to latest on mismatch — that previously masked a silent
    data-correctness bug where analysts thought they were viewing an older
    snapshot but got the latest tape.
    """
    if not snapshot:
        return snaps[-1]
    for s in snaps:
        if s['filename'] == snapshot:
            return s
    snap_stripped = _strip_snapshot_ext(snapshot)
    for s in snaps:
        if _strip_snapshot_ext(s['filename']) == snap_stripped:
            return s
    date_matches = [s for s in snaps if s['date'] == snapshot]
    if len(date_matches) == 1:
        return date_matches[0]
    if len(date_matches) > 1:
        names = [s['filename'] for s in date_matches]
        raise HTTPException(status_code=400, detail=f"Ambiguous snapshot date '{snapshot}' matches {len(date_matches)} files: {', '.join(names)}. Please specify by filename.")
    available = ', '.join(s['filename'] for s in snaps)
    raise HTTPException(status_code=400, detail=f"Snapshot '{snapshot}' not found for this product. Available: {available}")


def _load(company, product, snapshot):
    """Load and return the selected snapshot DataFrame + snapshot metadata."""
    _validate_path_param(company, "company")
    _validate_path_param(product, "product")
    snaps = get_snapshots(company, product)
    if not snaps:
        raise HTTPException(status_code=404, detail="No snapshots found")
    sel = _match_snapshot(snaps, snapshot)
    # Cache loaded tapes to avoid re-parsing the same file per page load
    _cache_key = sel['filepath']
    if _cache_key in _tape_cache:
        df = _tape_cache[_cache_key].copy()
    else:
        df = load_snapshot(sel['filepath'])
        _tape_cache[_cache_key] = df
        df = df.copy()  # Return a copy so downstream mutations don't corrupt cache

    # Fire TAPE_INGESTED event (once per unique tape per session)
    _key = (company, product, sel['filename'])
    if _key not in _tape_events_fired:
        _tape_events_fired.add(_key)
        try:
            from core.mind.event_bus import event_bus, Events
            # Extract basic metrics for intelligence listeners
            _metrics = {}
            try:
                _metrics["total_deals"] = len(df)
                if "Purchase value" in df.columns:
                    _metrics["total_purchase_value"] = float(df["Purchase value"].sum())
                if "Collected till date" in df.columns:
                    _metrics["total_collected"] = float(df["Collected till date"].sum())
                    if _metrics.get("total_purchase_value"):
                        _metrics["collection_rate"] = round(_metrics["total_collected"] / _metrics["total_purchase_value"] * 100, 2)
                if "Denied by insurance" in df.columns:
                    _metrics["total_denied"] = float(df["Denied by insurance"].sum())
                    if _metrics.get("total_purchase_value"):
                        _metrics["denial_rate"] = round(_metrics["total_denied"] / _metrics["total_purchase_value"] * 100, 2)
                if "Pending insurance response" in df.columns:
                    _metrics["total_pending"] = float(df["Pending insurance response"].sum())
                    if _metrics.get("total_purchase_value"):
                        _metrics["pending_rate"] = round(_metrics["total_pending"] / _metrics["total_purchase_value"] * 100, 2)
                if "Status" in df.columns:
                    _metrics["active_deals"] = int((df["Status"] == "Executed").sum())
                    _metrics["completed_deals"] = int((df["Status"] == "Completed").sum())
                if "Discount" in df.columns:
                    _metrics["avg_discount"] = round(float(df["Discount"].mean() * 100), 2)
                # SILQ columns
                if "Disbursed_Amount (SAR)" in df.columns:
                    _metrics["total_purchase_value"] = float(df["Disbursed_Amount (SAR)"].sum())
                if "Repaid_Amount" in df.columns:
                    _metrics["total_collected"] = float(df["Repaid_Amount"].sum())
                    if _metrics.get("total_purchase_value"):
                        _metrics["collection_rate"] = round(_metrics["total_collected"] / _metrics["total_purchase_value"] * 100, 2)
            except Exception:
                pass  # Metrics extraction is best-effort
            event_bus.publish(Events.TAPE_INGESTED, {
                "company": company,
                "product": product,
                "snapshot": sel['filename'],
                "metrics": _metrics,
            })
        except Exception:
            pass

    return df, sel

def _currency(company, product, requested):
    config = load_config(company, product)
    return config, requested or (config['currency'] if config else 'USD')

def _integrity_dir(company, product):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reports', f'{company}_{product}')
    os.makedirs(base, exist_ok=True)
    return base

def _integrity_path(company, product, snap_old, snap_new, suffix=''):
    # Sanitize snapshot names for filenames (replace problematic chars)
    safe_old = snap_old.replace('/', '_').replace('\\', '_')
    safe_new = snap_new.replace('/', '_').replace('\\', '_')
    return os.path.join(_integrity_dir(company, product), f'{safe_old}__vs__{safe_new}{suffix}.json')

# ── AI Response Cache ─────────────────────────────────────────────────────────

import hashlib

def _ai_cache_dir():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reports', 'ai_cache')
    os.makedirs(base, exist_ok=True)
    return base

def _ai_cache_key(endpoint: str, company: str, product: str,
                  snapshot: str = '', as_of_date: str = '', tab: str = '',
                  snapshot_date: str = '', currency: str = '') -> str:
    """Build a deterministic cache filename from request parameters.
    as_of_date is normalized: if it's empty or >= snapshot_date, it maps
    to the same key (all mean 'use all data from this tape')."""
    # Normalize: treat None/empty/snapshot_date/future as the same "full tape" state
    norm_aod = ''
    if as_of_date and snapshot_date and as_of_date < snapshot_date:
        norm_aod = as_of_date  # genuinely backdated — different data slice
    raw = f"{endpoint}|{company}|{product}|{snapshot}|{norm_aod}|{tab}|{currency}"
    # Include file mtime to invalidate cache when same-name file is replaced
    try:
        from core.loader import get_snapshots
        snaps = get_snapshots(company, product)
        snap_file = next((s for s in snaps if s['filename'] == snapshot), None)
        if snap_file and os.path.exists(snap_file['filepath']):
            mtime = str(int(os.path.getmtime(snap_file['filepath'])))
            raw += f"|{mtime}"
    except Exception:
        pass  # graceful fallback — cache works without mtime
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    safe = f"{company}_{product}_{endpoint}"
    if tab:
        safe += f"_{tab}"
    if snapshot:
        safe_snap = snapshot.replace('/', '_').replace('\\', '_').replace('.', '_')
        safe += f"_{safe_snap}"
    # Append hash to guarantee uniqueness
    return os.path.join(_ai_cache_dir(), f"{safe}_{h}.json")

def _ai_cache_get(cache_path: str) -> dict | None:
    """Return cached AI response or None if not cached."""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None

def _ai_cache_put(cache_path: str, data: dict) -> None:
    """Write AI response to disk cache."""
    data['cached'] = True
    data['cached_at'] = datetime.now().isoformat()
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except OSError:
        pass  # Silently fail — caching is best-effort


def _parse_agent_exec_summary_response(response_text: str):
    """Parse the analyst agent's executive-summary text into
    (narrative, findings, analytics_coverage, ok).

    The agent is prompted to return a JSON object with ``narrative`` +
    ``findings`` (required) and an optional ``analytics_coverage`` callout
    string. Sometimes preambles conversational text ("I now have comprehensive
    data…") or wraps in ```json fences. Tries, in order:
      1. Strip whitespace + ```json/``` fences, then json.loads the whole text.
      2. Extract the outermost ``{…}`` substring, then json.loads that.
      3. Fall back to a single "Summary generated (unparsed)" warning finding
         carrying the raw text, so the analyst sees what came back.

    Legacy list-shape responses (bare findings array) are accepted as
    findings-only (no narrative, no analytics_coverage).

    Returns a 4-tuple for backward compatibility, but callers written before
    2026-04-22 that unpack 3 values will get a TypeError — acceptable because
    all call sites live in this file.
    """
    text = (response_text or "").strip()
    if not text:
        return None, [], None, False

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                parsed = None

    if isinstance(parsed, list):
        return None, parsed, None, True
    if isinstance(parsed, dict):
        # analytics_coverage is optional — pass through verbatim if present and
        # non-empty. Filter out empty strings and whitespace-only placeholders
        # so the frontend doesn't render a blank callout.
        coverage = parsed.get("analytics_coverage")
        if isinstance(coverage, str):
            coverage = coverage.strip() or None
        else:
            coverage = None
        return parsed.get("narrative"), parsed.get("findings", []), coverage, True

    return None, [{
        "rank": 1, "severity": "warning",
        "title": "Summary generated (unparsed)",
        "explanation": response_text or "(empty response)",
        "data_points": [], "tab": "overview",
    }], None, False


def _extract_questions(text):
    """Extract numbered questions from AI analysis text."""
    questions = []
    in_questions = False
    for line in text.split('\n'):
        stripped = line.strip()
        if 'QUESTIONS FOR THE COMPANY' in stripped.upper():
            in_questions = True
            continue
        if in_questions:
            # Stop at next section header
            if stripped and (stripped.isupper() and len(stripped) > 10) or stripped.startswith('4.') and 'RECOMMENDED' in stripped.upper():
                break
            # Extract numbered questions
            m = re.match(r'^\d+[\.\)]\s*(.+)', stripped)
            if m:
                questions.append(m.group(1).strip())
    return questions

def _get_analysis_type(company, product):
    """Return the analysis_type from config, defaulting to 'klaim'."""
    config = load_config(company, product)
    return (config or {}).get('analysis_type', 'klaim')

def _resolve_snapshot(company, product, snapshot):
    """Resolve the selected snapshot metadata dict."""
    snaps = get_snapshots(company, product)
    if not snaps:
        raise HTTPException(status_code=404, detail="No snapshots found")
    return _match_snapshot(snaps, snapshot)

def _silq_load(company, product, snapshot, as_of_date, currency):
    """Load SILQ data (multi-sheet) with currency multiplier applied.
    Returns (df, sel, config, disp, mult, commentary_text, ref_date)."""
    sel = _resolve_snapshot(company, product, snapshot)
    df, commentary_text = load_silq_snapshot(sel['filepath'])
    df = filter_silq_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    # DPD reference date: as-of date if set, otherwise snapshot date
    ref_date = pd.to_datetime(as_of_date) if as_of_date else pd.to_datetime(sel['date'])
    return df, sel, config, disp, mult, commentary_text, ref_date

# ── Framework endpoint ─────────────────────────────────────────────────────────

@app.get("/framework")
def get_framework():
    """Return the analysis framework markdown document."""
    framework_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core', 'ANALYSIS_FRAMEWORK.md')
    try:
        with open(framework_path, 'r', encoding='utf-8') as f:
            return {'content': f.read()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Framework document not found")

# ── Methodology endpoints ─────────────────────────────────────────────────────

@app.get("/methodology/{analysis_type}")
def get_methodology_endpoint(analysis_type: str):
    """Return structured methodology data for an analysis type.
    Auto-generated from decorated compute functions + static sections."""
    # For Ejari and Tamara (read-only summaries), serve static JSON
    if analysis_type == 'ejari_summary':
        ejari_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'Ejari', 'RNPL', 'methodology.json'
        )
        if os.path.exists(ejari_path):
            with open(ejari_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="Ejari methodology not found")

    if analysis_type == 'tamara_summary':
        # Try KSA first, then UAE
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for product in ['KSA', 'UAE']:
            mpath = os.path.join(base, 'data', 'Tamara', product, 'methodology.json')
            if os.path.exists(mpath):
                with open(mpath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        raise HTTPException(status_code=404, detail="Tamara methodology not found")

    if analysis_type == 'aajil':
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mpath = os.path.join(base, 'data', 'Aajil', 'KSA', 'methodology.json')
        if os.path.exists(mpath):
            with open(mpath, 'r', encoding='utf-8') as f:
                return json.load(f)
        raise HTTPException(status_code=404, detail="Aajil methodology not found")

    result = get_methodology(analysis_type)
    if not result['sections']:
        raise HTTPException(status_code=404, detail=f"No methodology registered for: {analysis_type}")
    return result


@app.get("/methodology-registry")
def get_methodology_registry():
    """Return the raw function registry for auditing and framework Section 12 generation."""
    return get_registry()

# ── FX rates endpoint ──────────────────────────────────────────────────────────

@app.get("/fx-rates")
def get_fx_rates_endpoint():
    """Return current FX rates and source (live or fallback)."""
    from core.config import get_fx_rates, get_fx_source
    return {'rates': get_fx_rates(), 'source': get_fx_source()}

@app.get("/aggregate-stats")
def get_aggregate_stats():
    """
    Aggregate stats across ALL snapshots for all companies.
    Cached to disk — only recomputes when snapshot file list changes.
    - total_face_value_usd: sum of latest-snapshot face values, USD-normalised (no double-count)
    - total_deals: all deal rows across all snapshots (processing volume)
    - total_data_points: sum of rows × columns per snapshot (raw scale)
    - total_snapshots: count of tape files
    - total_companies: count of active companies (excl. ejari_summary)
    """
    from pathlib import Path
    from core.config import get_fx_rates

    REPORTS = Path("reports")
    REPORTS.mkdir(exist_ok=True)
    cache_path = REPORTS / "aggregate_stats_cache.json"

    # FX fallback rates (AED, SAR → USD)
    rates = get_fx_rates()
    FX = {'AED': rates.get('AED', 0.2723), 'SAR': rates.get('SAR', 0.2667)}

    # Schema version — bump this whenever the stats fields change
    STATS_SCHEMA_VERSION = "7"  # v7: face_value_column from config.json (no more hardcoded column names)

    # Build fingerprint from schema version + all snapshot filenames
    all_snap_ids = [f"schema:{STATS_SCHEMA_VERSION}"]
    for co in get_companies():
        for prod in get_products(co):
            for s in get_snapshots(co, prod):
                all_snap_ids.append(f"{co}/{prod}/{s['filename']}")
    fingerprint = sorted(all_snap_ids)

    # Cache hit?
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if cached.get('fingerprint') == fingerprint:
                return cached['stats']
        except Exception:
            pass

    # Recompute
    total_value_usd  = 0.0
    total_deals      = 0
    total_data_points = 0
    snapshot_count   = 0
    company_set      = set()

    for co in get_companies():
        for prod in get_products(co):
            cfg           = load_config(co, prod) or {}
            analysis_type = cfg.get('analysis_type', 'klaim')
            currency      = cfg.get('currency', 'USD')
            fx            = FX.get(currency, 1.0)

            snaps = get_snapshots(co, prod)
            company_set.add(co)

            for i, snap in enumerate(snaps):
                snapshot_count += 1

                if analysis_type == 'ejari_summary':
                    # ODS workbook — extract deal count + data points from all sheets
                    try:
                        import pandas as pd
                        xls = pd.ExcelFile(snap['filepath'], engine='odf')
                        for sheet in xls.sheet_names:
                            df_sheet = pd.read_excel(xls, sheet_name=sheet, header=None)
                            total_data_points += df_sheet.shape[0] * df_sheet.shape[1]
                        # Deal count + face value from Portfolio_Overview
                        from core.analysis_ejari import parse_ejari_workbook
                        parsed = parse_ejari_workbook(snap['filepath'])
                        km = parsed.get('portfolio_overview', {}).get('key_metrics', {})
                        contracts = km.get('total_contracts')
                        funded    = km.get('total_funded')
                        if contracts is not None:
                            total_deals += int(str(contracts).replace(',', '').strip())
                        # Only add face value from latest snapshot
                        if i == len(snaps) - 1 and funded is not None:
                            total_value_usd += float(str(funded).replace(',', '').strip())
                    except Exception:
                        pass
                    continue

                if analysis_type == 'tamara_summary':
                    # Tamara has outstanding AR (point-in-time), NOT total originated.
                    # Do NOT add to total_value_usd (which is "Face Value Analyzed" = originated).
                    # Only count data points and vintage records.
                    try:
                        import json as _json
                        with open(snap['filepath'], 'r', encoding='utf-8') as _f:
                            tdata = _json.load(_f)
                        fdd = tdata.get('deloitte_fdd', {})
                        ts = fdd.get('dpd_timeseries', [])
                        total_data_points += len(ts) * 12  # ~12 DPD buckets per month
                        # NOT adding to total_value_usd — outstanding != originated
                        vp = tdata.get('vintage_performance', {})
                        for metric_data in vp.values():
                            if isinstance(metric_data, dict):
                                for product_records in metric_data.values():
                                    if isinstance(product_records, list):
                                        total_deals += len(product_records)
                                        total_data_points += sum(len(r) for r in product_records)
                    except Exception:
                        pass
                    continue

                try:
                    if analysis_type == 'silq':
                        df, _ = load_silq_snapshot(snap['filepath'])
                    else:
                        df = load_snapshot(snap['filepath'])
                    total_deals       += len(df)
                    total_data_points += len(df) * len(df.columns)

                    # Face value only from latest snapshot to avoid double-counting deals
                    if i == len(snaps) - 1:
                        val_col = cfg.get('face_value_column', 'Purchase value')
                        if val_col in df.columns:
                            total_value_usd += float(df[val_col].sum()) * fx
                except Exception:
                    pass

    stats = {
        'total_face_value_usd':  round(total_value_usd),
        'total_deals':           total_deals,
        'total_data_points':     total_data_points,
        'total_snapshots':       snapshot_count,
        'total_companies':       len(company_set),
    }

    cache_path.write_text(json.dumps({
        'fingerprint':  fingerprint,
        'stats':        stats,
        'computed_at':  datetime.now().isoformat(),
    }))
    return stats


@app.get("/api/platform-stats")
def get_platform_stats():
    """
    Live platform capability stats for the /architecture page and Resources cards.

    Everything is computed on request — no caching — so numbers are always
    current. If this grows expensive we can add fingerprint-based caching like
    /aggregate-stats, but the counts here are cheap (directory/route walks).
    """
    from pathlib import Path
    import re

    project_root = Path(__file__).resolve().parent.parent

    # ── Routes (endpoint count by prefix) ──────────────────────────────────
    route_groups = {
        'tape': 0, 'portfolio': 0, 'legal': 0, 'research': 0,
        'memo': 0, 'intelligence': 0, 'integration': 0, 'operator': 0,
        'auth': 0, 'agents': 0, 'dataroom': 0, 'other': 0,
    }
    total_routes = 0
    for route in app.routes:
        path = getattr(route, 'path', '')
        if not path or path.startswith('/openapi') or path == '/docs' or path == '/redoc':
            continue
        total_routes += 1
        if '/legal' in path:
            route_groups['legal'] += 1
        elif '/portfolio' in path:
            route_groups['portfolio'] += 1
        elif '/memos' in path or '/memo-templates' in path:
            route_groups['memo'] += 1
        elif '/api/integration' in path:
            route_groups['integration'] += 1
        elif '/operator' in path:
            route_groups['operator'] += 1
        elif '/auth' in path:
            route_groups['auth'] += 1
        elif '/agents' in path:
            route_groups['agents'] += 1
        elif '/dataroom' in path:
            route_groups['dataroom'] += 1
        elif '/research' in path:
            route_groups['research'] += 1
        elif '/thesis' in path or '/knowledge' in path or '/mind' in path:
            route_groups['intelligence'] += 1
        elif '/charts/' in path or '/summary' in path or '/ai-' in path or '/companies/' in path:
            route_groups['tape'] += 1
        else:
            route_groups['other'] += 1

    # ── Companies & products ───────────────────────────────────────────────
    companies_list = []
    total_products = 0
    total_snapshots_all = 0
    total_dataroom_docs = 0
    total_legal_docs = 0
    for co in get_companies():
        if co.startswith('_'):
            continue
        prods = get_products(co)
        total_products += len(prods)
        snaps_co = 0
        for p in prods:
            snaps_co += len(get_snapshots(co, p))
        total_snapshots_all += snaps_co

        legal_dir = project_root / 'data' / co / 'legal'
        legal_count = 0
        if legal_dir.is_dir():
            legal_count = len([f for f in os.listdir(legal_dir) if f.lower().endswith('.pdf')])
            total_legal_docs += legal_count

        dataroom_registry = project_root / 'data' / co / 'dataroom' / 'registry.json'
        dataroom_count = 0
        if dataroom_registry.exists():
            try:
                with open(dataroom_registry) as f:
                    reg = json.load(f)
                dataroom_count = len(reg) if isinstance(reg, (dict, list)) else 0
                total_dataroom_docs += dataroom_count
            except Exception:
                pass

        cfg = load_config(co, prods[0]) if prods else {}
        companies_list.append({
            'name': co,
            'products': prods,
            'analysis_type': cfg.get('analysis_type') if cfg else None,
            'snapshots': snaps_co,
            'legal_docs': legal_count,
            'dataroom_docs': dataroom_count,
        })

    # ── Mind / Knowledge ───────────────────────────────────────────────────
    mind_entries = 0
    master_mind_dir = project_root / 'data' / '_master_mind'
    if master_mind_dir.is_dir():
        for jf in master_mind_dir.glob('*.jsonl'):
            try:
                mind_entries += sum(1 for line in open(jf) if line.strip())
            except Exception:
                pass
    for co_entry in companies_list:
        co_mind = project_root / 'data' / co_entry['name'] / 'mind'
        if co_mind.is_dir():
            for jf in co_mind.glob('*.jsonl'):
                try:
                    mind_entries += sum(1 for line in open(jf) if line.strip())
                except Exception:
                    pass

    # ── Framework sections ─────────────────────────────────────────────────
    framework_path = project_root / 'core' / 'ANALYSIS_FRAMEWORK.md'
    framework_sections = 0
    framework_mtime = None
    if framework_path.exists():
        try:
            content = framework_path.read_text(encoding='utf-8')
            framework_sections = len(re.findall(r'^## \d+\.', content, re.MULTILINE))
            framework_mtime = datetime.fromtimestamp(framework_path.stat().st_mtime).isoformat()
        except Exception:
            pass

    # ── Methodology pages (registered analysis types + static files) ──────
    methodology_count = 0
    try:
        reg = get_registry()
        methodology_count += len(reg)  # one page per analysis_type with registered metrics
    except Exception:
        pass
    # Static methodology files
    for static_path in [
        project_root / 'data' / 'Ejari' / 'RNPL' / 'methodology.json',
    ]:
        if static_path.exists():
            methodology_count += 1

    # ── Tests & source files ───────────────────────────────────────────────
    tests_count = 0
    tests_dir = project_root / 'tests'
    if tests_dir.is_dir():
        # Match: "def test_", "    def test_" (class-indented), "async def test_"
        test_pattern = re.compile(r'^\s*(?:async\s+)?def\s+test_', re.MULTILINE)
        for pyf in tests_dir.rglob('test_*.py'):
            try:
                content = pyf.read_text(encoding='utf-8', errors='ignore')
                tests_count += len(test_pattern.findall(content))
            except Exception:
                pass

    # ── Memos ──────────────────────────────────────────────────────────────
    memo_count = 0
    memos_dir = project_root / 'reports' / 'memos'
    if memos_dir.is_dir():
        for memo_sub in memos_dir.iterdir():
            if memo_sub.is_dir():
                # Count distinct memos (folders with meta.json)
                if (memo_sub / 'meta.json').exists():
                    memo_count += 1

    # ── DB tables (7 known — introspect for live count) ────────────────────
    db_tables = 0
    try:
        from core.models import Base as ModelBase
        db_tables = len(ModelBase.metadata.tables)
    except Exception:
        pass

    # ── AI tiers (from ai_client) ──────────────────────────────────────────
    ai_tiers = ['structured', 'research', 'judgment', 'polish', 'auto']

    # ── Agents: definitions + tools + sessions ─────────────────────────────
    agents_list = []
    agent_defs_dir = project_root / 'core' / 'agents' / 'definitions'
    if agent_defs_dir.is_dir():
        for agent_dir in agent_defs_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            config_path = agent_dir / 'config.json'
            if not config_path.exists():
                continue
            try:
                with open(config_path) as f:
                    agent_cfg = json.load(f)
                agents_list.append({
                    'name': agent_dir.name,
                    'model': agent_cfg.get('model', ''),
                    'tool_patterns': agent_cfg.get('tools', []),
                    'max_turns': agent_cfg.get('max_turns'),
                })
            except Exception:
                pass

    # Tool count — introspect the registry after register_all_tools() has
    # fired at app startup. If registration failed, this safely returns 0.
    tool_count = 0
    try:
        from core.agents.tools import registry as _tool_registry
        tool_count = len(_tool_registry.tool_names())
    except Exception:
        pass

    # Session count — JSON files in data/_agent_sessions/ (see
    # core/agents/session.py). Each file is one multi-turn session.
    sessions_count = 0
    sessions_dir = project_root / 'data' / '_agent_sessions'
    if sessions_dir.is_dir():
        try:
            sessions_count = sum(1 for _ in sessions_dir.glob('*.json'))
        except Exception:
            pass

    return {
        'generated_at': datetime.now().isoformat(),
        'companies': companies_list,
        'agents': agents_list,
        'totals': {
            'companies': len(companies_list),
            'products': total_products,
            'snapshots': total_snapshots_all,
            'routes': total_routes,
            'db_tables': db_tables,
            'mind_entries': mind_entries,
            'framework_sections': framework_sections,
            'methodology_pages': methodology_count,
            'dataroom_docs': total_dataroom_docs,
            'legal_docs': total_legal_docs,
            'tests': tests_count,
            'memos': memo_count,
            'ai_tiers': len(ai_tiers),
            'agents': len(agents_list),
            'agent_tools': tool_count,
            'agent_sessions': sessions_count,
        },
        'routes_by_group': route_groups,
        'framework_last_modified': framework_mtime,
    }


# ── Company / Product / Snapshot endpoints ────────────────────────────────────

@app.get("/companies")
def list_companies():
    result = []
    for co in get_companies():
        ps = get_products(co)
        all_snaps = [s for p in ps for s in get_snapshots(co, p)]
        all_snaps.sort(key=lambda s: s['date'] or '0000-00-00')
        since = all_snaps[0]['date'] if all_snaps else None
        result.append({
            'name': co,
            'products': ps,
            'total_snapshots': len(all_snaps),
            'since': since,
        })
    return result

@app.get("/companies/{company}/products")
def list_products(company: str):
    ps = get_products(company)
    if not ps:
        raise HTTPException(status_code=404, detail=f"No products found for {company}")
    return ps

@app.get("/companies/{company}/products/{product}/snapshots")
def list_product_snapshots(company: str, product: str, db: Session = Depends(get_db)):
    """List snapshots for a product.

    For tape-ingested types (klaim, silq): reads from DB (`snapshots` table).
    For non-tape types (ejari_summary, tamara_summary, aajil): reads the
    pre-computed file from disk. Response shape preserves `filename` + `date`
    for frontend back-compat; `source` and `row_count` added for DB-sourced rows.
    """
    at = _get_analysis_type(company, product)
    if at in ('klaim', 'silq') and db is not None:
        snaps = list_snapshots(db, company, product)
        return [
            {'filename': s['filename'], 'date': s['date'],
             'source': s['source'], 'row_count': s['row_count']}
            for s in snaps
        ]
    # Non-tape types keep the filesystem listing
    return [{'filename': s['filename'], 'date': s['date']}
            for s in get_snapshots(company, product)]

@app.get("/companies/{company}/products/{product}/config")
def get_product_config(company: str, product: str):
    config = load_config(company, product)
    if not config:
        return {'currency': 'USD', 'description': '', 'usd_rate': 1.0, 'configured': False}
    return {**config, 'configured': True}

@app.get("/companies/{company}/products/{product}/date-range")
def get_date_range(company: str, product: str, snapshot: Optional[str] = None):
    at = _get_analysis_type(company, product)
    if at in ('ejari_summary', 'tamara_summary', 'aajil'):
        snaps = get_snapshots(company, product)
        snap_date = snaps[-1]['date'] if snaps else ''
        return {'min_date': snap_date, 'max_date': snap_date, 'snapshot_date': snap_date}
    if at == 'silq':
        sel = _resolve_snapshot(company, product, snapshot)
        df, _ = load_silq_snapshot(sel['filepath'])
    else:
        df, sel = _load(company, product, snapshot)
    date_col = 'Disbursement_Date' if at == 'silq' else 'Deal date'
    if date_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"No {date_col} column found")
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])
    data_max = df[date_col].max().strftime('%Y-%m-%d')
    snap_date = sel['date']
    # Use snapshot date as upper bound if it's later than the data's max date
    effective_max = max(data_max, snap_date) if snap_date else data_max
    return {
        'min_date':      df[date_col].min().strftime('%Y-%m-%d'),
        'max_date':      effective_max,
        'snapshot_date': snap_date,
    }

# ── Summary ───────────────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/summary")
def get_summary(company: str, product: str,
                snapshot: Optional[str] = None,
                as_of_date: Optional[str] = None,
                currency: Optional[str] = None):
    at = _get_analysis_type(company, product)
    if at == 'ejari_summary':
        # Pull headline numbers from parsed ODS portfolio overview
        try:
            snaps = get_snapshots(company, product)
            if snaps:
                from core.analysis_ejari import parse_ejari_workbook
                parsed   = parse_ejari_workbook(snaps[-1]['filepath'])
                km       = parsed.get('portfolio_overview', {}).get('key_metrics', {})
                def _to_num(v, typ):
                    if v is None: return 0
                    return typ(str(v).replace(',', '').strip())
                contracts = _to_num(km.get('total_contracts'), int)
                funded    = _to_num(km.get('total_funded'),   float)
            else:
                contracts, funded = 0, 0
        except Exception as e:
            import logging; logging.getLogger(__name__).warning(f"Ejari summary parse error: {e}")
            contracts, funded = 0, 0
        return {'company': company, 'product': product, 'display_currency': 'USD',
                'total_deals': contracts, 'total_purchase_value': funded,
                'total_collected': 0, 'total_denied': 0, 'total_pending': 0,
                'total_expected': 0, 'collection_rate': 0, 'denial_rate': 0,
                'pending_rate': 0, 'active_deals': 0, 'completed_deals': 0,
                'avg_discount': 0, 'dso_available': False, 'hhi_group': 0,
                'top_1_group_pct': 0, 'analysis_type': 'ejari_summary'}
    if at == 'tamara_summary':
        try:
            snaps = get_snapshots(company, product)
            if snaps:
                filepath = snaps[-1]['filepath']
                if filepath not in _tamara_cache:
                    _tamara_cache[filepath] = parse_tamara_data(filepath)
                kpis = get_tamara_summary_kpis(_tamara_cache[filepath])
            else:
                kpis = {'total_purchase_value': 0, 'total_deals': 0, 'analysis_type': 'tamara_summary'}
        except Exception:
            kpis = {'total_purchase_value': 0, 'total_deals': 0, 'analysis_type': 'tamara_summary'}
        return {'company': company, 'product': product, 'display_currency': 'SAR' if product == 'KSA' else 'AED',
                'total_deals': kpis.get('total_deals', 0), 'total_purchase_value': kpis.get('total_purchase_value', 0),
                'total_collected': 0, 'total_denied': 0, 'total_pending': 0,
                'total_expected': 0, 'collection_rate': 0, 'denial_rate': 0,
                'pending_rate': 0, 'active_deals': 0, 'completed_deals': 0,
                'avg_discount': 0, 'dso_available': False, 'hhi_group': 0,
                'top_1_group_pct': 0, 'analysis_type': 'tamara_summary',
                'facility_limit': kpis.get('facility_limit', 0),
                'registered_users': kpis.get('registered_users', 0),
                'merchants': kpis.get('merchants', 0),
                'face_value_label': kpis.get('face_value_label', 'Face Value'),
                'deals_label': kpis.get('deals_label', 'Deals')}
    if at == 'aajil':
        try:
            df, aux, sel, config, disp, mult, ref_date = _aajil_tape_load(company, product, snapshot, as_of_date, currency)
            if df is not None:
                # Live tape computation
                s = compute_aajil_summary(df, mult=mult, ref_date=ref_date, aux=aux)
                return {'company': company, 'product': product, 'display_currency': disp,
                        'total_deals': s.get('total_deals', 0),
                        'total_purchase_value': s.get('total_principal', 0),
                        'face_value_label': 'GMV (Bill Notional)',
                        'deals_label': 'Credit Transactions',
                        'total_collected': s.get('total_realised', 0),
                        'total_denied': 0, 'total_pending': s.get('total_receivable', 0),
                        'total_expected': 0,
                        'collection_rate': s.get('collection_rate', 0),
                        'denial_rate': 0, 'pending_rate': 0,
                        'active_deals': s.get('accrued_count', 0),
                        'completed_deals': s.get('realised_count', 0),
                        'avg_discount': 0, 'dso_available': False,
                        'hhi_group': s.get('hhi_customer', 0),
                        'top_1_group_pct': 0,
                        'analysis_type': 'aajil',
                        'total_customers': s.get('total_customers', 0),
                        'total_written_off': s.get('total_written_off', 0),
                        'written_off_count': s.get('written_off_count', 0),
                        'emi_count': s.get('emi_count', 0),
                        'bullet_count': s.get('bullet_count', 0),
                        'avg_tenure': s.get('avg_tenure', 0),
                        'avg_yield': s.get('avg_total_yield', 0)}
            else:
                # Fall back to JSON
                snaps = get_snapshots(company, product)
                filepath = snaps[-1]['filepath'] if snaps else None
                if filepath and filepath not in _aajil_cache:
                    _aajil_cache[filepath] = parse_aajil_data(filepath)
                kpis = get_aajil_summary(_aajil_cache[filepath]) if filepath else {}
                return {'company': company, 'product': product, 'display_currency': 'SAR',
                        'total_deals': kpis.get('total_deals', 0), 'total_purchase_value': kpis.get('total_purchase_value', 0),
                        'total_collected': kpis.get('total_collected', 0), 'total_denied': 0, 'total_pending': 0,
                        'total_expected': 0, 'collection_rate': kpis.get('collection_rate', 0), 'denial_rate': 0,
                        'pending_rate': 0, 'active_deals': 0, 'completed_deals': 0,
                        'avg_discount': 0, 'dso_available': False, 'hhi_group': 0,
                        'top_1_group_pct': 0, 'analysis_type': 'aajil',
                        'face_value_label': 'AUM (Outstanding)', 'deals_label': 'Credit Transactions',
                        'total_customers': kpis.get('total_customers', 0)}
        except Exception as e:
            return {'company': company, 'product': product, 'display_currency': 'SAR',
                    'total_deals': 0, 'total_purchase_value': 0, 'analysis_type': 'aajil',
                    'error': str(e)}
    if at == 'silq':
        df, sel, config, disp, mult, commentary_text, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
        if not len(df):
            raise HTTPException(status_code=400, detail="No deals found for selected date range")
        summary = compute_silq_summary(df, mult, ref_date=ref_date)
        return {'company': company, 'product': product, 'display_currency': disp,
                'portfolio_commentary': commentary_text, **summary}

    df, sel  = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    if not len(df):
        raise HTTPException(status_code=400, detail="No deals found for selected date range")
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    summary  = compute_summary(df, config, disp, sel['date'], as_of_date)
    # Enrich with DSO and HHI
    dso_data = compute_dso(df, mult, as_of_date)
    hhi_data = compute_hhi(df, mult)
    summary['dso_available'] = dso_data.get('available', False)
    summary['dso']          = dso_data['weighted_dso']
    summary['median_dso']   = dso_data['median_dso']
    summary['hhi_group']    = hhi_data.get('group', {}).get('hhi', 0)
    summary['hhi_product']  = hhi_data.get('product', {}).get('hhi', 0)
    summary['top_1_group_pct'] = hhi_data.get('group', {}).get('top_1_pct', 0)
    return {'company': company, 'product': product, **summary}

# ── Chart endpoints ───────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/deployment")
def get_deployment_chart(company: str, product: str,
                         snapshot: Optional[str] = None,
                         as_of_date: Optional[str] = None,
                         currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {'data': compute_deployment(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/deployment-by-product")
def get_deployment_by_product(company: str, product: str,
                               snapshot: Optional[str] = None,
                               as_of_date: Optional[str] = None,
                               currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_deployment_by_product(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/collection-velocity")
def get_collection_velocity(company: str, product: str,
                             snapshot: Optional[str] = None,
                             as_of_date: Optional[str] = None,
                             currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_collection_velocity(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/collection-curves")
def get_collection_curves(company: str, product: str,
                           snapshot: Optional[str] = None,
                           as_of_date: Optional[str] = None,
                           currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_collection_curves(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/denial-trend")
def get_denial_trend(company: str, product: str,
                     snapshot: Optional[str] = None,
                     as_of_date: Optional[str] = None,
                     currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {'data': compute_denial_trend(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/cohort")
def get_cohort_analysis(company: str, product: str,
                         snapshot: Optional[str] = None,
                         as_of_date: Optional[str] = None,
                         currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {'cohorts': compute_cohorts(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/actual-vs-expected")
def get_actual_vs_expected(company: str, product: str,
                            snapshot: Optional[str] = None,
                            as_of_date: Optional[str] = None,
                            currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_actual_vs_expected(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/ageing")
def get_ageing(company: str, product: str,
               snapshot: Optional[str] = None,
               as_of_date: Optional[str] = None,
               currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_ageing(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/revenue")
def get_revenue(company: str, product: str,
                snapshot: Optional[str] = None,
                as_of_date: Optional[str] = None,
                currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    result = compute_revenue(df, mult)
    result['vat'] = compute_vat_summary(df, mult)
    return {**result, 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/concentration")
def get_concentration(company: str, product: str,
                       snapshot: Optional[str] = None,
                       as_of_date: Optional[str] = None,
                       currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    result   = compute_concentration(df, mult)
    # Enrich with HHI and Owner breakdown
    result['hhi']   = compute_hhi(df, mult)
    result['owner'] = compute_owner_breakdown(df, mult)
    return {**result, 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/returns-analysis")
def get_returns_analysis(company: str, product: str,
                         snapshot: Optional[str] = None,
                         as_of_date: Optional[str] = None,
                         currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_returns_analysis(df, mult), 'currency': disp}

# ── New analytics endpoints ───────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/dso")
def get_dso(company: str, product: str,
            snapshot: Optional[str] = None,
            as_of_date: Optional[str] = None,
            currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_dso(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/denial-funnel")
def get_denial_funnel(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_denial_funnel(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/stress-test")
def get_stress_test(company: str, product: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_stress_test(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/expected-loss")
def get_expected_loss(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_expected_loss(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/facility-pd")
def get_facility_pd(company: str, product: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None):
    from core.analysis import compute_facility_pd
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_facility_pd(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/loss-triangle")
def get_loss_triangle(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_loss_triangle(df, mult), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/group-performance")
def get_group_performance(company: str, product: str,
                          snapshot: Optional[str] = None,
                          as_of_date: Optional[str] = None,
                          currency: Optional[str] = None):
    df, _    = _load(company, product, snapshot)
    df       = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult     = apply_multiplier(config, disp)
    return {**compute_group_performance(df, mult, as_of_date), 'currency': disp}

@app.get("/companies/{company}/products/{product}/charts/risk-migration")
def get_risk_migration(company: str, product: str,
                       snapshot: Optional[str] = None,
                       compare_snapshot: Optional[str] = None,
                       as_of_date: Optional[str] = None,
                       currency: Optional[str] = None):
    """Roll-rate migration analysis comparing two snapshots."""
    snaps = get_snapshots(company, product)
    if len(snaps) < 2:
        return {'error': 'Need at least 2 snapshots for migration analysis',
                'available_snapshots': len(snaps)}

    # Default: compare second-to-last vs last snapshot
    if not snapshot:
        snapshot = snaps[-1]['filename']
    if not compare_snapshot:
        # Find the snapshot before the selected one
        sel_idx = next((i for i, s in enumerate(snaps) if s['filename'] == snapshot or s['date'] == snapshot), len(snaps) - 1)
        if sel_idx > 0:
            compare_snapshot = snaps[sel_idx - 1]['filename']
        else:
            return {'error': 'No earlier snapshot to compare against'}

    # Load both snapshots
    old_sel = next((s for s in snaps if s['filename'] == compare_snapshot or s['date'] == compare_snapshot), None)
    new_sel = next((s for s in snaps if s['filename'] == snapshot or s['date'] == snapshot), None)
    if not old_sel or not new_sel:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    old_df = load_snapshot(old_sel['filepath'])
    new_df = load_snapshot(new_sel['filepath'])

    if as_of_date:
        old_df = filter_by_date(old_df, as_of_date)
        new_df = filter_by_date(new_df, as_of_date)

    result = compute_roll_rates(old_df, new_df, old_sel['date'], new_sel['date'])

    # Also compute stress test & EL on the new snapshot for the Risk tab
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    result['stress_test']    = compute_stress_test(new_df, mult)
    result['expected_loss']  = compute_expected_loss(new_df, mult)
    result['currency']       = disp
    result['old_snapshot']   = old_sel['date']
    result['new_snapshot']   = new_sel['date']

    return result

# ── PAR (Portfolio at Risk) ───────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/par")
def get_par(company: str, product: str,
            snapshot: Optional[str] = None, currency: Optional[str] = None,
            as_of_date: Optional[str] = None):
    """Portfolio at Risk KPIs."""
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_par(df, mult, as_of_date=as_of_date or sel['date'])

# ── DTFC (Days to First Cash) ────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/dtfc")
def get_dtfc(company: str, product: str,
             snapshot: Optional[str] = None, currency: Optional[str] = None,
             as_of_date: Optional[str] = None):
    """Days to First Cash — leading indicator."""
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_dtfc(df, mult, as_of_date=as_of_date or sel['date'])

# ── Cohort Loss Waterfall ────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/cohort-loss-waterfall")
def get_cohort_loss_waterfall(company: str, product: str,
                              snapshot: Optional[str] = None, currency: Optional[str] = None,
                              as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_cohort_loss_waterfall(df, mult, as_of_date=as_of_date or sel['date'])

# ── Recovery Analysis ────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/recovery-analysis")
def get_recovery_analysis(company: str, product: str,
                          snapshot: Optional[str] = None, currency: Optional[str] = None,
                          as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_recovery_analysis(df, mult, as_of_date=as_of_date or sel['date'])

# ── Vintage Loss Curves ─────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/vintage-loss-curves")
def get_vintage_loss_curves(company: str, product: str,
                            snapshot: Optional[str] = None, currency: Optional[str] = None,
                            as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_vintage_loss_curves(df, mult, as_of_date=as_of_date or sel['date'])

# ── Underwriting Drift ──────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/underwriting-drift")
def get_underwriting_drift(company: str, product: str,
                           snapshot: Optional[str] = None, currency: Optional[str] = None,
                           as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_underwriting_drift(df, mult, as_of_date=as_of_date or sel['date'])

# ── Segment Analysis ─────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/segment-analysis")
def get_segment_analysis(company: str, product: str,
                         snapshot: Optional[str] = None, currency: Optional[str] = None,
                         as_of_date: Optional[str] = None, segment_by: str = 'product'):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_segment_analysis(df, mult, as_of_date=as_of_date or sel['date'], segment_by=segment_by)

# ── Collections Timing ───────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/collections-timing")
def get_collections_timing(company: str, product: str,
                           snapshot: Optional[str] = None, currency: Optional[str] = None,
                           as_of_date: Optional[str] = None, view: str = 'origination_month'):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_collections_timing(df, mult, as_of_date=as_of_date or sel['date'], view=view)

# ── Seasonality ──────────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/seasonality")
def get_seasonality(company: str, product: str,
                    snapshot: Optional[str] = None, currency: Optional[str] = None,
                    as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_seasonality(df, mult, as_of_date=as_of_date or sel['date'])

# ── CDR / CCR ────────────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/cdr-ccr")
def get_cdr_ccr(company: str, product: str,
                snapshot: Optional[str] = None, currency: Optional[str] = None,
                as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_cdr_ccr(df, mult, as_of_date=as_of_date or sel['date'])

# ── Loss Categorization ─────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/loss-categorization")
def get_loss_categorization(company: str, product: str,
                            snapshot: Optional[str] = None, currency: Optional[str] = None,
                            as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    return compute_loss_categorization(df, mult, as_of_date=as_of_date or sel['date'])

# ── Methodology Log ──────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/methodology-log")
def get_methodology_log(company: str, product: str,
                        snapshot: Optional[str] = None,
                        as_of_date: Optional[str] = None):
    df, sel = _load(company, product, snapshot)
    df = filter_by_date(df, as_of_date)
    return compute_methodology_log(df, as_of_date=as_of_date or sel['date'])

# ── HHI Time Series ─────────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/charts/hhi-timeseries")
def get_hhi_timeseries(company: str, product: str, currency: Optional[str] = None):
    """Compute HHI across ALL snapshots for time series view."""
    snaps = get_snapshots(company, product)
    if len(snaps) < 2:
        return {'available': False, 'reason': 'Need at least 2 snapshots'}

    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)

    points = []
    for snap in snaps:
        try:
            snap_df = load_snapshot(snap['filepath'])
            hhi = compute_hhi_for_snapshot(snap_df, mult)
            points.append({
                'date': snap['date'],
                'group_hhi': hhi.get('group_hhi'),
                'provider_hhi': hhi.get('provider_hhi'),  # None on tapes without Provider col
                'product_hhi': hhi.get('product_hhi'),
            })
        except Exception:
            continue

    if len(points) < 2:
        return {'available': False, 'reason': 'Insufficient valid snapshots'}

    # Trend detection
    group_vals = [p['group_hhi'] for p in points if p['group_hhi'] is not None]
    trend = 'stable'
    warning = None
    if len(group_vals) >= 2:
        if group_vals[-1] > group_vals[0] * 1.10:
            trend = 'increasing'
            warning = f'Group HHI increased from {group_vals[0]:.4f} to {group_vals[-1]:.4f}'
        elif group_vals[-1] < group_vals[0] * 0.90:
            trend = 'decreasing'

    return {
        'available': True,
        'points': points,
        'trend': trend,
        'warning': warning,
    }

# ── Ejari summary endpoint ────────────────────────────────────────────────────

from collections import OrderedDict

class _BoundedCache(OrderedDict):
    """LRU cache with max 10 entries."""
    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > 10:
            self.popitem(last=False)

_ejari_cache = _BoundedCache()

@app.get("/companies/{company}/products/{product}/ejari-summary")
def get_ejari_summary(company: str, product: str, snapshot: Optional[str] = None):
    """Return parsed Ejari ODS workbook as structured JSON (read-only summary)."""
    sel = _resolve_snapshot(company, product, snapshot)
    filepath = sel['filepath']
    if filepath not in _ejari_cache:
        _ejari_cache[filepath] = parse_ejari_workbook(filepath)
    return _ejari_cache[filepath]

# ── Tamara endpoint ─────────────────────────────────────────────────────────

_tamara_cache = _BoundedCache()

@app.get("/companies/{company}/products/{product}/tamara-summary")
def get_tamara_summary(company: str, product: str, snapshot: Optional[str] = None):
    """Return parsed Tamara BNPL data as structured JSON (pre-computed summary)."""
    sel = _resolve_snapshot(company, product, snapshot)
    filepath = sel['filepath']
    if filepath not in _tamara_cache:
        _tamara_cache[filepath] = parse_tamara_data(filepath)
    return _tamara_cache[filepath]

# ── Aajil endpoint ──────────────────────────────────────────────────────────

_aajil_cache = _BoundedCache()

@app.get("/companies/{company}/products/{product}/aajil-summary")
def get_aajil_summary_endpoint(company: str, product: str, snapshot: Optional[str] = None):
    """Return Aajil data — tape-computed if xlsx, JSON-parsed if json."""
    sel = _resolve_snapshot(company, product, snapshot)
    filepath = sel['filepath']
    if filepath.endswith('.json'):
        if filepath not in _aajil_cache:
            _aajil_cache[filepath] = parse_aajil_data(filepath)
        return _aajil_cache[filepath]
    # Tape mode: return computed summary + static qualitative data
    if filepath not in _aajil_tape_cache:
        _aajil_tape_cache[filepath] = load_aajil_snapshot(filepath)
    df, aux = _aajil_tape_cache[filepath]
    from core.analysis_aajil import compute_aajil_summary as _cs, AAJIL_QUALITATIVE_DATA
    summary = _cs(df, mult=1, aux=aux)
    return {**summary, **AAJIL_QUALITATIVE_DATA}

# ── Research Report endpoint (platform-level) ───────────────────────────────

@app.post("/companies/{company}/products/{product}/research-report")
def generate_research_report_endpoint(company: str, product: str,
                                       snapshot: Optional[str] = None):
    """Generate a comprehensive credit research report PDF for any company."""
    from fastapi.responses import Response
    from core.research_report import generate_research_report

    at = _get_analysis_type(company, product)
    sel = _resolve_snapshot(company, product, snapshot)
    filepath = sel['filepath']

    # Load data based on analysis type
    if at == 'tamara_summary':
        if filepath not in _tamara_cache:
            _tamara_cache[filepath] = parse_tamara_data(filepath)
        data = _tamara_cache[filepath]
    elif at == 'ejari_summary':
        if filepath not in _ejari_cache:
            _ejari_cache[filepath] = parse_ejari_workbook(filepath)
        data = _ejari_cache[filepath]
    else:
        # Tape-based: load data and compute key metrics for the report
        data = {'meta': {'company': company, 'product': product}}
        try:
            df, sel2 = _load(company, product, snapshot)
            config2, disp = _currency(company, product, None)
            mult = apply_multiplier(config2, disp)
            data['summary'] = compute_summary(df, config2, disp, sel2['date'])
            try:
                data['cohort'] = compute_cohort(df, mult)
            except Exception:
                pass
            try:
                data['concentration'] = compute_concentration(df, mult)
            except Exception:
                pass
            try:
                data['par'] = compute_par(df, mult)
            except Exception:
                pass
            try:
                data['expected_loss'] = compute_expected_loss(df, mult)
            except Exception:
                pass
            try:
                data['dso'] = compute_dso(df, mult)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Research report data load failed for %s/%s: %s", company, product, e)

    config = load_config(company, product) or {}
    ccy = config.get('currency', 'USD')

    # Generate PDF
    pdf_bytes = generate_research_report(
        company=company, product=product, data=data,
        analysis_type=at, ai_narrative=None, currency=ccy,
    )

    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{company}_{product}_Research_Report.pdf"'},
    )

# ── SILQ chart endpoints ─────────────────────────────────────────────────────

SILQ_CHART_MAP = {
    'delinquency':        compute_silq_delinquency,
    'collections':        compute_silq_collections,
    'concentration':      compute_silq_concentration,
    'cohort':             compute_silq_cohorts,
    'yield-margins':      compute_silq_yield,
    'tenure':             compute_silq_tenure,
    'borrowing-base':     compute_silq_borrowing_base,
    'covenants':          compute_silq_covenants,
    'seasonality':        compute_silq_seasonality,
    'loss-waterfall':     compute_silq_cohort_loss_waterfall,
    'underwriting-drift': compute_silq_underwriting_drift,
    'cdr-ccr':            compute_silq_cdr_ccr,
}

@app.get("/companies/{company}/products/{product}/charts/silq/{chart_name}")
def get_silq_chart(company: str, product: str, chart_name: str,
                   snapshot: Optional[str] = None,
                   as_of_date: Optional[str] = None,
                   currency: Optional[str] = None):
    """Generic SILQ chart endpoint — dispatches to the right compute function."""
    fn = SILQ_CHART_MAP.get(chart_name)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Unknown SILQ chart: {chart_name}")
    df, sel, config, disp, mult, _, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
    # Pass ref_date to functions that accept it (for DPD calculations)
    import inspect
    if 'ref_date' in inspect.signature(fn).parameters:
        result = fn(df, mult, ref_date=ref_date)
    else:
        result = fn(df, mult)
    return {**result, 'currency': disp}


# ── Aajil chart endpoints ────────────────────────────────────────────────────

_aajil_tape_cache = _BoundedCache()

AAJIL_CHART_MAP = {
    'traction':          compute_aajil_traction,
    'delinquency':       compute_aajil_delinquency,
    'collections':       compute_aajil_collections,
    'cohort':            compute_aajil_cohorts,
    'concentration':     compute_aajil_concentration,
    'underwriting':      compute_aajil_underwriting,
    'yield-margins':     compute_aajil_yield,
    'loss-waterfall':    compute_aajil_loss_waterfall,
    'customer-segments': compute_aajil_customer_segments,
    'seasonality':       compute_aajil_seasonality,
}


def _aajil_tape_load(company, product, snapshot, as_of_date, currency):
    """Load Aajil multi-sheet tape. Returns (df, aux, sel, config, disp, mult, ref_date) or None tuple if JSON."""
    sel = _resolve_snapshot(company, product, snapshot)
    filepath = sel['filepath']

    if filepath.endswith('.json'):
        return None, None, sel, {}, 'SAR', 1, None

    if filepath not in _aajil_tape_cache:
        _aajil_tape_cache[filepath] = load_aajil_snapshot(filepath)
    df, aux = _aajil_tape_cache[filepath]
    df = filter_aajil_by_date(df, as_of_date)
    config, disp = _currency(company, product, currency)
    mult = apply_multiplier(config, disp)
    ref_date = pd.to_datetime(as_of_date) if as_of_date else pd.to_datetime(sel['date'])
    return df, aux, sel, config, disp, mult, ref_date


@app.get("/companies/{company}/products/{product}/charts/aajil/{chart_name}")
def get_aajil_chart(company: str, product: str, chart_name: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None):
    """Generic Aajil chart endpoint — dispatches to the right compute function."""
    fn = AAJIL_CHART_MAP.get(chart_name)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Unknown Aajil chart: {chart_name}")
    df, aux, sel, config, disp, mult, ref_date = _aajil_tape_load(company, product, snapshot, as_of_date, currency)
    if df is None:
        raise HTTPException(status_code=400, detail="Tape file (.xlsx) required for chart computation")
    result = fn(df, mult=mult, ref_date=ref_date, aux=aux)
    return {**result, 'currency': disp}


@app.get("/companies/{company}/products/{product}/validate")
def validate_snapshot(company: str, product: str,
                      snapshot: Optional[str] = None):
    """Run data quality checks on a single tape."""
    at = _get_analysis_type(company, product)
    if at == 'aajil':
        sel = _resolve_snapshot(company, product, snapshot)
        if sel['filepath'].endswith('.json'):
            return {'critical': [], 'warnings': [], 'info': ['JSON snapshot — no tape validation'], 'passed': True, 'total_rows': 0}
        df, _ = load_aajil_snapshot(sel['filepath'])
        result = validate_aajil_tape(df)
    elif at == 'silq':
        sel = _resolve_snapshot(company, product, snapshot)
        df, _ = load_silq_snapshot(sel['filepath'])
        result = validate_silq_tape(df)
    else:
        df, sel = _load(company, product, snapshot)
        result = validate_tape(df)
    result['snapshot'] = sel['date']
    result['filename'] = sel['filename']
    return result

# ── Data Integrity endpoints ──────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/integrity/cached")
def get_integrity_cached(company: str, product: str,
                         snapshot_old: str, snapshot_new: str):
    """Check if integrity results are already cached."""
    path = _integrity_path(company, product, snapshot_old, snapshot_new)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"cached": False}

@app.get("/companies/{company}/products/{product}/integrity")
def run_integrity_checks(company: str, product: str,
                         snapshot_old: str, snapshot_new: str):
    """Run validation + consistency checks on two snapshots."""
    at = _get_analysis_type(company, product)
    if at == 'silq':
        old_sel = _resolve_snapshot(company, product, snapshot_old)
        new_sel = _resolve_snapshot(company, product, snapshot_new)
        old_df, _ = load_silq_snapshot(old_sel['filepath'])
        new_df, _ = load_silq_snapshot(new_sel['filepath'])
    else:
        old_df, old_sel = _load(company, product, snapshot_old)
        new_df, new_sel = _load(company, product, snapshot_new)

    validate_fn = validate_silq_tape if at == 'silq' else validate_tape
    validation_old = validate_fn(old_df)
    validation_new = validate_fn(new_df)
    consistency    = run_consistency_check(old_df, new_df, old_sel['date'], new_sel['date'])

    result = {
        "validation_old": validation_old,
        "validation_new": validation_new,
        "consistency":    consistency,
        "snapshot_old":   old_sel['date'],
        "snapshot_new":   new_sel['date'],
        "ran_at":         datetime.now().isoformat(),
    }

    # Cache to disk
    path = _integrity_path(company, product, snapshot_old, snapshot_new)
    with open(path, 'w') as f:
        json.dump(result, f, indent=2, default=str)

    return result

@app.post("/companies/{company}/products/{product}/integrity/report")
def generate_integrity_report(company: str, product: str, request: dict):
    """Generate AI analysis report from cached integrity results."""
    snapshot_old = request.get('snapshot_old')
    snapshot_new = request.get('snapshot_new')
    if not snapshot_old or not snapshot_new:
        raise HTTPException(status_code=400, detail="snapshot_old and snapshot_new are required")

    # Load cached integrity results
    cached_path = _integrity_path(company, product, snapshot_old, snapshot_new)
    if not os.path.exists(cached_path):
        raise HTTPException(status_code=404, detail="Must run integrity checks first")

    with open(cached_path, 'r') as f:
        cached = json.load(f)

    # Build checks list for reporter
    checks = [{
        "old_label": cached['snapshot_old'],
        "new_label": cached['snapshot_new'],
        "report":    cached['consistency'],
    }]

    # Generate AI analysis and PDF
    analysis_text = generate_ai_analysis(company, product, checks)
    pdf_path      = save_pdf_report(company, product, analysis_text, checks)
    questions     = _extract_questions(analysis_text)

    report = {
        "analysis_text": analysis_text,
        "questions":     questions,
        "pdf_path":      pdf_path,
        "generated_at":  datetime.now().isoformat(),
    }

    # Cache report JSON
    report_path = _integrity_path(company, product, snapshot_old, snapshot_new, '_report')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report

@app.get("/companies/{company}/products/{product}/integrity/report")
def get_integrity_report_cached(company: str, product: str,
                                snapshot_old: str, snapshot_new: str):
    """Return cached AI integrity report if available."""
    path = _integrity_path(company, product, snapshot_old, snapshot_new, '_report')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"cached": False}

@app.post("/companies/{company}/products/{product}/integrity/notes")
def save_integrity_notes(company: str, product: str, request: dict):
    """Save analyst notes/answers for integrity questions."""
    snapshot_old = request.get('snapshot_old')
    snapshot_new = request.get('snapshot_new')
    notes        = request.get('notes', {})
    if not snapshot_old or not snapshot_new:
        raise HTTPException(status_code=400, detail="snapshot_old and snapshot_new are required")

    path = _integrity_path(company, product, snapshot_old, snapshot_new, '_notes')
    with open(path, 'w') as f:
        json.dump({"notes": notes, "saved_at": datetime.now().isoformat()}, f, indent=2)

    return {"saved": True}

@app.get("/companies/{company}/products/{product}/integrity/notes")
def get_integrity_notes(company: str, product: str,
                        snapshot_old: str, snapshot_new: str):
    """Return saved analyst notes for an integrity check pair."""
    path = _integrity_path(company, product, snapshot_old, snapshot_new, '_notes')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {"notes": {}}

# ── AI Cache Management ───────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/ai-cache-status")
def get_ai_cache_status(company: str, product: str,
                        snapshot: Optional[str] = None,
                        as_of_date: Optional[str] = None):
    """Check which AI outputs are cached for this company/product/snapshot."""
    sel = _resolve_snapshot(company, product, snapshot)
    snap_key = sel.get('filename', snapshot or '')
    snap_date = sel.get('date', '')
    aod = as_of_date or ''

    endpoints = {
        'commentary': _ai_cache_key('commentary', company, product, snap_key, aod, snapshot_date=snap_date),
        'executive_summary': _ai_cache_key('executive_summary', company, product, snap_key, aod, snapshot_date=snap_date),
    }

    # Check common tab insights
    at = _get_analysis_type(company, product)
    if at == 'silq':
        tabs = ['delinquency', 'collections', 'concentration', 'cohort', 'yield-margins', 'tenure']
    elif at in ('ejari_summary', 'tamara_summary'):
        tabs = []
    elif at == 'aajil':
        tabs = ['traction', 'delinquency', 'collections', 'cohort', 'concentration',
                'yield-margins', 'loss-waterfall', 'customer-segments']
    else:
        tabs = ['deployment', 'collection', 'denial-trend', 'ageing', 'revenue',
                'concentration', 'cohort', 'actual-vs-expected', 'returns', 'risk-migration']

    tab_cache = {}
    for t in tabs:
        path = _ai_cache_key('tab_insight', company, product, snap_key, aod, t, snapshot_date=snap_date)
        c = _ai_cache_get(path)
        if c:
            tab_cache[t] = c.get('cached_at', True)

    result = {}
    for name, path in endpoints.items():
        c = _ai_cache_get(path)
        if c:
            result[name] = {'cached': True, 'cached_at': c.get('cached_at', ''), 'generated_at': c.get('generated_at', '')}
        else:
            result[name] = {'cached': False}

    result['tab_insights'] = tab_cache
    result['total_cached'] = sum(1 for v in result.values() if isinstance(v, dict) and v.get('cached')) + len(tab_cache)
    return result

# ── AI endpoints ──────────────────────────────────────────────────────────────

def _check_backdated(as_of_date: str | None, snapshot_date: str) -> None:
    """Raise 400 if as_of_date is before the snapshot date.
    AI analysis on backdated views is misleading because balance metrics
    (collected, denied, outstanding) reflect the snapshot date, not the as-of date."""
    if as_of_date and snapshot_date and as_of_date < snapshot_date:
        raise HTTPException(
            status_code=400,
            detail=(
                f"AI analysis is not available for backdated views. "
                f"As-of date ({as_of_date}) is before tape date ({snapshot_date}). "
                f"Balance metrics reflect the snapshot date, so AI commentary would be misleading. "
                f"Remove the as-of date filter or set it to the snapshot date."
            )
        )

def _ai_client():
    import anthropic
    from dotenv import load_dotenv
    load_dotenv()
    return anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

@app.get("/companies/{company}/products/{product}/ai-commentary")
def get_ai_commentary(company: str, product: str,
                      snapshot: Optional[str] = None,
                      as_of_date: Optional[str] = None,
                      currency: Optional[str] = None,
                      refresh: bool = False,
                      mode: Optional[str] = None):
    # Resolve snapshot first for consistent cache key
    sel_for_key = _resolve_snapshot(company, product, snapshot)
    snap_key = sel_for_key.get('filename', snapshot or '')
    snap_date = sel_for_key.get('date', '')
    _check_backdated(as_of_date, snap_date)
    cache_path = _ai_cache_key('commentary', company, product, snap_key, as_of_date or '', snapshot_date=snap_date, currency=currency or '')

    if not refresh:
        cached = _ai_cache_get(cache_path)
        if cached:
            return cached

    at = _get_analysis_type(company, product)

    if at == 'silq':
        df, sel, config, disp, mult, commentary_text, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
        s = compute_silq_summary(df, mult, ref_date=ref_date)
        d = compute_silq_delinquency(df, mult, ref_date=ref_date)
        c = compute_silq_collections(df, mult)

        commentary_ctx = ''
        if commentary_text:
            commentary_ctx = f"\nANALYST PORTFOLIO COMMENTARY (from tape):\n{commentary_text}\n"

        prompt = f"""You are a senior analyst at ACP Private Credit, analyzing SILQ's POS lending portfolio (BNPL, RBF & RCL loans) in KSA.
Data as of: {as_of_date or sel['date']}  |  Currency: {disp}

PORTFOLIO SNAPSHOT:
- Total Loans: {s['total_deals']:,} ({s['active_deals']} active, {s['completed_deals']} closed)
- Total Disbursed: {disp} {s['total_disbursed']/1e6:.1f}M
- Outstanding: {disp} {s['total_outstanding']/1e6:.1f}M
- Collection Rate: {s['collection_rate']:.1f}% (repaid vs collectable)
- Overdue Rate: {s['overdue_rate']:.1f}% of outstanding
- PAR30: {s['par30']:.1f}%, PAR60: {s['par60']:.1f}%, PAR90: {s['par90']:.1f}%
- Product Mix: {s['product_mix']}
- Avg Tenure: {s['avg_tenure']:.0f} weeks

DPD BUCKETS:
{[f"{b['label']}: {b['count']} loans ({b['pct']:.1f}%), {disp} {b['amount']/1e6:.2f}M" for b in d['buckets']]}

COLLECTION BY PRODUCT:
{[f"{p['product']}: {p['rate']:.1f}% collection rate, {p['deals']} deals" for p in c['by_product']]}
{commentary_ctx}
Write a concise portfolio commentary in 3 sections:
1. PORTFOLIO HEALTH (2-3 sentences) — overall collection and delinquency performance.
2. KEY OBSERVATIONS (3-4 bullets) — most important data points for an investment committee.
3. WATCH ITEMS (2-3 bullets) — areas that warrant monitoring. Be direct about concerns.

Professional tone, suitable for an investment committee memo. Be specific and data-driven."""
    else:
        df, sel  = _load(company, product, snapshot)
        df       = filter_by_date(df, as_of_date)
        config, disp = _currency(company, product, currency)
        mult     = apply_multiplier(config, disp)
        s        = compute_summary(df, config, disp, sel['date'], as_of_date)

        from core.analysis import add_month_column
        monthly  = add_month_column(df).groupby('Month').agg(
            purchase_value = ('Purchase value', 'sum'),
            collected      = ('Collected till date', 'sum'),
            denied         = ('Denied by insurance', 'sum'),
        ).reset_index().tail(6).to_dict(orient='records')

        prompt = f"""You are a senior analyst at ACP Private Credit, a private credit fund specializing in asset-backed lending.

You are analyzing the loan portfolio for {company.upper()} - {product.replace('_', ' ').title()}.
Data as of: {as_of_date or sel['date']}  |  Currency: {disp}

PORTFOLIO SNAPSHOT:
- Total Deals: {s['total_deals']:,}
- Purchase Value: {disp} {s['total_purchase_value']/1e6:.1f}M
- Total Collected: {disp} {s['total_collected']/1e6:.1f}M
- Collection Rate: {s['collection_rate']:.2f}%
- Denial Rate: {s['denial_rate']:.2f}%
- Pending Response: {disp} {s['total_pending']/1e6:.1f}M ({s['pending_rate']:.2f}% of portfolio)
- Deal Status: {s['status_breakdown']}

LAST 6 MONTHS ACTIVITY:
{monthly}

Write a concise portfolio commentary in 3 sections:
1. PORTFOLIO HEALTH (2-3 sentences) — overall collection performance and trends.
2. KEY OBSERVATIONS (3-4 bullets) — most important data points for an investment committee.
3. WATCH ITEMS (2-3 bullets) — areas that warrant monitoring. Be direct about concerns.

Professional tone, suitable for an investment committee memo. Be specific and data-driven."""

    # Agent mode: dynamic tool-calling agent generates richer commentary
    if mode == 'agent':
        try:
            from core.agents.internal import generate_agent_commentary
            commentary_text = generate_agent_commentary(company, product, snapshot, currency, as_of_date)
            result = {
                'commentary': commentary_text,
                'generated_at': datetime.now().isoformat(),
                'as_of_date': as_of_date or sel.get('date', ''),
                'mode': 'agent',
            }
            _ai_cache_put(cache_path, result)
            log_activity(AI_COMMENTARY, company, product, f"Generated agent commentary for {snap_key}")
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Fall through to legacy mode

    from core.ai_client import complete as _ai_complete
    msg = _ai_complete(
        tier="structured", system="", max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
        log_prefix="ai-commentary",
    )
    result = {
        'commentary':   msg.content[0].text,
        'generated_at': datetime.now().isoformat(),
        'as_of_date':   as_of_date or sel.get('date', ''),
    }
    _ai_cache_put(cache_path, result)
    log_activity(AI_COMMENTARY, company, product, f"Generated AI commentary for {snap_key}")
    return result


# ── AI Executive Summary ─────────────────────────────────────────────────────

def _build_klaim_full_context(df, mult, as_of_date, config, disp, snapshot_date):
    """Build comprehensive analytics context from ALL Klaim compute functions."""
    from core.analysis import add_month_column
    sections = []
    data_gaps = []

    # 1. Summary
    try:
        s = compute_summary(df, config, disp, snapshot_date, as_of_date)
        sections.append(f"PORTFOLIO SUMMARY: {s['total_deals']:,} deals, {disp} {s['total_purchase_value']/1e6:.1f}M originated, "
                       f"Collection Rate {s['collection_rate']:.1f}%, Denial Rate {s['denial_rate']:.1f}%, "
                       f"Pending {s['pending_rate']:.1f}%, Active {s['active_deals']}, Completed {s['completed_deals']}")
    except Exception as e:
        data_gaps.append(str(e))

    # 2. PAR (dual perspective)
    try:
        par = compute_par(df, mult, as_of_date)
        if par.get('available'):
            sections.append(f"PAR (Lifetime): 30+={par['lifetime_par30']:.2f}%, 60+={par['lifetime_par60']:.2f}%, 90+={par['lifetime_par90']:.2f}% "
                           f"| PAR (Active Outstanding): 30+={par['par30']:.1f}%, 60+={par['par60']:.1f}%, 90+={par['par90']:.1f}%")
    except Exception as e:
        data_gaps.append(str(e))

    # 3. DTFC
    try:
        dtfc = compute_dtfc(df, mult, as_of_date)
        if dtfc.get('available'):
            sections.append(f"DTFC: Median {dtfc['median_dtfc']:.0f}d, P90 {dtfc['p90_dtfc']:.0f}d ({dtfc['method']})")
    except Exception as e:
        data_gaps.append(str(e))

    # 4. DSO
    try:
        dso = compute_dso(df, mult, as_of_date)
        if dso.get('available'):
            sections.append(f"DSO: Weighted {dso['weighted_dso']:.0f}d, Median {dso['median_dso']:.0f}d, P95 {dso['p95_dso']:.0f}d")
    except Exception as e:
        data_gaps.append(str(e))

    # 5. Collection velocity
    try:
        cv = compute_collection_velocity(df, mult, as_of_date)
        recent = cv['monthly'][-3:] if cv.get('monthly') else []
        if recent:
            rates = ', '.join([f"{m.get('Month','?')}: {m.get('rate',0):.1f}%" for m in recent])
            sections.append(f"COLLECTION VELOCITY (last 3M): {rates} | Avg days to collect: {cv.get('avg_days',0):.0f}")
    except Exception as e:
        data_gaps.append(str(e))

    # 6. Denial trend
    try:
        dt = compute_denial_trend(df, mult)
        recent = dt[-3:] if dt else []
        if recent:
            rates = ', '.join([f"{m.get('Month','?')}: {m.get('denial_rate',0):.1f}%" for m in recent])
            sections.append(f"DENIAL TREND (last 3M): {rates}")
    except Exception as e:
        data_gaps.append(str(e))

    # 7. Ageing
    try:
        ag = compute_ageing(df, mult, as_of_date)
        health = {h['status']: h for h in ag.get('health_summary', [])}
        sections.append(f"AGEING: Outstanding {disp} {ag.get('total_outstanding',0)/1e6:.1f}M | "
                       f"Healthy {health.get('Healthy',{}).get('percentage',0):.0f}%, "
                       f"Watch {health.get('Watch',{}).get('percentage',0):.0f}%, "
                       f"Delayed {health.get('Delayed',{}).get('percentage',0):.0f}%, "
                       f"Poor {health.get('Poor',{}).get('percentage',0):.0f}%")
    except Exception as e:
        data_gaps.append(str(e))

    # 8. Concentration
    try:
        conc = compute_concentration(df, mult)
        hhi = conc.get('hhi', {})
        top_groups = conc.get('group', [])[:3]
        top_str = ', '.join([f"{g.get('Group','?')} ({g.get('share',0):.1f}%)" for g in top_groups])
        sections.append(f"CONCENTRATION: HHI={hhi.get('hhi',0):.4f} ({hhi.get('label','?')}), Top groups: {top_str}")
    except Exception as e:
        data_gaps.append(str(e))

    # 9. Returns
    try:
        ret = compute_returns_analysis(df, mult)
        rs = ret.get('summary', {})
        sections.append(f"RETURNS: Realised Margin {rs.get('realised_margin',0):.2f}%, "
                       f"Capital Recovery {rs.get('capital_recovery',0):.2f}%, "
                       f"Avg Discount {rs.get('avg_discount',0):.2f}%")
    except Exception as e:
        data_gaps.append(str(e))

    # 10. Expected Loss
    try:
        el = compute_expected_loss(df, mult)
        p = el.get('portfolio', {})
        sections.append(f"EXPECTED LOSS MODEL: PD={p.get('pd',0):.2f}%, LGD={p.get('lgd',0):.2f}%, "
                       f"EL Rate={p.get('el_rate',0):.4f}%")
    except Exception as e:
        data_gaps.append(str(e))

    # 11. Stress test
    try:
        st = compute_stress_test(df, mult)
        scenarios = st.get('scenarios', [])
        if scenarios:
            worst = scenarios[-1]
            sections.append(f"STRESS TEST: Worst scenario ({worst.get('scenario','')}): "
                           f"collection drops to {worst.get('stressed_rate',0):.1f}%")
    except Exception as e:
        data_gaps.append(str(e))

    # 12. Cohort loss waterfall
    try:
        clw = compute_cohort_loss_waterfall(df, mult)
        totals = clw.get('totals', {})
        sections.append(f"LOSS WATERFALL: Default rate {totals.get('default_rate',0):.2f}%, "
                       f"Recovery rate {totals.get('recovery_rate',0):.2f}%, "
                       f"Net loss rate {totals.get('net_loss_rate',0):.2f}%")
    except Exception as e:
        data_gaps.append(str(e))

    # 13. Recovery analysis
    try:
        ra = compute_recovery_analysis(df, mult)
        sections.append(f"RECOVERY: Portfolio recovery rate {ra.get('portfolio_recovery_rate',0):.1f}%")
    except Exception as e:
        data_gaps.append(str(e))

    # 14. Underwriting drift
    try:
        ud = compute_underwriting_drift(df, mult, as_of_date)
        flagged = [v for v in ud.get('vintages', []) if v.get('flags')]
        if flagged:
            sections.append(f"UNDERWRITING DRIFT: {len(flagged)} vintages flagged with drift out of {len(ud.get('vintages',[]))}")
        else:
            sections.append(f"UNDERWRITING DRIFT: No vintages flagged — origination quality stable")
    except Exception as e:
        data_gaps.append(str(e))

    # 15. Seasonality
    try:
        sn = compute_seasonality(df, mult)
        idx = sn.get('seasonal_index', [])
        if idx:
            peak = max(idx, key=lambda x: x.get('index', 0))
            trough = min(idx, key=lambda x: x.get('index', 0))
            sections.append(f"SEASONALITY: Peak month={peak.get('month','?')} (index {peak.get('index',0):.2f}), "
                           f"Trough month={trough.get('month','?')} (index {trough.get('index',0):.2f})")
    except Exception as e:
        data_gaps.append(str(e))

    # 16. Segment analysis
    try:
        sa = compute_segment_analysis(df, mult)
        dims = sa.get('dimensions', [])
        sections.append(f"SEGMENTS: Available dimensions: {', '.join(dims)}")
    except Exception as e:
        data_gaps.append(str(e))

    # 17. HHI time series (load all snapshots)
    try:
        hhi_ts = compute_hhi_for_snapshot(df, mult)
        sections.append(f"HHI (current snapshot): {hhi_ts.get('hhi',0):.4f}")
    except Exception as e:
        data_gaps.append(str(e))

    # 18. Group performance
    try:
        gp = compute_group_performance(df, mult)
        top3 = gp[:3] if gp else []
        if top3:
            top_str = ', '.join([f"{g.get('Group','?')}: coll={g.get('collection_rate',0):.1f}% den={g.get('denial_rate',0):.1f}%" for g in top3])
            sections.append(f"TOP PROVIDERS: {top_str}")
    except Exception as e:
        data_gaps.append(str(e))

    # 19. Cohorts (recent)
    try:
        cohorts = compute_cohorts(df, mult)
        recent = cohorts[-3:] if cohorts else []
        if recent:
            coh_str = ', '.join([f"{c.get('month','?')}: {c.get('deals',0)} deals, coll={c.get('collection_rate',0):.1f}%" for c in recent])
            sections.append(f"RECENT COHORTS: {coh_str}")
    except Exception as e:
        data_gaps.append(str(e))

    # 20. Loss categorization
    try:
        lc = compute_loss_categorization(df, mult)
        cats = lc.get('categories', [])
        if cats:
            cat_str = ', '.join([f"{c.get('category','?')}: {c.get('pct',0):.0f}%" for c in cats])
            sections.append(f"LOSS CATEGORIES: {cat_str}")
    except Exception as e:
        data_gaps.append(str(e))

    # 21. Legal compliance (if documents extracted)
    try:
        from core.legal_compliance import build_legal_context_for_executive_summary
        co = config.get('company', '')
        pr = config.get('product', '')
        legal_ctx = build_legal_context_for_executive_summary(co, pr)
        if legal_ctx:
            sections.append(legal_ctx)
    except Exception as e:
        data_gaps.append(str(e))

    # Inject Living Mind context (Layer 2 + Layer 4)
    try:
        # Don't pass analysis_type — config.json's `asset_class` field
        # (healthcare_receivables) is the correct Layer 2.5 key.
        mind_ctx = build_mind_context('klaim', config.get('product', 'UAE_healthcare'),
                                       'executive_summary')
        if not mind_ctx.is_empty:
            sections.append("")
            sections.append("PLATFORM MEMORY:")
            sections.append(mind_ctx.formatted)
    except Exception as e:
        data_gaps.append(str(e))

    if data_gaps:
        sections.append(f"\nDATA GAPS (could not compute {len(data_gaps)} sections): " + '; '.join(data_gaps[:10]))

    return '\n'.join(sections)


def _build_silq_full_context(df, mult, ref_date, config, disp):
    """Build comprehensive analytics context from ALL SILQ compute functions."""
    sections = []

    try:
        s = compute_silq_summary(df, mult, ref_date=ref_date)
        sections.append(f"PORTFOLIO: {s['total_deals']:,} loans, {disp} {s['total_disbursed']/1e6:.1f}M disbursed, "
                       f"Outstanding {disp} {s['total_outstanding']/1e6:.1f}M, "
                       f"Collection {s['collection_rate']:.1f}%, Overdue {s['overdue_rate']:.1f}%, "
                       f"PAR30={s['par30']:.1f}%, PAR60={s['par60']:.1f}%, PAR90={s['par90']:.1f}%")
    except Exception as e:
        logger.debug("SILQ context: summary failed: %s", e)

    try:
        d = compute_silq_delinquency(df, mult, ref_date=ref_date)
        buckets = d.get('buckets', [])
        if buckets:
            bk_str = ', '.join([f"{b['label']}: {b['count']} ({b['pct']:.1f}%)" for b in buckets])
            sections.append(f"DPD BUCKETS: {bk_str}")
        top_shops = d.get('top_overdue_shops', [])[:3]
        if top_shops:
            sh_str = ', '.join([f"{s.get('shop','?')}: {disp} {s.get('overdue',0)/1e3:.0f}K" for s in top_shops])
            sections.append(f"TOP OVERDUE SHOPS: {sh_str}")
    except Exception as e:
        logger.debug("SILQ context: delinquency failed: %s", e)

    try:
        c = compute_silq_collections(df, mult)
        bp = c.get('by_product', [])
        if bp:
            bp_str = ', '.join([f"{p['product']}: {p['rate']:.1f}%" for p in bp])
            sections.append(f"COLLECTIONS BY PRODUCT: {bp_str}")
    except Exception as e:
        logger.debug("SILQ context: collections failed: %s", e)

    try:
        conc = compute_silq_concentration(df, mult)
        top_shops = conc.get('shops', [])[:3]
        shop_strs = [f"{s.get('shop','?')} ({s.get('share',0):.1f}%)" for s in top_shops]
        sections.append(f"CONCENTRATION: HHI={conc.get('hhi',0):.4f}, Top shops: {', '.join(shop_strs)}")
    except Exception as e:
        logger.debug("SILQ context: concentration failed: %s", e)

    try:
        coh = compute_silq_cohorts(df, mult, ref_date=ref_date)
        recent = coh[-3:] if isinstance(coh, list) else coh.get('cohorts', [])[-3:]
        if recent:
            coh_str = ', '.join([f"{c.get('month','?')}: {c.get('loans',0)} loans, coll={c.get('collection_rate',0):.1f}%" for c in recent])
            sections.append(f"RECENT COHORTS: {coh_str}")
    except Exception as e:
        logger.debug("SILQ context: cohorts failed: %s", e)

    try:
        y = compute_silq_yield(df, mult)
        bp = y.get('by_product', [])
        if bp:
            bp_str = ', '.join([f"{p.get('product','?')}: margin={p.get('margin',0):.1f}%" for p in bp])
            sections.append(f"YIELD BY PRODUCT: {bp_str}")
    except Exception as e:
        logger.debug("SILQ context: yield failed: %s", e)

    try:
        t = compute_silq_tenure(df, mult, ref_date=ref_date)
        bands = t.get('tenure_bands', [])
        if bands:
            tb_str = ', '.join([f"{b.get('band','?')}: {b.get('count',0)} loans" for b in bands[:4]])
            sections.append(f"TENURE DISTRIBUTION: {tb_str}")
    except Exception as e:
        logger.debug("SILQ context: tenure failed: %s", e)

    # Inject Living Mind context (Layer 2 + Layer 4)
    try:
        mind_ctx = build_mind_context('SILQ', config.get('product', 'KSA'),
                                       'executive_summary')
        if not mind_ctx.is_empty:
            sections.append("")
            sections.append("PLATFORM MEMORY:")
            sections.append(mind_ctx.formatted)
    except Exception as e:
        logger.debug("SILQ context: mind failed: %s", e)

    return '\n'.join(sections)


def _build_aajil_full_context(data_or_df, mult=1, ref_date=None, aux=None, config=None, disp='SAR'):
    """Build analytics context from Aajil data — supports both tape (DataFrame) and JSON."""
    sections = []

    if isinstance(data_or_df, pd.DataFrame):
        # Live tape mode
        df = data_or_df
        s = compute_aajil_summary(df, mult=mult, ref_date=ref_date, aux=aux)
        sections.append("PORTFOLIO OVERVIEW (from loan tape):")
        sections.append(f"  Total Deals: {s['total_deals']}")
        sections.append(f"  GMV (Bill Notional): {disp} {s['total_principal']:,.0f}")
        sections.append(f"  Outstanding (Receivable): {disp} {s['total_receivable']:,.0f}")
        sections.append(f"  Realised (Collected): {disp} {s['total_realised']:,.0f}")
        sections.append(f"  Written Off: {disp} {s['total_written_off']:,.0f} ({s['written_off_count']} deals, {s['write_off_rate']*100:.1f}%)")
        sections.append(f"  Collection Rate: {s['collection_rate']*100:.1f}%")
        sections.append(f"  Total Customers: {s['total_customers']}")
        sections.append(f"  Avg Deals/Customer: {s['avg_deals_per_customer']:.1f}")
        sections.append(f"  Deal Type: EMI {s['emi_count']} ({s['emi_pct']*100:.0f}%), Bullet {s['bullet_count']} ({s['bullet_pct']*100:.0f}%)")
        sections.append(f"  Avg Tenure: {s['avg_tenure']:.1f} months")
        sections.append(f"  Avg Yield: {s['avg_total_yield']*100:.2f}%")
        sections.append(f"  HHI (Customer): {s['hhi_customer']:.4f}")

        t = compute_aajil_traction(df, mult=mult, aux=aux)
        sections.append("")
        sections.append(f"TRACTION: {len(t['volume_monthly'])} months of origination data")
        sections.append(f"  Total Disbursed: {disp} {t['total_disbursed']:,.0f}")
        gs = t.get('volume_summary_stats', {})
        if gs.get('mom_pct') is not None:
            sections.append(f"  MoM: {gs['mom_pct']:+.1f}%, QoQ: {gs.get('qoq_pct', 'N/A')}%, YoY: {gs.get('yoy_pct', 'N/A')}%")

        d = compute_aajil_delinquency(df, mult=mult, aux=aux)
        sections.append("")
        sections.append("DELINQUENCY:")
        sections.append(f"  Active Balance: {disp} {d['total_active_balance']:,.0f}")
        sections.append(f"  Overdue Balance: {disp} {d['total_overdue_balance']:,.0f}")
        sections.append(f"  PAR 1+ inst: {d['par_1_inst']*100:.1f}%, PAR 2+: {d['par_2_inst']*100:.1f}%, PAR 3+: {d['par_3_inst']*100:.1f}%")
        for bt in d.get('by_deal_type', []):
            sections.append(f"  {bt['deal_type']}: {bt['overdue_count']}/{bt['active_count']} overdue ({bt['overdue_pct']*100:.1f}%)")

        y = compute_aajil_yield(df, mult=mult, aux=aux)
        sections.append("")
        sections.append("YIELD & REVENUE:")
        sections.append(f"  Total Margin: {disp} {y['total_margin']:,.0f}")
        sections.append(f"  Total Fees: {disp} {y['total_fees']:,.0f}")
        sections.append(f"  Revenue/GMV: {y['revenue_over_gmv']*100:.2f}%")
        sections.append(f"  Avg Total Yield: {y['avg_total_yield']*100:.2f}%")

        lw = compute_aajil_loss_waterfall(df, mult=mult, aux=aux)
        sections.append("")
        sections.append("LOSS WATERFALL:")
        sections.append(f"  Gross Loss Rate: {lw['gross_loss_rate']*100:.2f}%")
        sections.append(f"  Written Off Amount: {disp} {lw['written_off_amount']:,.0f}")
        sections.append(f"  Net Loss: {disp} {lw['net_loss']:,.0f}")

        c = compute_aajil_concentration(df, mult=mult, aux=aux)
        sections.append("")
        sections.append(f"CONCENTRATION: HHI={c['hhi_customer']:.4f}, Top5={c['top5_share']*100:.1f}%, Top10={c['top10_share']*100:.1f}%")
        sections.append(f"  Industry unknown: {c['industry_unknown_pct']*100:.0f}%")

    else:
        # JSON fallback (legacy)
        data = data_or_df
        co = data.get('company_overview', {})
        sections.append("COMPANY OVERVIEW (from investor deck):")
        sections.append(f"  Company: Aajil (Buildnow) — SME raw materials trade credit, KSA")
        sections.append(f"  AUM: SAR {co.get('aum_sar', 0):,.0f}")
        sections.append(f"  GMV: SAR {co.get('gmv_sar', 0):,.0f}")
        sections.append(f"  Customers: {co.get('total_customers', 0)}, Transactions: {co.get('total_transactions', 0)}")

    # Inject Living Mind context
    try:
        mind_ctx = build_mind_context('Aajil', 'KSA',
                                       'executive_summary')
        if not mind_ctx.is_empty:
            sections.append("")
            sections.append("PLATFORM MEMORY:")
            sections.append(mind_ctx.formatted)
    except Exception:
        pass

    return '\n'.join(sections)


def _build_tamara_full_context(data):
    """Build comprehensive analytics context from parsed Tamara BNPL JSON snapshot."""
    sections = []

    # Overview
    ov = data.get('overview', {})
    co = data.get('company_overview', {})
    ft = data.get('facility_terms', {})
    sections.append(f"COMPANY: {co.get('full_name', 'Tamara')}, founded {co.get('founded', '?')}, "
                   f"{co.get('registered_users', 0)/1e6:.0f}M users, {co.get('merchants', 0):,} merchants, "
                   f"valuation ${co.get('valuation', 0)/1e9:.1f}B, {co.get('employees', 0)} employees")
    sections.append(f"PORTFOLIO: Outstanding {ov.get('total_pending', 0)/1e6:.1f}M, "
                   f"{ov.get('months_of_data', 0)} months of data, "
                   f"{ov.get('vintage_count', 0)} vintage cohorts tracked")
    sections.append(f"FACILITY: {ft.get('facility_name', '?')}, total limit ${ft.get('total_limit', 0)/1e9:.2f}B, "
                   f"max advance rate {ft.get('max_advance_rate', 0)*100:.0f}%, "
                   f"maturity {ft.get('final_maturity', '?')}")

    # Tranches
    tranches = ft.get('tranches', [])
    if tranches:
        tr_str = ', '.join([f"{t['name']} ${t['limit']/1e6:.0f}M ({t['rate']})" for t in tranches])
        sections.append(f"TRANCHES: {tr_str}")

    # Products & APR
    products = co.get('products', {})
    bnpl_plus = products.get('bnpl_plus', {})
    apr = bnpl_plus.get('apr', {})
    if apr:
        apr_str = ', '.join([f"{k}={v*100:.0f}%" for k, v in apr.items()])
        sections.append(f"BNPL+ APR SCHEDULE: {apr_str}")

    # Covenant compliance
    cs = data.get('covenant_status', {})
    triggers = cs.get('triggers', [])
    for t in triggers:
        status = t.get('status', 'unknown')
        current = t.get('current_value')
        sections.append(f"COVENANT {t.get('name', '?').upper()}: "
                       f"current={current:.2f}% " if current else f"COVENANT {t.get('name', '?').upper()}: current=N/A "
                       f"(L1={t.get('l1_threshold', 0):.1f}%, L2={t.get('l2_threshold', 0):.1f}%, L3={t.get('l3_threshold', 0):.1f}%), "
                       f"status={status}, headroom={t.get('headroom_pct', 'N/A')}pp")

    # Corporate covenants
    corp = ft.get('corporate_covenants', {})
    if corp:
        corp_items = [f"{k.replace('_', ' ')}: L1={v.get('threshold')}" for k, v in corp.items()]
        sections.append(f"CORPORATE COVENANTS: {'; '.join(corp_items)}")

    # Vintage performance summary
    vp = data.get('vintage_performance', {})
    for metric in ['default', 'delinquency']:
        portfolio = vp.get(metric, {}).get('portfolio', [])
        if not portfolio:
            continue
        scale = vp.get(metric, {}).get('_color_scale', {})
        label = 'DEFAULT (+120DPD)' if metric == 'default' else 'DELINQUENCY (+7DPD)'
        sections.append(f"VINTAGE {label}: {len(portfolio)} vintages, "
                       f"range {scale.get('min', 0)*100:.2f}%-{scale.get('max', 0)*100:.2f}%, "
                       f"median ~{scale.get('p25', 0)*100:.2f}%-{scale.get('p75', 0)*100:.2f}% IQR")

        # Recent 3 vintages with latest values
        for v in portfolio[-3:]:
            cols = sorted([k for k in v if k != 'vintage'])
            latest_col = cols[-1] if cols else None
            latest_val = v.get(latest_col) if latest_col else None
            if latest_val is not None:
                sections.append(f"  Vintage {v['vintage']}: latest {metric} rate = {latest_val*100:.2f}%")

    # Deloitte FDD summary
    fdd = data.get('deloitte_fdd', {})
    ts = fdd.get('dpd_timeseries', [])
    if ts:
        latest = ts[-1]
        dpd = latest.get('dpd_distribution', {})
        total = sum(v for v in dpd.values() if v) or 1
        not_late_pct = (dpd.get('Not Late', 0) or 0) / total * 100
        sections.append(f"DPD SNAPSHOT: {len(ts)} months, latest {latest.get('date', '?')}, "
                       f"current rate {100 - not_late_pct:.1f}% past due, "
                       f"total pending {latest.get('total_pending', 0)/1e6:.1f}M, "
                       f"written off {latest.get('total_written_off', 0)/1e6:.1f}M")

    # Product breakdown
    pb = fdd.get('product_breakdown', [])
    if pb:
        top_prods = sorted(pb, key=lambda x: x.get('pending_amount', 0), reverse=True)[:5]
        prod_str = ', '.join([f"{p['product']}: {p.get('pending_amount', 0)/1e6:.1f}M ({p.get('writeoff_pct', 0)*100:.1f}% WO)" for p in top_prods])
        sections.append(f"TOP PRODUCTS: {prod_str}")

    # Demographics
    demo = data.get('demographics', {})
    dims = demo.get('dimensions', {})
    for dim_name, records in dims.items():
        if records:
            top = sorted(records, key=lambda x: x.get('outstanding_ar', 0) or 0, reverse=True)[:3]
            dim_str = ', '.join([f"{r['category']}: AR={r.get('outstanding_ar', '?')}, Ever90={r.get('ever_90_rate', '?')}" for r in top])
            sections.append(f"DEMOGRAPHICS ({dim_name}): {dim_str}")

    # Investor reporting KPIs (latest values)
    ir = data.get('investor_reporting', {})
    kpis = ir.get('kpis', [])
    for k in kpis[:15]:
        vals = k.get('values', {})
        if vals:
            latest_key = sorted(vals.keys())[-1]
            sections.append(f"KPI {k['metric']}: {vals[latest_key]} (as of {latest_key})")

    # HSBC report summary
    hsbc = data.get('hsbc_reports', [])
    if hsbc:
        sections.append(f"HSBC REPORTS: {len(hsbc)} monthly investor reports available")

    # Inject Living Mind context (Layer 2 + Layer 4)
    try:
        mind_ctx = build_mind_context('Tamara', 'KSA',
                                       'executive_summary')
        if not mind_ctx.is_empty:
            sections.append("")
            sections.append("PLATFORM MEMORY:")
            sections.append(mind_ctx.formatted)
    except Exception:
        pass

    return '\n'.join(sections)


def _build_ejari_full_context(data):
    """Build comprehensive analytics context from parsed Ejari ODS workbook."""
    sections = []

    # Portfolio overview
    ov = data.get('portfolio_overview', {})
    km = ov.get('key_metrics', {})
    if km:
        sections.append(f"PORTFOLIO: {km.get('total_contracts', '?')} contracts, "
                       f"{km.get('active_loans', '?')} active, "
                       f"Originated ${km.get('total_originated', 0):,.0f}, "
                       f"Funded ${km.get('total_funded', 0):,.0f}, "
                       f"Outstanding principal ${km.get('outstanding_principal', 0):,.0f}, "
                       f"Outstanding fee ${km.get('outstanding_fee', 0):,.0f}, "
                       f"Collections ${km.get('total_collections', 0):,.0f}")
        par_str = f"PAR30={km.get('par30', '?')}, PAR60={km.get('par60', '?')}, PAR90={km.get('par90', '?')}, PAR180={km.get('par180', '?')}"
        sections.append(f"PAR: {par_str}")

    # DPD distribution
    dpd = ov.get('dpd_distribution', [])
    if dpd:
        dpd_str = ', '.join([f"{d['bucket']}: {d.get('loans', '?')} loans ({d.get('pct_outstanding', '?')} of O/S)" for d in dpd])
        sections.append(f"DPD DISTRIBUTION: {dpd_str}")

    # Monthly cohorts (recent 5)
    cohorts = data.get('monthly_cohort', [])
    recent = [c for c in cohorts if c.get('cohort') != 'TOTAL'][-5:]
    if recent:
        coh_str = ', '.join([f"{c.get('cohort', '?')}: {c.get('loans', '?')} loans, coll={c.get('coll_pct', '?')}, PAR30={c.get('par30', '?')}" for c in recent])
        sections.append(f"RECENT COHORTS: {coh_str}")

    # Loss waterfall totals
    wf = data.get('cohort_loss_waterfall', [])
    totals = next((w for w in wf if w.get('cohort') == 'TOTAL'), None)
    if totals:
        sections.append(f"LOSS WATERFALL (TOTAL): Disbursed ${totals.get('disbursed', 0):,.0f}, "
                       f"Gross default rate={totals.get('default_rate', '?')}, "
                       f"Fraud %={totals.get('fraud_pct', '?')}, "
                       f"Recovery rate (ex-fraud)={totals.get('recovery_rate_ex_fraud', '?')}, "
                       f"Net loss rate={totals.get('net_loss_rate', '?')}")
    # Per-vintage loss (recent 5)
    vintage_wf = [w for w in wf if w.get('cohort') != 'TOTAL'][-5:]
    if vintage_wf:
        vwf_str = ', '.join([f"{w.get('cohort', '?')}: default={w.get('default_rate', '?')}, net_loss={w.get('net_loss_rate', '?')}" for w in vintage_wf])
        sections.append(f"RECENT VINTAGE LOSSES: {vwf_str}")

    # Roll rates
    rr = data.get('roll_rates', [])
    if rr:
        rr_str = ', '.join([f"{r['bucket']}: cure={r.get('implied_cure_rate', '?')}, roll={r.get('implied_roll_rate', '?')}" for r in rr])
        sections.append(f"ROLL RATES: {rr_str}")

    # Segment analysis — summarize top segments by use case
    segs = data.get('segment_analysis', {})
    for dim_key, dim_label in [('use_case', 'USE CASE'), ('employment', 'EMPLOYMENT'), ('region', 'REGION')]:
        dim_data = segs.get(dim_key, [])
        if dim_data:
            top = sorted(dim_data, key=lambda s: s.get('loans', 0) or 0, reverse=True)[:3]
            seg_str = ', '.join([f"{s.get('segment', '?')}: {s.get('loans', '?')} loans, coll={s.get('coll_pct', '?')}, PAR30={s.get('par30', '?')}" for s in top])
            sections.append(f"SEGMENT ({dim_label}): {seg_str}")

    # Collections timing
    coll = data.get('collections_by_month', [])
    recent_coll = coll[-3:] if coll else []
    if recent_coll:
        coll_str = ', '.join([f"{c.get('month', '?')}: coll={c.get('coll_pct', '?')}" for c in recent_coll])
        sections.append(f"RECENT COLLECTIONS: {coll_str}")

    # Credit quality trends (recent 5)
    cq = data.get('credit_quality_trends', [])
    recent_cq = cq[-5:] if cq else []
    if recent_cq:
        cq_str = ', '.join([f"{c.get('cohort', '?')}: SIMAH={c.get('avg_simah', '?')}, salary={c.get('avg_salary', '?')}, DBR={c.get('avg_dbr', '?')}" for c in recent_cq])
        sections.append(f"CREDIT QUALITY TRENDS: {cq_str}")

    # Write-offs & fraud
    wo = data.get('writeoffs_fraud', {})
    wo_sum = wo.get('summary', {})
    if wo_sum:
        for metric, vals in wo_sum.items():
            sections.append(f"WRITE-OFF ({metric}): All={vals.get('all', '?')}, Fraud={vals.get('fraud', '?')}, Credit={vals.get('credit', '?')}")

    # Najiz & Legal (totals)
    najiz = data.get('najiz_legal', [])
    najiz_total = next((n for n in najiz if n.get('vintage') == 'TOTAL'), None)
    if najiz_total:
        sections.append(f"LEGAL RECOVERY: {najiz_total.get('cases', '?')} cases, "
                       f"execution rate={najiz_total.get('exec_rate', '?')}, "
                       f"recovery=${najiz_total.get('recovery', 0):,.0f}, "
                       f"fraud writeoff=${najiz_total.get('fraud_writeoff', 0):,.0f}")

    # Historical performance (recent vintages)
    hist = data.get('historical_performance', [])
    recent_hist = hist[-3:] if hist else []
    if recent_hist:
        h_str = ', '.join([f"{h.get('vintage', '?')}: gross_default={h.get('gross_default_pct', '?')}, LGD={h.get('lgd', '?')}" for h in recent_hist])
        sections.append(f"HISTORICAL PERFORMANCE: {h_str}")

    # Inject Living Mind context (Layer 2 + Layer 4)
    try:
        mind_ctx = build_mind_context('Ejari', 'RNPL',
                                       'executive_summary')
        if not mind_ctx.is_empty:
            sections.append("")
            sections.append("PLATFORM MEMORY:")
            sections.append(mind_ctx.formatted)
    except Exception:
        pass

    return '\n'.join(sections)


@app.get("/companies/{company}/products/{product}/ai-executive-summary")
def get_executive_summary(company: str, product: str,
                          snapshot: Optional[str] = None,
                          as_of_date: Optional[str] = None,
                          currency: Optional[str] = None,
                          refresh: bool = False,
                          mode: Optional[str] = None):
    """AI Executive Summary — holistic analysis of ALL computed metrics.

    Returns top 5-10 findings ranked by business impact with severity levels.
    Cached per (company, product, snapshot, as_of_date) — currency excluded
    since it only affects numeric display, not analytical findings.
    """
    sel_for_key = _resolve_snapshot(company, product, snapshot)
    snap_key = sel_for_key.get('filename', snapshot or '')
    snap_date = sel_for_key.get('date', '')
    _check_backdated(as_of_date, snap_date)
    cache_path = _ai_cache_key('executive_summary', company, product, snap_key, as_of_date or '', snapshot_date=snap_date, currency=currency or '')

    if not refresh:
        cached = _ai_cache_get(cache_path)
        if cached:
            return cached

    # Agent mode: skip manual context building — agent pulls data dynamically
    if mode == 'agent':
        try:
            from core.agents.internal import generate_agent_executive_summary
            section_guidance_map = {
                'tamara_summary': "Portfolio Overview & Scale, Vintage Default Performance, Delinquency Trends, Dilution, Covenant Compliance, Concentration, Financial Performance, Forward Outlook",
                'ejari_summary': "Portfolio Overview, Monthly Cohorts, Loss Waterfall, Roll Rates, Historical Performance, Segment Analysis, Credit Quality, Najiz & Legal, Write-offs",
                'silq': "Portfolio Overview, Delinquency & DPD, Collections by Product, Cohort Performance, Concentration, Yield & Tenure",
                'aajil': "Portfolio Overview, Traction, Delinquency, Collections, Cohorts, Concentration, Underwriting, Customer Segments, Forward Signals",
            }
            at = _get_analysis_type(company, product)
            guidance = section_guidance_map.get(at, None)
            summary_text = generate_agent_executive_summary(company, product, snapshot, currency, as_of_date, guidance)
            narrative, findings, analytics_coverage, _parsed_ok = _parse_agent_exec_summary_response(summary_text)
            result = {
                'narrative': narrative,
                'findings': findings,
                'analytics_coverage': analytics_coverage,
                'generated_at': datetime.now().isoformat(),
                'as_of_date': as_of_date or sel_for_key.get('date', ''),
                'mode': 'agent',
            }
            _ai_cache_put(cache_path, result)
            log_activity(AI_EXECUTIVE_SUMMARY, company, product, f"Generated agent executive summary for {snap_key}")
            return result
        except Exception:
            import traceback
            traceback.print_exc()
            # Fall through to legacy

    at = _get_analysis_type(company, product)

    if at == 'tamara_summary':
        sel = _resolve_snapshot(company, product, snapshot)
        filepath = sel['filepath']
        if filepath not in _tamara_cache:
            _tamara_cache[filepath] = parse_tamara_data(filepath)
        tamara_data = _tamara_cache[filepath]
        context = _build_tamara_full_context(tamara_data)
        company_desc = f"Tamara Buy Now Pay Later (BNPL + BNPL+) portfolio in {product}"
        disp = 'SAR' if product == 'KSA' else 'AED'
        n_metrics = len([l for l in context.split('\n') if l.strip()])
    elif at == 'aajil':
        df, aux, sel, config, disp, mult, ref_date = _aajil_tape_load(company, product, snapshot, as_of_date, currency)
        if df is not None:
            context = _build_aajil_full_context(df, mult=mult, ref_date=ref_date, aux=aux, config=config, disp=disp)
        else:
            filepath = sel['filepath']
            if filepath not in _aajil_cache:
                _aajil_cache[filepath] = parse_aajil_data(filepath)
            context = _build_aajil_full_context(_aajil_cache[filepath])
            disp = 'SAR'
        company_desc = "Aajil SME raw materials trade credit portfolio in KSA"
        n_metrics = len([l for l in context.split('\n') if l.strip()])
    elif at == 'ejari_summary':
        sel = _resolve_snapshot(company, product, snapshot)
        filepath = sel['filepath']
        if filepath not in _ejari_cache:
            _ejari_cache[filepath] = parse_ejari_workbook(filepath)
        ejari_data = _ejari_cache[filepath]
        context = _build_ejari_full_context(ejari_data)
        company_desc = "Ejari Rent Now Pay Later (RNPL) portfolio in KSA"
        disp = 'USD'
        n_metrics = len([l for l in context.split('\n') if l.strip()])
    elif at == 'silq':
        df, sel, config, disp, mult, _, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
        context = _build_silq_full_context(df, mult, ref_date, config, disp)
        company_desc = "SILQ POS lending portfolio (BNPL, RBF, RCL) in KSA"
        n_metrics = len([l for l in context.split('\n') if l.strip()])
    else:
        df, sel = _load(company, product, snapshot)
        df = filter_by_date(df, as_of_date)
        config, disp = _currency(company, product, currency)
        mult = apply_multiplier(config, disp)
        context = _build_klaim_full_context(df, mult, as_of_date or sel['date'], config, disp, sel['date'])
        company_desc = f"{company.upper()} healthcare claims factoring portfolio in UAE"
        n_metrics = len([l for l in context.split('\n') if l.strip()])

    # Company-specific narrative section guidance
    section_guidance = {
        'tamara_summary': (
            "Portfolio Overview & Scale, Vintage Default Performance, "
            "Delinquency Trends & DPD Analysis, Dilution & Refund Analysis, "
            "Covenant Compliance & Facility Health, Concentration Risk, "
            "Financial Performance & Unit Economics, BNPL+ Risk Assessment, "
            "Demographics & Segmentation, Forward Outlook"
        ),
        'ejari_summary': (
            "Portfolio Overview, Monthly Cohorts, Loss Waterfall, Roll Rates, "
            "Historical Performance, Segment Analysis, Credit Quality Trends, "
            "Najiz & Legal, Write-offs & Fraud"
        ),
        'silq': (
            "Portfolio Overview, Delinquency & DPD, Collections by Product, "
            "Cohort Performance, Concentration, Yield & Tenure"
        ),
        'aajil': (
            "Portfolio Overview & Scale, Traction (Volume & Balance), "
            "Delinquency & DPD (7/30/60/90), Collections by Vintage, "
            "Vintage Cohort Analysis, Concentration & Customer Types, "
            "Underwriting & Risk Mitigation, Trust Score Distribution, "
            "Customer Segments, Forward Signals"
        ),
    }
    sections_for = section_guidance.get(at,
        "Portfolio Overview, Cohort Performance, Collection & DSO, "
        "Denial & Loss Economics, Recovery & Risk Migration, "
        "Concentration & Segments, Forward Signals"
    )

    tab_slugs = {
        'tamara_summary': "overview, vintage, delinquency, default-analysis, dilution, collections, concentration, covenant-compliance, facility-structure, demographics, financial-performance, business-plan, bnpl-plus, notes",
        'ejari_summary': "overview, cohort, loss-waterfall, roll-rates, historical, collections-month, collections-orig, segments, credit-quality, najiz, writeoffs, notes",
        'silq': "overview, delinquency, collections, concentration, cohort-analysis, yield-margins, tenure, covenants",
        'aajil': "overview, traction, delinquency, collections, cohort-analysis, concentration, underwriting, trust-collections, customer-segments, yield-margins, loss-waterfall, covenants, notes",
    }
    tabs_for = tab_slugs.get(at,
        "overview, actual-vs-expected, deployment, collection, denial-trend, ageing, revenue, portfolio-tab, cohort-analysis, returns, risk-migration, loss-waterfall, recovery-analysis, underwriting-drift, segment-analysis, seasonality, cdr-ccr"
    )

    prompt = f"""You are a senior analyst at ACP Private Credit preparing an executive summary for the investment committee.

Company: {company_desc}
Data as of: {as_of_date or sel.get('date', '')}  |  Currency: {disp if 'disp' in dir() else 'N/A'}

COMPREHENSIVE ANALYTICS ({n_metrics} sections):
{context}

Produce a complete executive summary as a JSON object with two parts: a narrative credit memo and discrete findings.

Return this exact JSON structure:
{{
  "narrative": {{
    "sections": [
      {{
        "title": "Section Name",
        "content": "2-4 paragraphs of credit memo analysis. Use specific numbers from the data. Write in a professional, direct style — like a credit analyst presenting to an investment committee. Each paragraph should build the argument. Separate paragraphs with \\n\\n.",
        "conclusion": "One sentence takeaway for this section.",
        "metrics": [{{"label": "Metric Name", "value": "X.X%", "assessment": "healthy"}}]
      }}
    ],
    "summary_table": [
      {{"metric": "Key Metric", "value": "X.X%", "assessment": "Healthy"}}
    ],
    "bottom_line": "One paragraph (3-5 sentences) stating whether the book is investable, the primary risks, and 2-3 specific diligence items the IC should pursue."
  }},
  "findings": [
    {{
      "rank": 1,
      "severity": "critical" or "warning" or "positive",
      "title": "Short title (max 10 words)",
      "explanation": "2-3 sentences explaining why this matters and what action to take.",
      "data_points": ["Key number 1", "Key number 2"],
      "tab": "relevant-tab-slug"
    }}
  ]
}}

NARRATIVE RULES:
- Write sections in this order: {sections_for}
- Each section: 2-4 paragraphs with specific numbers. No vague statements.
- "content" should read like a credit memo — walk through the data, explain what it means, flag risks and positives.
- "conclusion" is a single sentence verdict for that section.
- "metrics" are the 2-4 most important numbers from that section. "assessment" must be one of: "healthy", "acceptable", "warning", "critical", "monitor".
- "summary_table": 6-10 rows covering the most important portfolio metrics across all sections. "assessment" values: "Healthy", "Acceptable", "Warning", "Critical", "Monitor".
- "bottom_line": state the investment thesis clearly. Is this book performing? What are the 2-3 things IC needs to diligence?

FINDINGS RULES:
- 5-10 findings ranked by business impact.
- "critical": immediate IC attention needed. "warning": monitor. "positive": good news.
- Tab slugs: {tabs_for}
- Be specific with numbers in data_points.

Return ONLY the JSON object, no other text."""

    from core.ai_client import complete as _ai_complete
    msg = _ai_complete(
        tier="judgment", system="", max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        log_prefix="ai-executive-summary",
    )

    # Parse the JSON response
    response_text = msg.content[0].text.strip()
    # Handle potential markdown code block wrapping
    if response_text.startswith('```'):
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

    try:
        parsed = json.loads(response_text)
        # Handle both old format (array of findings) and new format (object with narrative + findings)
        if isinstance(parsed, list):
            narrative = None
            findings = parsed
        else:
            narrative = parsed.get('narrative', None)
            findings = parsed.get('findings', [])
    except json.JSONDecodeError:
        narrative = None
        findings = [{'rank': 1, 'severity': 'warning', 'title': 'Summary generated',
                     'explanation': response_text, 'data_points': [], 'tab': 'overview'}]

    # D2: extract Layer 2.5 external citations so the UI can show the
    # reader which asset-class research fed this summary. Mind context
    # was already built inside the per-asset-class helpers above; we
    # rebuild here purely to pull the structured sources list (the
    # formatted text is already baked into the prompt). build_mind_context
    # reads from disk so the duplication is cheap.
    _asset_class_sources: list = []
    try:
        from core.mind import build_mind_context as _build_mind_ctx
        _mind_ctx = _build_mind_ctx(company, product, 'executive_summary')
        _asset_class_sources = _mind_ctx.asset_class_sources or []
    except Exception as e:
        logger.debug("exec_summary: asset_class_sources fetch failed: %s", e)

    result = {
        'narrative': narrative,
        'findings': findings,
        'generated_at': datetime.now().isoformat(),
        'as_of_date': as_of_date or sel.get('date', ''),
        'context_coverage': n_metrics,
        # D2: citation URLs that were in Layer 2.5 during generation,
        # deduped + capped at 50 in build_mind_context. Renders as a
        # collapsible "Informed by N sources" footer in the Exec Summary UI.
        'asset_class_sources': _asset_class_sources,
    }
    _ai_cache_put(cache_path, result)
    log_activity(AI_EXECUTIVE_SUMMARY, company, product, f"Generated executive summary for {snap_key}")
    return result


@app.get("/companies/{company}/products/{product}/ai-executive-summary/stream")
async def get_executive_summary_stream(
    company: str,
    product: str,
    request: Request,
    snapshot: Optional[str] = None,
    as_of_date: Optional[str] = None,
    currency: Optional[str] = None,
    refresh: bool = False,
):
    """Stream the agent-driven executive summary via SSE.

    The analyst agent runs with max_turns=20 in a background producer task;
    StreamEvents are drained through an asyncio.Queue. A ``: keepalive\\n\\n``
    SSE comment is emitted after 20s of idle — mirrors memo_generate_stream —
    so Cloudflare's ~100s edge-proxy cap can't kill long agent runs (Aajil
    legitimately exceeds 100s end-to-end). See tasks/lessons.md CF+SSE entry.

    Event types (heartbeats aside):
      start    — {company, product, snapshot}
      cached   — {from_cache: true}  (only on disk-cache hit)
      text / tool_call / tool_result / budget_warning — forwarded from runtime
      result   — {narrative, findings, asset_class_sources, generated_at, ...}
      error    — {message}
      done     — {ok, turns_used?, total_input_tokens?, total_output_tokens?, from_cache?}
    """
    import asyncio as _asyncio
    import time as _time
    from fastapi.responses import StreamingResponse

    # Same cache key / backdated guard as the sync endpoint so both share state
    sel_for_key = _resolve_snapshot(company, product, snapshot)
    snap_key = sel_for_key.get('filename', snapshot or '')
    snap_date = sel_for_key.get('date', '')
    _check_backdated(as_of_date, snap_date)
    cache_path = _ai_cache_key(
        'executive_summary', company, product, snap_key, as_of_date or '',
        snapshot_date=snap_date, currency=currency or ''
    )

    _sse_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # Disables nginx proxy_buffering — critical for SSE to flush byte-by-byte
        "X-Accel-Buffering": "no",
    }

    # Fast path: cached response → emit immediately (still as SSE so the
    # client uses one code path).
    if not refresh:
        cached = _ai_cache_get(cache_path)
        if cached:
            async def _cache_stream():
                yield f"event: start\ndata: {json.dumps({'company': company, 'product': product, 'snapshot': snap_key})}\n\n"
                yield f"event: cached\ndata: {json.dumps({'from_cache': True})}\n\n"
                yield f"event: result\ndata: {json.dumps(cached, default=str)}\n\n"
                yield f"event: done\ndata: {json.dumps({'ok': True, 'from_cache': True})}\n\n"
            return StreamingResponse(_cache_stream(), media_type="text/event-stream", headers=_sse_headers)

    # Per-company section guidance. Keys match analysis_type; fall through to
    # the default hierarchy-level guidance inside build_executive_summary_prompt.
    section_guidance_map = {
        'tamara_summary': "Portfolio Overview & Scale, Vintage Default Performance, Delinquency Trends, Dilution, Covenant Compliance, Concentration, Financial Performance, Forward Outlook",
        'ejari_summary': "Portfolio Overview, Monthly Cohorts, Loss Waterfall, Roll Rates, Historical Performance, Segment Analysis, Credit Quality, Najiz & Legal, Write-offs",
        'silq': "Portfolio Overview, Delinquency & DPD, Collections by Product, Cohort Performance, Concentration, Yield & Tenure",
        'aajil': "Portfolio Overview, Traction, Delinquency, Collections, Cohorts, Concentration, Underwriting, Customer Segments, Forward Signals",
    }
    at = _get_analysis_type(company, product)
    guidance = section_guidance_map.get(at)
    from core.agents.prompts import build_executive_summary_prompt
    prompt = build_executive_summary_prompt(
        company=company,
        product=product,
        snapshot=snapshot,
        currency=currency,
        as_of_date=as_of_date,
        section_guidance=guidance,
    )

    async def _stream():
        import threading as _threading
        from core.agents.config import load_agent_config
        from core.agents.runtime import AgentRunner
        from core.agents.session import AgentSession
        from core.agents.tools import build_tools_for_agent

        tool_specs = build_tools_for_agent("analyst")
        config = load_agent_config("analyst", tool_specs=tool_specs)
        config.max_turns = 20
        # Exec summary emits ~6-10 sections + 5-10 findings as structured JSON;
        # the analyst default (2000) truncates mid-string, making the response
        # unparseable. 16000 gives ~12K words of headroom.
        config.max_tokens_per_response = 16000
        session = AgentSession.create("analyst", metadata={
            "company": company, "product": product, "type": "executive_summary",
        })
        runner = AgentRunner(config)

        queue: _asyncio.Queue = _asyncio.Queue()
        SENTINEL = object()
        stop_event = _threading.Event()
        loop = _asyncio.get_event_loop()

        def _thread_push(item):
            # Thread-safe enqueue onto the main event loop's asyncio.Queue.
            # Called from the producer thread.
            try:
                loop.call_soon_threadsafe(queue.put_nowait, item)
            except RuntimeError:
                # Loop already closed (client disconnected + handler exited) — drop.
                pass

        # Run the agent's async stream in a DEDICATED thread with its own loop.
        # The analyst agent uses the SYNC Anthropic client, whose blocking HTTP
        # reads would otherwise freeze uvicorn's main event loop — killing
        # heartbeats AND preventing the consumer below from draining the queue.
        # See tasks/lessons.md 2026-04-19 entry; mirrors memo_generate_stream's
        # ThreadPoolExecutor offload (backend/agents.py).
        def _producer_thread():
            import asyncio as _a
            t_loop = _a.new_event_loop()
            _a.set_event_loop(t_loop)
            try:
                async def _drain():
                    async for event in runner.stream(prompt, session):
                        if stop_event.is_set():
                            break
                        _thread_push(event)
                t_loop.run_until_complete(_drain())
            except Exception as e:
                _thread_push(("__error__", e))
            finally:
                _thread_push(SENTINEL)
                try:
                    t_loop.close()
                except Exception:
                    pass

        producer_thread = _threading.Thread(target=_producer_thread, daemon=True)
        producer_thread.start()
        HEARTBEAT_INTERVAL_S = 20
        full_text: list = []
        agent_done_data: dict = {}
        stream_error: Optional[str] = None
        emitted_result = False

        # Announce the stream immediately — gives the client something to
        # render (status chip, elapsed timer) while the first Claude turn spins up.
        yield f"event: start\ndata: {json.dumps({'company': company, 'product': product, 'snapshot': snap_key})}\n\n"
        last_yield = _time.monotonic()

        try:
            while True:
                if await request.is_disconnected():
                    stop_event.set()
                    return

                try:
                    event = await _asyncio.wait_for(queue.get(), timeout=0.5)
                except _asyncio.TimeoutError:
                    if _time.monotonic() - last_yield >= HEARTBEAT_INTERVAL_S:
                        yield ": keepalive\n\n"
                        last_yield = _time.monotonic()
                    continue

                if event is SENTINEL:
                    break

                if isinstance(event, tuple) and event and event[0] == "__error__":
                    stream_error = f"{type(event[1]).__name__}: {event[1]}"
                    yield f"event: error\ndata: {json.dumps({'message': stream_error})}\n\n"
                    last_yield = _time.monotonic()
                    continue

                # StreamEvent from the agent runtime
                if event.type == "text":
                    full_text.append(event.data.get("delta", ""))

                if event.type == "done":
                    # Agent finished (no more tool calls). Parse the
                    # accumulated text, cache, emit our structured result,
                    # then fall through so the outer done below summarises
                    # metadata — we swallow the runtime's done because it
                    # duplicates meaning.
                    agent_done_data = dict(event.data or {})

                    response_text = "".join(full_text)
                    narrative, findings, analytics_coverage, _parsed_ok = _parse_agent_exec_summary_response(response_text)

                    # Layer 2.5 citations — same as sync endpoint
                    _asset_class_sources: list = []
                    try:
                        _mind_ctx = build_mind_context(company, product, "executive_summary")
                        _asset_class_sources = _mind_ctx.asset_class_sources or []
                    except Exception as _mind_err:
                        logger.debug("exec_summary_stream: asset_class_sources fetch failed: %s", _mind_err)

                    result_payload = {
                        "narrative": narrative,
                        "findings": findings,
                        "analytics_coverage": analytics_coverage,
                        "generated_at": datetime.now().isoformat(),
                        "as_of_date": as_of_date or snap_date,
                        "mode": "agent",
                        "asset_class_sources": _asset_class_sources,
                    }

                    try:
                        _ai_cache_put(cache_path, result_payload)
                        log_activity(
                            AI_EXECUTIVE_SUMMARY, company, product,
                            f"Generated streaming executive summary for {snap_key}",
                        )
                    except Exception as _cache_err:
                        logger.warning("exec_summary_stream: cache write failed: %s", _cache_err)

                    yield f"event: result\ndata: {json.dumps(result_payload, default=str)}\n\n"
                    last_yield = _time.monotonic()
                    emitted_result = True
                    # Swallow the runtime's done — we emit a single terminal
                    # `done` in the finally block so the client has one place
                    # to hang "stream complete" UI off.
                    continue

                # Pass through every other event (text, tool_call, tool_result,
                # budget_warning, error) exactly as the runtime emitted it.
                yield event.to_sse()
                last_yield = _time.monotonic()

                # Capture runtime-yielded error events into stream_error so the
                # terminal `done` payload carries the message. Without this,
                # onError in the frontend would fire with the real message, then
                # onDone would clobber it with the fallback "Stream ended without
                # a result" because d.error was empty. The runtime has already
                # returned after yielding error (runtime.py:491-499), so the
                # producer thread will push SENTINEL shortly.
                if event.type == "error" and stream_error is None:
                    stream_error = (event.data or {}).get("message") or "agent runtime error"
        finally:
            # Internal session — no persistence. Safe-delete best-effort.
            try:
                session.delete()
            except Exception:
                pass
            # Signal the producer thread to stop. It'll push SENTINEL and
            # exit on its next iteration. We don't join here — the thread is
            # daemon + best-effort; a lingering request to Anthropic will
            # unwind on its own.
            stop_event.set()

        # Terminal done — merges agent metadata when we have it.
        done_payload = {
            "ok": emitted_result and stream_error is None,
            "turns_used": agent_done_data.get("turns_used"),
            "total_input_tokens": agent_done_data.get("total_input_tokens"),
            "total_output_tokens": agent_done_data.get("total_output_tokens"),
        }
        if stream_error:
            done_payload["error"] = stream_error
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream", headers=_sse_headers)


@app.get("/companies/{company}/products/{product}/ai-tab-insight")
def get_tab_insight(company: str, product: str,
                    tab: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None,
                    refresh: bool = False,
                    mode: Optional[str] = None):
    """Generate a short AI insight for a specific dashboard tab. Cached per (company, product, snapshot, as_of_date, tab)."""
    sel_for_key = _resolve_snapshot(company, product, snapshot)
    snap_key = sel_for_key.get('filename', snapshot or '')
    snap_date = sel_for_key.get('date', '')
    _check_backdated(as_of_date, snap_date)
    cache_path = _ai_cache_key('tab_insight', company, product, snap_key, as_of_date or '', tab, snapshot_date=snap_date, currency=currency or '')

    if not refresh:
        cached = _ai_cache_get(cache_path)
        if cached:
            return cached

    at = _get_analysis_type(company, product)

    if at == 'silq':
        df, sel, config, disp, mult, _, ref_date = _silq_load(company, product, snapshot, as_of_date, currency)
    else:
        df, sel  = _load(company, product, snapshot)
        df       = filter_by_date(df, as_of_date)
        config, disp = _currency(company, product, currency)
        mult     = apply_multiplier(config, disp)
        ref_date = None

    # Build tab-specific data context
    tab_data = {}
    if at == 'silq':
        if tab == 'delinquency':
            tab_data = compute_silq_delinquency(df, mult, ref_date=ref_date)
        elif tab == 'collections':
            tab_data = compute_silq_collections(df, mult)
        elif tab == 'concentration':
            conc = compute_silq_concentration(df, mult)
            tab_data = {'top_shops': conc['shops'][:5], 'hhi': conc['hhi'], 'product_mix': conc['product_mix']}
        elif tab == 'cohort':
            tab_data = compute_silq_cohorts(df, mult, ref_date=ref_date)
        elif tab == 'yield-margins':
            tab_data = compute_silq_yield(df, mult)
        elif tab == 'tenure':
            tab_data = compute_silq_tenure(df, mult, ref_date=ref_date)
    else:
        if tab == 'deployment':
            tab_data = {'monthly_deployment': compute_deployment(df, mult)[-12:]}
        elif tab == 'collection':
            cv = compute_collection_velocity(df, mult, as_of_date)
            tab_data = {'buckets': cv['buckets'], 'recent_monthly': cv['monthly'][-12:]}
        elif tab == 'denial-trend':
            tab_data = {'denial_trend': compute_denial_trend(df, mult)[-12:]}
        elif tab == 'ageing':
            ag = compute_ageing(df, mult, as_of_date)
            tab_data = {'health_summary': ag['health_summary'], 'ageing_buckets': ag['ageing_buckets']}
        elif tab == 'revenue':
            rev = compute_revenue(df, mult)
            tab_data = {'totals': rev['totals'], 'recent_monthly': rev['monthly'][-12:]}
        elif tab == 'concentration':
            conc = compute_concentration(df, mult)
            tab_data = {'top_groups': conc.get('group', [])[:5], 'top_deals': conc.get('top_deals', [])[:5]}
        elif tab == 'cohort':
            tab_data = {'cohorts': compute_cohorts(df, mult)[-12:]}
        elif tab == 'actual-vs-expected':
            ave = compute_actual_vs_expected(df, mult)
            tab_data = {'overall_performance': ave['overall_performance'],
                        'total_collected': ave['total_collected'],
                        'total_expected': ave['total_expected'],
                        'recent': ave['data'][-6:]}
        elif tab == 'returns':
            ret = compute_returns_analysis(df, mult)
            tab_data = {'summary': ret['summary'], 'recent_monthly': ret['monthly'][-12:]}
        elif tab == 'risk-migration':
            el = compute_expected_loss(df, mult)
            st = compute_stress_test(df, mult)
            tab_data = {'expected_loss': el['portfolio'], 'stress_scenarios': st['scenarios']}

    tab_labels = {
        'deployment':          'Capital Deployment',
        'collection':          'Collection Velocity',
        'collection-velocity': 'Collection Velocity',
        'denial-trend':        'Denial Rate Trend',
        'ageing':              'Portfolio Ageing & Health',
        'revenue':             'Revenue Analysis',
        'concentration':       'Portfolio Concentration',
        'cohort':              'Cohort Analysis',
        'actual-vs-expected':  'Actual vs Expected',
        'returns':             'Returns Analysis',
        'risk-migration':      'Risk & Migration Analysis',
        'delinquency':         'Delinquency Analysis',
        'collections':         'Collections Analysis',
        'yield-margins':       'Yield & Margins',
        'tenure':              'Tenure Analysis',
    }

    prompt = f"""You are a senior credit analyst at ACP Private Credit reviewing the {tab_labels.get(tab, tab)} view for {company.upper()} ({product.replace('_', ' ').title()}) as of {as_of_date or sel['date']}.

DATA:
{tab_data}

Write 2-3 sentences of sharp, data-driven insight specifically about what this view shows.
Call out the single most important trend or concern visible in this data.
Be direct and specific — no generic commentary. No headers, just prose."""

    # Agent mode: agent pulls data dynamically via tools
    if mode == 'agent':
        try:
            from core.agents.internal import generate_agent_tab_insight
            insight_text = generate_agent_tab_insight(company, product, tab, snapshot, currency, as_of_date)
            result = {'insight': insight_text, 'tab': tab, 'mode': 'agent'}
            _ai_cache_put(cache_path, result)
            log_activity(AI_TAB_INSIGHT, company, product, f"Generated agent tab insight: {tab}")
            return result
        except Exception:
            import traceback
            traceback.print_exc()
            # Fall through to legacy

    from core.ai_client import complete as _ai_complete
    msg = _ai_complete(
        tier="structured", system="", max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
        log_prefix=f"ai-tab-insight.{tab}",
    )
    result = {'insight': msg.content[0].text, 'tab': tab}
    _ai_cache_put(cache_path, result)
    log_activity(AI_TAB_INSIGHT, company, product, f"Generated tab insight: {tab}")
    return result

@app.post("/companies/{company}/products/{product}/chat")
def chat_with_data(company: str, product: str, request: dict,
                   snapshot: Optional[str] = None,
                   as_of_date: Optional[str] = None,
                   currency: Optional[str] = None,
                   mode: Optional[str] = None):
    # Allow snapshot/currency from body (frontend sends them there) or query params
    snap = snapshot or request.get('snapshot')
    cur  = currency or request.get('currency')
    aod  = as_of_date or request.get('as_of_date')

    # Agent mode — use analyst agent with full tool access
    if mode == "agent":
        try:
            from core.agents.internal import generate_agent_chat
            answer = generate_agent_chat(company, product, request.get('question', ''), snap, cur, aod)
            log_activity(AI_CHAT, company, product, f"Agent chat: {request.get('question', '')[:80]}")
            return {'answer': answer, 'question': request.get('question', '')}
        except Exception:
            pass  # Fall through to legacy

    at = _get_analysis_type(company, product)

    if at == 'silq':
        return _silq_chat(company, product, request, snap, aod, cur)

    df, sel  = _load(company, product, snap)
    df       = filter_by_date(df, aod)
    config, disp = _currency(company, product, cur)
    mult     = apply_multiplier(config, disp)
    s        = compute_summary(df, config, disp, sel['date'], aod)

    from core.analysis import add_month_column
    monthly  = add_month_column(df).groupby('Month').agg(
        purchase_value = ('Purchase value', 'sum'),
        collected      = ('Collected till date', 'sum'),
        denied         = ('Denied by insurance', 'sum'),
        deal_count     = ('Purchase value', 'count'),
    ).reset_index()
    monthly['collection_rate'] = (monthly['collected'] / monthly['purchase_value'] * 100).round(1)
    monthly['denial_rate']     = (monthly['denied']    / monthly['purchase_value'] * 100).round(1)

    # ── Enriched context sections (each wrapped so failures are logged but skipped) ──

    group_perf_ctx = ""
    try:
        gp = compute_group_performance(df, mult, aod)
        top_groups = gp['groups'][:8]
        rows = []
        for g in top_groups:
            rows.append(f"  {g['group']}: {g['deal_count']} deals, "
                        f"coll {g['collection_rate']}%, denial {g['denial_rate']}%, "
                        f"DSO {g['dso']:.0f}d")
        if rows:
            group_perf_ctx = "\nGROUP PERFORMANCE (top 8 providers):\n" + "\n".join(rows)
    except Exception as e:
        logger.debug("Chat context: group_performance failed: %s", e)

    ageing_ctx = ""
    try:
        ag = compute_ageing(df, mult, aod)
        health = {h['status']: f"{h['percentage']}% ({h['deal_count']})" for h in ag['health_summary']}
        ageing_ctx = (f"\nACTIVE PORTFOLIO HEALTH ({ag['total_active_deals']} active deals):\n"
                      f"  {', '.join(f'{k}: {v}' for k, v in health.items())}")
    except Exception as e:
        logger.debug("Chat context: ageing failed: %s", e)

    dso_ctx = ""
    try:
        dso = compute_dso(df, mult, aod)
        dso_ctx = (f"\nDSO (Days Sales Outstanding, completed deals):\n"
                   f"  Weighted avg: {dso['weighted_dso']:.0f} days, "
                   f"Median: {dso['median_dso']:.0f} days, "
                   f"P95: {dso['p95_dso']:.0f} days")
    except Exception as e:
        logger.debug("Chat context: dso failed: %s", e)

    # compute_returns_analysis mutates df, so pass a copy
    ret = None
    try:
        ret = compute_returns_analysis(df.copy(), mult)
    except Exception as e:
        logger.debug("Chat context: returns_analysis failed: %s", e)

    returns_ctx = ""
    if ret:
        try:
            rs = ret['summary']
            returns_ctx = (f"\nRETURNS & MARGINS:\n"
                           f"  Avg discount: {rs['avg_discount']:.1f}%, "
                           f"Wgt avg discount: {rs['weighted_avg_discount']:.1f}%\n"
                           f"  Expected margin: {rs['expected_margin']:.1f}%, "
                           f"Realised margin: {rs['realised_margin']:.1f}%, "
                           f"Completed margin: {rs['completed_margin']:.1f}%\n"
                           f"  Fee yield: {rs['fee_yield']:.2f}%, "
                           f"Completed loss rate: {rs['completed_loss_rate']:.1f}%")
        except Exception as e:
            logger.debug("Chat context: returns_ctx failed: %s", e)

    discount_ctx = ""
    if ret and ret.get('discount_bands'):
        try:
            band_rows = []
            for b in ret['discount_bands']:
                band_rows.append(f"  {b['band']}: {b['deals']} deals, "
                                 f"coll {b['collection_rate']}%, "
                                 f"denial {b['denial_rate']}%, "
                                 f"margin {b['margin']:.1f}%")
            discount_ctx = "\nDISCOUNT BAND PERFORMANCE:\n" + "\n".join(band_rows)
        except Exception as e:
            logger.debug("Chat context: discount_bands failed: %s", e)

    new_repeat_ctx = ""
    if ret and ret.get('new_vs_repeat'):
        try:
            nr_rows = []
            for seg in ret['new_vs_repeat']:
                nr_rows.append(f"  {seg['type']}: {seg['deals']} deals, "
                               f"coll {seg['collection_rate']}%, "
                               f"denial {seg['denial_rate']}%, "
                               f"margin {seg['margin']:.1f}%")
            new_repeat_ctx = "\nNEW vs REPEAT BUSINESS:\n" + "\n".join(nr_rows)
        except Exception as e:
            logger.debug("Chat context: new_vs_repeat failed: %s", e)

    hhi_ctx = ""
    try:
        hhi = compute_hhi(df, mult)
        parts = []
        labels = {'group': 'Group', 'provider': 'Provider', 'product': 'Product'}
        for key in ['group', 'provider', 'product']:
            if key in hhi:
                h = hhi[key]
                parts.append(f"  {labels[key]}: HHI={h['hhi']:.4f}, "
                             f"Top1={h['top_1_pct']}%, Top5={h['top_5_pct']}% "
                             f"({h['count']} unique)")
        if parts:
            hhi_ctx = "\nCONCENTRATION (HHI):\n" + "\n".join(parts)
    except Exception as e:
        logger.debug("Chat context: hhi failed: %s", e)

    # ── New enrichment sections (collection curves, IRR, owner) ──

    irr_ctx = ""
    if ret and ret['summary'].get('has_irr'):
        try:
            rs = ret['summary']
            irr_ctx = (f"\nIRR ANALYSIS:\n"
                       f"  Avg Expected IRR: {rs['avg_expected_irr']:.1f}%, "
                       f"Avg Actual IRR: {rs['avg_actual_irr']:.1f}%\n"
                       f"  IRR Spread: {rs['irr_spread']:+.1f}%, "
                       f"Median Actual IRR: {rs['median_actual_irr']:.1f}%")
        except Exception as e:
            logger.debug("Chat context: irr failed: %s", e)

    collection_speed_ctx = ""
    try:
        curves = compute_collection_curves(df, mult)
        if curves.get('available'):
            agg = curves['aggregate']['points']
            speed_rows = []
            for pt in agg:
                if pt['days'] in [90, 180, 360]:
                    speed_rows.append(f"  {pt['days']}d: Expected {pt['expected_pct']:.1f}%, "
                                      f"Actual {pt['actual_pct']:.1f}%, "
                                      f"Accuracy {pt['accuracy']:.0f}%")
            if speed_rows:
                collection_speed_ctx = "\nCOLLECTION SPEED (% of PV collected by interval):\n" + "\n".join(speed_rows)
    except Exception as e:
        logger.debug("Chat context: collection_speed failed: %s", e)

    owner_ctx = ""
    try:
        owner_data = compute_owner_breakdown(df, mult)
        if owner_data.get('available'):
            owner_rows = []
            for o in owner_data['owners']:
                owner_rows.append(f"  {o['owner']}: {o['deal_count']} deals, "
                                  f"{o['percentage']:.1f}% of portfolio, "
                                  f"coll {o['collection_rate']:.1f}%, "
                                  f"denial {o['denial_rate']:.1f}%")
            if owner_rows:
                owner_ctx = "\nOWNER/SPV BREAKDOWN:\n" + "\n".join(owner_rows)
    except Exception as e:
        logger.debug("Chat context: owner_breakdown failed: %s", e)

    # Inject mind context with graph-aware scoring keyed to user question
    mind_chat_ctx = ""
    asset_class_sources: list = []
    try:
        mind_ctx = build_mind_context(company, product, 'chat',
                                       query_text=request.get('question', ''))
        if not mind_ctx.is_empty:
            mind_chat_ctx = f"\n\nPLATFORM MEMORY:\n{mind_ctx.formatted}"
        asset_class_sources = mind_ctx.asset_class_sources or []
    except Exception as e:
        logger.debug("Chat context: mind failed: %s", e)

    system = f"""You are an expert credit analyst assistant for ACP Private Credit,
analyzing the {company.upper()} - {product.replace('_', ' ').title()} loan portfolio.

PORTFOLIO SUMMARY (as of {aod or sel['date']}, currency: {disp}):
- Total Deals: {s['total_deals']:,} ({s['active_deals']} active, {s['completed_deals']} completed)
- Purchase Value: {disp} {s['total_purchase_value']/1e6:.2f}M
- Collection Rate: {s['collection_rate']:.1f}%
- Denial Rate: {s['denial_rate']:.1f}%
- Pending Response: {disp} {s['total_pending']/1e6:.2f}M ({s['pending_rate']:.1f}%)

MONTHLY PERFORMANCE (last 12 months):
{monthly.tail(12).to_string(index=False)}
{group_perf_ctx}{ageing_ctx}{dso_ctx}{returns_ctx}{discount_ctx}{new_repeat_ctx}{hhi_ctx}{irr_ctx}{collection_speed_ctx}{owner_ctx}{mind_chat_ctx}

INSTRUCTIONS:
- Answer questions precisely with specific numbers from the data above. Be concise but thorough.
- When a question requires deal-level detail, individual deal lookups, or data not available in your context, provide the best answer you can from what is available and note that for more granular detail the analyst should consult the full loan tape or reach out to the deal team.
- Do not fabricate numbers. If a metric is not in your context, say so."""

    msgs = [{"role": ("assistant" if h.get('role') == 'ai' else h.get('role', 'user')),
             "content": h.get('content') or h.get('text', '')}
            for h in request.get('history', [])[-6:]]
    msgs.append({"role": "user", "content": request.get('question', '')})

    from core.ai_client import complete as _ai_complete
    resp = _ai_complete(
        tier="structured", system=system, max_tokens=1000,
        messages=msgs, log_prefix=f"chat.{company}",
    )
    log_activity(AI_CHAT, company, product, f"Chat: {request.get('question', '')[:80]}")
    return {
        'answer': resp.content[0].text,
        'question': request.get('question', ''),
        # D2: surface Layer 2.5 external sources that were in context so
        # the analyst can see what external research fed the answer.
        # Already deduped + capped in build_mind_context.
        'asset_class_sources': asset_class_sources,
    }


def _silq_chat(company, product, request, snap, aod, cur):
    """SILQ-specific data chat with enriched context."""
    df, sel, config, disp, mult, commentary_text, ref_date = _silq_load(company, product, snap, aod, cur)
    s = compute_silq_summary(df, mult, ref_date=ref_date)
    d = compute_silq_delinquency(df, mult, ref_date=ref_date)
    c = compute_silq_collections(df, mult)
    conc = compute_silq_concentration(df, mult)
    y = compute_silq_yield(df, mult)
    t = compute_silq_tenure(df, mult)

    commentary_ctx = ''
    if commentary_text:
        commentary_ctx = f"\nANALYST PORTFOLIO COMMENTARY (from tape):\n{commentary_text}\n"

    # Inject mind context with graph-aware scoring keyed to user question
    mind_chat_ctx = ""
    asset_class_sources: list = []
    try:
        mind_ctx = build_mind_context(company, product, 'chat',
                                       query_text=request.get('question', ''))
        if not mind_ctx.is_empty:
            mind_chat_ctx = f"\n\nPLATFORM MEMORY:\n{mind_ctx.formatted}"
        asset_class_sources = mind_ctx.asset_class_sources or []
    except Exception as e:
        logger.debug("SILQ chat context: mind failed: %s", e)

    system = f"""You are an expert credit analyst assistant for ACP Private Credit,
analyzing the SILQ POS lending portfolio (BNPL, RBF & RCL loans) in KSA.

PORTFOLIO SUMMARY (as of {aod or sel['date']}, currency: {disp}):
- Total Loans: {s['total_deals']:,} ({s['active_deals']} active, {s['completed_deals']} closed)
- Total Disbursed: {disp} {s['total_disbursed']/1e6:.2f}M
- Outstanding: {disp} {s['total_outstanding']/1e6:.2f}M
- Total Overdue: {disp} {s['total_overdue']/1e6:.2f}M
- Collection Rate: {s['collection_rate']:.1f}%
- PAR30: {s['par30']:.1f}%, PAR60: {s['par60']:.1f}%, PAR90: {s['par90']:.1f}%
- Product Mix: {s['product_mix']}
- Avg Tenure: {s['avg_tenure']:.0f} weeks

DPD BUCKETS:
{chr(10).join(f"  {b['label']}: {b['count']} loans ({b['pct']:.1f}%), {disp} {b['amount']/1e6:.2f}M" for b in d['buckets'])}

COLLECTION BY PRODUCT:
{chr(10).join(f"  {p['product']}: {p['rate']:.1f}% rate, {p['deals']} deals, {disp} {p['repaid']/1e6:.2f}M repaid" for p in c['by_product'])}

TOP SHOPS BY DISBURSEMENT:
{chr(10).join(f"  Shop {sh['shop_id']}: {sh['share']:.1f}% share, {sh['deals']} deals" for sh in conc['shops'][:8])}

SHOP CONCENTRATION: HHI = {conc['hhi']:.4f}

YIELD & MARGINS:
  Portfolio margin rate: {y['margin_rate']:.2f}%
  Realised margin (closed only): {y['realised_margin_rate']:.2f}%
  By product: {[f"{p['product']}: {p['margin_rate']:.2f}%" for p in y['by_product']]}

TENURE ANALYSIS:
  Avg: {t['avg_tenure']:.0f} weeks, Median: {t['median_tenure']:.0f} weeks
  By product: {[f"{p['product']}: avg {p['avg_tenure']:.0f}w" for p in t['by_product']]}
{commentary_ctx}{mind_chat_ctx}
INSTRUCTIONS:
- Answer questions precisely with specific numbers from the data above. Be concise but thorough.
- When a question requires deal-level detail or data not in your context, provide the best answer you can and note limitations.
- Do not fabricate numbers. If a metric is not in your context, say so."""

    msgs = [{
        "role": ("assistant" if h.get('role') == 'ai' else h.get('role', 'user')),
        "content": h.get('content') or h.get('text', '')
    } for h in request.get('history', [])[-6:]]
    msgs.append({"role": "user", "content": request.get('question', '')})

    from core.ai_client import complete as _ai_complete
    resp = _ai_complete(
        tier="structured", system=system, max_tokens=1000,
        messages=msgs, log_prefix="chat.silq",
    )
    log_activity(AI_CHAT, company, product, f"Chat: {request.get('question', '')[:80]}")
    return {
        'answer': resp.content[0].text,
        'question': request.get('question', ''),
        'asset_class_sources': asset_class_sources,
    }
# ── Portfolio Analytics endpoints ─────────────────────────────────────────────

def _facility_params_path(company, product):
    """Path to stored facility parameters JSON."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..',
        'data', company, product, 'facility_params.json'
    )


def _covenant_history_path(company, product):
    """Path to covenant breach history JSON."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..',
        'data', company, product, 'covenant_history.json'
    )


def _load_covenant_history(company, product):
    """Load covenant breach history. Returns {covenant_name: [{period, compliant, date}, ...]}."""
    path = _covenant_history_path(company, product)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def _save_covenant_history(company, product, result):
    """Persist current covenant results into history file.
    Appends current period's results, keeping newest-first order, max 24 periods.
    """
    path = _covenant_history_path(company, product)
    history = _load_covenant_history(company, product)

    test_date = result.get('test_date', '')
    for cov in result.get('covenants', []):
        name = cov['name']
        if not cov.get('eod_rule'):
            continue
        record = {
            'period': cov.get('period', test_date),
            'compliant': cov.get('compliant', True),
            'current': cov.get('current'),
            'date': test_date,
            'method': cov.get('method'),  # see core/portfolio.py for taxonomy
        }
        records = history.get(name, [])
        # Deduplicate: replace existing record with same date
        records = [r for r in records if r.get('date') != test_date]
        records.insert(0, record)
        # Keep max 24 periods
        history[name] = records[:24]

    with open(path, 'w') as f:
        json.dump(history, f, indent=2)

def _load_facility_params(company, product):
    """Load facility params with 3-tier priority:
    1. Manual overrides (facility_params.json) — highest priority
    2. Document-extracted values (legal/) — baseline
    3. Hardcoded defaults (in compute functions) — fallback
    """
    from core.legal_compliance import merge_facility_params

    # Load manual params
    path = _facility_params_path(company, product)
    manual = {}
    if os.path.exists(path):
        with open(path, 'r') as f:
            manual = json.load(f)

    # Merge with document-extracted values (legal takes baseline, manual overrides)
    return merge_facility_params(company, product, manual)

def _portfolio_load(company, product, snapshot, as_of_date, currency, db=None):
    """Load a snapshot from DB for portfolio computation.

    DB is the authoritative source after Session 31. Tape files populate DB via
    scripts/ingest_tape.py (one snapshot per file); Integration API writes land
    in a rolling daily live snapshot (scripts/ingest_tape.py or the API writes
    directly). There is no tape-fallback read path — if the requested snapshot
    doesn't exist in DB, the endpoint 404s. `snapshot` accepts a snapshot name
    (e.g. "2026-04-15_uae_healthcare"), a filename with extension, or an ISO
    date; `None` resolves to the latest snapshot by `taken_at`.

    Only supported for klaim + silq analysis types. Ejari/Tamara/Aajil use
    non-tape ingestion (pre-computed summaries, data rooms) and don't participate
    in portfolio analytics.
    """
    config = load_config(company, product)
    analysis_type = config.get('analysis_type', '') if config else ''
    disp = currency or (config['currency'] if config else 'USD')
    mult = apply_multiplier(config, disp)

    if analysis_type not in ('klaim', 'silq'):
        raise HTTPException(
            status_code=400,
            detail=f"Portfolio analytics not available for analysis_type={analysis_type!r}",
        )

    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    snap = resolve_snapshot(db, company, product, snapshot)
    if snap is None:
        detail = (
            f"Snapshot not found: {snapshot!r}"
            if snapshot
            else f"No snapshots exist for {company}/{product}. "
                 f"Run `python scripts/ingest_tape.py --company {company} --product {product} --all`."
        )
        raise HTTPException(status_code=404, detail=detail)

    # If caller passed as_of_date AND it matches a real snapshot's taken_at,
    # prefer that snapshot over the one named in `snapshot`. This lets a
    # Portfolio "as-of date" dropdown act as a snapshot selector without the
    # frontend needing to wire both fields: pick a date → backend picks the
    # matching snapshot (same-day) and uses that date as ref_date. Falls back
    # to the resolved snapshot + filter otherwise (user picking an arbitrary
    # date that isn't an ingest point).
    if as_of_date:
        date_match = resolve_snapshot(db, company, product, snapshot=as_of_date)
        if date_match is not None and str(date_match.taken_at) == str(as_of_date):
            snap = date_match

    df = load_from_db(db, company, product, snapshot_id=snap.id)
    if as_of_date:
        df = filter_by_date(df, as_of_date) if analysis_type == 'klaim' else filter_silq_by_date(df, as_of_date)

    sel = {
        'id': str(snap.id),
        'filename': snap.name,
        'name': snap.name,
        'date': snap.taken_at.isoformat(),
        'source': snap.source,
    }
    ref_date = as_of_date or sel['date']

    facility_params = _load_facility_params(company, product)
    facility_params.update(db_facility_config(db, company, product))
    if config and 'usd_rate' in config:
        facility_params.setdefault('usd_rate', config['usd_rate'])

    return df, sel, config, disp, mult, ref_date, facility_params, analysis_type


@app.get("/companies/{company}/products/{product}/portfolio/borrowing-base")
def get_portfolio_borrowing_base(company: str, product: str,
                                  snapshot: Optional[str] = None,
                                  as_of_date: Optional[str] = None,
                                  currency: Optional[str] = None,
                                  db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    if atype == 'silq':
        result = portfolio_borrowing_base(df, mult, ref_date, fp)
    else:
        result = compute_klaim_borrowing_base(df, mult, ref_date, fp)

    # --- Movement Attribution: diff BB components vs previous snapshot ---
    try:
        snaps = get_snapshots(company, product)
        if len(snaps) >= 2:
            current_idx = next(
                (i for i, s in enumerate(snaps) if s['date'] == sel.get('date')), 0
            )
            prev_idx = current_idx - 1  # snaps sorted oldest-first (ascending)
            if prev_idx >= 0:
                prev_snap = snaps[prev_idx]
                if atype == 'silq':
                    prev_df, _ = load_silq_snapshot(prev_snap['filepath'])
                else:
                    prev_df = load_snapshot(prev_snap['filepath'])
                prev_ref = prev_snap['date']
                if atype == 'silq':
                    prev_result = portfolio_borrowing_base(prev_df, mult, prev_ref, fp)
                else:
                    prev_result = compute_klaim_borrowing_base(prev_df, mult, prev_ref, fp)

                def _d(a, b):
                    a = float(a) if isinstance(a, (int, float)) else 0.0
                    b = float(b) if isinstance(b, (int, float)) else 0.0
                    return a - b

                ck = result['kpis']
                pk = prev_result['kpis']
                net_change = _d(ck['borrowing_base'], pk['borrowing_base'])
                d_total = _d(ck['total_ar'], pk['total_ar'])
                d_inelig = -_d(ck['ineligible'], pk['ineligible'])

                steps = [
                    {'label': 'Previous Borrowing Base', 'value': pk['borrowing_base'], 'type': 'start'},
                    {'label': 'Δ Portfolio Size (Total A/R)', 'value': d_total, 'type': 'delta'},
                    {'label': 'Δ Eligibility (Ineligible A/R)', 'value': d_inelig, 'type': 'delta'},
                ]

                if atype != 'silq':
                    curr_adj = float(ck.get('adjusted_pool_balance') or 0)
                    prev_adj = float(pk.get('adjusted_pool_balance') or 0)
                    d_discount = (curr_adj - prev_adj) - _d(ck['eligible_ar'], pk['eligible_ar'])
                    if abs(d_discount) > 100:
                        steps.append({'label': 'Δ Concentration & Advance Rate', 'value': d_discount, 'type': 'delta'})
                    d_cash = _d(ck.get('cash_balance') or 0, pk.get('cash_balance') or 0)
                    if abs(d_cash) > 100:
                        steps.append({'label': 'Δ Cash Balance', 'value': d_cash, 'type': 'delta'})
                else:
                    d_rate = net_change - d_total - d_inelig
                    if abs(d_rate) > 100:
                        steps.append({'label': 'Δ Advance Rate Discount', 'value': d_rate, 'type': 'delta'})

                steps.append({'label': 'Current Borrowing Base', 'value': ck['borrowing_base'], 'type': 'end'})

                result['movement'] = {
                    'from_date': prev_ref,
                    'to_date': sel.get('date', ''),
                    'steps': steps,
                    'net_change': net_change,
                    'net_change_pct': net_change / float(pk['borrowing_base']) * 100 if pk['borrowing_base'] else 0,
                }
    except Exception:
        pass  # Movement data is optional — never break the main response

    # --- BB Analytics: breakeven + sensitivity ---
    try:
        ck = result['kpis']
        fp_advance = float(fp.get('advance_rate', 0.80 if atype == 'silq' else 0.90))
        available   = float(ck.get('available_to_draw') or 0)
        total_ar    = float(ck.get('total_ar')          or 0)
        eligible_ar = float(ck.get('eligible_ar')       or 0)
        facility_outstanding = float(fp.get('facility_drawn') or 0) * mult

        breakeven = None
        if fp_advance > 0 and total_ar > 0 and available > 0:
            # Eligible A/R must shrink by this much before BB ≤ outstanding
            eligible_reduction_needed = available / fp_advance
            stress_pct = eligible_reduction_needed / total_ar * 100
            breakeven = {
                'eligible_reduction_needed': eligible_reduction_needed,
                'stress_pct': round(stress_pct, 2),
                'headroom': available,
                'headroom_pct': round(available / float(ck.get('borrowing_base') or 1) * 100, 2),
                'facility_outstanding': facility_outstanding,
            }

        sensitivity = {
            'per_1pp_advance_rate': round(eligible_ar * 0.01, 0),   # ∂BB/∂rate per 1pp
            'per_1m_ineligible':    round(-fp_advance * 1_000_000 * mult, 0),  # ∂BB per 1M more ineligible
            'advance_rate_used':    fp_advance,
            'eligible_ar':          eligible_ar,
        }
        result['analytics'] = {'breakeven': breakeven, 'sensitivity': sensitivity}
    except Exception:
        pass

    return {**result, 'currency': disp, 'snapshot': sel['date'],
            'data_source': 'database', 'snapshot_source': sel.get('source', 'tape')}


@app.get("/companies/{company}/products/{product}/portfolio/concentration-limits")
def get_portfolio_concentration_limits(company: str, product: str,
                                        snapshot: Optional[str] = None,
                                        as_of_date: Optional[str] = None,
                                        currency: Optional[str] = None,
                                        db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    if atype == 'silq':
        result = portfolio_concentration_limits(df, mult, ref_date, fp)
    else:
        result = compute_klaim_concentration_limits(df, mult, ref_date, fp)
    return {**result, 'currency': disp, 'snapshot': sel['date'],
            'data_source': 'database', 'snapshot_source': sel.get('source', 'tape')}


@app.get("/companies/{company}/products/{product}/portfolio/covenants")
def get_portfolio_covenants(company: str, product: str,
                             snapshot: Optional[str] = None,
                             as_of_date: Optional[str] = None,
                             currency: Optional[str] = None,
                             db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    if atype == 'silq':
        result = portfolio_covenants(df, mult, ref_date, fp)
    else:
        result = compute_klaim_covenants(df, mult, ref_date, fp)

    # --- Consecutive breach tracking (EoD determination per MMA 18.3) ---
    try:
        history = _load_covenant_history(company, product)
        result = annotate_covenant_eod(result, history)
        _save_covenant_history(company, product, result)
    except Exception:
        pass  # History tracking is optional — never break the main response

    # --- Trend: load previous snapshot from DB to compute rate-of-change per covenant ---
    try:
        snaps = list_snapshots(db, company, product)  # DB-sourced, oldest-first by taken_at
        if len(snaps) >= 2:
            current_idx = next(
                (i for i, s in enumerate(snaps) if s['name'] == sel.get('name')), 0
            )
            prev_idx = current_idx - 1
            if prev_idx >= 0:
                prev_snap = snaps[prev_idx]
                prev_df = load_from_db(db, company, product, snapshot_id=prev_snap['id'])
                prev_ref = prev_snap['date']
                if atype == 'silq':
                    prev_result = portfolio_covenants(prev_df, mult, prev_ref, fp)
                else:
                    prev_result = compute_klaim_covenants(prev_df, mult, prev_ref, fp)
                prev_by_name = {c['name']: c for c in prev_result['covenants']}
                curr_dt = pd.to_datetime(ref_date)
                prev_dt = pd.to_datetime(prev_ref)
                days_between = max((curr_dt - prev_dt).days, 1)
                for cov in result['covenants']:
                    prev_cov = prev_by_name.get(cov['name'])
                    if prev_cov and isinstance(prev_cov.get('current'), (int, float)):
                        cov['previous_value'] = prev_cov['current']
                        cov['days_since_previous'] = days_between
    except Exception:
        pass  # Trend data is optional — never break the main response

    return {**result, 'currency': disp, 'snapshot': sel['date'],
            'data_source': 'database', 'snapshot_source': sel.get('source', 'tape')}


@app.get("/companies/{company}/products/{product}/portfolio/flow")
def get_portfolio_flow(company: str, product: str,
                        snapshot: Optional[str] = None,
                        as_of_date: Optional[str] = None,
                        currency: Optional[str] = None,
                        db: Session = Depends(get_db)):
    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)
    result = compute_portfolio_flow(df, mult)
    return {**result, 'currency': disp, 'snapshot': sel['date'],
            'data_source': 'database', 'snapshot_source': sel.get('source', 'tape')}


@app.get("/companies/{company}/products/{product}/portfolio/facility-params")
def get_facility_params(company: str, product: str):
    return _load_facility_params(company, product)


@app.post("/companies/{company}/products/{product}/portfolio/facility-params")
def save_facility_params(company: str, product: str, request: dict):
    """Save facility parameters (facility_limit, facility_drawn, cash_balance, etc.).
    NOTE: Currency is not stored here — monetary values are assumed to be in the
    product's reporting currency (from config.json). The frontend should send values
    in the reporting currency, not the display currency after FX conversion.
    """
    allowed_keys = {
        'facility_limit', 'facility_drawn', 'cash_balance',
        'equity_injection', 'advance_rate',
        'advance_rates_by_product', 'advance_rates_by_region',
        'approved_recipients',
        'single_payer_limit', 'wal_threshold_days',
        'net_cash_burn', 'net_cash_burn_3m_avg',
        'slack_webhook_url',
    }
    params = {k: v for k, v in request.items() if k in allowed_keys}
    params['updated_at'] = datetime.now().isoformat()

    path = _facility_params_path(company, product)
    with open(path, 'w') as f:
        json.dump(params, f, indent=2)

    log_activity(FACILITY_PARAMS_SAVED, company, product, f"Updated facility params: {', '.join(params.keys())}")
    return {'saved': True, 'params': params}


@app.post("/companies/{company}/products/{product}/portfolio/compliance-cert")
def generate_compliance_certificate(company: str, product: str,
                                     request: dict = None,
                                     snapshot: Optional[str] = None,
                                     as_of_date: Optional[str] = None,
                                     currency: Optional[str] = None,
                                     db: Session = Depends(get_db)):
    """Generate a Borrowing Base Certificate PDF and stream it to the client."""
    from core.compliance_cert import generate_compliance_cert
    from fastapi.responses import StreamingResponse
    import io

    request = request or {}
    officer_name = request.get('officer_name', '')
    cur_override = request.get('currency') or currency

    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, cur_override, db=db)

    # Compute all three data sources
    if atype == 'silq':
        bb_data   = portfolio_borrowing_base(df, mult, ref_date, fp)
        conc_data = portfolio_concentration_limits(df, mult, ref_date, fp)
        cov_data  = portfolio_covenants(df, mult, ref_date, fp)
    else:
        bb_data   = compute_klaim_borrowing_base(df, mult, ref_date, fp)
        conc_data = compute_klaim_concentration_limits(df, mult, ref_date, fp)
        cov_data  = compute_klaim_covenants(df, mult, ref_date, fp)

    bb_data['snapshot']  = sel['date']
    bb_data['currency']  = disp
    conc_data['currency'] = disp
    cov_data['currency']  = disp

    pdf_bytes = generate_compliance_cert(
        bb_data, conc_data, cov_data,
        company=company, product=product,
        currency=disp, officer_name=officer_name,
    )

    filename = f"BBC_{company}_{product}_{sel['date']}.pdf"
    log_activity(COMPLIANCE_CERT, company, product, f"Generated compliance cert: {filename}")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@app.post("/companies/{company}/products/{product}/portfolio/notify-breaches")
def notify_breaches(company: str, product: str,
                    snapshot: Optional[str] = None,
                    as_of_date: Optional[str] = None,
                    currency: Optional[str] = None,
                    db: Session = Depends(get_db)):
    """Send a Slack notification summarising any covenant or concentration breaches."""
    import urllib.request as ureq
    import json as _json

    df, sel, config, disp, mult, ref_date, fp, atype = _portfolio_load(
        company, product, snapshot, as_of_date, currency, db=db)

    webhook_url = fp.get('slack_webhook_url', '').strip()
    if not webhook_url:
        raise HTTPException(status_code=400, detail='No Slack webhook URL configured. Add one in Facility Parameters.')

    if atype == 'silq':
        cov_data  = portfolio_covenants(df, mult, ref_date, fp)
        conc_data = portfolio_concentration_limits(df, mult, ref_date, fp)
    else:
        cov_data  = compute_klaim_covenants(df, mult, ref_date, fp)
        conc_data = compute_klaim_concentration_limits(df, mult, ref_date, fp)

    covenants = cov_data.get('covenants', [])
    limits    = conc_data.get('limits', [])

    breach_covs  = [c for c in covenants if not c.get('compliant', True)]
    breach_concs = [l for l in limits    if not l.get('compliant', True)]
    total_breach = len(breach_covs) + len(breach_concs)

    if total_breach == 0:
        emoji = ':white_check_mark:'
        header = f'{emoji} *{company.upper()} / {product}* — All covenants and limits compliant as of {sel["date"]}.'
        fields = []
    else:
        emoji = ':rotating_light:'
        header = (
            f'{emoji} *BREACH ALERT — {company.upper()} / {product}*\n'
            f'{total_breach} breach(es) detected as of {sel["date"]}.'
        )
        fields = []
        for c in breach_covs:
            fields.append({
                'type': 'mrkdwn',
                'text': f'*Covenant: {c["name"]}*\nActual: {c.get("current", "?")} | Threshold: {c.get("threshold", "?")}',
            })
        for l in breach_concs:
            fields.append({
                'type': 'mrkdwn',
                'text': f'*Concentration: {l.get("name", "?")}*\nExposure: {l.get("current_value", "?")} | Limit: {l.get("limit_pct", "?")}%',
            })

    payload = {
        'blocks': [
            {'type': 'section', 'text': {'type': 'mrkdwn', 'text': header}},
        ]
    }
    if fields:
        payload['blocks'].append({'type': 'section', 'fields': fields[:10]})
    payload['blocks'].append({
        'type': 'context',
        'elements': [{'type': 'mrkdwn', 'text': f'Sent by Laith Analytics Platform | {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}'}],
    })

    body = _json.dumps(payload).encode('utf-8')
    req  = ureq.Request(webhook_url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with ureq.urlopen(req, timeout=10) as resp:
            status = resp.status
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'Slack delivery failed: {e}')

    if status != 200:
        raise HTTPException(status_code=502, detail=f'Slack returned HTTP {status}')

    log_activity(BREACH_NOTIFICATION, company, product, f"Sent Slack alert: {total_breach} breach(es)")
    return {
        'sent': True,
        'breach_count': total_breach,
        'covenant_breaches': len(breach_covs),
        'concentration_breaches': len(breach_concs),
        'snapshot': sel['date'],
    }

# ── Portfolio Dashboard Data endpoints ───────────────────────────────────────

@app.get("/companies/{company}/products/{product}/portfolio/invoices")
def get_portfolio_invoices(company: str, product: str,
                           page: int = 1, per_page: int = 50,
                           status: Optional[str] = None,
                           eligible: Optional[str] = None,
                           db: Session = Depends(get_db)):
    """List invoices for dashboard view with eligibility info."""
    from core.models import Invoice, Payment, Product, Organization
    from sqlalchemy import func as sqfunc

    if db is None:
        return {'invoices': [], 'total': 0, 'page': page, 'per_page': per_page}

    # Find product
    prod = (db.query(Product).join(Organization)
            .filter(Organization.name == company, Product.name == product).first())
    if not prod:
        return {'invoices': [], 'total': 0, 'page': page, 'per_page': per_page}

    q = db.query(Invoice).filter(Invoice.product_id == prod.id)
    if status:
        q = q.filter(Invoice.status == status.lower())

    total = q.count()
    rows = q.order_by(Invoice.invoice_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    invoices = []
    today = datetime.now().date()
    for inv in rows:
        # Compute collected amount
        collected = db.query(sqfunc.coalesce(sqfunc.sum(Payment.payment_amount), 0)).filter(
            Payment.invoice_id == inv.id).scalar()

        # Simple eligibility: not past due >90 days, status not denied
        days_overdue = (today - inv.due_date).days if inv.due_date and inv.due_date < today else 0
        is_eligible = inv.status not in ('paid', 'denied') and days_overdue <= 90
        ineligible_reason = None
        if not is_eligible:
            if inv.status in ('paid', 'denied'):
                ineligible_reason = f'Status: {inv.status}'
            elif days_overdue > 90:
                ineligible_reason = f'Past due: {days_overdue} days'

        invoices.append({
            'id': str(inv.id),
            'invoice_number': inv.invoice_number,
            'customer_name': inv.customer_name,
            'payer_name': inv.payer_name,
            'amount_due': float(inv.amount_due),
            'collected': float(collected),
            'currency': inv.currency,
            'status': inv.status,
            'invoice_date': str(inv.invoice_date) if inv.invoice_date else None,
            'due_date': str(inv.due_date) if inv.due_date else None,
            'days_overdue': days_overdue,
            'eligible': is_eligible,
            'ineligible_reason': ineligible_reason,
        })

    # Filter by eligibility if requested
    if eligible == 'true':
        invoices = [i for i in invoices if i['eligible']]
        total = len(invoices)
    elif eligible == 'false':
        invoices = [i for i in invoices if not i['eligible']]
        total = len(invoices)

    return {'invoices': invoices, 'total': total, 'page': page, 'per_page': per_page}


@app.get("/companies/{company}/products/{product}/portfolio/payments")
def get_portfolio_payments(company: str, product: str,
                           page: int = 1, per_page: int = 50,
                           payment_type: Optional[str] = None,
                           db: Session = Depends(get_db)):
    """List payments for dashboard view."""
    from core.models import Invoice, Payment, Product, Organization

    if db is None:
        return {'payments': [], 'total': 0, 'page': page, 'per_page': per_page}

    prod = (db.query(Product).join(Organization)
            .filter(Organization.name == company, Product.name == product).first())
    if not prod:
        return {'payments': [], 'total': 0, 'page': page, 'per_page': per_page}

    q = (db.query(Payment, Invoice.invoice_number)
         .join(Invoice, Payment.invoice_id == Invoice.id)
         .filter(Invoice.product_id == prod.id))
    if payment_type:
        q = q.filter(Payment.payment_type == payment_type.upper())

    total = q.count()
    rows = q.order_by(Payment.payment_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    payments = []
    for pay, inv_number in rows:
        payments.append({
            'id': str(pay.id),
            'invoice_id': str(pay.invoice_id),
            'invoice_number': inv_number,
            'payment_type': pay.payment_type,
            'payment_amount': float(pay.payment_amount),
            'currency': pay.currency,
            'payment_date': str(pay.payment_date) if pay.payment_date else None,
            'transaction_id': pay.transaction_id,
        })

    return {'payments': payments, 'total': total, 'page': page, 'per_page': per_page}


@app.get("/companies/{company}/products/{product}/portfolio/bank-statements")
def get_portfolio_bank_statements(company: str, product: str,
                                   page: int = 1, per_page: int = 50,
                                   db: Session = Depends(get_db)):
    """List bank statements for dashboard view."""
    from core.models import BankStatement, Organization

    if db is None:
        return {'statements': [], 'total': 0, 'page': page, 'per_page': per_page,
                'summary': {'cash_balance': 0, 'collection_balance': 0, 'last_upload': None}}

    org = db.query(Organization).filter_by(name=company).first()
    if not org:
        return {'statements': [], 'total': 0, 'page': page, 'per_page': per_page,
                'summary': {'cash_balance': 0, 'collection_balance': 0, 'last_upload': None}}

    q = db.query(BankStatement).filter(BankStatement.org_id == org.id)
    total = q.count()
    rows = q.order_by(BankStatement.statement_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Compute summary from latest statements per account type
    from sqlalchemy import func as sqfunc
    cash = (db.query(sqfunc.coalesce(BankStatement.balance, 0))
            .filter(BankStatement.org_id == org.id, BankStatement.account_type == 'cash-account')
            .order_by(BankStatement.statement_date.desc()).first())
    collection = (db.query(sqfunc.coalesce(BankStatement.balance, 0))
                  .filter(BankStatement.org_id == org.id, BankStatement.account_type == 'collection')
                  .order_by(BankStatement.statement_date.desc()).first())
    last = (db.query(sqfunc.max(BankStatement.statement_date))
            .filter(BankStatement.org_id == org.id).scalar())

    statements = [{
        'id': str(bs.id),
        'balance': float(bs.balance),
        'currency': bs.currency,
        'account_type': bs.account_type,
        'statement_date': str(bs.statement_date),
        'created_at': str(bs.created_at) if bs.created_at else None,
    } for bs in rows]

    return {
        'statements': statements,
        'total': total,
        'page': page,
        'per_page': per_page,
        'summary': {
            'cash_balance': float(cash[0]) if cash else 0,
            'collection_balance': float(collection[0]) if collection else 0,
            'last_upload': str(last) if last else None,
        },
    }


@app.get("/companies/{company}/products/{product}/portfolio/covenant-dates")
def get_portfolio_covenant_dates(company: str, product: str,
                                  db: Session = Depends(get_db)):
    """Return available covenant test dates (snapshot dates)."""
    snaps = list_snapshots(db, company, product) if db else []
    if not snaps:
        # Fallback for non-tape analysis types that don't live in DB
        snaps = get_snapshots(company, product)
    dates = sorted({s['date'] for s in snaps if s.get('date')}, reverse=True)
    return {'dates': dates}


# ── PDF Report Generation ─────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.post("/companies/{company}/products/{product}/generate-report")
def generate_pdf_report(company: str, product: str, request: dict = {}):
    """Generate a full dashboard PDF report and stream it back to the browser."""
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"Laith_{company.upper()}_Report_{timestamp}.pdf"

    script_path = os.path.join(PROJECT_ROOT, 'generate_report.py')
    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail="Report generator script not found")

    # Generate into a temp file — FastAPI will clean up after response is sent
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    cmd = [
        sys.executable, script_path,
        '--company', company,
        '--product', product,
        '--output', tmp.name,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=180, cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            os.unlink(tmp.name)
            detail = result.stderr[:2000] if result.stderr else "Report generation failed"
            raise HTTPException(status_code=500, detail=detail)
        if not os.path.exists(tmp.name) or os.path.getsize(tmp.name) == 0:
            os.unlink(tmp.name)
            raise HTTPException(status_code=500, detail="Report file was not created")
    except subprocess.TimeoutExpired:
        os.unlink(tmp.name)
        raise HTTPException(status_code=504, detail="Report generation timed out (>3 min)")

    log_activity(REPORT_GENERATED, company, product, f"Generated PDF report: {filename}")
    from starlette.background import BackgroundTask
    return FileResponse(
        tmp.name,
        media_type='application/pdf',
        filename=filename,
        background=BackgroundTask(os.unlink, tmp.name),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Research Hub — Data Room, Research Intelligence, Living Mind
# ══════════════════════════════════════════════════════════════════════════════

_dataroom_engine = DataRoomEngine()
_analytics_snapshot = AnalyticsSnapshotEngine()
_research_engine = DualResearchEngine()
_memo_generator = MemoGenerator()
_memo_storage = MemoStorage()


# ── Data Room endpoints ──────────────────────────────────────────────────────

@app.post("/companies/{company}/products/{product}/dataroom/snapshot-analytics")
def dataroom_snapshot_analytics(company: str, product: str,
                                 snapshot: Optional[str] = None,
                                 currency: Optional[str] = None):
    """Snapshot current analytics (tape summary, PAR, DSO, etc.) into the data room.

    This makes platform-computed analytics searchable alongside data room documents.
    Call once per snapshot to capture the analytical state.
    """
    at = _get_analysis_type(company, product)

    if at in ('ejari_summary', 'tamara_summary', 'aajil'):
        # For read-only summaries, snapshot the parsed data
        try:
            snaps = get_snapshots(company, product)
            if not snaps:
                return {'snapshotted': 0, 'message': 'No snapshots found'}
            snap_filename = snaps[-1]['filename']

            if at == 'tamara_summary':
                filepath = snaps[-1]['filepath']
                if filepath not in _tamara_cache:
                    _tamara_cache[filepath] = parse_tamara_data(filepath)
                data = _tamara_cache[filepath]
                docs = _analytics_snapshot.snapshot_ai_output(
                    company, product, 'parsed_summary', data, snap_filename)
                return {'snapshotted': 1 if docs else 0, 'snapshot': snap_filename}
            else:
                return {'snapshotted': 0, 'message': 'Ejari snapshot not yet supported'}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # For tape-based companies (Klaim, SILQ): snapshot key analytics
    try:
        if at == 'silq':
            df, sel, config, disp, mult, _, ref_date = _silq_load(company, product, snapshot, None, currency)
            summary = compute_silq_summary(df, mult, ref_date=ref_date)
            docs = _analytics_snapshot.snapshot_tape_analytics(
                company, product, sel['filename'], summary=summary)
        else:
            df, sel = _load(company, product, snapshot)
            config, disp = _currency(company, product, currency)
            mult = apply_multiplier(config, disp)
            summary = compute_summary(df, config, disp, sel['date'], None)

            # Compute additional key analytics for the snapshot
            par_data = None
            dso_data = None
            try:
                par_data = compute_par(df, mult, None)
            except Exception:
                pass
            try:
                dso_data = compute_dso(df, mult, None)
            except Exception:
                pass

            docs = _analytics_snapshot.snapshot_tape_analytics(
                company, product, sel['filename'],
                summary=summary, par=par_data, dso=dso_data)

        return {'snapshotted': len(docs), 'snapshot': sel['filename']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/companies/{company}/products/{product}/dataroom/analytics-timeline")
def dataroom_analytics_timeline(company: str, product: str,
                                  doc_type: Optional[str] = None):
    """Get all analytics snapshots over time for trend analysis."""
    return _analytics_snapshot.get_analytics_timeline(company, product, doc_type)


@app.get("/companies/{company}/products/{product}/dataroom/documents")
def dataroom_documents(company: str, product: str):
    """List all ingested documents from the data room registry."""
    return _dataroom_engine.catalog(company, product)


@app.get("/companies/{company}/products/{product}/dataroom/stats")
def dataroom_stats(company: str, product: str):
    """Aggregate data room stats: total docs, chunks, pages, by type."""
    return _dataroom_engine.get_stats(company, product)


@app.get("/companies/{company}/products/{product}/dataroom/documents/{doc_id}")
def dataroom_document_detail(company: str, product: str, doc_id: str):
    """Get a single document with its chunks and metadata."""
    result = _dataroom_engine.get_document(company, product, doc_id)
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@app.get("/companies/{company}/products/{product}/dataroom/documents/{doc_id}/view")
def dataroom_document_view(company: str, product: str, doc_id: str):
    """Stream the original file for viewing in browser."""
    import mimetypes
    result = _dataroom_engine.get_document(company, product, doc_id)
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    filepath = result.get('filepath', '')
    if not filepath:
        raise HTTPException(status_code=404, detail="Source file not found on disk")
    # Normalize path separators (registry may have Windows backslashes on Linux)
    filepath = filepath.replace('\\', os.sep).replace('/', os.sep)
    # If relative path, resolve against project root
    if not os.path.isabs(filepath):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', filepath)
    filepath = os.path.normpath(filepath)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Source file not found on disk")
    content_type = mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
    return FileResponse(filepath, media_type=content_type, filename=os.path.basename(filepath))


@app.post("/companies/{company}/products/{product}/dataroom/ingest")
def dataroom_ingest(company: str, product: str, source_dir: Optional[str] = None):
    """Scan and ingest a data room directory.

    If source_dir not provided, uses a default path pattern based on company.
    """
    if not source_dir:
        # Default: company-level dataroom folder inside the platform data directory
        source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', company, 'dataroom')
        if not os.path.exists(source_dir):
            raise HTTPException(status_code=400,
                              detail=f"No data room directory found at data/{company}/dataroom/. "
                                     f"Create the folder and add documents, or provide source_dir parameter.")

    result = _dataroom_engine.ingest(company, product, source_dir)
    log_activity(DATAROOM_INGEST, company, product, f"Ingested data room: {result.get('documents_ingested', '?')} documents")

    return result


@app.post("/companies/{company}/products/{product}/dataroom/upload")
def dataroom_upload_file(company: str, product: str, filepath: str):
    """Ingest a single file into the data room."""
    if not os.path.exists(filepath):
        raise HTTPException(status_code=400, detail=f"File not found: {filepath}")
    result = _dataroom_engine.ingest_file(company, product, filepath)
    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@app.post("/companies/{company}/products/{product}/dataroom/refresh")
def dataroom_refresh(company: str, product: str, source_dir: Optional[str] = None):
    """Incremental re-scan of the data room directory."""
    if not source_dir:
        source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', company, 'dataroom')
        if not os.path.exists(source_dir):
            raise HTTPException(status_code=400,
                              detail=f"No data room directory found at data/{company}/dataroom/. "
                                     f"Create the folder and add documents, or provide source_dir parameter.")
    result = _dataroom_engine.refresh(company, product, source_dir)
    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])
    return result


@app.get("/companies/{company}/products/{product}/dataroom/search")
def dataroom_search(company: str, product: str, q: str, top_k: int = 10):
    """Search across all ingested documents."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    return _dataroom_engine.search(company, product, q.strip(), top_k=min(top_k, 50))


@app.get("/companies/{company}/products/{product}/dataroom/health")
def dataroom_health_one(company: str, product: str):
    """Per-company dataroom health audit (Tier 2.2).

    Surfaces orphan registry entries, missing chunks, index status, last
    ingest timestamp and unclassified docs. Drives the OperatorCenter
    Data Rooms card and `dataroom_ctl audit`.
    """
    return _dataroom_engine.audit(company, product)


@app.get("/dataroom/health")
def dataroom_health_all():
    """Global dataroom health across every onboarded company.

    Iterates all companies with a dataroom/ folder and audits the first
    available product (dataroom is company-level; product is just the
    event-bus key). Returns a list so the OperatorCenter can render a
    health matrix in one fetch.
    """
    reports = []
    for co in get_companies():
        # Only audit companies that actually have a dataroom folder on disk.
        co_dr = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'data', co, 'dataroom'
        )
        if not os.path.isdir(co_dr):
            continue
        prods = get_products(co)
        prod = prods[0] if prods else ""
        try:
            reports.append(_dataroom_engine.audit(co, prod))
        except Exception as e:
            reports.append({
                "company": co,
                "product": prod,
                "error": str(e),
            })
    return {"datarooms": reports}


# ── Research Intelligence endpoints ──────────────────────────────────────────

@app.post("/companies/{company}/products/{product}/research/query")
def research_query(company: str, product: str, question: str,
                   include_analytics: bool = True, top_k: int = 10):
    """Ask a question across all ingested documents using Claude RAG.

    Uses Claude RAG with internal document chunks, analytics snapshots,
    and mind context for research synthesis.
    """
    result = _research_engine.query(
        company=company,
        product=product,
        question=question,
        include_analytics=include_analytics,
    )
    log_activity(RESEARCH_QUERY, company, product, f"Research: {question[:80]}")
    return result


@app.post("/companies/{company}/products/{product}/research/chat")
def research_chat(company: str, product: str, body: dict = {}):
    """Research chat endpoint — matches frontend postResearchChat() signature.
    Body: {question: str, history: list}
    """
    question = body.get('question', '')
    if not question or len(question.strip()) < 2:
        raise HTTPException(status_code=400, detail="Question required")
    # Delegate to the query endpoint logic
    return research_query(company, product, question.strip())


# ── Living Mind endpoints ────────────────────────────────────────────────────

@app.get("/companies/{company}/products/{product}/mind/profile")
def mind_profile(company: str, product: str):
    """Get the company mind profile — synthesized knowledge about this company."""
    cm = CompanyMind(company, product)
    return cm.get_company_profile()


@app.get("/companies/{company}/products/{product}/mind/context")
def mind_context_preview(company: str, product: str,
                          task_type: str = "executive_summary"):
    """Preview what the 6-layer mind context looks like for a given task type."""
    ctx = build_mind_context(company, product, task_type)
    return {
        'framework_length': len(ctx.framework),
        'master_mind_length': len(ctx.master_mind),
        'asset_class_length': len(ctx.asset_class),
        'methodology_length': len(ctx.methodology),
        'company_mind_length': len(ctx.company_mind),
        'thesis_length': len(ctx.thesis),
        'total_entries': ctx.total_entries,
        'is_empty': ctx.is_empty,
        'formatted_preview': ctx.formatted[:2000] if ctx.formatted else '',
    }


@app.post("/companies/{company}/products/{product}/mind/record")
def mind_record(company: str, product: str,
                category: str, content: str,
                metadata: Optional[str] = None):
    """Record an entry in the company mind.

    category: correction, finding, ic_feedback, data_quality, session_lesson
    """
    cm = CompanyMind(company, product)
    meta = json.loads(metadata) if metadata else {}

    if category == 'correction':
        entry = cm.record_correction(
            meta.get('correction_category', 'general'),
            meta.get('original', ''),
            meta.get('corrected', content),
            meta.get('reason', ''),
        )
    elif category == 'finding':
        entry = cm.record_research_finding(
            content,
            confidence=meta.get('confidence', 'medium'),
            source_docs=meta.get('source_docs', []),
        )
    elif category == 'ic_feedback':
        entry = cm.record_ic_feedback(content, memo_id=meta.get('memo_id'))
    elif category == 'data_quality':
        entry = cm.record_data_quality_note(content, meta.get('tape_or_doc', ''))
    elif category == 'session_lesson':
        entry = cm.record_session_lesson(content, meta.get('lesson_category', 'general'))
    else:
        raise HTTPException(status_code=400,
                          detail=f"Unknown category: {category}. "
                                 f"Valid: correction, finding, ic_feedback, data_quality, session_lesson")

    log_activity(MIND_ENTRY_RECORDED, company, product, f"Recorded {category}: {content[:60]}")
    return {'recorded': True, 'entry_id': entry.id, 'category': entry.category}


@app.get("/mind/master/context")
def master_mind_context(task_type: str = "executive_summary"):
    """Preview the master mind (fund-level) context."""
    master = MasterMind()
    ctx = master.get_context_for_prompt(task_type)
    return {
        'entry_count': ctx.entry_count,
        'categories': ctx.categories_included,
        'formatted_preview': ctx.formatted[:2000] if ctx.formatted else '',
    }


@app.post("/mind/master/record")
def master_mind_record(category: str, content: str,
                        source: Optional[str] = None,
                        metadata: Optional[str] = None):
    """Record an entry in the master mind (fund-level).

    category: preference, cross_company, framework_evolution, ic_norm, writing_style
    """
    master = MasterMind()
    meta = json.loads(metadata) if metadata else {}

    if category == 'preference':
        entry = master.record_analytical_preference(content, source or 'manual')
    elif category == 'cross_company':
        entry = master.record_cross_company_pattern(
            content,
            companies=meta.get('companies', []),
            evidence=meta.get('evidence', ''),
        )
    elif category == 'framework_evolution':
        entry = master.record_framework_evolution(content, meta.get('reason', ''), meta.get('date', ''))
    elif category == 'ic_norm':
        entry = master.record_ic_norm(content, meta.get('norm_category', 'general'))
    elif category == 'writing_style':
        entry = master.record_writing_style(content, source or 'manual')
    else:
        raise HTTPException(status_code=400,
                          detail=f"Unknown category: {category}. "
                                 f"Valid: preference, cross_company, framework_evolution, ic_norm, writing_style")

    return {'recorded': True, 'entry_id': entry.id, 'category': entry.category}


# ── Memo Engine endpoints ────────────────────────────────────────────────────

@app.get("/memo-templates")
def get_memo_templates():
    """List all available IC memo templates with full section definitions.

    Returns full shape expected by frontend: each template includes its
    ordered sections array ({key, title, required, source}). The frontend
    relies on these keys to drive section toggles and must match the
    backend's authoritative section keys to avoid silent drops during
    generation.
    """
    result = []
    for key, tmpl in MEMO_TEMPLATES.items():
        sections = [
            {
                "key": s["key"],
                "title": s["title"],
                "required": s.get("required", False),
                "source": s.get("source", "mixed"),
            }
            for s in tmpl["sections"]
        ]
        result.append({
            "key": key,
            "name": tmpl["name"],
            "description": tmpl["description"],
            "section_count": len(sections),
            "required_sections": sum(1 for s in sections if s["required"]),
            "sections": sections,
        })
    return result


@app.get("/companies/{company}/products/{product}/memos")
def list_company_memos(company: str, product: str, status: Optional[str] = None):
    """List all memos for a company/product."""
    return _memo_storage.list_memos(company=company, product=product, status=status)


@app.post("/companies/{company}/products/{product}/memos/generate")
def generate_memo(company: str, product: str, body: dict = {}):
    """Generate a full IC memo using AI.

    Body: {template: str, custom_sections: list[str] | null, title: str | null}
    """
    template_key = body.get('template', 'credit_memo')
    custom_sections = body.get('custom_sections')
    title = body.get('title')

    tmpl = get_template(template_key)
    if not tmpl:
        raise HTTPException(status_code=400, detail=f"Unknown template: {template_key}")

    try:
        memo = _memo_generator.generate_full_memo(
            company=company,
            product=product,
            template_key=template_key,
            custom_sections=custom_sections,
        )

        if title:
            memo['title'] = title

        # Capture transient research packs before save strips them
        research_packs_copy = dict(memo.get('_research_packs') or {})

        # Save to storage
        memo_id = _memo_storage.save(memo)
        memo['id'] = memo_id

        # Best-effort: record memo thesis to Company Mind so future memos
        # see the prior stance and can flag drift.
        try:
            from core.memo.agent_research import record_memo_thesis_to_mind
            record_memo_thesis_to_mind(memo, research_packs=research_packs_copy)
        except Exception as e:
            logger.warning("Thesis recording failed: %s", e)

        log_activity(MEMO_GENERATED, company, product, f"Generated {template_key} memo: {memo_id}")
        return memo

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memo generation failed: {str(e)[:500]}")


@app.get("/companies/{company}/products/{product}/memos/{memo_id}")
def get_memo_endpoint(company: str, product: str, memo_id: str,
             version: Optional[int] = None):
    """Get a memo (latest version by default)."""
    memo = _memo_storage.load(company, product, memo_id, version=version)
    if not memo or memo.get('error'):
        raise HTTPException(status_code=404, detail=memo.get('error', 'Memo not found'))
    return memo


@app.get("/companies/{company}/products/{product}/memos/{memo_id}/versions")
def list_memo_versions(company: str, product: str, memo_id: str):
    """List all versions of a memo."""
    memo = _memo_storage.load(company, product, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail='Memo not found')
    return {'memo_id': memo_id, 'current_version': memo.get('version', 1),
            'versions': list(range(1, memo.get('version', 1) + 1))}


@app.patch("/companies/{company}/products/{product}/memos/{memo_id}/sections/{section_key}")
def update_memo_section_endpoint(company: str, product: str, memo_id: str,
                         section_key: str, body: dict = {}):
    """Update a single section (creates new version)."""
    content = body.get('content', '')
    if not content:
        raise HTTPException(status_code=400, detail="Content required")

    # Capture old content before update (needed for learning engine)
    old_content = ''
    try:
        old_memo = _memo_storage.load(company, product, memo_id)
        if old_memo:
            for s in old_memo.get('sections', []):
                if s.get('key') == section_key:
                    old_content = s.get('content', '')
                    break
    except Exception:
        pass

    result = _memo_storage.update_section(company, product, memo_id, section_key, content)
    if not result or result.get('error'):
        raise HTTPException(status_code=404, detail=result.get('error', 'Update failed'))

    # Record the edit in the company mind for learning
    try:
        cm = CompanyMind(company, product)
        cm.record_memo_edit(memo_id, section_key, old_content, content)
    except Exception:
        pass

    # Fire MEMO_EDITED event for Intelligence System
    try:
        from core.mind.event_bus import event_bus, Events
        event_bus.publish(Events.MEMO_EDITED, {
            "company": company, "product": product,
            "section_key": section_key,
            "ai_version": old_content,
            "analyst_version": content,
            "memo_id": memo_id,
        })
    except Exception:
        pass

    return result


@app.post("/companies/{company}/products/{product}/memos/{memo_id}/sections/{section_key}/regenerate")
def regenerate_memo_section_endpoint(company: str, product: str, memo_id: str,
                             section_key: str, mode: Optional[str] = None):
    """Regenerate one section using AI while preserving the rest."""
    memo = _memo_storage.load(company, product, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail='Memo not found')

    # Agent mode — use memo_writer agent for richer output
    if mode == "agent":
        try:
            from core.agents.internal import generate_agent_section_regen
            content = generate_agent_section_regen(company, product, memo_id, section_key)
            if content:
                _memo_storage.update_section(company, product, memo_id, section_key, content)
                return {"section_key": section_key, "content": content}
        except Exception:
            pass  # Fall through to legacy

    try:
        new_section = _memo_generator.regenerate_section(memo, section_key)
        if not new_section:
            raise HTTPException(status_code=500, detail="Section regeneration returned empty")

        _memo_storage.update_section(company, product, memo_id, section_key, new_section.get('content', ''))
        return new_section

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)[:500]}")


@app.patch("/companies/{company}/products/{product}/memos/{memo_id}/status")
def update_memo_status_endpoint(company: str, product: str, memo_id: str, body: dict = {}):
    """Change memo status (draft->review->final->archived)."""
    new_status = body.get('status', '')
    valid = ('draft', 'review', 'final', 'archived')
    if new_status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {valid}")

    result = _memo_storage.update_status(memo_id, new_status)
    if not result or result.get('error'):
        raise HTTPException(status_code=404, detail=result.get('error', 'Status update failed'))
    return result


@app.post("/companies/{company}/products/{product}/memos/{memo_id}/export-pdf")
def export_memo_to_pdf(company: str, product: str, memo_id: str):
    """Export a memo as a dark-themed PDF."""
    memo = _memo_storage.load(company, product, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail='Memo not found')

    try:
        pdf_bytes = export_memo_pdf(memo, company, product)
        from fastapi.responses import Response
        filename = f"{company}_{product}_{memo.get('template', 'memo')}_{memo_id[:8]}.pdf"
        log_activity(MEMO_EXPORTED, company, product, f"Exported memo PDF: {filename}")
        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={'Content-Disposition': f'inline; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)[:500]}")
