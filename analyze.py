import os
from core.loader import (
    select_company, select_product, get_snapshots,
    load_snapshot, select_snapshot
)
from core.consistency import run_consistency_check, print_consistency_report
from core.reporter import run_and_save_report

EXCHANGE_RATES = {
    'USD': 1.0,
    'AED': 0.2723,
    'EUR': 1.08,
    'GBP': 1.27,
    'SAR': 0.2667,
    'KWD': 3.26,
}

def select_currency():
    currencies = list(EXCHANGE_RATES.keys())
    print("\n=== CURRENCY SETTINGS ===")
    for i, c in enumerate(currencies, 1):
        print(f"  {i}. {c}")
    
    while True:
        try:
            choice = int(input("\nWhat is the reported currency of this data? Enter number: "))
            if 1 <= choice <= len(currencies):
                reported = currencies[choice - 1]
                break
        except ValueError:
            pass
        print("Please enter a valid number")
    
    convert = False
    if reported != 'USD':
        ans = input(f"Data is in {reported}. Convert to USD as well? (yes/no): ").strip().lower()
        convert = ans in ['yes', 'y']
    
    return reported, convert

def format_currency(value, currency, convert=False, rate=1.0):
    symbols = {'USD': '$', 'AED': 'AED ', 'EUR': '€', 'GBP': '£', 'SAR': 'SAR ', 'KWD': 'KWD '}
    symbol = symbols.get(currency, currency + ' ')
    result = f"{symbol}{value:,.2f}"
    if convert and currency != 'USD':
        result += f"   |   ${value * rate:,.2f} USD"
    return result

# ── MAIN FLOW ────────────────────────────────────────────────

# Step 1: Select company
company = select_company()
if not company:
    exit()

# Step 2: Select product
product = select_product(company)
if not product:
    exit()

# Step 3: Get all snapshots
snapshots = get_snapshots(company, product)

# Step 4: Consistency checks
all_checks = []
all_passed = True

if len(snapshots) > 1:
    print(f"\n{len(snapshots)} snapshots found for {company.upper()} / {product.upper()}")
    print("Running consistency checks across all snapshots...")
    
    for i in range(1, len(snapshots)):
        old_snap = snapshots[i-1]
        new_snap = snapshots[i]
        
        old_df = load_snapshot(old_snap['filepath'])
        new_df = load_snapshot(new_snap['filepath'])
        
        report = run_consistency_check(
            old_df, new_df,
            old_snap['date'] or old_snap['filename'],
            new_snap['date'] or new_snap['filename']
        )
        
        print_consistency_report(
            report,
            old_snap['date'] or old_snap['filename'],
            new_snap['date'] or new_snap['filename']
        )
        
        all_checks.append({
            'old_label': old_snap['date'] or old_snap['filename'],
            'new_label': new_snap['date'] or new_snap['filename'],
            'report': report
        })
        
        if not report['passed']:
            all_passed = False
    
    # Step 5: Generate AI report if there are any findings
    has_warnings = any(
        len(c['report']['warnings']) > 0 or len(c['report']['issues']) > 0 
        for c in all_checks
    )
    
    if has_warnings:
        generate = input("\nGenerate AI data integrity report? (yes/no): ").strip().lower()
        if generate in ['yes', 'y']:
            run_and_save_report(company, product, all_checks)
    
    if not all_passed:
        proceed = input("\nCritical issues found. Proceed to analysis anyway? (yes/no): ").strip().lower()
        if proceed not in ['yes', 'y']:
            exit()

# Step 6: Select snapshot to analyze
selected = select_snapshot(company, product)
if not selected:
    exit()

df = load_snapshot(selected['filepath'])

# Step 7: Currency
reported_currency, convert_to_usd = select_currency()
rate = EXCHANGE_RATES.get(reported_currency, 1.0)

# Step 8: Financial summary
financial_cols = [
    'Purchase value', 'Purchase price', 'Gross revenue',
    'Paid by insurance', 'Denied by insurance',
    'Pending insurance response', 'Collected till date'
]

print(f"\n{'='*60}")
print(f"PORTFOLIO OVERVIEW — {company.upper()} / {product.upper()}")
print(f"Snapshot: {selected['date'] or selected['filename']}")
print(f"Currency: {reported_currency}")
print(f"{'='*60}")
print(f"Total deals:     {len(df):,}")

print(f"\n=== DEAL STATUS ===")
print(df['Status'].value_counts().to_string())

print(f"\n=== FINANCIAL SUMMARY ===")
for col in financial_cols:
    if col in df.columns:
        val = df[col].sum()
        print(f"  {col:<35} {format_currency(val, reported_currency, convert_to_usd, rate)}")

total_purchase = df['Purchase value'].sum()
total_collected = df['Collected till date'].sum()
total_denied = df['Denied by insurance'].sum()
total_pending = df['Pending insurance response'].sum()

print(f"\n=== KEY RATIOS ===")
print(f"  Collection rate:     {(total_collected / total_purchase * 100):.2f}%")
print(f"  Denial rate:         {(total_denied / total_purchase * 100):.2f}%")
print(f"  Pending exposure:    {(total_pending / total_purchase * 100):.2f}%")