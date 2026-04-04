# Lessons Learned
Persistent log of mistakes and patterns. Claude reviews this at session start to avoid repeat errors.

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


**Mistake:** SILQ's Overview crammed PAR30/PAR60 into inline KPI cards (PAR60 hidden as PAR30's subtitle), while Klaim had a dedicated "Portfolio at Risk" section with individual PAR cards. The Analysis Framework already defined a 5-level hierarchy (L1-L5) that should guide page structure, but it wasn't being applied to the frontend layout.
**Rule:** When adding a new company or tab, follow the established section structure (Main KPIs → Credit Quality → Leading Indicators). Use the Analysis Framework hierarchy to decide which section a metric belongs in. Don't inline L3 (Credit Quality) metrics with L1 (Size) KPIs. Consistency in section structure, bespoke content within sections.
