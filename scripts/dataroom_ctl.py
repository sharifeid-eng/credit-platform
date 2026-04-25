"""
Data Room Control — unified operator CLI.

Single entrypoint for diagnosing and repairing any company's data room.
Designed to be run inside the backend container via:

    docker compose exec -T backend python scripts/dataroom_ctl.py <command> [args]

Commands
--------
    audit [--company X]          Health report (alignment + deps + last ingest)
    needs-ingest --company X [--product P]
                                 Detect whether ingest is required (registry
                                 corruption OR new source files since last
                                 ingest). Exit 0 = ingest needed, 1 = clean.
    ingest --company X [--product P] [--source-dir DIR]
                                 Full ingest (DataRoomEngine.ingest)
    refresh --company X [--product P] [--source-dir DIR]
                                 Incremental refresh (DataRoomEngine.refresh)
    rebuild-index --company X [--product P]
                                 Rebuild TF-IDF index from existing chunks
    prune [--company X] [--product P]
                                 Delete orphan chunk files (no registry entry)
    dedupe [--company X] [--product P]
                                 Drop sha256-duplicate registry entries
                                 and registry entries for excluded filenames
    wipe --company X [--product P] [--yes]
                                 Delete registry/chunks/index/meta (prompts)
    classify --company X [--product P] [--only-other]
                                 Re-classify docs (optionally limited to 'other')

Exit codes
----------
    0 success, 1 audit detected misalignment, 2 usage/argument error,
    3 operation failed, 4 user aborted destructive op.

    `needs-ingest` inverts the audit convention to fit shell idiom
    `if needs-ingest; then ingest; fi`: 0 = ingest needed, 1 = clean.

All commands emit structured single-line JSON on stdout for easy scraping
by deploy.sh and CI, plus a human-readable summary on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure we can import core/* regardless of CWD.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.dataroom.engine import DataRoomEngine, _is_supported  # noqa: E402
from core.loader import get_companies, get_products  # noqa: E402


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _emit(payload: dict) -> None:
    """Print structured JSON result on stdout.

    Flushes stderr first so the human-readable summary lines emitted via
    `_err()` land BEFORE the JSON payload when the two streams are merged
    (e.g. `dataroom_ctl.py audit 2>&1 | head -1`). Without this, block-buffered
    stdout in a pipe can overtake line-buffered stderr at process exit.
    """
    sys.stderr.flush()
    print(json.dumps(payload, default=str))
    sys.stdout.flush()


def _resolve_product(engine: DataRoomEngine, company: str, product: str | None) -> str:
    """Pick a product if the caller didn't specify one.

    Dataroom is company-level; product is only used as an event-bus key.
    First non-'dataroom' product wins. Returns empty string if no products.
    """
    if product:
        return product
    try:
        prods = [p for p in get_products(company) if p != "dataroom"]
    except Exception:
        prods = []
    return prods[0] if prods else ""


def _default_source_dir(company: str) -> str:
    """Default ingest source: <repo>/data/<company>/dataroom."""
    return str(_REPO_ROOT / "data" / company / "dataroom")


# ── Commands ──────────────────────────────────────────────────────────────────


def cmd_audit(args: argparse.Namespace) -> int:
    engine = DataRoomEngine()
    companies = [args.company] if args.company else get_companies()

    reports = []
    any_misaligned = False
    for co in companies:
        # Skip companies without a dataroom folder
        dr_dir = _REPO_ROOT / "data" / co / "dataroom"
        if not dr_dir.is_dir():
            continue
        product = _resolve_product(engine, co, args.product if args.company else None)
        try:
            report = engine.audit(co, product)
        except Exception as e:
            report = {"company": co, "product": product, "error": str(e)}
        reports.append(report)
        if not report.get("aligned", False) and not report.get("error"):
            any_misaligned = True

        # Human-readable line on stderr
        if report.get("error"):
            _err(f"[{co}] ERROR: {report['error']}")
        else:
            status = "aligned" if report.get("aligned") else "MISALIGNED"
            _err(
                f"[{co}] {status}: registry={report.get('registry_count')} "
                f"chunks={report.get('chunk_count')} "
                f"missing={report.get('missing_chunks_total')} "
                f"orphan={report.get('orphan_chunks_total')} "
                f"unclassified={report.get('unclassified_count')} "
                f"index={report.get('index_status')}"
            )

    _emit({"command": "audit", "reports": reports})
    return 1 if any_misaligned else 0


def _needs_ingest_check(engine: DataRoomEngine, company: str, product: str) -> dict:
    """Determine whether a company's dataroom needs an ingest run.

    Pure function — caller decides exit code + stderr formatting. Two
    conditions trigger `needs_ingest=True`:

      (a) Registry corruption: registry.json missing, registry empty, or
          registry/chunks misalignment. Same heuristic as the legacy
          deploy.sh check, just expressed once instead of in inline bash.

      (b) Source files newer than `ingest_log.jsonl` mtime. This catches
          the session-37 footgun: sync-data.ps1 drops new source files on
          prod, deploy.sh runs, registry+chunks are still aligned (e.g.
          271 == 271), so the alignment check skips ingest — even though
          two new files are sitting on disk un-chunked. Comparing mtimes
          against the append-only ingest log is the simplest signal that
          new source data has arrived since the last successful run.

    Engine-written files (config.json, registry.json, meta.json,
    ingest_log.jsonl, etc.), dotfiles, and chunks/ + analytics/ subdirs
    are excluded from the source scan via `_is_supported()` — the same
    filter the engine uses during ingest. Importing it (rather than
    re-listing the exclusions here) keeps a single source of truth.

    Args:
        engine: DataRoomEngine instance (so tests can use a tmp data root).
        company: Company identifier.
        product: Product identifier (typically "" — dataroom is company-level).

    Returns:
        dict with: company, needs_ingest (bool), reason (str),
        registry_count, chunk_count, source_file_count, plus newer_count
        when reason == "newer_files".
    """
    dr_dir = engine._data_root / company / "dataroom"
    base = {
        "company": company,
        "registry_count": 0,
        "chunk_count": 0,
        "source_file_count": 0,
    }

    if not dr_dir.is_dir():
        return {**base, "needs_ingest": False, "reason": "no_dataroom_dir"}

    # Walk the dataroom for source files using the engine's exclusion logic.
    # Same filter as ingest()/refresh() so the two paths can never disagree.
    source_files = []
    for root, _dirs, filenames in os.walk(str(dr_dir)):
        for fname in filenames:
            fpath = Path(root) / fname
            if _is_supported(str(fpath)):
                source_files.append(fpath)

    base["source_file_count"] = len(source_files)

    # Empty dataroom — clean. No point ingesting nothing; would just write
    # an empty entry to ingest_log.jsonl every deploy.
    if not source_files:
        return {**base, "needs_ingest": False, "reason": "empty_dataroom"}

    # Condition (a): registry / chunks alignment
    registry_path = dr_dir / "registry.json"
    if not registry_path.exists():
        return {**base, "needs_ingest": True, "reason": "no_registry"}

    registry = engine._load_registry(company, product)
    base["registry_count"] = len(registry)

    chunks_root = dr_dir / "chunks"
    if chunks_root.is_dir():
        base["chunk_count"] = sum(1 for _ in chunks_root.glob("*.json"))

    if base["registry_count"] == 0:
        return {**base, "needs_ingest": True, "reason": "empty_registry"}

    if base["registry_count"] != base["chunk_count"]:
        return {**base, "needs_ingest": True, "reason": "registry_chunk_mismatch"}

    # Condition (b): source files newer than ingest_log.jsonl mtime
    ingest_log = dr_dir / "ingest_log.jsonl"
    if not ingest_log.exists():
        return {**base, "needs_ingest": True, "reason": "no_ingest_log"}

    log_mtime = ingest_log.stat().st_mtime
    newer_count = 0
    for f in source_files:
        try:
            if f.stat().st_mtime > log_mtime:
                newer_count += 1
        except OSError:
            # File disappeared between walk and stat — ignore; refresh
            # will reconcile on the next pass.
            continue

    if newer_count > 0:
        return {
            **base,
            "needs_ingest": True,
            "reason": "newer_files",
            "newer_count": newer_count,
        }

    return {**base, "needs_ingest": False, "reason": "clean"}


def cmd_needs_ingest(args: argparse.Namespace) -> int:
    """Detect whether ingest is required for a company's dataroom.

    Exit code:
        0 — ingest needed (deploy.sh runs `dataroom_ctl ingest` next)
        1 — clean (deploy.sh skips)

    NB: This inverts the audit-style 0/1 convention to fit the bash idiom
    `if dataroom_ctl needs-ingest --company X; then ...; fi`. The unusual
    direction is documented in the module docstring.
    """
    engine = DataRoomEngine()
    product = _resolve_product(engine, args.company, args.product)
    result = _needs_ingest_check(engine, args.company, product)

    # Human-readable line on stderr
    if result["needs_ingest"]:
        suffix = ""
        if result.get("newer_count") is not None:
            suffix = f" newer={result['newer_count']}"
        _err(
            f"[{args.company}] ingest needed ({result['reason']}): "
            f"registry={result['registry_count']} chunks={result['chunk_count']} "
            f"source_files={result['source_file_count']}{suffix}"
        )
    else:
        _err(
            f"[{args.company}] clean ({result['reason']}): "
            f"registry={result['registry_count']} chunks={result['chunk_count']} "
            f"source_files={result['source_file_count']}"
        )

    _emit({"command": "needs-ingest", "product": product, **result})
    return 0 if result["needs_ingest"] else 1


def cmd_ingest(args: argparse.Namespace) -> int:
    engine = DataRoomEngine()
    product = _resolve_product(engine, args.company, args.product)
    source_dir = args.source_dir or _default_source_dir(args.company)

    if not os.path.isdir(source_dir):
        _err(f"Source directory not found: {source_dir}")
        _emit({"command": "ingest", "error": "source_dir_not_found", "source_dir": source_dir})
        return 2

    _err(f"[{args.company}/{product or '-'}] Ingesting from {source_dir}...")
    result = engine.ingest(args.company, product, source_dir)

    if result.get("error"):
        _err(f"  FAILED: {result['error']}")
        _emit({"command": "ingest", "company": args.company, "product": product, **result})
        return 3

    _err(
        f"  Done: files_seen={result.get('total_files', '?')} "
        f"ingested={result.get('ingested', 0)} "
        f"skipped={result.get('skipped', 0)} "
        f"orphans_dropped={result.get('orphans_dropped', 0)} "
        f"errors={len(result.get('errors', []))}"
    )
    _emit({"command": "ingest", "company": args.company, "product": product, **result})
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    engine = DataRoomEngine()
    product = _resolve_product(engine, args.company, args.product)
    source_dir = args.source_dir or _default_source_dir(args.company)

    if not os.path.isdir(source_dir):
        _err(f"Source directory not found: {source_dir}")
        _emit({"command": "refresh", "error": "source_dir_not_found"})
        return 2

    _err(f"[{args.company}/{product or '-'}] Refreshing from {source_dir}...")
    result = engine.refresh(args.company, product, source_dir)

    if result.get("error"):
        _err(f"  FAILED: {result['error']}")
        _emit({"command": "refresh", "company": args.company, "product": product, **result})
        return 3

    _err(
        f"  Done: added={result.get('added', 0)} updated={result.get('updated', 0)} "
        f"removed={result.get('removed', 0)} unchanged={result.get('unchanged', 0)} "
        f"errors={len(result.get('errors', []))}"
    )
    _emit({"command": "refresh", "company": args.company, "product": product, **result})
    return 0


def cmd_rebuild_index(args: argparse.Namespace) -> int:
    engine = DataRoomEngine()
    product = _resolve_product(engine, args.company, args.product)

    _err(f"[{args.company}/{product or '-'}] Rebuilding index from existing chunks...")
    result = engine.rebuild_index_only(args.company, product)
    _err(
        f"  Done: registry={result['registry_count']} "
        f"index={result['index_status']} "
        f"bytes={result.get('index_size_bytes')} "
        f"duration={result['duration_s']}s"
    )
    _emit({"command": "rebuild-index", "company": args.company, "product": product, **result})
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Delete orphan chunk files (present on disk but not in registry).

    Complement to the registry-orphan eviction already wired into ingest()/
    refresh(). Useful for operators cleaning up after a wipe+re-ingest where
    new uuid4 doc_ids leave old chunk files behind.
    """
    engine = DataRoomEngine()
    companies = [args.company] if args.company else get_companies()

    reports = []
    any_failure = False
    for co in companies:
        dr_dir = _REPO_ROOT / "data" / co / "dataroom"
        if not dr_dir.is_dir():
            continue
        product = _resolve_product(engine, co, args.product if args.company else None)
        try:
            result = engine.prune(co, product)
        except Exception as e:
            any_failure = True
            result = {"error": str(e)}
        reports.append({"company": co, "product": product, **result})

        if result.get("error"):
            _err(f"[{co}] ERROR: {result['error']}")
        else:
            _err(
                f"[{co}/{product or '-'}] pruned: deleted={result.get('deleted', 0)} "
                f"kept={result.get('kept', 0)} "
                f"chunk_dir_missing={result.get('chunk_dir_missing', False)}"
            )

    _emit({"command": "prune", "reports": reports})
    return 3 if any_failure else 0


