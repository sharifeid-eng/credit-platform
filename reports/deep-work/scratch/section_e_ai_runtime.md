# Section E: AI Commentary & Agent Runtime Risks

**Files analyzed:** 18 (core/ai_client.py, core/agents/runtime.py, core/agents/internal.py, core/agents/prompts.py, core/agents/tools/analytics.py, core/agents/tools/external.py, core/agents/definitions/{analyst,memo_writer}/config.json, core/memo/generator.py, core/memo/agent_research.py, core/memo/analytics_bridge.py, core/mind/__init__.py, core/mind/master_mind.py, core/mind/asset_class_mind.py, core/mind/thesis.py, core/mind/pattern_detector.py, backend/main.py — AI endpoints + helpers, backend/agents.py)

**Findings:** Critical 9 | Warning 17 | Improvement 8 (34 total)

**Date:** 2026-04-26

---

## Findings

### CRITICAL Finding 1: Tamara UAE memos pull KSA's mind context (cross-product memory leak)

- **File:** `backend/main.py:2784` (and parallel issues at `:2658`, `:2488`, `:2575`, `:2896`)
- **Trigger:** Generate AI Executive Summary for Tamara/UAE — `_build_tamara_full_context(data)` is called at line 2970 with no product info, then internally hardcodes `build_mind_context('Tamara', 'KSA', 'executive_summary')`. Same pattern for Aajil (always 'KSA'), Klaim (always 'UAE_healthcare'), SILQ (always 'KSA' — with config-derived fallback), Ejari (always 'RNPL').
- **Impact:** Tamara has TWO products (KSA + UAE) — they have separate Company Mind directories on disk. UAE Executive Summary will inject KSA's findings (different securitization facility, different default rates, different concentration, different covenants) as Layer 4 context. The AI then writes UAE summary citing KSA-specific institutional notes. An IC member reading the UAE memo gets KSA-flavored conclusions. Cross-product contamination is undetectable from the output since the AI doesn't say "this came from the KSA mind".
- **Fix:** All five `_build_*_full_context` functions must accept `company` and `product` params and pass them to `build_mind_context`. Remove all five hardcoded calls. Add a regression test that builds context for Tamara/UAE and asserts the mind context fetched targets `data/Tamara/UAE/mind/` not `data/Tamara/KSA/mind/`.
- **Before/after:**
  ```python
  # Before (line 2784):
  mind_ctx = build_mind_context('Tamara', 'KSA', 'executive_summary')

  # After:
  def _build_tamara_full_context(data, company='Tamara', product='KSA'):
      ...
      mind_ctx = build_mind_context(company, product, 'executive_summary')
  ```

---

### CRITICAL Finding 2: Sync Executive Summary fallback parser misses analytics_coverage normalization

- **File:** `backend/main.py:3121-3133`
- **Trigger:** Sync `/ai-executive-summary` endpoint (NOT the streaming one) — non-agent path. AI returns malformed JSON. The sync path parses inline (`json.loads`) and on failure falls back to a single warning finding, but does NOT use `_parse_agent_exec_summary_response()` — which would normalize `analytics_coverage`. Result: sync responses NEVER carry `analytics_coverage`, while streaming/agent responses do.
- **Impact:** Frontend renders inconsistently — backdated/cached sync responses don't show the muted amber "Analytics Coverage" callout (session-33 contract), so analysts see different rendering for the same company depending on which code path served the request. Worse, if the streaming endpoint returns a parsed legacy-list response, `_parse_agent_exec_summary_response` returns `(None, parsed, None, True)` — but the sync endpoint doesn't surface that case at all. Stale caches written by the sync endpoint never expose `analytics_coverage`.
- **Fix:** Replace lines 3121-3133 with `narrative, findings, analytics_coverage, _parsed_ok = _parse_agent_exec_summary_response(response_text)` and add `analytics_coverage` to the returned `result` dict. Now both sync + stream endpoints share the contract.

---

### CRITICAL Finding 3: AI cache key omits snapshot_id for live-* DB snapshots — same-day mutations serve stale AI

- **File:** `backend/main.py:397-426`
- **Trigger:** Integration API mutates a `live-YYYY-MM-DD` snapshot mid-day (analyst pushes new invoices via Integration API). `_ai_cache_key()` keys on (endpoint, company, product, snapshot_filename, currency, file mtime). For DB-backed snapshots, `snap_file['filepath']` doesn't exist as an on-disk file — `os.path.exists(snap_file['filepath'])` returns False on line 413, no mtime added, key collapses to (endpoint, company, product, snap_name='live-2026-04-26', currency).
- **Impact:** Per Session 31, Integration API UPSERTs into `live-YYYY-MM-DD` until UTC midnight. AI summary generated at 09:00 caches under key `live-2026-04-26`. New invoices pushed at 14:00. AI summary re-fetched at 15:00 — cache hit, returns 09:00 stale data. Until next day's `live-2026-04-27` snapshot is created, the cache never invalidates. AI says "PAR30 stable at 4.2%" while actual is now 7.8%.
- **Fix:** Inject `snapshot.taken_at` AND `snapshot.ingested_at` into the cache key when `snapshot.source == 'live'`. Or add a `?last_modified=...` synthetic query param that changes whenever the snapshot's row count changes. Simplest: use snapshot.id (UUID) for non-tape snapshots, plus their `ingested_at` timestamp.

---

### CRITICAL Finding 4: build_mind_context resolution silently degrades to legacy fallback when both keys missing

