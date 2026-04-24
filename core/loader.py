import pandas as pd
import os
from datetime import datetime

# Resolve data directory relative to project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # this is the core/ folder
BASE_DIR = os.path.dirname(BASE_DIR)  # go up one level to credit-platform/
DATA_DIR = os.path.join(BASE_DIR, "data")

def get_companies():
    """Return list of companies that have data folders"""
    if not os.path.exists(DATA_DIR):
        print(f"Data directory not found: {DATA_DIR}")
        return []
    return [d for d in os.listdir(DATA_DIR)
            if os.path.isdir(os.path.join(DATA_DIR, d)) and not d.startswith('_')]

def get_products(company):
    """Return list of products for a company, read dynamically from subfolders"""
    company_path = os.path.join(DATA_DIR, company)
    _NON_PRODUCT_DIRS = {'dataroom', '_master_mind', 'mind', 'legal', '__pycache__', 'investor_packs'}
    return [d for d in os.listdir(company_path)
            if os.path.isdir(os.path.join(company_path, d)) and d not in _NON_PRODUCT_DIRS]

def get_snapshots(company, product):
    """Return all data files for a company/product, sorted by date"""
    product_path = os.path.join(DATA_DIR, company, product)
    snapshots = []
    
    # Known non-data files to exclude from snapshot discovery
    _EXCLUDE = {'config.json', 'methodology.json', 'covenant_history.json',
                 'facility_params.json', 'debtor_validation.json'}
    for file in os.listdir(product_path):
        if file in _EXCLUDE:
            continue
        if file.endswith('.csv') or file.endswith('.xlsx') or file.endswith('.ods') or file.endswith('.json'):
            filepath = os.path.join(product_path, file)
            snapshots.append({
                'filename': file,
                'filepath': filepath,
                'date': extract_date_from_filename(file)
            })
    
    snapshots.sort(key=lambda x: (x['date'] or '0000-00-00', x['filename']))
    return snapshots

def extract_date_from_filename(filename):
    """Extract date from filename like 2026-02-20_klaim_dealsheet.csv"""
    parts = filename.split('_')
    if parts:
        date_str = parts[0]
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            return None
    return None

def load_snapshot(filepath):
    """Load a single snapshot file into a dataframe.

    Handles malformed Excel files where the first row contains summary totals
    instead of headers (detected by checking if column names are numeric).
    """
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        # For multi-sheet Excel files, prefer well-known data sheet names,
        # then fall back to the largest sheet by row count.
        xls = pd.ExcelFile(filepath)
        best_sheet = None
        _PREFERRED_NAMES = {'data', 'sheet1', 'deals', 'loan tape', 'portfolio'}
        _SKIP_NAMES = {'summary', 'glossary', 'notes', 'instructions', 'metadata', 'readme'}
        if len(xls.sheet_names) > 1:
            # First: try preferred names
            for sn in xls.sheet_names:
                if sn.lower().strip() in _PREFERRED_NAMES:
                    best_sheet = sn
                    break
            # Second: largest non-skip sheet
            if not best_sheet:
                best_sheet, best_rows = xls.sheet_names[0], -1
                for sn in xls.sheet_names:
                    if sn.lower().strip() in _SKIP_NAMES:
                        continue
                    nrows = pd.read_excel(xls, sheet_name=sn).shape[0]
                    if nrows > best_rows:
                        best_sheet, best_rows = sn, nrows
        sheet = best_sheet or xls.sheet_names[0]
        df = pd.read_excel(filepath, sheet_name=sheet)
        # Detect malformed headers: if most column names are numeric (not strings),
        # the real headers are in the first data row
        named_cols = sum(1 for c in df.columns
                         if isinstance(c, str) and not c.startswith('Unnamed'))
        if named_cols == 0 and len(df) > 0:
            # First row likely contains real headers — reload with header=1
            df = pd.read_excel(filepath, sheet_name=sheet, header=1)

    df.columns = df.columns.str.strip()

    # Parse date columns if they exist (column-agnostic)
    if 'Deal date' in df.columns:
        df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce', format='mixed')
    if 'Disbursement_Date' in df.columns:
        df['Disbursement_Date'] = pd.to_datetime(df['Disbursement_Date'], errors='coerce')
    if 'Repayment_Deadline' in df.columns:
        df['Repayment_Deadline'] = pd.to_datetime(df['Repayment_Deadline'], errors='coerce')
    if 'Last_Collection_Date' in df.columns:
        df['Last_Collection_Date'] = pd.to_datetime(df['Last_Collection_Date'], errors='coerce')

    return df


