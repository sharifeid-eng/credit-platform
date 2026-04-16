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
import os
import pickle
import uuid
from datetime import datetime
from pathlib import Path

from .classifier import DocumentType, classify_document
from .chunker import chunk_document
from .parsers import get_parser


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

# Files to exclude from data room ingestion (config files, not data)
_EXCLUDE_FILENAMES = {"config.json", "methodology.json", "registry.json",
                      "index.pkl"}

# Directories to skip during recursive scan (prevents ingesting engine output)
_EXCLUDE_DIRS = {"chunks", "analytics", "__pycache__", "node_modules", ".git", "mind"}


def _is_supported(filepath: str) -> bool:
    """Check if a file has a supported extension for parsing."""
    p = Path(filepath)
    if p.name in _EXCLUDE_FILENAMES:
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

        # Build hash lookup for existing docs (filepath -> doc_id)
        existing_hashes = {}
        for doc_id, doc in registry.items():
            existing_hashes[doc.get("sha256")] = doc_id

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
            "errors": [],
            "documents": [],
        }

        for fpath in files:
            try:
                file_hash = _file_sha256(str(fpath))

                # Skip if already ingested with same hash
                if file_hash in existing_hashes:
                    result["skipped"] += 1
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

            except Exception as e:
                result["errors"].append({
                    "file": str(fpath),
                    "error": str(e),
                })

        self._save_registry(company, product, registry)

        # Rebuild search index
        self._build_index(company, product, registry)

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
        source = Path(source_dir)
        if not source.exists():
            return {"error": f"Directory not found: {source_dir}"}

        registry = self._load_registry(company, product)

        # Map current registry: filepath -> (doc_id, hash)
        current_files = {}
        for doc_id, doc in registry.items():
            fp = doc.get("filepath")
            if fp:
                current_files[fp] = (doc_id, doc.get("sha256"))

        # Scan source directory
        disk_files = {}
        for root, _dirs, filenames in os.walk(str(source)):
            for fname in filenames:
                fpath = str(Path(root) / fname)
                if _is_supported(fpath):
                    disk_files[fpath] = _file_sha256(fpath)

        result = {"added": 0, "updated": 0, "removed": 0, "unchanged": 0, "errors": []}

        # Detect new and changed files
        for fpath, file_hash in disk_files.items():
            if fpath in current_files:
                old_id, old_hash = current_files[fpath]
                if old_hash == file_hash:
                    result["unchanged"] += 1
                else:
                    # File changed: remove old, re-ingest
                    self._remove_doc(company, product, old_id, registry)
                    try:
                        doc = self._ingest_single_file(
                            company, product, fpath, file_hash, registry
                        )
                        if doc.get("error"):
                            result["errors"].append({"file": fpath, "error": doc["error"]})
                        else:
                            result["updated"] += 1
                    except Exception as e:
                        result["errors"].append({"file": fpath, "error": str(e)})
            else:
                # New file
                try:
                    doc = self._ingest_single_file(
                        company, product, fpath, file_hash, registry
                    )
                    if doc.get("error"):
                        result["errors"].append({"file": fpath, "error": doc["error"]})
                    else:
                        result["added"] += 1
                except Exception as e:
                    result["errors"].append({"file": fpath, "error": str(e)})

        # Detect removed files (in registry but not on disk)
        disk_paths = set(disk_files.keys())
        for fpath, (doc_id, _) in current_files.items():
            if fpath not in disk_paths:
                self._remove_doc(company, product, doc_id, registry)
                result["removed"] += 1

        self._save_registry(company, product, registry)
        self._build_index(company, product, registry)

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
            except Exception:
                pass

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

        return {
            "total_documents": len(registry),
            "total_chunks": total_chunks,
            "total_pages": total_pages,
            "by_type": by_type,
            "has_index": self._index_path(company, product).exists(),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

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

        # Classify
        text_preview = parse_result.text[:2000] if parse_result.text else None
        doc_type = classify_document(str(path), text_preview)

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
            "filepath": str(path),
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
        except Exception:
            pass

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

        Silently skips if sklearn is not available.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except ImportError:
            return  # No sklearn, search will use simple fallback

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
