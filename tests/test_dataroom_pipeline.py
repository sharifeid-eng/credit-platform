"""Regression tests for the DataRoom ingestion pipeline.

Covers the three classes of bugs fixed on 2026-04-20 that caused the Klaim
data room to display 153 documents when it really had 76:

1. Engine self-pollution — `_is_supported` must skip dotfiles and
   engine-written state files (`.classification_cache.json`, `meta.json`,
   `ingest_log.jsonl`, etc.) so the engine never ingests files it creates
   inside the walked source dir.

2. Within-pass hash dedup — `existing_hashes` / `registry_hashes` must be
   updated after every successful `_ingest_single_file()` so two files
   with identical bytes at different folder paths don't both become
   registry entries in the same ingest/refresh pass.

3. Refresh filepath relink — when a refresh sees a known hash at a new
   path AND the registered filepath is no longer on disk, update the
   registry entry's filepath to the disk path. Otherwise the removal
   sweep drops the entry AND the disk file never gets re-ingested =
   silent data loss (what happened to 55 Klaim docs after the nested
   `dataroom/dataroom/` was deleted).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from core.dataroom.engine import DataRoomEngine, _EXCLUDE_FILENAMES, _is_supported


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_engine(tmp: Path) -> tuple[DataRoomEngine, Path]:
    """Spin up a throwaway engine rooted at a temp data dir."""
    data_root = tmp / "data"
    (data_root / "testco" / "dataroom").mkdir(parents=True)
    return DataRoomEngine(data_root=str(data_root)), data_root


def _write_csv(path: Path, content: str = "name,value\nfoo,1\nbar,2\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ── Fix 1: self-pollution via engine-written files ───────────────────────────


class TestExclusions:
    """Engine-written files and dotfiles must never be ingested."""

    def test_dotfile_rejected_by_is_supported(self):
        # `.classification_cache.json` — written by classifier_llm, lives
        # inside data/{co}/dataroom/ so the walk finds it.
        assert not _is_supported("/x/dataroom/.classification_cache.json")
        assert not _is_supported("/x/dataroom/.hidden.pdf")

    def test_meta_json_rejected(self):
        # `meta.json` — engine's index_status sidecar.
        assert not _is_supported("/x/dataroom/meta.json")

    def test_named_exclusions_all_rejected(self):
        # Every filename in _EXCLUDE_FILENAMES must be skipped.
        for fname in _EXCLUDE_FILENAMES:
            assert not _is_supported(f"/x/dataroom/{fname}"), (
                f"{fname} should be in exclusion list but _is_supported accepted it"
            )

    def test_real_docs_still_pass(self):
        assert _is_supported("/x/dataroom/deal/ESOP.pdf")
        assert _is_supported("/x/dataroom/financials/model.xlsx")
        assert _is_supported("/x/dataroom/cohort.csv")

    def test_ingest_skips_cache_file(self, tmp_path):
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        _write_csv(dr / "real.csv")
        (dr / ".classification_cache.json").write_text("{}")
        (dr / "meta.json").write_text('{"index_status":"ok"}')

        result = engine.ingest("testco", "", str(dr))

        # Only real.csv is a supported file; cache + meta are excluded by walker.
        assert result["total_files"] == 1
        assert result["ingested"] == 1
        reg = engine._load_registry("testco", "")
        assert len(reg) == 1
        assert list(reg.values())[0]["filename"] == "real.csv"


# ── Fix 2: within-pass hash dedup ────────────────────────────────────────────


class TestWithinPassHashDedup:
    """Same file bytes at different paths → one registry entry per pass."""

    def test_ingest_dedups_same_bytes_at_two_paths(self, tmp_path):
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        payload = "name,value\nfoo,1\nbar,2\nbaz,3\n"
        _write_csv(dr / "Company Overview" / "ESOP.csv", payload)
        _write_csv(dr / "US Opportunity" / "ESOP.csv", payload)

        result = engine.ingest("testco", "", str(dr))

        assert result["total_files"] == 2
        assert result["ingested"] == 1
        assert result["duplicates_skipped"] == 1
        assert len(engine._load_registry("testco", "")) == 1

    def test_refresh_dedups_same_bytes_at_two_paths(self, tmp_path):
        """Refresh on a fresh registry must also hash-dedup same-bytes pairs."""
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        payload = "col,v\na,1\nb,2\n"
        _write_csv(dr / "path_A" / "same.csv", payload)
        _write_csv(dr / "path_B" / "same.csv", payload)

        result = engine.refresh("testco", "", str(dr))

        # Without within-pass dedup in refresh, both would be 'added'.
        assert result["added"] == 1
        assert result["duplicates_skipped"] == 1
        assert len(engine._load_registry("testco", "")) == 1


# ── Fix 3: refresh filepath relink (today's silent-data-loss bug) ────────────


class TestRefreshRelink:
    """When the registered filepath is gone but hash is found at a NEW
    path, the entry must be relinked — not skipped-then-removed.

    This is exactly what bit 55 Klaim docs after the nested
    `dataroom/dataroom/` directory was deleted: registry entries pointed
    into the deleted tree, the files were still present at the parent
    path, and the buggy refresh dedup-skipped them then the removal
    sweep dropped the entries. Net: 55 disk files unreferenced, 55
    entries gone."""

    def test_moved_file_is_relinked_not_dropped(self, tmp_path):
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        _write_csv(dr / "old_location" / "moved.csv")

        # Initial ingest registers the file at old_location.
        engine.ingest("testco", "", str(dr))
        reg = engine._load_registry("testco", "")
        assert len(reg) == 1
        old_id = next(iter(reg))
        assert "old_location" in reg[old_id]["filepath"]

        # Simulate a user reorganizing the dataroom: move the file to a new
        # folder without changing the bytes.
        old = dr / "old_location" / "moved.csv"
        new_dir = dr / "new_location"
        new_dir.mkdir()
        new = new_dir / "moved.csv"
        new.write_bytes(old.read_bytes())
        old.unlink()
        (dr / "old_location").rmdir()

        result = engine.refresh("testco", "", str(dr))

        # Entry must be relinked to the new path, not dropped + re-added.
        assert result["relinked"] == 1
        assert result["added"] == 0
        assert result["removed"] == 0

        reg_after = engine._load_registry("testco", "")
        assert len(reg_after) == 1, "relinked entry must survive"
        assert old_id in reg_after, "same doc_id, not a new ingest"
        assert "new_location" in reg_after[old_id]["filepath"]

    def test_genuine_duplicate_still_dedup_skipped(self, tmp_path):
        """If the registered filepath IS still on disk and another copy
        shows up elsewhere, that second copy is a genuine duplicate — skip
        it (don't relink, don't ingest)."""
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        payload = "a,b\n1,2\n"
        _write_csv(dr / "original" / "file.csv", payload)

        engine.ingest("testco", "", str(dr))

        # Add a second copy at another path; original stays in place.
        _write_csv(dr / "copy" / "file.csv", payload)

        result = engine.refresh("testco", "", str(dr))

        assert result["duplicates_skipped"] == 1
        assert result["relinked"] == 0
        assert result["removed"] == 0
        assert len(engine._load_registry("testco", "")) == 1


# ── dedupe_registry healing path (for pre-existing bad state) ────────────────


class TestDedupeRegistry:
    """`dedupe_registry()` heals registries that accumulated duplicates
    before the within-pass dedup fix was in place."""

    def test_collapses_sha_duplicates_keeping_earliest(self, tmp_path):
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        (dr / "chunks").mkdir()

        registry = {
            "aaa": {"doc_id": "aaa", "filename": "E.pdf", "sha256": "h1",
                    "ingested_at": "2026-01-01T00:00:00"},
            "bbb": {"doc_id": "bbb", "filename": "E.pdf", "sha256": "h1",
                    "ingested_at": "2026-02-01T00:00:00"},
            "ccc": {"doc_id": "ccc", "filename": "other.pdf", "sha256": "h2",
                    "ingested_at": "2026-01-15T00:00:00"},
        }
        (dr / "registry.json").write_text(json.dumps(registry))
        for did in registry:
            (dr / "chunks" / f"{did}.json").write_text("[]")

        result = engine.dedupe_registry("testco", "")

        assert result["sha_duplicates_removed"] == 1
        assert result["kept"] == 2
        reg_after = json.loads((dr / "registry.json").read_text())
        # aaa (earlier) wins over bbb.
        assert set(reg_after.keys()) == {"aaa", "ccc"}
        # Loser's chunks file also deleted.
        assert not (dr / "chunks" / "bbb.json").exists()

    def test_evicts_excluded_filename_entries(self, tmp_path):
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        (dr / "chunks").mkdir()

        registry = {
            "a": {"doc_id": "a", "filename": ".classification_cache.json",
                  "sha256": "h1", "ingested_at": "2026-01-01T00:00:00"},
            "b": {"doc_id": "b", "filename": "meta.json",
                  "sha256": "h2", "ingested_at": "2026-01-01T00:00:00"},
            "c": {"doc_id": "c", "filename": "real.pdf",
                  "sha256": "h3", "ingested_at": "2026-01-01T00:00:00"},
        }
        (dr / "registry.json").write_text(json.dumps(registry))
        for did in registry:
            (dr / "chunks" / f"{did}.json").write_text("[]")

        result = engine.dedupe_registry("testco", "")

        assert result["excluded_removed"] == 2
        assert result["kept"] == 1
        reg_after = json.loads((dr / "registry.json").read_text())
        assert set(reg_after.keys()) == {"c"}

    def test_idempotent(self, tmp_path):
        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        (dr / "chunks").mkdir()
        registry = {
            "a": {"doc_id": "a", "filename": "ok.pdf", "sha256": "h1",
                  "ingested_at": "2026-01-01T00:00:00"},
        }
        (dr / "registry.json").write_text(json.dumps(registry))
        (dr / "chunks" / "a.json").write_text("[]")

        # Twice in a row — second call must be a no-op.
        engine.dedupe_registry("testco", "")
        result2 = engine.dedupe_registry("testco", "")

        assert result2["sha_duplicates_removed"] == 0
        assert result2["excluded_removed"] == 0
        assert result2["kept"] == 1


# ── dataroom_ctl classify subcommand hardening (2026-04-24 follow-up) ────────
# The session-34 reclassify bug: my ad-hoc reclassify script skipped passing
# text_preview to classify_document(), collapsing 15 LLM-originally-classified
# files to 'other'. The lesson (tasks/lessons.md 2026-04-24) called for
# extending the existing dataroom_ctl `classify` subcommand with (a) sheet_names
# for Excel rule firing, (b) --dry-run flag to preview before writing.


class TestClassifyCommandHardening:
    """`dataroom_ctl classify` subcommand preserves original pipeline fidelity."""

    def test_help_mentions_use_llm_recommendation(self):
        """Help text should document the --use-llm recommendation so users
        don't accidentally regress LLM-classified docs."""
        import subprocess
        import sys
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "dataroom_ctl.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "classify", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        # The description should guide users toward --use-llm
        assert "--use-llm" in result.stdout
        assert "--dry-run" in result.stdout

    def test_dry_run_flag_registered(self):
        """`classify --dry-run` is registered and doesn't require other args."""
        import subprocess
        import sys
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "dataroom_ctl.py"
        # --dry-run listed in help
        result = subprocess.run(
            [sys.executable, str(script_path), "classify", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        # And "Preview changes" or similar language
        assert "Preview" in result.stdout or "dry-run" in result.stdout


# ── needs-ingest detection (session 37 + this session) ───────────────────────
# Closes the silent failure mode where sync-data.ps1 dropped new source
# files on prod but deploy.sh's old inline `registry_count == chunk_count`
# check was satisfied (e.g. 271 == 271) and skipped ingest. The new
# subcommand checks BOTH registry corruption AND source-file freshness
# vs ingest_log.jsonl mtime, so any of:
#   - new file dropped via sync-data.ps1 since last deploy
#   - registry/chunks mismatch
#   - missing registry / missing ingest log (fresh install)
# all return exit 0 ("ingest needed"). Engine-written sidecars +
# dotfiles + chunks/+analytics/ subdirs are excluded via the same
# _is_supported() filter the engine uses for ingest, so they can't
# spuriously trigger.


class TestNeedsIngest:
    """`dataroom_ctl needs-ingest` detects newly-added source files
    that the registry/chunks alignment check alone would miss."""

    @staticmethod
    def _seed_aligned_dataroom(
        engine: DataRoomEngine,
        data_root: Path,
        n_files: int = 2,
    ) -> Path:
        """Helper: seed an aligned dataroom (registry == chunks) with N csv files,
        then write an ingest_log.jsonl with mtime = NOW. Returns dataroom dir."""
        import time

        dr = data_root / "testco" / "dataroom"
        for i in range(n_files):
            _write_csv(dr / f"file{i}.csv", f"col,v\nrow_{i},{i}\n")

        # Real ingest produces aligned registry+chunks
        engine.ingest("testco", "", str(dr))
        # ingest writes ingest_log.jsonl as part of the record_ingest call
        # (not the engine itself — the cmd_ingest wrapper does it). For tests
        # we synthesize the log directly so we control its mtime.
        log = dr / "ingest_log.jsonl"
        log.write_text('{"ts":"2026-04-25","action":"ingest","added":2}\n')
        # Ensure source-file mtimes are clearly OLDER than the log mtime,
        # otherwise the freshness check would trip on the seeded files.
        old_ts = time.time() - 60.0
        for csv in dr.rglob("*.csv"):
            os.utime(csv, (old_ts, old_ts))
        return dr

    def test_returns_exit_1_when_aligned_and_no_new_files(self, tmp_path):
        """The clean case: registry+chunks aligned, ingest_log.jsonl newer
        than every source file → exit 1, reason='clean'."""
        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        self._seed_aligned_dataroom(engine, data_root, n_files=3)

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is False
        assert result["reason"] == "clean"
        assert result["registry_count"] == 3
        assert result["chunk_count"] == 3
        assert result["source_file_count"] == 3

    def test_returns_exit_0_when_new_source_file_added(self, tmp_path):
        """The session-37 case: aligned registry+chunks, but a brand-new
        .pdf got dropped after the last ingest → exit 0, reason='newer_files'."""
        import time

        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = self._seed_aligned_dataroom(engine, data_root, n_files=2)

        # Add a new source file with mtime > log mtime. Use a definitively-
        # future stamp to be robust on filesystems with second-level mtime.
        new_pdf = dr / "new_data" / "fresh_investor_pack.pdf"
        new_pdf.parent.mkdir()
        new_pdf.write_bytes(b"%PDF-1.4 fake")
        future = time.time() + 60.0
        os.utime(new_pdf, (future, future))

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is True
        assert result["reason"] == "newer_files"
        assert result["newer_count"] == 1
        # Registry/chunks still aligned at 2 — alignment check alone wouldn't
        # have triggered. This is the bug needs-ingest exists to catch.
        assert result["registry_count"] == 2
        assert result["chunk_count"] == 2

    def test_returns_exit_0_when_alignment_broken(self, tmp_path):
        """Pre-existing registry/chunks misalignment → exit 0, even if the
        ingest_log.jsonl is fresh (alignment check fires first)."""
        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = self._seed_aligned_dataroom(engine, data_root, n_files=2)

        # Delete one chunk file to simulate corruption
        chunks = list((dr / "chunks").glob("*.json"))
        chunks[0].unlink()

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is True
        assert result["reason"] == "registry_chunk_mismatch"
        assert result["registry_count"] == 2
        assert result["chunk_count"] == 1

    def test_returns_exit_0_when_no_ingest_log(self, tmp_path):
        """Aligned registry+chunks but no ingest_log.jsonl (fresh install
        scenario, or someone wiped the log) → exit 0, reason='no_ingest_log'.
        Without this branch we'd silently treat a brand-new prod as clean."""
        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = self._seed_aligned_dataroom(engine, data_root, n_files=2)

        (dr / "ingest_log.jsonl").unlink()

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is True
        assert result["reason"] == "no_ingest_log"

    def test_returns_exit_0_when_no_registry(self, tmp_path):
        """No registry.json but source files present → exit 0, 'no_registry'."""
        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = data_root / "testco" / "dataroom"
        _write_csv(dr / "real.csv")

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is True
        assert result["reason"] == "no_registry"
        assert result["source_file_count"] == 1

    def test_returns_clean_when_dataroom_is_empty(self, tmp_path):
        """No source files at all → clean. Calling ingest on an empty
        dataroom would just write an empty manifest entry every deploy."""
        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        # Don't write any source files; dataroom dir already exists per fixture.

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is False
        assert result["reason"] == "empty_dataroom"
        assert result["source_file_count"] == 0

    def test_excluded_files_dont_trigger_ingest(self, tmp_path):
        """Engine-written sidecars in _EXCLUDE_FILENAMES (meta.json,
        covenant_history.json, etc.) must NOT count as new source files.
        meta.json is rewritten on every ingest cycle as part of the index
        build; without exclusion, deploy.sh would treat the dataroom as
        perpetually dirty."""
        import time

        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = self._seed_aligned_dataroom(engine, data_root, n_files=2)

        future = time.time() + 60.0

        # `meta.json` is an existing engine-written sidecar — bump its mtime
        # in place so we don't corrupt its JSON contents (overwriting with
        # "{}" would also work since the file is excluded, but in-place
        # mtime bump is the more realistic scenario).
        meta = dr / "meta.json"
        if meta.exists():
            os.utime(meta, (future, future))

        # Other sidecars that may not exist yet — write fresh ones with
        # future mtime. None of these should appear in the source-file walk.
        for excluded in ("covenant_history.json", "facility_params.json",
                          "payment_schedule.json", "debtor_validation.json"):
            p = dr / excluded
            p.write_text("{}")
            os.utime(p, (future, future))

        result = _needs_ingest_check(engine, "testco", "")

        # All excluded — should still be clean despite future mtimes.
        assert result["needs_ingest"] is False, (
            f"Excluded sidecars triggered ingest: reason={result['reason']}, "
            f"newer_count={result.get('newer_count')}"
        )
        assert result["reason"] == "clean"

    def test_dotfiles_dont_trigger_ingest(self, tmp_path):
        """Dotfiles (e.g. `.classification_cache.json` written by the LLM
        classifier) must NOT trigger ingest. Engine ignores them at ingest
        time too — needs-ingest must agree."""
        import time

        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = self._seed_aligned_dataroom(engine, data_root, n_files=2)

        cache = dr / ".classification_cache.json"
        cache.write_text('{"a":"b"}')
        future = time.time() + 60.0
        os.utime(cache, (future, future))

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is False
        assert result["reason"] == "clean"

    def test_chunks_dir_files_dont_trigger_ingest(self, tmp_path):
        """Files inside chunks/ are engine output (one .json per registry
        entry). A freshly-written chunk file must NOT mark the dataroom
        as dirty — chunks are produced BY ingest, not consumed."""
        import time

        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = self._seed_aligned_dataroom(engine, data_root, n_files=2)

        # Touch one of the chunk files into the future
        chunk = next((dr / "chunks").glob("*.json"))
        future = time.time() + 60.0
        os.utime(chunk, (future, future))

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is False
        assert result["reason"] == "clean"

    def test_real_json_in_dataroom_root_does_trigger_ingest(self, tmp_path):
        """A real .json source file (e.g. an investor pack) at any
        non-engine path SHOULD trigger ingest. The exclude list is for
        engine-written sidecars by exact filename, not for the .json
        extension generally."""
        import time

        from scripts.dataroom_ctl import _needs_ingest_check

        engine, data_root = _make_engine(tmp_path)
        dr = self._seed_aligned_dataroom(engine, data_root, n_files=1)

        # Drop a non-excluded .json source file at a sub-folder path.
        new_json = dr / "investor_packs" / "2026-04-15_investor_pack.json"
        new_json.parent.mkdir()
        new_json.write_text('{"period":"Q1 2026"}')
        future = time.time() + 60.0
        os.utime(new_json, (future, future))

        result = _needs_ingest_check(engine, "testco", "")

        assert result["needs_ingest"] is True
        assert result["reason"] == "newer_files"
        assert result["newer_count"] == 1

    def test_help_lists_needs_ingest_subcommand(self):
        """Top-level help should show the new subcommand."""
        import subprocess
        import sys
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "dataroom_ctl.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "needs-ingest" in result.stdout

    def test_subcommand_help_documents_inverted_exit_codes(self):
        """`needs-ingest --help` must explain the 0/1 inversion vs audit,
        otherwise operators reading the help will misinterpret exit codes."""
        import subprocess
        import sys
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "dataroom_ctl.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "needs-ingest", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        # Must mention the bash idiom or the exit code semantics
        text = result.stdout.lower()
        assert "exit" in text
        assert "needs-ingest" in result.stdout
