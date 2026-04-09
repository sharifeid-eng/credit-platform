#!/usr/bin/env python3
"""
Tamara Data Preparation Script
================================
Reads ~100 source files from the data room and produces structured JSON
snapshots for the Laith platform.

Output:
  data/Tamara/KSA/2026-04-09_tamara_ksa.json
  data/Tamara/UAE/2026-04-09_tamara_uae.json

Usage:
  python scripts/prepare_tamara_data.py
"""

import json
import os
import sys
import re
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore', category=UserWarning)

# ── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_OUT = PROJECT_ROOT / "data" / "Tamara"

# Data room root on OneDrive
DR = Path(r"C:\Users\SharifEid\OneDrive - Amwal Capital Partners\Resources\Private Credit\Tamara")
DR_NEW = DR / "New"
DR_ADD = DR_NEW / "Additional DD"


def _safe(v):
    """Convert numpy/pandas types to JSON-safe Python types."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 6)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()[:10]
    if isinstance(v, datetime):
        return v.isoformat()[:10]
    return v


def _clean_df_to_records(df):
    """Convert a DataFrame to a list of dicts with clean values."""
    records = []
    for _, row in df.iterrows():
        records.append({str(k): _safe(v) for k, v in row.items()})
    return records


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VINTAGE COHORT MATRICES (Default / Delinquency / Dilution)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_cohort_matrix(filepath):
    """Parse a vintage cohort matrix Excel file.
    These are triangular: rows = vintages, cols = reporting months.
    Returns list of {vintage, mob_1, mob_2, ...} dicts.
    """
    try:
        df = pd.read_excel(filepath, header=None)
    except Exception as e:
        print(f"  WARN: Could not read {filepath}: {e}")
        return []

    # Find the header row (contains month names or dates)
    header_row = None
    for i in range(min(5, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[i] if pd.notna(v)]
        # Look for month names or date patterns
        month_names = ['january', 'february', 'march', 'april', 'may', 'june',
                       'july', 'august', 'september', 'october', 'november', 'december']
        if any(m in ' '.join(row_vals).lower() for m in month_names):
            header_row = i
            break

    if header_row is None:
        # Try reading with default header
        df = pd.read_excel(filepath)
        if df.empty:
            return []
        # Attempt to use first row as header
        header_row = 0
        df = pd.read_excel(filepath, header=None)

    # Extract year row if present (row above months)
    year_row = None
    if header_row > 0:
        year_candidates = df.iloc[header_row - 1]
        years_found = [v for v in year_candidates if pd.notna(v) and
                       str(v).strip().isdigit() and len(str(int(float(str(v).strip())))) == 4]
        if years_found:
            year_row = header_row - 1

    # Build column headers (month-year)
    months_row = df.iloc[header_row]
    columns = []
    current_year = None

    for col_idx in range(len(months_row)):
        if year_row is not None and pd.notna(df.iloc[year_row, col_idx]):
            try:
                current_year = int(float(str(df.iloc[year_row, col_idx]).strip()))
            except (ValueError, TypeError):
                pass

        month_val = months_row.iloc[col_idx]
        if pd.isna(month_val) or str(month_val).strip() == '':
            columns.append(None)
            continue

        month_str = str(month_val).strip()
        # Try to parse as date
        if re.match(r'\d{4}-\d{2}', month_str):
            columns.append(month_str[:7])
        elif current_year:
            # Map month name to number
            month_map = {'january': '01', 'february': '02', 'march': '03', 'april': '04',
                         'may': '05', 'june': '06', 'july': '07', 'august': '08',
                         'september': '09', 'october': '10', 'november': '11', 'december': '12'}
            ml = month_str.lower()
            for name, num in month_map.items():
                if ml.startswith(name[:3]):
                    columns.append(f"{current_year}-{num}")
                    break
            else:
                columns.append(None)
        else:
            columns.append(None)

    # Find the vintage column (usually "Breakdown D1" or first column)
    vintage_col_idx = 0
    for i, c in enumerate(columns):
        if c is None and i == 0:
            vintage_col_idx = 0
            break

    # Extract data rows
    data_start = header_row + 1
    records = []
    for row_idx in range(data_start, len(df)):
        vintage_val = df.iloc[row_idx, vintage_col_idx]
        if pd.isna(vintage_val) or str(vintage_val).strip() == '':
            continue

        vintage_str = str(vintage_val).strip()
        # Try to parse as date
        if re.match(r'\d{4}-\d{2}-\d{2}', vintage_str):
            vintage_str = vintage_str[:7]  # YYYY-MM
        elif re.match(r'\d{4}-\d{2}', vintage_str):
            pass  # already YYYY-MM
        else:
            continue  # skip non-vintage rows

        record = {'vintage': vintage_str}
        for col_idx in range(len(columns)):
            if columns[col_idx] and col_idx != vintage_col_idx:
                val = df.iloc[row_idx, col_idx]
                if pd.notna(val):
                    try:
                        record[columns[col_idx]] = round(float(val), 6)
                    except (ValueError, TypeError):
                        pass

        if len(record) > 1:  # has at least one data point beyond vintage
            records.append(record)

    return records


def parse_all_cohort_matrices(country='KSA'):
    """Parse all cohort matrices for a country. Returns dict with keys: default, delinquency, dilution."""
    result = {'default': {}, 'delinquency': {}, 'dilution': {}}

    # 1. Portfolio-level matrices from 24-March folder
    march_dir = DR_ADD / "24-March"
    country_tag = 'KSA' if country == 'KSA' else 'UAE'

    for metric in ['Default', 'Delinquency', 'Dilution']:
        fname = f"{metric} - {country_tag} Portfolio.xlsx"
        fpath = march_dir / fname
        if fpath.exists():
            print(f"  Parsing {fname}...")
            records = _parse_cohort_matrix(fpath)
            result[metric.lower()]['portfolio'] = records

    # 2. Per-product breakdowns
    breakdown_dir = DR_ADD / "Portfolio Performance Breakdowns"
    if breakdown_dir.exists():
        for f in sorted(breakdown_dir.iterdir()):
            if not f.suffix == '.xlsx' or f.name == 'Portfolio Breakdowns.xlsx':
                continue
            fname = f.name

            # Determine metric, country, product
            metric_key = None
            for m in ['Default', 'Delinquency', 'Dilution']:
                if fname.startswith(m):
                    metric_key = m.lower()
                    break
            if not metric_key:
                continue

            # Check country
            if country == 'KSA' and 'KSA' not in fname and 'UAE' in fname:
                continue
            if country == 'UAE' and 'UAE' not in fname:
                continue
            if country == 'KSA' and 'UAE' in fname:
                continue

            # Extract product label
            product_label = fname.replace(f"{m} - ", '').replace('.xlsx', '').strip()
            product_label = product_label.replace(f'{country_tag} ', '')

            print(f"  Parsing {fname} -> {product_label}...")
            records = _parse_cohort_matrix(f)
            if records:
                result[metric_key][product_label] = records

    # 3. Updated matrices from Question 5 (Nov 2025 data)
    q5_dir = DR_ADD / "Question 5"
    if q5_dir.exists():
        for f in sorted(q5_dir.iterdir()):
            if not f.suffix == '.pdf':
                continue  # Q5 has PDFs, not Excel — skip for now, parsed separately

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DELOITTE FDD LOAN PORTFOLIO
# ═══════════════════════════════════════════════════════════════════════════════

def parse_deloitte_fdd(country='KSA'):
    """Parse the Deloitte FDD loan portfolio dataset (12,799 rows)."""
    fpath = DR_ADD / "Deloitte" / "Project Top - Deloitte FDD IRL (02.04.26).xlsx"
    if not fpath.exists():
        print(f"  WARN: Deloitte FDD not found at {fpath}")
        return {}

    print(f"  Parsing Deloitte FDD ({country})...")
    # Sheet names may be truncated — find the matching one
    xl = pd.ExcelFile(fpath)
    loan_sheet = next((s for s in xl.sheet_names if '59.1.13' in s or 'Loan portfoli' in s), None)
    if not loan_sheet:
        print(f"  WARN: Loan portfolio sheet not found. Available: {xl.sheet_names}")
        return {}
    df = pd.read_excel(fpath, sheet_name=loan_sheet)

    # Filter by country
    country_code = 'SA' if country == 'KSA' else 'AE'
    df = df[df['country_code'] == country_code].copy()

    # DPD distribution over time
    dpd_timeseries = []
    for date_val in sorted(df['evolution_date'].unique()):
        subset = df[df['evolution_date'] == date_val]
        total_pending = subset['pending_amount'].sum()
        if total_pending == 0:
            continue

        dpd_dist = {}
        for bucket in subset['dpd_bucket'].unique():
            bucket_amount = subset[subset['dpd_bucket'] == bucket]['pending_amount'].sum()
            dpd_dist[str(bucket)] = _safe(bucket_amount)

        dpd_timeseries.append({
            'date': _safe(date_val),
            'total_pending': _safe(total_pending),
            'total_written_off': _safe(subset['Written_Off_amount'].sum()),
            'dpd_distribution': dpd_dist
        })

    # By product type
    product_breakdown = []
    latest_date = df['evolution_date'].max()
    latest = df[df['evolution_date'] == latest_date]
    for prod in sorted(latest['si_product'].unique()):
        prod_data = latest[latest['si_product'] == prod]
        product_breakdown.append({
            'product': str(prod),
            'pending_amount': _safe(prod_data['pending_amount'].sum()),
            'written_off': _safe(prod_data['Written_Off_amount'].sum()),
            'writeoff_pct': _safe(prod_data['Written_Off_amount'].sum() / max(prod_data['pending_amount'].sum(), 1)),
        })

    # By customer type
    customer_breakdown = []
    for ctype in sorted(latest['customer_type'].unique()):
        ct_data = latest[latest['customer_type'] == ctype]
        customer_breakdown.append({
            'customer_type': 'Existing' if ctype == 'Exi' else 'New',
            'pending_amount': _safe(ct_data['pending_amount'].sum()),
            'written_off': _safe(ct_data['Written_Off_amount'].sum()),
        })

    # ECL provision movement
    ecl = []
    try:
        ecl_sheet = next((s for s in xl.sheet_names if '59.1.14' in s or 'Actual Losses' in s), None)
        if ecl_sheet:
            ecl_df = pd.read_excel(fpath, sheet_name=ecl_sheet)
        else:
            ecl_df = pd.DataFrame()
        for _, row in ecl_df.iterrows():
            ecl.append({str(k): _safe(v) for k, v in row.items()})
    except Exception:
        pass

    return {
        'dpd_timeseries': dpd_timeseries,
        'product_breakdown': product_breakdown,
        'customer_breakdown': customer_breakdown,
        'ecl_movement': ecl,
        'latest_date': _safe(latest_date),
        'total_rows': len(df),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INVESTOR MONTHLY REPORTING
# ═══════════════════════════════════════════════════════════════════════════════

def parse_investor_reporting(country='KSA'):
    """Parse the Investor Monthly Reporting workbook."""
    # Try Jan '26 first, then Dec '25
    for fname in ["Investor Monthly Reporting_Jan'26.xlsx", "Investor Monthly Reporting_Dec'25.xlsx"]:
        fpath = DR_ADD / "New Requests" / fname
        if fpath.exists():
            break
    else:
        # Try alternate location
        fpath = DR_ADD / "Question 4" / "Investor Monthly Reporting_Dec'25.xlsx"
        if not fpath.exists():
            print("  WARN: Investor reporting not found")
            return {}

    print(f"  Parsing {fpath.name} ({country})...")

    sheet_map = {
        'KSA': '1.2 KPIs KSA',
        'UAE': '1.3 KPIs UAE',
    }
    cons_sheet = '1.1 KPIs cons'

    result = {'kpis': [], 'financials': [], 'gmv_monthly': []}

    # Parse KPI sheet
    try:
        kpi_sheet = sheet_map.get(country, cons_sheet)
        df = pd.read_excel(fpath, sheet_name=kpi_sheet, header=None)

        # Extract rows as key-value pairs
        # These sheets have metric names in col 0 and monthly values across columns
        kpi_records = []
        for row_idx in range(min(100, len(df))):
            label = df.iloc[row_idx, 0]
            if pd.isna(label):
                continue
            label = str(label).strip()
            if not label or label.startswith('Unnamed'):
                continue

            values = {}
            for col_idx in range(1, min(28, df.shape[1])):
                val = df.iloc[row_idx, col_idx]
                if pd.notna(val):
                    values[f"col_{col_idx}"] = _safe(val)

            if values:
                kpi_records.append({'metric': label, 'values': values})

        result['kpis'] = kpi_records
    except Exception as e:
        print(f"  WARN: KPI parse error: {e}")

    # Parse financial statements
    try:
        fs_map = {'KSA': '2.2 FS KSA', 'UAE': '2.3 FS UAE'}
        fs_sheet = fs_map.get(country, '2.1 FS Cons')
        df = pd.read_excel(fpath, sheet_name=fs_sheet, header=None)

        fs_records = []
        for row_idx in range(min(200, len(df))):
            label = df.iloc[row_idx, 0]
            if pd.isna(label):
                continue
            label = str(label).strip()
            if not label or label.startswith('Unnamed'):
                continue

            values = {}
            for col_idx in range(1, min(33, df.shape[1])):
                val = df.iloc[row_idx, col_idx]
                if pd.notna(val):
                    values[f"col_{col_idx}"] = _safe(val)

            if values:
                fs_records.append({'line_item': label, 'values': values})

        result['financials'] = fs_records
    except Exception as e:
        print(f"  WARN: FS parse error: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PORTFOLIO DEMOGRAPHICS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_demographics(country='KSA'):
    """Parse the Portfolio Breakdowns workbook (demographics + Ever-90)."""
    fpath = DR_ADD / "Portfolio Performance Breakdowns" / "Portfolio Breakdowns.xlsx"
    if not fpath.exists():
        return {}

    print(f"  Parsing demographics ({country})...")
    df = pd.read_excel(fpath, sheet_name='Portfolio Demographics')

    country_code = 'SA' if country == 'KSA' else 'AE'
    result = {}

    # The dataset has columns: category_type, category_value, country, outstanding_ar, ever_90_rate
    # Parse by identifying dimension groups
    current_dimension = None
    dimension_data = []

    for _, row in df.iterrows():
        row_dict = {str(k): _safe(v) for k, v in row.items()}

        # Filter by country column
        country_val = None
        for k, v in row_dict.items():
            if v in ['SA', 'AE', country_code]:
                country_val = v
                break

        if country_val and country_val == country_code:
            dimension_data.append(row_dict)

    result['raw'] = dimension_data
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. FINANCIAL MASTER
# ═══════════════════════════════════════════════════════════════════════════════

def parse_financial_master():
    """Parse the Financial Master workbook for actuals through Nov 2025."""
    fpath = DR_NEW / "54.2 Financials" / "54.2.2 Management Financials" / \
            "2025-11-30_Financial Master (New Version) - VF.xlsx"
    if not fpath.exists():
        print("  WARN: Financial Master not found")
        return {}

    print("  Parsing Financial Master...")
    result = {}

    try:
        xl = pd.ExcelFile(fpath)
        # Read the summary/executive sheet
        for sheet_name in xl.sheet_names[:5]:
            df = pd.read_excel(fpath, sheet_name=sheet_name, header=None)
            records = []
            for row_idx in range(min(50, len(df))):
                label = df.iloc[row_idx, 0]
                if pd.isna(label):
                    continue
                label = str(label).strip()
                if not label:
                    continue
                values = {}
                for col_idx in range(1, min(20, df.shape[1])):
                    val = df.iloc[row_idx, col_idx]
                    if pd.notna(val):
                        values[f"col_{col_idx}"] = _safe(val)
                if values:
                    records.append({'metric': label, 'values': values})
            result[sheet_name] = records
    except Exception as e:
        print(f"  WARN: Financial Master parse error: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. BUSINESS PLAN
# ═══════════════════════════════════════════════════════════════════════════════

def parse_business_plan():
    """Parse the 5-year business plan projections."""
    fpath = DR_ADD / "New Requests" / "Tamara Business Plan FY26-FY30.xlsx"
    if not fpath.exists():
        # Try alternate location
        fpath = DR_NEW / "54.2 Financials" / "54.2.6 Business Plan" / \
                "54.2.6.1 Tamara - 5yr Business Plan (2025) - 11-9-25.xlsx"
        if not fpath.exists():
            print("  WARN: Business Plan not found")
            return {}

    print(f"  Parsing Business Plan ({fpath.name})...")
    result = {}

    try:
        xl = pd.ExcelFile(fpath)
        # Read Summary sheet
        if 'Summary' in xl.sheet_names:
            df = pd.read_excel(fpath, sheet_name='Summary', header=None)
            records = []
            for row_idx in range(min(80, len(df))):
                label = df.iloc[row_idx, 0]
                if pd.isna(label):
                    continue
                label = str(label).strip()
                if not label:
                    continue
                values = {}
                for col_idx in range(1, min(30, df.shape[1])):
                    val = df.iloc[row_idx, col_idx]
                    if pd.notna(val):
                        values[f"col_{col_idx}"] = _safe(val)
                if values:
                    records.append({'metric': label, 'values': values})
            result['summary'] = records
    except Exception as e:
        print(f"  WARN: Business Plan parse error: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 7. HSBC INVESTOR REPORTS (PDF)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_hsbc_report(filepath):
    """Parse a single HSBC investor report PDF."""
    try:
        import pdfplumber
    except ImportError:
        print("  WARN: pdfplumber not installed — skipping PDF parsing")
        return {}

    print(f"  Parsing {Path(filepath).name}...")
    result = {
        'bb_test': {},
        'triggers': [],
        'concentration_limits': [],
        'stratifications': {},
        'tranches': [],
        'waterfall': [],
        'reserves': {},
    }

    try:
        with pdfplumber.open(filepath) as pdf:
            all_tables = []
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        all_tables.append(table)

            # Process tables based on content patterns
            for table in all_tables:
                if not table or not table[0]:
                    continue

                header = [str(c).strip() if c else '' for c in table[0]]
                header_text = ' '.join(header).lower()

                # Borrowing Base Test
                if 'borrowing base' in header_text or 'not late' in header_text:
                    for row in table[1:]:
                        if row and row[0]:
                            label = str(row[0]).strip()
                            val = str(row[-1]).strip() if row[-1] else ''
                            if label and val:
                                result['bb_test'][label] = val

                # Performance Triggers
                elif 'delinquen' in header_text or 'default' in header_text or 'trigger' in header_text:
                    for row in table[1:]:
                        if row and len(row) >= 3:
                            result['triggers'].append({
                                'label': str(row[0]).strip() if row[0] else '',
                                'values': [str(c).strip() if c else '' for c in row[1:]]
                            })

                # Concentration / Eligibility
                elif 'merchant' in header_text and ('limit' in header_text or 'threshold' in header_text or '%' in header_text):
                    for row in table[1:]:
                        if row and len(row) >= 3 and row[0]:
                            result['concentration_limits'].append({
                                'criterion': str(row[0]).strip(),
                                'values': [str(c).strip() if c else '' for c in row[1:]]
                            })

                # Stratifications (merchant category, instalment type, etc.)
                elif 'pending amount' in header_text or 'number of loans' in header_text:
                    strat_records = []
                    for row in table[1:]:
                        if row and row[0]:
                            strat_records.append([str(c).strip() if c else '' for c in row])
                    if strat_records:
                        # Use first column header as stratification name
                        strat_name = header[0] if header[0] else f'strat_{len(result["stratifications"])}'
                        result['stratifications'][strat_name] = {
                            'headers': header,
                            'rows': strat_records
                        }

                # Loan tranches
                elif 'senior' in header_text and ('balance' in header_text or 'limit' in header_text):
                    for row in table[1:]:
                        if row and row[0]:
                            result['tranches'].append({
                                'field': str(row[0]).strip(),
                                'values': [str(c).strip() if c else '' for c in row[1:]]
                            })

                # Payment waterfall
                elif 'priority' in header_text or 'waterfall' in header_text:
                    for row in table[1:]:
                        if row and row[0]:
                            result['waterfall'].append({
                                'step': str(row[0]).strip(),
                                'values': [str(c).strip() if c else '' for c in row[1:]]
                            })

    except Exception as e:
        print(f"  WARN: PDF parse error for {filepath}: {e}")

    return result


def parse_all_hsbc_reports(country='KSA'):
    """Parse all HSBC investor reports for a country."""
    if country == 'KSA':
        report_dir = DR_NEW / "54.3 Portfolio Investor Reporting" / "54.3.10 KSA"
    else:
        report_dir = DR_NEW / "54.3 Portfolio Investor Reporting" / "54.3.11 UAE"

    if not report_dir.exists():
        print(f"  WARN: HSBC report directory not found: {report_dir}")
        return []

    reports = []
    for f in sorted(report_dir.iterdir()):
        if f.suffix == '.pdf':
            # Extract date from filename
            date_match = re.search(r'(\d{1,2})[- ](\w+)[- ](\d{2,4})', f.name)
            report_date = None
            if date_match:
                day, month_str, year = date_match.groups()
                month_map = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                             'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                             'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
                             'january': '01', 'february': '02', 'march': '03',
                             'april': '04', 'june': '06', 'july': '07',
                             'august': '08', 'september': '09', 'october': '10',
                             'november': '11', 'december': '12'}
                month_num = month_map.get(month_str.lower()[:3], '01')
                if len(year) == 2:
                    year = '20' + year
                report_date = f"{year}-{month_num}-{day.zfill(2)}"

            parsed = parse_hsbc_report(f)
            parsed['report_date'] = report_date
            parsed['filename'] = f.name
            reports.append(parsed)

    return reports


# ═══════════════════════════════════════════════════════════════════════════════
# 8. DAILY DPD 7
# ═══════════════════════════════════════════════════════════════════════════════

def parse_daily_dpd7():
    """Parse the daily DPD 7 as of Due Date file."""
    fpath = DR_ADD / "24-March" / "DPD 7 as of Due Date.xlsx"
    if not fpath.exists():
        return {}

    print("  Parsing daily DPD 7...")
    df = pd.read_excel(fpath)
    result = {'KSA': [], 'UAE': []}

    for _, row in df.iterrows():
        row_dict = {str(k): _safe(v) for k, v in row.items()}
        # Determine country from row data
        for k, v in row_dict.items():
            if v == 'UAE' or v == 'AE':
                result['UAE'].append(row_dict)
                break
            elif v == 'KSA' or v == 'SA':
                result['KSA'].append(row_dict)
                break

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 9. STATIC DATA (from research + diligence pack)
# ═══════════════════════════════════════════════════════════════════════════════

def get_facility_terms(country='KSA'):
    """Return facility terms extracted from debt presentations."""
    if country == 'KSA':
        return {
            'facility_name': 'Project Gasoline — KSA Securitisation',
            'spv': 'Tamara Capital Designated Activity Company (Ireland)',
            'originator': 'Tamara Finance Company (KSA)',
            'close_date': '2025-08-18',
            'revolving_end': '2028-08-17',
            'final_maturity': '2029-08-18',
            'total_limit': 2375000000,
            'max_advance_rate': 0.95,
            'tranches': [
                {'name': 'Senior A', 'limit': 620000000, 'rate': 'SOFR + 265bp', 'lender': 'Goldman Sachs'},
                {'name': 'Senior B', 'limit': 280000000, 'rate': 'SOFR + 265bp', 'lender': 'Citibank'},
                {'name': 'Senior C', 'limit': 300000000, 'rate': '6.158% fixed', 'lender': 'Atlas (Apollo)'},
                {'name': 'Mezzanine', 'limit': 243750000, 'rate': 'SOFR + 725bp', 'lender': 'AP Phoenix (Apollo)'},
                {'name': 'Junior', 'limit': 22940000, 'rate': 'N/A', 'lender': 'Originator'},
            ],
            'triggers': {
                'delinquency': {'metric': '+7DPD Cohort (3M)', 'l1': 0.09, 'l2': 0.12, 'l3': 0.15},
                'default': {'metric': '+120DPD Cohort (6M)', 'l1': 0.05, 'l2': 0.075, 'l3': 0.09},
                'dilution': {'metric': 'Refund Rolling 3M', 'l1': 0.075, 'l2': 0.10, 'l3': 0.125},
            },
            'corporate_covenants': {
                'min_liquidity': {'threshold': 20000000, 'l2': 17500000, 'l3': 15000000},
                'min_tnw': {'threshold': 60000000, 'l2': 55000000, 'l3': 50000000},
                'max_de': {'threshold': 3.0, 'l2': 3.5, 'l3': 4.0},
                'sovereign_cds': {'threshold': 0.015, 'l2': 0.02, 'l3': 0.025},
            },
            'concentration_limits': [
                {'name': 'WA MDR', 'threshold': '>= 3.5%', 'type': 'min'},
                {'name': 'WA Remaining Term', 'threshold': '<= 8 months', 'type': 'max'},
                {'name': 'Repeat Obligors', 'threshold': '> 50%', 'type': 'min'},
                {'name': 'Single Merchant (non-exempt)', 'threshold': '<= 25%', 'type': 'max'},
                {'name': 'Top 5 Merchants', 'threshold': '<= 60%', 'type': 'max'},
                {'name': 'Top 10 Merchants', 'threshold': '<= 75%', 'type': 'max'},
                {'name': 'Split-in-Four or Less', 'threshold': '>= 50%', 'type': 'min'},
                {'name': 'Split-in-13-to-24', 'threshold': '<= 15%', 'type': 'max'},
            ],
        }
    else:  # UAE
        return {
            'facility_name': 'Project Gasoline 2.0 — UAE Securitisation',
            'spv': 'Tamara Capital UAE Designated Activity Company (Ireland)',
            'originator': 'Tamara FZE (UAE)',
            'close_date': '2024-05-31',
            'revolving_end': '2026-05-18',
            'final_maturity': '2026-11-17',
            'total_limit': 131250000,
            'max_advance_rate': 0.925,
            'tranches': [
                {'name': 'Senior A', 'limit': 100000000, 'rate': 'SOFR + 380bp', 'lender': 'Goldman Sachs'},
                {'name': 'Mezzanine', 'limit': 15625000, 'rate': 'SOFR + 775bp', 'lender': 'AP Phoenix II (Apollo)'},
                {'name': 'Junior', 'limit': 1000000, 'rate': '10% fixed', 'lender': 'Originator'},
            ],
            'triggers': {
                'delinquency': {'metric': '+7DPD Cohort (3M)', 'l1': 0.10, 'l2': 0.13, 'l3': 0.16},
                'default': {'metric': '+120DPD Cohort (6M)', 'l1': 0.08, 'l2': 0.105, 'l3': 0.155},
                'dilution': {'metric': 'Diluted Rolling 3M', 'l1': 0.15, 'l2': 0.175, 'l3': 0.20},
            },
            'corporate_covenants': {
                'min_liquidity': {'threshold': 30000000, 'l2': 27500000, 'l3': 25000000},
                'min_tnw': {'threshold': 30000000, 'l2': 27500000, 'l3': 25000000},
                'max_de': {'threshold': 2.0, 'l2': 2.5, 'l3': 3.0},
                'sovereign_cds': {'threshold': 0.0232, 'l2': 0.0282, 'l3': 0.0332},
            },
            'concentration_limits': [
                {'name': 'WA MDR', 'threshold': '>= 2.5%', 'type': 'min'},
                {'name': 'WA Remaining Term', 'threshold': '<= 5 months', 'type': 'max'},
                {'name': 'Repeat Obligors', 'threshold': '> 50%', 'type': 'min'},
                {'name': 'Single Merchant (non-exempt)', 'threshold': '<= 25%', 'type': 'max'},
                {'name': 'Top 5 Merchants', 'threshold': '<= 65%', 'type': 'max'},
                {'name': 'Top 10 Merchants', 'threshold': '<= 80%', 'type': 'max'},
                {'name': 'Split-in-Four', 'threshold': '>= 60%', 'type': 'min'},
                {'name': 'Split-in-Six', 'threshold': '<= 30%', 'type': 'max'},
            ],
        }


def get_company_overview():
    """Return static company overview data from research."""
    return {
        'name': 'Tamara',
        'full_name': 'Tamara Finance Company',
        'holding_company': 'Tamara Company (Cayman Islands)',
        'founded': 2020,
        'headquarters': 'Riyadh, Saudi Arabia',
        'ceo': 'Abdulmajeed Alsukhan',
        'coo': 'Turki Bin Zarah',
        'cfo': 'Mo Alahmadi',
        'cto': 'Ali Elgamal',
        'cro': 'Sami Louali',
        'employees': 988,
        'registered_users': 20000000,
        'merchants': 87000,
        'total_equity_raised': 556000000,
        'valuation': 1000000000,
        'latest_round': 'Series C ($340M, Dec 2023)',
        'key_investors': ['SNB Capital', 'Sanabil (PIF)', 'Coatue', 'Shorooq', 'Checkout.com'],
        'markets': ['KSA (primary)', 'UAE', 'Kuwait (licensing)', 'Bahrain (licensed)'],
        'products': {
            'bnpl': {'name': 'BNPL', 'tenor': '0-6 months', 'max_size': 'SAR 5,000', 'splits': [2, 3, 4, 6]},
            'bnpl_plus': {'name': 'BNPL+', 'tenor': '4-24 months', 'max_size': 'SAR 20,000', 'splits': [4, 6, 9, 12, 18, 24],
                          'apr': {'Pi4': 0.21, 'Pi6': 0.24, 'Pi9': 0.35, 'Pi12': 0.38, 'Pi24': 0.40}},
            'smart': {'name': 'Smart (Subscription)', 'fee': 'SAR 19/month'},
            'genius': {'name': 'Genius (Credit Card)', 'fee': 'SAR 50/month', 'status': 'Launching Q4 2025'},
        },
        'regulatory': {
            'ksa_bnpl': 'Finance Here license — Live',
            'ksa_bnpl_plus': 'Consumer Financing — Live (Mar 2025)',
            'ksa_credit_card': 'Finance Here — Q4 2025 launch',
            'uae_bnpl': 'Restricted Finance License — Oct 2025',
        },
        'market_position': 'Tamara + Tabby duopoly (~93% of KSA BNPL market)',
        'ipo_target': 'End of FY28 (management plan)',
        'series_d': '$300M planned Q4 2026-Q1 2027',
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Assemble and output
# ═══════════════════════════════════════════════════════════════════════════════

def build_country_json(country):
    """Build the complete JSON snapshot for a country."""
    print(f"\n{'='*60}")
    print(f"  Building {country} JSON snapshot")
    print(f"{'='*60}")

    data = {
        'meta': {
            'company': 'Tamara',
            'product': country,
            'report_date': '2026-04-09',
            'currency': 'SAR' if country == 'KSA' else 'AED',
            'data_sources': [
                'HSBC Investor Reports (10 monthly, Jan-Oct 2025)',
                'Vintage Cohort Matrices (~50 Excel files)',
                'Deloitte FDD Loan Portfolio (12,799 rows)',
                'Monthly Investor Reporting (25 months)',
                'Financial Master (actuals through Nov 2025)',
                'Portfolio Demographics Workbook',
                'Debt Presentation Decks (Q1 2026)',
                'Business Plan FY26-FY30',
            ],
        },
        'company_overview': get_company_overview(),
        'facility_terms': get_facility_terms(country),
        'vintage_performance': parse_all_cohort_matrices(country),
        'deloitte_fdd': parse_deloitte_fdd(country),
        'investor_reporting': parse_investor_reporting(country),
        'hsbc_reports': parse_all_hsbc_reports(country),
    }

    # KSA-only sections
    if country == 'KSA':
        data['demographics'] = parse_demographics(country)
        data['business_plan'] = parse_business_plan()
        data['financial_master'] = parse_financial_master()

        # Daily DPD
        dpd7 = parse_daily_dpd7()
        data['daily_dpd7'] = dpd7.get('KSA', [])
    else:
        data['demographics'] = parse_demographics(country)
        dpd7 = parse_daily_dpd7()
        data['daily_dpd7'] = dpd7.get('UAE', [])

    # Data notes
    data['data_notes'] = [
        'Default = +120DPD (receivables >120 days past due)',
        'Delinquency = +7DPD (receivables >7 days past due)',
        'Dilution = refunds/cancellations as % of eligible originated',
        'Write-off occurs at DPD 90. Recovery efforts continue post write-off.',
        'BNPL product types: Pi2 (Pay in 2), Pi3, Pi4, Pi6',
        'BNPL+ product types: Pi4, Pi6, Pi9, Pi12, Pi24 (Murabaha profit-bearing)',
        'Pi6 exists in both BNPL and BNPL+ segments',
        f'Securitisation facility: {data["facility_terms"]["facility_name"]}',
        f'Total facility limit: ${data["facility_terms"]["total_limit"]:,.0f}',
        'Eligible receivable criteria: resident, 18+, max balance, no 30-day-late in prior 12M, down payment paid',
    ]

    return data


def main():
    """Main entry point."""
    print("Tamara Data Preparation")
    print("=" * 60)

    for country in ['KSA', 'UAE']:
        data = build_country_json(country)

        # Output path
        out_dir = DATA_OUT / country
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"2026-04-09_tamara_{country.lower()}.json"

        # Write JSON
        print(f"\n  Writing {out_file}...")
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

        file_size = out_file.stat().st_size / 1024 / 1024
        print(f"  Done: {file_size:.1f} MB")

    print(f"\n{'='*60}")
    print("  Data preparation complete!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
