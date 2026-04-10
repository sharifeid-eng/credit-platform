"""
Base parser interface for data room document parsers.

All parsers inherit from BaseParser and return ParseResult dataclasses.
"""

from dataclasses import dataclass, field


@dataclass
class ParseResult:
    """Result of parsing a single document.

    Attributes:
        text: Full extracted text content.
        tables: List of table dicts, each with 'headers' (list[str]) and 'rows' (list[list]).
        metadata: Parser-specific metadata (e.g. sheet names, author, creation date).
        page_count: Number of pages (PDFs/DOCX) or sheets (Excel).
        error: Error message if parsing partially failed (None = success).
    """
    text: str = ""
    tables: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    page_count: int = 0
    error: str = None


class BaseParser:
    """Abstract base class for document parsers.

    Subclasses must set `extensions` and implement `parse()`.
    """

    extensions: list = []

    def can_handle(self, filepath: str) -> bool:
        """Check if this parser can handle the given file based on extension."""
        lower = str(filepath).lower()
        return any(lower.endswith(ext) for ext in self.extensions)

    def parse(self, filepath: str) -> ParseResult:
        """Parse the document at filepath and return a ParseResult.

        Must be implemented by subclasses.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement parse()")
