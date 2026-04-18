"""
Data Room Control — unified operator CLI.

Single entrypoint for diagnosing and repairing any company's data room.
Designed to be run inside the backend container via:

    docker compose exec -T backend python scripts/dataroom_ctl.py <command> [args]

Commands
--------
    audit [--company X]          Health report (alignment + deps + last ingest)
    ingest --company X [--product P] [--source-dir DIR]
                                 Full ingest (DataRoomEngine.ingest)
    refresh --company X [--product P] [--source-dir DIR]
                                 Incremental refresh (DataRoomEngine.refresh)
    rebuild-index --company X [--product P]
                                 Rebuild TF-IDF index from existing chunks
    prune [--company X] [--product P]
                                 Delete orphan chunk files (no registry entry)
    wipe --company X [--product P] [--yes]
                                 Delete registry/chunks/index/meta (prompts)
    classify --company X [--product P] [--only-other]
                                 Re-classify docs (optionally limited to 'other')

Exit codes
----------
    0 success, 1 audit detected misalignment, 2 usage/argument error,
    3 operation failed, 4 user aborted destructive op.

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

from core.dataroom.engine import DataRoomEngine  # noqa: E402
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

        new_type = classify_document(filepath, preview).value

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

    if updated:
        engine._save_registry(args.company, product, registry)

    _err(
        f"[{args.company}] Classified {len(registry)} docs: "
        f"{updated} updated, {llm_calls} LLM calls"
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

    sp = sub.add_parser("wipe", help="Delete registry/chunks/index/meta (source files preserved)")
    sp.add_argument("--company", required=True)
    sp.add_argument("--product")
    sp.add_argument("--yes", action="store_true", help="Skip confirmation")
    sp.set_defaults(func=cmd_wipe)

    sp = sub.add_parser("classify", help="Re-classify docs without re-parsing")
    sp.add_argument("--company", required=True)
    sp.add_argument("--product")
    sp.add_argument("--only-other", action="store_true",
                    help="Only re-classify docs currently marked 'other' or 'unknown'")
    sp.add_argument("--use-llm", action="store_true",
                    help="Enable Haiku LLM fallback (requires classifier_llm)")
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