- **File:** `core/mind/__init__.py:200-208`
- **Trigger:** A new company with a config.json missing both `asset_class` AND `analysis_type` (typo, partial migration, or unconfigured product) — e.g. an integration test config or experimental product. `resolved_at = cfg.get("asset_class") or cfg.get("analysis_type")` returns `None`, the `if resolved_at:` block at line 208 silently skips Layer 2.5 — no error logged.
- **Impact:** Layer 2.5 is silently empty. Memo / Exec Summary / Chat have no asset-class benchmarks. The "Informed by N asset-class sources" footer disappears with no indication why. Worse, since Layer 2.5 was only fully wired in session 27, a partially-onboarded company can produce AI output that LOOKS confident but missed an entire knowledge layer. No alerting.
- **Fix:** Log a WARNING when `resolved_at` is None but `cfg` was loaded successfully. Add a startup-time validator (or `/api/operator/health` check) that scans every `data/*/*/config.json` and flags missing `asset_class`. Same logic in any code path that calls `build_mind_context` with `analysis_type=None`.

---

### CRITICAL Finding 5: Citation audit returns "no issues" on JSON parse failure (rubber-stamps AI)

- **File:** `core/memo/generator.py:826-831`
- **Trigger:** Stage 5.5 citation audit prompt asks Sonnet for `{"issues": [...]}`. If Sonnet response is invalid JSON (truncation, prose preamble, or model outage causing partial response), `json.loads(text)` raises `JSONDecodeError`. The code catches it, logs a warning, and returns `[]`.
- **Impact:** A failed citation audit is INDISTINGUISHABLE from a successful audit that found nothing. The memo proceeds to polish with `_citation_issues=[]`, fabricated citations stay in output, IC members read citations to documents that don't exist in the data room. Session-33 doctrine "BE CONSERVATIVE — only flag clear mismatches" + this silent failure = bias toward not flagging fabrications. Combined with the fact that prompt also says "If NO citations are problematic, return: {"issues": []}" — there's no way to distinguish "0 issues found" from "audit failed".
- **Fix:** Distinguish parse failure from empty result. Return a synthetic `{"section_key": "_audit_failed", "severity": "high", "reason": "citation audit failed to parse"}` issue on JSON failure. Polish prompt then sees that the audit didn't run and can warn the analyst in Methodology footer: "Citation audit failed for [section]; verify references manually."

---

### CRITICAL Finding 6: 5-layer mind context Layer 2.5 sources never included in Klaim sync exec summary

- **File:** `backend/main.py:3142-3147` vs `backend/main.py:2484-2495`
- **Trigger:** Sync exec summary calls `_build_klaim_full_context(...)` which internally calls `build_mind_context(...)` and APPENDS `mind_ctx.formatted` to `sections`. After that, line 3142 calls `build_mind_context(...)` AGAIN to extract `asset_class_sources` for the response payload.
- **Impact:** Two issues:
  (a) Two calls to `build_mind_context` — wasteful (each call does I/O + scoring).
  (b) The formatted text from the FIRST call (used in the prompt) and the sources list from the SECOND call may DISAGREE if entries change between the two calls (race condition with web_search approval mid-request).
  More importantly, a CORRECTION race: web_search agent finishes and writes a pending entry → analyst approves → second `build_mind_context` call sees the new entry → frontend receives sources that point to research the AI in fact NEVER saw. The "Informed by" claim is then false.
- **Fix:** Have `build_mind_context` return `MindLayeredContext` once, formatted into prompt + sources to response in a single call. Eliminates double I/O AND race condition.

---

### CRITICAL Finding 7: Pattern detector race — concurrent ingests + ack file_count duplicate

- **File:** `core/mind/pattern_detector.py:430-501` (`write_patterns_to_company_mind`)
- **Trigger:** Two `dataroom_ctl ingest --company X` runs fire concurrently (e.g. analyst + post-ingest hook + scheduled cron). Both call `auto_fire_after_ingest(X)`. Both call `detect_recurring_patterns(X)` which reads registry.json. The pattern detection produces (file_count=5, status=CANDIDATE) for both runs. Both call `write_patterns_to_company_mind(X, patterns)`. Both check `latest_by_pattern[pattern_id]` — neither has seen the other's append yet. Both pass the idempotency check (`same` is False because no prior entry). Both write a new mind entry. Result: TWO duplicate entries with identical pattern_id AND file_count.
- **Impact:** mind/recurring_channels.jsonl now has duplicate entries that violate the "idempotency on pattern_id" contract. The Operator Channels tab counts `5` patterns when actual is `4`. `write_fund_wide_stats` also runs concurrently, both write `_master_mind/recurring_channel_stats.json`, last writer wins — worse, partial-write corruption possible since `json.dump` isn't atomic.
- **Fix:** Use `os.replace` for atomic JSON writes. For mind appends, accept that duplicates are possible but add a deduplication pass on read in CompanyMind that filters by `(pattern_id, file_count, automation_status)`. Alternatively, file lock around the entire detection + write sequence per company.

---

### CRITICAL Finding 8: Thesis drift checker can mark pillar "broken" when actual=0 (silent metric absence)

