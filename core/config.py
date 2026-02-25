import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

SUPPORTED_CURRENCIES = {
    'AED': 0.2723,
    'USD': 1.0,
    'EUR': 1.08,
    'GBP': 1.27,
    'SAR': 0.2667,
    'KWD': 3.26,
}

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