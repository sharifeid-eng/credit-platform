# Section D: UX Trust Audit

**Files analyzed:** 20
**Findings:** Critical 7 | Warning 13 | Improvement 8
**Date:** 2026-04-26

This audit examined the React presentation layer for ways an analyst or IC member could be misled by a chart, KPI, badge, or interaction state. Doctrine items per the assignment (lifetime-primary PAR, "Informed by N sources" wording, balance columns reflecting snapshot date, 5-color severity scale, sidebar drawer pattern) are explicitly NOT flagged.

## Findings

### CRITICAL Finding 1: SilqTabContent and KlaimTabContent reference an out-of-scope `snapshotsMeta`, breaking the Data Integrity dropdown silently

- **File:** `frontend/src/pages/TapeAnalytics.jsx:247` (SILQ branch) and `frontend/src/pages/TapeAnalytics.jsx:366` (Klaim branch)
- **Trigger:** User navigates to `Data Integrity` tab on either Klaim or SILQ.
- **Impact:** `<DataIntegrityChart ... snapshotsMeta={snapshotsMeta} ... />` at lines 247 and 366 references the identifier `snapshotsMeta`, but the surrounding function `SilqTabContent` (line 232) destructures only `{ tab, activeTab, company, product, snapshot, snapshots, currency, asOfDate, summary, summaryLoading, aiCache, onAiCache, isBackdated }` — `snapshotsMeta` is not destructured. `KlaimTabContent` at line 267 has the identical bug. Since the file imports nothing named `snapshotsMeta`, the JSX evaluates the bare name against the module/global scope; under strict mode this throws ReferenceError on render, blanking the tab. In dev with Vite + React 18, the most likely outcome is a hard error on tab open. If the Data Integrity tab still renders for any of these paths, the dropdowns would lose their TAPE/LIVE pill annotations — the user wouldn't be able to distinguish a tape snapshot from a same-day live snapshot when picking the two-tape comparison. That defeats the entire point of `SnapshotSelect`.
- **Fix:** Add `snapshotsMeta` to the destructured prop lists of both `SilqTabContent` and `KlaimTabContent`, then pass it down from the parent (which already has it via `useCompany()`).
- **Before/after snippet:**
```jsx
// Before (line 232 + 267)
function SilqTabContent({ tab, activeTab, company, product, snapshot, snapshots, currency, asOfDate, ... }) {
  // ...
  return <DataIntegrityChart company={company} product={product} snapshots={snapshots} snapshotsMeta={snapshotsMeta} currency={currency} />
  //                                                                                  ^^^^^^^^^^^^^^^^^ undefined identifier
}

// After
function SilqTabContent({ tab, activeTab, company, product, snapshot, snapshots, snapshotsMeta, currency, asOfDate, ... }) {
  // ...same line works
}
```

### CRITICAL Finding 2: EjariDashboard fabricates a "$ at risk" subtitle for PAR cards by multiplying PAR rate × outstanding_principal — but PAR's actual denominator is undocumented

- **File:** `frontend/src/pages/EjariDashboard.jsx:93-96`
- **Trigger:** User loads Ejari dashboard, looks at any PAR card on Overview.
- **Impact:** Subtitle for each PAR card is computed as `fmtDollar(km.outstanding_principal * (km.par30 || 0))` — which produces a dollar amount **only correct if PAR30's denominator is `outstanding_principal`**. The Ejari ODS workbook is parsed verbatim by `core/analysis_ejari.py`; the parser doesn't expose the denominator at all, so the frontend has no way to know whether the upstream PAR is computed against active outstanding, lifetime originated, or something else. If Ejari's PAR is in fact lifetime-style (against `total_originated`) — which is plausible because their workbook also surfaces `total_originated` and `total_funded` separately from `outstanding_principal` — then the displayed "$X at risk" can be off by a factor of 2-5×, in either direction depending on the book's age. An IC member could misjudge concentration.
- **Fix:** Either (a) get the upstream ODS to expose `par30_amount` directly so the at-risk number is a measured quantity, or (b) drop the multiplication entirely and show `(km.active_loans * km.par30).toFixed(0)} loans flagged` — a unitless count that doesn't pretend to be an exposure measurement, or (c) explicitly label the subtitle as "approx" with a tooltip naming the assumption. Per the §17 exemption documented for Ejari (parser reshapes upstream aggregates), declining to display a derived dollar figure is the safest option.
- **Before/after snippet:**
```jsx
// Before (line 93)
<KpiCard label="PAR 30+" value={fmtPct(km.par30)} sub={`${fmtDollar(km.outstanding_principal * (km.par30 || 0))} at risk`} ... />

// After (option b — unitless count)
<KpiCard label="PAR 30+" value={fmtPct(km.par30)} sub={`${Math.round((km.active_loans || 0) * (km.par30 || 0))} loans flagged`} ... />
```

