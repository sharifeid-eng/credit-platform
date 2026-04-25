# End of Session Wrap-Up

Perform a thorough end-of-session close. Work through every step below in order. Do not skip any step. Do not ask for confirmation before each step — just do them and report what was done.

---

## Step 1 — Inventory uncommitted changes

Run `git status` and `git diff --stat`. List every modified, untracked, or deleted file. For each file, state whether it needs to be committed.

## Step 1b — Check for untracked data artifacts that should be committed

These files are generated at runtime but ARE tracked (not gitignored). Check if any exist and are untracked:
```
git ls-files --others --exclude-standard -- "data/*/dataroom/registry.json" "data/*/mind/relations.json" "data/*/legal/*_extracted.json" "reports/memos/"
```
If any results appear, stage them — they represent work product that won't survive worktree cleanup.

## Step 2 — Run tests + warning-drift check

Run `pytest tests/ -q` from the project root. Report pass/fail counts. If any tests fail, fix them before proceeding — do not commit broken code.

**Warning-drift check (mandatory — do not skip):** also capture the pytest warning count from the final line (`N passed, M warnings in …`). Compare against the baseline below:

> **Last recorded baseline: 0 warnings (session 30 tail, 2026-04-22, post-deprecation-cleanup `6805cec`)**

If the current count is within ±5 of baseline, proceed without comment. If it jumped by >10, this means today's work introduced new deprecations or code smells worth flagging. Extract the top 3 warning categories:

```
pytest tests/ -q 2>&1 | Select-String -Pattern "DeprecationWarning|UserWarning|PendingDeprecationWarning" -Context 0,1 | Group-Object Line | Sort-Object Count -Descending | Select-Object -First 3
```

Flag any new category in the EoD summary ("+N new deprecations in <category>"). Don't require fixing them in this session — just surface the jump so new deprecations don't hide in existing background noise. After significant refactors (either up or down), update the baseline number at the top of this step.

Known background warnings as of the last baseline: **none.** All internal `datetime.utcnow()` and Pydantic class-based `Config` occurrences were cleared in the session-30-tail deprecation cleanup merge (`6805cec`). Any new warning that appears is introduced by today's work.

## Step 3 — Safety check: confirm .env is not tracked

Run `git ls-files .env`. If it returns anything, stop immediately and remove it from tracking with `git rm --cached .env` before proceeding.

## Step 4 — Clean up stale cache files

Delete any stale cache files that should not persist between sessions:
- `reports/aggregate_stats_cache.json` (will recompute on next request)
- Any other temp files in `reports/` that are auto-generated (not hand-crafted)

Do not delete hand-written files like notes or analyst reports.

## Step 5 — Update `tasks/todo.md`

