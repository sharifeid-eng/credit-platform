"""
Data Room Ingestion Engine.

Generalized engine that replaces per-company ETL scripts. Scans directories,
parses files, chunks content, builds search indexes, and maintains a
file-based registry for incremental updates.

Storage layout:
    data/{company}/dataroom/
        registry.json          - Document registry (metadata + hashes)
        chunks/{doc_id}.json   - Chunked content per document
        index.pkl              - TF-IDF search index (optional, requires sklearn)
"""

import hashlib
import json
import logging
import os
import pickle
import uuid
from datetime import datetime
from pathlib import Path

from .classifier import DocumentType, classify_document
from .chunker import chunk_document
from .ingest_log import record_ingest, read_manifest, last_ingest
from .parsers import get_parser

logger = logging.getLogger("laith.dataroom")


# ── JSON serialization helper ─────────────────────────────────────────────────

def _safe(v):
    """Convert numpy/pandas types to JSON-safe Python types."""
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
        if isinstance(v, (np.bool_,)):
            return bool(v)
    except ImportError:
        pass
    try:
        import pandas as pd
        if isinstance(v, pd.Timestamp):
            return v.isoformat()[:10]
    except ImportError:
        pass
    if isinstance(v, datetime):
        return v.isoformat()[:19]
    return v


# ── File hashing ──────────────────────────────────────────────────────────────

def _file_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file for change detection."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ── Supported file extensions ─────────────────────────────────────────────────

_SUPPORTED_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".ods", ".csv", ".tsv", ".docx", ".doc", ".json"
}

# Files to exclude from data room ingestion (config files, engine output,
# not user-facing data). Dotfiles (anything starting with ".") are also
# excluded in _is_supported — covers .classification_cache.json, .ingest_log,
# and any future engine-written state that lives inside the dataroom dir.
_EXCLUDE_FILENAMES = {"config.json", "methodology.json", "registry.json",
                      "index.pkl", "meta.json", "ingest_log.jsonl",
                      "covenant_history.json", "facility_params.json",
                      "debtor_validation.json", "payment_schedule.json"}

# Directories to skip during recursive scan (prevents ingesting engine output)
_EXCLUDE_DIRS = {"chunks", "analytics", "__pycache__", "node_modules", ".git", "mind"}


def _normalize_filepath(filepath: str) -> str:
    """Normalize filepath for cross-platform comparison.

    Registry entries may have Windows backslashes from local ingestion.
    Normalize to forward slashes for consistent matching on any OS.
    """
    return filepath.replace('\\', '/')


def _is_supported(filepath: str) -> bool:
    """Check if a file has a supported extension for parsing."""
    p = Path(filepath)
    if p.name in _EXCLUDE_FILENAMES:
        return False
    # Skip dotfiles (engine-written caches/state inside the dataroom dir).
    if p.name.startswith("."):
        return False
    # Skip files inside excluded directories
    for part in p.parts:
        if part in _EXCLUDE_DIRS:
            return False
    return p.suffix.lower() in _SUPPORTED_EXTENSIONS


# ── DataRoomEngine ────────────────────────────────────────────────────────────