def cmd_dedupe(args: argparse.Namespace) -> int:
    """Drop sha256-duplicate registry entries + excluded-filename entries.

    Heals registries that accumulated duplicates under the pre-fix engine
    (same file bytes ingested from two folder paths became two doc_ids).
    Also removes any registry entries for files now on the exclusion list
    (e.g. `.classification_cache.json`) that shouldn't have been ingested.

    Idempotent; safe to re-run. Auto-called by ingest()/refresh() too.
    """
    engine = DataRoomEngine()
    companies = [args.company] if args.company else get_companies()

    reports = []
    any_failure = False
    for co in companies:
        dr_dir = _REPO_ROOT / "data" / co / "dataroom"
        if not dr_dir.is_dir():
            continue
        product = _resolve_product(engine, co, args.product if args.company else None)
        try:
            result = engine.dedupe_registry(co, product)
        except Exception as e:
            any_failure = True
            result = {"error": str(e)}
        reports.append({"company": co, "product": product, **result})

        if result.get("error"):
            _err(f"[{co}] ERROR: {result['error']}")
        else:
            _err(
                f"[{co}/{product or '-'}] deduped: "
                f"sha_duplicates_removed={result.get('sha_duplicates_removed', 0)} "
                f"excluded_removed={result.get('excluded_removed', 0)} "
                f"kept={result.get('kept', 0)}"
            )

    _emit({"command": "dedupe", "reports": reports})
    return 3 if any_failure else 0


