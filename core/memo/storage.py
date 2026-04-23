"""
File-based memo storage with immutable versioning.

Storage layout:
    reports/memos/{company}_{product}/
        {memo_id}/
            v1.json      — version 1 of the full memo
            v2.json      — version 2 (after edits)
            ...
            meta.json    — mutable metadata (status, current_version, title)

All versions are immutable once written. Edits create new versions.
Status transitions: draft -> review -> final -> archived
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_BASE = _PROJECT_ROOT / "reports" / "memos"

# Valid status transitions
_STATUS_TRANSITIONS = {
    "draft": {"review", "archived"},
    "review": {"draft", "final", "archived"},
    "final": {"archived"},
    "archived": {"draft"},  # Allow un-archiving back to draft
}


class MemoStorage:
    """File-based memo storage with immutable versioning.

    Each memo gets a directory under reports/memos/{company}_{product}/{memo_id}/.
    Versions are stored as v1.json, v2.json, etc. A meta.json file tracks
    the current version, status, and other mutable metadata.
    """

    def __init__(self, base_dir: Optional[str] = None):
        """Initialize storage.

        Args:
            base_dir: Root directory for memo storage. Defaults to
                      reports/memos/ under the project root.
        """
        if base_dir:
            self.base = Path(base_dir)
        else:
            self.base = _DEFAULT_BASE

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _memo_dir(self, company: str, product: str, memo_id: str) -> Path:
        """Get the directory for a specific memo."""
        product_dir = f"{company}_{product}"
        return self.base / product_dir / memo_id

    def _product_dir(self, company: str, product: str) -> Path:
        """Get the directory for all memos of a company/product."""
        return self.base / f"{company}_{product}"

    def _read_meta(self, memo_dir: Path) -> Optional[dict]:
        """Read meta.json from a memo directory."""
        meta_path = memo_dir / "meta.json"
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read meta.json at %s: %s", meta_path, e)
            return None

    def _write_meta(self, memo_dir: Path, meta: dict) -> None:
        """Write meta.json to a memo directory."""
        meta_path = memo_dir / "meta.json"
        meta_path.write_text(
            json.dumps(meta, indent=2, default=str),
            encoding="utf-8",
        )

    def _read_version(self, memo_dir: Path, version: int) -> Optional[dict]:
        """Read a specific version of a memo."""
        version_path = memo_dir / f"v{version}.json"
        if not version_path.exists():
            return None
        try:
            return json.loads(version_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read %s: %s", version_path, e)
            return None

    def _write_version(self, memo_dir: Path, version: int,
                       memo: dict) -> None:
        """Write a version file (immutable — will not overwrite)."""
        version_path = memo_dir / f"v{version}.json"
        if version_path.exists():
            raise ValueError(
                f"Version {version} already exists at {version_path}. "
                "Versions are immutable."
            )
        version_path.write_text(
            json.dumps(memo, indent=2, default=str),
            encoding="utf-8",
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def save(self, memo: dict) -> str:
        """Save a memo (creates new version if existing, or first version if new).

        Args:
            memo: Full memo dict (must contain id, company, product).

        Returns:
            memo_id: The ID of the saved memo.
        """
        memo_id = memo.get("id")
        company = memo.get("company", "unknown")
        product = memo.get("product", "unknown")

        if not memo_id:
            raise ValueError("Memo must have an 'id' field")

        memo_dir = self._memo_dir(company, product, memo_id)
        memo_dir.mkdir(parents=True, exist_ok=True)

        # Read existing meta or create new
        meta = self._read_meta(memo_dir)
        if meta is None:
            # First save — create meta and write v1
            version = 1
            meta = {
                "id": memo_id,
                "company": company,
                "product": product,
                "template": memo.get("template", ""),
                "template_name": memo.get("template_name", ""),
                "title": memo.get("title", ""),
                "status": memo.get("status", "draft"),
                "current_version": version,
                "created_at": memo.get("created_at", datetime.now(timezone.utc).isoformat()),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                # Hybrid pipeline metadata (additive, safely absent on legacy memos)
                "generation_mode": memo.get("generation_mode"),
                "polished": memo.get("polished", False),
                "models_used": memo.get("models_used", {}),
                "total_tokens_in": (memo.get("generation_meta") or {}).get("total_tokens_in"),
                "total_tokens_out": (memo.get("generation_meta") or {}).get("total_tokens_out"),
                "cost_usd_estimate": (memo.get("generation_meta") or {}).get("cost_usd_estimate"),
            }
        else:
            # Existing memo — increment version
            version = meta.get("current_version", 0) + 1
            meta["current_version"] = version
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            # Update title/status if changed in the memo
            if "title" in memo:
                meta["title"] = memo["title"]
            # Update hybrid pipeline metadata if present (refresh on regeneration)
            for field in ("generation_mode", "polished", "models_used"):
                if field in memo:
                    meta[field] = memo[field]
            gen_meta = memo.get("generation_meta") or {}
            for src, dst in (("total_tokens_in", "total_tokens_in"),
                             ("total_tokens_out", "total_tokens_out"),
                             ("cost_usd_estimate", "cost_usd_estimate")):
                if src in gen_meta:
                    meta[dst] = gen_meta[src]

        # Extract transient fields that should NOT land in v{N}.json
        #  - _research_packs → sidecar file (audit trail)
        #  - _citation_issues → sidecar file (audit trail)
        research_packs = memo.pop("_research_packs", None) if isinstance(memo, dict) else None
        citation_issues = memo.pop("_citation_issues", None) if isinstance(memo, dict) else None

        # Write the version file (without transient fields)
        memo_with_version = {**memo, "version": version}
        self._write_version(memo_dir, version, memo_with_version)

        # Update meta
        self._write_meta(memo_dir, meta)

        # Sidecar: research packs — only written once (first save; immutable).
        # Subsequent versions may regenerate individual sections but the
        # original research evidence is captured at creation time.
        if research_packs:
            sidecar_path = memo_dir / "research_packs.json"
            if not sidecar_path.exists():
                try:
                    sidecar_path.write_text(
                        json.dumps(research_packs, indent=2, default=str),
                        encoding="utf-8",
                    )
                    logger.info("Wrote research packs sidecar: %s", sidecar_path)
                except Exception as e:
                    logger.warning("Failed to write research_packs sidecar: %s", e)

        # Sidecar: citation issues flagged by validation pass
        if citation_issues:
            sidecar_path = memo_dir / "citation_issues.json"
            try:
                sidecar_path.write_text(
                    json.dumps(citation_issues, indent=2, default=str),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.warning("Failed to write citation_issues sidecar: %s", e)

        logger.info("Saved memo %s v%d at %s", memo_id, version, memo_dir)
        return memo_id

    def load(self, company: str, product: str, memo_id: str,
             version: Optional[int] = None) -> Optional[dict]:
        """Load a memo. If version=None, loads the latest version.

        Args:
            company: Company identifier.
            product: Product identifier.
            memo_id: Memo ID.
            version: Specific version to load (default: latest).

        Returns:
            Full memo dict, or None if not found.
        """
        memo_dir = self._memo_dir(company, product, memo_id)
        meta = self._read_meta(memo_dir)
        if meta is None:
            logger.warning("Memo %s not found at %s", memo_id, memo_dir)
            return None

        if version is None:
            version = meta.get("current_version", 1)

        memo = self._read_version(memo_dir, version)
        if memo is None:
            logger.warning("Version %d of memo %s not found", version, memo_id)
            return None

        # Merge current status from meta (status is mutable)
        memo["status"] = meta.get("status", memo.get("status", "draft"))
        return memo

    def list_memos(self, company: Optional[str] = None,
                   product: Optional[str] = None,
                   status: Optional[str] = None) -> list:
        """List all memos, optionally filtered by company/product/status.

        Returns:
            List of memo summary dicts (id, company, product, template,
            title, status, version, created_at, updated_at).
        """
        results = []

        if not self.base.exists():
            return results

        for product_dir in sorted(self.base.iterdir()):
            if not product_dir.is_dir():
                continue

            # Parse company_product directory name
            dir_name = product_dir.name
            parts = dir_name.split("_", 1)
            if len(parts) != 2:
                continue
            dir_company, dir_product = parts

            # Apply company/product filters
            if company and dir_company != company:
                continue
            if product and dir_product != product:
                continue

            for memo_dir in sorted(product_dir.iterdir()):
                if not memo_dir.is_dir():
                    continue

                meta = self._read_meta(memo_dir)
                if meta is None:
                    continue

                # Apply status filter
                if status and meta.get("status") != status:
                    continue

                results.append({
                    "id": meta.get("id", memo_dir.name),
                    "company": meta.get("company", dir_company),
                    "product": meta.get("product", dir_product),
                    "template": meta.get("template", ""),
                    "template_name": meta.get("template_name", ""),
                    "title": meta.get("title", ""),
                    "status": meta.get("status", "draft"),
                    "current_version": meta.get("current_version", 1),
                    "created_at": meta.get("created_at", ""),
                    "updated_at": meta.get("updated_at", ""),
                })

        # Sort by updated_at descending (most recent first)
        results.sort(key=lambda m: m.get("updated_at", ""), reverse=True)
        return results

    def update_status(self, company: str, product: str,
                      memo_id: str, new_status: str) -> dict:
        """Change memo status with transition validation.

        Valid transitions:
            draft -> review, archived
            review -> draft, final, archived
            final -> archived
            archived -> draft

        Args:
            company: Company identifier.
            product: Product identifier.
            memo_id: Memo ID.
            new_status: Target status.

        Returns:
            Updated meta dict.

        Raises:
            ValueError: If the transition is not valid.
        """
        memo_dir = self._memo_dir(company, product, memo_id)
        meta = self._read_meta(memo_dir)
        if meta is None:
            raise ValueError(f"Memo {memo_id} not found")

        current_status = meta.get("status", "draft")
        allowed = _STATUS_TRANSITIONS.get(current_status, set())

        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions: {sorted(allowed)}"
            )

        meta["status"] = new_status
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._write_meta(memo_dir, meta)
        logger.info("Memo %s status changed: %s -> %s",
                     memo_id, current_status, new_status)
        return meta

    def update_section(self, company: str, product: str,
                       memo_id: str, section_key: str,
                       new_content: str,
                       new_metrics: Optional[list] = None) -> dict:
        """Update a single section's content (creates a new version).

        Args:
            company: Company identifier.
            product: Product identifier.
            memo_id: Memo ID.
            section_key: Which section to update.
            new_content: New text content for the section.
            new_metrics: Optional updated metrics list.

        Returns:
            Updated memo dict (the new version).

        Raises:
            ValueError: If memo or section not found.
        """
        memo = self.load(company, product, memo_id)
        if memo is None:
            raise ValueError(f"Memo {memo_id} not found")

        # Find and update the section
        section_found = False
        for section in memo.get("sections", []):
            if section.get("key") == section_key:
                section["content"] = new_content
                if new_metrics is not None:
                    section["metrics"] = new_metrics
                section["generated_by"] = "manual_edit"
                section["edited_at"] = datetime.now(timezone.utc).isoformat()
                section_found = True
                break

        if not section_found:
            raise ValueError(
                f"Section '{section_key}' not found in memo {memo_id}"
            )

        # Save as new version
        self.save(memo)
        return memo

    def delete_memo(self, company: str, product: str,
                    memo_id: str) -> bool:
        """Delete a memo and all its versions.

        Only deletes memos in 'archived' status for safety.

        Returns:
            True if deleted, False if not found or not archived.
        """
        memo_dir = self._memo_dir(company, product, memo_id)
        meta = self._read_meta(memo_dir)

        if meta is None:
            return False

        if meta.get("status") != "archived":
            logger.warning(
                "Refusing to delete memo %s (status: %s). "
                "Archive it first.",
                memo_id, meta.get("status"),
            )
            return False

        import shutil
        try:
            shutil.rmtree(memo_dir)
            logger.info("Deleted memo %s at %s", memo_id, memo_dir)
            return True
        except OSError as e:
            logger.error("Failed to delete memo %s: %s", memo_id, e)
            return False