class DataRoomEngine:
    """Generalized data room ingestion engine.

    Provides methods to ingest, catalog, search, and refresh documents
    for any company/product combination. All state is stored as JSON files
    under the dataroom/ subdirectory of the product's data folder.

    Args:
        data_root: Root data directory (default: project data/ folder).
    """

    def __init__(self, data_root: str = None):
        if data_root:
            self._data_root = Path(data_root)
        else:
            # Default: project_root/data
            self._data_root = Path(__file__).resolve().parent.parent.parent / "data"

    def _dataroom_dir(self, company: str, product: str) -> Path:
        """Get the dataroom storage directory for a company."""
        d = self._data_root / company / "dataroom"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _chunks_dir(self, company: str, product: str) -> Path:
        """Get the chunks storage directory."""
        d = self._dataroom_dir(company, product) / "chunks"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _registry_path(self, company: str, product: str) -> Path:
        """Path to the document registry JSON file."""
        return self._dataroom_dir(company, product) / "registry.json"

    def _index_path(self, company: str, product: str) -> Path:
        """Path to the TF-IDF index pickle file."""
        return self._dataroom_dir(company, product) / "index.pkl"

    def _load_registry(self, company: str, product: str) -> dict:
        """Load the document registry from disk.

        Returns dict keyed by doc_id with document metadata.
        """
        path = self._registry_path(company, product)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_registry(self, company: str, product: str, registry: dict):
        """Save the document registry to disk."""
        path = self._registry_path(company, product)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, default=str)

    def _save_chunks(self, company: str, product: str, doc_id: str, chunks: list):
        """Save document chunks to disk."""
        path = self._chunks_dir(company, product) / f"{doc_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, default=str)

    def _meta_path(self, company: str, product: str) -> Path:
        """Path to per-dataroom meta/status file (index build state, etc.)."""
        return self._dataroom_dir(company, product) / "meta.json"

    def _meta_status(self, company: str, product: str) -> dict:
        """Load dataroom meta/status dict (returns {} if missing or invalid)."""
        path = self._meta_path(company, product)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_meta_status(self, company: str, product: str, status: dict):
        """Persist dataroom meta/status dict."""
        path = self._meta_path(company, product)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2, default=str)
        except OSError as e:
            logger.warning("[dataroom] Failed to write meta.json: %s", e)

    def _load_chunks(self, company: str, product: str, doc_id: str) -> list:
        """Load chunks for a document from disk."""
        path = self._chunks_dir(company, product) / f"{doc_id}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    # ── Public API ────────────────────────────────────────────────────────────

    def ingest(self, company: str, product: str, source_dir: str) -> dict:
        """Scan directory recursively, detect file types, parse all files, chunk, build index.

        Walks source_dir, finds all supported files, parses them, classifies
        document types, chunks content, and updates the registry. One bad file
        does not stop the entire ingest.

        Args:
            company: Company identifier (e.g. "Tamara").
            product: Product identifier (e.g. "KSA").
            source_dir: Path to the source directory to scan.

        Returns:
            IngestResult dict with:
            - total_files: number of supported files found
            - ingested: number successfully ingested
            - skipped: number skipped (already up-to-date)
            - errors: list of {file, error} dicts
            - documents: list of ingested doc_id strings
        """
        started_at = datetime.now()
        source = Path(source_dir)
        if not source.exists():
            return {
                "total_files": 0,
                "ingested": 0,
                "skipped": 0,
                "errors": [{"file": str(source_dir), "error": "Directory not found"}],
                "documents": [],
            }

        registry = self._load_registry(company, product)

        # Sweep orphan chunk files (chunks with no matching registry entry).
        # Keeps filesystem in sync with registry on every ingest. See prune().
        prune_result = self.prune(company, product)
        orphan_chunks_deleted = prune_result.get("deleted", 0)

        # Heal pre-existing duplicates and ingested engine-state files.
        # Cheap, idempotent — runs every ingest so state converges.
        dedupe_result = self.dedupe_registry(company, product)
        # Re-load because dedupe_registry may have rewritten it.
        registry = self._load_registry(company, product)

        # Build hash lookup for existing docs, but ONLY for entries whose chunks
        # file actually exists on disk. Orphan registry entries (chunks missing)
        # are evicted so their source files re-ingest. Fixes the dedup-skip bug:
        # if a synced registry.json arrives on a server with no chunks/, every
        # file would otherwise be skipped silently.
        chunks_root = self._chunks_dir(company, product)
        existing_hashes = {}
        orphans = []
        for doc_id, doc in list(registry.items()):
            if (chunks_root / f"{doc_id}.json").exists():
                existing_hashes[doc.get("sha256")] = doc_id
            else:
                orphans.append((doc_id, doc.get("filename", "?")))

        for doc_id, fname in orphans:
            registry.pop(doc_id, None)
            logger.warning(
                "[dataroom] Dropped orphan registry entry %s (%s) — chunks file missing; will re-ingest",
                doc_id, fname,
            )

        # Find all supported files
        files = []
        for root, _dirs, filenames in os.walk(str(source)):
            for fname in filenames:
                fpath = Path(root) / fname
                if _is_supported(str(fpath)):
                    files.append(fpath)

        result = {
            "total_files": len(files),
            "ingested": 0,
            "skipped": 0,
            "duplicates_skipped": 0,
            "orphans_dropped": len(orphans),
            "orphan_chunks_deleted": orphan_chunks_deleted,
            "sha_duplicates_removed": dedupe_result["sha_duplicates_removed"],
            "excluded_entries_removed": dedupe_result["excluded_removed"],
            "errors": [],
            "documents": [],
        }

        for fpath in files:
            try:
                file_hash = _file_sha256(str(fpath))

                # Skip if already ingested with same hash. `existing_hashes`
                # is updated on each successful ingest below so same-bytes
                # files at different paths within the same pass are deduped
                # (e.g. one PDF referenced from two deal-folder breadcrumbs).
                if file_hash in existing_hashes:
                    result["skipped"] += 1
                    # duplicates_skipped = subset of skipped that is a
                    # within-pass duplicate (not just a no-op re-ingest).
                    # A hash only enters existing_hashes mid-loop when we
                    # ingested it earlier in THIS call.
                    if existing_hashes[file_hash] in result["documents"]:
                        result["duplicates_skipped"] += 1
                    result["documents"].append(existing_hashes[file_hash])
                    continue

                doc_record = self._ingest_single_file(
                    company, product, str(fpath), file_hash, registry
                )
                if doc_record.get("error"):
                    result["errors"].append({
                        "file": str(fpath),
                        "error": doc_record["error"],
                    })
                else:
                    result["ingested"] += 1
                    result["documents"].append(doc_record["doc_id"])
                    existing_hashes[file_hash] = doc_record["doc_id"]

            except Exception as e:
                result["errors"].append({
                    "file": str(fpath),
                    "error": str(e),
                })

        self._save_registry(company, product, registry)

        # Rebuild search index
        self._build_index(company, product, registry)

        # Append to ingest manifest so audit/health endpoints can report
        status = self._meta_status(company, product)
        record_ingest(
            self._data_root, company, product,
            action="ingest",
            started_at=started_at,
            result=result,
            extras={
                "index_status": status.get("index_status", "unknown"),
                "index_size_bytes": status.get("index_size_bytes"),
                "registry_count": len(registry),
                "orphan_chunks_deleted": orphan_chunks_deleted,
            },
        )

        return result

    def ingest_file(self, company: str, product: str, filepath: str) -> dict:
        """Ingest a single file.

        Parses the file, classifies it, chunks the content, and updates the
        registry and search index.

        Args:
            company: Company identifier.
            product: Product identifier.
            filepath: Path to the file to ingest.

        Returns:
            DocumentRecord dict with doc_id, type, chunks count, and metadata.
        """
        path = Path(filepath)
        if not path.exists():
            return {"error": f"File not found: {filepath}"}

        if not _is_supported(str(path)):
            return {"error": f"Unsupported file type: {path.suffix}"}

        registry = self._load_registry(company, product)
        file_hash = _file_sha256(str(path))

        doc_record = self._ingest_single_file(
            company, product, str(path), file_hash, registry
        )

        self._save_registry(company, product, registry)
        self._build_index(company, product, registry)

        return doc_record

    def catalog(self, company: str, product: str) -> list:
        """List all ingested documents from the registry.

        Args:
            company: Company identifier.
            product: Product identifier.

        Returns:
            List of document record dicts sorted by ingest time.
        """
        registry = self._load_registry(company, product)
        docs = list(registry.values())
        docs.sort(key=lambda d: d.get("ingested_at", ""), reverse=True)
        return docs

    def refresh(self, company: str, product: str, source_dir: str) -> dict:
        """Incremental update -- detect new/changed files by SHA-256 hash.

        Re-scans the source directory. Files with unchanged hashes are skipped.
        Files with new hashes are re-ingested. Files in the registry but no
        longer on disk are marked as removed.

        Args:
            company: Company identifier.
            product: Product identifier.
            source_dir: Path to the source directory.

        Returns:
            RefreshResult dict with counts of added, updated, removed, unchanged.
        """
        started_at = datetime.now()
        source = Path(source_dir)
        if not source.exists():
            return {"error": f"Directory not found: {source_dir}"}

        registry = self._load_registry(company, product)

        # Sweep orphan chunk files (chunks with no matching registry entry).
        prune_result = self.prune(company, product)
        orphan_chunks_deleted = prune_result.get("deleted", 0)

        # Heal pre-existing duplicates and ingested engine-state files.
        dedupe_result = self.dedupe_registry(company, product)
        registry = self._load_registry(company, product)

        # Map current registry: normalized filepath -> (doc_id, hash).
        # Orphan entries (chunks file missing) are evicted so the file
        # re-ingests cleanly on this pass.
        chunks_root = self._chunks_dir(company, product)
        current_files = {}
        orphans = []
        for doc_id, doc in list(registry.items()):
            if not (chunks_root / f"{doc_id}.json").exists():
                orphans.append((doc_id, doc.get("filename", "?")))
                continue
            fp = doc.get("filepath")
            if fp:
                current_files[_normalize_filepath(fp)] = (doc_id, doc.get("sha256"))

        for doc_id, fname in orphans:
            registry.pop(doc_id, None)
            logger.warning(
                "[dataroom.refresh] Dropped orphan registry entry %s (%s) — chunks file missing",
                doc_id, fname,
            )

        # Scan source directory
        disk_files = {}
        for root, _dirs, filenames in os.walk(str(source)):
            for fname in filenames:
                fpath = str(Path(root) / fname)
                if _is_supported(fpath):
                    disk_files[fpath] = _file_sha256(fpath)

        result = {"added": 0, "updated": 0, "removed": 0, "unchanged": 0,
                  "duplicates_skipped": 0,
                  "relinked": 0,
                  "orphan_chunks_deleted": orphan_chunks_deleted,
                  "sha_duplicates_removed": dedupe_result["sha_duplicates_removed"],
                  "excluded_entries_removed": dedupe_result["excluded_removed"],
                  "errors": []}

        # Hash lookup across all registry entries with surviving chunks, so we
        # can detect same-bytes-different-path within this pass. Updated as
        # we ingest so two NEW disk files with identical bytes don't both
        # become registry entries.
        registry_hashes = {
            doc.get("sha256"): doc_id
            for doc_id, doc in registry.items()
            if (chunks_root / f"{doc_id}.json").exists() and doc.get("sha256")
        }

        # Track which registry entries were relinked to a new on-disk path
        # this pass. Any paths mapped here are considered "present on disk"
        # by the removal sweep below, so relinked entries aren't dropped.
        relinked_disk_paths: set = set()

        # Detect new and changed files
        for fpath, file_hash in disk_files.items():
            norm_fpath = _normalize_filepath(fpath)
            if norm_fpath in current_files:
                old_id, old_hash = current_files[norm_fpath]
                if old_hash == file_hash:
                    result["unchanged"] += 1
                else:
                    # File changed: remove old, re-ingest
                    self._remove_doc(company, product, old_id, registry)
                    registry_hashes.pop(old_hash, None)
                    try:
                        doc = self._ingest_single_file(
                            company, product, fpath, file_hash, registry
                        )
                        if doc.get("error"):
                            result["errors"].append({"file": fpath, "error": doc["error"]})
                        else:
                            result["updated"] += 1
                            registry_hashes[file_hash] = doc["doc_id"]
                    except Exception as e:
                        result["errors"].append({"file": fpath, "error": str(e)})
            else:
                # Same-bytes match at a new path. Could be either:
                #   (a) The ONLY registry entry for this hash, whose recorded
                #       filepath no longer exists on disk (source was moved) —
                #       relink to the new path so removal sweep keeps it.
                #   (b) A genuine second copy of an already-registered file —
                #       dedup-skip so we don't create a duplicate entry.
                # The old filepath check distinguishes them: if the registry's
                # path for this hash is NOT on disk, relink; else dedup.
                if file_hash in registry_hashes:
                    existing_id = registry_hashes[file_hash]
                    existing_fp = _normalize_filepath(
                        registry[existing_id].get("filepath", "")
                    )
                    existing_on_disk = existing_fp in {
                        _normalize_filepath(p) for p in disk_files.keys()
                    }
                    if not existing_on_disk and existing_fp not in relinked_disk_paths:
                        # Source file was moved — update registry filepath so
                        # the removal sweep doesn't drop this entry.
                        registry[existing_id]["filepath"] = norm_fpath
                        relinked_disk_paths.add(norm_fpath)
                        result["relinked"] += 1
                        logger.info(
                            "[dataroom.refresh] Relinked %s: %s → %s",
                            existing_id, existing_fp or "(unknown)", norm_fpath,
                        )
                    else:
                        result["duplicates_skipped"] += 1
                    continue
                # New file
                try:
                    doc = self._ingest_single_file(
                        company, product, fpath, file_hash, registry
                    )
                    if doc.get("error"):
                        result["errors"].append({"file": fpath, "error": doc["error"]})
                    else:
                        result["added"] += 1
                        registry_hashes[file_hash] = doc["doc_id"]
                except Exception as e:
                    result["errors"].append({"file": fpath, "error": str(e)})

        # Detect removed files (in registry but not on disk).
        # Relinked entries appear in the registry with a new filepath that
        # isn't in current_files (which was built before the loop), so we
        # union relinked paths into the "on disk" set.
        disk_paths = {_normalize_filepath(p) for p in disk_files.keys()}
        for fpath, (doc_id, _) in current_files.items():
            if fpath in disk_paths:
                continue
            # If this doc was relinked to a new path, skip removal.
            new_fp = _normalize_filepath(registry.get(doc_id, {}).get("filepath", ""))
            if new_fp in relinked_disk_paths:
                continue
            self._remove_doc(company, product, doc_id, registry)
            result["removed"] += 1

        self._save_registry(company, product, registry)
        self._build_index(company, product, registry)

        # Append structured manifest entry (Tier 2.3 — ingest_log).
        status = self._meta_status(company, product)
        record_ingest(
            self._data_root, company, product,
            action="refresh",
            started_at=started_at,
            result=result,
            extras={
                "index_status": status.get("index_status", "unknown"),
                "index_size_bytes": status.get("index_size_bytes"),
                "registry_count": len(registry),
                "orphans_dropped": len(orphans),
                "orphan_chunks_deleted": orphan_chunks_deleted,
            },
        )

        return result

    def get_document(self, company: str, product: str, doc_id: str) -> dict:
        """Get a single document with its chunks.

        Args:
            company: Company identifier.
            product: Product identifier.
            doc_id: Document ID from the registry.

        Returns:
            Dict with document metadata and chunks list, or error.
        """
        registry = self._load_registry(company, product)
        doc = registry.get(doc_id)
        if not doc:
            return {"error": f"Document not found: {doc_id}"}

        chunks = self._load_chunks(company, product, doc_id)
        return {
            **doc,
            "chunks": chunks,
        }

    def search(self, company: str, product: str, query: str, top_k: int = 10) -> list:
        """Search across all chunks using TF-IDF similarity.

        Falls back to simple word-frequency matching if sklearn is not available.

        Args:
            company: Company identifier.
            product: Product identifier.
            query: Search query string.
            top_k: Number of top results to return (default 10).

        Returns:
            List of result dicts with doc_id, chunk_index, score, text snippet,
            and document metadata.
        """
        index_path = self._index_path(company, product)

        # Try sklearn-based TF-IDF search
        if index_path.exists():
            try:
                results = self._search_tfidf(company, product, query, top_k)
                if results is not None:
                    return results
            except Exception as e:
                logger.warning(
                    "[dataroom.search] TF-IDF search failed for %s/%s: %s — "
                    "falling back to word-frequency search",
                    company, product, e,
                )
        else:
            logger.info(
                "[dataroom.search] No index.pkl for %s/%s — using word-frequency fallback",
                company, product,
            )

        # Fallback: simple word-frequency search
        return self._search_simple(company, product, query, top_k)

    def get_stats(self, company: str, product: str) -> dict:
        """Aggregate stats for a company/product data room.

        Args:
            company: Company identifier.
            product: Product identifier.

        Returns:
            Dict with total_documents, total_chunks, by_type breakdown,
            total_pages, and storage info.
        """
        registry = self._load_registry(company, product)

        if not registry:
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "total_pages": 0,
                "by_type": {},
                "has_index": False,
            }

        total_chunks = 0
        total_pages = 0
        by_type = {}

        for doc_id, doc in registry.items():
            doc_type = doc.get("document_type", "other")
            by_type.setdefault(doc_type, {"count": 0, "chunks": 0, "pages": 0})
            by_type[doc_type]["count"] += 1
            by_type[doc_type]["pages"] += doc.get("page_count", 0)

            chunk_count = doc.get("chunk_count", 0)
            by_type[doc_type]["chunks"] += chunk_count
            total_chunks += chunk_count
            total_pages += doc.get("page_count", 0)

        status = self._meta_status(company, product)
        return {
            "total_documents": len(registry),
            "total_chunks": total_chunks,
            "total_pages": total_pages,
            "by_type": by_type,
            "has_index": self._index_path(company, product).exists(),
            "index_status": status.get("index_status", "unknown"),
            "index_built_at": status.get("index_built_at"),
            "index_size_bytes": status.get("index_size_bytes"),
        }

    def rebuild_index_only(self, company: str, product: str) -> dict:
        """Rebuild the TF-IDF index from existing chunks without re-parsing source files.

        Used by `dataroom_ctl rebuild-index` after:
          - sklearn install fixes a degraded_no_sklearn state
          - an index.pkl file is corrupted or deleted
          - chunks were manually edited

        Returns {status, registry_count, index_status, duration_s}.
        """
        started_at = datetime.now()
        registry = self._load_registry(company, product)
        self._build_index(company, product, registry)
        status = self._meta_status(company, product)
        return {
            "status": "ok",
            "registry_count": len(registry),
            "index_status": status.get("index_status", "unknown"),
            "index_size_bytes": status.get("index_size_bytes"),
            "duration_s": round((datetime.now() - started_at).total_seconds(), 2),
        }

    def wipe(self, company: str, product: str) -> dict:
        """Delete registry, chunks, index, and meta for a dataroom.

        Destructive -- dataroom_ctl wipe prompts for confirmation before
        calling this. Source files under dataroom/ are not touched.
        """
        import shutil
        dr_dir = self._dataroom_dir(company, product)
        removed = {"registry": False, "chunks": 0, "index": False, "meta": False}

        reg = dr_dir / "registry.json"
        if reg.exists():
            reg.unlink()
            removed["registry"] = True

        chunks_dir = self._chunks_dir(company, product)
        if chunks_dir.exists():
            removed["chunks"] = len(list(chunks_dir.glob("*.json")))
            shutil.rmtree(chunks_dir, ignore_errors=True)

        idx = self._index_path(company, product)
        if idx.exists():
            idx.unlink()
            removed["index"] = True

        meta = self._meta_path(company, product)
        if meta.exists():
            meta.unlink()
            removed["meta"] = True

        logger.warning(
            "[dataroom.wipe] Wiped %s/%s: registry=%s chunks=%d index=%s meta=%s",
            company, product, removed["registry"], removed["chunks"],
            removed["index"], removed["meta"],
        )
        return removed

    def prune(self, company: str, product: str) -> dict:
        """Delete chunk files on disk whose doc_id is not in the registry.

        Complement to the existing orphan-registry eviction in `ingest()` and
        `refresh()` (which drop registry entries whose chunks file is missing).
        This handles the reverse leak: because `doc_id` is a random uuid4, every
        forced re-ingest writes new chunk files alongside the old ones. Sha256
        dedup keeps the registry clean; the filesystem leaks without prune().

        Returns {"deleted": int, "kept": int, "chunk_dir_missing": bool}.
        Idempotent; safe when chunks/ doesn't exist.
        """
        registry = self._load_registry(company, product)
        chunks_dir = self._chunks_dir(company, product)

        if not chunks_dir.exists():
            return {"deleted": 0, "kept": 0, "chunk_dir_missing": True}

        registered_ids = set(registry.keys())
        deleted = 0
        kept = 0
        for p in chunks_dir.glob("*.json"):
            if p.stem in registered_ids:
                kept += 1
                continue
            try:
                p.unlink()
                deleted += 1
                logger.warning(
                    "[dataroom.prune] Deleted orphan chunk %s for %s/%s — no matching registry entry",
                    p.name, company, product,
                )
            except OSError as e:
                logger.warning("[dataroom.prune] Failed to delete %s: %s", p, e)

        if deleted or kept:
            logger.info(
                "[dataroom.prune] %s/%s: deleted=%d kept=%d",
                company, product, deleted, kept,
            )
        return {"deleted": deleted, "kept": kept, "chunk_dir_missing": False}

    def dedupe_registry(self, company: str, product: str) -> dict:
        """Clean up pre-existing duplicates and ingested engine-written files.

        Heals registries that accumulated state under the pre-fix behavior:
          - Two+ registry entries with the same sha256 (same bytes ingested
            from different folder paths — keeps the earliest ingested_at,
            deletes the rest along with their chunk files).
          - Registry entries whose filename is now on the exclusion list
            (e.g. `.classification_cache.json`, `meta.json`) — deletes them
            and their chunk files.

        Idempotent. Auto-called from `ingest()` and `refresh()` so state
        converges on every run; also exposed via `dataroom_ctl dedupe`.

        Returns:
            {"sha_duplicates_removed": int, "excluded_removed": int,
             "kept": int, "chunk_files_deleted": int}
        """
        registry = self._load_registry(company, product)
        if not registry:
            return {
                "sha_duplicates_removed": 0,
                "excluded_removed": 0,
                "kept": 0,
                "chunk_files_deleted": 0,
            }

        chunks_dir = self._chunks_dir(company, product)
        chunk_files_deleted = 0

        # Pass 1 — evict entries whose filename is on the exclusion list or
        # is a dotfile. These should never have been ingested.
        excluded_removed = 0
        for doc_id, doc in list(registry.items()):
            fname = doc.get("filename", "")
            if fname in _EXCLUDE_FILENAMES or fname.startswith("."):
                logger.warning(
                    "[dataroom.dedupe] Removing excluded entry %s (%s) from %s/%s",
                    doc_id, fname, company, product,
                )
                self._remove_doc(company, product, doc_id, registry)
                chunk_files_deleted += 1
                excluded_removed += 1

        # Pass 2 — group surviving entries by sha256. For each group with
        # more than one entry, keep the earliest `ingested_at` (fallback:
        # lowest doc_id) and drop the rest.
        by_hash: dict = {}
        for doc_id, doc in registry.items():
            sha = doc.get("sha256")
            if not sha:
                continue
            by_hash.setdefault(sha, []).append(doc_id)

        sha_duplicates_removed = 0
        for sha, ids in by_hash.items():
            if len(ids) < 2:
                continue
            ids.sort(
                key=lambda d: (
                    registry[d].get("ingested_at", "9999"),
                    d,
                )
            )
            winner = ids[0]
            for loser in ids[1:]:
                logger.warning(
                    "[dataroom.dedupe] Duplicate sha256 %s… — keeping %s (%s), "
                    "removing %s (%s) from %s/%s",
                    sha[:10], winner, registry[winner].get("filename", "?"),
                    loser, registry[loser].get("filename", "?"),
                    company, product,
                )
                self._remove_doc(company, product, loser, registry)
                chunk_files_deleted += 1
                sha_duplicates_removed += 1

        # Persist the cleaned registry
        if excluded_removed or sha_duplicates_removed:
            self._save_registry(company, product, registry)

        # Any chunk files still referencing removed doc_ids were unlinked
        # via _remove_doc; account for chunks dir actually missing.
        if not chunks_dir.exists():
            chunk_files_deleted = 0

        return {
            "sha_duplicates_removed": sha_duplicates_removed,
            "excluded_removed": excluded_removed,
            "kept": len(registry),
            "chunk_files_deleted": chunk_files_deleted,
        }

    def audit(self, company: str, product: str = "") -> dict:
        """Full health audit for a company/product data room.

        Surfaces misalignments that deploy.sh and /dataroom/health both care about:
          - registry_count vs chunk_count (orphan registry entries or stray chunks)
          - missing_chunks -- registry entries whose chunks file isn't on disk
          - orphan_chunks -- chunk files with no matching registry entry
          - index_status -- ok / degraded_no_sklearn / empty_no_chunks / unknown
          - last_ingest -- most recent clean entry from ingest_log.jsonl
          - unclassified_count -- docs classified as 'other' or 'unknown'

        Args:
            company: Company identifier.
            product: Product identifier (optional for company-level datarooms).

        Returns:
            Structured dict consumed by /dataroom/health and dataroom_ctl audit.
        """
        registry = self._load_registry(company, product)
        chunks_root = self._chunks_dir(company, product)

        # Per-doc chunk alignment
        missing_chunks = []
        registered_ids = set()
        unclassified_count = 0
        for doc_id, doc in registry.items():
            registered_ids.add(doc_id)
            if not (chunks_root / f"{doc_id}.json").exists():
                missing_chunks.append({
                    "doc_id": doc_id,
                    "filename": doc.get("filename", "?"),
                })
            if doc.get("document_type") in ("other", "unknown", None):
                unclassified_count += 1

        # Orphan chunks (chunk files with no registry entry)
        orphan_chunks = []
        chunk_count = 0
        if chunks_root.exists():
            for p in chunks_root.glob("*.json"):
                chunk_count += 1
                if p.stem not in registered_ids:
                    orphan_chunks.append(p.name)

        status = self._meta_status(company, product)
        idx_path = self._index_path(company, product)
        index_age_seconds = None
        if idx_path.exists():
            try:
                index_age_seconds = int(
                    (datetime.now().timestamp() - idx_path.stat().st_mtime)
                )
            except OSError:
                pass

        last = last_ingest(self._data_root, company)

        aligned = (
            len(registry) > 0
            and len(registry) == chunk_count
            and not missing_chunks
            and not orphan_chunks
        )

        return {
            "company": company,
            "product": product or "",
            "registry_count": len(registry),
            "chunk_count": chunk_count,
            "aligned": aligned,
            "missing_chunks": missing_chunks[:20],  # cap for payload size
            "missing_chunks_total": len(missing_chunks),
            "orphan_chunks": orphan_chunks[:20],
            "orphan_chunks_total": len(orphan_chunks),
            "unclassified_count": unclassified_count,
            "index_status": status.get("index_status", "unknown"),
            "index_built_at": status.get("index_built_at"),
            "index_size_bytes": status.get("index_size_bytes"),
            "index_age_seconds": index_age_seconds,
            "last_ingest": last,
        }

    # -- Internal helpers --------------------------------------------------

    def _ingest_single_file(
        self, company: str, product: str, filepath: str, file_hash: str, registry: dict
    ) -> dict:
        """Parse, classify, chunk, and register a single file.

        Mutates the registry dict in place. Returns the document record.
        """
        path = Path(filepath)

        # Parse
        parser = get_parser(str(path))
        if parser is None:
            return {"error": f"No parser for file type: {path.suffix}"}

        parse_result = parser.parse(str(path))

        if parse_result.error and not parse_result.text and not parse_result.tables:
            return {"error": parse_result.error}

        # Classify — rule-based first (filename → text → sheet-names),
        # with optional LLM fallback (Tier 3.2) only when rules return 'other'.
        text_preview = parse_result.text[:2000] if parse_result.text else None
        sheet_names = parse_result.metadata.get("sheets") if parse_result.metadata else None
        doc_type = classify_document(str(path), text_preview, sheet_names=sheet_names)

        if doc_type == DocumentType.OTHER:
            try:
                from .classifier_llm import classify_with_llm
                llm_result = classify_with_llm(
                    filepath=str(path),
                    text_preview=text_preview or "",
                    sheet_names=sheet_names or [],
                    sha256=file_hash,
                    data_root=str(self._data_root),
                    company=company,
                )
                if llm_result and llm_result.get("doc_type"):
                    # Promote only if model is confident; otherwise mark unknown.
                    confidence = llm_result.get("confidence", 0.0)
                    if confidence >= 0.6:
                        try:
                            doc_type = DocumentType(llm_result["doc_type"])
                        except ValueError:
                            # Model returned a type we don't recognize — keep as unknown
                            doc_type = DocumentType.UNKNOWN
                    else:
                        doc_type = DocumentType.UNKNOWN
            except ImportError:
                # classifier_llm not installed — silently keep 'other'
                pass
            except Exception as e:
                logger.warning(
                    "[dataroom] LLM classifier fallback failed for %s: %s",
                    path.name, e,
                )

        # Chunk
        chunks = chunk_document(
            text=parse_result.text,
            tables=parse_result.tables,
            metadata={
                "filename": path.name,
                "document_type": doc_type.value,
            },
        )

        # Generate doc_id
        doc_id = str(uuid.uuid4())[:12]

        # Build document record
        doc_record = {
            "doc_id": doc_id,
            "filename": path.name,
            "filepath": _normalize_filepath(str(path)),
            "document_type": doc_type.value,
            "sha256": file_hash,
            "page_count": parse_result.page_count,
            "chunk_count": len(chunks),
            "text_length": len(parse_result.text) if parse_result.text else 0,
            "table_count": len(parse_result.tables) if parse_result.tables else 0,
            "parser_metadata": {
                k: _safe(v) for k, v in parse_result.metadata.items()
            },
            "ingested_at": datetime.now().isoformat()[:19],
        }

        if parse_result.error:
            doc_record["parse_warnings"] = parse_result.error

        # Save chunks
        self._save_chunks(company, product, doc_id, chunks)

        # Update registry
        registry[doc_id] = doc_record

        # Fire DOCUMENT_INGESTED event for Intelligence System
        try:
            from core.mind.event_bus import event_bus, Events
            event_bus.publish(Events.DOCUMENT_INGESTED, {
                "company": company,
                "product": product,
                "doc_id": doc_id,
                "text": (parse_result.text[:5000] if parse_result.text else ""),
                "document_type": doc_type.value,
                "filename": path.name,
            })
        except Exception as e:
            # Non-fatal: event bus / listener failure must not block ingest.
            # Logged so operator can see if entity extraction / thesis drift
            # are silently skipping.
            logger.info(
                "[dataroom] DOCUMENT_INGESTED event dispatch failed for %s: %s",
                doc_id, e,
            )

        return doc_record

    def _remove_doc(self, company: str, product: str, doc_id: str, registry: dict):
        """Remove a document from registry and delete its chunks file."""
        if doc_id in registry:
            del registry[doc_id]

        chunk_path = self._chunks_dir(company, product) / f"{doc_id}.json"
        if chunk_path.exists():
            try:
                chunk_path.unlink()
            except OSError:
                pass

    def _build_index(self, company: str, product: str, registry: dict):
        """Build TF-IDF search index from all chunks.

        Index is stored as a pickle file containing the vectorizer,
        the TF-IDF matrix, and chunk references (doc_id + chunk_index).

        Logs a clear warning if sklearn is unavailable and records the
        degraded state in the registry meta so health checks can surface it.
        """
        status = self._meta_status(company, product)

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except ImportError:
            logger.warning(
                "[dataroom.index] sklearn not installed — TF-IDF index NOT built "
                "for %s/%s. Search will fall back to word-frequency scoring. "
                "Install scikit-learn to enable semantic search.",
                company, product,
            )
            status["index_status"] = "degraded_no_sklearn"
            status["index_built_at"] = datetime.now().isoformat()[:19]
            self._save_meta_status(company, product, status)
            return

        all_texts = []
        all_refs = []

        for doc_id in registry:
            chunks = self._load_chunks(company, product, doc_id)
            for chunk in chunks:
                text = chunk.get("text", "")
                if text.strip():
                    all_texts.append(text)
                    all_refs.append({
                        "doc_id": doc_id,
                        "chunk_index": chunk.get("chunk_index", 0),
                        "chunk_type": chunk.get("chunk_type", "text"),
                        "section_heading": chunk.get("section_heading"),
                    })

        if not all_texts:
            logger.warning(
                "[dataroom.index] No chunks to index for %s/%s (registry has %d docs "
                "but zero non-empty chunks). Leaving index.pkl untouched.",
                company, product, len(registry),
            )
            status["index_status"] = "empty_no_chunks"
            status["index_built_at"] = datetime.now().isoformat()[:19]
            self._save_meta_status(company, product, status)
            return

        vectorizer = TfidfVectorizer(
            max_features=10000,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        tfidf_matrix = vectorizer.fit_transform(all_texts)

        index_data = {
            "vectorizer": vectorizer,
            "matrix": tfidf_matrix,
            "refs": all_refs,
            "texts": all_texts,
        }

        index_path = self._index_path(company, product)
        with open(index_path, "wb") as f:
            pickle.dump(index_data, f)

        logger.info(
            "[dataroom.index] Built TF-IDF index for %s/%s: %d chunks, %d bytes",
            company, product, len(all_texts), index_path.stat().st_size,
        )
        status["index_status"] = "ok"
        status["index_built_at"] = datetime.now().isoformat()[:19]
        status["index_chunk_count"] = len(all_texts)
        status["index_size_bytes"] = index_path.stat().st_size
        self._save_meta_status(company, product, status)

    def _search_tfidf(
        self, company: str, product: str, query: str, top_k: int
    ) -> list:
        """Search using the pre-built TF-IDF index.

        Returns list of result dicts or None if index can't be loaded.
        """
        from sklearn.metrics.pairwise import cosine_similarity

        index_path = self._index_path(company, product)
        with open(index_path, "rb") as f:
            index_data = pickle.load(f)

        vectorizer = index_data["vectorizer"]
        matrix = index_data["matrix"]
        refs = index_data["refs"]
        texts = index_data["texts"]

        query_vec = vectorizer.transform([query])
        scores = cosine_similarity(query_vec, matrix).flatten()

        # Get top-k indices
        top_indices = scores.argsort()[::-1][:top_k]

        registry = self._load_registry(company, product)
        results = []

        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue

            ref = refs[idx]
            doc_id = ref["doc_id"]
            doc_meta = registry.get(doc_id, {})

            # Text snippet (first 300 chars)
            text = texts[idx]
            snippet = text[:300] + "..." if len(text) > 300 else text

            results.append({
                "doc_id": doc_id,
                "chunk_index": ref["chunk_index"],
                "score": round(score, 4),
                "snippet": snippet,
                "section_heading": ref.get("section_heading"),
                "filename": doc_meta.get("filename"),
                "document_type": doc_meta.get("document_type"),
            })

        return results

    def _search_simple(
        self, company: str, product: str, query: str, top_k: int
    ) -> list:
        """Simple word-frequency search fallback when sklearn is not available.

        Scores chunks by the count of query words that appear in the chunk text.
        """
        query_words = set(query.lower().split())
        if not query_words:
            return []

        registry = self._load_registry(company, product)
        scored = []

        for doc_id, doc_meta in registry.items():
            chunks = self._load_chunks(company, product, doc_id)
            for chunk in chunks:
                text = chunk.get("text", "")
                if not text:
                    continue

                text_lower = text.lower()
                # Score: count of unique query words found + frequency bonus
                words_found = sum(1 for w in query_words if w in text_lower)
                if words_found == 0:
                    continue

                freq_score = sum(text_lower.count(w) for w in query_words)
                score = words_found * 10 + min(freq_score, 50)

                snippet = text[:300] + "..." if len(text) > 300 else text

                scored.append({
                    "doc_id": doc_id,
                    "chunk_index": chunk.get("chunk_index", 0),
                    "score": score,
                    "snippet": snippet,
                    "section_heading": chunk.get("section_heading"),
                    "filename": doc_meta.get("filename"),
                    "document_type": doc_meta.get("document_type"),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