- **File:** `core/mind/thesis.py:283-294`
- **Trigger:** A thesis pillar `metric_key='collection_rate', threshold=0.85, direction='above'`. Tape ingestion fires TAPE_INGESTED event. The listener calls `tracker.check_drift({"collection_rate": 0.0})` because the underlying compute function returned 0 for an edge case (empty active book, divide-by-zero handled by returning 0). At line 285: `breached = actual < pillar.threshold` → `0 < 0.85` → True → pillar breaks, conviction drops 30 points, drift alert fires.
- **Impact:** Edge cases where compute_summary returns `collection_rate=0` (e.g., a snapshot with no completed deals yet) would erroneously break a healthy thesis pillar. Drift alerts spam OperatorCenter. Conviction tanks artificially. The Tamara session-37 acceptance criteria explicitly relies on conviction monotonically rising with quarterly packs — a single bad metric would crater conviction. Worse: there's no dampening — once broken, conviction goes from 100 → 70 in one event.
- **Fix:** Add sentinel handling: if `actual is None` OR `actual == 0` AND threshold > 0 AND there's no other evidence the metric is genuinely 0, skip the pillar's drift check this round and log "metric not yet observable". Or, check `latest_metrics.get(pillar.metric_key, _SENTINEL)` and `if actual is _SENTINEL: continue`. The current check `if actual is None: continue` doesn't catch `0.0`.

---

### CRITICAL Finding 9: Memo Stage 6 polish "metrics preserved verbatim" only true for content; metrics array can be silently dropped

- **File:** `core/memo/generator.py:1106-1117`
- **Trigger:** Stage 6 polish updates `section["content"]` from `polished_by_key.get(...)` but never validates that the polished content STILL CONTAINS the metric values from `section["metrics"]`. Opus 4.7 prompted with "PRESERVE: All specific numbers" can still subtly change a number while keeping the prose flow ("rate of 87.3%" → "rate of approximately 87%").
- **Impact:** §17 disclosure tags `[Confidence A, pop=clean_book]` may be in metrics array but stripped from polished prose. Worse, polish receives the FULL memo body (line 1015-1027) — Opus 4.7 sees Section A's number (87.3%) when polishing Section B and might "harmonize" Section B's number to match. Documented contradiction-resolution behaviour — but for non-contradicting numbers, this is silent rewriting. No invariant check post-polish.
- **Fix:** Post-polish validation: walk the metrics array, assert each `value` substring appears in `polished_content` (regex-match for numbers with formatting tolerance: `87.3%` ≈ `87.3 percent` ≈ `~87%`). On failure, revert that section to pre-polish content + flag in `generation_meta["polish"]["preservation_failures"]`.

---

### WARNING Finding 10: External web_search response can have empty synthesis but citations preserved — pending entry has fake content

- **File:** `core/agents/tools/external.py:137-154`
- **Trigger:** Anthropic web_search returns a `web_search_tool_result` with citations but NO `text` block (e.g., model context exhausted, model declined to synthesize). Synthesis text = `""`. Code at line 137: `if not citations and not synthesis: return "Web search returned no usable results."` — but with citations and empty synthesis, code proceeds. Line 151: `content=synthesis or "(no synthesis text)"`.
- **Impact:** Pending review queue gets entry with content "(no synthesis text)" plus citations. Analyst sees citations but no summary. If approved, Asset Class Mind gets entry with placeholder content. Future memos retrieve this as "knowledge" but it has no actual claim text.
- **Fix:** When synthesis is empty but citations exist, build a synthetic content from titles: `"; ".join(c['title'] for c in citations[:5])`. Or refuse to write the entry and return "Search returned citations but no synthesis — try refining the query".

---

### WARNING Finding 11: Tool timeout circuit breaker counts graceful skips when handler exception escapes

- **File:** `core/agents/runtime.py:240-243` and `:470`
- **Trigger:** A tool handler raises an unexpected `RuntimeError` (e.g. from `compute_silq_summary` if a column type changes upstream). Line 240 catches `Exception`, returns `f"Tool error ({tool_name}): {type(e).__name__}: {e}"`. Line 470 detects `result.startswith("Tool error")` → counts toward the 3-consecutive-errors circuit breaker.
- **Impact:** A single recurring runtime error (e.g., a pandas FutureWarning escalated to an error in newer pandas) would trip the circuit breaker after 3 calls — agent terminates with "3 consecutive tool errors". The agent's only signal is to stop and emit "stopping to avoid loop" — no diagnostic about WHICH tool failed three times. Whoever waits for the agent reads the partial output as a complete summary. Worse, the "Tool error" prefix is mandated by session-33 lesson to NOT start with `Error:` — but the runtime CREATES errors that DO start with `Error:` for unknown tools (`return f"Error: Unknown tool '{tool_name}'"` at line 204) and session-limit (line 193).
- **Fix:** Differentiate "graceful skip" (handler returned a string starting with "X not available for…") from "handler raised". Only handler-raised errors should count toward circuit breaker. Make the prefix detection more sophisticated: `is_error = bool(re.match(r"^(Tool error \(|Error: (Unknown tool|Session tool call))", result))` — explicit allowlist of error patterns rather than open-ended `startswith`.

---

### WARNING Finding 12: Asset class key resolution falls back to analysis_type even when invalid

