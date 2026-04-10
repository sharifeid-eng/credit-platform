"""
IC Memo Engine for the Laith Credit Platform.

Generates investment committee-ready memos by combining:
  - Live tape/portfolio analytics (via AnalyticsBridge)
  - Data room research context (via DataRoomEngine.search)
  - Living Mind institutional memory (via build_mind_context)
  - AI-powered narrative generation (via Claude API)

Four memo templates:
  - credit_memo: Initial investment recommendation
  - monitoring_update: Monthly portfolio health check
  - due_diligence: Deep-dive on prospective companies
  - quarterly_review: Fund-level cross-company review

Usage:
    from core.memo import MemoGenerator, MemoStorage, get_template, list_templates
    from core.memo.pdf_export import export_memo_pdf

    gen = MemoGenerator()
    memo = gen.generate_full_memo("Tamara", "KSA", "credit_memo")
    storage = MemoStorage()
    memo_id = storage.save(memo)
    pdf_bytes = export_memo_pdf(memo, "Tamara", "KSA")
"""

from .templates import get_template, list_templates, SourceLayer, MEMO_TEMPLATES
from .analytics_bridge import AnalyticsBridge
from .generator import MemoGenerator
from .storage import MemoStorage
from .pdf_export import export_memo_pdf

__all__ = [
    "get_template",
    "list_templates",
    "SourceLayer",
    "MEMO_TEMPLATES",
    "AnalyticsBridge",
    "MemoGenerator",
    "MemoStorage",
    "export_memo_pdf",
]
