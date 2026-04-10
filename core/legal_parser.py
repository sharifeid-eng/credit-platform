"""
core/legal_parser.py
PDF-to-structured-markdown conversion for legal documents.

Uses PyMuPDF (via pymupdf4llm) for markdown conversion and pdfplumber
for table extraction. Legal documents are well-structured (articles,
sections, schedules) — we exploit this structure for semantic chunking.
"""

import os
import re
import json
import hashlib
import logging
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    page: int
    headers: list[str]
    rows: list[list[str]]
    caption: str = ""


@dataclass
class ParsedDocument:
    markdown: str
    sections: dict[str, str]         # section_key → content
    tables: list[ExtractedTable]
    metadata: dict
    definitions_text: str = ""       # Extracted definitions section
    page_count: int = 0


def parse_legal_document(file_path: str) -> ParsedDocument:
    """Parse a legal PDF into structured markdown with sections and tables.

    Pipeline:
      1. pymupdf4llm → full markdown (preserves headers, lists)
      2. pdfplumber → table extraction (advance rate schedules, etc.)
      3. Section chunking by article/section headers
      4. Definitions section isolation
    """
    import pymupdf4llm
    import pymupdf

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    # Step 1: Markdown conversion
    logger.info(f"Converting PDF to markdown: {file_path}")
    markdown = pymupdf4llm.to_markdown(file_path, show_progress=False)

    # Step 2: Metadata
    doc = pymupdf.open(file_path)
    metadata = {
        'page_count': len(doc),
        'title': doc.metadata.get('title', ''),
        'author': doc.metadata.get('author', ''),
        'creation_date': doc.metadata.get('creationDate', ''),
        'file_size_bytes': os.path.getsize(file_path),
    }
    page_count = len(doc)
    doc.close()

    # Step 3: Table extraction via pdfplumber
    tables = _extract_tables(file_path)

    # Step 4: Section chunking
    sections = _chunk_by_section(markdown)

    # Step 5: Isolate definitions section
    definitions_text = _find_definitions(sections, markdown)

    return ParsedDocument(
        markdown=markdown,
        sections=sections,
        tables=tables,
        metadata=metadata,
        definitions_text=definitions_text,
        page_count=page_count,
    )


def _extract_tables(file_path: str) -> list[ExtractedTable]:
    """Extract tables from PDF using pdfplumber."""
    import pdfplumber

    tables = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                for tbl in page_tables:
                    if not tbl or len(tbl) < 2:
                        continue
                    # First row as headers, rest as data
                    headers = [str(c or '').strip() for c in tbl[0]]
                    rows = []
                    for row in tbl[1:]:
                        rows.append([str(c or '').strip() for c in row])
                    if any(h for h in headers):  # Skip tables with empty headers
                        tables.append(ExtractedTable(
                            page=i + 1,
                            headers=headers,
                            rows=rows,
                        ))
    except Exception as e:
        logger.warning(f"pdfplumber table extraction failed: {e}")

    return tables


def _chunk_by_section(markdown: str) -> dict[str, str]:
    """Split markdown into sections by header hierarchy.

    Legal documents typically use patterns like:
      # ARTICLE I — DEFINITIONS
      ## Section 1.01 — Defined Terms
      # SCHEDULE A — ELIGIBILITY CRITERIA

    Returns dict: normalized_key → section_content
    """
    sections = {}
    current_key = 'PREAMBLE'
    current_lines = []

    # Match markdown headers (# through ###) and common legal numbering
    header_pattern = re.compile(
        r'^(?:#{1,3}\s+)?'                        # Optional markdown # prefix
        r'(?:'
        r'(?:ARTICLE|SECTION|SCHEDULE|EXHIBIT|ANNEX|APPENDIX|PART)\s+'  # Legal keyword
        r'[IVXLCDM\d]+[\.\)]?\s*[\-—:.]?\s*'     # Numbering (Roman or Arabic)
        r'(.+)'                                    # Title text
        r'|'
        r'#{1,3}\s+(.+)'                          # Pure markdown header
        r')',
        re.IGNORECASE | re.MULTILINE,
    )

    for line in markdown.split('\n'):
        m = header_pattern.match(line.strip())
        if m:
            # Save previous section
            if current_lines:
                sections[current_key] = '\n'.join(current_lines).strip()
            title = (m.group(1) or m.group(2) or line).strip()
            current_key = _normalize_section_key(title)
            current_lines = [line]
        else:
            current_lines.append(line)

    # Save last section
    if current_lines:
        sections[current_key] = '\n'.join(current_lines).strip()

    return sections


