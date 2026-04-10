"""
Data Room Ingestion Engine for the Laith Credit Platform.

Provides generalized document ingestion, parsing, classification, chunking,
and search capabilities for private credit data rooms. Replaces per-company
ETL scripts with a unified engine.

Usage:
    from core.dataroom import DataRoomEngine, DocumentType, classify_document

    engine = DataRoomEngine()
    result = engine.ingest("Tamara", "KSA", "/path/to/data/room")
    docs = engine.catalog("Tamara", "KSA")
    hits = engine.search("Tamara", "KSA", "covenant compliance")
"""

from .engine import DataRoomEngine
from .classifier import DocumentType, classify_document
from .chunker import chunk_document
from .parsers import get_parser, PARSER_REGISTRY
from .parsers.base import ParseResult, BaseParser

__all__ = [
    "DataRoomEngine",
    "DocumentType",
    "classify_document",
    "chunk_document",
    "get_parser",
    "PARSER_REGISTRY",
    "ParseResult",
    "BaseParser",
]
