# Next Session — Real web_search Smoke + Deferred Items

Paste the block below into a fresh local Claude Code session started in `C:\Users\SharifEid\credit-platform`. It packages everything the next session needs: the real-world web_search smoke test (with browser automation), the visual UI checks, and the D1–D7 deferred items from session 27.

---

## Paste this into Claude Code

```
TASK: Real external.web_search end-to-end smoke test + visual UI verification.

CONTEXT:
- Branch: main at 49337ca or later. Session 27 shipped the External Intelligence
  four-layer system (Commits 1a/1b/2/3 plus follow-up fixes). 428 pytest + 16/16
  verify_external_intelligence.py already green on laptop.
- The one untested path is a real Claude web_search_20250305 call. Everything
  around it (pending-review queue, asset class mind, promotion pipeline,
  Layer 2.5 AI context, analyst agent tool exposure) has been verified with
  mocks. I need you to close that last 10%.
- Platform runs locally via `.\start.ps1` — backend at localhost:8000,
  frontend at localhost:5173.
- See tasks/todo.md "Completed 2026-04-20 (session 27)" for full context on
  what was built.

YOU ARE DOING TWO THINGS: (A) a real end-to-end smoke in Chrome, and (B) a
visual pass over the three Resources pages. Both use browser automation —
install Playwright if you don't have it. Do NOT mock anything in Part A; it
has to hit real Claude.

───────────────────────────────────────────────────────────────────────────
PART A — REAL WEB_SEARCH END-TO-END SMOKE
───────────────────────────────────────────────────────────────────────────

Pre-flight:
1. Confirm backend + frontend are running (start.ps1 if not).
2. Check backend logs for "Registered N agent tools" at startup — N should be
   43. If not, something didn't import; stop and report.
3. Install Playwright in the venv: `pip install playwright && playwright
   install chromium`. Or use chrome-devtools-mcp if already configured.

Flow (drive Chrome from start to finish, take a screenshot at EVERY numbered
step, save to reports/web-search-smoke/):

  1.  Open http://localhost:5173. Log in if prompted.
  2.  Click any company card (Klaim recommended — it has analysis_type that
      maps to healthcare_receivables context).
  3.  Go to Tape Analytics → Overview. Find the Data Chat panel (right side).
  4.  Type EXACTLY: "Search the web for typical default rates in healthcare
      receivables factoring in MENA, and save it to the
      healthcare_receivables asset class for future reference."
  5.  Submit. Start a 90-second timer — web_search is a nested Claude call.
  6.  Capture the agent's response text. Expected markers:
        - Mentions "pending review" or "queued for analyst review"
        - Includes a short ID like "Pending ID: abc12345"
        - Lists at least 2 source URLs
      If the agent answered from memory without calling the tool, grep the
      backend log for "external.web_search" — if no hits, the tool wasn't
      invoked. Stop and report the response text + the agent's turn count.
  7.  Navigate to /operator. Click "Pending" tab.
  8.  Verify EXACTLY ONE new pending entry with:
        - Source chip = web_search
        - Scope chip = "→ asset_class/healthcare_receivables"
        - Category = external_research
        - Non-empty content
        - Citation list with clickable URLs (click one to confirm it opens)
  9.  Click Approve. Confirm the entry moves to Approved (status counts
      update: Pending -1, Approved +1).
  10. Click "Asset Classes" tab. Expect a healthcare_receivables chip.
  11. Click the chip. Verify the approved entry appears as a card with:
        - Purple category chip
        - Source = web_search
        - Content matches what was approved
        - Citation list present
  12. Click "↑ Promote to Master" on the entry.
  13. Expect a green "Promoted to Master" badge on the card. Promote button
      should disappear/disable.
  14. Hit `http://localhost:8000/companies/klaim/UAE_healthcare/mind/context
      ?task_type=executive_summary` in a new tab. Capture the JSON.
      Assert asset_class_length > 0 and "healthcare_receivables" appears in
      formatted_preview.
  15. On disk, cat `data/_master_mind/sector_context.jsonl`. Expect the last
      line to contain the promoted content with metadata.promoted_from chain:
        {"scope": "asset_class", "key": "healthcare_receivables", ...}

Report: pass/fail per step, screenshot filenames, full JSON from step 14,
cost estimate from backend logs for the nested Claude call.

Known failure modes — log the exact error if hit:
- web_search_20250305 not available on model tier used → report the exact
  anthropic error and which model was resolved for tier="research"
- Handler runs but queue stays empty → check data/_pending_review/
  permissions + silent except in core/agents/tools/external.py
- Agent picks wrong target_scope/target_key/category → capture the tool_use
  block args; may need to tighten the tool description

───────────────────────────────────────────────────────────────────────────
PART B — VISUAL UI PASS
───────────────────────────────────────────────────────────────────────────

Drive Chrome through every Resources page and flag anything visually off.
Screenshot everything.

  1.  http://localhost:5173 — three Resources cards (Operator, Framework,
      Architecture) with live vitals. Confirm no dashes in the vitals row.
  2.  Click Architecture card → /architecture. Verify:
        - 12 stat tiles at top, all showing numbers (Tests should be >400)
        - "Feedback Loops" section: 3 loop rows (Ingestion teal, Learning
          gold, Intelligence violet), each with 5 boxes + closing dashed arc
        - No text overlap between section headers and row boxes
        - "System Architecture" section below: LLM/FX/JWT arrows do not
          obscure FastAPI box labels
        - 7 capability cards ("Self-Improvement Loops" first)
  3.  Click "← Back to dashboard".
  4.  Click Operator → /operator. Count tabs (expect 12: Health · Commands
      · Follow-ups · Activity · Mind · Briefing · Learning · Thesis ·
      Agents · Data Rooms · Pending · Asset Classes).
      - Pending tab should show the approve/reject history from Part A
      - Asset Classes tab should show healthcare_receivables chip
  5.  Click each of the three new tabs (Data Rooms, Pending, Asset Classes)
      and screenshot. No console errors in DevTools.
  6.  Test scroll-to-top: scroll to bottom of Home, click any Resources
      card. New page should load at the top, not mid-scroll.

Report any visual issues with screenshots + a short description.

───────────────────────────────────────────────────────────────────────────
DEFERRED ITEMS (D1–D7) — SCOPE FROM THESE AFTER SMOKE PASSES
───────────────────────────────────────────────────────────────────────────

Full details in CLAUDE.md "Known Gaps & Next Steps" under Session 27. Quick
summary so the user can pick:

  D1. Company → Asset Class promote button in Mind tab UI.
      Backend endpoint POST /api/mind/promote already exists and was
      tested (test 09 in verify_external_intelligence.py). UI missing
      because the category mapping across Company↔AssetClass boundary
      needs a real-world test first.

  D2. Memo / ExecSummary / chat citation rendering for Layer 2.5 entries.
      External context flows into AI prompts via build_mind_context()
      automatically. UI doesn't yet say "this answer was informed by
      Asset Class entry X with citations Y, Z."

  D3. Unit tests for new modules. verify_external_intelligence.py covers
      the logic but isn't in pytest. Port the 16 checks into proper
      pytest files: tests/test_asset_class_mind.py,
      tests/test_pending_review.py, tests/test_promotion.py,
      tests/test_external_tool.py, tests/test_backend_external.py.

  D4. Seed Asset Class Mind with opening entries per analysis_type.
      Ships empty; feature is invisible until populated. Draft 2-3
      entries per analysis_type drawn from CLAUDE.md + existing Company
      Mind entries.

  D5. Extend other agents (memo_writer, compliance_monitor, onboarding)
      with external.* patterns. Currently only analyst has external.*
      tools. Decide per-agent: memo_writer is the obvious next target.

  D6. Framework codification hook for technical research. Technical
      research papers that would update the Framework itself should
      pipe into the /extend-framework slash command.

  D7. Scheduled external pollers. Parked by design — on-demand model
      preferred. Revisit only if on-demand proves too reactive.

Ask the user which D items to tackle after smoke passes. Do NOT start any
of them without confirmation — each is scoped as its own session.
```

---

## File locations (for reference)

The kickoff prompt above is also saved at `tasks/next-session-kickoff.md` in the repo so you can re-find it later. Deferred items are in `CLAUDE.md` under "Known Gaps & Next Steps → Session 27 deferred".