### CRITICAL Finding 3: EjariDashboard PAR cards have no ConfidenceBadge or population disclosure — IC sees a number with no provenance

- **File:** `frontend/src/pages/EjariDashboard.jsx:93-96`
- **Trigger:** User compares Ejari PAR 30+ to Klaim/SILQ/Aajil PAR 30+ side-by-side via Executive Summary table or memos.
- **Impact:** Klaim, SILQ, and Aajil all wire `confidence` and `population` props into PAR KpiCards (lines 423-425 of TapeAnalytics SILQ branch, 576-578 Klaim branch, 313-339 Aajil). Ejari ships none. An IC reader sees four PAR cards across the platform that look visually identical but have radically different provenance (Klaim/SILQ/Aajil are observed against `total_originated` per Framework §17; Ejari is whatever the upstream ODS chose to compute). The intentional Ejari §17 exemption documented in `core/analysis_ejari.py` doesn't excuse the UI from disclosing that the metric is upstream-computed.
- **Fix:** Add `confidence="C"` (single-snapshot upstream aggregate, opaque method), `population="snapshot_date_state"`, and `confidenceNote="Ejari workbook upstream PAR — denominator and methodology disclosed in the Notes sheet, not by Laith"` to each Ejari PAR card.

### CRITICAL Finding 4: Currency toggle does not invalidate disk-cached AI commentary — switching USD → AED → USD can serve a stale-currency response

- **File:** `frontend/src/contexts/CompanyContext.jsx:93-96` + `frontend/src/components/AICommentary.jsx:13-27`
- **Trigger:** User generates AI commentary in USD → toggles to AED → switches snapshot/tab → toggles back to USD → reads commentary.
- **Impact:** `CompanyContext` clears `aiCache` only on `[snapshot]` change (line 94-96), NOT on `[currency]` change. Per CLAUDE.md ("AI response disk cache" entry), the BACKEND cache key includes currency, so a refresh-aware backend would return the right cached commentary. But the FRONTEND in-memory `aiCache` state survives currency toggles and is rendered verbatim by `AICommentary.jsx:128` (`<CommentaryBody text={cached} />`). Numbers in AI commentary are currency-specific (e.g., "AED 8.5M collected"). After flipping USD → AED → USD without an explicit Regenerate, an analyst can be reading AED-denominated commentary while the dashboard cards display USD figures. The disconnect is silent — there's no "stale" indicator on commentary.
- **Fix:** In `CompanyContext.jsx`, change the cache-clearing effect to also depend on `currency`:
```jsx
// Before (line 94-96)
useEffect(() => {
  setAiCache(null)
}, [snapshot])

// After
useEffect(() => {
  setAiCache(null)
}, [snapshot, currency])
```

### CRITICAL Finding 5: Aajil cohort table "% of Active" computed against `total_active_balance` even when bucket data is lifetime — denominator could be wrong by 10-20×

- **File:** `frontend/src/pages/AajilDashboard.jsx:391`
- **Trigger:** User views Aajil Delinquency tab → Bucket Detail table.
- **Impact:** Last column "% of Active" formula: `(b.balance / dd.total_active_balance * 100).toFixed(1)`. If `b.balance` represents originated/lifetime balance for that bucket and `total_active_balance` is the active-only book, the ratios printed will be inflated 10-20× (since active is typically a small fraction of originated for installment products). The chart at line 343-355 uses the same `buckets` array but does not divide by anything — it shows raw balance — so the chart and the table would tell completely different stories on the same data without any cross-check warning.
- **Fix:** Verify the population of `bucket.balance` from backend (active vs lifetime), and either rename the column to match (e.g., "% of Active Outstanding" with a tooltip naming the denominator) or add a ConfidenceBadge marker. If the backend ships a per-bucket disclosure field (`bucket_population`), display it in the table header.

### CRITICAL Finding 6: Aajil collection rate Y-axis pinned to `domain={[0, 130]}` — invites misreading rate spikes as fundamental performance, hides scale artifacts

- **File:** `frontend/src/pages/AajilDashboard.jsx:411`
- **Trigger:** User views Aajil Collections tab line chart.
- **Impact:** Right-axis line shows "Collection Rate %" with hardcoded `domain={[0, 130]}`. This is visually anchored to >100% to accommodate over-collection events (e.g., late lump-sum payments arriving in a later month than their cohort), but: (a) at this fixed scale, monthly collection rate variation between 75-95% (the meaningful range) becomes a faint zigzag near the bottom-middle of the chart while transient >100% spikes dominate the eye; (b) the chart doesn't label that >100% indicates timing-mismatch over-collection — an IC member sees 130% and assumes something is wrong with the data. Combined with the line's narrow visual range, real performance trends are obscured.
- **Fix:** Either compute domain dynamically from data (`Math.max(...vals) * 1.1`) capped at e.g. 200, OR add a small caveat note below the chart: "Rates >100% reflect lump-sum cash arriving outside the originating cohort's month." Better: split into two charts — one for collection rate (capped 0-100%) and one for cumulative recovery (the over-100% case).

