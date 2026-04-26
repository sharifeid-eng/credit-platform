"""
Recurring Channel Pattern Detection — surfaces dataroom files arriving on a
recurring cadence (same `document_type` accumulating over time) and the
automation status of each channel (parser + post-ingest hook).

Architecture
------------
Per-company patterns are PRIMARY storage; they go to **Company Mind** under
the `recurring_channels` category via `write_patterns_to_company_mind()`.

Cross-company emergent patterns (≥2 companies in the same `asset_class` with
the same `document_type` cluster) are SURFACED as candidates only — they do
NOT auto-write to Asset Class Mind. The analyst promotes via the existing
`core/mind/promotion.py` infrastructure (Operator Center button).

Master Mind gets ONE rolling stats file (`recurring_channel_stats.json`)
periodically refreshed by `write_fund_wide_stats()` for fund-level visibility
of "X automated, Y candidates, Z early" — never per-pattern entries.

Status taxonomy
---------------
- AUTOMATED: ≥3 files AND post-ingest hook exists AND parser script exists
- PARTIAL:   ≥3 files AND (hook OR parser exists, not both)
- CANDIDATE: ≥3 files AND neither hook nor parser exists
- EARLY:     1-2 files (watch — not yet enough to invest in automation)

Cadence detection
-----------------
Cadence is computed as the mean of pairwise day-deltas between sorted
`ingested_at` timestamps in the registry. Bucketed:
- monthly:   25-35 days mean delta
- quarterly: 80-100 days mean delta
- annual:    350-380 days mean delta
- irregular: any other non-empty mean
- unknown:   <2 timestamps

Note: when an entire dataroom is ingested in one batch (e.g. fresh-install
re-ingest), `ingested_at` clusters tightly and cadence_label will be
"irregular". The file_count threshold is the primary actionability signal,
cadence is supplementary.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"
_DEFAULT_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"

# Threshold constants
_CANDIDATE_MIN_FILES = 3   # ≥ this count = needs evaluation (not EARLY)

# (label, low_inclusive, high_inclusive) in days
_CADENCE_BUCKETS: List[Tuple[str, int, int]] = [
    ("monthly", 25, 35),
    ("quarterly", 80, 100),
    ("annual", 350, 380),
]

# Status sort key (lower = more actionable, surfaced first in UI)
_STATUS_ORDER: Dict[str, int] = {
    "CANDIDATE": 0,
    "PARTIAL": 1,
    "EARLY": 2,
    "AUTOMATED": 3,
}

# Document types we never count toward patterns — unclassified files would
# otherwise inflate `OTHER` clusters that aren't actionable.
_SKIP_DOC_TYPES = {"other", "unknown"}


# ── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass
class RecurringPattern:
    """One detected (company, document_type) cluster."""

    pattern_id: str          # f"{company}::{document_type}" — stable identity
    company: str
    document_type: str
    asset_class: str
    file_count: int
    file_dates: List[str]    # sorted ingested_at timestamps
    cadence_days: Optional[int]
    cadence_label: str       # monthly | quarterly | annual | irregular | unknown
    hook_exists: bool
    parser_exists: bool
    automation_status: str   # AUTOMATED | PARTIAL | CANDIDATE | EARLY
    recommendation: str
    detected_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmergentPattern:
    """Cross-company (asset_class, document_type) combo where ≥2 companies
    show similarity. Surfaced as a CANDIDATE for Asset Class Mind promotion;
    never auto-written.
    """

    asset_class: str
    document_type: str
    companies: List[str]
    company_file_counts: Dict[str, int]
    detected_at: str
    suggested_text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Internal helpers ────────────────────────────────────────────────────────


def _classify_cadence(deltas_days: List[float]) -> Tuple[Optional[int], str]:
    """Map mean(deltas_days) to a cadence label.

    Returns (cadence_days, label). cadence_days is None when fewer than two
    timestamps were available (no deltas to average).
    """
    if not deltas_days:
        return None, "unknown"
    avg = int(round(mean(deltas_days)))
    for label, low, high in _CADENCE_BUCKETS:
        if low <= avg <= high:
            return avg, label
    return avg, "irregular"


def _file_dates_from_entries(entries: List[Dict[str, Any]]) -> List[str]:
    """Extract sorted ingested_at timestamps from registry entries."""
    dates: List[str] = []
    for e in entries:
        ts = e.get("ingested_at")
        if isinstance(ts, str) and ts:
            dates.append(ts)
    dates.sort()
    return dates


def _deltas_days(timestamps: List[str]) -> List[float]:
    """Day-deltas between consecutive parsed timestamps."""
    parsed: List[datetime] = []
    for ts in timestamps:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed.append(dt)
        except (ValueError, AttributeError):
            continue
    parsed.sort()
    if len(parsed) < 2:
        return []
    return [
        (parsed[i] - parsed[i - 1]).total_seconds() / 86400.0
        for i in range(1, len(parsed))
    ]


def _hook_exists(company: str, data_dir: Path) -> bool:
    """Company-level `.post-ingest.sh` presence."""
    return (data_dir / company / "dataroom" / ".post-ingest.sh").is_file()


def _parser_exists(company: str, document_type: str, scripts_dir: Path) -> bool:
    """Heuristic: a company-specific parser script exists for this doc_type.

    Pattern: `scripts/ingest_{company.lower()}_*.py`. A parser counts as a
    match when the filename stem contains:
      - 1 of the doc_type's words for single-word types
      - 2 of the doc_type's words for 2+-word types

    Two-word minimum prevents `ingest_tamara_investor_pack.py` from
    accidentally matching `investor_report` (only one word overlap).
    """
    if not scripts_dir.is_dir():
        return False
    co_lower = company.lower()
    doc_words = [w for w in document_type.lower().split("_") if w]
    if not doc_words:
        return False
    needed_overlap = 2 if len(doc_words) >= 2 else 1
    for parser_path in scripts_dir.glob(f"ingest_{co_lower}_*.py"):
        stem = parser_path.stem.lower()
        overlap = sum(1 for w in doc_words if w in stem)
        if overlap >= needed_overlap:
            return True
    return False


def _classify_status(file_count: int, hook_exists: bool, parser_exists: bool) -> str:
    """Map (file_count, hook, parser) to one of the 4 status labels."""
    if file_count < _CANDIDATE_MIN_FILES:
        return "EARLY"
    if hook_exists and parser_exists:
        return "AUTOMATED"
    if hook_exists or parser_exists:
        return "PARTIAL"
    return "CANDIDATE"


def _build_recommendation(
    company: str,
    document_type: str,
    status: str,
    file_count: int,
    hook_exists: bool,
    parser_exists: bool,
) -> str:
    """Human-readable recommendation tailored to the status."""
    if status == "EARLY":
        return (
            f"{company} has {file_count} {document_type} file(s); "
            f"will become a CANDIDATE at >= {_CANDIDATE_MIN_FILES} files."
        )
    if status == "AUTOMATED":
        return (
            f"{company} × {document_type} fully automated "
            f"(post-ingest hook + parser detected, {file_count} files in channel)."
        )
    if status == "PARTIAL":
        missing = []
        if not hook_exists:
            missing.append("post-ingest hook")
        if not parser_exists:
            missing.append("parser script")
        return (
            f"{company} × {document_type}: partial automation — missing "
            f"{' + '.join(missing)}. Channel has {file_count} files; "
            f"consider completing automation."
        )
    return (
        f"{company} has accumulated {file_count} {document_type} files with no "
        f"automation. Set up automation following the Tamara pattern: write "
        f"`scripts/ingest_{company.lower()}_{document_type}.py` (model on "
        f"`ingest_tamara_investor_pack.py`) and add a "
        f"`data/{company}/dataroom/.post-ingest.sh` invoking it."
    )


def _resolve_asset_class(company: str, data_dir: Path) -> str:
    """Pick the first product's `asset_class` from `config.json`.

    Falls back to `analysis_type` (legacy configs), then to "unknown" when
    no config is found at all. Companies with no `config.json` shouldn't
    happen in practice; the fallback exists so detection doesn't crash.
    """
    co_dir = data_dir / company
    if not co_dir.is_dir():
        return "unknown"
    for child in sorted(co_dir.iterdir()):
        if not child.is_dir() or child.name in ("dataroom", "mind", "legal"):
            continue
        cfg_path = child / "config.json"
        if not cfg_path.exists():
            continue
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        ac = cfg.get("asset_class") or cfg.get("analysis_type")
        if ac:
            return str(ac)
    return "unknown"


def _load_registry(company: str, data_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load the dataroom registry. Returns empty dict on missing/malformed."""
    registry_path = data_dir / company / "dataroom" / "registry.json"
    if not registry_path.is_file():
        return {}
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


