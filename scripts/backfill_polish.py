"""Backfill polish pass on existing draft memos.

Context (2026-04-19): Stage 6 polish was rewritten from one-shot all-sections
JSON to per-section parallel calls because the monolithic response hit
max_tokens truncation on ~40K+ char memos, producing JSONDecodeError and
leaving memos saved with `polished: false`. This script reprocesses the
affected memos through the fixed polish stage only — no re-generation, no
research, no citation audit (all already saved in the prior version).

Scope:
    - Iterates reports/memos/{company}_{product}/{memo_id}/meta.json
    - Picks memos where status == "draft" AND polished == false
    - Loads the latest version, runs MemoGenerator._polish_memo(...)
    - If polish succeeded (memo["polished"] == True), bumps to v{N+1}.json
      via MemoStorage.save(). If it failed or was partial, optionally still
      saves (flagged via --save-partial) so operators can inspect.
    - Sidecars (research_packs.json, citation_issues.json) are preserved
      automatically — .save() only writes the citation_issues sidecar on
      first save when it's transient; here those fields aren't on the loaded
      memo (transient fields are stripped before writing v{N}.json), so the
      existing sidecars stay untouched.

Usage:
    python scripts/backfill_polish.py --dry-run
    python scripts/backfill_polish.py            # executes
    python scripts/backfill_polish.py --company klaim --product UAE_healthcare
    python scripts/backfill_polish.py --memo-id c1686e76-841
    python scripts/backfill_polish.py --save-partial  # save even if partial polish
    python scripts/backfill_polish.py --max 5    # cap at 5 memos per run

Safety:
    - Dry-run by default prints what would be processed without writing.
    - Never deletes prior versions; always creates v{N+1}.
    - Skips memos that already have polished==true.
    - Skips non-draft memos (review/final/archived stay immutable).
    - Exits with non-zero code if any polish attempt raised unexpectedly.

Cost estimate:
    Each memo = ~11 polishable sections × Opus 4.7 polish call.
    Per-section: ~2K prompt tokens + ~3K output = ~5K tokens.
    ~$0.50-0.80 per memo at Opus 4.7 pricing.
    Run against a small batch first (--max 3) to validate.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Iterator, Optional

# Project root — adjust sys.path so `from core.memo import ...` works when
# invoked from anywhere.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.memo.generator import MemoGenerator
from core.memo.storage import MemoStorage

logger = logging.getLogger("backfill_polish")


def _iter_memo_meta(base: Path) -> Iterator[tuple[Path, dict]]:
    """Yield (meta_path, meta_dict) for every memo under reports/memos/."""
    if not base.exists():
        return
    for product_dir in base.iterdir():
        if not product_dir.is_dir():
            continue
        for memo_dir in product_dir.iterdir():
            if not memo_dir.is_dir():
                continue
            meta_path = memo_dir / "meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping unreadable meta: %s — %s", meta_path, e)
                continue
            yield meta_path, meta


def _select(meta: dict, filters: dict) -> bool:
    """Return True iff this memo matches all requested filters."""
    if meta.get("status") != "draft":
        return False
    if meta.get("polished") is True:
        return False
    if filters.get("company") and meta.get("company") != filters["company"]:
        return False
    if filters.get("product") and meta.get("product") != filters["product"]:
        return False
    if filters.get("memo_id") and meta.get("id") != filters["memo_id"]:
        return False
    return True


def backfill_one(storage: MemoStorage, generator: MemoGenerator,
                 meta: dict, dry_run: bool, save_partial: bool) -> dict:
    """Reprocess one memo through the polish stage. Returns a result record."""
    memo_id = meta["id"]
    company = meta["company"]
    product = meta["product"]

    result = {
        "memo_id": memo_id,
        "company": company,
        "product": product,
        "prev_version": meta.get("current_version"),
        "prev_polished": meta.get("polished"),
        "action": None,
        "new_version": None,
        "polished": None,
        "sections_polished": None,
        "sections_failed": None,
        "error": None,
    }

    if dry_run:
        result["action"] = "would_process"
        return result

    memo = storage.load(company, product, memo_id)
    if memo is None:
        result["action"] = "skip_load_failed"
        result["error"] = "storage.load returned None"
        return result

    try:
        polished_memo = generator._polish_memo(memo)
    except Exception as e:
        logger.error("Polish raised for %s/%s/%s: %s",
                     company, product, memo_id, e, exc_info=True)
        result["action"] = "polish_exception"
        result["error"] = str(e)
        return result

    result["polished"] = bool(polished_memo.get("polished"))
    polish_meta = (polished_memo.get("generation_meta") or {}).get("polish") or {}
    result["sections_polished"] = polish_meta.get("sections_polished")
    result["sections_failed"] = polish_meta.get("sections_failed")

    if not result["polished"] and not save_partial:
        result["action"] = "skip_partial_not_saved"
        return result

    try:
        storage.save(polished_memo)
    except Exception as e:
        logger.error("Save raised for %s: %s", memo_id, e, exc_info=True)
        result["action"] = "save_exception"
        result["error"] = str(e)
        return result

    # Re-read meta to confirm new version
    new_meta_path = Path(storage.base) / f"{company}_{product}" / memo_id / "meta.json"
    try:
        new_meta = json.loads(new_meta_path.read_text(encoding="utf-8"))
        result["new_version"] = new_meta.get("current_version")
    except Exception:
        pass
    result["action"] = "polished_and_saved" if result["polished"] else "partial_saved"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=None,
                        help="Memo storage root (default: reports/memos/)")
    parser.add_argument("--company", default=None, help="Filter by company")
    parser.add_argument("--product", default=None, help="Filter by product")
    parser.add_argument("--memo-id", default=None, help="Filter by memo id")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be processed without writing")
    parser.add_argument("--save-partial", action="store_true",
                        help="Save new version even if polish was partial")
    parser.add_argument("--max", type=int, default=None,
                        help="Cap at N memos per run")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    storage = MemoStorage(base_dir=args.base)
    generator = MemoGenerator()

    base = storage.base
    filters = {
        "company": args.company,
        "product": args.product,
        "memo_id": args.memo_id,
    }

    candidates = []
    for _meta_path, meta in _iter_memo_meta(base):
        if _select(meta, filters):
            candidates.append(meta)

    if args.max:
        candidates = candidates[: args.max]

    if not candidates:
        print("[backfill_polish] No draft memos with polished=false match filters.")
        return 0

    print(f"[backfill_polish] Found {len(candidates)} candidate(s). "
          f"dry_run={args.dry_run} save_partial={args.save_partial}")

    results = []
    for meta in candidates:
        print(f"  → {meta['company']}/{meta['product']}/{meta['id']} "
              f"(v{meta.get('current_version')}, polished={meta.get('polished')})")
        r = backfill_one(storage, generator, meta, args.dry_run, args.save_partial)
        results.append(r)
        print(f"    action={r['action']} polished={r['polished']} "
              f"v{r['prev_version']}→v{r['new_version']} "
              f"ok={r['sections_polished']} fail={r['sections_failed']} "
              f"err={r['error']}")

    # Summary
    success = sum(1 for r in results if r["action"] == "polished_and_saved")
    partial = sum(1 for r in results if r["action"] == "partial_saved")
    errors = sum(1 for r in results if r["action"] in ("polish_exception", "save_exception"))
    skipped = sum(1 for r in results if r["action"]
                  in ("skip_partial_not_saved", "skip_load_failed", "would_process"))

    print(f"\n[backfill_polish] SUMMARY: total={len(results)} "
          f"success={success} partial={partial} errors={errors} skipped={skipped}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
