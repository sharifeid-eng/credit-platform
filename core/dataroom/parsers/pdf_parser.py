"""
PDF parser using pdfplumber for text and table extraction.
"""

from pathlib import Path
from .base import BaseParser, ParseResult


class PdfParser(BaseParser):
    """Extract text and tables from PDF files using pdfplumber."""

    extensions = [".pdf"]

    def parse(self, filepath: str) -> ParseResult:
        """Extract text and tables from a PDF document.

        Uses pdfplumber to:
        - Extract text from each page (joined by page separators)
        - Extract tables from each page as {headers, rows} dicts
        - Record page count and any per-page extraction errors

        Returns:
            ParseResult with full text, extracted tables, and page count.
        """
        try:
            import pdfplumber
        except ImportError:
            return ParseResult(
                error="pdfplumber not installed. Run: pip install pdfplumber"
            )

        path = Path(filepath)
        if not path.exists():
            return ParseResult(error=f"File not found: {filepath}")

        pages_text = []
        tables = []
        errors = []
        page_count = 0

        try:
            with pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    # Extract text
                    try:
                        text = page.extract_text()
                        if text:
                            pages_text.append(text)
                        else:
                            pages_text.append("")
                    except Exception as e:
                        pages_text.append("")
                        errors.append(f"Page {i + 1} text extraction error: {e}")

                    # Extract tables
                    try:
                        page_tables = page.extract_tables()
                        if page_tables:
                            for raw_table in page_tables:
                                if not raw_table or len(raw_table) < 2:
                                    continue
                                # First row as headers, rest as data rows
                                headers = [
                                    str(c).strip() if c else ""
                                    for c in raw_table[0]
                                ]
                                rows = []
                                for row in raw_table[1:]:
                                    rows.append([
                                        str(c).strip() if c else ""
                                        for c in row
                                    ])
                                tables.append({
                                    "headers": headers,
                                    "rows": rows,
                                    "page": i + 1,
                                })
                    except Exception as e:
                        errors.append(f"Page {i + 1} table extraction error: {e}")

        except Exception as e:
            return ParseResult(error=f"Failed to open PDF: {e}")

        full_text = "\n\n--- Page Break ---\n\n".join(pages_text)

        metadata = {"filename": path.name}
        if errors:
            metadata["extraction_errors"] = errors

        return ParseResult(
            text=full_text,
            tables=tables,
            metadata=metadata,
            page_count=page_count,
            error=None if not errors else f"{len(errors)} extraction warnings",
        )