# ── Public API ──────────────────────────────────────────────────────────────


def detect_recurring_patterns(
    company: str,
    *,
    data_dir: Optional[Path] = None,
    scripts_dir: Optional[Path] = None,
) -> List[RecurringPattern]:
    """Detect recurring channels for one company.

    Reads `data/{company}/dataroom/registry.json`, groups by `document_type`
    (excluding `other`/`unknown`), classifies each cluster.

    Returns patterns sorted: CANDIDATE > PARTIAL > EARLY > AUTOMATED
    (most-actionable first), with file_count as tiebreaker.
    """
    data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
    scripts_dir = Path(scripts_dir) if scripts_dir else _DEFAULT_SCRIPTS_DIR

    registry = _load_registry(company, data_dir)
    if not registry:
        return []

    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for doc in registry.values():
        if not isinstance(doc, dict):
            continue
        doc_type = doc.get("document_type")
        if not isinstance(doc_type, str) or doc_type in _SKIP_DOC_TYPES:
            continue
        by_type.setdefault(doc_type, []).append(doc)

    if not by_type:
        return []

    asset_class = _resolve_asset_class(company, data_dir)
    hook_present = _hook_exists(company, data_dir)
    detected_at = datetime.now(timezone.utc).isoformat()

    patterns: List[RecurringPattern] = []
    for doc_type, entries in by_type.items():
        file_count = len(entries)
        if file_count < 1:
            continue
        file_dates = _file_dates_from_entries(entries)
        cadence_days, cadence_label = _classify_cadence(_deltas_days(file_dates))
        parser_present = _parser_exists(company, doc_type, scripts_dir)
        status = _classify_status(file_count, hook_present, parser_present)
        recommendation = _build_recommendation(
            company, doc_type, status, file_count, hook_present, parser_present,
        )
        patterns.append(RecurringPattern(
            pattern_id=f"{company}::{doc_type}",
            company=company,
            document_type=doc_type,
            asset_class=asset_class,
            file_count=file_count,
            file_dates=file_dates,
            cadence_days=cadence_days,
            cadence_label=cadence_label,
            hook_exists=hook_present,
            parser_exists=parser_present,
            automation_status=status,
            recommendation=recommendation,
            detected_at=detected_at,
        ))

    patterns.sort(key=lambda p: (_STATUS_ORDER.get(p.automation_status, 99), -p.file_count))
    return patterns