### CRITICAL Finding 7: PortfolioStatsHero "Live Portfolio" banner shows ALL dashes but is rendered with the same visual weight as the live "Data Analyzed" banner — desktop users may misread "—" as zero

- **File:** `frontend/src/components/PortfolioStatsHero.jsx:182-194`
- **Trigger:** First-time visitor, or returning user, lands on Home page on desktop.
- **Impact:** Banner 2 ("Live Portfolio") renders five stat cells all with `empty` prop, which display "—" via `StatCell` line 35 (`empty ? '—' : ...`). Each is labeled with a real metric: "Active Exposure", "PAR 30+", "PAR 90+", "Covenants in Breach", "Concentration (HHI)". The visual treatment is identical to the populated banner above. On mobile the banner is hidden (line 182 `{!isMobile && ...}`) — but on desktop, an IC member glancing at the Home page can read "PAR 30+ —" as "PAR 30+ none" or "PAR 30+ zero", thus inferring the platform monitors zero portfolios at risk. Worse: there's no "Coming soon" or "Awaiting integration" sub-label.
- **Fix:** Either hide Banner 2 entirely until any of its values is real (use the same `{!isMobile && stats?.has_live_data && ...}` pattern), or add a watermark across the banner reading "Live data feed — not yet connected" with reduced opacity on the values.

### WARNING Finding 8: Klaim Operational WAL/Realized WAL stale-banner conflict — "Degraded — active-clean only" appears in both header AND card subtitle

- **File:** `frontend/src/pages/TapeAnalytics.jsx:597-602` and 666-674
- **Trigger:** User loads Klaim tape that lacks `Collection days so far` (e.g., Mar 3 2026 tape).
- **Impact:** When `opWal.confidence === 'C'`, the section header at line 666-674 shows "Degraded on this tape — active only" gold dashed badge AND the Operational WAL card's `sub` field (line 597-599) repeats `"Degraded — active-clean only (tape lacks close-age)"`. The user sees the same warning twice with slightly different wording, which can read as two separate caveats. The card's `confidence: opWal.confidence` (passed to the C-grade ConfidenceBadge) is a third disclosure of the same fact.
- **Fix:** Pick ONE disclosure surface. The most discoverable is the ConfidenceBadge tooltip; the section-header amber pill is visible at a glance. Drop the redundant card-subtitle text and use the freed space for "Excludes 0 stale deals (0% of PV)" parity with the non-degraded subtitle.

### WARNING Finding 9: ConfidenceBadge tooltip is browser-native `title=` attribute — desktop hover works but mobile/tablet have no tap-to-reveal mechanism

- **File:** `frontend/src/components/ConfidenceBadge.jsx:131-141`
- **Trigger:** Mobile/tablet user (assignment confirms isMobile is supported per the breakpoint hook) reviews Klaim/SILQ/Aajil dashboard.
- **Impact:** The §17 disclosure (population, method, note) lives entirely inside the native `title="..."` attribute (line 133). On desktop this surfaces on mouse hover. On touch devices (iPad, phone) browsers either ignore `title=` entirely or require long-press (varies by OS/browser). The whole framework §17 audit trail (sessions 34, 35, 36) hinges on analysts being able to read these tooltips. A tablet-only IC member never sees the population disclosure for any rate — they see only the A/B/C letter without context. The doctrine "active remains available for covenant compliance" is invisible to them.
- **Fix:** Replace native `title=` with a controlled tooltip primitive (e.g., Radix UI Tooltip or a tiny custom component) that opens on `onClick`/`onTouchStart` for touch devices and `onMouseEnter` for pointer devices. Alternatively, on touch devices, expand the tooltip into an inline reveal toggled by tapping the badge.

### WARNING Finding 10: AICommentary toggle between cached + Regenerate has no visual indicator that ON-CACHE state and POST-REGENERATE state are different — analyst loses provenance trail

- **File:** `frontend/src/components/AICommentary.jsx:46-65, 71-100`
- **Trigger:** User generates commentary, sees "CACHED" badge → clicks "Regenerate" → fresh commentary renders.
- **Impact:** `fromCache` is set to `false` after Regenerate (line 20) so the CACHED badge disappears. But: (a) there's no visual indicator that the body text JUST changed (other than the slide-up animation on line 121-130, which fires on every render of the body); (b) the "Regenerate" button doesn't change to "Regenerate again" or show last-generated timestamp; (c) `cached` is the prop name but ALSO the variable name for the commentary text — this terminology overload makes it impossible to tell at a glance whether you're looking at fresh content. An analyst could click Regenerate, see the body update with mostly-similar text (Anthropic re-runs are not deterministic), and not realize whether they got new analysis or stale cache.
- **Fix:** Track `lastGeneratedAt: Date | null` inside the component and display "Generated 2m ago" in the header next to the CACHED badge area. After Regenerate, this swaps to "Just now" briefly. The state separation makes provenance clear without changing the underlying cache logic.

