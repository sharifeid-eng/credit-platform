# Lessons Learned
Persistent log of mistakes and patterns. Claude reviews this at session start to avoid repeat errors.

---

## 2026-04-24 — Walkers that only audit top-level fields miss per-row disclosures in nested lists

**Problem:** Session 35 built the §17 meta-audit walker and declared "every rate field now has population + confidence." It found 45 top-level scalar gaps and fixed them. But the walker only inspected the root of each compute function's return dict — it never recursed into list-valued fields like `vintages[]`, `by_product[]`, `transition_matrix[]`. Session 36's gap-review extension added a per-row walker and surfaced **19 additional gaps in 7 compute functions** — per-row rates (e.g., `vintages[].gross_default_rate`, `by_product[].margin_rate`) that inherit no discipline from their parent dict.

The walker's coverage boundary was implicit; it read "covers all rate fields" but actually meant "covers all *top-level scalar* rate fields." Anyone reading the test name (`TestMetaAuditRateFieldDisclosure`) could reasonably assume full coverage and skip building a sibling test for list-row fields.

**Rule:** When writing a walker that audits a contract across compute functions, enumerate every shape the return value can take and either cover each shape or explicitly document which shapes are out-of-scope. The shapes to consider:
1. Top-level scalar fields (simple) — covered by session 35.
2. Top-level list-of-dict fields (cohorts[], vintages[], buckets[]) — per-row rates need disclosure via dict-level inheritance, list-level `<list>_population`/`<list>_confidence`, or row-level.
3. Nested dict fields (e.g., compute_concentration's `hhi: {...}` sub-dict) — sub-dict's own keys may need independent declarations.
4. Top-level list returns (like compute_cohorts returning bare list) — harder to attach disclosure; usually need an exemption documented in the walker test file.

**How to apply:**
- When authoring a walker in the future, start by mapping every return-value shape in the scope before writing heuristics. Write sibling `Test*` classes for each shape.
- Accept §17 disclosure through 5 modes explicitly (dict-level, per-field, family-level, list-level, documented exemption) so compute-function authors have flexibility in how they declare.
- When a new walker surfaces gaps, fix them in the SAME commit that lands the walker — keeps the first "walker pass" clean, so the next session isn't debugging which gaps pre-existed vs which the walker just introduced.
- Reference: session 36 `f7ef580` walker extension surfaced Klaim `compute_facility_pd.transition_matrix[].to_default_pct`, SILQ `compute_silq_tenure.distribution[].margin_rate`, Aajil `compute_aajil_yield.by_deal_type[].avg_total_yield` — none of these would have been flagged by the session-35 scalar walker, and none were user-visible until a memo asked for a recovery_rate across vintages.

---

## 2026-04-24 — Multiple concurrent Claude Code sessions on the same repo share working tree state during branch switches

**Problem:** Session 36 ran alongside another session (Tamara investor pack ingest) on the same `credit-platform` main repo. When I switched branches, the other session's uncommitted files (with modified working tree) followed me across `git checkout`. `git add -A` would have committed THEIR work to MY branch. I caught it by running `git status --short` before staging, but it's the kind of cross-contamination that can silently ship another session's WIP into production.

Symptoms to watch for:
- `git status` shows files you don't remember modifying.
- Branch reflog shows `checkout: moving from <my-branch> to <other-session-branch>` entries you didn't initiate.
- `git worktree list` shows more worktrees than you created.

**Rule:** Never use `git add -A` or `git add .` when other Claude Code sessions are running on the same repo. Always `git add <specific-files>` with file paths you authored this session.

**How to apply:**
- Before EVERY `git add`, run `git status --short` and mentally diff: "which files did I touch, which are from another session?" If any file's modification is a surprise, stop — investigate with `git log --follow <file>` and `git blame` before staging.
- Before EVERY `git commit`, re-check `git branch --show-current` — another session may have switched you to their branch during a stash pop or similar.
- Use `git stash push -u -m "desc" -- <file-list>` with explicit file list when you need to temporarily isolate one session's work before branch-switching to another.
- When you spot another session's uncommitted work in your working tree: stash it (`git stash push -u -m "other session WIP" -- <their-files>`), do your branch-switch + commit + push, then switch back to their branch and `git stash pop` to restore. Don't leave them with an empty working tree.
- If you accidentally commit another session's file to your branch, cherry-pick or reset immediately — don't let it reach `origin/main`. The commit history is much harder to untangle after a push.

Reference: session 36 caught `core/analysis_tamara.py`, `core/dataroom/classifier.py`, `data/Tamara/investor_packs/`, `frontend/src/pages/research/DocumentLibrary.jsx`, and `scripts/ingest_tamara_investor_pack.py` in the mixed working tree. Cleaned up via selective `git add` + stash push/pop dance across 3 branch switches.

---

## 2026-04-24 — Doctrine revision that lands in the framework doc must propagate to the UI + compute declarations in the same landing

**Problem:** Session 35 codified §17 "Dual-view pattern taxonomy" arguing Pattern 1 (active-primary) applied to lending products (SILQ) and Pattern 2 (parallel-equal) applied to factoring (Klaim). Session 35's SILQ PAR fix implemented Pattern 1 exactly. Session 36 user review said: "flip it; lifetime-primary across all companies." The fix required touching 4 surfaces to stay coherent:

1. `core/ANALYSIS_FRAMEWORK.md` §17 — revise the taxonomy subsection.
2. `core/FRAMEWORK_INDEX.md` Core Principles — add new "Credit Quality PAR: lifetime-primary universal" principle, renumber subsequent.
3. `frontend/src/pages/TapeAnalytics.jsx` (SILQ + Klaim sections) + `AajilDashboard.jsx` — flip value/subtitle/section-label in every Credit Quality KPI card.
4. Backend compute functions — already emitted both populations; no change needed (the doctrine revision changed which one the UI selects as headline, not which the backend computes).

Missing any one of the four creates analyst confusion: framework doc says lifetime but UI shows active, or UI flipped but framework still argues for Pattern 1. Session 36 landed all four in one cohesive series (`7d68c9c` docs, `4a43f02` UI) within the same PR branch.

**Rule:** Framework doctrine changes are inseparable from their implementation surfaces. If you can't update all of (doctrine doc + index + UI + compute contracts) in the same landing, don't ship the doctrine change alone — the drift between doc and implementation is worse than the old doctrine being suboptimal.

**How to apply:**
- When proposing a framework revision, enumerate the surfaces it will touch BEFORE committing to the revision. If the implementation churn is too large, negotiate scope with the user first — maybe a narrower revision is enough.
- When implementing a framework revision, land the doctrine + implementation in the same branch (not separate PRs); reviewers should see the whole story in one diff.
- Framework §17 has two "kinds" of subsections: normative doctrine (principle propagation, pattern taxonomy) and descriptive taxonomy (the 7 populations). Normative changes need implementation churn; descriptive additions usually don't.
- Reference: session 36 `7d68c9c` + `4a43f02` landed the §17 pattern-taxonomy revision AND the UI flip in sequential commits on the same branch, merged as a single coherent unit to main.

---

## 2026-04-24 — Build walkers before eyeballing audits; per-company audits miss cross-company propagation

**Problem:** Session 34 Framework §17 audit enumerated gaps company-by-company from tables I built by hand. After the sweep I declared it complete with 0 regressions and 0 new gaps surfaced. The user then pointed at the SILQ Credit Quality dashboard and asked: "why is PAR only shown vs Active Outstanding here, when the same dual was added for Aajil?" The SILQ PAR dual-view miss was visible to a human staring at the UI but invisible to my manual per-company walkthrough.

Session 35 built a systematic walker (`tests/test_population_discipline_meta_audit.py`) that introspects every compute function's return dict and flags rate-like fields without §17 disclosure. **First run found 45 gaps** across Klaim/SILQ/Aajil — an order of magnitude more than I would have enumerated by eye. Fixed all 45. Walker now runs on every test pass, so future sessions can't quietly reintroduce gaps.

**Rule:** When a platform-wide discipline is declared (every metric must carry X + Y), write the walker FIRST. Manually enumerated audits systematically miss cross-company propagation because human attention is per-company, not per-pattern.

**How to apply:**
- For any new platform-wide contract (§17 population/confidence, audit trail fields, covenant EoD history, etc.), build a walker as the FIRST commit, not the last. The walker's output becomes the audit gap list.
- Walker structure: introspect returns from every compute function against a minimal synthetic tape, walk the top-level dict, apply heuristics for "fields that need the contract" (name patterns + value-range checks for rate-likes), report findings with function + field names so the fix target is obvious from CI output.
- Add the walker BEFORE touching any compute function. Run it to generate the gap list. Then fix. The first fix commit has the walker passing, subsequent commits keep it passing.
- Reference: session 35 walker surfaced 45 gaps; manual audit (session 34) missed the SILQ PAR / SILQ delinquency / Aajil summary collection_rate / cdr_ccr portfolio / stale_exposure zombie_subset / stress_test recovery / cohort_loss_waterfall totals gaps. Every one of those would have been a "user finds it in production later" moment.
- Corollary for propagation tests: when a dual-view exists on company A, write a propagation test that asserts the same dual exists on B, C, D. Session 35's `TestMetaAuditDualPropagation` is the pattern. Locks in "if you added it for A, you MUST add it for B before CI passes."

---

## 2026-04-24 — Summary fns must mirror compute fns on dual-view surfaces

**Problem:** Session 34 P1-4 added 3-population collection rate dual to `compute_aajil_collections` (blended + realised + clean). But `compute_aajil_summary` kept only the blended `collection_rate`. Analyst reading the Overview card saw the ambiguous blended view; only analysts drilling into the Collections tab saw the population-honest duals. Surfaced by session 35 walker.

**Rule:** If a compute function gains a dual view, the summary function (if any exists) MUST surface the same dual. Overview cards are the analyst-facing layer; detail pages are the implementation layer. Both need the dual for the analyst to see it.

**How to apply:**
- When adding `<field>_realised` / `<field>_clean` / `<field>_lifetime` to a compute_X fn, grep the codebase for `compute_X_summary` (or `compute_{type}_summary` for read-only types) — if it exists and cites the base `<field>`, add the duals there too.
- Add a propagation test: given a metric exists in both places, assert both places have the dual.
- Reference: session 35 `TestMetaAuditDualPropagation.test_summary_collection_rate_dual_consistency` for the pattern. Aajil gap caught, fixed in `compute_aajil_summary` to now return `collection_rate` + `collection_rate_realised` + `collection_rate_clean` + the three populations.

---

## 2026-04-24 — Three dual-view patterns, not one; pick the right one per asset class

**Problem:** Session 34 implemented dual-view PAR differently across asset classes:
- Klaim: lifetime as primary, active as secondary (IC view dominates)
- Aajil: active install-count as primary + par_primary (days-based) as fallback + lifetime as alternate
- SILQ (session 35 fix): active as primary, lifetime as context

All three are correct for their asset class. But there was no codified guide for which pattern to pick. Next onboarding would have guessed.

**Rule:** Three dual-view patterns exist, each for a specific asset-class economic context:
- **Pattern 1 — Single-primary + context** (lending-style): active pool IS the live book, so active is primary; lifetime is sanity-check context. Example: SILQ PAR, Aajil Operational WAL.
- **Pattern 2 — Parallel-equal** (factoring-style): active is covenant-bound, lifetime is IC-bound, neither dominates. Both headline. Example: Klaim PAR.
- **Pattern 3 — N-way comparison** (yield-style): 3+ populations each answer a distinct question. Example: Aajil yield (blended/realised/active), Aajil collections (blended/realised/clean).

**How to apply:**
- At onboarding time, declare the asset-class economics in `config.json` (lending / factoring / yield-style / read-only).
- Pick the dual-view pattern that matches.
- Framework §17 "Dual-view pattern taxonomy" subsection (session 35 addition) codifies the when-to-use guidance.
- Reference: `core/ANALYSIS_FRAMEWORK.md` §17 after "Backwards compat for dual-view rollout" / "Principle propagation discipline" / "Dual-view pattern taxonomy" — codified during session 35.

---

## 2026-04-24 — Audit-first, implement-second: turn ambiguity into doctrine BEFORE the code changes, not after

**Problem (inverted, i.e. what went right worth codifying):** Session 30 surfaced Klaim WAL as having four legitimate values (148d Active / 137d Total / 79d Operational / 65d Realized), each answering a different question. The impulse is to pick one, call it "WAL", and move on. The better move — which session 34 took — was to pause, audit every compute function across all 5 companies for the same class of population-mismatch problem, draft a Framework section capturing the doctrine, and only THEN implement. The audit report predicted 6 P0s, 8 P1s, 5 P2s, 3 UNCERTAINs; the implementation found exactly those, plus zero new gaps. That's the signal the audit was worth doing.

**Rule:** When one instance of a structural pattern surfaces (e.g., "this metric has two legitimate populations"), assume the pattern recurs. Build an audit pass over the similar surface area BEFORE fixing the one instance. The audit report becomes the implementation checklist + the Framework doctrine draft + the promotion blocker for the Mind candidate entry that captured the pattern in the first place.

**How to apply:**
- When a Mind entry is marked `codification_status: "pending_second_data_point"`, THAT is your signal to run the cross-company audit that promotes it. Don't keep accumulating instances — promote once the second case is documented.
- Audit artifact structure: per-company tables (function / numerator / denominator / population / confidence / dual-view-available / gap-flag), ranked gap list (P0 correctness / P1 missing views / P2 cleanup / UNCERTAIN user-review), doctrine draft as markdown, Mind-entry replacement text. All in one commit as `reports/{topic}_audit_{date}.md`, then the implementation sweep works the audit as its TODO.
- Doctrine codification happens in the SAME sweep as the fixes — don't split "implement the fixes" from "update the Framework". If a P0 required the doctrine to exist (e.g., "every covenant must declare confidence"), the doctrine addition goes ahead of the fix in the commit sequence, not afterward.
- See `reports/metric_population_audit_2026-04-22.md` + the 23-commit sequence `4e14b59..cce1c9b` as the reference pattern. 5,296 lines of diff, 135 new tests, 0 regressions at every commit, 0 new audit gaps surfaced during implementation — the audit was a good predictor because it was done at the right level of detail BEFORE coding began.

---

## 2026-04-24 — Data transmission + prompt instruction must land in the same commit, not sequentially

**Problem:** Adding a new field to a compute output dict is only half the work. If downstream consumers (memo prompts, AI chat context, Intelligence System) don't know the field exists, the information never reaches the reader. Session 34 added `confidence` + `population` to every covenant dict in the first sweep but didn't touch the memo prompt or the analytics_bridge. Result: memos generated BEFORE the prompt+bridge commit never cited confidence grades; memos AFTER do. Analysts reading archived memos from the window between the two commits get a degraded experience. The fix is to land data + consumer in the SAME commit or a back-to-back pair, with tests asserting the field flows from compute output → bridge → prompt surface.

**Rule:** For any new dict field meant to be analyst-visible, the same commit (or a tightly-coupled pair) should include:
1. The compute function change that emits the field.
2. At least one consumer change (prompt text, bridge transformation, UI component prop) that renders or cites the field.
3. A regression test asserting the consumer reads the field correctly.

If these land across commits separated by hours or days, the window of "archived memos / cached AI outputs that don't cite the new field" is a silent data-consistency problem — worse than not having the field at all, because it creates two vintages of output with the same timestamp.

**How to apply:**
- Before adding a new dict field, grep for callers: `grep -rn "\[.covenant.\]" backend/ core/` (or similar). If callers exist, plan the consumer change alongside.
- In the commit message, explicitly list the end-to-end flow: "compute output → analytics_bridge → memo prompt → UI badge". If you can't describe all four points, you're missing wiring.
- When back-to-back is unavoidable (e.g., frontend + backend in different repos), ship a no-op renderer first (field present but hidden), then enable rendering in the second commit. This way the audit trail shows both states have the field, not just post-render.
- Reference: session 34 Step 6 commit `6896d91` bundled the memo prompt + analytics_bridge + tests in ONE commit explicitly because prior confidence-grading commits had deferred that wiring. Lesson reinforces: if I had wired it in the initial sweep (commit `a4d0d34`), there'd be no "generate a pre-commit memo to reproduce" debugging surface later.

---

## 2026-04-24 — Every dict-level discipline (confidence grading, population codes) needs a meta-test walker

**Problem:** Framework §10 declared confidence grading mandatory but only Klaim WAL actually shipped the grade on its output dict. The bug existed for 14+ months because no test asserted "every covenant has a confidence field". Session 34 added `test_population_discipline_guard.py` — a meta-test that walks every covenant and concentration-limit dict emitted by the 4 compute functions and asserts the §17 contract. If a new covenant lands without the fields, the test fails with the covenant name in the error message. This is the discipline-enforcement mechanism that was missing.

**Rule:** For any platform-wide structural discipline (confidence grading, population declaration, audit trail fields, etc.), write a meta-test that walks the surface and asserts the contract. Meta-tests that grep/iterate the codebase or runtime outputs are the insurance policy against "we have the rule documented but no enforcement".

**How to apply:**
- Meta-test pattern: iterate over every element of a known structure (covenant list, compute function registry, etc.) and assert each element satisfies the contract.
- Include helpful error messages — `assert 'confidence' in cov, f"Covenant '{cov['name']}' missing 'confidence'"`. The engineer reading the CI failure needs to know WHICH covenant broke the contract.
- Pin frozen contracts: the set of allowed values (e.g. `{'A', 'B', 'C'}`), the method→confidence mapping, the taxonomy prefix set. Lock these in via explicit `assert == frozenset(...)` so any new code adding a value must explicitly vote the new value in.
- Run the meta-test before the prose rule in code review. A "discipline" documented only in CLAUDE.md or a Framework section will drift; a meta-test in CI can't drift without someone explicitly removing it (and reviewers see the removal).
- See `tests/test_population_discipline_guard.py` for the reference pattern.

---

## 2026-04-22 — Container and host are separate filesystems — installing a dep on one doesn't install it on the other

**Problem:** Deploy today surfaced a Playwright "host system missing libxfixes3" warning during the backend container build. I ran `apt-get install libxfixes3` on the prod host and declared the issue fixed. Then — confidently but incorrectly — I said "the backend container image already has libxfixes3 from the earlier rebuild" when the same warning fired again on the next deploy. User ran `docker exec credit-platform-backend-1 ldconfig -p | grep libxfixes` which returned empty — the container was still missing the library despite the host install. The real fix was adding `libxfixes3` to `docker/backend.Dockerfile`'s apt install list, rebuilding the image, redeploying. Two confident wrong answers from me in one sequence; the actual root cause was a basic confusion between host and container dependency scopes.

**Rule:** Containers have their own filesystems. Installing a system library on the host (`apt-get install` on the VM / bare metal) does NOT make that library available to processes running inside containers. Processes inside a container only see the union of (a) the container image's layers, (b) mounted volumes. Host-level system libraries are invisible unless explicitly bind-mounted (unusual and fragile). For any missing-runtime-library failure inside Docker, the fix belongs in the Dockerfile, not on the host — unless there's a specific reason the dep needs to be usable by host-level processes too.

**How to apply:**
- When debugging "X library missing" errors that manifest inside a container, verify AT THE CONTAINER LEVEL first: `docker exec <container> ldconfig -p | grep -i <libname>`. Do NOT verify at the host level (`apt list --installed | grep <libname>` on the host) — that tells you about the host, not the container, and gives false confidence.
- When the verification reveals the library is absent from the container, the fix goes in the Dockerfile's `RUN apt-get install -y ...` list. Rebuild the image (via `docker compose build` or a full deploy), then re-verify at the container level.
- A host-level `apt-get install` of the same library is only useful if (a) a non-containerized process on the host also needs it, or (b) the container bind-mounts host `/usr/lib` (unusual). Neither applies for a typical Playwright-in-container setup.
- `grep` is case-sensitive by default. X11 libraries use mixed case (`libXfixes`, `libXrandr`, `libXcomposite`) while Debian package names use lowercase (`libxfixes3`, `libxrandr2`, `libxcomposite1`). Use `grep -i` when searching ldconfig output against package names, or you'll get a false-empty result like I did today even after the library was correctly installed.
- Symptom in the wild: a missing-library error that keeps recurring after each deploy despite "fixing" it. Nine times out of ten this means you're fixing the host or installing the lib in the wrong image stage. Trust `docker exec <container>` over anything else — the running container is the only source of truth for what the running container sees.
- See `docker/backend.Dockerfile` commit `78c6f81` for the Playwright-specific fix pattern (list libxfixes3 alongside the other Chromium deps in the RUN apt-get install line).

---

## 2026-04-22 — Directory-level .gitignore + pre-existing tracked files = ambiguous state; split the policy explicitly

**Problem:** `.gitignore` had `data/_master_mind/` as a blanket exclude, but 4 files in that directory (`framework_evolution.jsonl`, `ic_norms.jsonl`, `preferences.jsonl`, `writing_style.jsonl`) were already tracked from before the rule was added. Git's tracking-precedence kept them tracked, so commits succeeded — but every `git add` emitted "the following paths are ignored" warnings, and any analyst following the warning at face value would assume the file wasn't being committed. Session 30's Framework codification candidate commit hit this and only worked because the committer ignored the warning. A different analyst could easily have fought the gitignore ("why won't git add my file?") or, worse, `git rm --cached`'d the tracked files to "fix" the warning — breaking every other machine that pulls main.

Content-model check after the fact confirmed the tracked files were CORRECTLY tracked: Master Mind JSONL entries are self-contained text records (Framework candidates, IC norms, fund preferences, writing style) with no UUID pointers to per-machine stores. They're institutional knowledge that should converge across machines. The `.gitignore` line was written at a time when Master Mind was expected to be per-machine (like Company Mind), but that assumption never held.

**Rule:** When a directory has mixed content — some files meant to be tracked, some per-machine state — a single directory-level rule is always ambiguous. Either:
1. Split the per-machine content into a clearly-named sibling directory (e.g., `data/_master_mind/` shared + `data/_master_mind_local/` per-machine), and gitignore the sibling; OR
2. Keep the directory shared by default (no rule) and add specific sub-path exclusions for any per-machine files that land inside.

Pick option 2 unless the per-machine content is going to dominate — the shared-by-default posture matches git's own conventions (tracked unless proven otherwise).

**How to apply:**
- Before writing a `data/X/` rule, ask: does EVERY file that could land in this directory share the same tracking policy? If no, use specific sub-paths.
- Before writing a rule for a directory that already contains tracked files, run `git ls-files <dir>` — if the output is non-empty, the rule is mis-scoped. Either keep those files tracked and narrow the rule, or untrack them explicitly with `git rm --cached` in the same commit (surfaces the intent, avoids the "ignored but tracked" trap).
- The content-model question to ask before deciding: does this file reference UUIDs / state that only exists locally (relations.json → entities.jsonl IDs, for example)? If yes, per-machine. If no, shared.
- For existing ambiguous state: don't retroactively `git rm --cached` files that have propagated across machines — it breaks everyone's local state. Clarify the rule instead.

---

## 2026-04-22 — Semantic upgrades to compute-function outputs need cross-file test grep, not just in-module

**Problem:** Task #2 (curve-based close-age fallback) legitimately upgraded the `wal_total_method` tag from `collection_days_so_far` to `collection_days_so_far_with_curve_fallback` when curves fill gaps for any completed-deal row. The implementer added tests for the new tag in `tests/test_analysis_klaim.py` (their scope) and verified 97 Klaim tests green locally. But a Session 31 test in a DIFFERENT file (`tests/test_db_snapshots.py::TestSnapshotIsolation::test_apr15_wal_total_resolves_mar3_wal_total_is_none`) was pinned to the OLD exact-string value via `assert apr_wal['wal_total_method'] == 'collection_days_so_far'`. Task #2's own suite passed; the cross-file pin only fired at merge time when the full `pytest tests/ -q` ran on integrated main. One-line fix (`in ('old_value', 'new_value')`) but a preventable friction.

**Rule:** When a compute function's output contract changes even in a strictly additive / semantically-upgraded way (new tag value, new optional field, wider enum set), the implementer must grep the WHOLE test tree for hardcoded assertions against the old value — not just within the module's own test file. Pinned string/enum assertions in cross-module tests are the most common failure mode because they're out of the implementer's mental model of "my scope".

**How to apply:**
- When a spawned task prompt involves "add a new value to an enum" / "add a new method tag" / "return a new optional field", explicitly instruct the implementer to run `git grep -n "<old_exact_value>"` across `tests/` as part of their pre-commit check. Not just `pytest tests/test_<mymodule>.py` — the full `pytest tests/ -q` on their worktree.
- If they find pinned assertions in other test files, the fix is usually accepting both old + new values (set-membership check) rather than flipping the assertion to the new value — keeps the regression guard alive for any code path that still legitimately emits the old value (e.g. older tapes without the new column).
- If the prompt's "don't modify other modules" guardrail would prohibit that fix, the implementer should flag it in their summary as a known test-catchup task rather than silently leaving a future merge-time failure.
- Verification at merge: always run the FULL `pytest tests/ -q` after each task merges before moving to the next. We did this today; it caught the pinned assertion at task #2 merge and prevented it from compounding under tasks #3/#4/#5.

---

## 2026-04-22 — `git` 3-way merge collapses identical prologues across parallel additions, synthesising mixed conflicts

**Problem:** Tasks #3 and #4 both added new FastAPI endpoints at the same region of `backend/main.py` in their respective branches. Each endpoint had an identical 4-line prologue (`df, sel = _load(company, product, snapshot); df = filter_by_date(df, as_of_date); config, disp = _currency(company, product, currency); mult = apply_multiplier(config, disp)`). When merging task #4 after task #3, git's 3-way merge saw the prologue as "unchanged" in both branches and collapsed it into a single copy — then flagged the DIFFERENT docstring+signature above and the DIFFERENT `return` statement below as conflicts. The resulting conflict region looked mangled: `<<<<<<< HEAD` (task #3's `cash-duration` signature + docstring), then `=======`, then task #4's `operational-wal` signature, then `>>>>>>>`, then the SHARED prologue (only one copy of it), then another conflict block for the return statements. Naively resolving by picking one side would silently drop one endpoint's function body or merge them into a Frankenstein function with the wrong signature.

Correct resolution: rewrite the region so each endpoint has its OWN complete function body with its OWN prologue. Three endpoints, three prologues, no shared lines.

**Rule:** When git reports a conflict that includes "auto-merged" shared context lines between conflict markers in adjacent regions, don't trust the structure git produced — read the FULL function(s) the conflict sits inside and rewrite as if you were authoring the intended final state directly. For function-level additions where each branch contributed a full new function that happens to share prologue/epilogue patterns, the resolution is always "N independent complete functions", never "one blended function with interleaved pieces".

**How to apply:**
- Detect the shape early: if a conflict region inside a `.py` file has MULTIPLE conflict marker pairs separated by a few lines of non-marker code, and the non-marker code looks like it could appear in either branch's function body (because it's identical stock boilerplate), assume git mis-collapsed a shared prologue. Read the function boundaries (start of `def` to next `def` or blank line) on BOTH branches via `git show <branch>:<file>` to see what the intended function bodies are.
- Resolution strategy: don't edit inside the conflict markers. Delete the entire conflicted region, then paste in N complete intended functions side-by-side, each with its own full body. Remove the markers. Re-verify with `grep -n '<<<<<<<\|=======\|>>>>>>>' <file>` returning empty.
- When spawning parallel tasks that will add new endpoints / new routes / new test classes to the same files, warn the implementers in the prompt that the merge will likely conflict in those regions and document the expected resolution pattern (both blocks kept, adjacent, each complete).

