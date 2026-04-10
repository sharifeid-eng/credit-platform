"""
JSON file parser for the data room engine.

Handles structured JSON data files (e.g., Tamara data room snapshots).
Extracts text representation from nested JSON for chunking and search.
"""

import json
from pathlib import Path
from .base import BaseParser, ParseResult


class JsonParser(BaseParser):
    """Parse JSON data files into text + tables for the data room."""

    extensions = [".json"]

    def parse(self, filepath: str) -> ParseResult:
        """Extract text representation from a JSON file.

        Walks the JSON structure and produces a human-readable text
        representation suitable for chunking and search.
        """
        path = Path(filepath)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return ParseResult(text="", error=f"JSON parse error: {e}")

        text_parts = []
        tables = []

        if isinstance(data, dict):
            text_parts.append(f"JSON Data File: {path.name}")
            text_parts.append(f"Top-level keys: {', '.join(data.keys())}")
            text_parts.append("")

            for key, value in data.items():
                section_text = self._render_section(key, value)
                if section_text:
                    text_parts.append(section_text)

                # Extract table-like structures (list of dicts)
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    headers = list(value[0].keys())
                    rows = [[str(item.get(h, "")) for h in headers] for item in value[:50]]
                    tables.append({
                        "sheet": key,
                        "headers": headers,
                        "rows": rows,
                    })

        elif isinstance(data, list):
            text_parts.append(f"JSON Array: {path.name} ({len(data)} items)")
            if data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [[str(item.get(h, "")) for h in headers] for item in data[:50]]
                tables.append({"headers": headers, "rows": rows})

        text = "\n".join(text_parts)

        return ParseResult(
            text=text,
            tables=tables,
            metadata={
                "format": "json",
                "top_level_type": type(data).__name__,
                "key_count": len(data) if isinstance(data, dict) else len(data) if isinstance(data, list) else 1,
            },
            page_count=0,
        )

    def _render_section(self, key: str, value, depth: int = 0, max_depth: int = 3) -> str:
        """Render a JSON section as readable text."""
        indent = "  " * depth
        parts = []

        if depth > max_depth:
            parts.append(f"{indent}{key}: [nested data]")
            return "\n".join(parts)

        if isinstance(value, dict):
            parts.append(f"{indent}## {key.replace('_', ' ').title()}")
            for k, v in value.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    parts.append(f"{indent}  {k}: {v}")
                elif isinstance(v, dict):
                    sub = self._render_section(k, v, depth + 1, max_depth)
                    if sub:
                        parts.append(sub)
                elif isinstance(v, list):
                    if v and isinstance(v[0], dict):
                        parts.append(f"{indent}  {k}: [{len(v)} records]")
                        # Show first 3 items
                        for item in v[:3]:
                            summary = ", ".join(f"{ik}={iv}" for ik, iv in list(item.items())[:5])
                            parts.append(f"{indent}    - {summary}")
                    else:
                        parts.append(f"{indent}  {k}: {v[:5]}{'...' if len(v) > 5 else ''}")

        elif isinstance(value, list):
            parts.append(f"{indent}## {key.replace('_', ' ').title()} ({len(value)} items)")
            if value and isinstance(value[0], dict):
                for item in value[:3]:
                    summary = ", ".join(f"{ik}={iv}" for ik, iv in list(item.items())[:5])
                    parts.append(f"{indent}  - {summary}")
                if len(value) > 3:
                    parts.append(f"{indent}  ... and {len(value) - 3} more")
            elif value:
                parts.append(f"{indent}  {value[:10]}")

        elif isinstance(value, (str, int, float, bool)) or value is None:
            parts.append(f"{indent}{key}: {value}")

        return "\n".join(parts)