- Move everything completed this session into a new `## Completed — YYYY-MM-DD` section (use today's date).
- Clear the `## Active` section if there is nothing left in progress.
- Preserve all prior completed sections as-is.

## Step 6 — Update `tasks/lessons.md`

Review the full conversation for any: mistakes made and corrected, patterns to avoid, user corrections, architectural decisions with non-obvious rationale. Add a dated entry for each new lesson. If there are no new lessons, note that explicitly so this step is visibly done.

## Step 7 — Update `CLAUDE.md`

- Update the **What's Working** section to reflect anything new that was built or changed.
- **Reconcile "Known Gaps & Next Steps"** — scan every `- [ ]` item and check it off (`- [x]`) if it was implemented this session or previously. Cross-reference against "What's Working" entries. Mark completed sections with `✅ COMPLETE` when all items are done.
- Update the file tree in **Project Structure** if any files were added or deleted.
- Update any architectural decision notes in **Key Architectural Decisions** if relevant.
- Remove any references to things that no longer exist.

## Step 8 — Commit all changes

Stage and commit `CLAUDE.md`, `tasks/todo.md`, `tasks/lessons.md`, any data artifacts flagged in Step 1b, and any other modified files that haven't been committed yet. Use a clear, descriptive commit message. Do **not** commit `.env`.

## Step 9 — Merge to main and push

**This step is NON-NEGOTIABLE. The deploy script pulls `main`. If work stays on a feature branch, it doesn't deploy.**

If you are in a worktree, commit on the worktree branch first, then merge from the main working directory:
```
cd C:\Users\SharifEid\credit-platform
git checkout main
git pull origin main
git merge <feature-branch> --no-edit
git push origin main
```

If you are on a feature branch (not in a worktree):
```
git checkout main
git pull origin main
git merge <feature-branch> --no-edit
git push origin main
```

If you are already on main:
```
git push origin main
```

## Step 10 — Sync feature branch (if one exists)

After main is pushed, sync the feature branch so it matches:
```
git checkout <feature-branch>
git merge main --no-edit
git push origin <feature-branch>
git checkout main
```

**Task-branch hygiene sweep** (no-op if nothing was merged this session):

After all merges land, list any remaining `claude/*` branches that are now fully merged to main — these are stragglers from prior work that never got cleaned during their merge:

```powershell
git branch --merged main | Select-String "^  claude/"
```

For each listed branch, release its worktree and delete the branch:

```powershell
git worktree remove --force .claude/worktrees/<name>
git branch -D claude/<name>
```

If `worktree remove` fails with Windows "permission denied" (a process holds the directory — another Claude Code session, VS Code, a terminal cd'd inside, Explorer window), verify git's metadata is already released via `git worktree list | Select-String "<name>"` — empty output means metadata is gone and `git branch -D` will succeed regardless. The empty directory on disk clears at next reboot, when the holding process exits, or on the next EoD sweep (next step) — functionally harmless in the interim.

Per-merge cleanup during the merge sequence is the better discipline; this sweep only catches stragglers that slipped through.

**Opportunistic filesystem orphan sweep (mandatory — do not skip):** After the branch cleanup, walk `.claude/worktrees/` and attempt to remove any directory that git no longer tracks as a worktree. These are leftovers from prior sessions whose holding process failed to release the directory at the time — reboots and process exits since then may have freed them up. Silent-fail on busy directories; we'll catch them on the next EoD run.

**From the main repo directory (bash in the `/c/.../credit-platform` root, NOT the worktree):**
```bash
cd /c/Users/SharifEid/credit-platform && \
  for d in .claude/worktrees/*/; do
    name=$(basename "$d")
    # Skip directories that git still tracks as active worktrees
    git worktree list | grep -q "/$name " && continue
    rm -rf "$d" 2>/dev/null && echo "  swept: $name" || true
  done
```

The loop is idempotent — running it on every EoD gradually reclaims orphans as their holders exit. The user's system had 12 orphans dating back 11+ days when this sweep was added; the first run cleaned 6 and left 5 stuck (which will clear on the next sweep once their Claude Code sessions exit).

Report in the EoD summary how many orphans were swept (0 is the healthy steady state; > 0 is normal opportunistic catch-up). Don't investigate stuck ones — they'll clear naturally on a later run.

## Step 11 — Production redeploy reminder

If this session changed any backend, frontend, core/, or data/ files (not just docs/CLAUDE.md/todo.md), remind the user:

> **Changes were pushed that affect the running app.** To update production, SSH into the server and redeploy:
> ```
> ssh root@204.168.252.26
> cd /opt/credit-platform && ./deploy.sh
> ```

**Dataroom sync check (mandatory — do not skip):**

The prior version of this check (`git diff HEAD~10 | grep registry.json`) has been structurally broken since session 26.1 removed `registry.json` from git tracking (see `.gitignore:55`). A `git diff` will NEVER see registry changes now — the check always returned empty regardless of whether raw dataroom files were added. Session 37 surfaced the gap: two new Tamara files were added to the local dataroom, EoD said "no sync needed", prod silently missed them until the user manually ran `sync-data.ps1`.

Since raw dataroom files are ALL gitignored, git cannot detect dataroom changes. Use filesystem mtime instead — the `ingest_log.jsonl` per-dataroom is the authoritative signal. Every successful `dataroom_ctl ingest`/`refresh` appends a line to that file.

```powershell
# PowerShell — find any dataroom ingest_log modified in last 24 hours
Get-ChildItem -Path "data\*\dataroom\ingest_log.jsonl" -ErrorAction SilentlyContinue `
  | Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-1) } `
  | ForEach-Object { $_.FullName }
```

```bash
# Bash equivalent
find data/*/dataroom/ingest_log.jsonl -mtime -1 -type f 2>/dev/null
```

Also check for NEW source files added but not yet ingested (still bearing a `.classification_cache.json` / registry mtime older than the source file):

```bash
# Find any source file newer than its parent dataroom's ingest_log
for log in data/*/dataroom/ingest_log.jsonl; do
  [ ! -f "$log" ] && continue
  co=$(basename $(dirname $(dirname "$log")))
  newer=$(find "data/$co/dataroom" -type f \
    \( -name "*.pdf" -o -name "*.xlsx" -o -name "*.xls" -o -name "*.docx" -o -name "*.ods" -o -name "*.csv" \) \
    -newer "$log" 2>/dev/null | head -5)
  [ -n "$newer" ] && echo "$co has newer source files than last ingest:" && echo "$newer"
done
```