---

## 2026-04-22 — Ask "is this latent elsewhere?" BEFORE fixing a user-reported bug

**Problem:** User reported Aajil Executive Summary rendering raw markdown instead of structured narrative. My instinct was to fix the specific symptom — hardened the sync-path prompt and JSON parser. That shipped. Then the same user saw a new failure mode, then another, then another. Each fix exposed the next layer:

1. Markdown dump (fix: JSON contract in prompt)
2. Truncated JSON (fix: bump max_tokens from 2000 to 16000)
3. Generic "Stream ended without a result" (fix: propagate runtime errors into terminal done)
4. "3 consecutive tool errors" (fix: add Aajil branches to 2 more unguarded tools)

Four round-trips, four deploys, user burning time each cycle. The real failure was my scope discipline: I fixed what the user reported instead of asking "what class of bug is this, and where else could it live?"

When the user explicitly asked "are these issues Aajil specific?" after seeing the fixes work, I traced the answer — 6 of 7 content issues were prompt-level, affecting every company. Klaim and SILQ hadn't surfaced them only because their tool coverage was fuller, leaving less room for agent drift. Had I asked that question on the first round, I would have audited ALL tool dispatch tables for ALL analysis_types in one pass instead of discovering gaps one at a time through user friction.

**Rule:** When a user reports a bug, before writing the fix, spend one think-cycle on:
1. **What's the class of bug?** (signature mismatch, silent fallback, unguarded assumption, ...)
2. **Where else does this class of bug live?** (grep for the same pattern, audit sibling functions)
3. **Would a fuller audit ship in the same round?** If yes, do it. One deploy instead of four.

**How to apply:**
- Never fix only the specific file the user named. Grep for the pattern across the codebase first.
- Write the audit into the plan, not as follow-up. "Fix DSO tool for Aajil" is incomplete; "audit all load_tape() call sites for every analysis_type" is the work.
- When presenting the fix, explicitly name what's platform-wide vs what's case-specific. Don't let the user discover it three iterations later.

---

## 2026-04-22 — Parse-failure fallbacks must render as failure, never as success

**Problem:** Sync-path `/ai-executive-summary` endpoint tried `json.loads()` on the agent's response. On failure it wrapped the raw text as a single finding with `severity='positive'` and `title='Agent Summary'`. The frontend rendered this as a **teal POSITIVE card** with the entire markdown dump as the "explanation". To the analyst, it looked like a successful output — they had no signal that parsing had failed. They kept clicking Refresh (which re-read the same bad cache) until someone spotted the broken rendering.

```python
# Original — looks harmless, is catastrophically misleading:
except (json.JSONDecodeError, AttributeError):
    findings = [{'rank': 1, 'severity': 'positive', 'title': 'Agent Summary',
                 'explanation': summary_text, ...}]
```

The severity and title were inherited by copy-paste from a debug placeholder. Nobody verified what they rendered as. Teal POSITIVE + "Agent Summary" + 40KB of raw markdown in the explanation field = the exact output an analyst would least suspect of being broken.

**Rule:** Every fallback path for "we couldn't parse/compute/fetch what the user asked for" must be visually distinct from a successful response. Parse failures are `severity='warning'` at minimum (never 'positive', never 'success'), title names the failure mode ('Summary generated (unparsed)', not 'Agent Summary'), body quotes the raw response verbatim for analyst debugging.

**How to apply:**
- When you see `severity='positive'` or `status='ok'` inside an `except:` or fallback branch, that's the bug. Fix the severity to match the actual state.
- For UI renderers that key on severity/status, do a visual smoke test of every fallback path — does the "couldn't parse" fallback look distinguishable from a real success? If not, the semantic label is wrong.
- Write a test: `test_severity_never_positive_on_failure` (now in `tests/test_exec_summary_stream.py::TestParseAgentExecSummaryResponse`). Lock the contract.

---

## 2026-04-22 — Agent tool dispatch must be audited against every analysis_type, not just the "primary" one

**Problem:** The analyst agent has ~20 analytics tools in `core/agents/tools/analytics.py`. Each was written with Klaim in mind; some gained SILQ branches later; Aajil was added most recently. Only SOME tools got Aajil branches during onboarding — the others silently fell into their `else` branches which called `load_tape()` (Klaim-shaped CSV loader). When the agent is given a narrow task, it only calls a few tools and the gaps are invisible. The Executive Summary — which calls the agent with `max_turns=20` and instructions to pull data for 9 sections — is the stress test. It calls every tool. Gaps compound: two or three unguarded tools crash in a row, runtime's "3 consecutive errors → stop" circuit breaker fires, the whole response aborts with no data.

Four tools were unguarded on Aajil, discovered over two audit rounds:
- `_get_covenants` (imported nonexistent `compute_aajil_covenants`)
- `_get_deployment` (grouped by nonexistent `Month` column)
- `_get_ageing_breakdown` (filtered by nonexistent `Status='Executed'`)
- `_get_dso_analysis` + `_get_dtfc_analysis` (metrics genuinely Klaim-specific; crashed on column assumptions)

The first three were caught on pass one. The last two were only surfaced after error propagation was fixed and the "3 consecutive tool errors" message became visible. If I had audited ALL `load_tape()` call sites in pass one (there are 19), I would have found them.

**Rule:** When adding a new `analysis_type` to the platform, audit every tool dispatch helper in `core/agents/tools/` against the new type. Checklist in CLAUDE.md under "Agent Tool Coverage Checklist".

**How to apply:**
- Grep for `load_tape\(` across `core/agents/tools/` and verify every call site has an early-return guard OR a company-specific branch before it.
- Graceful-skip strings must NOT start with `Error:` or `Tool error` — the runtime counts those toward the 3-errors circuit breaker (`core/agents/runtime.py:470`). Lead with "X not available for analysis_type=Y — try Z instead".
- Write a regression test class per analysis_type in `tests/test_agent_tools.py` — pin the graceful-skip contract for every tool handler.
- Before declaring a new company onboarded, run a full Executive Summary end-to-end — it exercises ~12 tools in one go. If the agent bails with "3 consecutive tool errors", you have coverage gaps.

---

## 2026-04-22 — `max_tokens_per_response` defaults guard cost, not output size — structured JSON needs explicit bumps

**Problem:** `core/agents/definitions/analyst/config.json` sets `max_tokens_per_response: 2000`. This was fine for commentary, tab insights, chat — all short-form prose. When the Executive Summary endpoint started asking the same analyst agent for structured JSON with 6-10 narrative sections, a summary table, a bottom line, and 10 findings, the response easily exceeded 8K tokens. Output truncated mid-string (observed: response ended at `"assessment":` inside a metric object), leaving unparseable JSON. Symptom was "WARNING / Summary generated (unparsed)" even though the agent had finished its reasoning and was successfully writing the JSON.

Worth noting: Claude bills on actual output tokens, not budget. Raising `max_tokens` from 2000 to 16000 costs nothing unless the model legitimately fills the extra space. The default is conservative to cap runaway costs on buggy prompts, not to constrain legitimate long-form output.

**Rule:** `max_tokens_per_response` is a cost guard, not a correctness knob. Structured output (JSON with nested arrays) needs headroom proportional to schema complexity. Budget ~500-1000 tokens per top-level object and error on the high side.

**How to apply:**
- For any agent call producing structured JSON with N sections × M fields, estimate: `total_tokens ≈ sections × fields × 50`. For exec summary (10 × 15 × 50 ≈ 7500), 16000 is safe headroom.
- Override per-call using `_run_agent_sync(..., max_tokens_per_response=16000)` or `config.max_tokens_per_response = 16000` — don't change the global default.
- Test failure mode: if you see JSON ending at a mid-field `"key":` position, it's truncation not agent error.

---

## 2026-04-22 — Button labels must describe the action, not imply a semantic that contradicts it

**Problem:** ExecutiveSummary.jsx has two buttons side-by-side: a small "Regenerate" (outline) and a gold "Refresh" (prominent). User clicked "Refresh" expecting fresh output; got the same stale cached result. The code:

```jsx
<button onClick={() => generate(true)}>Regenerate</button>    // ← refresh=true, busts cache
<button onClick={() => generate(false)}>Refresh</button>      // ← refresh=false, serves cache
```

The labels mean the opposite of what a user expects:
- "Refresh" in every other UI means "re-fetch fresh data"
- "Regenerate" is the explicit cache-bust action here, but it's the smaller/less-prominent button

User clicked the prominent gold button labeled "Refresh" three times during debugging before I noticed the label contradiction. Each click silently served the same cached bad output. If either button had been labeled correctly, we would have saved two deploy cycles.

**Rule:** Button labels must describe the literal action. "Refresh" should always re-fetch or re-compute. If you have both a cache-read and a cache-bust action, label them differently ("Reload from cache" / "Regenerate") or collapse to one button that always busts cache when explicitly clicked.

**How to apply:**
- When a button controls cache state, verify its label matches the cache action it takes.
- If the UI has a "prominent" CTA button, it should do the thing users most-likely want. For stale-result screens, that's usually cache-bust.
- Consider swapping the visual prominence: make the cache-bust button gold/primary, the cache-read button secondary or hidden entirely.
- (Follow-up for this platform: swap the labels or collapse to one "Regenerate" button on ExecutiveSummary.jsx. Tracked as a UX nit, not a bug.)

---

## 2026-04-22 — Sync client in an async SSE endpoint freezes the whole event loop

**Problem:** First cut of `get_executive_summary_stream` in `backend/main.py` ran the agent's async generator inline in the asyncio task:

```python
async def _producer():
    async for event in runner.stream(prompt, session):  # <-- blocks event loop
        await queue.put(event)
```

Browser test on Aajil: stage stuck at "Starting…" for 83s while the elapsed counter kept ticking. Backend log showed tool calls actually executing (agent was alive and burning Claude turns). But ZERO events reached the client until that first Claude turn's HTTP socket finally freed. Heartbeats also never fired — the 20s `: keepalive\n\n` emitter never got a chance to run. Even `/health` on the same uvicorn instance timed out while a stream was in flight.

Root cause: `AgentRunner.stream()` is declared `async`, but its hot path is `with self._get_client().messages.stream(...)` which is the SYNC Anthropic client. Sync httpx call = blocks the thread until the first response byte arrives. In an async handler on a single-worker uvicorn, that's the entire event loop. Producer can't yield, consumer can't drain, heartbeats can't fire, other requests stall.

**Why I didn't spot it sooner:** `backend/agents.py::_stream_agent` uses the same `async for event in agent.stream(...)` pattern AND works in production. I copied that pattern thinking it was correct. But memo and analyst endpoints run at CF-proxy scale where a burst of concurrent requests masks single-request event-loop starvation, and their agent calls are shorter (<30s, no heartbeat needed). Aajil's exec summary with 20-turn cap + broken tools = the degenerate case that exposes the latent bug. The fix already existed in the codebase — `memo_generate_stream` offloads its pipeline to a `ThreadPoolExecutor` and uses `loop.call_soon_threadsafe` to push progress events back — but the analyst/stream endpoint had quietly been shipping the broken pattern.

**Fix:** Run the async generator in a dedicated thread with its own event loop, push events back to the main loop's `asyncio.Queue` via `loop.call_soon_threadsafe`:

```python
loop = asyncio.get_event_loop()
stop_event = threading.Event()

def _thread_push(item):
    try:
        loop.call_soon_threadsafe(queue.put_nowait, item)
    except RuntimeError:  # loop closed — client gone
        pass

def _producer_thread():
    t_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(t_loop)
    try:
        async def _drain():
            async for event in runner.stream(prompt, session):
                if stop_event.is_set():
                    break
                _thread_push(event)
        t_loop.run_until_complete(_drain())
    finally:
        _thread_push(SENTINEL)
        t_loop.close()

threading.Thread(target=_producer_thread, daemon=True).start()
```

After the fix: first tool_call event reached the browser at 00:06. 15+ stages rendered live during a 4m24s run — well past CF's 100s cap that produced the original 524.

**Rule:** If an async generator touches ANY synchronous I/O (sync HTTP client, sync DB driver, blocking C extension), it CANNOT be awaited inline in a FastAPI async handler. Offload to a thread. Treat the rule as binding for any agent/streaming endpoint that uses the `anthropic.Anthropic` (sync) client rather than `anthropic.AsyncAnthropic`.

**How to apply:**
- When adding a new SSE endpoint that runs an agent or any `anthropic.Anthropic` call: use the thread-offload pattern from `memo_generate_stream` OR the one documented above for `get_executive_summary_stream`. Never `async for event in runner.stream(...)` directly in an asyncio task.
- `backend/agents.py::_stream_agent` is currently using the broken pattern — it works in the common case because analyst/compliance runs are short, but a long one will starve the event loop. Follow-up: refactor it to the same thread-offload pattern as a preventative fix.
- When debugging "stream shows X for Y seconds then resumes" or "heartbeat never fires", check whether a sync call sits inside an async generator somewhere in the call chain. Event-loop starvation always looks like batched, bursty output.
- Browser-side elapsed counters / connection-alive indicators lie about this. They're driven by `setInterval` in the client, not server byte flow. The only honest server-liveness signal is "did a new event or comment line arrive in the network tab?" — verify via Chrome DevTools → Network → response stream, not by watching the UI clock tick.

---

## 2026-04-22 — Runtime-written state files must be gitignored, not committed

**Problem:** Session 31 EoD committed `data/klaim/UAE_healthcare/covenant_history.json` and `data/klaim/mind/relations.json` (in commit `4b05dcc` — "chore: runtime side-effects"). My reasoning was: "they're tracked files dirty in the working tree; EoD says commit the data artifacts; so commit them." First prod redeploy after the push failed:

```
error: Your local changes to the following files would be overwritten by merge:
    data/klaim/UAE_healthcare/covenant_history.json
    data/klaim/mind/relations.json
Please commit your changes or stash them before you merge.
Aborting
```

Root cause: these are runtime-written state files. The backend appends to `covenant_history.json` on every `/portfolio/covenants` call (for EoD-consecutive-breach tracking per MMA 18.3). The intelligence event-bus writes `relations.json` on every `TAPE_INGESTED` / `DOCUMENT_INGESTED` event. Laptop and prod write their own histories from their own backend traffic — the two diverge continuously. A commit of either machine's version is semantically meaningless (not a source change) AND guaranteed to collide with the other machine's local state.

These files had been historically tracked (pre-`.gitignore`-discipline era), which is how I got tricked into treating them as content rather than state. `.gitignore` already excluded the analogous cases (`ai_cache/`, `_master_mind/`, `_platform_health.json`) — these two were just never ported over.

**Rule:** If a file gets written by the backend process at runtime (even once, even via rare append), it must be gitignored. It doesn't matter that it's currently "tracked" in git's eyes — being previously-committed is a bug to fix, not a reason to keep committing. Every machine keeps its own copy; no version is canonical.

**How to apply:**
- When EoD inventories dirty files, test each one with "is this file modified by the running backend on its own, without a human edit?" If yes, gitignore + `git rm --cached`.
- When adding a new sidecar storage file (covenant history, relation graph, cache, audit log, index, health probe), add it to `.gitignore` IN THE SAME COMMIT that introduces the write. Don't wait for an EoD to catch it.
- Existing lesson on the opposite pattern (2026-04-21, "Tape files don't deploy with git") covers manual-only files that NEED manual sync. This lesson covers the inverse — automatic-write files that MUST NOT be synced.
- Pattern cleanup in commit `f0e35b9` — `data/*/*/covenant_history.json` and `**/mind/relations.json` added to `.gitignore`; three files `git rm --cached`'d. Prod recovery required a cp-backup / pull / cp-restore dance to preserve real production evaluation history.

---

## 2026-04-22 — Silent data-source routing betrays every downstream consumer

**Problem:** `backend/main.py::_portfolio_load` silently preferred the DB path whenever `has_db_data(db, co, prod)` returned True, with zero indication to the caller. In every session after the one-time `scripts/seed_db.py` run, the backend was serving stale Mar-3-vintage DB data for Klaim even though:
- The Apr 15 tape file was on disk with all 65 columns.
- The snapshot dropdown in the UI let the analyst pick "2026-04-15".
- The response JSON dutifully echoed `snapshot: 2026-04-21` (from `sel['date'] = datetime.now()`).
- The "Tape Fallback" badge continued to say "Tape Fallback" while DB was the actual source.
- The DB had no snapshot dimension — `invoice_number` uniqueness was global, so the same ID couldn't exist in multiple snapshots anyway; there was only ever one "current state" per product.

The bug surfaced only when a covenant-card rendering fix triggered a closer look at the returned numbers. Apr 15 WAL was 183d / Breach instead of the expected 148d / Path B. The delta was four compounding silent failures: (1) snapshot param ignored, (2) `sel['date']` defaulted to today, (3) `db_loader` mapped only the Sep-2025 column set (dropped `Expected collection days`, `Collection days so far`, `Provider`), (4) UI badge hid the routing decision.

**Rule:** A read path with a fallback MUST return a `data_source` / `snapshot_source` field and the UI MUST surface it. "Silently prefer DB if available, otherwise tape" is a bug generator because the two paths diverge over time (schema drift, seed staleness, ref_date drift) and no one notices until the divergence becomes semantically absurd. Make the routing observable at every layer: response field, log line, UI badge.

