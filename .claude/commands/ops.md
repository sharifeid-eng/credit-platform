# Operator Briefing

Perform a quick operator status check and present a concise briefing. This is designed for the start of a session — surface what needs attention without overwhelming detail.

---

## Step 1 — Read platform state

Read the following files to understand current state:
- `tasks/todo.md` — check the Active section for open items
- `tasks/lessons.md` — check the most recent 3 entries for patterns to avoid
- `reports/deep-work/progress.json` — check if a deep work session left unfinished business

## Step 2 — Check company health

For each company directory under `data/`:
1. List snapshots and note the most recent date — flag if >30 days stale
2. Check if `mind/` directory has JSONL files — flag if empty
3. Check if `legal/` has `*_extracted.json` files — note legal coverage
4. Check if `dataroom/registry.json` exists — note ingestion status

## Step 3 — Check for uncommitted changes

Run `git status --short` and `git log --oneline -3` to see if there's work in flight from a prior session.

## Step 4 — Present briefing

Format the output as a concise briefing:

```
═══ LAITH OPERATOR BRIEFING ═══
Date: {today}
Branch: {current branch}

── Company Health ──
{company}: {tape_count} tapes, latest {date} ({N}d ago) {🟢/🟡/🔴}
  Legal: {extracted/missing}  |  Mind: {N entries/empty}  |  DataRoom: {N docs/none}
  Gaps: {list any detected gaps}

── Open Items ──
{list active items from todo.md}

── Recent Lessons ──
{last 3 entries from lessons.md}

── Git Status ──
{clean / N uncommitted changes}
Last commits: {3 most recent}

── Recommendations ──
{1-3 actionable suggestions based on what you found}
```

Keep it under 40 lines. Focus on what needs attention, not what's fine.