If EITHER check returns anything (dataroom ingested this session OR disk has newer source files than last ingest), remind the user:

> **Sync dataroom files to production.** Raw dataroom files (PDFs, xlsx, docx) are not in git. Run from your laptop PowerShell:
> ```powershell
> cd C:\Users\SharifEid\credit-platform
> .\scripts\sync-data.ps1                    # all companies
> .\scripts\sync-data.ps1 -Company {name}    # one company only
> ```
>
> **CRITICAL: `deploy.sh` alone is NOT sufficient after sync.** The alignment check inside `deploy.sh` only detects registry-vs-chunks misalignment — it does NOT detect new source files on disk. After `sync-data.ps1` lands new files on prod, you must MANUALLY trigger re-ingest:
> ```bash
> ssh root@204.168.252.26 'cd /opt/credit-platform && \
>   docker compose exec -T backend python scripts/dataroom_ctl.py ingest --company {name}'
> ```
>
> For Tamara-specific flows (investor packs + thesis), additional commands:
> ```bash
> # Parse new investor pack into structured JSON
> ssh root@204.168.252.26 'cd /opt/credit-platform && \
>   docker compose exec -T backend python scripts/ingest_tamara_investor_pack.py \
>   --file "data/Tamara/dataroom/Financials/54.2.2 Management Financials/<pack.xlsx>"'
>
> # Seed thesis (one-time per prod environment)
> ssh root@204.168.252.26 'cd /opt/credit-platform && \
>   docker compose exec -T backend python scripts/seed_tamara_thesis.py'
> ```
> The Tamara flow requires 2-3 steps (dataroom ingest + pack parse + thesis seed) because the investor pack produces a per-machine JSON (gitignored) and the thesis is also per-machine. A future enhancement would wrap these into a single `post-sync-tamara.sh` on the server.

**Tape file tracking check (mandatory — do not skip):** Raw loan tapes (`data/{company}/{product}/YYYY-MM-DD_*.csv|xlsx|ods`) ARE tracked in git — they ship to production via `git pull` during `deploy.sh` just like code. There is no gitignore rule for them. An untracked tape is almost always a mistake (tape was copied onto the laptop but never `git add`'d — surfaced once in session 34 when an Apr 15 Klaim tape had been on disk for 4 days without being committed, causing a silent Tape-vs-Portfolio Analytics skew on prod). Run:
```
git ls-files --others --exclude-standard -- "data/*/*/2*.csv" "data/*/*/2*.xlsx" "data/*/*/2*.ods"
```
This lists untracked date-prefixed files in per-product directories. The expected healthy state is empty output — all tape files should be committed. If any file appears, **commit it**:
```
git add data/{company}/{product}/YYYY-MM-DD_{name}.csv
git commit -m "data: add {company} {date} tape (N rows, M cols)"
```
Then the existing `deploy.sh` flow ships it to prod via `git pull`. No separate SCP needed.

**When might a tape legitimately stay untracked?** Only if the file is scratch/experimental and will not be used for analysis. Real tapes destined for IC output must be in git — otherwise prod's Tape Analytics serves the previous snapshot silently (the Postgres DB ingestion path via `scripts/ingest_tape.py` updates Portfolio Analytics, but Tape Analytics still reads files from disk for Klaim). Untracked-tape = tape-vs-portfolio data skew on prod.

If only documentation files changed (CLAUDE.md, tasks/, .claude/), skip this step — no redeploy needed.

## Step 12 — Sync all environments

Changes were pushed to GitHub. Remind the user to sync any environment that wasn't the one running this session:

> **Sync other environments:**
>
> If this was a **cloud session**, pull to your laptop:
> ```powershell
> cd C:\Users\SharifEid\credit-platform
> git pull origin main
> ```
>
> If this was a **local laptop session**, the production server needs the code (if code changed — handled by Step 11's redeploy), and any future cloud sessions will auto-clone from GitHub so they're already covered.

## Step 13 — Final verification

Run `git log --oneline -5` and `git status` to confirm:
- Working tree is clean
- Both main and feature branch (if any) are at the same commit
- No uncommitted changes remain
- `.env` is not tracked (`git ls-files .env` returns nothing)

Report the final commit hash, confirm the session is cleanly closed, and state whether a production redeploy is needed.