def load_silq_snapshot(filepath):
    """Load a SILQ snapshot that may contain multiple data sheets.

    Returns (combined_df, commentary_text).
    - Reads all data sheets (skips 'Portfolio Commentary')
    - Normalises Loan_Type → Product, fills missing Margin Collected with 0
    - Casts Shop_ID to string, normalises Loan_Status to title case
    - Extracts portfolio commentary text if sheet exists
    """
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        for col in ('Disbursement_Date', 'Repayment_Deadline',
                     'Last_Collection_Date'):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        return df, None

    xls = pd.ExcelFile(filepath)
    commentary_text = None
    data_frames = []

    for sn in xls.sheet_names:
        # Commentary sheet → extract text
        if 'commentary' in sn.lower():
            try:
                cdf = pd.read_excel(xls, sheet_name=sn)
                if len(cdf) > 0:
                    commentary_text = str(cdf.iloc[0, 0])
            except Exception:
                pass
            continue

        # Data sheet
        df = pd.read_excel(xls, sheet_name=sn)
        # Malformed header detection (summary-row-as-header):
        # Check if columns are mostly numeric or Unnamed — if so, real headers
        # are in the first data row. Also catch pandas-deduped numeric strings
        # like '181335085.67000005.1'.
        def _is_real_header(c):
            if not isinstance(c, str):
                return False
            if c.startswith('Unnamed'):
                return False
            # Numeric-looking strings (possibly with .N suffix from pandas dedup)
            try:
                float(c.replace('.1', '').replace('.2', ''))
                return False
            except ValueError:
                return True
        real_named = sum(1 for c in df.columns if _is_real_header(c))
        if real_named == 0 and len(df) > 0:
            df = pd.read_excel(xls, sheet_name=sn, header=1)

        # Drop unnamed index columns
        df = df.drop(columns=[c for c in df.columns
                               if str(c).startswith('Unnamed')], errors='ignore')
        df.columns = df.columns.str.strip()

        # Skip tiny/empty sheets
        if len(df) < 2:
            continue

        # Normalise product column: Loan_Type → Product
        if 'Loan_Type' in df.columns and 'Product' not in df.columns:
            df = df.rename(columns={'Loan_Type': 'Product'})

        # Fill missing columns that exist in other sheets
        if 'Margin Collected' not in df.columns:
            df['Margin Collected'] = 0.0
            df['_margin_synthetic'] = True
        else:
            df['_margin_synthetic'] = False
        if 'Comment' not in df.columns:
            df['Comment'] = ''

        # Source sheet metadata
        df['_source_sheet'] = sn

        data_frames.append(df)

    if not data_frames:
        raise ValueError(f"No data sheets found in {filepath}")

    combined = pd.concat(data_frames, ignore_index=True)

    # Normalise Shop_ID to string (BNPL=numeric, RBF=text codes)
    if 'Shop_ID' in combined.columns:
        combined['Shop_ID'] = combined['Shop_ID'].astype(str)

    # Normalise Loan_Status to title case (CURRENT → Current, OVERDUE → Overdue)
    if 'Loan_Status' in combined.columns:
        combined['Loan_Status'] = (combined['Loan_Status']
                                   .astype(str).str.strip().str.title())

    # Parse date columns
    for col in ('Disbursement_Date', 'Repayment_Deadline',
                 'Last_Collection_Date'):
        if col in combined.columns:
            combined[col] = pd.to_datetime(combined[col], errors='coerce')

    return combined, commentary_text


