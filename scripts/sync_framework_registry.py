#!/usr/bin/env python3
"""
Auto-generate ANALYSIS_FRAMEWORK.md Section 12 (Compute Function Registry)
from the METRIC_REGISTRY.

Usage:
    python scripts/sync_framework_registry.py

This replaces the manually-maintained tables in Section 12 with tables
generated from the actual registered methodology metadata.
"""
import os
import sys
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import and register
from core.metric_registry import METRIC_REGISTRY, get_registry
from core.methodology_klaim import register_klaim_methodology
from core.methodology_silq import register_silq_methodology

register_klaim_methodology()
register_silq_methodology()


def generate_section_12():
    """Generate markdown for Section 12 from the registry."""
    registry = get_registry()
    lines = []
    lines.append("## 12. Compute Function Registry\n")
    lines.append("This section is **auto-generated** from the metric registry. Run `python scripts/sync_framework_registry.py` to update.\n")

    for analysis_type in ['klaim', 'silq']:
        entries = registry.get(analysis_type, [])
        if not entries:
            continue

        label = {'klaim': 'Klaim', 'silq': 'SILQ'}.get(analysis_type, analysis_type)
        lines.append(f"\n### {label}\n")
        lines.append("| Section | Level | Tab | Denominator | Confidence | Required Columns |")
        lines.append("|---------|-------|-----|-------------|------------|------------------|")

        seen_sections = set()
        for entry in sorted(entries, key=lambda e: e.get('order', 999)):
            sec = entry.get('section', '?')
            if sec in seen_sections:
                continue
            seen_sections.add(sec)
            level = f"L{entry['level']}" if entry.get('level') else '--'
            tab = entry.get('tab', '--') or '--'
            denom = entry.get('denominator', '--') or '--'
            conf = entry.get('confidence', '--') or '--'
            cols = ', '.join(entry.get('required_columns', [])[:4])
            if len(entry.get('required_columns', [])) > 4:
                cols += ', ...'
            lines.append(f"| {sec} | {level} | {tab} | {denom} | {conf} | {cols} |")

    return '\n'.join(lines) + '\n'


def update_framework_md():
    """Replace Section 12 in ANALYSIS_FRAMEWORK.md."""
    framework_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'core', 'ANALYSIS_FRAMEWORK.md'
    )

    with open(framework_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find Section 12 and Section 13 boundaries
    pattern = r'(## 12\. Compute Function Registry.*?)(## 13\.)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("ERROR: Could not find Section 12 boundaries in ANALYSIS_FRAMEWORK.md")
        print("Make sure '## 12. Compute Function Registry' and '## 13.' exist.")
        sys.exit(1)

    new_section = generate_section_12() + '\n---\n\n'
    new_content = content[:match.start(1)] + new_section + content[match.start(2):]

    with open(framework_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Updated Section 12 in {framework_path}")
    print(f"  Klaim: {len([e for e in METRIC_REGISTRY if e.get('analysis_type') == 'klaim'])} entries")
    print(f"  SILQ:  {len([e for e in METRIC_REGISTRY if e.get('analysis_type') == 'silq'])} entries")


if __name__ == '__main__':
    update_framework_md()