**How to apply:**
- Every data-source endpoint returns an explicit provenance field (this session added `data_source='database'` + `snapshot_source=sel.source` to all 4 portfolio endpoints).
- Frontend badges key off the provenance field, not a frontend guess (`PortfolioAnalytics.jsx` now reads `data.data_source` honestly).
- When adding a new "if DB configured and has data" shortcut, STOP and ask: does the DB have the same richness as the fallback? If no, the shortcut is a regression trap. Either make DB match (this session's `extra_data` JSONB spread-back) or route explicitly via caller intent (query param), never silently.
- When `sel['date']` (or any "as-of" field) is derived from system time instead of data state, it's a lie. Always key off the underlying data (snapshot.taken_at, tape filename, ingest timestamp).

---

## 2026-04-22 — JSONB spread-back kills the "hand-map every column in the loader" pattern

**Problem:** The original `load_klaim_from_db` had a ~20-line hand-maintained dictionary mapping `inv.extra_data['discount'] → 'Discount'`, `inv.extra_data['pending'] → 'Pending insurance response'`, etc. Every time a new tape column was added (Mar 2026's IRR + collection curves, Apr 15's direct-DPD + Provider), a parallel edit was needed in both `seed_db.py` (write) and `db_loader.py` (read) — or the column got silently dropped on the DB path. Five new Apr 15 columns had been added to the tape but the corresponding mapper edits never happened, so those columns vanished whenever DB was serving.

**Rule:** `extra_data` JSONB keys should be the EXACT tape column names verbatim. No snake_case translation, no renames. The writer (`scripts/ingest_tape.py`) dumps every non-core column under its original name; the reader spreads every key back onto the DataFrame as a column. A new tape column flows through the entire stack automatically — zero code changes from ingest to dashboard.

**How to apply:**
- Reserve the relational schema for fields you need to INDEX or JOIN on (invoice_number, amount_due, status, invoice_date). Everything else → JSONB.
- When designing a new persistent store for tape-shaped data, resist the urge to "normalize" column names. The tape format IS the contract. Rename in the UI layer if you need to.
- Test: add one new column to a tape, ingest it, confirm it appears in the DataFrame produced by the loader without touching any Python. If that fails, the pipeline is fragile.

---

## 2026-04-21 — Tape files don't deploy with git; EoD must flag them for manual SCP

**Problem:** Session 30 added `data/klaim/UAE_healthcare/2026-04-15_uae_healthcare.csv`, the new Klaim April tape (8,080 rows × 65 cols, 4 MB). Following my own EoD Step 11, I checked `git diff HEAD~N --name-only | grep registry.json` → empty → told the user "no dataroom sync needed" and considered the deploy path complete. User then opened the production dashboard and the Apr 15 snapshot was missing from the dropdown. Root cause: raw tape files live under `data/{company}/{product}/` and are gitignored (correctly — we don't want 4 MB CSVs in git history). `sync-data.ps1` only walks `dataroom/` subdirectories to push PDFs/xlsx/docx there; it does NOT touch sibling tape directories. And `deploy.sh` pulls from git, so it can't bring a file git doesn't know about. Net: the tape only ever existed on the laptop. EoD Step 11 as written only checked the dataroom rail, missed the parallel tape rail entirely.

**Rule:** Any data file that is (a) gitignored and (b) not covered by an existing sync script is platform-dark until manually SCP'd. EoD must enumerate both rails — dataroom registry changes AND new/modified tape files — before signing off. A green deploy without the data isn't really green; the user won't see the work until the raw file lands on the server.

**How to apply:**
- EoD skill Step 11 now has a second mandatory sub-check for untracked date-prefixed tape files (`git ls-files --others --exclude-standard -- "data/*/*/2*.csv" "data/*/*/2*.xlsx" "data/*/*/2*.ods"`), mirroring the existing `registry.json` dataroom check. Don't remove either.
- Cross-reference the untracked-files list against session activity — a pre-existing tape from an earlier session will ALSO appear as untracked (gitignored, local-only), so "file is untracked" alone is insufficient. Flag only files the session added / replaced / analysed.
- The SCP command per file: `scp -o ServerAliveInterval=30 <laptop-path> root@<server>:/opt/credit-platform/data/<company>/<product>/`. The server-side `/app/data/` volume mount picks it up immediately; no backend restart required because `get_snapshots()` re-reads the directory on every call.
- Any time a new gitignored data category is introduced (new asset-class-specific file type, new off-tape sidecar that carries analyst-entered numbers like cash balance, a CSV the user drops alongside a tape), the EoD skill's Step 11 needs a parallel check added to its enumeration. The rule-of-thumb: if it's gitignored AND the platform reads it AND no sync script covers it → it needs an EoD deploy check.
- Symptom in the wild: a successful deploy + clean git state + "all tests pass" but the user reports a specific snapshot/document/report isn't visible on production. Suspect a data-sync rail the EoD didn't enumerate before investigating app bugs.

---

## 2026-04-21 — Persistent history files must record the compute method per entry

**Problem:** `covenant_history.json` stored `{period, compliant, current, date}` per covenant per evaluation — but not the method used to compute `current`. The Apr 13 entry was written using proxy DPD on the March tape (no `Expected collection days` column). On Apr 15, Klaim supplied the April tape which added the column, flipping Paid-vs-Due to method `direct`. `annotate_covenant_eod`'s `two_consecutive_breaches` rule compared Apr 13 (proxy, 70.3%) + Apr 15 (direct, 83.4%) as two consecutive breaches and flagged a spurious EoD. Both numbers were correct at their respective moments — but treating them as a series misrepresented a methodology transition as a repeated breach.

Simultaneously, in my first Final Report for the April tape add, I narrated "PAR30 improved -7.9pp between Apr 13 and Apr 15" as direction-of-travel signal. The user caught that the two points used different DPD methods and weren't like-for-like — the apparent improvement might have been the methodology change, not a portfolio change.

**Rule:** Any persistent history file that accumulates a metric over time must record **how the metric was computed** at each append, not just the value. Consumer logic that applies cross-period rules (consecutive-breach detection, trend narratives, rolling averages, YoY comparisons) must check method consistency before treating two points as comparable. Legacy entries predating the method field must be handled as "unknown, don't penalise" — otherwise existing history becomes invalid the moment the field is added.

**How to apply:**
- Add a `method` field to every record in any JSONL/JSON history store at the same time you introduce the store. Cheap up front; avoids a retroactive backfill later. For Klaim: `covenant_history.json` records now carry `method`.
- When rules compare consecutive points (`annotate_covenant_eod` 2-consec check, any rolling-avg Z-score, seasonality YoY compare), gate the comparison on `prev.method == current.method`. If they differ, treat as reset / first-breach-after-method-change / flag-for-review — not as a silent third entry in a series.
- Missing-method legacy entries: use `bool(prev_method and current_method and prev_method != current_method)` short-circuit so `None` reads as "unknown, don't penalise". Prevents retroactive invalidation of existing history when the field is added.
- When narrating a period-over-period trend (in commentary, memos, the Final Report for a new tape), first check whether compute method changed between the two points. If yes, say so explicitly — "lower vs prior period, but the prior used a proxy measure; first clean methodology-comparable delta will be period N+1". Don't frame it as a portfolio trend.
- Symptom in the wild: a time-series chart showing a step change exactly at the moment a new data column arrived or a compute function was updated — suspect the methodology transition before the portfolio.
- See `tests/test_analysis_klaim.py::TestCovenantMethodTagging` — `test_method_change_breaks_consecutive_breach_chain` and `test_missing_method_treated_as_unknown_not_penalised`.

---

## 2026-04-21 — Validate the business identity before writing the validation check

**Problem:** `core/validation.py` Balance Identity check assumed `Collected + Denied + Pending` should sum to `Purchase value` (±5%). On Apr 15 it flagged 2,775 of 8,080 deals — a 34% false-positive rate. The actual Klaim accounting identity is `Paid + Denied + Pending ≡ PV` (holds to floating-point zero); `Collected` legitimately exceeds `Paid` because it also includes VAT reimbursement and fees. The original check was using an intuitive-sounding but WRONG identity — no one validated it against a real tape before committing.

**Rule:** Any validation rule of the form `A + B + C ≈ D` is a claim about how the business data is structured. That claim needs empirical verification on the real data before the check ships: mean and stddev of `A+B+C - D` should be near zero (not just "within tolerance"). If the stddev is material, the rule is wrong — either the columns don't mean what you think, or there's an unmodeled term. Fix the rule; don't widen the tolerance.

**How to apply:**
- When writing or modifying a "this should equal that" check: first run it against the latest real tape interactively. Compute `diff.mean()`, `diff.std()`, `diff.abs().max()`. If `mean ≈ 0` and `stddev ≈ 0` and `max ≈ 0`, the identity holds — the check is well-founded. If any is materially non-zero, stop and re-read the column definitions.
- For Klaim specifically: `Collected` = Paid + VAT reimbursement + fees received. Only `Paid` is part of the face-value identity. `Collected > Paid` for every deal with non-zero VAT/fees — this is structural, not a data error.
- Symptom in the wild: when a validation check fires on >5% of rows on a known-clean tape, the check is usually wrong, not the data. Always investigate the math first.
- See `tests/test_analysis_klaim.py::TestBalanceIdentityKlaim::test_paid_den_pen_equals_pv_on_apr15` for the invariant assertion — it verifies the identity holds to floating-point zero before asserting the check fires on ≤5 deals.

---

## 2026-04-21 — For dual-view metrics with asymmetric weighting, use observed values not contractual inferences

**Problem:** Adding Total-WAL alongside Active-WAL for the Klaim covenant. User asserted invariant `wal_total < wal_active` on Apr 15 because completed deals have bounded life while actives accumulate age. First attempt used `min(Expected collection days, elapsed)` as the completed-deal close-age proxy. Result: `wal_total = 152.8d > wal_active = 148d`. Invariant failed.

Why: Klaim has 1,503 active deals (mean elapsed 248d, median 121d) and 6,576 completed deals (mean Expected collection days 94d, median 87d). PV-weighted Total across the whole book weighs completed deals' CONTRACTUAL term against active deals' ACTUAL elapsed age. Because active-WAL is outstanding-weighted (young active deals with big outstanding dominate) while Total is PV-weighted, the two are measuring different things with different weight vectors — the invariant survives only if BOTH are grounded in what actually happened.

Switched to `Collection days so far` (observed, clipped to `[0, elapsed]`, fallback to `Expected collection days` when missing/negative). Result: `wal_total = 137.2d < wal_active = 148d` ✓. Completed deals' mean OBSERVED life = 60d (much shorter than contractual 87d — on average they pay faster than term).

**Rule:** If you're introducing a dual view of a metric with asymmetric weighting (one view uses outstanding-weight, the other PV-weight) and the acceptance criterion is a strict ordering between them, the cross-view invariant is fragile. Prefer OBSERVED values over CONTRACTUAL inferences for the side where observations exist — the invariant survives the weighting difference only if both views are grounded in what actually happened, not what was supposed to happen.

**How to apply:**
- When designing a new metric that must compare against an existing one under a different weighting, STOP and compute both candidates on the real tape before coding. If the invariant fails, you've picked the wrong proxy — diagnose WHY (which rows push the sum the wrong way, what assumption they violate) before switching. Don't just try another proxy blindly.
- For Klaim: `Collection days so far` is the observed completion duration for completed deals (despite some data noise — a few rows negative or >3y). `Expected collection days` is the contractual term used at pricing time, not observed. Observed > contractual precedence for life-of-deal computations.
- Document the chosen proxy in `compute_methodology_log()` as a `close_date_proxy` audit-trail entry so IC consumers can see which path was used per tape vintage.
- See `tests/test_analysis_klaim.py::TestDualViewWAL::test_total_wal_strictly_less_than_active_on_apr15` — the assertion message explicitly says "if not, the close-date proxy is wrong" so a future failure is self-diagnosing.

---

## 2026-04-20 — Dedup maps must update inside the loop, never just at setup

**Problem:** `core/dataroom/engine.py` ingest() built an `existing_hashes` dict once from the prior registry at the top of the function, then loop-checked every on-disk file against it. When two files with identical bytes existed at different paths (same corporate PDF referenced from `Company Overview/` AND `US Opportunity/` — common in data rooms), the first got ingested successfully, **but `existing_hashes` was never updated with the new hash**, so the second file hit `file_hash in existing_hashes == False` and got ingested as a duplicate with a different doc_id. Klaim had 75 such pairs; the UI displayed 153 docs instead of the real ~76. `refresh()` had the exact same shape (keyed on filepath, not hash). Identical root cause.

**Rule:** Any dedup map built from prior state at the start of a processing loop MUST be mutated inside the loop after every successful operation that could produce a new key. If the loop can both (a) add new items and (b) use the map to decide whether to add more — the map must reflect the post-add state, not just the pre-loop state.

**How to apply:**
- Look for this pattern in any ingest/batch-processing code: `seen = {build_from_prior_state}; for x in items: if x.key in seen: skip; else: process(x)` — check whether `process(x)` updates `seen`. If not, it's buggy.
- Write a unit test that exercises the multiple-new-items-same-key path specifically (two on-disk files, same bytes, different paths). The single-item test won't catch it.
- Surface the dedup count in the result payload (`duplicates_skipped`, `relinked`, etc.) — makes the behavior observable in operator tools without requiring new diagnostics code later.
- See `tests/test_dataroom_pipeline.py::TestWithinPassHashDedup` for the regression pair.

---

## 2026-04-20 — Engine must never ingest files it writes into the source directory

**Problem:** `core/dataroom/classifier_llm.py` writes its SHA-keyed classification cache to `data/{co}/dataroom/.classification_cache.json`. The ingest engine walks the same `data/{co}/dataroom/` directory with `os.walk`. `_is_supported()` only excluded 4 filenames (`config.json`, `methodology.json`, `registry.json`, `index.pkl`) — nothing caught dotfiles, nothing caught `meta.json` or `ingest_log.jsonl` that the engine itself writes. Every ingest picked up the cache, the meta sidecar, and the ingest log as JSON "documents" and indexed them. Combined with the dedup bug above, each also got duplicated.

**Rule:** If an engine writes state files (caches, logs, status sidecars) into a directory it also walks as input, every such filename must be explicitly excluded from the walker. Dotfiles should be unconditionally rejected — anything starting with `.` inside a data directory is metadata by convention, not content. Any time a NEW engine-written file is introduced (a future ingest log, a future sidecar), add it to the exclusion list in the same PR.

**How to apply:**
- In `core/dataroom/engine.py`, `_EXCLUDE_FILENAMES` + the dotfile prefix check in `_is_supported` form the ingestion firewall. When adding any new sidecar, update both the set and any analogous sets in other pipelines (`core/mind/`, `core/research/`) before merging.
- Write a regression test that creates a real-looking directory containing a dotfile + a genuine doc, runs ingest, and asserts `len(registry) == 1`.
- Consider whether the state file should live in a sibling directory instead (`data/_dataroom_state/{co}.json`) — moving state out of the walked tree is the more durable fix. Not worth retrofitting now, but the right default for new engines.

---

## 2026-04-20 — When hash-dedup finds a match but the registered filepath is gone, RELINK — never just skip

**Problem:** After deploying the two fixes above, the user cleaned up a latent `data/klaim/dataroom/dataroom/` full-duplicate directory on the server (leftover from the session-17 product-level → company-level migration). Running `refresh --company klaim` afterwards showed `removed=55 unchanged=21 duplicates_skipped=55` — **55 registry entries silently disappeared in a single command.**

Root cause: during the previous ingest's dedupe, the "winner" registry entry for 55 sha256 groups had a `filepath` pointing INTO the nested directory (because that was the earlier `ingested_at`). When the nested dir was deleted and refresh ran, my within-pass dedup saw each disk file's hash match an existing entry and chose `duplicates_skipped` — but the entry's registered filepath was no longer on disk, so the end-of-function removal sweep deleted the entry. Net: disk file unreferenced, entry gone, next query → 0 hits. Silent data loss.

**Rule:** When a dedup map records a hit, there are TWO distinct situations, and they must be handled differently:
1. **The registered path IS still on disk** → this is a genuine second copy → dedup-skip is correct.
2. **The registered path is NOT on disk** → the source file was moved/renamed → the entry's path must be RELINKED to the current disk path before the removal sweep runs. Otherwise the removal sweep drops the now-stale entry and the disk file has no referent.

**How to apply:**
- In any refresh/reconcile loop that has (a) a hash-keyed map to existing entries AND (b) a trailing "remove entries whose path isn't on disk" sweep, the hash-hit branch must check whether the existing entry's path is in the disk set. If not, mutate the entry's path in place; if yes, treat as duplicate.
- Add a `relinked` counter to the result payload alongside `duplicates_skipped` so operators can tell the two paths apart from the audit log.
- Write a regression test: ingest a file at path A, move it to path B without changing bytes, delete path A, run refresh, assert the entry's `filepath` now points to B and `relinked == 1`.
- See `tests/test_dataroom_pipeline.py::TestRefreshRelink::test_moved_file_is_relinked_not_dropped` for the canonical regression.
- **Meta-lesson:** when a fix introduces a new branch in a state machine, walk through every OTHER branch in the same function and check whether the new branch's "continue" leaves the other branches in an inconsistent state. My Bug 2 fix added within-pass dedup; Bug 4 was a missed interaction with the pre-existing removal sweep that I should have caught in the same PR.

---

## 2026-04-20 — Don't trust ANY local view for "did my commit reach GitHub?" — only `git ls-remote` against the real URL

**Problem:** Ran `git push origin main` from a cloud Claude Code sandbox. Output showed `To http://127.0.0.1:<port>/git/sharifeid-eng/credit-platform` — a local proxy URL. Declared work "pushed + shipped." A separate cloud session reported the commit and the file it created "do not exist in git history" on its end. I couldn't tell from inside my sandbox whether my proxy's push had actually propagated to GitHub or if the other session was looking at stale refs. When I finally ran `git ls-remote https://github.com/sharifeid-eng/credit-platform.git main` against the public URL, the commit WAS there — the proxy had propagated correctly, and the other session had simply not fetched. But I had no way to know that without the direct check.

**Rule:** Neither side of a sandbox-to-sandbox disagreement about "is this commit on GitHub?" is trustworthy on its own:
- **Your sandbox's `origin/main`** points at a local proxy; `git log origin/main` shows whatever the proxy has cached, not necessarily GitHub.
- **Another sandbox's `origin/main`** is a different proxy with its own cache — a commit you pushed may not appear in their view until they fetch, and even their fetch talks to THEIR proxy, which may be stale.

The ONLY authoritative source is GitHub itself, accessed directly:
```
git ls-remote https://github.com/<owner>/<repo>.git main
```
This bypasses every local `origin` config and every proxy cache. It returns the canonical commit hash for `refs/heads/main` as GitHub has it right now.

**How to apply:** For any commit that MUST land durably (EOD work, next-session handoff docs, production-destined code), append this verification after the push:
```
git push origin main
EXPECTED=$(git rev-parse main)
ACTUAL=$(git ls-remote https://github.com/<owner>/<repo>.git main | cut -f1)
[ "$EXPECTED" = "$ACTUAL" ] && echo "✓ landed on GitHub" || echo "✗ mismatch — investigate"
```
If the hashes don't match, the push failed silently — investigate before moving on.

**Equally important — when someone else reports "the commit isn't there":** Don't recreate work on their word alone. Run `git ls-remote https://github.com/...` first. If GitHub has it, the other party has a stale fetch; tell them to `git fetch origin && git log origin/main`. If GitHub doesn't have it, THEN recreate.

The cost of the extra check is a single command. The cost of skipping it is either (a) declaring work shipped that isn't, or (b) recreating work that already exists — both produce silent divergence across sessions and trust erosion.

---

## 2026-04-20 — After a force-push rebase, local clones need hard-reset, not pull

**Problem:** Session rebased branch `claude/resources-section-discussion-lMMAr` onto main (9 new commits) and force-pushed. User's laptop still had the old pre-rebase commit. `git pull` tried to auto-merge the divergent histories and produced conflicts across 5 files — none of which the user had actually edited locally.

**Rule:** When a branch has been force-pushed (i.e. `git pull` output contains the `+` marker and `(forced update)`), the remote history has been rewritten. `git pull` is the wrong command — it tries to merge the old and new histories. The correct recovery is:
```
git merge --abort
git reset --hard origin/<branch>
```
`reset --hard` says "discard local, trust the remote" — safe when all the work is actually on origin (as it is after a rebase + force-push).

**How to apply:** Before giving a user "pull" instructions on a branch you've rebased, warn them that if they had the branch checked out pre-rebase, they'll need the abort + reset sequence. And in commit/PR instructions after a rebase, include the recovery block so they can self-diagnose.

---

## 2026-04-20 — Mock-patching a core module requires importing it FIRST

**Problem:** A verification script used `mock.patch("core.ai_client.complete", ...)` and `mock.patch("core.loader.DATA_DIR", ...)` without importing those modules first. Result: `AttributeError: module 'core' has no attribute 'ai_client'` / `'loader'`. The `core/__init__.py` doesn't re-export submodules, so `getattr(core, 'ai_client')` fails until `import core.ai_client` has actually run.

**Rule:** When using `mock.patch("pkg.module.attr", ...)` — the string form — the target's parent package must have `module` as an attribute. For namespace packages (most of our `core/*`), that means an explicit `import core.module` has to execute before the patch. Two safe patterns:
1. `import core.ai_client` at the top of the test, then `mock.patch("core.ai_client.complete", ...)` works.
2. `import core.ai_client; mock.patch.object(core.ai_client, "complete", ...)` — resolves via the module object directly, bypasses the string lookup.

**How to apply:** Default to pattern 2 (`mock.patch.object`) — it's more robust and gets a real NameError if the module doesn't exist, rather than a confusing AttributeError on the package at test time.

---

## 2026-04-20 — Register-all-tools pulls pandas transitively; test in isolation

**Problem:** A test that only cared about a single tool (`external.web_search`) called `register_all_tools()` to populate the registry. That function imports every tool module — including `analytics.py`, which imports `core/agents/tools/_helpers.py`, which imports pandas. The sandbox didn't have pandas; the test errored on what looked like an unrelated import.

**Rule:** If a test only needs ONE tool registered, import that tool module directly — module-level `registry.register(...)` calls fire on import. `register_all_tools()` is for app startup, not for tests that want a narrow surface.

```python
# Good — minimal footprint:
from core.agents.tools import registry
import core.agents.tools.external  # triggers registration of external.*

# Bad — pulls pandas, anthropic, analytics, dataroom, memo, portfolio, ...:
from core.agents.tools import register_all_tools
register_all_tools()
```

**How to apply:** Always prefer targeted imports in tests. Keep fixtures small. If a test needs the whole tool graph, it's probably a smoke test and should live in a suite that runs with the full environment.

---

## 2026-04-20 — React Router preserves scroll position across navigations

**Problem:** User scrolled down the Home page to click the Operator card (in the Resources section near the bottom). `/operator` rendered but the page was already scrolled mid-page — because React Router preserves `window.scrollY` across navigations by default. Looked like a broken layout; was actually correct rendering at the wrong scroll offset.

**Rule:** Add a `ScrollToTopOnNavigate` component once at the top of the router that listens to `useLocation().pathname` and calls `window.scrollTo({top:0, left:0, behavior:'auto'})` on change. Mount it inside `BrowserRouter` so every route transition triggers it.

**Don't use** `behavior:'smooth'` — it fights with the route transition animation and produces a jarring double-motion. Same-path tab changes (e.g. `:tab` URL param swaps on the same pathname) should NOT trigger scroll reset — the effect depends on `pathname` alone, which stays constant for tab switches.

**How to apply:** Whenever adding a new top-level route to a React Router app, confirm the project has a scroll-reset handler. This repo now has `ScrollToTopOnNavigate` in `frontend/src/App.jsx`.

---

## 2026-04-20 — Agent tool registry vs agent config: both must opt in

**Problem:** Shipped a new `external.web_search` agent tool. Registered it correctly in `core/agents/tools/__init__.py register_all_tools()`. Confirmed with a direct lookup: tool was in the registry. But no agent would actually use it — because each agent's `config.json` has a tool-patterns allowlist, and none of them included `external.*`. The tool was in the registry but invisible to all agents.

**Rule:** Adding a new tool module is a TWO-step process:
1. Register the tool module in `register_all_tools()` (import triggers the module-level `registry.register(...)` call)
2. Add the module's glob pattern to every agent's `config.json` "tools" array that should be able to use it

**How to apply:** Before declaring a new tool "done," grep every agent config.json for the new pattern and decide which agents actually need it. `analyst` is usually the first target for any user-facing chat tool; `memo_writer` for anything that informs memos; etc.

---

## 2026-04-20 — `def test_` regex must tolerate indentation and `async`

**Problem:** `/api/platform-stats` counted tests with `re.findall(r'^def test_', content, re.MULTILINE)`. Returned 0 for the Architecture page's "Tests" tile despite ~428 tests existing. Cause: regex required `def test_` at column 0, so class-indented tests (`    def test_foo`) and async tests (`async def test_bar`) silently didn't match.

**Rule:** When counting test functions via regex, the tolerant pattern is `^\s*(?:async\s+)?def\s+test_`. Matches:
- `def test_foo(...)` (top-level)
- `    def test_foo(...)` (class-indented)
- `async def test_foo(...)` (async top-level)
- `    async def test_foo(...)` (async class-indented)

**How to apply:** Any code that counts "tests" or "functions" via regex should assume the code under test uses classes, async, decorators, etc. The repo's test style includes all of these. Cheap to be liberal; expensive to silently return 0.

---

## 2026-04-19 — `rm -rf` on a non-existent path exits 0 silently, masking wrong-path bugs

**Problem:** Ran `docker compose exec -T backend rm -rf reports/memos/klaim/UAE_healthcare/ad7cc868-a64` to delete a verification memo. The command exited cleanly. A follow-up `ls` on the parent returned "No such file or directory" — read as "dir auto-pruned on empty, clean deletion ✅". Actually the path had **never existed**: the memo archive uses a flat `{company}_{product}` directory convention (`reports/memos/klaim_UAE_healthcare/`), not nested (`reports/memos/klaim/UAE_healthcare/`). The memo was still live on the website; user had to report it before we found the real path.

**Rule:** Before running any destructive filesystem command against a derived path, verify the path exists with a read-only `ls` or `find` first. Treat "silent success" from `rm -rf` as evidence of nothing — it means either (a) the deletion worked, or (b) the path didn't exist. You cannot tell them apart from exit code alone. Always follow with a positive-evidence check: `ls` the *parent* directory and confirm the target is absent from a list that contains other expected entries.

**Why:** Path conventions in this codebase are not self-documenting. `reports/memos/` uses `{co}_{prod}` flat; `data/` uses `{co}/dataroom/` nested; some tools use hyphens, others underscores. Assuming the layout from memory is a recipe for deleting nothing and thinking you deleted something, or (worse, in another codebase) deleting everything and thinking you deleted one thing.

**How to apply:** For any cleanup command, the verification pattern is `find <parent> -name "<target_pattern>"` **before** and **after** the delete. Before should list the target(s); after should list nothing. If "before" is empty, stop — you have the wrong path. Applies equally to `docker compose exec rm`, `Remove-Item -Recurse`, `git clean`, and any `--force` flag.

---

## 2026-04-19 — `.gitignore` negations for server-local state are a collision trap

**Problem:** `.gitignore` had `!data/*/dataroom/registry.json` negating the broader `data/*/dataroom/*` ignore, intended to keep the "lightweight catalog" in version control for re-ingest idempotence. But `registry.json` contains doc_id UUIDs generated per-ingest on whichever machine ran the last `ingest` — **server-local state, not portable**. Session 24 Tier 1.2 codified "server is authoritative registry owner" in `sync-data.ps1` (excluded registry.json from push) but left the git-tracking path open. Session 26 EOD commit inadvertently staged SILQ's registry; the VPS `git pull` then died with `untracked working tree files would be overwritten by merge` because the server had its own authoritative copy with different UUIDs.

**Rule:** If a file is per-machine state (UUIDs, cache keys, derived doc_ids, any identifier generated at runtime that differs across independent runs of the same logical operation), it must not be tracked in git. A `.gitignore` negation that overrides a blanket ignore for such files is a smell — it means you've picked one machine as the "canonical" owner but the VCS can't tell which, so any other machine that independently generates that file will collide on pull.

**Why:** The "server is authoritative" rule has to hold on **both** rails — the sync pipeline AND the git pipeline. Closing one leaves the other wide open to recreate the problem. Worse: you only find out at the next deploy, after everything looks green locally.

**How to apply:** Before negating an ignore pattern for any file in `data/`, `reports/`, or runtime-derived directories, ask: "could two machines running the same code generate different contents for this file?" If yes, never track it. If multiple machines need coordinated state, use a real sync mechanism (scp, rsync, object store), not git. For this repo: `git rm --cached` + remove the negation + commit. The authoritative file stays on the authoritative machine; other machines are free to generate and hold their own copies untouched by version control.

---

## 2026-04-19 — When Compute fn signatures change, audit every tool dispatch table too

**Problem:** `core/agents/tools/analytics.py` had six handlers calling `compute_*` functions in `core/analysis.py` + `core/portfolio.py` with drifted signatures. Three caused hard TypeError/ImportError at runtime (memo pipeline died with "network error" in browser). Two more were **silent correctness bugs** — `compute_segment_analysis(df, mult, dimension)` was routing `dimension` through the 3rd positional (`as_of_date`), which silently ignored it and returned segments for the wrong dimension. Bug had been live for weeks with no symptoms because the handler was rarely invoked and output looked plausible.

**Rule:** Any time you refactor the signature of a compute function in `core/analysis.py`, `core/analysis_*.py`, `core/portfolio.py`, etc., `grep -n "compute_fn_name(" core/agents/` and inspect each call site. Agent tool dispatch tables are easy to miss because they're in a separate layer from the analytical code and the type checker (or lack thereof) won't catch it.

**Why:** The agent tools layer is a shadow contract — it mirrors analytical functions but in a loose dict-routing pattern, not direct calls. Signature drift doesn't surface until the agent actually tries to invoke the tool, which might happen only during memo generation or deep research. The silent ones are worse than the loud ones.

**How to apply:** Add a lightweight smoke test per handler (`tests/test_agent_tools.py` has 6 such tests now covering Klaim). Run before any agent-layer change. Better yet: refactor dispatch tables to import the function references directly so a signature change is a syntax error at import time, not a runtime KeyError after minutes of pipeline.

---

## 2026-04-19 — Cloudflare HTTP/2 and HTTP/3 both proxy-break SSE

**Problem:** Browser memo-generate progress stream failed with `net::ERR_QUIC_PROTOCOL_ERROR` (with HTTP/3 on) and `net::ERR_HTTP2_PROTOCOL_ERROR` (after HTTP/3 disabled at edge). Backend `POST /agents/.../memo/generate` returned 200 OK and pipeline completed; browser never saw the stream. Cloudflare's edge proxy buffers/cuts long-lived SSE under both QUIC and HTTP/2, independent of origin config.

**Rule:** Any new long-running SSE endpoint behind Cloudflare needs a transport-plan decision up front: (1) Configuration Rule bypassing buffering on the path, (2) Cloudflare Tunnel, (3) grey-cloud subdomain, or (4) non-SSE polling fallback. Don't ship SSE + Cloudflare orange-cloud + hope.

**Why:** The "works locally" trap. In dev the stream is direct to uvicorn; in prod a silent 60-120s proxy edge cut produces `ERR_HTTP2_PROTOCOL_ERROR` with no signal to the backend, and the backend returns 200 OK in logs. Debugging this from stderr alone is impossible — you have to correlate browser DevTools with cf-ray headers.

**How to apply:** For every streaming endpoint, verify end-to-end from a browser behind Cloudflare before claiming done. Add a non-SSE fallback endpoint as belt-and-suspenders when the UX requires completion guarantees. Memo pipeline already persists to disk regardless of SSE, so the data is recoverable — but the UX is broken.

**Resolution (session 26.2, commit `f5d2a7b`):** 20s SSE heartbeat in `backend/agents.py` `memo_generate_stream` — `: keepalive\n\n` comment line emitted when event queue is idle ≥20s. Keeps byte flow alive under CF Free's ~100s idle-proxy cap during long pipeline stages (research, polish can each run 60-90s silently). Comment lines are ignored per SSE spec and by the frontend's manual parser. 15-line backend patch, zero frontend change, zero infra. Verified end-to-end: fresh Klaim memo `13a852f9-4ba` completed 2m35s, $5.27, polished=True, fully green browser UX. **Pattern to reuse:** for any future SSE endpoint with inter-event gaps >20s, emit a heartbeat — cheaper than Tunnel and sufficient for the idle-timeout failure mode. If the failure mode is HTTP/2 protocol-cut (distinct from idle-timeout), heartbeat won't help and Cloudflare Tunnel is the next step.

---

## 2026-04-19 — Verify victory conditions from persisted artifacts, not the request that created them

**Problem:** Browser SSE died mid-flight. First instinct: "the generate call failed, retry." Actual state: backend fully completed, memo persisted with all 12 sections + both sidecars + meta.json — only the browser progress stream died. Inspected `/app/reports/memos/klaim_UAE_healthcare/c1686e76-841/v1.json` directly and Check C passed.

**Rule:** When a long-running write operation's transport fails, check the target storage before re-running. SSE, WebSocket, long-polling — all can drop while the underlying work finishes successfully on the server. Especially true for pipelines that call `storage.save()` before emitting the final "done" event.

**Why:** Re-running a 3-minute $1+ pipeline because the browser gave up is wasteful. The filesystem is the source of truth, not the HTTP response.

**How to apply:** After any "network error" / "connection dropped" / "stream closed" symptom on a write operation, first command should be `ls -lt {target_dir}/ | head` + inspect the newest artifact before replanning.

---

## 2026-04-19 — Meta schema drift: always fetch actual keys before asserting on meta

**Problem:** Wrote a verification script using `meta.get('memo_id')` and `meta.get('template_key')` — actual meta schema uses `id` and `template`. Output showed `None` for both, led to 30s of "the save path must be broken" panic before I inspected `meta.keys()` and saw the right fields were there under different names.

**Rule:** Before running assertions on meta/config/result dicts, print the sorted key list once. Takes 5 seconds, saves 30 minutes of false alarms.

**Why:** Schema drift across generator/save layers is invisible until you query an expected field and get `None`. The `None` is ambiguous — did the field fail to populate, or did I query the wrong name?

**How to apply:** Standard verification block pattern is `print('KEYS:', sorted(d.keys()))` followed by the specific assertions. If a required key is missing, the keys list will show it; if a key exists under a different name, likewise.

---

## 2026-04-18 — `except Exception` in a thread-pool worker does not catch `BaseException`

**Problem:** `core/memo/generator.py` production memo generation truncated at 3/12 sections with no trace in `errors[]`. The `_worker` function inside `_generate_parallel` had `try: ... except Exception: ...` around `self.generate_section(...)`, and the outer loop iterated `as_completed(futures)` calling `fut.result()` un-wrapped. Suspected root cause: an SSE client disconnect raises `GeneratorExit` inside a `progress_cb` call — `GeneratorExit` inherits from `BaseException`, not `Exception`, so it bypasses the worker's catch, propagates through the future, and `fut.result()` re-raises it. The unhandled exception tears down the `as_completed` loop before subsequent futures can be drained.

**Rule:** In ThreadPoolExecutor code, both the worker body AND the result-collection loop must catch `BaseException` — not just `Exception` — when the worker touches anything that can legitimately raise `SystemExit`/`GeneratorExit`/`KeyboardInterrupt`. SSE callbacks, subprocess signals, and async-context cleanup all fall in this category. Pair it with explicit backfill: if `results[idx]` is still `None` after the loop, synthesize an error placeholder so downstream code sees a complete list.

**Why:** `except Exception` was written defensively but misses exactly the failure mode that matters in a long-running SSE server: client disconnect mid-request. Recording the error with stage attribution makes it visible in `memo["errors"]` so the user can see what went wrong.

**How to apply:** Anywhere you use ThreadPoolExecutor with per-task `try/except`, make the outer `fut.result()` catch `BaseException` and continue the loop (log with `exc_info=True`, append to an error sink). Pattern now lives in `core/memo/generator.py::_generate_parallel`.

---

## 2026-04-18 — When a pipeline truncates, read the save layer before chasing upstream filters

**Problem:** Observed production symptom: memo v1.json had 3 sections instead of 12. First instinct was to look for a filter in the generator. Checking the save layer first (`core/memo/storage.py`) confirmed it does *not* filter sections — `memo["sections"]` is written verbatim. That single read eliminated an entire hypothesis space and focused the investigation on the 6-stage pipeline upstream.

**Rule:** Before debugging a "missing data" bug, verify where the data is last seen intact. Read the save/serialize layer and confirm whether it can drop or filter records. If it can't, you know the loss happened earlier; if it can, that's your fix point.

**Why:** Saved ~30 min of hunting imaginary filters. The file was 400 lines and the answer was a 2-minute read.

**How to apply:** For any data-loss bug, pull up the save path first. `git log -p` on the storage file also tells you whether any recent change added filtering.

---

## 2026-04-18 — Pipeline error gates should check content presence, not error count

**Problem:** `generate_full_memo` had `if not errors: run_citation_audit()` and `if polish and not errors: run_polish()`. A single `generated_by=="error"` section anywhere in the 12 would short-circuit BOTH downstream stages, producing a memo with partial body content but no polish applied and no citation audit. This was the actual 2026-04-18 production bug shape — one Stage 2 failure would skip Stages 5.5/6 entirely.

**Rule:** Pipeline continuation gates should ask "do I have enough usable input to make progress?" not "were there any errors?" Error count is noisy — a memo with 11 good sections and 1 failed one should still get polished.

**How to apply:** Replace `if not errors:` with content-presence checks like `if any(s.get("content") for s in memo["sections"]):`. Still collect errors into `memo["errors"]` for transparency, but don't let them block partial success.

---

## 2026-04-18 — SPA route and backend API path must not share a prefix

**Problem:** React Router had `/operator` as an SPA route. Backend had `APIRouter(prefix="/operator")` plus three intelligence routes starting with `/operator/`. Reverse proxy prefix-matched `/operator` to the backend. In-app navigation worked (React Router handled it client-side), but direct URL / browser refresh hit the server, which 404'd because there was no exact `/operator` route — only subroutes.

**Rule:** All backend API endpoints go under `/api/*`. SPA routes own the bare namespace. This is already the convention for `/api/integration/*` — extend it uniformly. When you see a new backend route that doesn't start with `/api/`, ask: could this collide with a current or future frontend route?

**How to apply:** Audit `APIRouter(prefix=...)` and bare `@app.get(...)` decorators in any new file. If the prefix isn't `/api/`, justify why in the PR description.

---

## 2026-04-18 — Directory-layout migrations must grep EVERY caller, not just the primary consumers

**Problem:** Session 17 moved datarooms from product-level (`data/{company}/{product}/dataroom/`) to company-level (`data/{company}/dataroom/`). The primary consumer (`DataRoomEngine`) was updated. Legal and Mind paths in `backend/operator.py` were already at company-level. But line 102 of `operator.py` — the Health tab's dataroom probe — was missed and kept pointing at the old path. Six months later, production Health tab showed "Data room not ingested" for every company with a populated dataroom. Caught only during a smoke test of an unrelated fix.

**Root cause:** Session 17's migration PR updated the primary consumer and the two paths that shared the file with dataroom. The ancillary code (operator health matrix) was in a different file and accessed the path via a slightly different pattern (`product_path / "dataroom" / ...` instead of a constant), so the migration grep didn't find it.

**Rule:** When reorganizing a shared directory layout, grep for every string containing the directory name — not just well-known consumers. Use multiple patterns:
  - `"dataroom"` — plain string
  - `/ "dataroom"` — pathlib composition
  - `/dataroom/` — embedded in paths
  - `product_path.*dataroom` — product-level accessors that need to move

Cross-reference against a list of every file that touches the data layer. Health dashboards, operator tools, diagnostic scripts, and periodic audit jobs all read the same paths but are easy to forget.

**How to apply:** Any migration PR should include a "grep verification" checklist in the commit message listing every pattern searched and every file touched. If the migration is incomplete, latent bugs surface months later in places no one remembers to look.

---

## 2026-04-18 — Renaming a backend route prefix is incomplete without auditing the reverse proxy config

**Problem:** Session 25 moved backend operator endpoints from `/operator/*` to `/api/operator/*` and updated all Python + frontend callers. Full test suite green. Deployed. User visited `laithanalytics.ai/operator` and STILL got `{"detail":"Not Found"}` — the exact bug we thought we'd fixed. Root cause: `docker/nginx.conf` had an explicit `location /operator { proxy_pass http://backend:8000 }` block that continued forwarding `/operator` to the backend regardless of what Python routes existed. Backend now had no handler at `/operator` (only at `/api/operator/*`), so it returned FastAPI's 404 JSON instead of the SPA falling through.

**Rule:** When renaming a backend route prefix (especially one that collided with an SPA route), the fix has three layers, not one: (1) Python route decorators, (2) frontend callers, (3) reverse proxy config. Miss any one and the bug persists. For this codebase, proxy config lives at `docker/nginx.conf` and is baked into the frontend image at build time — changes don't ship until redeploy.

**Why:** The original spec (Option 1 vs Option 2) flagged this risk — "Option 2 (proxy-only, cheapest): Edit the reverse proxy config on the Hetzner box." I chose Option 1 (rename Python routes) and assumed the proxy auto-fell through when backend had no match. It does not when there's an explicit `location` block.

**How to apply:** Route-rename checklist:
1. `grep -rn "APIRouter(prefix=" backend/` — find all backend prefixes
2. `grep -rn "['\"]/<prefix>" frontend/src/` — find all frontend callers
3. `grep -rn "location /<prefix>" docker/ nginx/ *.conf` — find proxy blocks
4. Bonus: check `backend/cf_auth.py` `_SKIP_PREFIXES` for auth middleware exclusions

Only after all three layers are consistent can the rename be considered complete.

---

## 2026-04-18 — `temperature` is model-specific — tier-aware kwarg filtering beats per-call-site edits

**Problem:** Opus 4.7 deprecated `temperature`. One call site (`memo/generator.py:858` polish pass) hit a 400 error. The fix could have been a one-line `temperature=` removal at that site, but the same pattern is risk-eligible anywhere else a caller routes to Opus 4.7. Instead of hunting call sites on every future model deprecation, centralize the filter at the tier boundary.

**Rule:** When a model-specific kwarg deprecation hits one call site, centralize the fix at the tier router (here: `core.ai_client.complete()`) with a `_STRIPS_TEMPERATURE_TIERS` set. Callers can keep passing the kwarg; the router quietly drops it for tiers whose models reject it.

**Why:** Anthropic adds/removes kwargs on major model families periodically. Each deprecation otherwise becomes a whack-a-mole across backend/core/memo files.

**How to apply:** Any tiered API wrapper (ai_client, email sender, feature-flagged service) should handle tier-specific kwarg filtering in the wrapper, not at call sites.

---

## 2026-04-18 — Explicit `sys.stderr.flush()` before final stdout emit fixes CLI ordering races

**Problem:** `scripts/dataroom_ctl.py audit` in a shell `for` loop with `2>&1 | head -1` sometimes printed the JSON payload before the human summary line. The per-command handlers correctly called `_err()` (stderr) first and `_emit()` (stdout) last, but when both streams are merged via redirect, block-buffered stdout can race with line-buffered stderr at process exit depending on OS scheduling.

**Rule:** For CLIs that mix stderr and stdout and document an ordering convention, add explicit flushes in the emission helpers. `sys.stderr.flush()` before the final stdout `print()` is all it takes.

**How to apply:** Any CLI where stderr-first / stdout-last ordering matters (common for scrape-friendly tools that put human summary on stderr and machine-readable JSON on stdout) needs explicit flush discipline.

---

## 2026-04-18 — SHA-256 dedup must verify the artifact, not just the key

**Problem:** `DataRoomEngine.ingest()` built `existing_hashes = {doc["sha256"]: doc_id for ...}` from the registry, then skipped any file whose hash was already keyed. If the registry was pushed to a fresh server without the matching `chunks/` directory (as `sync-data.ps1` was doing), every file got reported "skipped" — even though no chunks existed to serve searches or memos. Live symptom: server showed "0 new, 40 skipped" on the SILQ dataroom while chunks/ was empty and search returned nothing.

**Root cause:** The dedup key (sha256) is a hash of the **source file**, but the dedup contract is really "I already have the processed artifact (chunks)". If the artifact is missing but the key is present, skipping is wrong — the correct action is to evict the stale key and re-ingest.

**Fix:** Before populating `existing_hashes`, check `chunks/{doc_id}.json` exists on disk. If missing, `registry.pop(doc_id)` and log an eviction warning. Same fix applied to `refresh()`. Result field `orphans_dropped` surfaces the count so operators see what happened.

**Rule:** Any dedup check that references a downstream artifact (chunks, index, cached output) must verify the artifact exists before trusting the key. "File already processed" ≠ "processed output exists". Bonus: structure the registry so an audit function can detect both directions of misalignment (missing chunks for a registry entry, and orphan chunks with no registry entry) — surfacing either direction is a symptom that something went wrong upstream.

---

## 2026-04-18 — Bare `except ImportError: return` silently disables features

**Problem:** Production container shipped without `sklearn`, `pdfplumber`, `python-docx`, `pymupdf`, `pymupdf4llm`. Each was wrapped in a bare `try: import X; except ImportError: return` block at the top of the consumer function. Net effect: PDFs produced no text (pdfplumber missing), `index.pkl` was 0 bytes (sklearn missing), searches silently fell back to word-frequency scoring. Nobody noticed for weeks because there was zero logging.

**Root cause:** `except ImportError: return` is a convenience for graceful degradation, but without a WARNING/ERROR log and a status flag readable by an audit endpoint, the degradation is silent and permanent.

**Fix:** Three layers of defense:
1. **Startup probe** (`backend/main.py` lifespan) — imports each optional dep, writes ERROR log + `data/_platform_health.json` with `missing[]` + `present[]`.
2. **Call-time warning** — `_build_index()` and `_search_tfidf()` log WARNING when the import fails and set `index_status: "degraded_no_sklearn"` in `meta.json`.
3. **Audit surfaces it** — `engine.audit()` reads `meta.json` and reports `index_status` in the `/dataroom/health` endpoint. Deploy.sh / CI can curl this and fail loudly if status isn't `ok`.

**Rule:** An `ImportError` for an optional dep must always (a) log at WARNING or ERROR, (b) write a machine-readable status flag to a location an audit endpoint can read. "Feature disabled because dep missing" should always be observable without reading logs.

---

## 2026-04-18 — `git stash` before deploy silently eats server-side state

**Problem:** `deploy.sh` ran `git stash -q` before `git pull` to avoid merge conflicts on local server edits, but never called `git stash pop`. Any server-side modifications were silently discarded every deploy.

**Fix:** Remove `git stash` entirely. The server should have zero local edits; if `git pull` fails, we *want* deploy to stop, not silently wipe state.

**Rule:** Never use `git stash` in an automated deploy script. If the server is authoritative for any state, that state lives in `data/` (gitignored) or a database, not in tracked files. If `git pull` fails on the server, that's a signal to investigate — don't paper over it.

---

## 2026-04-18 — CLI design for deploy.sh consumers: JSON stdout, human stderr

**Problem:** `deploy.sh` invoking `python -c "from core.dataroom.engine import ..."` made it impossible to scrape structured results (exit codes ambiguous, output interleaved, no machine-readable summary).

**Fix:** `scripts/dataroom_ctl.py` prints structured single-line JSON on stdout (scrapeable by deploy.sh / CI) and human-friendly progress on stderr. Exit codes carry semantic meaning: `0=ok, 1=audit misalignment, 2=usage error, 3=op failed, 4=user aborted destructive op`.

**Rule:** Any CLI that will be consumed by a deploy script or CI pipeline must separate machine output (stdout JSON) from human output (stderr text), and use meaningful exit codes (not 0/1 for everything). Destructive operations need a `--yes` confirmation gate.

---

## 2026-04-17 — CSS tokens: grep before using a variable name

**Problem:** 142 references to `var(--accent-gold)` across 30 frontend files were all rendering as transparent. The CSS token defined in `tokens.css` is `--gold` (short form); the long form `--accent-gold` was used everywhere but **never defined**. CSS silently fell through to transparent. The Continue, Generate, and New Memo buttons in MemoBuilder all appeared invisible on the dark navy background.

**Fix:** Added aliases (`--accent-gold: var(--gold)`, plus teal/red/blue) to `tokens.css`. Single 4-line change fixed 142 broken references across 30 files.

**Rule:** When writing CSS that references a custom property, grep `styles/tokens.css` first to confirm the exact name exists. Don't rely on a convention (long-form vs short-form) — verify the actual definition. When adding a new token, add both forms as aliases upfront to prevent this drift.

---

## 2026-04-17 — Anthropic tool names: no dots allowed

**Problem:** `/memos/generate` SSE endpoint returned `400 — tools.0.custom.name: String should match pattern '^[a-zA-Z0-9_-]{1,128}$'`. The internal registry used dotted names (`analytics.get_par_analysis`) to enable glob patterns like `analytics.*` via fnmatch. The Anthropic API rejects dots in tool names.

**Fix:** Translate at the API boundary only. `ToolSpec.to_api_schema()` replaces `.` with `_` when building the API payload. `AgentConfig.get_handler()` matches BOTH the dotted name (registry key) and the underscored name (what Claude sends back in tool_use blocks). Internal registry keeps dots so glob patterns work.

**Rule:** When the internal representation of a name differs from what the external API accepts, translate at the boundary in both directions. Never propagate the external constraint into internal code.

---

## 2026-04-17 — Rate-limit engineering for multi-turn agents

**Problem:** Memo agent blew past 10K input-tokens-per-minute rate limit within 2-3 sections because every turn re-sent the accumulated conversation. By turn 8 the conversation is ~30K tokens; making 4 such calls within a minute = 120K ITPM.

**Root cause:** Long-conversation agents compound token cost exponentially. A single-burst agent with 5-turn cap consumes ~10K tokens total, fine. A 30-turn memo agent consumes 150K+ total with bursts that breach any org cap.

**Fix pattern (hybrid pipeline):**
1. Parallel structured sections each in their own isolated context (no accumulation).
2. Short-burst agents (max 5 turns) for research — returns JSON, not prose.
3. Judgment sections synthesized sequentially by a non-agent Opus call that sees body + research pack (no tool loop).
4. Central client with `max_retries=3` absorbs transient 429s via SDK exponential backoff.
5. `LAITH_PARALLEL_SECTIONS=3` cap on stage-2 concurrency prevents parallel burst from exceeding ITPM.

**Rule:** Never build a long-running multi-turn agent where context accumulates across >5 turns unless the user can afford enterprise rate limits. Prefer isolated short bursts + sequential synthesis. For internal operations that need tool calls, set `max_turns=5` as the default and only raise with explicit justification.

---

## 2026-04-17 — Transient fields in storage: strip at the save boundary

**Problem:** I wanted the memo object to carry rich runtime data (research packs, citation issues) so the polish pass could see it, but I didn't want that data to bloat the permanent `v{N}.json` memo file. First attempt was to pop the fields in the caller before calling `storage.save(memo)` — but there were two save paths (legacy endpoint + agent SSE) and it was easy to forget in one of them.

**Fix:** Put the strip logic in `MemoStorage.save()` itself. Pop `_research_packs` and `_citation_issues` BEFORE writing the version file. If the fields have content, write them to sidecar files (`research_packs.json`, `citation_issues.json`) next to the memo. Both save paths get the right behavior for free.

**Rule:** Convention: prefix transient fields with underscore (`_research_packs`, `_citation_issues`). Make storage modules aware of the convention and responsible for stripping. Callers shouldn't need to remember which fields are transient — storage knows.

---

## 2026-04-17 — Priority ordering bug: iterate priority list, not stances list

**Problem:** `record_memo_thesis_to_mind()` was supposed to prefer `investment_thesis` stance over `exec_summary` when both existed. Wrote:
```python
priority = ("investment_thesis", "exec_summary", "recommendation")
headline = next((s for s in stances if s["section_key"] in priority), stances[0])
```
This iterates `stances` (dict insertion order) and picks the first stance whose key is ANYWHERE in priority — so `exec_summary` (if inserted first) wins regardless of priority rank.

**Fix:** Iterate the priority list in order, picking the first stance matching each priority key:
```python
headline = next(
    (s for key in priority for s in stances if s["section_key"] == key),
    stances[0],
)
```
The outer loop walks priority in rank order; the inner generator finds a matching stance. First match wins.

**Rule:** When "prefer A over B" logic needs to respect order, iterate the PRIORITY list, not the DATA list. Using `x in priority` checks membership but loses rank. Using nested comprehension `for rank in priority for item in data` walks ranks in order. Caught by a unit test checking both stances were present — manual test would have missed it if `investment_thesis` happened to be inserted first.

---

## 2026-04-17 — Integration discipline: infrastructure ≠ feature

**Problem:** Built a complete agent framework (41 tools, 4 agent types, SSE streaming, rate limiting, 69 tests) but left it dormant. Backend had `if mode == 'agent'` branches, api.js had `getExecutiveSummaryAgent()` function, `useAgentStream` hook existed — but no frontend component actually passed `mode: 'agent'`. The infrastructure was correct and tested, but the user experience was unchanged. Marked the plan as complete because every technical component existed.

**Root cause:** The plan was organized by technical layer (runtime → tools → endpoints → frontend hooks), not by user outcome. Verification was component-level ("does this function exist?") not flow-level ("when the user clicks Generate Commentary, does the agent path execute?"). Treated "capability exists" as "capability is active."

**Rules (BINDING for all future plans):**
1. **Organize plans by user-visible outcome, not technical layer.** Each feature is a vertical slice: backend + frontend + wiring + verification. A feature is not done until the user's experience changes.
2. **Write verification steps as user actions.** Bad: "✅ `generate_agent_commentary()` exists." Good: "✅ Load dashboard → click Generate → backend logs show agent path, not legacy path."
3. **For every new function/hook/endpoint, answer: "Who calls this?"** If no existing call site invokes the new code, it's dead capability. Show the specific line in a .jsx component or endpoint handler that triggers it.
4. **Demand a "diff of user experience" before marking complete.** "What does the user see differently now vs before?" If the answer is only "new endpoints exist" — it's an API, not a feature.
5. **Never mark a multi-phase plan complete without an integration sweep.** After all phases, audit: does every new backend capability have a frontend caller? Does every new frontend hook have a component using it? Does every event listener actually do work (not just log)?

## 2026-04-16 — Always --no-cache backend builds in deploy.sh

**Problem:** Docker's `COPY core/` layer cache doesn't reliably invalidate after `git pull`. The `--no-cache` detection logic (comparing HEAD before/after pull) only catches changes in the *current* pull. If a previous deploy pulled code but built with stale cache, subsequent deploys see "Already up to date" and never trigger `--no-cache`. Required manual `docker compose build --no-cache backend` multiple times.
**Fix:** Changed `deploy.sh` to always use `--no-cache` for backend builds. The ~2min build time is acceptable for infrequent deploys. Frontend still uses cache (it invalidates correctly).
**Rule:** Don't try to be clever with Docker cache invalidation on deploy. The cost of a stale container (broken features, debugging time) far exceeds the cost of a 2-minute rebuild.

## 2026-04-16 — Worktrees can't run ETL scripts that read raw data files

**Problem:** ETL script `prepare_tamara_data.py` uses `PROJECT_ROOT` (derived from `__file__`) to find source data. When run from a worktree, `PROJECT_ROOT` points to the worktree directory which doesn't have raw dataroom files (they're not in git). The script silently produced empty sections.
**Fix:** Copy the modified script to the main repo and run from there, or set `PROJECT_ROOT` explicitly. The JSON outputs then need to be copied back to the worktree.
**Rule:** Any script that reads from `data/*/dataroom/` (raw files) must be run from the main repo, not a worktree. The ETL output (JSON snapshots) should be committed so it IS available in worktrees.

## 2026-04-16 — Use data-driven keys, not hardcoded Unicode strings

**Problem:** Excel values contained en-dash characters (`–`, U+2013) that looked identical to hyphen-minus but were different Unicode codepoints. Hardcoded Python strings `'2\u20133'` didn't match the actual JSON values `'2–3'` from openpyxl parsing, causing enrichment lookups to silently miss.
**Fix:** Instead of iterating over hardcoded key lists, extract the actual keys from the data (`sorted(total_by_stage.keys())`). This is resilient to any Unicode encoding the source uses.
**Rule:** When processing user-provided Excel data, never hardcode dimension values. Always derive them from the data itself.

## 2026-04-16 — Dataroom registry stores platform-specific filepaths

**Problem:** `registry.json` stores filepaths with whatever separator the OS produces. Klaim/Tamara had relative Windows backslash paths (`data\klaim\dataroom\file.pdf`), Aajil had absolute Windows paths (`C:\Users\...\data\Aajil\...`). The document view endpoint did `os.path.exists(filepath)` on the raw path — fails on Linux production. Re-ingest also failed to match existing files when separator changed.
**Fix:** Added `_normalize_filepath()` to `core/dataroom/engine.py` — normalizes all paths to forward slashes. Applied at: registry reads (comparison), disk scan comparisons, removal detection, new record storage, and view endpoint resolution.
**Rule:** Any filepath stored in JSON/config files must be normalized to forward slashes before storage. When reading stored paths for filesystem access, resolve relative paths against a known root and normalize separators for the current OS.

## 2026-04-16 — Docker compose build caches stale code after git pull

**Problem:** `deploy.sh` ran `git pull` then `docker compose build`, but Docker cached the `COPY core/` and `COPY backend/` layers from a previous build. The container ran old code despite the host having new files. Health check and ingest calls failed because the container didn't have the new `/health` endpoint.
**Fix:** `deploy.sh` now compares `HEAD` before and after `git pull`. If any `core/` or `backend/` files changed, it runs `--no-cache` for the backend build automatically.
**Rule:** When adding deploy-time features that depend on new backend code (endpoints, Python imports), always verify the container actually has the new code. `docker compose build` with Docker's layer cache is not guaranteed to pick up file changes after `git pull`.

## 2026-04-16 — Production endpoints require auth — use Python imports for internal calls

**Problem:** `deploy.sh` tried to call the dataroom ingest endpoint via HTTP from inside the container, but Cloudflare Auth middleware returned 401. Internal deploy scripts can't authenticate against the production auth layer.
**Fix:** Call `DataRoomEngine.ingest()` directly via `docker compose exec -T backend python -c "..."` — bypasses HTTP entirely. Added `/health` endpoint to auth skip list for future health checks.
**Rule:** Deploy scripts that need to trigger backend operations should use direct Python imports, not HTTP endpoints. HTTP endpoints have auth middleware in production.

## 2026-04-15 — Runtime data artifacts must be committed in EOD

**Problem:** Session 19 ingested Tamara data room (226 files, registry.json) but the EOD process didn't commit `registry.json` — it only existed in the worktree's working directory. When the worktree was cleaned up, the registry was lost. Found it by accident in a stale worktree (`nifty-chebyshev`).
**Fix:** Added Step 1b to `/eod` — explicit check for untracked data artifacts: `registry.json`, `mind/*.jsonl`, `relations.json`, `*_extracted.json`, `reports/memos/`. These are runtime-generated but represent expensive work product (AI extraction, data room ingestion).
**Rule:** Any file generated by an expensive operation (AI calls, data room ingestion) that can't be cheaply regenerated MUST be committed. The EOD step 1b glob pattern catches these.

## 2026-04-15 — Worktrees don't share .env with main repo

**Problem:** Memo generation in a worktree produced all `placeholder` sections because `ANTHROPIC_API_KEY` wasn't found. The `.env` file exists in the main repo root but not in the worktree directory. `load_dotenv()` without an explicit path doesn't find it.
**Fix:** Pass explicit path to dotenv: `load_dotenv("C:/Users/SharifEid/credit-platform/.env", override=True)` or set env var via shell: `ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d= -f2)`.
**Rule:** When running Python scripts from a worktree, always explicitly set API keys. Don't assume `.env` will be found automatically.

## 2026-04-15 — Whole-book vs facility-specific data classification matters

**Discovery:** User corrected assumption that vintage cohort matrices (Default/Delinquency/Dilution breakdowns by product) were facility-specific. They are whole-book data representing Tamara's overall underwriting quality, not the securitised pool. Only HSBC investor reports, legal DD (labeled "ABF"), and debt presentations are facility-specific.
**Rule:** Don't assume data room documents are facility-specific based on their analytical content (vintage matrices, cohort data). The distinction between whole-book and facility pool requires understanding the document's source and audience. HSBC trustee reports = facility. Internal analytics = likely whole-book. When ambiguous, ask.

---

## 2026-04-15 — Company-level directories: legal/, mind/, dataroom/

**Decision:** Moved `legal/` and `mind/` from product level (`data/{company}/{product}/`) to company level (`data/{company}/`), matching the existing pattern for `dataroom/`. These resources are shared across all products within a company — facility agreements and institutional memory aren't product-specific.
**Rule:** When adding a new shared directory under a company, remember to: (1) add it to `_NON_PRODUCT_DIRS` in `core/loader.py` so it's not discovered as a product, (2) update ALL discovery loops that iterate `company/product/` subdirectories (operator, intelligence, briefing, kb_query, master_mind — there are many), (3) update tests that create mock directory structures. A single `get_X_dir()` function is the right pattern — but watch for hardcoded paths in discovery loops that bypass it.

## 2026-04-15 — Parallel branch path migrations require data file audits

**Discovery:** A parallel branch moved `mind/` and `legal/` from product-level to company-level (`data/{company}/mind/` instead of `data/{company}/{product}/mind/`). Code changes referencing `base_dir` attributes were fine — they automatically pick up new paths. But *data files* I created at `data/Tamara/KSA/mind/` needed manual migration to `data/Tamara/mind/`. Multi-product companies also needed entries merged (KSA + UAE into one directory with `product` metadata tags).
**Rule:** When a parallel branch changes directory structure, audit (1) code paths (grep for old pattern), (2) new data files created in this session, and (3) attribute-based references (safe if constructors change). Data files are the easiest to miss because they don't show up in code diffs.

## 2026-04-15 — React.useState inside IIFE render callbacks breaks hooks rules

**Discovery:** Tried adding `React.useState` inside an immediately-invoked function expression within a `renderSection()` switch-case return. This violates React's Rules of Hooks — hooks must be at the top level of a component, not inside callbacks/IIFEs. Fixed by using the first product as default instead of a stateful selector.
**Rule:** Never use `useState` inside `(() => { ... })()` patterns within render functions. If you need local state within a switch case, extract it to a separate component or use parent-level state.

## 2026-04-15 — Cascade Volume = Principal Amount, not Bill Notional

**Discovery:** Compared Laith's computed volume (SAR 327M) vs Cascade Debt's displayed volume (SAR 381M). After testing all tape columns against Cascade's monthly figures, found that Cascade uses `Principal Amount` (bill + margin + origination fee, no VAT) — NOT `Bill Notional` (raw materials cost) and NOT `Sale Total` (includes VAT). The match was exact to within SAR 5-180 per month.
**Rule:** When onboarding from an external platform, always cross-validate specific monthly figures (not just totals) against multiple tape columns to identify the exact mapping. Check: Bill, Sale Notional, Sale Total, Principal Amount. A 16% discrepancy should trigger immediate investigation.

## 2026-04-15 — React useState must be before any early return

**Discovery:** Added `useState` for `dpdThreshold` and `tractionView` after the loading early-return check. React's Rules of Hooks require all hooks to be called in the same order every render. The early return on first render (loading=true) meant those hooks didn't exist, causing "Rendered more hooks than during the previous render" crash.
**Rule:** ALL useState/useEffect calls MUST be before any `if (loading) return` or `if (!data) return` statements in a component.

## 2026-04-15 — Recharts ResponsiveContainer needs explicit width and height

**Discovery:** Charts rendered as empty boxes (title visible, no bars/lines). The `<ResponsiveContainer>` had no width/height props. Unlike CSS containers, Recharts' ResponsiveContainer collapses to zero height without explicit dimensions.
**Rule:** Always use `<ResponsiveContainer width="100%" height={300}>` — never bare `<ResponsiveContainer>`.

## 2026-04-15 — Growth stats must skip partial months

**Discovery:** MoM growth showed -74.8% (vs Cascade's +32.36%) because April had only 13 days of data. The last month in the tape is almost always partial.
**Rule:** For MoM/QoQ/YoY growth calculations, detect partial months (last month has < 25 days) and use the second-to-last month as the reference. Add `as_of` to the growth stats to show which month was used.

## 2026-04-15 — Overdue No of Installments can be fractional

**Discovery:** Delinquency bucketing showed 320/342 deals (22 missing). The `Overdue No of Installments` column had fractional values (0.02, 0.5, 1.66) — not integer installment counts. These fell through `== 0`, `== 1`, `== 2` checks.
**Rule:** Always `.round().astype(int)` before bucketing overdue installment counts. Tape columns that look like integers may contain fractional values from the source system's interpolation.

---

## 2026-04-14 — load_dotenv() does not override existing env vars by default

**Discovery:** `ANTHROPIC_API_KEY` was set as an empty string in the parent shell environment. `load_dotenv()` (python-dotenv) does NOT override existing env vars by default — it only sets vars that don't exist yet. So even though `.env` had the correct key, `os.environ.get("ANTHROPIC_API_KEY")` returned `""` (empty string, falsy), causing Claude RAG synthesis to silently fall back to retrieval-only mode.
**Rule:** Always use `load_dotenv(override=True)` when the `.env` file should be the source of truth. This is especially important for API keys that may exist as empty strings in CI/CD, Docker, or inherited shell environments. Without `override=True`, a stale empty env var silently shadows the `.env` value.

## 2026-04-14 — Competitive platform analysis is high-value for onboarding

**Discovery:** Researching the Cascade Debt platform (Aajil's existing reporting tool) before designing the dashboard yielded 6 concrete features to learn from: DPD 7 threshold, Traction dual view, Loan/Borrower cohort toggle, With/Without Cure toggle, Weekly Collection Rates, and global "Display by" segmentation. Several of these are gaps in our existing platform that apply to ALL companies, not just Aajil.
**Rule:** When onboarding a new company that uses an external reporting tool, always explore that tool first. It reveals (1) what data columns to expect in the tape, (2) what visualizations the IC is already familiar with, (3) platform-wide feature gaps to address. The "Display by" segmentation and configurable DPD thresholds are direct lessons that improve the entire platform.

## 2026-04-14 — New company onboarding follows the Tamara pattern when tape is pending

**Discovery:** Aajil has an investor deck but no loan tape yet (coming from Cascade Debt). The correct pattern is data-room-ingestion → JSON snapshot → read-only dashboard → Phase B conversion to SILQ-style DataFrame compute functions when tape arrives. This is exactly the Tamara pattern. Key files: `scripts/prepare_{company}_data.py` → `core/analysis_{company}.py` → `{Company}Dashboard.jsx`. Backend routing branches needed in 6+ locations in main.py.
**Rule:** For companies without a tape: (1) create extraction script that produces JSON, (2) write parser/enrichment analysis module, (3) build read-only dashboard, (4) document expected tape columns in methodology for Phase B. Always wire ALL routing branches: /summary, /date-range, /methodology, /aggregate-stats, AI context builders, tab insight lists.

---

## 2026-04-14 — Mobile flex layouts need explicit flex-direction: column

**Discovery:** MemoEditor's main layout container used `display: flex` (defaults to `flex-direction: row`). On desktop, the sidebar nav + content panel worked fine side-by-side. On mobile, the horizontal tab bar and content panel were also side-by-side, causing the content to get 0 width and be clipped by `overflow: hidden`. The page appeared completely blank — no tabs, no content, just an empty bordered box.
**Rule:** Any flex container that switches between a sidebar layout (desktop) and a stacked layout (mobile) MUST include `flexDirection: isMobile ? 'column' : 'row'`. The default `row` breaks mobile. Audit all `display: flex` containers that have both a `{!isMobile && ...}` desktop child and a `{isMobile && ...}` mobile child — the parent layout must also be responsive.

## 2026-04-14 — Always verify argument count when calling storage/service methods

**Discovery:** `_memo_storage.update_section()` requires `(company, product, memo_id, section_key, content)` but both call sites in `main.py` passed only `(memo_id, section_key, content)` — missing `company` and `product`. This caused a TypeError on any section edit or regeneration attempt. The bug was introduced when the endpoint handler parameters didn't match the storage method signature.
**Rule:** When calling a storage/service method from an endpoint handler, always verify that the handler's path parameters (`company`, `product`, `memo_id`) are forwarded in the correct order. If the method signature has 5+ positional args, use keyword arguments to make the mapping explicit and prevent positional misalignment.

## 2026-04-14 — New tapes must be assessed for scope before loading as snapshots

**Discovery:** April 14 tape had 357 deals (99.4% active) vs March's 7,697 (81% completed). Loading it as a regular snapshot would show 45% collection rate vs 91%, alarming the dashboard. It was an active-deals-only extract, not a full portfolio snapshot. The test suite also broke because `_find_latest_tape()` picked it up automatically and tests assumed a mature portfolio.
**Rule:** When a new tape arrives: (1) check deal count vs prior tape — a 90%+ drop means different scope, (2) check Status distribution — if >90% Executed, it's likely active-only, (3) confirm with the company before loading, (4) use a `staging/` folder for unconfirmed tapes to keep them out of the platform and test fixtures.

---

## 2026-04-13 — Data room must live at company level, not product level

**Discovery:** The data room engine stored everything at `data/{company}/{product}/dataroom/` but the actual data room files live at `data/{company}/dataroom/` (company level). This caused: (1) the engine couldn't find files, (2) `dataroom` was picked up as a "product" by the loader, (3) the `_EXCLUDE_DIRS` set blocked scanning when source path contained "dataroom" in its parts.
**Rule:** Data room = company-level (`data/{company}/dataroom/`). Products share the same data room. The engine's output subdirs (`chunks/`, `analytics/`) go inside the dataroom dir. Exclude those subdirs from scanning, not "dataroom" itself. Also exclude "dataroom" from `get_products()` so it's not treated as a product.

## 2026-04-13 — Memo sections referencing data room are only as good as the data room coverage

**Discovery:** The Klaim memo's "Market & Competitive Context" section honestly flagged that data room sources had low relevance scores (0.11-0.25) for market data. The "Financial Performance" section was similarly thin. But "Facility Structure" and "Credit Quality" were rich because the legal documents and tape analytics provided strong evidence.
**Rule:** Before generating a memo, check data room coverage per section. Sections that rely on data room (company_overview, market_context, facility_structure, financial_performance) need corresponding document types ingested. If coverage is thin, flag it upfront rather than generating speculative content. The memo appendix (auto-generated) lists all sources — review it to assess coverage.

---

## 2026-04-13 — Never auto-ingest external directories without asking the user first

**Discovery:** The data room ingest endpoint was called without specifying a source path, which caused it to scan the default OneDrive directory and pull in 23 files — including pitch decks, corporate docs, and other materials that weren't intended for the data room. The user wasn't asked which folder to ingest or what documents to include.
**Rule:** Always ask the user which directory/files to ingest before running data room ingestion. The user should specify the source path explicitly. Don't assume a default OneDrive or external folder. For Klaim, only facility agreements + platform tapes + AI-generated analytics belong in the data room.

---

## 2026-04-13 — Non-data JSON files in product directories break snapshot loader

**Discovery:** `covenant_history.json` was created in `data/klaim/UAE_healthcare/` by the covenants endpoint. The loader's `get_snapshots()` picks up all `.json` files, and `covenant_history.json` has no date prefix → `extract_date_from_filename()` returns None → `sort()` crashes on `'<' not supported between instances of 'str' and 'NoneType'`. Same risk for `facility_params.json` and `debtor_validation.json`.
**Rule:** Any new JSON file created in a product directory must be added to `_EXCLUDE` in `core/loader.py`. Alternatively, non-data files should go in subdirectories (legal/, mind/) rather than the product root. The existing `_EXCLUDE` set only had `config.json` and `methodology.json`.

## 2026-04-13 — Analytics bridge must handle both dict and list covenant formats

**Discovery:** Tamara's covenant triggers are stored as a list of objects (`[{name, status, ...}]`) but the analytics bridge assumed dict format (`{trigger_name: {status: ...}}`). The `.items()` call on a list caused `'list' object has no attribute 'items'`. This is the same class of bug as the DocumentLibrary `by_type` issue (session 15).
**Rule:** When accessing data structures from different company types, always check with `isinstance()` before calling `.items()`, `.values()`, or other dict-specific methods. Summary-type companies (Ejari, Tamara) may use different data shapes than tape companies (Klaim, SILQ).

---

## 2026-04-13 — Event deduplication needed when helper is called per-endpoint

**Discovery:** `_load()` in `backend/main.py` is called by 30+ chart endpoints on every request. Firing `TAPE_INGESTED` inside `_load()` without deduplication would trigger entity extraction, thesis drift checks, and compilation 30+ times per page load. Solution: module-level `_tape_events_fired: set` that tracks `(company, product, snapshot)` tuples — fires once per unique tape per process lifetime.
**Rule:** When wiring events into helper functions that are called from many endpoints, always add deduplication. A module-level set is the simplest approach for per-session dedup. It resets on server restart, which is correct behavior. The cost of a 30-element set is negligible; the cost of 30 redundant entity extractions is not.

## 2026-04-13 — Memo edit learning requires capturing old content BEFORE update

**Discovery:** The memo section update endpoint was passing `''` for `ai_version` to `cm.record_memo_edit()`. The learning engine skips corrections where `ai_words == 0` (empty original). The fix is to load the memo before `update_section()` to capture the old content, then pass it as `ai_version`. This adds one file read but is necessary for the learning loop to function.
**Rule:** When recording before/after pairs for learning, always capture the "before" state BEFORE the mutation. This seems obvious but the original code was written before the learning engine existed — the empty string was a placeholder that became a bug when the downstream consumer was built.

## 2026-04-13 — Backend nested objects vs frontend flat value assumptions

**Discovery:** `DataRoomEngine.get_stats()` returns `by_type` as `{"pdf": {"count": 5, "chunks": 20, "pages": 100}}` but `DocumentLibrary.jsx` treated each value as a plain number (`count` directly), causing a React render crash that blanked the entire page. No error boundary caught it.
**Rule:** When a backend API returns nested objects where the frontend expects flat values, the crash is silent (blank page, no error message). Always check API response shape against frontend consumption. When adding structured data to an existing API response, check all consumers — the frontend may have been written against a simpler schema or a different version of the backend.

## 2026-04-13 — Absolute-positioned badges need flow content padding reservation

**Discovery:** KpiCard's trend badge (`position: absolute; top: 12; right: 12`) overlapped the label text on wider desktop cards where "COLLECTION RATE" extended into the badge area. The label had no `paddingRight` to reserve space for the badge. Same pattern existed between the stale "TAPE DATE" badge and trend badge (both in top-right corner), and in TamaraDashboard threshold labels when values are close together.
**Rule:** Whenever you position something `position: absolute` in a corner of a container, the normal-flow content in that corner MUST have matching padding to reserve space. This is easy to miss because collisions only appear when data is longer than expected. Audit checklist: (1) find all `position: absolute` children, (2) check if any flow sibling can grow into that space, (3) add padding/margin if so. Also check for badge-on-badge overlap when multiple absolute elements share a corner — stagger them vertically or give them distinct positions.

## 2026-04-13 — Edit tool writes to the specified path, not the worktree CWD

**Discovery:** When working in a git worktree at `.claude/worktrees/dazzling-payne/`, the Edit tool writes to the exact file path specified. If I specify `C:\Users\SharifEid\credit-platform\frontend\src\...` (the main repo path), it edits the main repo — not the worktree copy. The worktree's files live at `C:\Users\SharifEid\credit-platform\.claude\worktrees\dazzling-payne\frontend\src\...`.
**Rule:** In worktree sessions, ALWAYS use the full worktree path for Edit/Read/Write operations. Check with `pwd` to confirm the worktree root, then use that as the base for all file paths. Edits to the main repo path will silently succeed but won't show in `git diff` from the worktree.

## 2026-04-12 — Worktree .claude/ directory is separate from main repo .claude/

**Discovery:** Slash commands created in `.claude/commands/` inside a worktree are NOT automatically in the main repo's `.claude/commands/`. The worktree has its own copy. The `.gitignore` rule `!.claude/commands/` negates the `.claude/` ignore, but from the worktree root `.claude/` matches the top-level ignore before the negation applies.
**Rule:** When creating new slash commands in a worktree, they need to be manually copied to the main repo's `.claude/commands/` directory. Track this as a post-merge step.

## 2026-04-12 — Event bus design: listeners must never block writes

**Discovery:** When adding event publishing to `_append_entry()` in master_mind.py and company_mind.py, the event bus publish call must be wrapped in try/except and never allowed to prevent the JSONL write from completing. The mind system is the source of truth — events are optional notifications.
**Rule:** Event bus listeners are fire-and-forget. Wrap `event_bus.publish()` in try/except in write paths. The bus itself already catches listener exceptions, but the publish call site must also be guarded against import errors or bus initialization failures.

## 2026-04-12 — Backward-compatible schema extension via metadata._graph

**Discovery:** Extending MindEntry with graph fields (relations, source_refs, node_type, staleness) without a migration. Solved by storing new fields in `metadata["_graph"]` subkey — existing code ignores unknown metadata keys, so old readers work fine. New readers check for `_graph` and extract graph fields. Lazy upgrade on read via `upgrade_entry()`.
**Rule:** When extending an append-only JSONL schema, prefer metadata sub-keys over top-level field additions. This avoids migration scripts and preserves backward compatibility. Use a lazy upgrade function in `_read_entries()` that adds defaults without rewriting files.

---

## 2026-04-11 — Red Team reviews catch calculation errors that tests don't

**Discovery:** The first Red Team review (Mode 6) found `weighted_avg_discount` was double-multiplied by FX rate (`* mult` applied when numerator and denominator already contained `mult` via `total_pv`). This shipped in the original Returns tab code, passed all tests, and was shown to IC. Tests didn't catch it because they tested with `mult=1` (local currency).
**Rule:** Tests with `mult=1.0` won't catch FX-related bugs. Add at least one test per financial function that uses a non-1.0 multiplier (e.g., `mult=0.2723` for AED). Schedule Red Team Mode 6 at least monthly.

## 2026-04-11 — Comments lie about sort order — verify against the actual code

**Discovery:** `backend/main.py` line 2826 had comment `# snaps sorted newest-first` but `get_snapshots()` sorts ascending (oldest-first). The `prev_idx = current_idx + 1` was therefore pointing at the NEXT snapshot, not the previous one. BB movement attribution and covenant trends were comparing against the wrong reference period.
**Rule:** Never trust sort-order comments — verify by reading the sort function. When writing sort-dependent code, reference the sort location: `# sorted ascending in get_snapshots() (loader.py:42)`.

## 2026-04-11 — AI context `try/except: pass` is the most dangerous pattern on a financial platform

**Discovery:** `_build_klaim_full_context()` had 22 `try/except Exception: pass` blocks. When a compute function fails, the AI generates analysis WITHOUT that metric — and can conclude "portfolio is healthy" because it literally doesn't know PAR data was missing. This is worse than a 500 error because the user trusts the confident output.
**Rule:** In AI context builders, NEVER use `except: pass`. Collect errors: `data_gaps.append(str(e))`. Append a DATA GAPS section so the AI can caveat its findings. A visible "could not compute PAR" is infinitely better than a confident "portfolio looks good" that omits PAR.

---

## 2026-04-11 — Subagent-generated code must be verified against actual function signatures
**Mistake:** The memo `analytics_bridge.py` (written by a subagent) imported `parse_tamara_snapshot` from `core.analysis_tamara` — a function that doesn't exist. The real function is `parse_tamara_data`. Would crash at runtime.
**Rule:** When a subagent writes cross-module imports, verify function names exist (`grep "def function_name" target_module.py`). Subagents guess names from patterns.

---

## 2026-04-11 — Registry format must be consistent across all engines writing to the same file
**Mistake:** `AnalyticsSnapshotEngine` wrote `registry.json` as `list[dict]` while `DataRoomEngine` expected `dict[str, dict]`. Using both corrupted the registry.
**Rule:** Multiple modules sharing the same file MUST use the same schema. Add migration paths for format changes.

---

## 2026-04-11 — docker-compose `environment` overrides `env_file`
**Issue:** Added `CF_TEAM=${CF_TEAM:-}` in the `environment` section of docker-compose.yml. The `env_file: .env.production` also contains `CF_TEAM=amwalcp`. Expected `.env.production` to win, but Docker Compose evaluates `environment` AFTER `env_file` — so `${CF_TEAM:-}` (empty from host shell) overwrote the value from the file. Backend saw empty `CF_TEAM`, fell back to dev mode.
**Rule:** Never put `${VAR:-}` in the `environment` section for vars that should come from `env_file`. Either use `env_file` alone (preferred) or hardcode values in `environment`. The `environment` section is for computed values (like `DATABASE_URL` with interpolation) and overrides; `env_file` is for simple key=value secrets.

## 2026-04-11 — Cloudflare Access logo must be hosted publicly
**Issue:** Set the Cloudflare Access login page logo to `https://laithanalytics.ai/lion.png`. The logo didn't render because the entire domain is behind Cloudflare Access — Cloudflare can't fetch the image from a domain it's protecting (chicken-and-egg). The preview in the Cloudflare dashboard worked because it fetches differently than the live page.
**Rule:** Cloudflare Access login page assets (logo, favicon) must be hosted on a public URL not behind the same Access policy. Options: Imgur, S3 bucket, GitHub raw, or create a Cloudflare Access bypass rule for specific asset paths.

## 2026-04-12 — Never name a module after a Python stdlib module

**Issue:** `backend/operator.py` shadows Python's built-in `operator` module. When uvicorn is launched from the `backend/` directory (`cd backend && python -m uvicorn main:app`), Python adds `backend/` to `sys.path` and finds our `operator.py` before the stdlib one. This triggers a circular import crash: `collections` → `from operator import eq` → our `operator.py` → `json` → `re` → `functools` → `collections` (circular). Manifests as `ImportError: cannot import name 'namedtuple' from partially initialized module 'collections'`.
**Rule:** Never name a backend module after a Python stdlib module (`operator`, `collections`, `signal`, `logging`, `string`, `typing`, etc.). Always run uvicorn from the project root using dot notation (`python -m uvicorn backend.main:app`) so `backend/` is a package, not a path entry. If a naming conflict is discovered, rename the file — don't rely on launch instructions.

## 2026-04-12 — Never write integration code against a guessed API

**Issue:** Integration code was written speculatively against a guessed third-party API. Method calls would have thrown `AttributeError` on real use. The code passed review because it looked plausible and the graceful degradation path meant the app never actually tried to use it.
**Rule:** Before writing integration code against a third-party library: (1) install it, (2) inspect the actual API surface (`dir()`, `inspect.signature()`), (3) write a minimal end-to-end test that calls the real API. If you can't install it, stub the integration and document it as TODO — don't write fake-working code. Always verify the package is in `requirements.txt` after implementing.

---

## 2026-04-11 — Don't use a specific company as a "default" fallback
**Issue:** When making Research Chat suggestions per-company, the initial implementation fell back to Klaim suggestions (`SUGGESTED_QUESTIONS.klaim`) for unknown analysis types. User correctly flagged this — Klaim is just one company, not a sensible default.
**Rule:** When building per-company/per-type maps with a fallback, always use a genuinely generic `default` key. No company should be treated as the canonical default — it leaks company-specific language into other contexts.

---

## 2026-04-11 — Every new backend route prefix needs an Nginx proxy location
**Issue:** Added `/operator` endpoints in `backend/operator.py` but never added a corresponding `location /operator` block in `docker/nginx.conf`. On production, Nginx served `index.html` (SPA fallback) instead of proxying to the backend. The frontend received HTML instead of JSON, axios threw a parse error, and the page showed empty content. Took a second round of debugging (after the user sent production screenshots) to identify Nginx as the culprit.
**Rule:** When adding a new route prefix to the backend (e.g., `/operator`, `/mind`, `/memo-templates`), ALWAYS add a matching `location` block in `docker/nginx.conf`. The Nginx config only proxies explicitly listed prefixes — everything else serves `index.html`. Checklist: backend route → nginx.conf → deploy.
**2026-04-12 repeat:** Happened again with new backend endpoints — forgot the nginx rule. Production returned HTML instead of JSON. This is now the #1 production deployment gotcha.

## 2026-04-11 — Internal directories in `data/` must be filtered at the source
**Issue:** `_master_mind` directory lives under `data/` alongside real company directories. `get_companies()` returned it as a company, causing a ghost card on the landing page. The `operator.py` endpoint had its own `startswith("_")` filter, but `main.py`'s `/companies` and `/aggregate-stats` endpoints did not — fix at the source (`get_companies()`) rather than adding filters in every caller.
**Rule:** When a utility function like `get_companies()` returns data consumed by multiple callers, fix the function itself rather than patching each consumer. Defensive filters in callers are OK as belt-and-suspenders but should not be the primary fix.

## 2026-04-11 — Always add error states to pages that fetch data on mount
**Issue:** `OperatorCenter.jsx` fetched from `/operator/status` on mount, but only had a loading state — no error state. When the API was unreachable, the page rendered blank with no feedback. User sees nothing and can't diagnose the problem.
**Rule:** Every page/component that fetches data on mount needs three states: loading, error, and success. The error state should show what went wrong and offer a retry action. Never silently swallow API errors in a catch block that only logs to console.

---

## 2026-04-13 — Adopted Karpathy coding discipline principles into CLAUDE.md

**Context:** Adapted Andrej Karpathy's 4 LLM coding principles (via `forrestchang/andrej-karpathy-skills`) into the project's Workflow Rules. The principles address the three most common LLM coding pitfalls: silent assumptions, overcomplicated code, and drive-by refactoring.
**What changed:**
- Added "Coding Discipline" section to CLAUDE.md with 4 explicit principles (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution)
- Strengthened Planning with "state assumptions" and "surface ambiguity" rules — directly addressing 10+ lessons.md entries caused by silent assumptions (sort order, registry format, subagent function names)
- Tightened Subagent rule with quality gates (spec + success criteria + constraints) — directly addressing analytics_bridge phantom import lesson
- Tightened bug fixing from "just fix it" to "reproduce with test → find root cause → fix" — directly addressing the 28 red team findings pattern
- Added "test-first by default" to Verification with non-1.0 FX multiplier requirement — directly addressing the weighted_avg_discount double-multiply lesson
**Rule:** These are preventive rules. Most lessons.md entries document post-hoc corrections. The Karpathy principles encode the discipline that would have prevented those mistakes. Review them alongside lessons.md at session start.

---

## 2026-04-11 — EOD MUST merge feature branch into main before pushing
**Mistake:** `/eod` Step 9 says "push to main" but when work was done on a feature branch (`claude/prepare-context-DToUt`), I pushed to the feature branch instead and rationalized skipping the merge. The deploy script pulls `main` — so the code never reached production.
**Rule:** EOD Step 9 is non-negotiable: if on a feature branch, `git checkout main && git merge <branch> --no-edit && git push origin main`. The `/eod` command has been updated to make this explicit. Never skip this step regardless of what the session task instructions say about which branch to develop on.

---

## 2026-04-11 — Postgres password is baked into the Docker volume at first init
**Issue:** `POSTGRES_PASSWORD` in `docker-compose.yml` only sets the password when the `pgdata` volume is first created. Changing it later in `.env` doesn't update the existing database. If the volume was created with a blank password, you must `ALTER USER` inside the running container before the new password will work. Production DB password: `laith`.
**Rule:** When debugging "password authentication failed" after changing `POSTGRES_PASSWORD`, remember the volume already has the old password. Fix inside Postgres first: `docker compose exec db psql -U laith -d laith_credit -c "ALTER USER laith PASSWORD 'new_pw';"`.

---

## 2026-04-11 — Docker Compose reads `${VAR}` from `.env` in project root, not `.env.production`
**Issue:** `docker-compose.yml` interpolates `${POSTGRES_PASSWORD}` from the shell environment or a `.env` file in the project root. The `env_file: .env.production` directive only loads vars into the container's environment, NOT into docker-compose's variable substitution. Appending `POSTGRES_PASSWORD` to `.env.production` had no effect on the `WARN: variable not set` message.
**Rule:** Variables used in `docker-compose.yml` `${...}` syntax must be in `.env` (project root) or exported in the shell. Variables needed only by the app go in `.env.production` (loaded via `env_file`).

---

## 2026-04-11 — Always verify requirements.txt matches local venv after adding new packages
**Mistake:** `python-multipart` was installed locally in session 4 (needed by `UploadFile` in `backend/legal.py`) but never added to `backend/requirements.txt`. The Docker container crashed on startup because the package was missing. The site was down and it wasn't caught for multiple sessions.
**Rule:** After any session that adds a new Python import, check `backend/requirements.txt` before EOD. A quick verification: `grep -r "^from\|^import" backend/ core/ | grep -v __pycache__ | sort -u` vs contents of requirements.txt. Also: the `/eod` function should eventually include a "verify Docker builds" step.

---

## 2026-04-11 — .gitignore blocks `.claude/` — use `git add -f` for slash commands
**Issue:** `.claude/` directory is in `.gitignore` (likely from a default template). When trying to `git add .claude/commands/ops.md`, git silently ignores it. Must use `git add -f .claude/commands/ops.md` to force-add individual files.
**Rule:** When adding new slash commands to `.claude/commands/`, always use `git add -f`.

---

## 2026-04-11 — Place log_activity() calls BEFORE the return statement, not after
**Mistake:** When adding `log_activity()` to the breach notification endpoint, the call was placed after the `return {...}` statement, making it unreachable dead code.
**Rule:** When instrumenting endpoints with logging, always place the log call before the return. If the return builds a dict inline, either: (1) assign to a variable first, log, then return, or (2) place the log call on the line before `return {`.

---

## 2026-04-11 — Operator state reads from existing files, no new infrastructure needed
**Design decision:** The Operator Command Center (`/operator/status`) reads from files that already exist (config.json, registry.json, mind/*.jsonl, legal/*_extracted.json, reports/ai_cache/) rather than introducing a new database or state system. Gap detection uses heuristic rules against these existing files. This keeps the system simple and avoids migration costs. Personal follow-ups are stored separately in `tasks/operator_todo.json` (not tasks/todo.md which is Claude's session scratch space).

---

## 2026-04-10 — Multi-document extraction must merge, not pick latest
**Mistake:** `load_latest_extraction()` picked the single document with the latest `extracted_at` timestamp. When all 4 Klaim documents had the same timestamp, it alphabetically chose "Fee letter" — returning 0 covenants, 0 reporting, 0 EODs (all the substance is in the MMA/MRPA).
**Rule:** For multi-document facilities, always merge all extractions. Lists (covenants, EODs, reporting) are concatenated and deduped by name. Dicts (facility_terms) are merged with primary credit_agreement winning on conflict. Track `source_documents` array for provenance.

---

## 2026-04-10 — Relative paths in core/ modules break when backend runs from subdirectory
**Mistake:** `get_legal_dir()` used `os.path.join('data', company, product, 'legal')` — a relative path. When uvicorn runs from `backend/`, this resolved to `backend/data/klaim/...` which doesn't exist. The function returned an empty list, making all Legal Analysis tabs show "no documents".
**Rule:** All path construction in `core/` modules must use `os.path.dirname(os.path.abspath(__file__))` to anchor to the project root, matching the pattern established in `core/loader.py`. Never use bare relative paths like `os.path.join('data', ...)`.

---

## 2026-04-10 — Tape columns represent sellers, not payers (Klaim)
**Lesson:** The `Group` column in Klaim tapes contains healthcare provider names (143 sellers), NOT insurance company names (payers/Account Debtors). The MRPA lists 13 approved Account Debtors (insurance companies), but the tape has no column to identify which insurer owes on each deal. This means the 10% non-eligible debtor concentration limit cannot be monitored from tape data alone. Recommendation: request a payer column in future tape exports.

---

## 2026-04-10 — Registry format must be consistent across all engines writing to the same file
**Mistake:** `AnalyticsSnapshotEngine` wrote `registry.json` as `list[dict]` while `DataRoomEngine` expected `dict[str, dict]`. Running both on the same company corrupted the registry — all DataRoomEngine operations (catalog, search, stats) crashed with `AttributeError: 'list' object has no attribute 'items'`.
**Rule:** When multiple modules read/write the same file, they MUST use the same schema. Either: (1) share a common `_load_registry`/`_save_registry`, (2) add a migration path in the reader (handle both old and new formats), or (3) use separate files. We chose option (2): the snapshot engine now auto-migrates list→dict on read.

---

## 2026-04-10 — Data room ingestion must exclude its own output directories
**Mistake:** `DataRoomEngine.ingest()` recursively scanned a directory and ingested files inside `dataroom/chunks/` — its own output. This created self-referential documents (chunk metadata tables appearing as searchable content), polluting search results and inflating document counts.
**Rule:** Any recursive file scanner MUST exclude directories it writes to. Add `_EXCLUDE_DIRS = {"dataroom", "mind", "__pycache__"}` and check path parts during traversal. More generally: write paths and read paths should never overlap without explicit exclusion.

---

## 2026-04-10 — Living Mind methodology layer requires registration at startup
**Mistake:** `build_mind_context()` Layer 3 (Methodology) returned empty during standalone tests. The methodology data only exists after `register_klaim_methodology()` is called at import time by `main.py`. Standalone scripts don't trigger this registration.
**Rule:** The metric registry is populated at import time via explicit `register_*()` calls in `main.py`. Any code that reads from the registry outside of the FastAPI app (scripts, tests, CLI) must call the registration functions first. This is by design — not a bug — but should be documented.

---

## 2026-04-10 — Parallel worktree sessions need careful merge planning
**Mistake:** Two Claude sessions (Research Hub + Legal Analysis) worked in parallel on different worktrees, both modifying `main.py`, `Sidebar.jsx`, `App.jsx`, and `api.js`. Merge required resolving 3 conflicts.
**Rule:** When running parallel worktree sessions: (1) document which files each session will modify upfront, (2) have the session with fewer shared-file changes commit first, (3) use the handoff prompt pattern to transfer context between sessions. The merge was clean because both sessions added to different sections — additive changes merge well, overlapping edits don't.

---

## 2026-04-09 — Summary endpoint must pass through ALL fields from KPI builder, not cherry-pick
**Mistake:** `get_tamara_summary_kpis()` returned `face_value_label` and `deals_label` fields, but the `/summary` endpoint hardcoded a return dict that only picked specific fields (`total_deals`, `total_purchase_value`, `facility_limit`, etc.) and didn't include the label fields. The frontend received no label overrides and fell back to "Face Value" / "Deals".
**Rule:** When adding new fields to a KPI builder function, always check the endpoint that consumes it — if the endpoint constructs a hardcoded return dict (not `**kpis`), the new fields won't pass through. Either use `**kpis` spread or explicitly add every new field. Grep for the field name in the endpoint response to verify it's included.

---

## 2026-04-09 — Metrics with different semantics must not share the same label
**Mistake:** Tamara's `total_purchase_value` was outstanding AR (a point-in-time balance) but was displayed as "Face Value" (which for Klaim/SILQ means total originated — a cumulative metric). This inflated the aggregate banner from $308M to $665M by mixing fundamentally different metrics. The user caught it.
**Rule:** When onboarding a new company, audit every metric that feeds into shared display components (landing page cards, aggregate stats banner). If the metric has a different semantic meaning than what the label implies, either: (1) use a different field name, (2) pass a custom label, or (3) exclude it from aggregates. Never assume "total_purchase_value" means the same thing across all analysis types.

---

## 2026-04-09 — Uvicorn --reload only watches the --app-dir, not parent imports
**Mistake:** Changed `core/analysis_tamara.py` and `core/loader.py` expecting uvicorn's `--reload` to pick them up. It didn't — the server was started from `backend/` with `--reload` which only watches files in the `backend/` directory, not `core/` (which is a sibling). Had to manually restart the server multiple times.
**Rule:** When running `uvicorn main:app --reload` from `backend/`, file changes in `core/` will NOT trigger a reload. Either: (1) restart the server manually after changing `core/` files, (2) start uvicorn with `--reload-dir ../core` to add the watch path, or (3) touch `backend/main.py` after editing core files (but this is unreliable — the import cache may not refresh).

---

## 2026-04-09 — Adding file extensions to the loader catches unintended files
**Mistake:** Added `.json` to `get_snapshots()` for Tamara data room JSON files. This also matched `config.json` and `methodology.json` in the same directory — they have no date prefix (returning `date: null`) and aren't data snapshots. The frontend saw these extra entries and failed to pass a valid snapshot filename to `/summary`, causing a 404 that broke the Tamara card on the landing page.
**Rule:** When extending `get_snapshots()` to support new file extensions, always add an exclusion list for known non-data files in the same directory. Pattern: `_EXCLUDE = {'config.json', 'methodology.json'}` checked before the extension test. More generally: any time a file-discovery function is broadened, test it against ALL existing directories to check for false positives, not just the new one.

---

## 2026-04-07 — As-of-date only filters deals, not balances — AI must not run on backdated views
**Mistake:** The as_of_date picker filters deals by `Deal date <= as_of_date` but all balance columns (`Collected till date`, `Denied by insurance`, `Outstanding`, etc.) still reflect the tape snapshot date. This means collection rates are inflated, outstanding is understated, PAR is artificially low, and margins are wrong for any backdated view. AI analysis on this data would produce confident but misleading commentary.
**Rule:** (1) Every metric on a backdated view that depends on collection/denial/balance columns must be visually flagged as "reflects tape date". (2) AI endpoints (commentary, executive summary, tab insights) must refuse to run when `as_of_date < snapshot_date` — the AI has no way to distinguish safe from unsafe metrics and will present inflated numbers as fact. (3) When onboarding new tapes or companies, always verify: does `filter_by_date` affect only deal selection, or does it also adjust balances? For point-in-time tapes, the answer is always "deal selection only". (4) Safe metrics in a backdated view: deal count, originated volume, deployment, vintage composition. Unsafe: everything that uses Collected/Denied/Outstanding/Pending columns.

---

## 2026-04-07 — Never skip /eod even if "everything looks clean"
**Mistake:** User asked "do I need eod?" and I said no because the working tree was clean and changes were pushed. But `/eod` Step 10 (sync feature branch to main) was not done — the feature branch with all Docker/deployment code was never merged into main. The server was running from the feature branch instead of main.
**Rule:** Always run `/eod` or explicitly walk through every step. "Working tree is clean" doesn't mean the session is properly closed — branch merging, todo updates, and lessons are separate from commit status.

---

## 2026-04-07 — Roadmap Checklists Drift from "What's Working"
**Mistake:** 15 items in CLAUDE.md's "Analytical Framework Expansion" checklist were still marked `- [ ]` despite all being implemented and documented in "What's Working". The `/eod` command updated "What's Working" (Step 7) but never cross-referenced the roadmap checklists to check off completed items.
**Rule:** During `/eod` Step 7, always scan every `- [ ]` item in "Known Gaps & Next Steps" and check off any that were implemented. Cross-reference against "What's Working" entries. Mark entire sections `✅ COMPLETE` when all items are done. Two sources of truth = eventual drift.

---

## 2026-04-07 — Worktree Edits Don't Affect Running Server
**Mistake:** Edited `core/analysis_silq.py` in the worktree (`.claude/worktrees/serene-heisenberg/`) and expected the running uvicorn server to pick it up. The server was running from the main project root with different file paths. Also, the server was started without `--reload`, so even touching files in the correct directory wouldn't trigger a restart.
**Rule:** When a running backend is serving from the main project root, edits in a worktree won't be picked up. Either: (1) apply the fix to the main project's files directly, or (2) restart the server from the worktree. Also verify `--reload` is enabled — check with `Get-WmiObject Win32_Process` to see the actual command line args.

---

## 2026-04-07 — Standardize Summary Field Names Across Companies
**Mistake:** SILQ's `compute_silq_summary()` returned `total_disbursed` while the frontend expected `total_purchase_value` (the field name Klaim uses). This caused a blank Face Value on the landing page for SILQ. Each company used its own domain-specific field name without a common alias.
**Rule:** When adding a new company, ensure the `/summary` endpoint returns all fields the frontend consumes. The canonical field names are: `total_purchase_value`, `total_deals`, `total_collected`, `total_denied`, `total_pending`, `collection_rate`. If the domain uses a different term (e.g. `total_disbursed`), return BOTH the domain-specific name AND the canonical alias.

---

## 2026-04-07 — Companion metadata files beat inline decorators for large codebases
**Decision:** Instead of adding @metric decorators to 48 compute functions (which would add ~500 lines of metadata inline, cluttering the pure-compute modules), created separate companion files (`methodology_klaim.py`, `methodology_silq.py`) that register metadata after import. This keeps `analysis.py` clean (pure computation) while making methodology content easily editable.
**Rule:** When metadata is large (multi-line strings, nested structures), prefer companion registration files over inline decorators. Reserve decorators for small metadata (< 3 fields).

---

## 2026-04-06 — No new lessons this session (Framework tooling)
Session focused on creating framework slash commands, hooks, and documentation. No code errors or corrections — all deliverables were documentation/config.

---

## 2026-04-05 — No new lessons this session (Ejari formatting)
Session focused on aligning Ejari dashboard formatting with Klaim/SILQ. Straightforward component swap — no mistakes or corrections.

---

## 2026-04-05 — Session Source Determines Browser Access
**Mistake:** Spent significant time trying to configure Playwright MCP to connect to Chrome, going through CDP endpoints, executable paths, and multiple restarts. Root cause: the session was started from mobile (claude.ai), which runs the Claude Code agent in a cloud Linux sandbox with no access to the user's Windows machine. localhost:5173/8000 and Chrome are all unreachable from there.
**Rule:** Browser/Chrome access (via the Claude Code Chrome extension) only works when the session is started from the **Claude Code desktop app** on the same machine as Chrome. If `localhost` is unreachable and Chrome won't connect, the first question is: "Was this session started from mobile or web?" If yes, ask the user to restart from the desktop app. Never attempt Playwright MCP workarounds — they can't cross the sandbox boundary.

---

## 2026-04-05 — ODS Numbers Are Comma-Formatted Strings
**Mistake:** The Ejari ODS workbook stores numbers like `'1,348'` and `'12,727,014'` as formatted strings, not numeric types. `int('1,348')` throws `ValueError`, caught silently by `except Exception: contracts, funded = 0, 0`, returning zeros. Took multiple debugging rounds to find because the backend test (direct API call) wasn't being run until late.
**Rule:** When parsing ODS/Excel cells that should be numeric, always strip commas before converting: `int(str(v).replace(',', '').strip())`. Whenever a backend endpoint silently returns zeros for a field that should have data, immediately test the endpoint directly (`Invoke-RestMethod`) to confirm what's actually being returned before debugging frontend code.

---

## 2026-04-05 — Silent Failures from Wrong Loader Function
**Mistake:** Used `load_snapshot()` for SILQ tapes in `/aggregate-stats`. SILQ requires `load_silq_snapshot()` (multi-sheet Excel). The wrong loader returned empty data silently — bare `except Exception: pass` swallowed the error, leaving `total_deals = 0`.
**Rule:** Never use bare `except: pass` in data loops — at minimum log the error. When adding a new loop over all companies/snapshots, always dispatch to the correct loader per `analysis_type` (silq → `load_silq_snapshot`, klaim → `load_snapshot`, ejari_summary → handle separately).

---

## 2026-04-05 — load_silq_snapshot Returns a Tuple
**Mistake:** Called `df = load_silq_snapshot(...)` then `len(df)` — but `load_silq_snapshot` returns `(df, commentary_text)`. Assigning the tuple to `df` meant `len(df) == 2` and `df.columns` threw, again swallowed silently.
**Rule:** `load_silq_snapshot` always returns `(df, commentary_text)` — always unpack: `df, _ = load_silq_snapshot(...)`. Check the function signature before calling any loader that isn't `load_snapshot`.

---

## 2026-04-05 — Cache Fingerprint Must Include Schema Version
**Mistake:** Changed stats field names (`total_records` → `total_deals`) but the cache fingerprint only tracked snapshot filenames. The cache hit check matched and served stale data with old field names, causing the frontend to show zeros.
**Rule:** Any file-based cache fingerprint must include a schema version constant. Bump `STATS_SCHEMA_VERSION` whenever the response shape changes. Pattern: `fingerprint = ["schema:v3", ...snapshot_ids]`.

---

## 2026-04-02 — Worktree .env Not Found
**Mistake:** Started a uvicorn server in a git worktree (`/.claude/worktrees/peaceful-cray/backend/`) but the `.env` file only exists in the main project root. `load_dotenv()` traverses parent directories but won't find `.env` outside the worktree directory tree. The API call failed with an auth error.
**Rule:** When testing backend changes in a worktree, either: (1) copy `.env` into the worktree root, or (2) copy the changed files to the main project directory and test with the already-running server there. Option 2 is simpler when the main server has `--reload`. Clean up any `.env` copies from worktrees afterward.

---

## 2026-03-28 — SILQ Product Name Cleanup
**Mistake:** Updated all code references (tests, AI prompts, docs) to new product names (RCL, RBF) before verifying the tape data had actually been updated. Tests failed because the Excel file still had old names (RBF_Exc, RBF_NE).
**Rule:** When a task depends on external data changes (tape edits, DB migrations, config changes), verify the data first before updating code that references it. Run a quick data check (`df['column'].value_counts()`) before writing assertions.

---

## 2026-04-01 — Dynamic Grid Reflow from Async Data
**Mistake:** PAR KPI grid used `repeat(${parKpis.length + dtfcKpis.length}, 1fr)` — columns depended on async state. PAR loaded first (3 cols), then DTFC arrived and the grid jumped to 5 cols, visibly resizing the PAR cards mid-view.
**Rule:** Never derive CSS grid column count from async data that loads incrementally. Use a fixed column count (e.g. `repeat(5, 1fr)`) so the layout is stable from first render. Empty cells are better than layout shifts.

---

## 2026-04-09 — Inline styles + responsive design = useBreakpoint hook, not CSS media queries
**Context:** The entire frontend uses inline `style={{}}` objects (not CSS classes or Tailwind). Inline styles cannot use `@media` queries. The architectural choice for mobile responsiveness was a JS-based `useBreakpoint()` hook that returns `{ isMobile, isTablet, isDesktop }` via `matchMedia` listeners, with components branching their inline style values conditionally. An alternative was migrating everything to Tailwind classes, but that would have required rewriting hundreds of style objects across 40+ files.
**Rule:** When adding responsive behavior to an inline-style codebase, prefer a shared `useBreakpoint` hook over migrating to CSS classes. But for grid columns, prefer CSS `auto-fill`/`auto-fit` with `minmax()` — these are intrinsically responsive and don't need JS breakpoint detection at all. `repeat(auto-fill, minmax(140px, 1fr))` replaces `repeat(5, 1fr)` and works at any viewport width without importing any hook.

## 2026-04-09 — Fixed sidebar widths are the #1 mobile killer
**Context:** A 240px fixed sidebar consumed ~50% of a 375px mobile screen, making all company page content unreadable. The fix was converting it to a slide-in drawer with backdrop overlay, coordinated via a React context between the Navbar (hamburger button) and CompanyLayout (drawer).
**Rule:** Any persistent sidebar > 200px must have a mobile-drawer alternative. The pattern: (1) `MobileMenuContext` shared between navbar and layout, (2) sidebar becomes `position: fixed` + `transform: translateX(-100%)` on mobile, (3) backdrop overlay with click-to-close, (4) auto-close on route change, (5) body scroll lock when open.

---

## 2026-04-04 — Emoji Flags Don't Render on Windows Chrome
**Mistake:** Used regional indicator emoji (🇦🇪, 🇸🇦) for country flags on company cards. They render correctly on macOS/Linux but show as two-letter codes (AE, SA) on Windows Chrome — Windows has no built-in emoji flag support.
**Rule:** Never use emoji flags for flags that need to be visually correct across platforms. Use `<img src="https://flagcdn.com/16x12/{cc}.png">` with ISO 3166-1 alpha-2 country codes (ae, sa, us). flagcdn.com is free, fast, and renders consistently everywhere.

---

## 2026-04-04 — replace_all Misses Siblings with Different Indentation
**Mistake:** Used `replace_all: true` to increase font size on two sibling elements ("Portfolio Companies" and "Resources" section labels). Only the first was updated — the second had a different indentation (3 spaces vs 4 spaces), so the string didn't match.
**Rule:** When doing replace_all on repeated patterns that may have slight differences (trailing spaces, indent depth), verify the count of replacements made. If there are N occurrences to update and the tool only matched fewer, check each remaining one individually. Use Grep to confirm 0 remaining instances of the old value.

---

## 2026-04-04 — Rate Already a Percentage, Don't Multiply ×100
**Mistake:** Backend `/summary` returns `collection_rate` as a percentage (e.g. 85.3). The frontend multiplied it by 100 again (→ 8530%). The bug existed in two places: CompanyCard and PortfolioStatsHero.
**Rule:** Before displaying any rate/percentage from the backend, check what unit the endpoint returns. When in doubt, log the raw value. Never multiply a value by 100 without verifying it isn't already a percentage.

---

## 2026-04-04 — Remove Props When Component Becomes Self-Fetching
**Mistake:** After rebuilding PortfolioStatsHero to fetch its own data, Home.jsx still passed `companies={companies} summaries={summaries}` props to it. The component silently ignored them — no error, but dead prop passing.
**Rule:** When refactoring a component from prop-driven to self-fetching, immediately update every call site to remove the now-obsolete props. Grep for all usages before finishing the task.

---

## 2026-04-04 — Canvas z-index and Fixed Background Layering
**Context:** Adding a Canvas animation + SVG pattern behind page content on the landing page.
**Rule:** When stacking fixed-position layers (canvas, pattern, content), assign explicit z-indexes with a gap: `-1` for decorative backgrounds, `0` for canvas, `1` for interactive content. Use `position: relative; z-index: 1` on the stats hero/content wrappers to ensure they sit above the canvas. Without explicit z-index on content wrappers, fixed-positioned canvas can bleed through.

---

## 2026-04-04 — Framer Motion in SVG Context
**Context:** Added Sparkline SVG component inside KpiCard using a `<polyline>` — no Framer Motion needed for static sparklines.
**Rule:** Don't reflexively wrap SVG elements in `motion.*` — Framer Motion has limited SVG transform support. For simple static charts (sparklines, mini donuts) use plain SVG elements. Reserve Framer Motion for layout animations on DOM elements.

---

## 2026-04-04 — Prop Added, Data Not Wired = Half-Done
**Context:** Added `sparklineData` prop to KpiCard and `trend` prop already existed. Neither is being populated from TapeAnalytics because it requires computing a delta or extracting historical series.
**Rule:** When a UI prop is added but the data source isn't wired yet, note it explicitly in todo.md as a follow-up. Don't mark the task complete until data flows end-to-end and the feature is visible in the UI.

---


## 2026-04-09 — Showcase tabs must lead with charts, not tables — tables alone aren't a "showcase"
**Context:** The Tamara plan specified "rich interactive Recharts visualizations" for all 14 tabs, calling them "showcase highlights." In execution, 9 of 14 tabs were downgraded to raw data tables due to time pressure. The plan promised trend lines for financial performance, grouped bars for demographics, projection charts for business plan, and a 17-step waterfall for facility payments. None of these materialized. The result is functional but not the "best possible demonstration of Laith" the user requested.
**Rule:** When a task is explicitly flagged as a showcase or demo, prioritize the 5-6 highest-impact visualizations over completeness. Build the novel/impressive charts first (heatmap, covenant triggers, waterfall), then fill remaining tabs with tables. A dashboard with 5 stunning charts and 9 tables is more impressive than 14 mediocre tables. Also: estimate visualization complexity upfront — a Recharts LineChart takes 15 minutes, a CSS-grid heatmap takes 45, a custom waterfall takes 60. Budget accordingly.

---

## 2026-04-09 — Data extraction failures should be caught and reported, not silently empty
**Context:** The investor reporting, demographics, business plan, and financial master sections all parsed to empty arrays. The prepare script's `try/except` blocks swallowed errors, and the dashboard showed "No data available" without explaining why. The root causes were: (1) investor reporting sheet names don't match the hardcoded expectations, (2) demographics workbook has a different structure than assumed, (3) business plan summary sheet column layout varies. These were all fixable but invisible.
**Rule:** Data preparation scripts must log every extraction attempt with success/failure and row counts. At minimum: `print(f"  Parsed {len(records)} records from {source}")`. When a section returns 0 records, log a WARNING with the attempted file path and expected format. The dashboard should distinguish "data not available" (no source file) from "data extraction failed" (source exists but parser failed) — different colors, different messages.

---

## 2026-04-09 — AI Executive Summary context must be wired before marking a company "onboarded"
**Context:** Tamara was marked as onboarded and committed, but `_build_tamara_full_context()` was never implemented. The AI Executive Summary endpoint falls through to the generic Klaim context builder, which frames Tamara as "healthcare claims factoring" — completely wrong. This would produce a misleading IC-grade document if a user generates an executive summary.
**Rule:** A company is NOT fully onboarded until: (1) all tabs render with data, (2) AI Executive Summary works with correct context, (3) methodology serves correctly, (4) the company appears in FRAMEWORK_INDEX.md. Add these as checklist items in the `/onboard-company` command.

---

## 2026-04-09 — Data room ingestion is a distinct third pattern, not a variant of tape or summary
**Context:** Tamara has ~100 files across PDF, Excel, and mixed formats — nothing like a loan tape or a single ODS workbook. The initial instinct was to force it into the Ejari "summary" pattern, but the parser complexity was totally different. The solution was a three-layer architecture: (1) ETL script that reads raw data room files and produces structured JSON, (2) runtime parser that reads JSON and enriches with presentation fields, (3) frontend dashboard that renders from the enriched JSON. This separation means the messy multi-format parsing runs once (not per-request), the JSON is version-controlled and portable, and the runtime serving is fast.
**Rule:** When onboarding a company whose data is a data room (not a single tape or workbook), always use the ETL → JSON → parser pattern. Never try to parse PDFs or heterogeneous Excel files at runtime. The ETL script lives in `scripts/prepare_{company}_data.py`, the JSON lives in `data/{Company}/{Product}/`, and the parser lives in `core/analysis_{company}.py`. Re-run the ETL when new data arrives in the data room.

---

## 2026-04-09 — Research reports should be a platform capability, not per-company scripts
**Context:** Started to build `scripts/generate_tamara_report.py` as a one-off, but the user correctly identified that this should be a reusable platform feature. Every company benefits from a professional PDF credit research report — the data context, section structure, and AI narrative generation are all parameterizable by analysis_type.
**Rule:** When building a feature that works against a company's parsed data, always ask: "Does this generalize to all companies?" If yes, put it in `core/` with a backend endpoint, not in `scripts/`. The pattern: `core/{capability}.py` with company-specific builders dispatched by analysis_type, plus a `POST` endpoint in `main.py`.

---

## 2026-04-09 — HSBC PDF table parsing requires pdfplumber not PyPDF
**Context:** The HSBC investor reports have structured tables (BB waterfall, trigger tests, concentration limits, stratifications) that need tabular extraction. pdfplumber handles this well — it extracts tables as lists of lists. The table positions and headers are consistent across all 20 reports, making batch processing reliable. PyPDF only extracts raw text without table structure.
**Rule:** For PDF files with structured tables (investor reports, compliance certificates, facility agreements), use pdfplumber. For PDF files with only narrative text, raw text extraction (pypdf) is sufficient. Always test the parser against 2-3 sample files before batch-processing the full set.

---

## 2026-04-09 — Vintage cohort matrices have a consistent structure: header detection matters
**Context:** The ~50 vintage cohort Excel files all follow the same structure (triangular vintage × MOB matrix) but have slight variations: some have a year row above the month row, some don't; some use date strings, others use month names; the vintage column can be labeled "Breakdown D1" or just be the first column. A rigid parser that assumed exact headers would break on half the files.
**Rule:** When parsing Excel files from external sources, build header detection that searches the first 5 rows for known patterns (month names, date formats, keywords) rather than assuming a fixed row. Handle both date-string and month-name column headers. Always log warnings (not errors) for files that don't parse, and continue processing the rest.

---

## 2026-04-09 — Unicode arrows in print statements fail on Windows cp1252 console
**Mistake:** Used `→` (U+2192) in a Python print statement. Crashed on Windows because the console uses cp1252 encoding which doesn't support that character. Quick fix: replace with `->`.
**Rule:** In Python scripts that will run on Windows, never use Unicode arrows, em-dashes, or other non-ASCII symbols in print/log statements. Use ASCII equivalents: `->` not `→`, `--` not `—`, `*` not `•`. Or set `sys.stdout.reconfigure(encoding='utf-8')` at the top of the script, but the ASCII approach is more portable.

---

**Mistake:** SILQ's Overview crammed PAR30/PAR60 into inline KPI cards (PAR60 hidden as PAR30's subtitle), while Klaim had a dedicated "Portfolio at Risk" section with individual PAR cards. The Analysis Framework already defined a 5-level hierarchy (L1-L5) that should guide page structure, but it wasn't being applied to the frontend layout.
**Rule:** When adding a new company or tab, follow the established section structure (Main KPIs → Credit Quality → Leading Indicators). Use the Analysis Framework hierarchy to decide which section a metric belongs in. Don't inline L3 (Credit Quality) metrics with L1 (Size) KPIs. Consistency in section structure, bespoke content within sections.

---

## 2026-04-20 — Layer 2.5 needs a dedicated `asset_class` key, not the company-level `analysis_type`
**Context:** Shipped the External Intelligence Layer 2.5 (session 27, commit `1d17e31`) resolving the asset-class key from `cfg["analysis_type"]`. Passed the `verify_external_intelligence.py` 16-check harness because the harness always injected `analysis_type="healthcare_receivables"` directly. Real configs have `analysis_type="klaim"` / `"silq"` / `"tamara_summary"` / `"aajil"` / `"ejari_summary"` — company-shortnames that drive dashboard routing. These never matched the semantic asset-class filenames (`healthcare_receivables.jsonl`, `bnpl.jsonl`, etc.) so `AssetClassMind(analysis_type)` opened an always-empty file. Every company had Layer 2.5 silently blank from day one. Only caught because a real end-to-end smoke test (approve → promote → check `asset_class_length`) showed 0 instead of non-zero.
**Mistake:** A single overloaded config field carrying two unrelated meanings (routing key + semantic class). One works for the company-specific dashboard layer, the other for the cross-company knowledge layer — the same string can't be both.
**Rule:** When a config field appears to drive two distinct systems, check whether they actually want the same value. If one system slices by company-product ("one-off per tape") and the other by semantic class ("shared across companies in the same class"), they need separate fields. For Layer 2.5: `asset_class` is now distinct from `analysis_type` in every `config.json`, and `build_mind_context()` prefers `asset_class` with an `analysis_type` fallback for legacy configs. Generalizes: any time you're tempted to "reuse" a config field for a new feature, ask whether the field's existing users want the same value as the new feature. If the answer is "mostly but not always," introduce a new field rather than forcing convergence.

---

## 2026-04-20 — Verification harnesses that inject their own inputs can mask the integration bug
**Context:** `scripts/verify_external_intelligence.py` was 16/16 green on the laptop when Finding #3 above was latent. The failing integration path was `build_mind_context(company, product) → read config → resolve asset_class`. The harness never exercised that read-from-config path — every test either passed `analysis_type` explicitly or seeded a test config with `analysis_type="healthcare_receivables"`. The code that reads actual shipped configs was uncovered.
**Mistake:** Structure-level tests that use hand-crafted inputs prove the unit works for the inputs you thought to hand it. They don't prove anything about the inputs real callers produce. Integration risk lives in the gap between "test input space" and "production input space."
**Rule:** Whenever a verification harness exists, add at least one test that reads actual shipped config files from disk (not fixtures). For Layer 2.5 the fix was `test_shipped_configs_have_asset_class_field` in `tests/test_asset_class_resolution.py` — iterates over `data/*/*/config.json` and asserts every shipped config declares the field. This class of test fails any time the shipped state drifts from the code's assumptions. Generalizes to any dispatcher keyed on config data: add a "shipped configs agree with dispatcher expectations" test.

---

## 2026-04-20 — Agent runtime needs per-tool timeouts when tools make nested model calls
**Context:** `AgentRunner.TOOL_TIMEOUT_SECONDS = 30` was a global constant. Worked fine for the existing analytics/dataroom/memo tools — all pure-Python. Broke the moment `external.web_search` shipped, because that handler makes a nested Claude call with server-side `web_search_20250305` which routinely runs 40-90s. Symptom was confusing: handler completes on its own thread + writes the pending entry to disk, but runtime times out at 30s and returns "Tool error: Timed out after 30s" to the agent. Agent then tells the user "search failed" — even though the pending entries are fully populated. Three separate reports of "web_search isn't working" before someone noticed the entries WERE in the queue.
**Mistake:** Single-dimension limit (time) applied uniformly to tools with dramatically different time budgets. Pure-Python tools finish in <1s; nested Claude calls are orders of magnitude slower.
**Rule:** Any runtime limit that's expressed as a single global should be audited when a new category of tool ships. Timeouts, token budgets, turn limits, memoization keys — these are all tool-category-dependent. The fix pattern: add a prefix-keyed override dict (`TOOL_TIMEOUT_OVERRIDES_BY_PREFIX = {"external.": 180}`) + a classmethod resolver (`_timeout_for_tool(tool_name)`), default preserved for existing tools. Zero risk to the happy path; fixes the new category. Generalizes: per-prefix overrides beat global constants whenever tool heterogeneity grows.

---

## 2026-04-20 — Agent-side call-count discipline belongs in the tool description
**Context:** One user request ("search the web for typical default rates in healthcare receivables factoring in MENA") produced three distinct `external.web_search` tool calls with sub-queries ("medical receivables factoring loss rates denial rates Middle East", "healthcare insurance claims factoring default rate benchmark MENA GCC receivables", "default rates healthcare receivables factoring MENA Middle East UAE insurance cl…"). Each call created a separate pending-review entry with 30-40 citations. Tripled Claude token spend, tripled the analyst review load, and made the one-query/one-entry contract implicit in the pending-review UI wrong (the UI doesn't know three entries came from one user request).
**Mistake:** Assumed the agent would infer "make one call" from the tool description's general tone. It won't — agents optimize for completeness, not for call-count minimality, unless explicitly told.
**Rule:** Tool descriptions should include an explicit CALL BUDGET clause when the desired behavior is "one call per user request." Format: "CALL BUDGET: make ONE comprehensive call per user request — craft a single broad query that covers the whole topic rather than splitting into multiple sub-queries. Only make a second call if the first returns no usable results and a clearly different angle is required." Lock this in via a regression test that greps the description for the budget clause (documentation drift kills this otherwise). Generalizes: any tool that costs real money per call OR that creates analyst workload per call needs a call budget in its description, not just in implicit norms.

---

## 2026-04-20 — Gitignored source data + tracked derivative index = broken references cross-machine
**Context:** `data/_asset_class_mind/*.jsonl` files are gitignored (per-machine runtime state, same pattern as `_master_mind/`). The knowledge-graph `data/{co}/mind/relations.json` files — which point at entity UUIDs inside those jsonl files — were NOT gitignored. After session-28 smoke testing, my working tree had 14 new `supersedes` relations in `klaim/mind/relations.json` pointing to UUIDs that only existed in the local gitignored jsonl. Committing those relations would have broken every other machine's knowledge graph (pointers to nothing).
**Mistake:** An index file was tracked while its source-of-truth files were ignored. The index's UUIDs are only meaningful in the context of the local jsonl state.
**Rule:** If a file is an index over other files, it must share the other files' tracking status. Either both tracked (index is reproducible and content is stable) or both ignored (both rebuild on each machine). Apply this test any time you see a `*_index.json`, `registry.json`, `relations.json`, `consolidated.json` — check what it references and whether those references are tracked. Session 24's `dataroom/registry.json` story is the same pattern: registry was tracked, chunks were ignored, doc_ids drifted. The correct fix there was to untrack `registry.json`. For `relations.json` we're punting on the file's tracking status for now and instead discarding the 14 new edges by `git checkout`; a follow-up should decide whether to untrack the file entirely.

---

## 2026-04-20 — UI buttons labelled as provenance operations need to actually do them
**Context:** Mind tab's "Promote to Master" button existed for months (pre-session-27). It called `updateOperatorMindEntry(id, {promoted: true})` — a soft flag that set a boolean on the source entry and nothing else. No copy to `data/_master_mind/`. No provenance chain. No Layer 2 visibility. The button label said "Promote to Master" and the UI showed a ✓ "Promoted" badge afterwards, so analysts had zero signal that their "promotions" were going nowhere. Only surfaced because D1 introduced a sibling "Promote to Asset Class" button that DOES work correctly, and the obvious question followed: why is that one an inline form with category picker while this one just toggles a flag?
**Mistake:** Shipping two buttons that look like they do the same operation at different scopes, when one is a real provenance copy and the other is a soft flag. The UI was lying — badge labels implied work had happened when it hadn't.
**Rule:** Any UI affordance that claims a provenance/promotion/copy operation must actually perform it end-to-end. If the backing pipeline isn't ready, the button should be disabled with "(coming soon)" rather than ship as a placeholder that sets a "we pretended" flag. Apply this whenever the verb in a button label implies real state change — "Promote", "Publish", "Submit", "Approve" — and trace it to the endpoint to confirm the verb is truthful. If you find a case where it isn't, fix the endpoint or change the verb.

---

## 2026-04-20 — Flattening a context into a string loses structure future UIs need
**Context:** `build_mind_context()` was designed to return a dataclass of six string layers. Good enough for AI prompting (we just concat the strings). But D2 asked for "show the external citations that fed this answer" — and citations live in `AssetClassMind` entries' metadata, not in the flattened `asset_class` string layer. Had to extend `MindLayeredContext` with a new `asset_class_sources: List[Dict]` field so the UI can render citation rows without re-parsing the formatted text. Same pattern probably needed for Layer 4 (company mind provenance) and Layer 5 (thesis alerts as structured objects) eventually.
**Mistake:** Optimising only for the immediate consumer (AI prompts want text) and treating downstream consumers (analyst UI, citation rendering, audit tools) as out-of-scope. Every time an upstream structure gets collapsed into text, a downstream system that needs the structure has to either re-parse it (fragile) or add a new parallel field (the approach we took).
**Rule:** When a function assembles a context object for one consumer, leave structured fields alongside the string representation — don't collapse early. A `MindLayeredContext` with `asset_class: str` AND `asset_class_sources: List[Dict]` (and `.formatted` as a property) is strictly more useful than one that just has the string. Same applies to `MindContext` for each individual mind layer — keep `.entries` alongside `.formatted` so consumers that need structure have it.

---

## 2026-04-20 — Pragmatic scoping beats ideological purity when a helper-signature refactor blocks a small feature
**Context:** D2 broader asked for Layer 2.5 citation rendering in the Executive Summary. The `_build_{klaim,silq,aajil,tamara,ejari}_full_context()` helpers each return a single formatted string — they internally call `build_mind_context()` and bake its `.formatted` output into the prompt. Purist approach: change those 5 helpers to return tuples `(str, List[Dict])` or a dataclass, thread the sources through the dispatcher, and have one source-of-truth. Engineering cost: ~5 files changed, 5 call sites updated, commit diff obscures the real change. Pragmatic approach: call `build_mind_context()` a second time at the endpoint level purely to extract `asset_class_sources`, leave the helpers untouched. File reads are cheap; duplication is ~10 lines. Shipped the pragmatic version — 2 files instead of 7 — and the commit message is a clean narrative about a frontend-facing feature, not a plumbing refactor.
**Mistake would have been:** Doing the full refactor because "we should only build mind context once." That's an optimization for a call pattern that isn't hot (this endpoint runs once per analyst click, cached afterwards). The refactor would've been correct and slightly more efficient and 5× the blast radius.
**Rule:** When a helper's return type blocks a feature, weigh cost of adding a parallel call vs. cost of widening the helper. Prefer the parallel call when: (a) the helper is called in a request-scoped or cache-guarded path (not a hot loop), (b) the data it recomputes is cheap (files, not network), (c) widening the signature ripples to ≥3 callers. Prefer the refactor when: the helper is on a hot path, the data is expensive to recompute, or you're doing the refactor anyway for other reasons. Document the trade-off in the commit message so the next reader knows it was deliberate.

---

## 2026-04-20 — Stale endpoints die quietly when the only caller switches away
**Context:** Session 28 commit 00fccf3 rewired the Mind tab's "Promote to Master" button from the legacy soft-flag PATCH `/operator/mind/{id}` to the real `/api/mind/promote` pipeline. The backend PATCH endpoint still existed afterwards — it had the `MindUpdate` model, the `update_mind_entry` handler, and the `_promote_to_master` helper, all unused but still registered on the router. Session 28 follow-up round 2 cleaned them up. Impact of NOT cleaning up: zero functional (nobody called it) but non-zero architectural — a future engineer investigating how promotions work would find TWO promotion paths, one with shallow provenance, one with real, and would reasonably wonder which is canonical. Left-behind deprecated code rots into archaeology.
**Rule:** When you rewire a UI caller away from an endpoint, plan to delete the endpoint in the same branch or the very next one. Don't leave "dead but harmless" endpoints behind — they accumulate, confuse future investigators, and become load-bearing by mistake when someone googles the URL and assumes it's the canonical path. Check with `grep` that nothing else calls it (including tests, slash commands, and ops scripts), then remove the handler + the helper + the model + the CLIENT export in one atomic commit. Comment the removal site with a pointer to the replacement so diff-archaeologists find their way.

---

## 2026-04-20 — Backwards-compatible API changes cheaper than breaking ones, even for one caller
**Context:** `postChat()` in `services/api.js` used to return `r.data.answer` directly — a string. D2 needed the full response object so `DataChat.jsx` could also read `asset_class_sources`. Two options: (1) change the return type to object, update the one caller, (2) add a new `postChatWithSources()` helper leaving `postChat` alone. Picked (1) because greps showed exactly one caller, so "backwards compat" was free. But even with one caller, the change-vs-add decision is worth thinking about deliberately — a second caller tomorrow makes retroactive breakage painful.
**Rule:** Before changing a return type (or function signature, or response payload shape) on a public-ish function, grep every caller. If the count is zero or one AND the file is genuinely internal (not an npm-published SDK), change in place — duplicate helpers rot. If the count is more than one OR the boundary is external, add a new function with the richer shape and leave the old one. Applies to Python and JS equally; applies to HTTP API responses too (returning a new key is safe; renaming or restructuring is not).

---

## 2026-04-20 — Module-level constants computed from other constants at load time need both monkeypatched in tests
**Context:** Porting `verify_external_intelligence.py` to pytest (D3), my `isolated_project` fixture monkeypatched `core.mind.master_mind._PROJECT_ROOT` to a temp path. Expected all `MasterMind()` file writes to land in that temp dir. They didn't — `TestFrameworkCodification` tests saw the real `data/_master_mind/framework_evolution.jsonl` because `_MASTER_DIR = _PROJECT_ROOT / "data" / "_master_mind"` was computed at module-load time from the ORIGINAL `_PROJECT_ROOT`, not read from the patched one. Had to patch `_MASTER_DIR` directly as well. The `asset_class_mind.py` module avoided this by having the fixture patch both `_PROJECT_ROOT` AND `_BASE_DIR`, but `master_mind.py` only had `_PROJECT_ROOT` patched — an inconsistency that hid the bug.
**Mistake:** Assuming a single-variable monkeypatch propagates through module-level derived constants. Python evaluates module-level assignments once at import time; later mutations to a source variable don't retroactively update computed constants that reference it.
**Rule:** When writing a test fixture that redirects a module's I/O target, identify EVERY module-level variable that's a function of the root path, not just the root itself. `grep -n "^_[A-Z_]*\s*=" target_module.py` to surface them. Patch every one. Apply especially to any module that uses `_PROJECT_ROOT / "..." / "..."` patterns — those Path expressions freeze at import. Longer-term fix: defer the derivation to a function call (`_master_dir()` instead of `_MASTER_DIR = ...`) so tests only need to patch `_PROJECT_ROOT`. Not done here — too many callers reference `_MASTER_DIR` directly — but worth doing next time a new mind store ships.

---

## 2026-04-20 — When a slash command does its own housekeeping, verify the sub-commands actually advanced state
**Context:** Ran `/eod` at session end. Step 9 in the command says "merge to main and push" — NON-NEGOTIABLE. But in this session, every commit along the way already went directly to `main` (because the worktree was already checked out on `main`, and I was pushing after each round). Step 9's merge-from-feature-branch logic didn't apply and the git log already showed the commits on origin/main. Had to read what Step 9 actually does vs. what the current repo state was, and note "already on main, already pushed, this is a no-op" rather than mechanically running the commands (which would either fail harmlessly or do something redundant).
**Mistake would have been:** Running every step mechanically without checking whether the state it tried to establish was already true. `git checkout main` when already on main is fine; but "merge `<feature-branch>`" when there's no feature branch would fail, and the script doesn't expect to hit the no-op case.
**Rule:** Slash commands that do state-mutation steps (commit, merge, push) should be read as "ensure this state" not "run this command unconditionally." Before each mutation step: check current state against desired state. If already there, note it's a no-op and move on; don't re-run. Applies to `/eod`, `/init`, any future state-ensuring slash command. Corollary: when writing such commands, phrase steps as preconditions ("main is up to date with origin"), not commands ("run git pull"), so future runners can check-then-act rather than act-blindly.