def load_aajil_snapshot(filepath):
    """Load an Aajil multi-sheet tape.

    Returns (deals_df, aux_data) where aux_data is a dict with:
        'dpd_cohorts': DataFrame from 'Current_DPD_New Cohorts' sheet
        'collections': DataFrame from 'Collections' sheet
        'payments': DataFrame from 'Payments' sheet (if needed)
    """
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning)

    xls = pd.ExcelFile(filepath)

    # ── Deals sheet (primary) ────────────────────────────────────────
    deals = pd.read_excel(xls, sheet_name='Deals')
    deals.columns = deals.columns.str.strip()
    # Drop empty unnamed columns
    deals = deals[[c for c in deals.columns if not c.startswith('Unnamed')]]
    # Parse dates
    for col in ('Invoice Date', 'Expected Completion', 'Write Off Date'):
        if col in deals.columns:
            deals[col] = pd.to_datetime(deals[col], errors='coerce')
    # Drop fully-null rows (last 2 rows may be empty)
    deals = deals.dropna(subset=['Transaction ID'])

    aux = {}

    # ── Current_DPD_New Cohorts sheet ────────────────────────────────
    try:
        dpd = pd.read_excel(xls, sheet_name='Current_DPD_New Cohorts', header=None)
        aux['dpd_cohorts'] = dpd
    except Exception:
        aux['dpd_cohorts'] = None

    # ── Collections sheet ────────────────────────────────────────────
    try:
        coll = pd.read_excel(xls, sheet_name='Collections', header=None)
        aux['collections'] = coll
    except Exception:
        aux['collections'] = None

    # ── Payments sheet (instalment-level) ────────────────────────────
    try:
        pay = pd.read_excel(xls, sheet_name='Payments')
        pay.columns = pay.columns.str.strip()
        aux['payments'] = pay
    except Exception:
        aux['payments'] = None

    return deals, aux


def select_company():
    """Interactive prompt to select a company"""
    companies = get_companies()
    
    if not companies:
        print("No company data found in the data/ folder.")
        return None
    
    print("\n=== SELECT COMPANY ===")
    for i, company in enumerate(companies, 1):
        products = get_products(company)
        print(f"  {i}. {company.upper()} ({len(products)} product(s): {', '.join(products)})")
    
    while True:
        try:
            choice = int(input("\nSelect company number: "))
            if 1 <= choice <= len(companies):
                return companies[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(companies)}")
        except ValueError:
            print("Please enter a valid number")

def select_product(company):
    """Interactive prompt to select a product"""
    products = get_products(company)
    
    if not products:
        print(f"No products found for {company}")
        return None
    
    if len(products) == 1:
        print(f"\nOne product found: {products[0].upper()} — selecting automatically")
        return products[0]
    
    print(f"\n=== SELECT PRODUCT FOR {company.upper()} ===")
    for i, product in enumerate(products, 1):
        snapshots = get_snapshots(company, product)
        print(f"  {i}. {product.upper()} ({len(snapshots)} snapshot(s))")
    
    while True:
        try:
            choice = int(input("\nSelect product number: "))
            if 1 <= choice <= len(products):
                return products[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(products)}")
        except ValueError:
            print("Please enter a valid number")

def select_snapshot(company, product):
    """Interactive prompt to select which snapshot to analyze"""
    snapshots = get_snapshots(company, product)
    
    if not snapshots:
        print(f"No data files found for {company}/{product}")
        return None
    
    print(f"\n=== AVAILABLE SNAPSHOTS — {company.upper()} / {product.upper()} ===")
    for i, snap in enumerate(snapshots, 1):
        date_label = snap['date'] or 'unknown date'
        print(f"  {i}. {date_label}  —  {snap['filename']}")
    
    print(f"  {len(snapshots) + 1}. Use latest snapshot")
    
    while True:
        try:
            choice = int(input("\nSelect snapshot number: "))
            if choice == len(snapshots) + 1:
                selected = snapshots[-1]
            elif 1 <= choice <= len(snapshots):
                selected = snapshots[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(snapshots) + 1}")
                continue
            
            print(f"\nLoading: {selected['filename']}")
            return selected
        except ValueError:
            print("Please enter a valid number")