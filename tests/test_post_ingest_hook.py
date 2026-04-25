"""Regression tests for the generic post-ingest hook (deploy.sh) and the
Tamara-specific implementation (data/Tamara/dataroom/.post-ingest.sh).

Background — the session-38 footgun:
After session-37's `needs-ingest` subcommand landed, deploy.sh correctly
re-ingests datarooms when new source files arrive. But for Tamara
specifically, dataroom_ctl ingest only refreshes the search index — it does
NOT run the structured parser (`scripts/ingest_tamara_investor_pack.py`)
that produces `data/Tamara/investor_packs/YYYY-MM-DD_investor_pack.json`
which the Quarterly Financials dashboard tab depends on. Analysts had to
remember a manual prod step after every sync+deploy.

This test file pins the contract for two layers:

1. Generic hook in deploy.sh — runs `data/{co}/dataroom/.post-ingest.sh`
   when present, after a successful `dataroom_ctl ingest`. Failures
   logged but never fail the deploy.
2. Tamara-specific hook — finds the newest investor pack file (covers
   both quarterly "Investor Pack" and monthly "Investor Reporting"
   filename conventions) and invokes the parser inside the backend
   container with --force.

Bash regressions are silent killers (a typo in the hook block could
disable post-ingest processing for every company), so we also pin
`bash -n` syntax checks on both shell files.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_SH = REPO_ROOT / "deploy.sh"
TAMARA_HOOK = REPO_ROOT / "data" / "Tamara" / "dataroom" / ".post-ingest.sh"

# Inline mirror of the deploy.sh hook block — pinned by
# `test_deploy_sh_contains_hook_block` so divergence between the inline
# snippet and the real deploy.sh fails CI immediately. The inline snippet
# stays minimal (just the hook block, not the surrounding loop or the
# docker exec calls) so tests can run on any host without docker.
DEPLOY_HOOK_RUNNER = r"""#!/bin/bash
# Mirror of deploy.sh hook block. Receives company name as $1.
# Tests should keep this snippet byte-for-byte aligned with deploy.sh.
set -e
company="$1"
hook="data/${company}/dataroom/.post-ingest.sh"
if [ -f "$hook" ]; then
    echo "  ${company}: running post-ingest hook ($hook)..."
    bash "$hook" || echo "    Hook failed (exit=$?)"
fi
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _bash() -> str:
    """Locate bash. On Windows we rely on Git Bash being on PATH."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not on PATH (required for shell-script tests)")
    return bash


def _write_executable(path: Path, content: str) -> None:
    """Write a bash script. We do not chmod +x — deploy.sh invokes hooks
    via `bash "$hook"` precisely so the executable bit isn't required
    (Windows clones don't reliably preserve it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _run(cmd: list, cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing both streams. Never raises on non-zero
    exit — tests assert on .returncode explicitly."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
    )


# ── Generic hook in deploy.sh ────────────────────────────────────────────────