def detect_emergent_asset_class_patterns(
    *,
    data_dir: Optional[Path] = None,
    scripts_dir: Optional[Path] = None,
) -> List[EmergentPattern]:
    """Walk every company; surface (asset_class, doc_type) combos shared by 2+.

    Emergent patterns are SIGNALS for the analyst — they do NOT auto-write
    to Asset Class Mind. The Operator Center surfaces them with a "Promote
    to Asset Class Mind" button that hands off to `core/mind/promotion.py`.

    Filters:
    - Skips patterns below CANDIDATE threshold (count < 3) — early channels
      shouldn't drive cross-company generalisations.
    - Skips companies whose `asset_class` resolves to "unknown".
    """
    data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
    scripts_dir = Path(scripts_dir) if scripts_dir else _DEFAULT_SCRIPTS_DIR

    if not data_dir.is_dir():
        return []

    combo_map: Dict[Tuple[str, str], Dict[str, int]] = {}

    for company_dir in data_dir.iterdir():
        if not company_dir.is_dir() or company_dir.name.startswith("_"):
            continue
        company = company_dir.name
        patterns = detect_recurring_patterns(
            company, data_dir=data_dir, scripts_dir=scripts_dir,
        )
        for p in patterns:
            if p.file_count < _CANDIDATE_MIN_FILES:
                continue
            if p.asset_class == "unknown":
                continue
            key = (p.asset_class, p.document_type)
            combo_map.setdefault(key, {})[company] = p.file_count

    detected_at = datetime.now(timezone.utc).isoformat()
    emergent: List[EmergentPattern] = []
    for (asset_class, doc_type), companies_dict in sorted(combo_map.items()):
        if len(companies_dict) < 2:
            continue
        companies = sorted(companies_dict.keys())
        suggested = (
            f"{asset_class} companies typically deliver {doc_type} files. "
            f"Observed across {len(companies)} portfolio companies: "
            f"{', '.join(companies)}."
        )
        emergent.append(EmergentPattern(
            asset_class=asset_class,
            document_type=doc_type,
            companies=companies,
            company_file_counts=dict(companies_dict),
            detected_at=detected_at,
            suggested_text=suggested,
        ))
    return emergent


