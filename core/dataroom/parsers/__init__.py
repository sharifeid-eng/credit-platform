"""
Parser registry for data room document ingestion.

Routes files to the appropriate parser based on file extension.
"""

from .pdf_parser import PdfParser
from .excel_parser import ExcelParser
from .csv_parser import CsvParser
from .docx_parser import DocxParser
from .json_parser import JsonParser

# Ordered list of parsers. First match wins.
PARSER_REGISTRY = [
    PdfParser(),
    ExcelParser(),
    CsvParser(),
    DocxParser(),
    JsonParser(),
]


def get_parser(filepath: str):
    """Return the first parser that can handle this file type.

    Args:
        filepath: Path to the file to parse.

    Returns:
        A parser instance, or None if no parser can handle the file.
    """
    for parser in PARSER_REGISTRY:
        if parser.can_handle(filepath):
            return parser
    return None


__all__ = [
    "PARSER_REGISTRY",
    "get_parser",
    "PdfParser",
    "ExcelParser",
    "CsvParser",
    "DocxParser",
]