def cmd_wipe(args: argparse.Namespace) -> int:
    engine = DataRoomEngine()
    product = _resolve_product(engine, args.company, args.product)

    if not args.yes:
        _err(
            f"WARNING: this will delete registry, chunks, index, and meta for "
            f"{args.company}/{product or '-'}. Source files are preserved."
        )
        _err("Re-run with --yes to confirm.")
        return 4

    _err(f"[{args.company}/{product or '-'}] Wiping dataroom state...")
    removed = engine.wipe(args.company, product)
    _err(f"  Removed: {removed}")
    _emit({"command": "wipe", "company": args.company, "product": product, "removed": removed})
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    """Re-classify docs in registry without re-parsing.

    Reads cached chunk text for each document, runs classify_document(),
    optionally falls through to LLM fallback for 'other' if classifier_llm
    is available.
    """
    from core.dataroom.classifier import classify_document, DocumentType

    engine = DataRoomEngine()
    product = _resolve_product(engine, args.company, args.product)
    registry = engine._load_registry(args.company, product)

    if not registry:
        _err(f"[{args.company}] Empty registry — run `ingest` first.")
        _emit({"command": "classify", "error": "empty_registry"})
        return 2

    # Optional LLM fallback — only imported if present.
    llm_fn = None
    if args.only_other or args.use_llm:
        try:
            from core.dataroom.classifier_llm import classify_with_llm
            llm_fn = classify_with_llm
        except ImportError:
            _err("  (classifier_llm not installed — LLM fallback disabled)")

    updated = 0
    llm_calls = 0
    before = {}
    after = {}

    for doc_id, doc in registry.items():
        current = doc.get("document_type", "other")
        before[current] = before.get(current, 0) + 1

        if args.only_other and current not in ("other", "unknown"):
            after[current] = after.get(current, 0) + 1
            continue

        # Load first chunk's text for preview
        chunks = engine._load_chunks(args.company, product, doc_id)
        preview = chunks[0].get("text", "")[:2000] if chunks else ""
        filepath = doc.get("filepath", doc.get("filename", ""))

        # For Excel files, read sheet names so the _SHEET_RULES phase fires.
        # Skipping this was the silent bug that caused 15 files to regress
        # to 'other' during the 2026-04-24 reclassify session — the re-classify
        # script only passed filepath + sheet_names, NOT text_preview, and
        # every file that relied on _TEXT_RULES for its original type lost
        # classification. See tasks/lessons.md 2026-04-24 entry.
        sheet_names = None
        if filepath.lower().endswith(('.xlsx', '.xlsm', '.xls')):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
                sheet_names = list(wb.sheetnames)
                wb.close()
            except Exception:  # noqa: BLE001
                pass  # Classifier will rely on filepath + text_preview only

        new_type = classify_document(filepath, preview, sheet_names).value

        # LLM fallback if still 'other'
        if new_type == "other" and llm_fn:
            try:
                llm_calls += 1
                llm_result = llm_fn(
                    filepath=filepath,
                    text_preview=preview,
                    sha256=doc.get("sha256", ""),
                    data_root=str(_REPO_ROOT / "data"),
                    company=args.company,
                )
                if llm_result and llm_result.get("doc_type"):
                    new_type = llm_result["doc_type"]
            except Exception as e:
                _err(f"  LLM fallback failed for {doc.get('filename')}: {e}")

        if new_type != current:
            doc["document_type"] = new_type
            updated += 1

        after[new_type] = after.get(new_type, 0) + 1

    if updated and not args.dry_run:
        engine._save_registry(args.company, product, registry)

    suffix = " (dry-run — no writes)" if args.dry_run else ""
    _err(
        f"[{args.company}] Classified {len(registry)} docs: "
        f"{updated} updated, {llm_calls} LLM calls{suffix}"
    )
    _emit({
        "command": "classify",
        "company": args.company,
        "product": product,
        "total": len(registry),
        "updated": updated,
        "llm_calls": llm_calls,
        "before": before,
        "after": after,
    })
    return 0