- **File:** `core/mind/__init__.py:204-205`
- **Trigger:** A company's config has `analysis_type: "klaim"` but no `asset_class` field (legacy config). `resolved_at = cfg.get("asset_class") or cfg.get("analysis_type")` → `"klaim"`. AssetClassMind looks for `data/_asset_class_mind/klaim.jsonl`. That file doesn't exist (it's `healthcare_receivables.jsonl`). `_load_all` returns `[]`. Layer 2.5 is empty — no asset-class benchmarks injected.
- **Impact:** This is the EXACT session-28 Finding #3 latent regression. The fallback is masked because: (a) the file is just missing, no error; (b) `entries=[]` produces empty `MindContext`; (c) build_mind_context proceeds. The AI output looks normal. There's no "I couldn't find your asset class" warning. Session-28 fix added `asset_class` to all configs but a future onboarding that copies an old config will silently regress.
- **Fix:** Either (a) drop the legacy fallback — require `asset_class`, error loudly if absent (preferred); or (b) maintain a whitelist of valid asset_class keys and warn if `resolved_at` doesn't match. Add a startup-time integrity check that walks `data/_asset_class_mind/` and asserts every config's `asset_class` resolves to an existing JSONL.

---

### WARNING Finding 13: SSE thread offload still missing in backend/agents.py:_stream_agent — risks reintroducing 2026-04-22 freeze

- **File:** `backend/agents.py:135-145`
- **Trigger:** `_stream_agent` runs `agent.stream(message, session)` inline via `asyncio.create_task` (`producer_task = asyncio.create_task(_producer())`) — NOT in a dedicated thread. The agent's `runner.stream` is async-declared but uses the SYNC Anthropic client internally. When Claude takes 60-90s on a tool call, the asyncio event loop blocks for that duration.
- **Impact:** Per CLAUDE.md note dated 2026-04-22: "this works in the short-call common case but has the same latent bug". For memo `regenerate-section`, compliance check, and onboarding endpoints — all use `_stream_agent` — the same freeze that bricked Aajil exec summary CAN occur. As Aajil's tool coverage expands or memo_writer's research packs lengthen, this will manifest. Heartbeats DO fire (line 159-162) because the consumer loop wakes every 500ms. But then the producer task isn't actually progressing — the agent is blocked in `client.messages.stream` (sync) with no thread to make progress.
  - Wait — re-reading: `_producer` is spawned via `asyncio.create_task` (line 145). Inside, it does `async for event in agent.stream(...)` — an ASYNC generator. The agent's stream is async-declared. So the asyncio event loop SHOULD await it cooperatively. But — `agent.stream` calls `self._get_client().messages.stream(...)` — the SDK's blocking call, not async. The `with` statement at line 380 of runtime.py blocks the OS thread. Since the task runs on the main thread, the main thread blocks too.
- **Fix:** Refactor `_stream_agent` to mirror `get_executive_summary_stream` — spawn a dedicated `threading.Thread` with its own asyncio loop. This is what session-32 codified as binding for any agent SSE endpoint. Memo regen, compliance check, onboarding stream endpoints all need the fix.

---

### WARNING Finding 14: Layer 1 framework context loaded from FRAMEWORK_INDEX.md may silently drop §17 if file moved/missing

- **File:** `core/mind/master_mind.py:577-619`
- **Trigger:** `FRAMEWORK_INDEX.md` is moved, deleted, or its "## Core Principles" header is renamed (e.g., to "## Core Doctrine"). Line 578 returns the §17 fallback. But if Section name changes mid-file (current matches `## Core Principles`, future change to `## Foundational Principles`) — line 590's `if "## Core Principles" in line:` won't match. Then `result_lines = ["## ACP Analysis Framework — Core Principles"]` (single header line), len==1, takes the fallback at line 601. The fallback is ALSO appended with §17 (line 619). So it works.
  - However: if the file EXISTS and has the header but is CORRUPTED (e.g., empty section with no body), the loop succeeds with `len > 1` and returns just the header + §17. AI gets minimal Layer 1.
- **Impact:** Subtle: framework context degraded but no error. AI produces lower-quality output (no Population Discipline reminders specific to current company onboards). Worse, no telemetry — `total_entries` doesn't include Layer 1.
- **Fix:** Add a sentinel check: after assembly, if `len(result_lines) <= 2`, log a warning. Add `_FRAMEWORK_LOAD_HEALTH` boolean exposed via `/api/operator/status` so the analyst sees framework load failures alongside dataroom audits.

---

### WARNING Finding 15: Memo polish and citation audit JSON parsing tolerates ```json fences but Stage 2 sections do not

- **File:** `core/memo/generator.py:160-180` (`_parse_ai_response`)
- **Trigger:** Stage 2 (structured sections) prompt says "Return ONLY valid JSON, no markdown fences" but Sonnet 4.6 occasionally adds them. `_parse_ai_response` strips ```json correctly. But Stage 5 judgment sections also use `_parse_ai_response`. If Opus 4.7 returns nested fences (a fenced block within a fenced block, or an unfenced JSON containing literal "```" inside a string), the `endswith` check at line 167 strips the trailing ``` and corrupts the JSON.
- **Impact:** Polished section saved as plain text with JSON fragment in it. Frontend renders raw `{"content":` prefix in IC memo. Per session-33 lesson "fallback severity must render as failure" — but this falls back to `{"content": text.strip(), "metrics": [], "citations": []}` (line 180) → polished_by_key gets the full text with fences → polish thinks it succeeded. 
- **Fix:** Use the more robust `_parse_agent_exec_summary_response` style (find outermost balanced `{...}`, fall back to text). Apply consistently across all four AI parsers (Stage 2, Stage 5 judgment, Stage 5.5 citation, Stage 6 polish).

---

### WARNING Finding 16: pending_review queue has no concurrency guard — concurrent web_search calls can corrupt JSONL

- **File:** `core/external/pending_review.py` (referenced from external.py:144-153)
- **Trigger:** Two analyst sessions both running an agent that calls `external.web_search` in parallel. Both reach `queue.add(...)`. JSONL append is technically atomic on POSIX (single `write()` of <PIPE_BUF=4096 bytes), but on Windows (the dev env per CLAUDE.md "Platform: win32") `open('a').write` is NOT guaranteed atomic. Two appends could interleave and produce a corrupt JSONL line.
- **Impact:** PendingReviewQueue.list() crashes parsing the corrupted line, OR worse, silently skips the line — losing an analyst-pending entry. Session 27 "trust boundary" (Asset Class Mind only via approved entries) is breakable: a corrupt line means the approval flow can't act on it, but the AI still saw the fresh asset_class data.
- **Fix:** File lock (filelock package, or `msvcrt.locking` on Windows) around all writes to `data/_pending_review/queue.jsonl`. Also add a recovery pass at read time that skips malformed lines + emits a warning.

---

### WARNING Finding 17: Memo SSE queue uses unbounded asyncio.Queue — slow consumer leaks memory

- **File:** `backend/agents.py:269-283` (memo_generate_stream)
- **Trigger:** Pipeline emits dozens of progress events (section_start, section_done, research_start, research_done, polish_start, polish_done) per memo. Total events ~50-80. Browser disconnected/buffered network. `progress_cb` keeps calling `loop.call_soon_threadsafe(queue.put_nowait, ...)`. Queue is unbounded.
- **Impact:** For a single broken connection, ~80 events of ~200 bytes each = ~16KB. Negligible. BUT — the `_generate_parallel` Stage 2 ThreadPoolExecutor + Stage 6 polish ThreadPoolExecutor can submit progress events in tight bursts. If the consumer is slow (heartbeat is 500ms granularity), backpressure builds. Worst case for huge memos, memory spike.
- **Fix:** Use `asyncio.Queue(maxsize=1000)` to bound the queue. On overflow, drop the oldest event (warn). For a memo, dropping a `section_start` event isn't catastrophic — but dropping `saved` IS. Mark `saved` and `error` events as "must-deliver" by waiting indefinitely.

---

### WARNING Finding 18: build_mind_context fall-through omits Layer 2.5 when ANY exception fires

- **File:** `core/mind/__init__.py:208-259`
- **Trigger:** Exception inside the asset_class block (e.g., disk I/O error reading the JSONL, JSON parse error on a single corrupt line, `_load_all` swallowed but `get_context_for_prompt` raised). `except Exception as e:` at line 256 catches everything, sets `asset_class_formatted = ""` and `asset_class_sources = []`. NO log of the underlying entries.
- **Impact:** AI output looks normal. The `asset_class_sources` field in the response is empty, frontend doesn't render the "Informed by N sources" footer. Analyst doesn't see ANY signal that Layer 2.5 was attempted but failed. Worse, the same exception in Layer 4 (Company Mind) silently kills institutional knowledge for that company. Session-23's Klaim seed (18 entries) — if any one entry's JSON gets corrupted, the entire layer disappears.
- **Fix:** Per-entry error handling, not per-layer. Log every exception with the company/product/asset_class identifier. Bubble up a `degraded_layers: List[str]` field on `MindLayeredContext` so callers can see if data was missing. Render in operator: "Mind context degraded for SILQ/KSA: Layer 2.5 (asset_class)".

---

### WARNING Finding 19: max_tokens=2000 default creates silent truncation risk for memo_writer agent

- **File:** `core/agents/definitions/memo_writer/config.json:11`
- **Trigger:** `memo_writer` config sets `"max_tokens_per_response": 3000`. But research pack JSON output can include up to 10 key_metrics + 10 quotes + 5 contradictions + 8 supporting_evidence + verbose contradictions descriptions. Per `_normalize_pack` truncation (lines 161-170), the LIMITS allow up to 33 items. Each item ~150-300 chars JSON-encoded. 33 × 250 = ~8K chars ≈ ~2K tokens. Tight margin.
- **Impact:** A research pack with many citations + contradictions + agent reasoning prose ABOVE the JSON gets truncated. `_parse_pack` strategy 2/3 may still extract the JSON if the truncation happened in agent commentary. But if truncated INSIDE the JSON (in a quote text or contradiction description), Strategy 1 fails, Strategy 2 catches the partial fence, Strategy 3 finds malformed JSON, returns EMPTY_PACK. The judgment section then runs Opus 4.7 with no research. Memo quality degrades silently.
- **Fix:** Bump memo_writer `max_tokens_per_response` to 6000 specifically for research pack calls. Or add a length-check after `_parse_pack`: if the parsed pack has FEWER items than the JSON suggests (truncation indicator), retry with higher token budget.

---

### WARNING Finding 20: Pattern detector cadence label "irregular" misclassifies single-batch ingests as low-priority

- **File:** `core/mind/pattern_detector.py:128-141`
- **Trigger:** Per docstring at line 36-40: "when an entire dataroom is ingested in one batch (e.g. fresh-install re-ingest), `ingested_at` clusters tightly and cadence_label will be 'irregular'". But the file_count threshold drives actionability. Suppose Tamara's investor pack folder has 4 packs ingested 3 days apart (regular fortnightly cycle) — average cadence is 4 days. Falls outside all buckets (monthly 25-35, quarterly 80-100, annual 350-380). Labelled "irregular" → analyst doesn't recognize this is a real recurring channel.
- **Impact:** A 4-day cadence (analyst diligence pace) is genuinely a "recurring" channel but gets the same treatment as random uploads. Session-37 added `auto_fire_after_ingest` post-tamara investor pack — this works because file_count>=3, but the cadence label doesn't help the operator triage.
- **Fix:** Add a "weekly" bucket (5-9 days) and a "biweekly" bucket (12-16 days). Or replace cadence buckets with a continuous score: `actionability = file_count × consistency` where consistency = 1/coefficient_of_variation(deltas).

---

### WARNING Finding 21: Memo polish per-section calls each ship full body — token economics + cache eviction risk

- **File:** `core/memo/generator.py:1012-1027`
- **Trigger:** Each section's polish call is built with `full_body` (the entire memo concatenated). For 12-section memos, full_body is ~30-40KB. 12 parallel calls × 40KB body × ~20 tokens per 100 chars = ~240K input tokens just for body context. Plus system prompt + section prompt + contradictions block.
- **Impact:** Per CLAUDE.md "intentional reliability over token economy" — acknowledged. But: prompt caching with `cache_control` on the system prompt would help — the central client wraps the system prompt with cache_control automatically (`system_with_cache`). HOWEVER, the body changes per polish call, so cache HITS are limited. If multiple sections share `_PARALLEL_CAP=3` workers concurrently, they hit Anthropic with 3 prompts where only the section identity differs. Cache prefix only matters up to first 1024-token boundary; differing user content cuts cache. Cost estimate at $3.50-6.00 may understate due to repeated full-body token billing.
- **Fix:** Mark the system prompt + shared `contra_block_shared` + `full_body` as cache-eligible (one cache breakpoint). Per-section content goes after the cache boundary. This needs `cache_control` placed correctly, which `complete()` only does for system prompt. Add a way to mark user content prefix as cache-able too.

---

### WARNING Finding 22: ConfidenceBadge population/method values from analytics_bridge can be None — unrendered

- **File:** `core/memo/analytics_bridge.py:140-153` (`_attach_disclosure`)
- **Trigger:** A compute function that doesn't yet emit §17 disclosure (e.g., a future extension or one in progress) returns a dict with no `confidence`/`population` fields. `_get_disclosure` returns `(None, None, None)`. `_attach_disclosure` is a no-op.
- **Impact:** Acceptable today (graceful degradation). But the `format_as_memo_block` at line 1024 only ADDS disclosure tags when fields are present. AI sees the metric WITHOUT disclosure → AI assumes Confidence A (per §17 Layer 1 doctrine "Grade A metrics: don't pollute prose with brackets"). A B-grade metric without explicit field is treated as A — silent confidence inflation.
- **Fix:** Force every compute function to declare confidence/population as non-optional. Add a CI test in `test_population_discipline_meta_audit.py` that fails if any metric the bridge consumes lacks both fields.

---

### WARNING Finding 23: Tool memoization key sorts by `default=str` — dict ordering in input_json may vary

- **File:** `core/agents/runtime.py:196`
- **Trigger:** `memo_key = f"{tool_name}:{json.dumps(tool_input, sort_keys=True, default=str)}"`. `sort_keys=True` handles top-level. But `default=str` for non-JSON-serializable values (datetime, Decimal, pandas Timestamp from a corrupt input) renders to string. Two calls with identical semantic input but different stringification of edge values produce different keys.
- **Impact:** Cache misses where hits should occur — wasted Claude calls. Conversely, two semantically DIFFERENT inputs that happen to stringify identically (e.g., `{"a": 1.0}` and `{"a": "1.0"}`) collide → wrong cached result returned.
- **Fix:** Reject non-serializable values explicitly with a clear error rather than `default=str`. Tool inputs should always be JSON-native types (strings, numbers, booleans).

---

### WARNING Finding 24: Memo SSE event_stream doesn't guarantee `done` fires after `error` — finally block races

- **File:** `backend/agents.py:340-371`
- **Trigger:** `progress_cb("error", ...)` fires (line 305). The next iteration of the consumer sees `event_type=='error'`, sets `done=True`, breaks the while loop. Falls into the bottom block where `future.result(timeout=5)` runs. `_run_pipeline` returned the memo despite the error. `done` event fires with `memo_id`. But the inner block at line 369-371 is wrapped in try/except — if `future.result` raises (e.g., generator save failed AFTER the error was already sent), the `except` block emits ANOTHER `error` event but never a `done`.
- **Impact:** Frontend's `onError` fires twice or `onDone` never fires. The frontend session-33 fix locally tracks `errorSet` but only the streaming exec summary frontend uses that pattern. Memo SSE client may hang waiting for `done`.
- **Fix:** Always emit a terminal `done` event in `finally`. If errored, set `done.ok=False` + `error` field.

---

### WARNING Finding 25: Pattern detector fund-wide stats overwrites file non-atomically — partial-write corruption risk

- **File:** `core/mind/pattern_detector.py:564-567`
- **Trigger:** `auto_fire_after_ingest` runs concurrently from multiple processes (cron + manual + CI). All call `write_fund_wide_stats`. The file write at line 566-567 is `open('w')` followed by `json.dump`. Crash mid-write (process killed, disk full) → file truncated, JSON corrupt.
- **Impact:** OperatorCenter Channels tab fails to render fund-wide summary. Master Mind seed for asset_class onboarding fails. Cascade: a corrupt stats file blocks subsequent `auto_fire_after_ingest` runs because the read at startup may fail.
- **Fix:** Atomic write — write to `<path>.tmp` then `os.replace(<path>.tmp, <path>)`. Standard pattern for any single-file mutable JSON.

---

### WARNING Finding 26: Sync exec summary inner JSON parse uses `re.sub` and bare `json.loads` — duplicates vs `_parse_agent_exec_summary_response`

- **File:** `backend/main.py:3115-3133`
- **Trigger:** Sync exec summary endpoint inlines its own JSON parser. Code at line 3117-3119 strips ```json fences via `re.sub` (incomplete — doesn't handle nested fences or edge cases the outer-substring heuristic catches). Line 3122 `json.loads(response_text)`. Falls back to a single warning finding.
- **Impact:** Two divergent parsers across sync vs streaming. Streaming uses `_parse_agent_exec_summary_response` (3-strategy: strip fences → outer braces → fallback). Sync uses the simpler 1-strategy. AI returns same response — sync parses it differently than stream. Cache key is the same. Result: cache hit/miss serves different content. Session-33 doctrine "FALLBACK MUST RENDER AS FAILURE" — sync's fallback at line 3132 says `severity: 'warning'` (correct). But the streaming uses `severity: 'warning'` too (correct). What differs: streaming returns `analytics_coverage`, sync doesn't.
- **Fix:** Eliminate the inline parser at 3115-3133. Replace with `_parse_agent_exec_summary_response(response_text)` call. Single source of truth.

---

### IMPROVEMENT Finding 27: SSE heartbeat strings include backslash-n that's ambiguous in some logging contexts

- **File:** `backend/main.py:3326`, `backend/agents.py:161`
- **Trigger:** Heartbeat literal `": keepalive\n\n"`. The `\n` is interpreted as newline by Python (correct SSE format). But when this output is captured into application logs that escape control chars, the log shows `: keepalive\n\n` literally — operator can't tell if heartbeats are firing or if the literal escape is being sent over the wire.
- **Impact:** Diagnostic only. Operator sees "no heartbeats" when troubleshooting CF Free idle drops, but they're firing.
- **Fix:** Add an INFO log line each time a heartbeat fires, with the SSE byte count.

---

### IMPROVEMENT Finding 28: get_model() caches resolved tier across forks — workers see stale fallback

- **File:** `core/ai_client.py:55-95`
- **Trigger:** `_RESOLVED_MODELS` is a module-level dict. Anthropic deprecates Opus 4.6 mid-run. The first call sees 4.6 unavailable → `_mark_unavailable` advances to 4.20250514, caches. Subsequent calls in the same process use 4.20250514. Restart needed to retry 4.6.
- **Impact:** No live recovery if Anthropic restores 4.6. Current behavior is acceptable (process restart anyway). But for long-running services without restart, fallback chain pin is irreversible.
- **Fix:** Optional retry timer — every 1hr clear `_RESOLVED_MODELS` and let primary be retried.

---

### IMPROVEMENT Finding 29: Tool description "CALL BUDGET: make ONE comprehensive call" relies on model compliance

- **File:** `core/agents/tools/external.py:185-193`
- **Trigger:** Per session-28 Finding #2 the agent splits one user request into 3 parallel web_search calls — fixed by adding "CALL BUDGET" clause to description. But model compliance with description constraints is non-binding — Sonnet under pressure can still split.
- **Impact:** Each split = 3× cost + 3 pending entries to review. Cost overrun if abused.
- **Fix:** Add per-session enforcement: count `external.web_search` calls in `AgentRunner._session_tool_calls`. Reject the 2nd+ call within the same session unless previous returned no usable results.

---

### IMPROVEMENT Finding 30: Layer 1 §17 guidance is static — doesn't update if framework doc evolves

- **File:** `core/mind/master_mind.py:32-54`
- **Trigger:** §17 guidance is a Python string constant in `master_mind.py`. ANALYSIS_FRAMEWORK.md §17 evolves (per session-36 doctrine revision: "Pattern 1 single-primary lending-style; Pattern 2 parallel-equal factoring-style; Pattern 3 N-way yield-style"). The Python constant must be manually kept in sync.
- **Impact:** Future framework revisions (§17 codification of new patterns) require touching both .md AND .py. Drift-prone.
- **Fix:** Lazy-load §17 from `core/ANALYSIS_FRAMEWORK.md` itself, similar to the FRAMEWORK_INDEX.md Core Principles loader. Cache on first read.

---

### IMPROVEMENT Finding 31: AI cache mtime check fails for non-existent files but cache key still partially valid

- **File:** `backend/main.py:412-417`
- **Trigger:** When `snap_file['filepath']` is a DB-only filename (no on-disk file), `os.path.exists` returns False, mtime not added to key. Same key serves both pre-DB-snapshot and post-DB-snapshot AI summaries.
- **Impact:** Already covered in Finding #3 but worth noting as a defense-in-depth: file mtime IS the correct invalidation signal for tape files but DB snapshots need a different invalidator.
- **Fix:** When snap is DB-backed (`source in ('live', 'manual')`), use `snap.ingested_at` as the mtime equivalent.

---

### IMPROVEMENT Finding 32: Session 32 thread offload pattern not documented in CLAUDE.md as a sample

- **File:** `backend/main.py:3244-3303`
- **Trigger:** Session-32 lesson is "binding for all SSE agent endpoints" but the pattern is implemented inline in main.py — not refactored into a reusable helper. Future endpoints will copy-paste, drift.
- **Impact:** `backend/agents.py:_stream_agent` (Finding #13) is the regression — wasn't refactored to follow the pattern.
- **Fix:** Extract the thread-offload pattern into `core/agents/sse_helpers.py::run_agent_in_thread()`. Have all SSE endpoints call it. Add a CI test that imports `_stream_agent` and asserts it uses the helper.

---

### IMPROVEMENT Finding 33: Polish prompt explicitly states "DO NOT remove caveats" but no validation enforces it

- **File:** `core/memo/generator.py:961-967`
- **Trigger:** Polish system prompt at line 963 says "DO NOT remove caveats or data gap acknowledgements". Opus 4.7 can still drop a "[Data gap: provider not in tape]" parenthetical when polishing for "tone consistency".
- **Impact:** Caveats matter — they're how the analyst signals data limits to IC. Silent removal misleads. Per finding #9 the metrics array preservation isn't validated either.
- **Fix:** Pre-polish, extract sentinel substrings (anything in square brackets matching `[Data gap...]`, `[Confidence X...]`, `[pop=...]`). Post-polish, assert every sentinel still appears. On miss, revert + flag.

---

### IMPROVEMENT Finding 34: Briefing.py's morning briefing has no staleness signal — all-companies-silent looks identical to all-companies-fine

- **File:** `core/mind/briefing.py` (referenced from CLAUDE.md, not loaded)
- **Trigger:** Per CLAUDE.md "morning briefing — does it surface stale data?". If every company's last_ingest is >7 days old, briefing shows "no priority actions" — same output as a healthy week.
- **Impact:** Operator misses extended silence. Tape ingestion failures become invisible.
- **Fix:** Add per-company "last activity" timestamps. If max(last_activity across all companies) > 5 days, surface a "Platform-wide silence" alert at top of briefing.

---

## Themes / patterns observed

1. **Hardcoded company/product in mind context calls** (Finding #1) — Five `_build_*_full_context` functions all hardcode their target company/product. This pattern is identical across files, suggesting copy-paste origin. The Tamara case is the worst (cross-product KSA/UAE leak) but Aajil could grow products too.

2. **Sync vs Stream divergence** (Findings #2, #6, #26) — The sync `/ai-executive-summary` and streaming `/ai-executive-summary/stream` have nearly-identical output contracts but use DIFFERENT parsing pipelines, DIFFERENT mind context fetches, and DIFFERENT fallback shapes. Anything added to one must be manually added to the other. Session-33 added `analytics_coverage` and `_parse_agent_exec_summary_response` to streaming; sync didn't get the same treatment.

3. **Silent failures in mind context** (Findings #4, #12, #18) — Multiple paths drop institutional context without alarming: legacy fallback to `analysis_type`, exception-swallowing, file-missing AssetClassMind. Each looks like a successful run with no Layer 2.5. AI users have no way to detect "you saw less knowledge than you should have".

4. **Race conditions in append-only stores** (Findings #7, #16, #25) — Pattern detector mind writes, pending-review queue, fund-wide stats — all use simple `open('a').write` or `open('w')` without OS-level locking or atomic write semantics. Session-31's snapshot UPSERT path is well-defended but the JSONL/JSON layers aren't.

5. **Token budget vs reliability trade-off undocumented** (Findings #15, #19, #21) — Memo polish per-section costs ~11x input tokens (intentional). Citation audit and judgment sections also have non-trivial token budgets. The platform has no internal alarm if a memo costs >$10 (analyst would only see post-hoc in the cost field).

6. **Tool circuit breaker + handler exception coupling** (Finding #11) — The 3-consecutive-errors rule fires on legitimate handler runtime errors. A single recurring bug breaks the agent.

7. **Polish + parser validation gap** (Findings #9, #15, #33) — Polish stage trusts the LLM to preserve metrics, citations, and caveats based on prompt text. No post-output validation. Hallucination potential is real.

8. **§17 confidence/population fields gracefully degrade** (Finding #22) — Missing fields = treated as A-grade by default. Inflates confidence silently for incomplete analytics.

---

## Appendix — Noted intentional decisions

- **Per-section polish fan-out** (~11× input tokens, $3.50-6.00/memo) is intentional — session 26.2 reliability trade-off vs single-blob 40KB Opus 4.7 truncation. Not flagged.
- **SSE thread offload requirement** (session 32) is binding for new agent SSE endpoints. Flagged for `backend/agents.py:_stream_agent` (Finding #13) as latent regression.
- **5-layer mind context architecture** (Framework → Master → Asset Class → Methodology → Company → Thesis) is doctrine. Not flagged.
- **"Informed by N asset-class sources" wording** is intentional non-per-paragraph framing. Honest about what we can vs can't claim. Not flagged.
- **Asset class keying by `config["asset_class"]` (semantic, not company-shortname)** — session 28 Finding #3 fix. Anything keying by `analysis_type` is a regression. Findings #4, #12 flag latent regressions.
- **max_tokens=16000 for exec summary, 2000 default** (session 33) — appropriate. Not flagged. Memo_writer (3000) flagged for research pack truncation risk (Finding #19).
- **Graceful-skip strings must NOT start with "Error:"** (session 33) — runtime currently DOES produce `"Error: ..."` for unknown tools and session limits (lines 193, 204) which DO count toward circuit breaker. Flagged in Finding #11 as defense-in-depth refinement.

---

## TL;DR — Top 5 most important findings

1. **Finding #1 (CRITICAL)** — Tamara UAE Executive Summary uses KSA's Company Mind. Five `_build_*_full_context` functions hardcode product. UAE memos cite KSA-flavored institutional context. Cross-product memory leak undetectable in output. Fix: pass company/product through.

2. **Finding #3 (CRITICAL)** — AI cache key omits snapshot_id for live-* DB snapshots. Integration API mid-day mutations served as stale AI summaries until next UTC day. PAR went 4.2% → 7.8%, AI still says 4.2%. Fix: include `snapshot.ingested_at` in cache key for non-tape sources.

3. **Finding #5 (CRITICAL)** — Citation audit returns `[]` (no issues) on JSON parse failure — INDISTINGUISHABLE from genuine "no issues found". Fabricated citations slip through to polished memo. Fix: synthesize `_audit_failed` issue on parse error.

4. **Finding #7 (CRITICAL)** — Pattern detector concurrent ingests can both write the same `pattern_id` mind entry (idempotency check fails because neither has seen the other's append). JSONL accumulates duplicates. Fix: file lock + atomic write.

5. **Finding #13 (WARNING but high latent)** — `backend/agents.py:_stream_agent` still uses inline `asyncio.create_task` pattern that session 32 codified as broken. Heartbeats fire, but agent is blocked in sync Anthropic client on the main thread. Memo regen, compliance check, onboarding endpoints all share the bug. Fix: refactor to threading.Thread + own loop, mirror `get_executive_summary_stream`.
