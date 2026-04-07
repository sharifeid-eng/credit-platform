# End of Session Wrap-Up

Perform a thorough end-of-session close. Work through every step below in order. Do not skip any step. Do not ask for confirmation before each step — just do them and report what was done.

---

## Step 1 — Inventory uncommitted changes

Run `git status` and `git diff --stat`. List every modified, untracked, or deleted file. For each file, state whether it needs to be committed.

## Step 2 — Run tests

Run `pytest tests/ -q` from the project root. Report pass/fail counts. If any tests fail, fix them before proceeding — do not commit broken code.

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

Stage and commit `CLAUDE.md`, `tasks/todo.md`, `tasks/lessons.md`, and any other modified source files that haven't been committed yet. Use a clear, descriptive commit message. Do **not** commit `.env`.

## Step 9 — Push to main

`git push origin main`

## Step 10 — Sync feature branch (if one exists)

If there is an active feature branch (check `git branch -a`), fast-forward it to main:
```
git checkout <feature-branch>
git merge main --no-edit
git push origin <feature-branch>
git checkout main
```

## Step 11 — Production redeploy reminder

If this session changed any backend, frontend, or core/ code (not just docs/CLAUDE.md/todo.md), remind the user:

> **Code was pushed that affects the running app.** To update production, SSH into the server and redeploy:
> ```
> ssh root@204.168.252.26
> cd /opt/credit-platform && ./deploy.sh
> ```

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
