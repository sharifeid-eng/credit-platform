"""
CSV and TSV parser using pandas.
"""

from pathlib import Path
from .base import BaseParser, ParseResult


class CsvParser(BaseParser):
    """Extract text and table from CSV/TSV files."""

    extensions = [".csv", ".tsv"]

    def parse(self, filepath: str) -> ParseResult:
        """Extract text and table from a CSV or TSV file.

        Reads the file into a DataFrame, produces a text summary
        (column names, row count, sample rows), and returns the full
        data as a single table dict.

        Returns:
            ParseResult with text summary and one table.
        """
        try:
            import pandas as pd
        except ImportError:
            return ParseResult(error="pandas not installed")

        path = Path(filepath)
        if not path.exists():
            return ParseResult(error=f"File not found: {filepath}")

        sep = "\t" if path.suffix.lower() == ".tsv" else ","

        try:
            df = pd.read_csv(str(path), sep=sep, low_memory=False)
        except Exception as e:
            return ParseResult(error=f"Failed to read CSV: {e}")

        # Clean column names
        cols = [str(c).strip() for c in df.columns]
        df.columns = cols

        nrows = len(df)
        ncols = len(cols)

        # Build text summary
        text_parts = [
            f"CSV File: {path.name}",
            f"Shape: {nrows} rows x {ncols} columns",
            f"Columns: {', '.join(cols)}",
            "",
        ]

        # Column type summary
        text_parts.append("Column Types:")
        for col in cols:
            dtype = str(df[col].dtype)
            nulls = int(df[col].isna().sum())
            text_parts.append(f"  {col}: {dtype} ({nulls} nulls)")
        text_parts.append("")

        # Sample rows (first 10)
        preview_rows = min(nrows, 10)
        text_parts.append(f"First {preview_rows} rows:")
        for _, row in df.head(preview_rows).iterrows():
            vals = [_format_csv_cell(row[c]) for c in cols]
            text_parts.append(" | ".join(vals))

        if nrows > preview_rows:
            text_parts.append(f"... ({nrows - preview_rows} more rows)")

        # Basic descriptive stats for numeric columns
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            text_parts.append("")
            text_parts.append("Numeric Summary:")
            try:
                desc = df[numeric_cols].describe()
                for col in numeric_cols[:10]:  # Limit to first 10 numeric cols
                    text_parts.append(
                        f"  {col}: min={desc[col].get('min', '?'):.4g}, "
                        f"mean={desc[col].get('mean', '?'):.4g}, "
                        f"max={desc[col].get('max', '?'):.4g}"
                    )
            except Exception:
                pass

        full_text = "\n".join(text_parts)

        # Build table
        rows = []
        for _, row in df.iterrows():
            rows.append([_format_csv_cell(row[c]) for c in cols])

        table = {
            "headers": cols,
            "rows": rows,
        }

        metadata = {
            "filename": path.name,
            "rows": nrows,
            "cols": ncols,
            "separator": sep,
        }

        return ParseResult(
            text=full_text,
            tables=[table],
            metadata=metadata,
            page_count=1,
        )


def _format_csv_cell(v) -> str:
    """Format a cell value to string."""
    if v is None:
        return ""
    try:
        import numpy as np
        if isinstance(v, float) and np.isnan(v):
            return ""
    except ImportError:
        if isinstance(v, float) and v != v:
            return ""
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v).strip()