def write_patterns_to_company_mind(
    company: str,
    patterns: List[RecurringPattern],
) -> int:
    """Append entries to `data/{company}/mind/recurring_channels.jsonl`.

    Idempotency: only appends a new entry when the LATEST existing entry for
    the same `pattern_id` has a different `automation_status` OR `file_count`.
    Status transitions (e.g. CANDIDATE → AUTOMATED after analyst sets up the
    hook) preserve historical context — both rows survive in the JSONL,
    forming an audit trail.

    Returns: count of new entries written.
    """
    if not patterns:
        return 0

    from core.mind.company_mind import CompanyMind

    # Product slot is informational — CompanyMind writes to the company-level
    # `mind/` directory regardless of product. Empty string is fine.
    mind = CompanyMind(company, "")
    existing = mind._read_entries("recurring_channels")

    latest_by_pattern: Dict[str, Dict[str, Any]] = {}
    for entry in existing:
        pid = entry.metadata.get("pattern_id")
        if not pid:
            continue
        prior = latest_by_pattern.get(pid)
        if prior is None or entry.timestamp > prior["timestamp"]:
            latest_by_pattern[pid] = {
                "timestamp": entry.timestamp,
                "automation_status": entry.metadata.get("automation_status"),
                "file_count": entry.metadata.get("file_count"),
            }

    written = 0
    for pattern in patterns:
        prior = latest_by_pattern.get(pattern.pattern_id)
        if prior:
            same = (
                prior["automation_status"] == pattern.automation_status
                and prior["file_count"] == pattern.file_count
            )
            if same:
                continue
        content = (
            f"Recurring channel: {pattern.company} × {pattern.document_type} "
            f"({pattern.file_count} files, {pattern.cadence_label}, "
            f"status={pattern.automation_status})"
        )
        mind.record(
            category="recurring_channels",
            content=content,
            metadata={
                "pattern_id": pattern.pattern_id,
                "automation_status": pattern.automation_status,
                "file_count": pattern.file_count,
                "document_type": pattern.document_type,
                "asset_class": pattern.asset_class,
                "hook_exists": pattern.hook_exists,
                "parser_exists": pattern.parser_exists,
                "cadence_days": pattern.cadence_days,
                "cadence_label": pattern.cadence_label,
                "recommendation": pattern.recommendation,
                "detected_at": pattern.detected_at,
                "prior_status": prior["automation_status"] if prior else None,
            },
        )
        written += 1
    return written