### WARNING Finding 11: ExecutiveSummary `assetClassSources` footer renders identically to a primary content section — the muted teal looks like an attribution claim

- **File:** `frontend/src/pages/ExecutiveSummary.jsx:746-808`
- **Trigger:** User reads Executive Summary with Asset Class Mind entries that have citations.
- **Impact:** The "Informed by N asset-class sources" footer (line 774) is intentionally NOT a per-paragraph attribution — that's documented in the comment at line 740-744. But visually: the teal box with `borderRadius: 8`, `border: '1px solid rgba(45,212,191,0.18)'`, and 25 numbered citations rendered as `<ol>` is the same visual weight as the credit findings section above it (which uses `border: 1px solid {sev.border}22, borderLeft: 3px solid`). An IC member glancing at it could read it as "the agent cited these 25 sources to support its findings", which is the bug-prone interpretation the comment explicitly warns against. The "Informed by" wording is a doctrine item per the assignment so should NOT be changed — but the visual styling is a separate UX trust issue.
- **Fix:** Reduce the visual prominence: lighter background, no border, smaller font. Position it lower on the page (after Findings, not between Bottom Line and Findings) so it reads as a footer, not a body section. Add an inline tooltip on the toggle button explaining "These sources were available in AI context but were not necessarily cited per claim."

### WARNING Finding 12: BackdatedBanner shows two-column "ACCURATE / TAPE DATE" split that wraps awkwardly on narrow screens — list of metric names becomes a wall of text

- **File:** `frontend/src/components/BackdatedBanner.jsx:27-36`
- **Trigger:** User on mobile/tablet (or with narrow desktop window) selects an as-of date earlier than the snapshot date.
- **Impact:** The `<div style={{ marginTop: 6, display: 'flex', gap: 20 }}>` doesn't include `flexDirection: isMobile ? 'column' : 'row'`. The inline metric lists ("Deal count, originated volume, deployment, cohort selection, vintage composition" / "Outstanding, collected, denied, rates, margins, PAR, revenue, ageing") wrap in unpredictable ways on narrow viewports. Worse — there's no `useBreakpoint()` reference at all in this file. CLAUDE.md explicitly notes: "any flex container that switches between sidebar (desktop) and stacked (mobile) layout MUST include flexDirection: isMobile ? 'column' : 'row' — the default row breaks mobile."
- **Fix:** Add a useBreakpoint hook to BackdatedBanner and apply `flexDirection: isMobile ? 'column' : 'row'` and `gap: isMobile ? 8 : 20` on the inner flex container. Same fix for the outer wrapper at line 14-21 to handle very narrow widths.

### WARNING Finding 13: Klaim PAR card colors flag 1.5% LIFETIME PAR 30+ as warning (gold) — but 1.5% is highly compliant on a lifetime denominator (covenant trigger is 7%)

- **File:** `frontend/src/pages/TapeAnalytics.jsx:576`
- **Trigger:** User loads Klaim tape, looks at PAR 30+ card on Overview.
- **Impact:** Color thresholds: `(par.lifetime_par30 ?? par.par30) > 2 ? 'red' : (par.lifetime_par30 ?? par.par30) > 1 ? 'gold' : 'teal'`. After session 36, the headline IS lifetime — with denominator `total_originated`. Klaim's actual lifetime PAR 30+ is ~2.4% (per CLAUDE.md "Apr 15 ... PAR30 covenant breached (36.6% vs 7% threshold)" — that was active; lifetime is much smaller). The covenant breach threshold for Klaim is 7% on the active-outstanding view; the lifetime view never approaches 7% in normal operation. So a 1.5% lifetime PAR 30+ trips the 'gold' warning color despite being deeply compliant. The thresholds 1% / 2% appear to be tuned for lifetime ranges but they're TIGHTER than the covenant — i.e., the dashboard cries wolf at numbers nowhere near covenant breach.
- **Fix:** Recalibrate thresholds to align with what an IC actually wants flagged. For Klaim lifetime: `> 5 ? 'red' : > 3 ? 'gold' : 'teal'` (more space before warning). Better: drive thresholds from facility-config covenant levels rather than hardcoded magic numbers — backend already exposes them.

### WARNING Finding 14: SILQ PAR card subtitle "Active: X.XX%" can be misread as "Active PAR is 0% of (something)" when the active denominator is empty