class TestDeployHookBlock:
    """The generic hook in deploy.sh runs `data/{co}/dataroom/.post-ingest.sh`
    after ingest, but never fails the deploy."""

    def test_runs_hook_when_present(self, tmp_path: Path):
        """Hook present → bash runs it. Sentinel file confirms execution."""
        bash = _bash()

        # Stage a fake dataroom layout under tmp_path so the relative
        # `data/{co}/dataroom/.post-ingest.sh` lookup resolves.
        sentinel = tmp_path / "sentinel.touched"
        hook_path = tmp_path / "data" / "testco" / "dataroom" / ".post-ingest.sh"
        # Use absolute sentinel path so the cwd doesn't matter at hook-run time.
        _write_executable(
            hook_path,
            f"#!/bin/bash\nset -e\ntouch '{sentinel.as_posix()}'\n",
        )

        runner = tmp_path / "runner.sh"
        _write_executable(runner, DEPLOY_HOOK_RUNNER)

        result = _run([bash, str(runner), "testco"], cwd=tmp_path)

        assert result.returncode == 0, (
            f"hook wrapper must exit 0 (got {result.returncode}); "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert sentinel.exists(), "hook script must have run and created the sentinel"
        assert "running post-ingest hook" in result.stdout

    def test_skips_hook_when_absent(self, tmp_path: Path):
        """No hook file → wrapper exits 0 silently, no work happens."""
        bash = _bash()

        # Note: dataroom dir exists but `.post-ingest.sh` does NOT.
        (tmp_path / "data" / "testco" / "dataroom").mkdir(parents=True)
        sentinel = tmp_path / "sentinel.never"

        runner = tmp_path / "runner.sh"
        _write_executable(runner, DEPLOY_HOOK_RUNNER)

        result = _run([bash, str(runner), "testco"], cwd=tmp_path)

        assert result.returncode == 0
        assert not sentinel.exists()
        # Should NOT log the running message when there's no hook.
        assert "running post-ingest hook" not in result.stdout

    def test_continues_when_hook_fails(self, tmp_path: Path):
        """Hook exits 1 → wrapper still exits 0 (deploy must not fail)."""
        bash = _bash()

        hook_path = tmp_path / "data" / "testco" / "dataroom" / ".post-ingest.sh"
        _write_executable(
            hook_path,
            "#!/bin/bash\necho 'simulated failure'\nexit 1\n",
        )

        runner = tmp_path / "runner.sh"
        _write_executable(runner, DEPLOY_HOOK_RUNNER)

        result = _run([bash, str(runner), "testco"], cwd=tmp_path)

        # The whole point of this test: hook failure must NOT abort deploy.
        assert result.returncode == 0, (
            f"wrapper must exit 0 even when hook fails (got {result.returncode})"
        )
        assert "Hook failed" in result.stdout, (
            "wrapper must log 'Hook failed (exit=...)' so analysts see the failure"
        )

    def test_deploy_sh_contains_hook_block(self):
        """The inline DEPLOY_HOOK_RUNNER must stay aligned with deploy.sh.
        We assert key substrings — full byte-for-byte match would be too
        brittle (deploy.sh has surrounding loop + docker exec calls), but
        the core hook semantics must be present verbatim."""
        # Explicit utf-8 — deploy.sh contains em-dashes in comments and
        # the default cp1252 decode chokes on them on Windows.
        deploy_text = DEPLOY_SH.read_text(encoding="utf-8")

        # The hook lookup pattern. If anyone refactors deploy.sh and
        # accidentally drops this, every company's post-ingest hook
        # silently stops firing — same class of bug as the gitignored-
        # registry collision (session 26.1).
        assert 'hook="data/${company}/dataroom/.post-ingest.sh"' in deploy_text
        assert '[ -f "$hook" ]' in deploy_text
        assert 'bash "$hook" || echo "    Hook failed (exit=$?)"' in deploy_text


# ── Tamara-specific hook ─────────────────────────────────────────────────────


class TestTamaraHook:
    """The Tamara hook locates the newest investor pack and invokes the
    structured parser. Tests use LAITH_HOOK_DRY_RUN=1 to skip the
    `docker compose exec` call so they don't depend on docker."""

    def test_finds_latest_pack_by_mtime(self, tmp_path: Path):
        """Three packs with staggered mtimes → newest one is selected.
        This is the core Tamara use case: when an analyst drops a fresh
        investor pack into the Management Financials folder, the hook
        must always pick THAT file, not an older sibling."""
        bash = _bash()

        search_dir = tmp_path / "Financials" / "54.2.2 Management Financials"
        search_dir.mkdir(parents=True)

        # Three fake pack files with explicit mtime ordering. We use
        # os.utime rather than `touch -d` because the latter's date
        # parsing varies between coreutils versions.
        old_pack = search_dir / "old_Investor_Pack.xlsx"
        mid_pack = search_dir / "mid_Investor_Reporting.xlsx"
        new_pack = search_dir / "new_Investor_Pack.xlsx"
        for f in (old_pack, mid_pack, new_pack):
            f.write_bytes(b"PK\x03\x04 fake xlsx")  # marker bytes are fine
        now = time.time()
        os.utime(old_pack, (now - 7200, now - 7200))
        os.utime(mid_pack, (now - 3600, now - 3600))
        os.utime(new_pack, (now, now))

        result = _run(
            [bash, str(TAMARA_HOOK)],
            cwd=tmp_path,
            env={
                "LAITH_TAMARA_SEARCH_DIR": str(search_dir),
                "LAITH_HOOK_DRY_RUN": "1",
            },
        )

        assert result.returncode == 0, (
            f"dry-run hook must exit 0; stderr={result.stderr!r}"
        )
        # Hook prints `parsing <basename>` then `DRY RUN — would invoke parser on <full path>`.
        assert "new_Investor_Pack.xlsx" in result.stdout, (
            f"newest pack must be selected; stdout={result.stdout!r}"
        )
        assert "DRY RUN" in result.stdout
        # Older files must NOT be the chosen one. (They might appear in
        # the search dir listing but not in the "parsing" line.)
        assert "parsing old_Investor_Pack.xlsx" not in result.stdout
        assert "parsing mid_Investor_Reporting.xlsx" not in result.stdout

    def test_no_op_when_no_packs(self, tmp_path: Path):
        """Search dir exists but has no matching pack files → exit 0
        with the expected skip message. This covers fresh installs
        where Tamara hasn't delivered any packs yet."""
        bash = _bash()

        search_dir = tmp_path / "empty_search_dir"
        search_dir.mkdir()
        # Add a file that should NOT match the pattern, to verify the
        # iname filter is doing its job.
        (search_dir / "unrelated.csv").write_text("col,v\nfoo,1\n")

        result = _run(
            [bash, str(TAMARA_HOOK)],
            cwd=tmp_path,
            env={"LAITH_TAMARA_SEARCH_DIR": str(search_dir)},
        )

        assert result.returncode == 0
        assert "no investor packs found" in result.stdout
        assert "DRY RUN" not in result.stdout
        assert "parsing" not in result.stdout

    def test_no_op_when_search_dir_missing(self, tmp_path: Path):
        """Search dir doesn't exist at all → exit 0 with skip message.
        Defensive: guards against analyst pointing the env var at a
        bad path during a test run."""
        bash = _bash()

        result = _run(
            [bash, str(TAMARA_HOOK)],
            cwd=tmp_path,
            env={"LAITH_TAMARA_SEARCH_DIR": str(tmp_path / "does_not_exist")},
        )

        assert result.returncode == 0
        assert "search dir not present" in result.stdout


# ── Syntax checks ────────────────────────────────────────────────────────────


class TestShellSyntax:
    """`bash -n` parses without executing — catches syntax errors before
    they hit prod. Both deploy.sh and the Tamara hook must be valid bash."""

    def test_deploy_sh_syntax_valid(self):
        bash = _bash()
        result = subprocess.run(
            [bash, "-n", str(DEPLOY_SH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"deploy.sh has bash syntax errors:\n{result.stderr}"
        )

    def test_tamara_hook_syntax_valid(self):
        bash = _bash()
        assert TAMARA_HOOK.exists(), (
            f"Tamara hook script must be tracked at {TAMARA_HOOK} — "
            "check .gitignore re-include rule"
        )
        result = subprocess.run(
            [bash, "-n", str(TAMARA_HOOK)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Tamara hook has bash syntax errors:\n{result.stderr}"
        )
