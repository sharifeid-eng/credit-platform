"""
Bridge to notebooklm-py (v0.3+) for second-opinion research.

Supports two integration paths:
    1. Python import (``import notebooklm``) — preferred, in-process.
    2. CLI subprocess (``notebooklm`` command) — fallback if Python import
       fails but the CLI tool is installed.

Graceful degradation: if neither is available *or* authentication is missing,
``self.available = False`` and all query methods return empty results.

Notebook IDs and synced sources are persisted to a JSON sidecar file
per (company, product) so they survive restarts.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Root data directory — matches project convention
_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"


class NotebookLMEngine:
    """Bridge to NotebookLM for second-opinion research queries.

    Tries Python import first, falls back to CLI subprocess. If neither
    is available, ``self.available`` is ``False`` and all methods return
    gracefully degraded results.
    """

    def __init__(self):
        """Initialise the engine, probing for available integration paths."""
        self._python_module = None
        self._use_python = self._try_python_import()
        self._use_cli = self._check_cli_available() if not self._use_python else False
        self._authenticated = False

        # Check authentication if we have a library
        if self._use_python or self._use_cli:
            self._authenticated = self._check_auth()

        self.available = (self._use_python or self._use_cli) and self._authenticated

        # In-memory cache of notebook IDs: (company, product) -> notebook_id
        # Populated from disk on first access per company/product
        self._notebook_ids: dict[tuple[str, str], str] = {}
        # Tracks synced source IDs: (company, product) -> {doc_id: source_id}
        self._synced_sources: dict[tuple[str, str], dict[str, str]] = {}

        if self.available:
            method = "python" if self._use_python else "cli"
            logger.info("NotebookLMEngine: available via %s (authenticated)", method)
        elif self._use_python or self._use_cli:
            logger.warning(
                "NotebookLMEngine: library found but NOT authenticated. "
                "Run 'notebooklm login' or set NOTEBOOKLM_AUTH_JSON env var."
            )
        else:
            logger.info(
                "NotebookLMEngine: not available "
                "(neither notebooklm Python package nor CLI found)"
            )

    # ------------------------------------------------------------------
    # Health / status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return a diagnostic status dict for operator dashboards."""
        return {
            "library_installed": self._use_python or self._use_cli,
            "integration_method": "python" if self._use_python else ("cli" if self._use_cli else None),
            "authenticated": self._authenticated,
            "available": self.available,
            "notebooks_cached": len(self._notebook_ids),
        }

    # ------------------------------------------------------------------
    # Availability probing
    # ------------------------------------------------------------------

    def _try_python_import(self) -> bool:
        """Attempt to import the notebooklm Python package."""
        try:
            import notebooklm as nlm  # type: ignore[import-untyped]
            if hasattr(nlm, "NotebookLMClient") and hasattr(nlm, "AskResult"):
                self._python_module = nlm
                return True
            logger.debug(
                "NotebookLMEngine: notebooklm module imported but "
                "missing expected API (NotebookLMClient or AskResult)."
            )
            return False
        except ImportError:
            return False
        except Exception as exc:
            logger.debug("NotebookLMEngine: Python import error: %s", exc)
            return False

    def _check_cli_available(self) -> bool:
        """Check whether the ``notebooklm`` CLI command is available on PATH."""
        try:
            result = subprocess.run(
                ["notebooklm", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.debug(
                    "NotebookLMEngine: CLI available, version: %s",
                    result.stdout.strip()[:80],
                )
                return True
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        except Exception as exc:
            logger.debug("NotebookLMEngine: CLI check error: %s", exc)
            return False

    def _check_auth(self) -> bool:
        """Verify that NLM authentication is configured.

        Checks: NOTEBOOKLM_AUTH_JSON env var, or storage_state.json on disk.
        For the Python path, attempts a lightweight API call (list notebooks).
        For CLI, runs ``notebooklm auth check``.
        """
        # Env-var auth takes priority
        if os.environ.get("NOTEBOOKLM_AUTH_JSON"):
            logger.debug("NotebookLMEngine: NOTEBOOKLM_AUTH_JSON env var detected")
            return True

        if self._use_cli:
            try:
                result = subprocess.run(
                    ["notebooklm", "auth", "check"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    return True
                # auth check may not exist in all versions; try list as fallback
                result = subprocess.run(
                    ["notebooklm", "list"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return result.returncode == 0
            except Exception:
                return False

        if self._use_python:
            try:
                import asyncio
                import notebooklm as nlm

                async def _test():
                    client = await nlm.NotebookLMClient.from_storage()
                    async with client:
                        await client.notebooks.list()
                        return True

                return self._run_async(_test())
            except Exception as exc:
                logger.debug("NotebookLMEngine: auth check via Python failed: %s", exc)
                return False

        return False

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _sidecar_path(self, company: str, product: str) -> Path:
        """Path to the JSON sidecar that stores notebook ID + synced sources."""
        return _DATA_ROOT / company / product / "dataroom" / "notebooklm_state.json"

    def _load_state(self, company: str, product: str) -> dict:
        """Load persisted NLM state from disk."""
        path = self._sidecar_path(company, product)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("NotebookLMEngine: failed to read state %s: %s", path, exc)
        return {}

    def _save_state(self, company: str, product: str, state: dict) -> None:
        """Persist NLM state to disk."""
        path = self._sidecar_path(company, product)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(state, indent=2))
        except OSError as exc:
            logger.warning("NotebookLMEngine: failed to save state %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Notebook management
    # ------------------------------------------------------------------

    def ensure_notebook(self, company: str, product: str) -> Optional[str]:
        """Create or reuse a NotebookLM notebook for this company/product.

        Checks in-memory cache, then disk sidecar, then creates a new one.
        Validates that a cached notebook still exists on the NLM side.

        Returns:
            Notebook ID string, or None if creation failed.
        """
        cache_key = (company, product)

        # 1. In-memory cache
        if cache_key in self._notebook_ids:
            return self._notebook_ids[cache_key]

        if not self.available:
            return None

        # 2. Disk sidecar
        state = self._load_state(company, product)
        if state.get("notebook_id"):
            notebook_id = state["notebook_id"]
            # Validate it still exists
            if self._notebook_exists(notebook_id):
                self._notebook_ids[cache_key] = notebook_id
                # Also restore synced sources cache
                self._synced_sources[cache_key] = state.get("synced_sources", {})
                logger.info(
                    "NotebookLMEngine: restored notebook %s for %s/%s from disk",
                    notebook_id, company, product,
                )
                return notebook_id
            else:
                logger.warning(
                    "NotebookLMEngine: cached notebook %s no longer exists, creating new",
                    notebook_id,
                )

        # 3. Create new
        notebook_name = f"Laith — {company}/{product}"
        notebook_id = self._create_notebook(notebook_name)

        if notebook_id:
            self._notebook_ids[cache_key] = notebook_id
            self._synced_sources[cache_key] = {}
            # Persist
            self._save_state(company, product, {
                "notebook_id": notebook_id,
                "notebook_title": notebook_name,
                "synced_sources": {},
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            logger.info(
                "NotebookLMEngine: created notebook %s for %s/%s",
                notebook_id, company, product,
            )
            return notebook_id

        return None

    def _notebook_exists(self, notebook_id: str) -> bool:
        """Check if a notebook ID still exists on the NLM side."""
        try:
            if self._use_python:
                import asyncio
                import notebooklm as nlm

                async def _check():
                    client = await nlm.NotebookLMClient.from_storage()
                    async with client:
                        nb = await client.notebooks.get(notebook_id)
                        return nb is not None

                return self._run_async(_check())
            else:
                # CLI: try to list sources (lightweight check)
                result = subprocess.run(
                    ["notebooklm", "source", "list", "-n", notebook_id, "--json"],
                    capture_output=True, text=True, timeout=15,
                )
                return result.returncode == 0
        except Exception:
            return False

    def _create_notebook(self, title: str) -> Optional[str]:
        """Create a new notebook and return its ID."""
        try:
            if self._use_python:
                import asyncio
                import notebooklm as nlm

                async def _create():
                    client = await nlm.NotebookLMClient.from_storage()
                    async with client:
                        nb = await client.notebooks.create(title)
                        return nb.id

                return self._run_async(_create())
            else:
                result = subprocess.run(
                    ["notebooklm", "create", title, "--json"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        return data.get("id") or data.get("notebook_id", "").strip()
                    except json.JSONDecodeError:
                        # CLI may print just the ID
                        return result.stdout.strip() or None
                return None
        except Exception as exc:
            logger.warning("NotebookLMEngine: create notebook failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def sync_sources(
        self,
        company: str,
        product: str,
        documents: list[dict],
    ) -> dict:
        """Upload documents to the company notebook as NLM sources.

        Skips documents already synced (by doc_id). Waits for source
        processing to complete before returning.

        Args:
            company: Company slug.
            product: Product slug.
            documents: List of document dicts. Each should have:
                - ``doc_id``: unique identifier (for dedup tracking)
                - ``filepath``: path to file on disk, OR
                - ``text`` + ``title``: inline text content

        Returns:
            Dict with ``uploaded``, ``skipped``, ``errors``, ``notebook_id``.
        """
        result = {"uploaded": 0, "skipped": 0, "errors": [], "notebook_id": None}

        notebook_id = self.ensure_notebook(company, product)
        if not notebook_id:
            result["errors"].append("Could not create or find notebook")
            return result

        result["notebook_id"] = notebook_id
        cache_key = (company, product)
        synced = self._synced_sources.get(cache_key, {})

        for doc in documents:
            doc_id = doc.get("doc_id", doc.get("filename", ""))
            if not doc_id:
                result["errors"].append("Document missing doc_id/filename")
                continue

            # Skip already synced
            if doc_id in synced:
                result["skipped"] += 1
                continue

            filepath = doc.get("filepath")
            text = doc.get("text", "")
            title = doc.get("title", doc.get("filename", "document"))

            try:
                source_id = self._add_source(
                    notebook_id, filepath=filepath, text=text, title=title
                )
                if source_id:
                    synced[doc_id] = source_id
                    result["uploaded"] += 1
                else:
                    result["errors"].append(f"{title}: upload returned no source ID")
            except Exception as exc:
                result["errors"].append(f"{title}: {exc}")

        # Persist updated sync state
        self._synced_sources[cache_key] = synced
        state = self._load_state(company, product)
        state["synced_sources"] = synced
        state["last_sync"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._save_state(company, product, state)

        logger.info(
            "NotebookLMEngine: synced %d new, %d skipped, %d errors for %s/%s",
            result["uploaded"], result["skipped"], len(result["errors"]),
            company, product,
        )
        return result

    def _add_source(
        self,
        notebook_id: str,
        filepath: Optional[str] = None,
        text: str = "",
        title: str = "document",
    ) -> Optional[str]:
        """Add a single source to a notebook. Returns source ID or None."""
        if self._use_python:
            import asyncio
            import notebooklm as nlm

            async def _add():
                client = await nlm.NotebookLMClient.from_storage()
                async with client:
                    if filepath and Path(filepath).exists():
                        source = await client.sources.add_file(
                            notebook_id, filepath,
                            wait=True, wait_timeout=120.0,
                        )
                    elif text:
                        source = await client.sources.add_text(
                            notebook_id, title=title, content=text,
                            wait=True, wait_timeout=120.0,
                        )
                    else:
                        return None
                    return source.id if source else None

            return self._run_async(_add())
        else:
            # CLI fallback
            if filepath and Path(filepath).exists():
                cmd = [
                    "notebooklm", "source", "add",
                    str(filepath),
                    "-n", notebook_id,
                    "--type", "file",
                    "--json",
                ]
            elif text:
                cmd = [
                    "notebooklm", "source", "add",
                    text[:10000],
                    "-n", notebook_id,
                    "--type", "text",
                    "--title", title,
                    "--json",
                ]
            else:
                return None

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    return data.get("id", "").strip() or None
                except json.JSONDecodeError:
                    return result.stdout.strip() or None
            else:
                raise RuntimeError(
                    f"CLI source add failed (exit {result.returncode}): "
                    f"{result.stderr.strip()[:200]}"
                )

    def list_sources(self, notebook_id: str) -> list[dict]:
        """List all sources currently in a notebook.

        Returns list of dicts with id, title, kind, status.
        """
        if not self.available or not notebook_id:
            return []

        try:
            if self._use_python:
                import asyncio
                import notebooklm as nlm

                async def _list():
                    client = await nlm.NotebookLMClient.from_storage()
                    async with client:
                        sources = await client.sources.list(notebook_id)
                        return [
                            {
                                "id": s.id,
                                "title": s.title,
                                "kind": str(s.kind),
                                "is_ready": s.is_ready,
                                "is_processing": s.is_processing,
                                "is_error": s.is_error,
                            }
                            for s in sources
                        ]

                return self._run_async(_list())
            else:
                result = subprocess.run(
                    ["notebooklm", "source", "list", "-n", notebook_id, "--json"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    return json.loads(result.stdout) if result.stdout.strip() else []
                return []
        except Exception as exc:
            logger.warning("NotebookLMEngine: list sources failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Chat / query
    # ------------------------------------------------------------------

    def query(
        self,
        notebook_id: str,
        question: str,
        source_ids: Optional[list[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Ask a question against a company notebook.

        Args:
            notebook_id: The notebook to query.
            question: Natural-language question.
            source_ids: Optional list of source IDs to scope the query to.
            conversation_id: Optional conversation ID for follow-ups.

        Returns:
            Dict with ``answer``, ``references``, ``conversation_id``,
            ``turn_number``, ``engine``, ``available``.
        """
        if not self.available or not notebook_id:
            return {
                "answer": "",
                "references": [],
                "conversation_id": None,
                "turn_number": 0,
                "engine": "notebooklm",
                "available": False,
            }

        try:
            if self._use_python:
                return self._query_python(notebook_id, question, source_ids, conversation_id)
            else:
                return self._query_cli(notebook_id, question, source_ids)
        except Exception as exc:
            logger.warning("NotebookLMEngine: query failed: %s", exc)
            return {
                "answer": "",
                "references": [],
                "conversation_id": None,
                "turn_number": 0,
                "engine": "notebooklm",
                "available": True,
                "error": str(exc),
            }

    def _query_python(
        self,
        notebook_id: str,
        question: str,
        source_ids: Optional[list[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """Execute a query via the Python API. Returns structured result."""
        import asyncio
        import notebooklm as nlm

        async def _ask():
            client = await nlm.NotebookLMClient.from_storage()
            async with client:
                ask_result: nlm.AskResult = await client.chat.ask(
                    notebook_id,
                    question,
                    source_ids=source_ids,
                    conversation_id=conversation_id,
                )
                return ask_result

        ask_result = self._run_async(_ask())

        # Convert ChatReference objects to serialisable dicts
        references = []
        for ref in (ask_result.references or []):
            references.append({
                "source_id": ref.source_id,
                "citation_number": ref.citation_number,
                "cited_text": ref.cited_text or "",
                "start_char": ref.start_char,
                "end_char": ref.end_char,
                "chunk_id": ref.chunk_id,
            })

        return {
            "answer": ask_result.answer or "",
            "references": references,
            "conversation_id": ask_result.conversation_id,
            "turn_number": ask_result.turn_number,
            "engine": "notebooklm",
            "available": True,
        }

    def _query_cli(
        self,
        notebook_id: str,
        question: str,
        source_ids: Optional[list[str]] = None,
    ) -> dict:
        """Execute a query via the CLI. Returns structured result."""
        cmd = [
            "notebooklm", "ask", question,
            "-n", notebook_id,
            "--json",
        ]
        if source_ids:
            for sid in source_ids:
                cmd.extend(["-s", sid])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            raise RuntimeError(
                f"CLI ask failed (exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            # Plain text answer
            return {
                "answer": result.stdout.strip(),
                "references": [],
                "conversation_id": None,
                "turn_number": 0,
                "engine": "notebooklm",
                "available": True,
            }

        # CLI --json returns structured data
        answer = data.get("answer", data.get("response", result.stdout.strip()))
        references = []
        for ref in data.get("references", data.get("citations", [])):
            if isinstance(ref, dict):
                references.append({
                    "source_id": ref.get("source_id", ""),
                    "citation_number": ref.get("citation_number"),
                    "cited_text": ref.get("cited_text", ref.get("text", "")),
                    "start_char": ref.get("start_char"),
                    "end_char": ref.get("end_char"),
                    "chunk_id": ref.get("chunk_id"),
                })

        return {
            "answer": answer,
            "references": references,
            "conversation_id": data.get("conversation_id"),
            "turn_number": data.get("turn_number", 0),
            "engine": "notebooklm",
            "available": True,
        }

    # ------------------------------------------------------------------
    # Research (web/deep research)
    # ------------------------------------------------------------------

    def start_research(
        self,
        notebook_id: str,
        query: str,
        source: str = "web",
        mode: str = "fast",
    ) -> Optional[dict]:
        """Start a research session (web crawl + source import).

        Args:
            notebook_id: Target notebook.
            query: Research topic.
            source: "web" or "drive".
            mode: "fast" or "deep".

        Returns:
            Research task info dict, or None on failure.
        """
        if not self.available or not notebook_id:
            return None

        try:
            if self._use_python:
                import asyncio
                import notebooklm as nlm

                async def _research():
                    client = await nlm.NotebookLMClient.from_storage()
                    async with client:
                        return await client.research.start(
                            notebook_id, query, source=source, mode=mode,
                        )

                return self._run_async(_research())
            else:
                cmd = [
                    "notebooklm", "source", "add-research", query,
                    "-n", notebook_id,
                    "--mode", mode,
                    "--no-wait",
                    "--json",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    try:
                        return json.loads(result.stdout)
                    except json.JSONDecodeError:
                        return {"status": "started", "raw": result.stdout.strip()}
                return None
        except Exception as exc:
            logger.warning("NotebookLMEngine: start_research failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Chat configuration
    # ------------------------------------------------------------------

    def configure_chat(
        self,
        notebook_id: str,
        custom_prompt: Optional[str] = None,
    ) -> bool:
        """Configure the chat persona for a notebook.

        Sets a custom system prompt so NLM answers in the style of a
        senior credit analyst aligned with the Laith platform conventions.
        """
        if not self.available or not notebook_id:
            return False

        prompt = custom_prompt or (
            "You are a senior credit analyst for a private credit fund. "
            "Answer questions with precision, citing specific numbers and dates. "
            "Flag any data quality concerns. Use professional IC-memo style prose."
        )

        try:
            if self._use_python:
                import asyncio
                import notebooklm as nlm

                async def _configure():
                    client = await nlm.NotebookLMClient.from_storage()
                    async with client:
                        await client.chat.configure(
                            notebook_id, custom_prompt=prompt,
                        )
                        return True

                return self._run_async(_configure())
            else:
                result = subprocess.run(
                    ["notebooklm", "configure",
                     "-n", notebook_id,
                     "--custom-prompt", prompt],
                    capture_output=True, text=True, timeout=15,
                )
                return result.returncode == 0
        except Exception as exc:
            logger.warning("NotebookLMEngine: configure_chat failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Async helper
    # ------------------------------------------------------------------

    @staticmethod
    def _run_async(coro) -> Any:
        """Run an async coroutine from sync code.

        Handles the case where an event loop is already running (e.g.
        inside a FastAPI endpoint served by uvicorn) by spawning a
        thread with its own event loop.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Already in an async context — run in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=180)
        else:
            return asyncio.run(coro)