- **File:** `frontend/src/pages/TapeAnalytics.jsx:417-420`
- **Trigger:** User views SILQ Overview when active_outstanding is 0 (e.g., a tape with all loans completed/written off).
- **Impact:** `silqParBuildSub` returns `${atRisk} · Active: ${activePct.toFixed(2)}%`. If `summary.par30` is `null` because `active_outstanding === 0`, the subtitle skips the Active suffix correctly. But if `summary.par30 === 0` (a real zero — no overdue active loans), the subtitle reads "X.X K at risk · Active: 0.00%". The "at risk" amount is computed against lifetime; the "Active: 0.00%" is technically true but reads like a boast/claim that could be misread as fundamental quality rather than a degenerate state of an aging book.
- **Fix:** Append a tooltip or symbol when `summary.par30 === 0 && active_count_low`, or change the wording to "Active book empty" when `active_outstanding < small_threshold`.

### WARNING Finding 15: Snapshot `<select>` in Covenants.jsx is a NATIVE select, NOT SnapshotSelect — TAPE/LIVE pills missing, same-day collisions invisible

- **File:** `frontend/src/components/portfolio/Covenants.jsx:108-129`
- **Trigger:** User on Portfolio Analytics → Covenants tab opens the date dropdown.
- **Impact:** Per CLAUDE.md session 31: same-day tape + live collision exists, and `resolve_snapshot` resolves by ingested-time DESC. The Tape Analytics dashboard uses `SnapshotSelect` to disambiguate via colored pills. But Portfolio Covenants uses a native `<select>` with raw date strings (line 122-126). When two snapshots exist for the same date (e.g., 2026-04-15 from tape + live-2026-04-15), the native select shows two identical-looking entries. Analyst clicks one or the other and gets different covenant readings without knowing which source is which.
- **Fix:** Replace the native `<select>` with `SnapshotSelect`, plumbing `snapshotsMeta` from `useCompany()`. Same fix likely applies to other covenant-history dropdowns elsewhere in the portfolio area.

### WARNING Finding 16: BorrowingBase Movement Attribution reverses the sign convention — positive `net_change` shown as teal "good", but BB increase due to advance rate widening is actually risk-on

- **File:** `frontend/src/components/portfolio/BorrowingBase.jsx:101-118`
- **Trigger:** User views Borrowing Base after a period when advance rates widened (e.g., facility amendment) or eligibility criteria loosened.
- **Impact:** `d.movement.net_change >= 0 ? 'rgba(45,212,191,0.1)' : ...` paints positive change as teal (positive). But "BB increase" is not unambiguously good — it can mean (a) more receivables originated (risk-positive), (b) advance rate widened (risk-on, fund leverage up), (c) concentration limit relaxed (risk-on). An IC member sees teal-positive on a chart showing "+$5M BB" and assumes good; the underlying driver could be a rate widening that ALSO increased fund risk. The waterfall steps below (line 124-178) do break out the drivers, but the pill at the top has already painted the moral judgment.
- **Fix:** Drop the green/red coloring on the headline pill — make it neutral white/muted. Reserve color for the per-step deltas where the driver is unambiguous (e.g., concentration adjustment going UP is unambiguously good = teal; portfolio shrinkage is ambiguous = neutral).

### WARNING Finding 17: AICommentary renders raw text via `whiteSpace: 'pre-wrap'` and string parsing for headers — markdown-style asterisks or hashes from AI render as literal characters, not formatted text

- **File:** `frontend/src/components/AICommentary.jsx:139-178`
- **Trigger:** AI generates commentary that includes markdown (e.g., `**bold**` or `## Header`).
- **Impact:** `CommentaryBody` parses lines via simple regex (line 145-146): bullets `^[•\-›]/` and headers (line ending in `:` and short). It does NOT process markdown. If Claude outputs `**Critical:**` for emphasis, the asterisks render literally. If it outputs `## Risk Assessment`, that renders as a paragraph starting with hashes. The user sees raw markdown punctuation. Worse: Anthropic's models often emit markdown by default; enforcing plain-text in the system prompt is fragile across model upgrades.
- **Fix:** Add a markdown renderer (e.g., `react-markdown`) for AI-generated text. Strip markdown is option B but loses semantic meaning. Either way, document the contract in the comment block at line 5 ("AICommentary — dark theme...").

### IMPROVEMENT Finding 18: SnapshotSelect arrow keys don't wrap — pressing ArrowDown at end stays at end without indicator

- **File:** `frontend/src/components/SnapshotSelect.jsx:78-84`
- **Trigger:** Power user navigates dropdown via keyboard.
- **Impact:** `setHighlight(i => Math.min(... + 1, snapshots.length - 1))` clamps. Behavior is correct but not discoverable; user pressing ArrowDown 5 times when there are 4 snapshots gets no signal at boundary.
- **Fix:** Either add wraparound (`(i + 1) % snapshots.length`) or visually pulse the highlighted row when at boundary.

