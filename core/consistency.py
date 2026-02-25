import pandas as pd

def find_id_column(df):
    """Find the ID column regardless of exact name"""
    id_candidates = ['ID', 'Id', 'id', 'Reference', 'reference', 'Deal ID', 'deal_id']
    for col in id_candidates:
        if col in df.columns:
            return col
    return None

def run_consistency_check(old_df, new_df, old_label, new_label):
    """Compare two snapshots and return a consistency report"""
    issues = []
    warnings = []
    info = []

    # ── 0. Column comparison ─────────────────────────────────
    old_cols = set(old_df.columns)
    new_cols = set(new_df.columns)
    
    added_cols = new_cols - old_cols
    removed_cols = old_cols - new_cols
    
    if added_cols:
        info.append({
            'severity': 'INFO',
            'check': 'New Columns',
            'detail': f"Columns added in {new_label}: {', '.join(added_cols)}"
        })
    if removed_cols:
        warnings.append({
            'severity': 'WARNING',
            'check': 'Missing Columns',
            'detail': f"Columns present in {old_label} but missing in {new_label}: {', '.join(removed_cols)}"
        })

    # ── 1. Find ID column ────────────────────────────────────
    old_id_col = find_id_column(old_df)
    new_id_col = find_id_column(new_df)

    if not old_id_col or not new_id_col:
        # No ID column found - use Deal date + Purchase value as composite key
        warnings.append({
            'severity': 'WARNING',
            'check': 'No ID Column',
            'detail': 'No ID column found. Using Deal date + Purchase value as composite key for comparison.'
        })
        # Skip ID-based checks
        id_based_checks = False
    else:
        id_based_checks = True
        old_ids = set(old_df[old_id_col].astype(str))
        new_ids = set(new_df[new_id_col].astype(str))
        
        missing_from_new = old_ids - new_ids
        if missing_from_new:
            issues.append({
                'severity': 'CRITICAL',
                'check': 'Missing Deals',
                'detail': f"{len(missing_from_new)} deals in {old_label} are missing from {new_label}",
                'ids': list(missing_from_new)[:10]
            })
        
        new_deals = new_ids - old_ids
        info.append({
            'severity': 'INFO',
            'check': 'New Deals',
            'detail': f"{len(new_deals)} new deals added since {old_label}"
        })

        # ── 2. Check completed deals for amount changes ──────
        common_immutable = ['Purchase value', 'Purchase price', 'Gross revenue']
        available_immutable = [c for c in common_immutable 
                               if c in old_df.columns and c in new_df.columns]

        if available_immutable and old_id_col and new_id_col:
            old_completed = old_df[old_df['Status'] == 'Completed'][
                [old_id_col] + available_immutable]
            new_completed = new_df[new_df['Status'] == 'Completed'][
                [new_id_col] + available_immutable]
            
            merged = old_completed.merge(
                new_completed, 
                left_on=old_id_col, 
                right_on=new_id_col, 
                suffixes=('_old', '_new')
            )
            
            for col in available_immutable:
                if f'{col}_old' in merged.columns and f'{col}_new' in merged.columns:
                    changed = merged[abs(merged[f'{col}_old'] - merged[f'{col}_new']) > 0.01]
                    if not changed.empty:
                        issues.append({
                            'severity': 'CRITICAL',
                            'check': f'{col} Changed on Completed Deals',
                            'detail': f"{len(changed)} completed deals have different {col} values"
                        })

        # ── 3. Check for illogical status changes ────────────
        if 'Status' in old_df.columns and 'Status' in new_df.columns:
            old_status = old_df[[old_id_col, 'Status']].copy()
            new_status = new_df[[new_id_col, 'Status']].copy()
            
            status_merged = old_status.merge(
                new_status,
                left_on=old_id_col,
                right_on=new_id_col,
                suffixes=('_old', '_new')
            )
            
            reversed_status = status_merged[
                (status_merged['Status_old'] == 'Completed') & 
                (status_merged['Status_new'] != 'Completed')
            ]
            if not reversed_status.empty:
                issues.append({
                    'severity': 'CRITICAL',
                    'check': 'Status Reversal',
                    'detail': f"{len(reversed_status)} deals moved backwards from Completed status"
                })

    # ── 4. Portfolio-level checks ────────────────────────────
    if 'Collected till date' in old_df.columns and 'Collected till date' in new_df.columns:
        old_rate = (old_df['Collected till date'].sum() / 
                    old_df['Purchase value'].sum())
        new_rate = (new_df['Collected till date'].sum() / 
                    new_df['Purchase value'].sum())
        rate_shift = abs(new_rate - old_rate)
        
        if rate_shift > 0.05:
            warnings.append({
                'severity': 'WARNING',
                'check': 'Collection Rate Shift',
                'detail': f"Collection rate changed by {rate_shift:.1%} ({old_rate:.1%} → {new_rate:.1%})"
            })
        else:
            info.append({
                'severity': 'INFO',
                'check': 'Collection Rate',
                'detail': f"Collection rate: {old_rate:.1%} ({old_label}) → {new_rate:.1%} ({new_label})"
            })

    if 'Denied by insurance' in old_df.columns and 'Denied by insurance' in new_df.columns:
        old_denial = (old_df['Denied by insurance'].sum() / 
                      old_df['Purchase value'].sum())
        new_denial = (new_df['Denied by insurance'].sum() / 
                      new_df['Purchase value'].sum())
        denial_shift = abs(new_denial - old_denial)
        
        if denial_shift > 0.02:
            warnings.append({
                'severity': 'WARNING',
                'check': 'Denial Rate Shift',
                'detail': f"Denial rate changed by {denial_shift:.1%} ({old_denial:.1%} → {new_denial:.1%})"
            })
        else:
            info.append({
                'severity': 'INFO',
                'check': 'Denial Rate',
                'detail': f"Denial rate: {old_denial:.1%} ({old_label}) → {new_denial:.1%} ({new_label})"
            })

    # ── 5. Deal count check ──────────────────────────────────
    old_count = len(old_df)
    new_count = len(new_df)
    
    if new_count < old_count:
        issues.append({
            'severity': 'CRITICAL',
            'check': 'Deal Count Decreased',
            'detail': f"New snapshot has fewer rows: {old_count} ({old_label}) → {new_count} ({new_label})"
        })
    else:
        info.append({
            'severity': 'INFO',
            'check': 'Deal Count',
            'detail': f"Deal count: {old_count} ({old_label}) → {new_count} ({new_label})"
        })

    return {
        'issues': issues,
        'warnings': warnings,
        'info': info,
        'passed': len(issues) == 0
    }

def print_consistency_report(report, old_label, new_label):
    """Print a formatted consistency report"""
    print(f"\n{'='*60}")
    print(f"CONSISTENCY CHECK: {old_label} vs {new_label}")
    print(f"{'='*60}")
    
    if report['passed']:
        print("✓ No critical issues found\n")
    else:
        print(f"✗ {len(report['issues'])} critical issue(s) found\n")
    
    if report['issues']:
        print("CRITICAL ISSUES:")
        for item in report['issues']:
            print(f"  ✗ [{item['check']}] {item['detail']}")
            if 'ids' in item:
                print(f"    Sample IDs: {', '.join(item['ids'][:5])}")
        print()
    
    if report['warnings']:
        print("WARNINGS:")
        for item in report['warnings']:
            print(f"  ⚠ [{item['check']}] {item['detail']}")
        print()
    
    print("INFO:")
    for item in report['info']:
        print(f"  ℹ [{item['check']}] {item['detail']}")
    
    print(f"{'='*60}\n")