def _normalize_section_key(title: str) -> str:
    """Normalize section title to a clean key."""
    # Remove numbering artifacts
    key = re.sub(r'^[IVXLCDM\d]+[\.\):\-—\s]+', '', title, flags=re.IGNORECASE)
    key = key.strip().upper()
    # Collapse whitespace
    key = re.sub(r'\s+', '_', key)
    # Remove non-alphanumeric except underscore
    key = re.sub(r'[^A-Z0-9_]', '', key)
    return key or 'UNNAMED'


def _find_definitions(sections: dict, full_markdown: str) -> str:
    """Find and return the definitions section content.

    This is critical — the definitions glossary is prepended to every
    subsequent extraction pass as context.
    """
    # Check section keys for definitions
    for key, content in sections.items():
        if 'DEFINITION' in key or 'DEFINED_TERM' in key:
            return content

    # Fallback: search for definitions header in full text
    patterns = [
        r'(?:ARTICLE\s+[I1][\s\-—:]+)?DEFINITION',
        r'DEFINED\s+TERMS',
        r'INTERPRETATION\s+AND\s+DEFINITION',
    ]
    for pat in patterns:
        match = re.search(pat, full_markdown, re.IGNORECASE)
        if match:
            # Return from match to the next article header or 15000 chars
            start = match.start()
            # Find next ARTICLE header
            next_article = re.search(
                r'\n#{1,3}\s*ARTICLE\s+[IVXLCDM\d]+',
                full_markdown[start + 100:],
                re.IGNORECASE,
            )
            end = start + 100 + next_article.start() if next_article else start + 15000
            return full_markdown[start:min(end, len(full_markdown))]

    return ""


# ── Caching Helpers ───────────────────────────────────────────────────────

def get_legal_dir(company: str, product: str) -> str:
    """Return the legal document directory for a company/product."""
    base = os.path.join('data', company, product, 'legal')
    os.makedirs(base, exist_ok=True)
    return base


def get_cache_path(file_path: str, suffix: str) -> str:
    """Return cache file path for a given PDF and suffix."""
    base = os.path.splitext(file_path)[0]
    return f"{base}_{suffix}"


def save_parsed_cache(file_path: str, parsed: ParsedDocument) -> None:
    """Save parsed markdown to cache file."""
    md_path = get_cache_path(file_path, 'markdown.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(parsed.markdown)
    logger.info(f"Saved markdown cache: {md_path}")


def load_extraction_cache(file_path: str) -> dict | None:
    """Load cached extraction result if it exists."""
    cache_path = get_cache_path(file_path, 'extracted.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_extraction_cache(file_path: str, result: dict) -> None:
    """Save extraction result to cache."""
    cache_path = get_cache_path(file_path, 'extracted.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)
    logger.info(f"Saved extraction cache: {cache_path}")


def list_legal_documents(company: str, product: str) -> list[dict]:
    """List all legal documents for a company/product."""
    legal_dir = get_legal_dir(company, product)
    docs = []
    for fname in sorted(os.listdir(legal_dir)):
        if not fname.lower().endswith('.pdf'):
            continue
        fpath = os.path.join(legal_dir, fname)
        cache = load_extraction_cache(fpath)
        docs.append({
            'filename': fname,
            'file_path': fpath,
            'file_size': os.path.getsize(fpath),
            'extracted': cache is not None,
            'extraction_status': 'completed' if cache else 'pending',
            'extracted_at': cache.get('extracted_at') if cache else None,
            'overall_confidence': cache.get('overall_confidence') if cache else None,
        })
    return docs
