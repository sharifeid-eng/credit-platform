"""
Excel and ODS parser using pandas for tabular data extraction.
"""

import warnings
from pathlib import Path
from .base import BaseParser, ParseResult


class ExcelParser(BaseParser):
    """Extract text and tables from Excel (.xlsx, .xls) and ODS workbooks."""

    extensions = [".xlsx", ".xls", ".ods"]

    def parse(self, filepath: str) -> ParseResult:
        """Extract text and tables from an Excel/ODS workbook.

        Reads all sheets. For each sheet:
        - Converts the DataFrame to a text representation (column names + rows)
        - Stores the DataFrame as a table dict with headers and rows
        - Records sheet name and dimensions in metadata

        ODS files use the 'odf' engine (requires odfpy package).

        Returns:
            ParseResult with concatenated text, all tables, and sheet metadata.
        """
        try:
            import pandas as pd
        except ImportError:
            return ParseResult(error="pandas not installed")

        path = Path(filepath)
        if not path.exists():
            return ParseResult(error=f"File not found: {filepath}")

        engine = None
        if path.suffix.lower() == ".ods":
            engine = "odf"

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                all_sheets = pd.read_excel(
                    str(path), sheet_name=None, engine=engine, header=0
                )
        except ImportError as e:
            pkg = "odfpy" if engine == "odf" else "openpyxl"
            return ParseResult(error=f"{pkg} not installed: {e}")
        except Exception as e:
            return ParseResult(error=f"Failed to read workbook: {e}")

        text_parts = []
        tables = []
        sheet_info = []

        for sheet_name, df in all_sheets.items():
            # Skip completely empty sheets
            if df.empty:
                continue

            # Clean column names
            cols = [str(c).strip() for c in df.columns]
            df.columns = cols

            # Drop fully-empty rows and columns
            df = df.dropna(how="all").dropna(axis=1, how="all")
            if df.empty:
                continue

            cols = list(df.columns)
            nrows = len(df)

            # Text representation
            text_parts.append(f"=== Sheet: {sheet_name} ({nrows} rows, {len(cols)} cols) ===")
            text_parts.append("Columns: " + ", ".join(cols))

            # Show first 20 rows as text
            preview_rows = min(nrows, 20)
            for _, row in df.head(preview_rows).iterrows():
                vals = []
                for c in cols:
                    v = row[c]
                    vals.append(_format_cell(v))
                text_parts.append(" | ".join(vals))
            if nrows > preview_rows:
                text_parts.append(f"... ({nrows - preview_rows} more rows)")
            text_parts.append("")

            # Table dict
            rows = []
            for _, row in df.iterrows():
                rows.append([_format_cell(row[c]) for c in cols])

            tables.append({
                "headers": cols,
                "rows": rows,
                "sheet": sheet_name,
            })

            sheet_info.append({
                "name": sheet_name,
                "rows": nrows,
                "cols": len(cols),
            })

        full_text = "\n".join(text_parts)
        metadata = {
            "filename": path.name,
            "sheets": sheet_info,
            "total_sheets": len(sheet_info),
        }

        return ParseResult(
            text=full_text,
            tables=tables,
            metadata=metadata,
            page_count=len(sheet_info),
        )


def _format_cell(v) -> str:
    """Format a single cell value to string, handling NaN and numpy types."""
    if v is None:
        return ""
    try:
        import numpy as np
        if isinstance(v, float) and np.isnan(v):
            return ""
        if isinstance(v, (np.integer,)):
            return str(int(v))
        if isinstance(v, (np.floating,)):
            return f"{float(v):.4g}"
    except ImportError:
        pass
    if isinstance(v, float):
        if v != v:  # NaN check without numpy
            return ""
        return f"{v:.4g}"
    return str(v).strip()
