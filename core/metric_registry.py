"""
Metric Registry — the bridge between compute functions and the Methodology page.

Every compute function decorated with @metric(...) is automatically registered here.
The get_methodology() function groups them into sections and returns structured JSON
that the frontend renders as the Methodology page.

This means: add @metric to a function → Methodology page updates automatically.
"""

import re
import functools
import logging

logger = logging.getLogger(__name__)

# Global registry — populated at import time by @metric decorators
METRIC_REGISTRY = []

# Static sections — for methodology content that has no compute function
STATIC_SECTIONS = []


def metric(
    section,
    title,
    level=None,
    tab=None,
    analysis_type='klaim',
    required_columns=None,
    optional_columns=None,
    denominator=None,
    confidence=None,
    order=0,
    metrics=None,
    tables=None,
    notes=None,
    prose=None,
    subsections=None,
):
    """Decorator that registers a compute function's methodology metadata.

    Usage:
        @metric(
            section='Collection Performance',
            title='Collection Velocity',
            level=2,
            tab='collection',
            analysis_type='klaim',
            required_columns=['Deal date', 'Purchase value', 'Collected till date'],
            denominator='total',
            confidence='A',
            order=3,
            metrics=[
                {'name': 'Collection Rate', 'formula': 'Collected / Purchase Value', 'rationale': '...'},
            ],
            notes=['Only uses completed deals for DSO calculation.'],
            prose='Collection velocity measures how fast capital returns...',
        )
        def compute_collection_velocity(df, mult, as_of_date=None):
            ...
    """
    def decorator(fn):
        meta = {
            'function': fn.__name__,
            'module': fn.__module__,
            'section': section,
            'title': title,
            'level': level,
            'tab': tab,
            'analysis_type': analysis_type,
            'required_columns': required_columns or [],
            'optional_columns': optional_columns or [],
            'denominator': denominator,
            'confidence': confidence,
            'order': order,
            'metrics': metrics or [],
            'tables': tables or [],
            'notes': notes or [],
            'prose': prose,
            'subsections': subsections or [],
        }
        fn._metric_meta = meta
        METRIC_REGISTRY.append(meta)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        wrapper._metric_meta = meta
        return wrapper
    return decorator


def register_static_section(
    section,
    title=None,
    level=None,
    analysis_type='klaim',
    order=0,
    metrics=None,
    tables=None,
    notes=None,
    prose=None,
    subsections=None,
):
    """Register a methodology section that has no compute function.

    Used for Currency Conversion, Product Types, Data Caveats, etc.
    """
    entry = {
        'function': None,
        'module': None,
        'section': section,
        'title': title or section,
        'level': level,
        'tab': None,
        'analysis_type': analysis_type,
        'required_columns': [],
        'optional_columns': [],
        'denominator': None,
        'confidence': None,
        'order': order,
        'metrics': metrics or [],
        'tables': tables or [],
        'notes': notes or [],
        'prose': prose,
        'subsections': subsections or [],
    }
    STATIC_SECTIONS.append(entry)


def _slugify(text):
    """Convert section title to URL-friendly ID."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def get_methodology(analysis_type):
    """Build structured methodology data for an analysis_type.

    Groups all registered functions by section, merges metrics/tables/notes
    from multiple functions in the same section, and returns ordered sections.

    Returns:
        {
            'analysis_type': 'klaim',
            'sections': [
                {
                    'id': 'portfolio-overview',
                    'title': 'Portfolio Overview Metrics',
                    'level': 1,
                    'order': 1,
                    'prose': '...',
                    'metrics': [...],
                    'tables': [...],
                    'notes': [...],
                    'subsections': [...]
                },
                ...
            ]
        }
    """
    # Collect entries matching this analysis_type (or 'both')
    all_entries = METRIC_REGISTRY + STATIC_SECTIONS
    entries = [
        e for e in all_entries
        if e['analysis_type'] in (analysis_type, 'both')
    ]

    if not entries:
        return {'analysis_type': analysis_type, 'sections': []}

    # Group by section name
    sections_map = {}
    for entry in entries:
        sec_name = entry['section']
        if sec_name not in sections_map:
            sections_map[sec_name] = {
                'id': _slugify(sec_name),
                'title': sec_name,
                'level': entry['level'],
                'order': entry['order'],
                'prose': None,
                'metrics': [],
                'tables': [],
                'notes': [],
                'subsections': [],
            }

        sec = sections_map[sec_name]
        # Use the first non-None level and lowest order
        if sec['level'] is None and entry['level'] is not None:
            sec['level'] = entry['level']
        if entry['order'] < sec['order']:
            sec['order'] = entry['order']
        # Merge prose (first one wins)
        if entry['prose'] and not sec['prose']:
            sec['prose'] = entry['prose']
        # Merge content lists
        sec['metrics'].extend(entry['metrics'])
        sec['tables'].extend(entry['tables'])
        sec['notes'].extend(entry['notes'])
        sec['subsections'].extend(entry['subsections'])

    # Sort by order, then alphabetically
    sections = sorted(sections_map.values(), key=lambda s: (s['order'], s['title']))

    return {'analysis_type': analysis_type, 'sections': sections}


def get_registry():
    """Return the raw function registry for auditing and Section 12 generation.

    Returns:
        {
            'klaim': [{'function': 'compute_summary', 'level': 1, ...}, ...],
            'silq': [...],
            ...
        }
    """
    result = {}
    for entry in METRIC_REGISTRY:
        at = entry['analysis_type']
        if at == 'both':
            for t in ('klaim', 'silq'):
                result.setdefault(t, []).append(entry)
        else:
            result.setdefault(at, []).append(entry)
    return result
