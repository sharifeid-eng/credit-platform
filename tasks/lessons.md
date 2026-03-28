# Lessons Learned
Persistent log of mistakes and patterns. Claude reviews this at session start to avoid repeat errors.

---

## 2026-03-28 — SILQ Product Name Cleanup
**Mistake:** Updated all code references (tests, AI prompts, docs) to new product names (RCL, RBF) before verifying the tape data had actually been updated. Tests failed because the Excel file still had old names (RBF_Exc, RBF_NE).
**Rule:** When a task depends on external data changes (tape edits, DB migrations, config changes), verify the data first before updating code that references it. Run a quick data check (`df['column'].value_counts()`) before writing assertions.
