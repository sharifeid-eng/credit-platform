"""
Document chunking for search and retrieval.

Splits parsed documents into chunks suitable for TF-IDF indexing and
eventual RAG-style retrieval.
"""

import re


def chunk_document(
    text: str,
    tables: list = None,
    metadata: dict = None,
    max_chunk_tokens: int = 800,
    overlap_tokens: int = 100,
) -> list:
    """Split a document into chunks suitable for retrieval.

    Strategy:
    - Split text on paragraph/section boundaries (double newlines, page breaks)
    - Tables are preserved as single chunks (even if > max_chunk_tokens)
    - Each chunk gets: text, chunk_index, section_heading (if detectable), source metadata
    - Overlap between consecutive text chunks for context continuity

    Token estimation uses word count * 1.3 as a simple approximation.

    Args:
        text: Full extracted text from the document.
        tables: Optional list of table dicts from parsing (each with headers/rows).
        metadata: Optional metadata dict to attach to each chunk.
        max_chunk_tokens: Maximum tokens per chunk (default 800).
        overlap_tokens: Token overlap between consecutive text chunks (default 100).

    Returns:
        List of chunk dicts, each with:
        - text: chunk text content
        - chunk_index: integer position in the document
        - chunk_type: "text" or "table"
        - section_heading: detected heading for this chunk (may be None)
        - metadata: copy of input metadata
    """
    if not text and not tables:
        return []

    chunks = []
    chunk_index = 0
    base_meta = metadata or {}

    # ── Phase 1: Split text into sections ──────────────────────────────────

    if text:
        sections = _split_into_sections(text)

        for section_heading, section_text in sections:
            section_text = section_text.strip()
            if not section_text:
                continue

            token_est = _estimate_tokens(section_text)

            if token_est <= max_chunk_tokens:
                # Fits in one chunk
                chunks.append({
                    "text": section_text,
                    "chunk_index": chunk_index,
                    "chunk_type": "text",
                    "section_heading": section_heading,
                    "metadata": dict(base_meta),
                })
                chunk_index += 1
            else:
                # Split into overlapping sub-chunks
                sub_chunks = _split_with_overlap(
                    section_text, max_chunk_tokens, overlap_tokens
                )
                for sub in sub_chunks:
                    chunks.append({
                        "text": sub,
                        "chunk_index": chunk_index,
                        "chunk_type": "text",
                        "section_heading": section_heading,
                        "metadata": dict(base_meta),
                    })
                    chunk_index += 1

    # ── Phase 2: Add tables as individual chunks ───────────────────────────

    if tables:
        for table in tables:
            table_text = _table_to_text(table)
            if not table_text.strip():
                continue

            heading = table.get("sheet") or table.get("table_index")
            if heading is not None:
                heading = f"Table: {heading}"

            chunks.append({
                "text": table_text,
                "chunk_index": chunk_index,
                "chunk_type": "table",
                "section_heading": heading,
                "metadata": dict(base_meta),
            })
            chunk_index += 1

    return chunks


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text using word count * 1.3."""
    words = len(text.split())
    return int(words * 1.3)


def _estimate_words_for_tokens(tokens: int) -> int:
    """Inverse of _estimate_tokens: how many words fit in N tokens."""
    return int(tokens / 1.3)


def _split_into_sections(text: str) -> list:
    """Split text into (heading, body) tuples based on structural cues.

    Detects:
    - Markdown headings (# ... )
    - Page breaks (--- Page Break ---)
    - Double newlines as paragraph boundaries

    Returns list of (heading_or_None, section_text) tuples.
    """
    # Split on page breaks first
    pages = re.split(r"\n*---\s*Page Break\s*---\n*", text)

    sections = []
    current_heading = None

    for page in pages:
        # Split on markdown headings
        parts = re.split(r"\n(#{1,3}\s+.+)", page)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            heading_match = re.match(r"^#{1,3}\s+(.+)$", part)
            if heading_match:
                current_heading = heading_match.group(1).strip()
                continue

            # Split long sections on double newlines
            paragraphs = re.split(r"\n\s*\n", part)
            accumulated = []
            accumulated_tokens = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                para_tokens = _estimate_tokens(para)

                # Check if this paragraph starts a new heading-like line
                # (e.g., "=== Sheet: ..." or all-caps lines)
                sheet_match = re.match(r"^===\s*(.+?)\s*===", para)
                if sheet_match:
                    # Flush accumulated text
                    if accumulated:
                        sections.append((current_heading, "\n\n".join(accumulated)))
                        accumulated = []
                        accumulated_tokens = 0
                    current_heading = sheet_match.group(1)
                    continue

                if accumulated_tokens + para_tokens > 1200:
                    # Flush to avoid oversized sections (chunker will still split)
                    if accumulated:
                        sections.append((current_heading, "\n\n".join(accumulated)))
                    accumulated = [para]
                    accumulated_tokens = para_tokens
                else:
                    accumulated.append(para)
                    accumulated_tokens += para_tokens

            if accumulated:
                sections.append((current_heading, "\n\n".join(accumulated)))

    return sections


def _split_with_overlap(text: str, max_tokens: int, overlap_tokens: int) -> list:
    """Split text into overlapping chunks by word boundaries.

    Each chunk has at most max_tokens estimated tokens. Consecutive chunks
    share overlap_tokens worth of words at their boundaries.
    """
    words = text.split()
    max_words = _estimate_words_for_tokens(max_tokens)
    overlap_words = _estimate_words_for_tokens(overlap_tokens)

    if max_words < 1:
        max_words = 1

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + max_words, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append(chunk_text)

        if end >= len(words):
            break

        # Move start forward, keeping overlap
        start = end - overlap_words
        if start < 0:
            start = 0
        # Prevent infinite loop if overlap >= max_words
        if start >= end:
            start = end

    return chunks


def _table_to_text(table: dict) -> str:
    """Convert a table dict to a text representation.

    Produces a pipe-delimited text table with headers and rows.
    """
    headers = table.get("headers", [])
    rows = table.get("rows", [])

    if not headers and not rows:
        return ""

    lines = []

    # Sheet/source label if available
    sheet = table.get("sheet")
    if sheet:
        lines.append(f"[Table from: {sheet}]")

    if headers:
        lines.append(" | ".join(str(h) for h in headers))
        lines.append(" | ".join("---" for _ in headers))

    for row in rows:
        lines.append(" | ".join(str(c) for c in row))

    return "\n".join(lines)
