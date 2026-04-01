# Lessons Learned
Persistent log of mistakes and patterns. Claude reviews this at session start to avoid repeat errors.

---

## 2026-03-28 — SILQ Product Name Cleanup
**Mistake:** Updated all code references (tests, AI prompts, docs) to new product names (RCL, RBF) before verifying the tape data had actually been updated. Tests failed because the Excel file still had old names (RBF_Exc, RBF_NE).
**Rule:** When a task depends on external data changes (tape edits, DB migrations, config changes), verify the data first before updating code that references it. Run a quick data check (`df['column'].value_counts()`) before writing assertions.

---

## 2026-04-01 — Dynamic Grid Reflow from Async Data
**Mistake:** PAR KPI grid used `repeat(${parKpis.length + dtfcKpis.length}, 1fr)` — columns depended on async state. PAR loaded first (3 cols), then DTFC arrived and the grid jumped to 5 cols, visibly resizing the PAR cards mid-view.
**Rule:** Never derive CSS grid column count from async data that loads incrementally. Use a fixed column count (e.g. `repeat(5, 1fr)`) so the layout is stable from first render. Empty cells are better than layout shifts.

---

## 2026-04-01 — Overview Page Consistency Drift
**Mistake:** SILQ's Overview crammed PAR30/PAR60 into inline KPI cards (PAR60 hidden as PAR30's subtitle), while Klaim had a dedicated "Portfolio at Risk" section with individual PAR cards. The Analysis Framework already defined a 5-level hierarchy (L1-L5) that should guide page structure, but it wasn't being applied to the frontend layout.
**Rule:** When adding a new company or tab, follow the established section structure (Main KPIs → Credit Quality → Leading Indicators). Use the Analysis Framework hierarchy to decide which section a metric belongs in. Don't inline L3 (Credit Quality) metrics with L1 (Size) KPIs. Consistency in section structure, bespoke content within sections.
