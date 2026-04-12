"""
Operator Command Center — Backend endpoints for the Laith platform operator dashboard.

Provides:
- GET  /operator/status         — Aggregate health, commands, gaps, freshness
- GET  /operator/todo           — Personal follow-up list
- POST /operator/todo           — Add follow-up item
- PATCH /operator/todo/{id}     — Update follow-up item (toggle complete, edit)
- DELETE /operator/todo/{id}    — Delete follow-up item
- GET  /operator/mind           — Browse all mind entries (master + company)
- PATCH /operator/mind/{id}     — Promote/archive a mind entry
- POST /operator/digest         — Generate weekly digest (Slack or JSON)
"""

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.loader import get_companies, get_products, get_snapshots, DATA_DIR
from core.config import load_config
from core.activity_log import read_activity_log

router = APIRouter(prefix="/operator", tags=["operator"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TODO_PATH = _PROJECT_ROOT / "tasks" / "operator_todo.json"
_REPORTS_DIR = _PROJECT_ROOT / "reports"

# ── Command Registry (static) ────────────────────────────────────────────────

COMMANDS = [
    # Framework commands
    {"name": "/onboard-company", "description": "Full 6-phase onboarding workflow with framework compliance checks", "category": "framework"},
    {"name": "/add-tape", "description": "Validate, compare, integrate new tape file", "category": "framework"},
    {"name": "/validate-tape", "description": "Comprehensive data quality checks with A-F grading", "category": "framework"},
    {"name": "/framework-audit", "description": "Audit ALL companies against framework (L1-L5 coverage)", "category": "framework"},
    {"name": "/extend-framework", "description": "Add new metrics/tabs with propagation across all layers", "category": "framework"},
    {"name": "/methodology-sync", "description": "Detect drift between methodology page and backend", "category": "framework"},
    {"name": "/company-health", "description": "Quick diagnostic: coverage, freshness, gaps, compliance score", "category": "framework"},
    # Session commands
    {"name": "/eod", "description": "End-of-session cleanup: tests, docs, commit, push", "category": "session"},
    {"name": "/simplify", "description": "Review changed code for reuse, quality, efficiency", "category": "session"},
    {"name": "/ops", "description": "Operator briefing — surfaces platform status in terminal", "category": "session"},
    # Deep work modes
    {"name": "MODE 1: Codebase Health Audit", "description": "Comprehensive health check — tech debt, inconsistencies, silent failures", "category": "deep_work"},
    {"name": "MODE 2: Test Generation Sprint", "description": "Identify untested code paths, generate test suite", "category": "deep_work"},
    {"name": "MODE 3: Architecture Review", "description": "Extensibility, maintainability, refactoring roadmap", "category": "deep_work"},
    {"name": "MODE 4: Documentation Sprint", "description": "System overview, API reference, component guide", "category": "deep_work"},
    {"name": "MODE 5: Prompt Optimisation", "description": "Audit and improve AI prompts, evaluation framework", "category": "deep_work"},
    {"name": "MODE 6: Red Team Review", "description": "Adversarial review — misleading results, silent failures", "category": "deep_work"},
    {"name": "MODE 7: Regression Validation", "description": "Verify prior Critical/High findings are resolved", "category": "deep_work"},
]

# ── Helper functions ──────────────────────────────────────────────────────────

def _compute_company_health(company: str, product: str, config: dict) -> dict:
    """Assemble health data for a single company/product."""
    analysis_type = config.get("analysis_type", "klaim")
    currency = config.get("currency", "USD")
    product_path = Path(DATA_DIR) / company / product

    # Tape freshness
    snaps = get_snapshots(company, product)
    tape_count = len(snaps)
    latest_date = snaps[-1]["date"] if snaps else None
    days_stale = None
    freshness_status = "unknown"
    if latest_date:
        try:
            days_stale = (date.today() - date.fromisoformat(latest_date)).days
            if days_stale <= 30:
                freshness_status = "fresh"
            elif days_stale <= 60:
                freshness_status = "stale"
            else:
                freshness_status = "outdated"
        except ValueError:
            freshness_status = "unknown"

    # Legal coverage
    legal_dir = product_path / "legal"
    legal_docs = []
    legal_extracted = False
    if legal_dir.is_dir():
        legal_docs = [f for f in os.listdir(legal_dir) if f.endswith(".pdf")]
        legal_extracted = any(f.endswith("_extracted.json") for f in os.listdir(legal_dir))

    # Data room
    registry_path = product_path / "dataroom" / "registry.json"
    dataroom_docs = 0
    if registry_path.exists():
        try:
            with open(registry_path) as f:
                reg = json.load(f)
            dataroom_docs = len(reg) if isinstance(reg, dict) else len(reg) if isinstance(reg, list) else 0
        except Exception:
            pass

    # Mind entries
    mind_dir = product_path / "mind"
    mind_counts = {}
    mind_total = 0
    if mind_dir.is_dir():
        for jf in mind_dir.glob("*.jsonl"):
            try:
                count = sum(1 for line in open(jf) if line.strip())
                mind_counts[jf.stem] = count
                mind_total += count
            except Exception:
                pass

    # AI cache coverage
    ai_cache_dir = _REPORTS_DIR / "ai_cache"
    ai_cached = {"commentary": False, "executive_summary": False, "tab_insights": 0}
    if ai_cache_dir.is_dir():
        prefix = f"{company}_{product}_"
        for cf in ai_cache_dir.iterdir():
            if not cf.name.startswith(prefix):
                continue
            if "commentary" in cf.name and "tab" not in cf.name:
                ai_cached["commentary"] = True
            elif "executive_summary" in cf.name:
                ai_cached["executive_summary"] = True
            elif "tab_insight" in cf.name:
                ai_cached["tab_insights"] += 1

    # Gaps detection
    gaps = _detect_gaps(company, product, config, snaps, legal_extracted,
                        dataroom_docs, mind_total, days_stale, product_path)

    return {
        "company": company,
        "product": product,
        "analysis_type": analysis_type,
        "currency": currency,
        "tape_freshness": {
            "latest_date": latest_date,
            "days_stale": days_stale,
            "status": freshness_status,
        },
        "tape_count": tape_count,
        "legal_docs": len(legal_docs),
        "legal_extracted": legal_extracted,
        "dataroom_docs": dataroom_docs,
        "mind_entries": mind_counts,
        "mind_total": mind_total,
        "ai_cache": ai_cached,
        "gaps": gaps,
    }


def _detect_gaps(company, product, config, snaps, legal_extracted,
                 dataroom_docs, mind_total, days_stale, product_path) -> list:
    """Heuristic gap detection for a company/product."""
    gaps = []
    analysis_type = config.get("analysis_type", "klaim")

    # Tape freshness
    if not snaps:
        gaps.append({"severity": "critical", "text": "No tape data available"})
    elif days_stale and days_stale > 60:
        gaps.append({"severity": "warning", "text": f"Latest tape is {days_stale} days old — request updated tape"})
    elif days_stale and days_stale > 30:
        gaps.append({"severity": "info", "text": f"Latest tape is {days_stale} days old"})

    # Legal coverage
    if analysis_type not in ("ejari_summary", "tamara_summary"):
        if not legal_extracted:
            gaps.append({"severity": "info", "text": "No facility agreement uploaded/extracted"})

    # Known data gaps from debtor_validation.json
    debtor_path = product_path / "legal" / "debtor_validation.json"
    if debtor_path.exists():
        try:
            with open(debtor_path) as f:
                dv = json.load(f)
            cg = dv.get("critical_gap")
            if cg:
                gaps.append({"severity": "critical", "text": cg})
        except Exception:
            pass

    # Mind entries
    if mind_total == 0:
        gaps.append({"severity": "info", "text": "Company Mind not populated — AI context will be limited"})

    # Data room
    if dataroom_docs == 0 and analysis_type not in ("ejari_summary",):
        gaps.append({"severity": "info", "text": "Data room not ingested"})

    return gaps


def _load_todos() -> List[Dict[str, Any]]:
    """Load operator todo items from disk."""
    if not _TODO_PATH.exists():
        return []
    try:
        with open(_TODO_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def _save_todos(todos: List[Dict[str, Any]]) -> None:
    """Persist operator todo items to disk."""
    _TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_TODO_PATH, "w") as f:
        json.dump(todos, f, indent=2, ensure_ascii=False)


def _read_all_mind_entries() -> List[Dict[str, Any]]:
    """Read ALL mind entries across master + all companies for browsing."""
    entries = []

    # Master mind
    master_dir = Path(DATA_DIR) / "_master_mind"
    if master_dir.is_dir():
        for jf in master_dir.glob("*.jsonl"):
            try:
                with open(jf) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        entry["_source"] = "master"
                        entry["_company"] = None
                        entry["_product"] = None
                        entry["_file"] = jf.stem
                        entries.append(entry)
            except Exception:
                pass

    # Company minds
    for co in get_companies():
        if co.startswith("_"):
            continue
        for prod in get_products(co):
            mind_dir = Path(DATA_DIR) / co / prod / "mind"
            if not mind_dir.is_dir():
                continue
            for jf in mind_dir.glob("*.jsonl"):
                try:
                    with open(jf) as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            entry = json.loads(line)
                            entry["_source"] = "company"
                            entry["_company"] = co
                            entry["_product"] = prod
                            entry["_file"] = jf.stem
                            entries.append(entry)
                except Exception:
                    pass

    # Sort newest first
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries


# ── Pydantic Models ───────────────────────────────────────────────────────────

class TodoCreate(BaseModel):
    text: str
    company: Optional[str] = None
    priority: str = "P1"  # P0, P1, P2
    category: str = "general"  # general, data_request, ic_followup, bug, feature

class TodoUpdate(BaseModel):
    text: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    category: Optional[str] = None

class MindUpdate(BaseModel):
    promoted: Optional[bool] = None
    archived: Optional[bool] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
def get_operator_status():
    """Aggregate operator status across all companies, commands, and activity."""
    companies_health = []

    for co in get_companies():
        if co.startswith("_"):
            continue
        for prod in get_products(co):
            config = load_config(co, prod) or {}
            health = _compute_company_health(co, prod, config)
            companies_health.append(health)

    # Activity log (recent 50)
    activity = read_activity_log(limit=50)

    # Operator todos
    todos = _load_todos()

    # Deep work sessions
    progress_path = _REPORTS_DIR / "deep-work" / "progress.json"
    deep_work_sessions = []
    if progress_path.exists():
        try:
            with open(progress_path) as f:
                dw = json.load(f)
            deep_work_sessions = dw.get("sessions", [])
        except Exception:
            pass

    # NotebookLM engine status
    nlm_status = None
    try:
        from core.research.notebooklm_bridge import NotebookLMEngine
        engine = NotebookLMEngine()
        nlm_status = engine.get_status()
    except Exception:
        nlm_status = {"available": False, "error": "Failed to probe NLM engine"}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commands": COMMANDS,
        "companies": companies_health,
        "activity_log": activity,
        "todos": todos,
        "deep_work_sessions": deep_work_sessions,
        "notebooklm": nlm_status,
    }


@router.get("/todo")
def get_operator_todos():
    """Get all operator follow-up items."""
    return _load_todos()


@router.post("/todo")
def create_operator_todo(item: TodoCreate):
    """Add a new operator follow-up item."""
    from core.activity_log import log_activity, OPERATOR_TODO

    todos = _load_todos()
    new_item = {
        "id": str(uuid.uuid4())[:8],
        "text": item.text,
        "company": item.company,
        "priority": item.priority,
        "category": item.category,
        "completed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    todos.append(new_item)
    _save_todos(todos)

    log_activity(OPERATOR_TODO, company=item.company, detail=f"Added: {item.text}")
    return new_item


@router.patch("/todo/{item_id}")
def update_operator_todo(item_id: str, update: TodoUpdate):
    """Update an operator follow-up item (toggle complete, edit text, etc.)."""
    todos = _load_todos()
    item = next((t for t in todos if t["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Todo item not found")

    if update.text is not None:
        item["text"] = update.text
    if update.priority is not None:
        item["priority"] = update.priority
    if update.category is not None:
        item["category"] = update.category
    if update.completed is not None:
        item["completed"] = update.completed
        item["completed_at"] = datetime.now(timezone.utc).isoformat() if update.completed else None

    _save_todos(todos)
    return item


@router.delete("/todo/{item_id}")
def delete_operator_todo(item_id: str):
    """Delete an operator follow-up item."""
    todos = _load_todos()
    todos = [t for t in todos if t["id"] != item_id]
    _save_todos(todos)
    return {"ok": True}


@router.get("/mind")
def get_mind_entries(company: Optional[str] = None, category: Optional[str] = None):
    """Browse all mind entries across master + all companies.

    Query params:
        company: Filter to a specific company (optional)
        category: Filter to a specific category (optional)
    """
    entries = _read_all_mind_entries()

    if company:
        entries = [e for e in entries if e.get("_company") == company or (company == "_master" and e.get("_source") == "master")]
    if category:
        entries = [e for e in entries if e.get("category") == category or e.get("_file") == category]

    return {
        "total": len(entries),
        "entries": entries[:100],  # Cap at 100 for response size
    }


@router.patch("/mind/{entry_id}")
def update_mind_entry(entry_id: str, update: MindUpdate):
    """Promote or archive a mind entry.

    Promotion: copies a company mind entry to master mind.
    Archive: marks an entry with archived flag (soft delete).
    """
    # Find the entry across all JSONL files
    all_dirs = []

    # Master mind
    master_dir = Path(DATA_DIR) / "_master_mind"
    if master_dir.is_dir():
        all_dirs.append(("master", None, None, master_dir))

    # Company minds
    for co in get_companies():
        if co.startswith("_"):
            continue
        for prod in get_products(co):
            mind_dir = Path(DATA_DIR) / co / prod / "mind"
            if mind_dir.is_dir():
                all_dirs.append(("company", co, prod, mind_dir))

    # Search for the entry
    for source, co, prod, mind_dir in all_dirs:
        for jf in mind_dir.glob("*.jsonl"):
            lines = []
            found = False
            try:
                with open(jf) as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            lines.append(line)
                            continue
                        entry = json.loads(stripped)
                        if entry.get("id") == entry_id:
                            found = True
                            if update.promoted is not None:
                                entry["promoted"] = update.promoted
                            if update.archived is not None:
                                entry["archived"] = update.archived
                            lines.append(json.dumps(entry, ensure_ascii=False) + "\n")

                            # If promoting from company to master, also append to master
                            if update.promoted and source == "company":
                                _promote_to_master(entry, co, prod)
                        else:
                            lines.append(line)
                if found:
                    with open(jf, "w") as f:
                        f.writelines(lines)
                    return {"ok": True, "id": entry_id}
            except Exception:
                continue

    raise HTTPException(status_code=404, detail="Mind entry not found")


def _promote_to_master(entry: dict, company: str, product: str):
    """Copy a company mind entry to the master mind cross_company file."""
    master_dir = Path(DATA_DIR) / "_master_mind"
    master_dir.mkdir(parents=True, exist_ok=True)
    cross_company_path = master_dir / "cross_company.jsonl"

    promoted_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": "cross_company",
        "content": f"[Promoted from {company}/{product}] {entry.get('content', '')}",
        "metadata": {
            "source_company": company,
            "source_product": product,
            "source_id": entry.get("id"),
            "source_category": entry.get("category"),
        },
        "promoted": False,
    }
    with open(cross_company_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(promoted_entry, ensure_ascii=False) + "\n")


@router.post("/digest")
def generate_operator_digest(webhook_url: Optional[str] = None):
    """Generate a weekly operator digest.

    If webhook_url is provided, sends to Slack. Otherwise returns JSON.
    """
    # Get full status
    status = get_operator_status()

    # Build digest sections
    lines = ["*Laith Operator Digest*", f"Generated: {date.today().isoformat()}", ""]

    # Company health summary
    lines.append("*Company Health:*")
    for co in status["companies"]:
        freshness = co["tape_freshness"]
        icon = {"fresh": ":large_green_circle:", "stale": ":large_yellow_circle:", "outdated": ":red_circle:"}.get(freshness["status"], ":white_circle:")
        mind_note = f", {co['mind_total']} mind entries" if co["mind_total"] else ""
        lines.append(f"{icon} *{co['company']}/{co['product']}* — {co['tape_count']} tapes, "
                     f"{'legal extracted' if co['legal_extracted'] else 'no legal'}"
                     f"{mind_note}")
        for gap in co["gaps"]:
            sev_icon = {
                "critical": ":rotating_light:",
                "warning": ":warning:",
                "info": ":information_source:",
            }.get(gap["severity"], "")
            lines.append(f"  {sev_icon} {gap['text']}")

    # Open todos
    open_todos = [t for t in status["todos"] if not t.get("completed")]
    if open_todos:
        lines.append("")
        lines.append(f"*Open Follow-ups ({len(open_todos)}):*")
        for t in open_todos[:10]:
            prio = t.get("priority", "P1")
            co_tag = f" [{t['company']}]" if t.get("company") else ""
            lines.append(f"  • `{prio}`{co_tag} {t['text']}")

    # Recent activity (last 7 days)
    recent = [a for a in status["activity_log"][:20]]
    if recent:
        lines.append("")
        lines.append(f"*Recent Activity ({len(recent)} events):*")
        for a in recent[:8]:
            co_tag = f" [{a.get('company', '')}]" if a.get("company") else ""
            lines.append(f"  • {a['action']}{co_tag}: {a.get('detail', '')}"[:120])

    digest_text = "\n".join(lines)

    # Send to Slack if webhook provided
    if webhook_url:
        import urllib.request
        payload = json.dumps({"text": digest_text}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            return {"ok": True, "sent_to": "slack", "preview": digest_text}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Slack webhook failed: {e}")

    return {"ok": True, "digest": digest_text}