### IMPROVEMENT Finding 19: SnapshotSelect dropdown doesn't auto-scroll to keep highlighted row visible during keyboard nav

- **File:** `frontend/src/components/SnapshotSelect.jsx:124-131`
- **Trigger:** User opens dropdown, presses ArrowDown rapidly through 30+ snapshots (Klaim has 5+, but bigger companies will have more).
- **Impact:** `maxHeight: 320, overflowY: 'auto'` — dropdown scrolls if content exceeds 320px. But arrow-key highlight changes don't automatically scroll the item into view. User can press ArrowDown past visible rows and not see the highlight until the focused row scrolls naturally. A practical concern only when N > ~12.
- **Fix:** Add a `useEffect` or `ref.scrollIntoView({ block: 'nearest' })` keyed off `highlight`.

### IMPROVEMENT Finding 20: ConfidenceBadge uses native `title=` for tooltip — text may overflow on long population codes + notes (no max-width, no rich formatting)

- **File:** `frontend/src/components/ConfidenceBadge.jsx:131-141`
- **Trigger:** User hovers a Confidence-C badge with a long `note` (e.g., "Operational-age proxy for contractual DPD; deals where Pending Insurance Response > 60d treated as overdue. Recoverable via reinstatement after dispute resolution.").
- **Impact:** Native `title=` tooltips on most browsers wrap based on the OS, not the page CSS. On Windows, tooltips can be ~400px wide; on macOS they wrap differently. Long Framework §17 disclosures display unpredictably. Combined with Finding 9 (no touch support), this is the second reason to swap the primitive.
- **Fix:** Same as Finding 9 — replace with controlled component. Allows max-width, Markdown bullet rendering, and consistent layout cross-platform.

### IMPROVEMENT Finding 21: TabInsight clears state on `[snapshot, currency]` change but NOT on `[asOfDate]` change