# ── Argparse wiring ───────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dataroom_ctl",
        description="Unified operator CLI for the data room pipeline.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("audit", help="Health report across all or one company")
    ap.add_argument("--company", help="Audit only this company (default: all)")
    ap.add_argument("--product", help="Product key (rarely needed)")
    ap.set_defaults(func=cmd_audit)

    nip = sub.add_parser(
        "needs-ingest",
        help="Detect whether ingest is required (registry corruption OR new source files)",
        description=(
            "Returns exit code 0 if ingestion is needed for COMPANY, 1 if "
            "the dataroom is fully reality-aligned. Two trigger conditions: "
            "(a) registry corruption (missing/empty registry, registry-vs-chunks "
            "mismatch); (b) any source file newer than ingest_log.jsonl mtime. "
            "Source-file scan uses the same exclusion list as the engine "
            "(_EXCLUDE_FILENAMES + dotfiles + chunks/ + analytics/). "
            "Exit codes invert the audit convention to match the bash idiom "
            "`if needs-ingest; then ingest; fi`."
        ),
    )
    nip.add_argument("--company", required=True, help="Company to check")
    nip.add_argument("--product", help="Product key (autodetected if omitted)")
    nip.set_defaults(func=cmd_needs_ingest)

    for name, func in [("ingest", cmd_ingest), ("refresh", cmd_refresh)]:
        sp = sub.add_parser(name, help=f"{name.capitalize()} a dataroom")
        sp.add_argument("--company", required=True)
        sp.add_argument("--product", help="Product key (autodetected if omitted)")
        sp.add_argument("--source-dir", help="Override source directory")
        sp.set_defaults(func=func)

    sp = sub.add_parser("rebuild-index", help="Rebuild TF-IDF index from existing chunks")
    sp.add_argument("--company", required=True)
    sp.add_argument("--product")
    sp.set_defaults(func=cmd_rebuild_index)

    sp = sub.add_parser("prune", help="Delete orphan chunk files (no matching registry entry)")
    sp.add_argument("--company", help="Prune only this company (default: all)")
    sp.add_argument("--product", help="Product key (autodetected if omitted)")
    sp.set_defaults(func=cmd_prune)

    sp = sub.add_parser(
        "dedupe",
        help="Drop sha256-duplicate registry entries + excluded-filename entries",
    )
    sp.add_argument("--company", help="Dedupe only this company (default: all)")
    sp.add_argument("--product", help="Product key (autodetected if omitted)")
    sp.set_defaults(func=cmd_dedupe)

    sp = sub.add_parser("wipe", help="Delete registry/chunks/index/meta (source files preserved)")
    sp.add_argument("--company", required=True)
    sp.add_argument("--product")
    sp.add_argument("--yes", action="store_true", help="Skip confirmation")
    sp.set_defaults(func=cmd_wipe)

    sp = sub.add_parser(
        "classify",
        help="Re-classify docs without re-parsing",
        description=(
            "Re-run classify_document() on every registry entry using filepath + "
            "text_preview + sheet_names. Typical flow after editing classifier.py: "
            "`classify --company X --use-llm --dry-run` (preview) then drop "
            "--dry-run. --use-llm preserves LLM-fallback classifications that "
            "rule-only re-classify would otherwise regress to 'other'."
        ),
    )
    sp.add_argument("--company", required=True)
    sp.add_argument("--product")
    sp.add_argument("--only-other", action="store_true",
                    help="Only re-classify docs currently marked 'other' or 'unknown'")
    sp.add_argument("--use-llm", action="store_true",
                    help="Enable Haiku LLM fallback (requires classifier_llm). Recommended when re-classifying after a rule edit — preserves originally-LLM-classified docs.")
    sp.add_argument("--dry-run", action="store_true",
                    help="Preview changes without writing registry. Prints before/after counts + updated count.")
    sp.set_defaults(func=cmd_classify)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        _err("\nInterrupted.")
        return 4
    except Exception as e:
        _err(f"UNEXPECTED ERROR: {e}")
        _emit({"command": args.cmd, "error": str(e)})
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