def write_fund_wide_stats(
    *,
    data_dir: Optional[Path] = None,
    scripts_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compute + write fund-wide rolling stats.

    Single JSON file at `data/_master_mind/recurring_channel_stats.json`,
    REWRITTEN (not appended) on each run. Per CLAUDE.md design constraint:
    Master Mind doesn't get per-pattern entries; just one strategic summary.
    """
    data_dir = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
    scripts_dir = Path(scripts_dir) if scripts_dir else _DEFAULT_SCRIPTS_DIR

    by_status = {"AUTOMATED": 0, "PARTIAL": 0, "CANDIDATE": 0, "EARLY": 0}
    by_company: Dict[str, Dict[str, int]] = {}
    total_patterns = 0
    emergent_count = 0

    if data_dir.is_dir():
        for company_dir in sorted(data_dir.iterdir()):
            if not company_dir.is_dir() or company_dir.name.startswith("_"):
                continue
            company = company_dir.name
            patterns = detect_recurring_patterns(
                company, data_dir=data_dir, scripts_dir=scripts_dir,
            )
            if not patterns:
                continue
            company_summary = {"AUTOMATED": 0, "PARTIAL": 0, "CANDIDATE": 0, "EARLY": 0}
            for p in patterns:
                by_status[p.automation_status] = by_status.get(p.automation_status, 0) + 1
                company_summary[p.automation_status] = company_summary.get(p.automation_status, 0) + 1
            by_company[company] = company_summary
            total_patterns += len(patterns)

        emergent = detect_emergent_asset_class_patterns(
            data_dir=data_dir, scripts_dir=scripts_dir,
        )
        emergent_count = len(emergent)

    today = datetime.now(timezone.utc)
    stats = {
        "generated_at": today.isoformat(),
        "total_patterns": total_patterns,
        "by_status": by_status,
        "by_company": by_company,
        "emergent_candidates": emergent_count,
        "summary": (
            f"As of {today.strftime('%Y-%m-%d')}: "
            f"{len(by_company)} companies with recurring channels, "
            f"{by_status['AUTOMATED']} automated, "
            f"{by_status['CANDIDATE']} candidates flagged, "
            f"{by_status['PARTIAL']} partial, "
            f"{by_status['EARLY']} too early to call. "
            f"{emergent_count} cross-company emergent pattern(s) "
            f"pending analyst review."
        ),
    }

    out_path = data_dir / "_master_mind" / "recurring_channel_stats.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, default=str)
    return stats


def auto_fire_after_ingest(company: str) -> Dict[str, Any]:
    """Wrapper called from `dataroom_ctl ingest`/`refresh` post-success.

    Best-effort: catches every exception so detection failures NEVER break
    the deploy pipeline. Returns a dict with `error` set on failure.
    """
    summary: Dict[str, Any] = {
        "company": company,
        "patterns_detected": 0,
        "new_mind_entries": 0,
        "fund_stats_updated": False,
    }
    try:
        patterns = detect_recurring_patterns(company)
        summary["patterns_detected"] = len(patterns)
        summary["new_mind_entries"] = write_patterns_to_company_mind(company, patterns)
        write_fund_wide_stats()
        summary["fund_stats_updated"] = True
    except Exception as e:  # noqa: BLE001 — must not crash deploy
        logger.warning(
            "pattern_detector.auto_fire_after_ingest(%s) failed: %s", company, e,
        )
        summary["error"] = str(e)
    return summary


__all__ = [
    "RecurringPattern",
    "EmergentPattern",
    "detect_recurring_patterns",
    "detect_emergent_asset_class_patterns",
    "write_patterns_to_company_mind",
    "write_fund_wide_stats",
    "auto_fire_after_ingest",
]