- **File:** `frontend/src/components/TabInsight.jsx:16-21`
- **Trigger:** User opens TabInsight cached → changes as-of date (e.g., to backdate) → toggles open.
- **Impact:** `useEffect(() => { setText(null); setOpen(false); ... }, [snapshot, currency])` — missing `asOfDate` dependency. If user backdates the view (which makes AI insights INVALID per the backend's HTTP 400 backdated guard) but text was previously cached, opening the toggle will show stale insight text from a non-backdated view alongside an "Disabled for backdated views" label. The body text doesn't auto-clear.
- **Fix:** Add `asOfDate` to the dependency array. Or pull `isBackdated` from the parent and treat it as a clearing trigger.

### IMPROVEMENT Finding 22: AajilDashboard collection rate table uses raw `< 0.05 ? 'Well diversified' : 'Moderate'` HHI thresholds without disclosing source

- **File:** `frontend/src/pages/AajilDashboard.jsx:237 + 505`
- **Trigger:** User views Aajil Overview / Concentration tab, sees "Well diversified" subtitle on HHI card.
- **Impact:** The threshold 0.05 is a literal — Aajil's HHI is `0.0X` per CLAUDE.md (well below the 0.10/0.15 levels common in concentration analysis). "Well diversified" judgment color-codes a methodology decision into the UI. If the IC's risk policy uses a different cutoff (e.g., 0.10 considered concentrated for SME credit), the dashboard contradicts policy without naming the source.
- **Fix:** Add a Confidence/PopulationPill with the threshold note, or footnote naming the source ("0.05 cutoff per Cascade Debt convention").

### IMPROVEMENT Finding 23: ExecutiveSummary StreamProgressPanel TIMER continues even after `error` event — terminal stage frozen at "Writing narrative" while loop above shows error

- **File:** `frontend/src/pages/ExecutiveSummary.jsx:393-409, 447-451`
- **Trigger:** Mid-pipeline error (e.g., circuit breaker, rate limit) during streaming generation.
- **Impact:** `onError` calls `finish()` which clears the timer. Looks correct. BUT: if `onError` fires AFTER `onText` events updated `stage` to "Writing narrative", and before the `finally` block in `finish()` resets `stage`, there's a brief window where the StreamProgressPanel shows `stage="Writing narrative"` with a blinking cursor while the error block above renders. Two contradictory "the agent is doing X" indicators appear simultaneously.
- **Fix:** In `onError`, set `setStage(null)` BEFORE calling `finish()` to ensure the loading panel goes blank immediately when an error appears.

### IMPROVEMENT Finding 24: PortfolioAnalytics data source badge says "Tape Fallback" — but per session 31, no tape-fallback exists; misleading orange-amber styling

- **File:** `frontend/src/pages/PortfolioAnalytics.jsx:115-130`
- **Trigger:** Backend returns `data_source` other than `'database'` (e.g., legacy tape mode in dev environment).
- **Impact:** Per CLAUDE.md session 31: "the tape-fallback read path was removed; portfolio endpoints query DB only." If `dataSource !== 'database'`, the UI labels it "Tape Fallback" with amber styling implying a degraded mode. But session 31 made tape-fallback IMPOSSIBLE — so seeing "Tape Fallback" in production means SOMETHING ELSE went wrong (e.g., backend mismatch, env var unset, stale service). The label is no longer descriptive of reality and could mislead an analyst into accepting bad data as merely "fallback".
- **Fix:** Change the non-database label to "UNKNOWN SOURCE" with red styling, OR fail closed (refuse to render until `dataSource === 'database'`) so a misconfigured backend produces a visible empty state, not a fake "fallback" badge.

### IMPROVEMENT Finding 25: PortfolioAnalytics ignores prior `setError` between rapid tab switches — error message persists across tab change

- **File:** `frontend/src/pages/PortfolioAnalytics.jsx:60-80`
- **Trigger:** User on `borrowing-base` tab gets an error → switches to `concentration-limits` tab without acknowledging.
- **Impact:** `useEffect(() => { ..., setError(null); ... }, [company, product, snapshot, currency, asOfDate, tab, refreshKey])` — does call `setError(null)` on every fetch start. But the fetch is gated by `if (SELF_LOADING_TABS.includes(tab)) return` (line 65) — for `invoices` / `payments` / `bank-statements`, the early-return prevents `setError(null)` from running. So if user gets a covenants-tab error, then switches to invoices, the prior error banner persists at the top of the page (line 98-106 condition `error && (...)` is true regardless of which tab is active).
- **Fix:** Move `setError(null)` BEFORE the early-return at line 65, or move it to a separate `useEffect` keyed only on `[tab]`.

### IMPROVEMENT Finding 26: CovenantTriggerCard threshold marker labels can collide with current-value marker, hiding "Current: X%" reading

- **File:** `frontend/src/components/portfolio/CovenantTriggerCard.jsx:51-71`
- **Trigger:** Tamara dashboard shows a covenant where current_value sits within 8% of an L1/L2/L3 threshold.
- **Impact:** Threshold labels (L1/L2/L3) are positioned at `top: tooClose ? -24 : -14` — they stagger vertically when too close, but the `current_value` marker has no such collision detection. When current ≈ threshold, the marker (3px wide colored bar) AND the dashed L-label line overlap. Visually, user can't tell whether they're at L1 boundary or L2 boundary.
- **Fix:** Add a small label adjacent to the current-value marker (e.g., "→ X%") and apply the same tooClose logic between current and any threshold within 8%.

### IMPROVEMENT Finding 27: DataChat suggested-question prompts include "Search the data room for..." but no DocumentLibrary deep-link from the chat — analyst doesn't know to switch context

- **File:** `frontend/src/components/DataChat.jsx:412-413, 418-419`
- **Trigger:** User clicks suggested prompt "Search the data room for any references to the facility concentration limits."
- **Impact:** Question fires through agent endpoint — agent uses `search_dataroom` tool to find docs. Output is text in the chat bubble. No link back to the actual document for the user to read. If agent returns "Found 3 references in MMA.pdf" the user has no way to JUMP to the doc — they have to manually navigate Sidebar → Research Hub → Document Library and search.
- **Fix:** Make the agent response template include doc IDs, and have DataChat render `[MMA.pdf]` as a clickable link to `GET /companies/{co}/products/{p}/dataroom/documents/{id}/view` in a new tab.

### IMPROVEMENT Finding 28: SilqOverviewTab Overdue Rate color flag triggers at >15% (line 401) — but covenant for SILQ is at 30%/45% (per CLAUDE.md tape spec); cards cry wolf well before the operational concern

- **File:** `frontend/src/pages/TapeAnalytics.jsx:401`
- **Trigger:** User views SILQ Overview with overdue_rate between 16-30%.
- **Impact:** `summary.overdue_rate > 15 ? 'red' : 'gold'` — the threshold 15 is hardcoded, not derived from the covenant. Same antipattern as Finding 13 for Klaim PAR. Combined: across the dashboard there's no single source of truth for "is this metric in a problem state?" — each KpiCard ships its own magic numbers.
- **Fix:** Treat covenant levels (loaded from facility config) as the source of truth and color-code cards relative to them. Provides a single switch when an amendment changes the threshold.

## Themes / patterns observed

- **Out-of-scope identifier bug pattern (Findings 1, 17).** Two independent components reference identifiers that are never destructured from props. Both render-blocking under React strict mode. Suggests an automated lint rule (`no-undef` in eslint or React DevTools) is not enforcing JSX identifier scope. A repo-wide audit of `<Component {prop}={notDestructured} />` would surface more.

- **Currency-stale cache pattern (Finding 4).** `CompanyContext` clears `aiCache` on `[snapshot]` only — does not depend on `[currency]`. AI responses contain currency-specific numbers; a USD/AED toggle without regen produces silent inconsistency. Same gap likely affects TabInsight (Finding 21 confirmed for asOfDate; currency unverified).

- **Hardcoded color thresholds vs. covenant thresholds (Findings 13, 14, 28).** Multiple cards use literal cutoffs (1%, 2%, 1.5%, 15%) for color-coding. None of these derive from facility config. Three independent component authors made up three different "what counts as warning" answers. An IC member comparing dashboard signals across companies sees different thresholds without disclosure.

- **§17 ConfidenceBadge coverage holes (Findings 3, 7, 9, 20).** Ejari PAR cards (Finding 3) ship no badge. PortfolioStatsHero (Finding 7) ships dashes that look like real values. Native `title=` tooltips (Findings 9 and 20) break on touch and have unpredictable wrap. Together these undermine the framework §17 audit trail surfaced by sessions 34/35/36 in three different ways.

- **Native HTML primitives where SnapshotSelect should be used (Finding 15).** Covenants.jsx still uses a native `<select>`. The same-day tape+live ambiguity (CLAUDE.md session 31) makes the native select dangerous. Likely other places — every other dropdown should be audited for snapshot semantics.

- **AI commentary trust gaps (Findings 4, 10, 17, 23).** The cache → regen → display pipeline has multiple state confluences but no single timestamp source. Markdown rendering not handled. Stage indicator can persist after error. Each fix is small but together they erode the analyst's ability to know "what state is this AI output actually in?".

- **Y-axis manipulation in charts (Finding 6, plus risk in others).** Aajil collection chart pinned at `[0, 130]`. Other charts variously pin to 100, 110. The IC perspective: a chart with a fixed-domain Y axis hides outliers but also hides important resolution. Need a unified "ChartTheme" decision across the codebase.

- **Mobile flex-direction lapses (Finding 12).** BackdatedBanner and likely others ignore the CLAUDE.md binding rule. A repo-wide search for `display: 'flex'` containers without `flexDirection: isMobile ? 'column' : 'row'` would surface more.

## Appendix — Noted intentional decisions

The following are doctrine items that were deliberately NOT flagged per the assignment:
- **Lifetime-primary PAR for Klaim, SILQ, Aajil** (session 36 universal §17 rule). All three companies show lifetime as headline, active in subtitle/tooltip. Ejari and Tamara are exempt from §17 and don't dual-show.
- **"Informed by N asset-class sources" footer wording** (intentionally NOT a per-paragraph attribution; documented in `ExecutiveSummary.jsx:740-744` and `DataChat.jsx:254-258`).
- **Tape Analytics balance columns reflect snapshot date** even when as-of-date is backdated (ANALYSIS_FRAMEWORK.md §15). BackdatedBanner correctly classifies metrics as ACCURATE vs TAPE DATE.
- **5-color severity scale on Executive Summary** (Healthy/Acceptable/Warning/Critical/Monitor — line 8-26 of ExecutiveSummary.jsx).
- **240px sidebar drawer pattern on mobile** — coordinated via `MobileMenuContext`.
- **CovenantCard Path B carve-out renders muted note instead of breach projection** (session 30 fix at `CovenantCard.jsx:184-193`) — verified working as designed.
- **Pre-existing pure-CSS preferences** (font choices, spacing tokens, gradient backgrounds) — not flagged per audit rules.

## TL;DR — Top 5 most important findings

1. **Findings 1 (Critical)** — `snapshotsMeta` referenced but not destructured in TapeAnalytics.jsx lines 247 and 366. Either renders broken or strips TAPE/LIVE pills from the Data Integrity dropdown — defeating session 31 disambiguation. Two-line fix; highest priority because it can break a tab outright.

2. **Finding 4 (Critical)** — Currency toggle does NOT clear `aiCache` in `CompanyContext`. USD → AED → USD without regenerating shows AED-denominated commentary alongside USD KpiCards. Silent. Direct three-line fix in `CompanyContext.jsx:94-96`.

3. **Findings 2 + 3 (Critical)** — Ejari PAR cards fabricate a "$X at risk" subtitle without knowing the upstream PAR denominator, AND ship no ConfidenceBadge to disclose this. IC sees a number with implied precision that the underlying ODS doesn't actually claim.

4. **Findings 13 + 14 + 28 (Warning, but pattern)** — Color thresholds for PAR, overdue rate, and HHI are hardcoded magic numbers, not derived from facility covenants. The dashboard cries wolf well below the IC-relevant trigger line, eroding the alert signal.

5. **Findings 9 + 20 (Warning)** — `ConfidenceBadge` tooltip is native HTML `title=`. Mobile/tablet users — likely some IC members reviewing on iPad — never see the §17 population/method disclosure that sessions 34, 35, 36 worked extensively to surface. Replace with a controlled tooltip primitive that handles `onTouchStart` and consistent wrap.
