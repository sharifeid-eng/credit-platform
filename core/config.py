import os
import json
import time
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Fallback rates (used when live API is unavailable)
FALLBACK_RATES = {
    'AED': 0.2723,
    'USD': 1.0,
    'EUR': 1.08,
    'GBP': 1.27,
    'SAR': 0.2667,
    'KWD': 3.26,
}

# Live FX cache: {rates: {...}, fetched_at: timestamp, source: 'live'|'fallback'}
_fx_cache = {'rates': None, 'fetched_at': 0, 'source': 'fallback'}
_FX_CACHE_TTL = 3600  # 1 hour


def _fetch_live_rates():
    """Fetch live FX rates from exchangerate-api.com (free, no key required).
    Returns dict of {currency: usd_rate} or None on failure."""
    import urllib.request
    try:
        url = 'https://open.er-api.com/v6/latest/USD'
        req = urllib.request.Request(url, headers={'User-Agent': 'Laith/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get('result') != 'success':
            return None
        usd_rates = data['rates']
        # Convert: we need "1 LOCAL = X USD", API gives "1 USD = X LOCAL"
        live = {}
        for code in FALLBACK_RATES:
            if code == 'USD':
                live['USD'] = 1.0
            elif code in usd_rates and usd_rates[code] > 0:
                live[code] = round(1.0 / usd_rates[code], 6)
        logger.info(f"Live FX rates fetched: {live}")
        return live
    except Exception as e:
        logger.warning(f"Live FX fetch failed: {e}")
        return None


def get_fx_rates():
    """Return current FX rates (live with fallback).
    Caches for 1 hour to avoid excessive API calls."""
    global _fx_cache
    now = time.time()
    if _fx_cache['rates'] and (now - _fx_cache['fetched_at']) < _FX_CACHE_TTL:
        return _fx_cache['rates']

    live = _fetch_live_rates()
    if live:
        _fx_cache = {'rates': live, 'fetched_at': now, 'source': 'live'}
        return live

    # Fallback
    _fx_cache = {'rates': dict(FALLBACK_RATES), 'fetched_at': now, 'source': 'fallback'}
    return dict(FALLBACK_RATES)


def get_fx_source():
    """Return 'live' or 'fallback' indicating current rate source."""
    return _fx_cache.get('source', 'fallback')


# SUPPORTED_CURRENCIES is now dynamic — callers should use get_fx_rates()
# Keep as a property for backward compat (populated on first access)
SUPPORTED_CURRENCIES = FALLBACK_RATES.copy()

def get_config_path(company, product):
    return os.path.join(DATA_DIR, company, product, 'config.json')

def load_config(company, product):
    """Load config for a company/product, return defaults if not found"""
    config_path = get_config_path(company, product)
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return None

def save_config(company, product, config):
    """Save config for a company/product"""
    config_path = get_config_path(company, product)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

def is_new_product(company, product):
    """Check if this product has been configured before"""
    return load_config(company, product) is None

def setup_product(company, product):
    """Interactive setup for a new product"""
    print(f"\n=== NEW PRODUCT DETECTED: {company.upper()} / {product.upper()} ===")
    print("Please configure this product before proceeding.\n")

    # Currency selection
    currencies = list(SUPPORTED_CURRENCIES.keys())
    print("What is the reported currency for this product?")
    for i, c in enumerate(currencies, 1):
        print(f"  {i}. {c}")

    while True:
        try:
            choice = int(input("\nSelect currency number: "))
            if 1 <= choice <= len(currencies):
                currency = currencies[choice - 1]
                break
        except ValueError:
            pass
        print("Please enter a valid number")

    # Product description
    description = input(f"\nBrief description of this product (e.g. 'Medical claims factoring'): ").strip()

    config = {
        'currency': currency,
        'description': description,
        'company': company,
        'product': product,
        'usd_rate': SUPPORTED_CURRENCIES[currency]
    }

    save_config(company, product, config)
    print(f"\n✓ Config saved. Reported currency set to {currency}.")
    return config

def get_or_create_config(company, product):
    """Get existing config or run setup for new product"""
    config = load_config(company, product)
    if config is None:
        config = setup_product(company, product)
    return config