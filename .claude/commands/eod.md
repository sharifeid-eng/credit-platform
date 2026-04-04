# End of Session Wrap-Up

Perform a thorough end-of-session close. Work through every step below in order. Do not skip any step. Do not ask for confirmation before each step — just do them and report what was done.

---

## Step 1 — Inventory uncommitted changes

Run `git status` and `git diff --stat`. List every modified, untracked, or deleted file. For each file, state whether it needs to be committed.

## Step 2 — Update `tasks/todo.md`

- Move everything completed this session into a new `## Completed — YYYY-MM-DD` section (use today's date).
- Clear the `## Active` section if there is nothing left in progress.
- Preserve all prior completed sections as-is.

## Step 3 — Update `tasks/lessons.md`

- Review the full conversation for any: mistakes made and corrected, patterns to avoid, user corrections, architectural decisions with non-obvious rationale.
- Add a dated entry for each new lesson. If there are no new lessons, note that explicitly so this step is visibly done.

## Step 4 — Update `CLAUDE.md`

- Update the **What's Working** section to reflect anything new that was built or changed.
- Update the file tree in **Project Structure** if any files were added or deleted.
- Update any architectural decision notes in **Key Architectural Decisions** if relevant.
- Remove any references to things that no longer exist.

## Step 5 — Commit all changes

Stage and commit `CLAUDE.md`, `tasks/todo.md`, `tasks/lessons.md`, and any other modified source files that haven't been committed yet. Use a clear, descriptive commit message. Do **not** commit `.env`.

## Step 6 — Push to main

`git push origin main`

## Step 7 — Sync feature branch (if one exists)

If there is an active feature branch (check `git branch -a`), fast-forward it to main:
```
git checkout <feature-branch>
git merge main --no-edit
git push origin <feature-branch>
git checkout main
```

## Step 8 — Final verification

Run `git log --oneline -5` and `git status` to confirm:
- Working tree is clean
- Both main and feature branch (if any) are at the same commit
- No uncommitted changes remain

Report the final commit hash and confirm the session is cleanly closed.
