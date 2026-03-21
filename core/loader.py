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
            if os.path.isdir(os.path.join(DATA_DIR, d))]

def get_products(company):
    """Return list of products for a company, read dynamically from subfolders"""
    company_path = os.path.join(DATA_DIR, company)
    return [d for d in os.listdir(company_path)
            if os.path.isdir(os.path.join(company_path, d))]

def get_snapshots(company, product):
    """Return all data files for a company/product, sorted by date"""
    product_path = os.path.join(DATA_DIR, company, product)
    snapshots = []
    
    for file in os.listdir(product_path):
        if file.endswith('.csv') or file.endswith('.xlsx'):
            filepath = os.path.join(product_path, file)
            snapshots.append({
                'filename': file,
                'filepath': filepath,
                'date': extract_date_from_filename(file)
            })
    
    snapshots.sort(key=lambda x: x['date'] or '0000-00-00')
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
        # For multi-sheet Excel files, pick the largest sheet (most data rows)
        xls = pd.ExcelFile(filepath)
        best_sheet = None
        if len(xls.sheet_names) > 1:
            best_sheet, best_rows = xls.sheet_names[0], -1
            for sn in xls.sheet_names:
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
        df['Deal date'] = pd.to_datetime(df['Deal date'], errors='coerce')
    if 'Disbursement_Date' in df.columns:
        df['Disbursement_Date'] = pd.to_datetime(df['Disbursement_Date'], errors='coerce')
    if 'Repayment_Deadline' in df.columns:
        df['Repayment_Deadline'] = pd.to_datetime(df['Repayment_Deadline'], errors='coerce')
    if 'Last_Collection_Date' in df.columns:
        df['Last_Collection_Date'] = pd.to_datetime(df['Last_Collection_Date'], errors='coerce')

    return df

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