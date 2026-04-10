"""
Bridge to notebooklm-py for second-opinion research.

Supports two integration paths:
    1. Python import (``import notebooklm``) — preferred, in-process.
    2. CLI subprocess (``notebooklm`` command) — fallback if Python import
       fails but the CLI tool is installed.

Graceful degradation: if neither is available, ``self.available = False``
and all query methods return empty results without raising.

Notebook IDs are cached per (company, product) to avoid creating duplicates.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
        self.available = self._use_python or self._use_cli

        # Cache of notebook IDs: (company, product) -> notebook_id
        self._notebook_ids: dict[tuple[str, str], str] = {}

        if self.available:
            method = "python" if self._use_python else "cli"
            logger.info("NotebookLMEngine: available via %s", method)
        else:
            logger.info(
                "NotebookLMEngine: not available "
                "(neither notebooklm Python package nor CLI found)"
            )

    # ------------------------------------------------------------------
    # Availability probing
    # ------------------------------------------------------------------

    def _try_python_import(self) -> bool:
        """Attempt to import the notebooklm Python package.

        Returns True if the import succeeds and the module exposes the
        expected interface.
        """
        try:
            import notebooklm as nlm  # type: ignore[import-untyped]
            # Verify minimum API surface
            if hasattr(nlm, "NotebookLMClient") or hasattr(nlm, "query"):
                self._python_module = nlm
                return True
            logger.debug(
                "NotebookLMEngine: notebooklm module imported but "
                "missing expected API (NotebookLMClient or query)."
            )
            return False
        except ImportError:
            return False
        except Exception as exc:
            logger.debug("NotebookLMEngine: Python import error: %s", exc)
            return False

    def _check_cli_available(self) -> bool:
        """Check whether the ``notebooklm`` CLI command is available on PATH.

        Returns True if the command exists and returns a zero or known
        exit code.
        """
        try:
            result = subprocess.run(
                ["notebooklm", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Accept exit code 0 (success) or 1 (some CLIs use 1 for --version)
            if result.returncode in (0, 1):
                logger.debug(
                    "NotebookLMEngine: CLI available, version output: %s",
                    result.stdout.strip()[:80],
                )
                return True
            return False
        except FileNotFoundError:
            return False
        except subprocess.TimeoutExpired:
            return False
        except Exception as exc:
            logger.debug("NotebookLMEngine: CLI check error: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Notebook management
    # ------------------------------------------------------------------

    def ensure_notebook(self, company: str, product: str) -> Optional[str]:
        """Create or reuse a NotebookLM notebook for this company/product.

        Notebook IDs are cached in memory for the lifetime of this engine
        instance.

        Args:
            company: Company slug.
            product: Product slug.

        Returns:
            Notebook ID string, or None if creation failed.
        """
        cache_key = (company, product)
        if cache_key in self._notebook_ids:
            return self._notebook_ids[cache_key]

        if not self.available:
            return None

        notebook_name = f"Laith — {company}/{product}"

        try:
            if self._use_python:
                notebook_id = self._run_python("create_notebook", notebook_name)
            else:
                notebook_id = self._run_cli("create", "--name", notebook_name)

            if notebook_id:
                notebook_id = str(notebook_id).strip()
                self._notebook_ids[cache_key] = notebook_id
                logger.info(
                    "NotebookLMEngine: created notebook %s for %s/%s",
                    notebook_id,
                    company,
                    product,
                )
                return notebook_id
        except Exception as exc:
            logger.warning(
                "NotebookLMEngine: failed to create notebook for %s/%s: %s",
                company,
                product,
                exc,
            )

        return None

    def sync_sources(
        self,
        company: str,
        product: str,
        documents: list[dict],
    ) -> dict:
        """Upload documents to the company notebook.

        Takes a list of document dicts (with at minimum ``filepath`` or
        ``text`` and ``filename`` keys) and uploads them as sources to
        the NotebookLM notebook.

        Args:
            company: Company slug.
            product: Product slug.
            documents: List of document dicts. Each must have either
                ``filepath`` (path to file on disk) or ``text`` + ``filename``.

        Returns:
            Dict with ``uploaded`` count, ``errors`` list, ``notebook_id``.
        """
        result = {"uploaded": 0, "errors": [], "notebook_id": None}

        notebook_id = self.ensure_notebook(company, product)
        if not notebook_id:
            result["errors"].append("Could not create or find notebook")
            return result

        result["notebook_id"] = notebook_id

        for doc in documents:
            filepath = doc.get("filepath")
            text = doc.get("text", "")
            filename = doc.get("filename", "document")

            try:
                if filepath and Path(filepath).exists():
                    if self._use_python:
                        self._run_python(
                            "add_source_file", notebook_id, str(filepath)
                        )
                    else:
                        self._run_cli(
                            "add-source", "--notebook", notebook_id,
                            "--file", str(filepath),
                        )
                elif text:
                    if self._use_python:
                        self._run_python(
                            "add_source_text", notebook_id, text, filename
                        )
                    else:
                        self._run_cli(
                            "add-source", "--notebook", notebook_id,
                            "--text", text[:10000],  # CLI may have limits
                            "--name", filename,
                        )
                else:
                    result["errors"].append(
                        f"No filepath or text for document: {filename}"
                    )
                    continue

                result["uploaded"] += 1

            except Exception as exc:
                result["errors"].append(f"{filename}: {exc}")

        logger.info(
            "NotebookLMEngine: synced %d/%d sources to notebook %s",
            result["uploaded"],
            len(documents),
            notebook_id,
        )
        return result

    def query(self, notebook_id: str, question: str) -> dict:
        """Run a query against a company notebook.

        Args:
            notebook_id: The notebook to query.
            question: Natural-language question.

        Returns:
            Dict with ``answer``, ``sources`` list, and ``engine`` key.
            Returns empty/error result if NLM is unavailable.
        """
        if not self.available or not notebook_id:
            return {
                "answer": "",
                "sources": [],
                "engine": "notebooklm",
                "available": False,
            }

        try:
            if self._use_python:
                raw = self._run_python("query", notebook_id, question)
            else:
                raw = self._run_cli(
                    "query",
                    "--notebook", notebook_id,
                    "--question", question,
                )

            # Parse the response
            answer, sources = self._parse_nlm_response(raw)

            return {
                "answer": answer,
                "sources": sources,
                "engine": "notebooklm",
                "available": True,
            }

        except Exception as exc:
            logger.warning("NotebookLMEngine: query failed: %s", exc)
            return {
                "answer": "",
                "sources": [],
                "engine": "notebooklm",
                "available": True,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Internal: Python API
    # ------------------------------------------------------------------

    def _run_python(self, method: str, *args) -> Any:
        """Call an async method on the notebooklm Python client.

        Uses asyncio.run() to bridge sync→async since the notebooklm-py
        library uses an async client with ``async with`` context manager.

        Args:
            method: Method name (e.g. ``"create_notebook"``, ``"query"``).
            *args: Positional arguments to pass.

        Returns:
            The return value from the Python API.

        Raises:
            RuntimeError: If the Python module is not loaded.
        """
        import asyncio

        if self._python_module is None:
            raise RuntimeError("notebooklm Python module not loaded")

        nlm = self._python_module

        async def _execute():
            client = await nlm.NotebookLMClient.from_storage()
            async with client:
                if method == "create_notebook":
                    nb = await client.notebooks.create(title=args[0])
                    return nb.id if hasattr(nb, 'id') else str(nb)
                elif method == "list_notebooks":
                    return await client.notebooks.list()
                elif method == "add_source_file":
                    notebook_id, filepath = args[0], args[1]
                    return await client.sources.add(
                        notebook_id=notebook_id, file_path=filepath
                    )
                elif method == "add_source_text":
                    notebook_id, text = args[0], args[1]
                    title = args[2] if len(args) > 2 else "document"
                    return await client.sources.add(
                        notebook_id=notebook_id, text=text, title=title
                    )
                elif method == "query":
                    notebook_id, question = args[0], args[1]
                    result = await client.chat.send(
                        notebook_id=notebook_id, message=question
                    )
                    return result
                else:
                    raise AttributeError(
                        f"Unknown method: {method}"
                    )

        # Handle case where event loop is already running
        try:
            loop = asyncio.get_running_loop()
            # Already in async context — use nest_asyncio or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, _execute()).result(timeout=60)
        except RuntimeError:
            # No running loop — safe to use asyncio.run()
            return asyncio.run(_execute())

    # ------------------------------------------------------------------
    # Internal: CLI fallback
    # ------------------------------------------------------------------

    def _run_cli(self, *args) -> str:
        """Run a notebooklm CLI command via subprocess.

        Args:
            *args: Arguments to pass after ``notebooklm``.

        Returns:
            Stripped stdout output.

        Raises:
            subprocess.CalledProcessError: If the command fails.
            subprocess.TimeoutExpired: If the command takes too long.
        """
        cmd = ["notebooklm"] + [str(a) for a in args]
        logger.debug("NotebookLMEngine CLI: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()[:200]
            raise subprocess.CalledProcessError(
                result.returncode,
                cmd,
                output=result.stdout,
                stderr=result.stderr,
            )

        return result.stdout.strip()

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_nlm_response(self, raw: Any) -> tuple[str, list[dict]]:
        """Parse a raw NotebookLM response into (answer, sources).

        Handles multiple response formats: plain string, JSON string,
        dict with ``answer``/``response`` key, or object with attributes.

        Args:
            raw: The raw response from NLM (string, dict, or object).

        Returns:
            Tuple of (answer_text, list_of_source_dicts).
        """
        if raw is None:
            return ("", [])

        # If it's a string, try JSON parsing
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    raw = parsed
                else:
                    return (raw, [])
            except (json.JSONDecodeError, ValueError):
                return (raw, [])

        # If it's a dict
        if isinstance(raw, dict):
            answer = raw.get("answer") or raw.get("response") or raw.get("text", "")
            sources = raw.get("sources") or raw.get("citations") or []
            return (str(answer), sources if isinstance(sources, list) else [])

        # If it's an object with attributes
        answer = getattr(raw, "answer", None) or getattr(raw, "response", None) or ""
        sources = getattr(raw, "sources", None) or getattr(raw, "citations", None) or []
        return (str(answer), sources if isinstance(sources, list) else [])
