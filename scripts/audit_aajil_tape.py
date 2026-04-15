#!/usr/bin/env python3
"""Comprehensive audit of all Aajil compute functions against the real tape."""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from core.loader import load_aajil_snapshot
from core.analysis_aajil import *

df, aux = load_aajil_snapshot('data/Aajil/KSA/2026-04-13_aajil_ksa.xlsx')

SEP = "=" * 80
issues = []

def check(name, condition, msg):
    if not condition:
        issues.append(f"[{name}] {msg}")
        print(f"   !! ISSUE: {msg}")

print(SEP)
print("AAJIL TAPE DEEP AUDIT")
print(SEP)

# 1. RAW TAPE
print("\n1. RAW TAPE STATISTICS")
print(f"   Deals: {len(df)}")
print(f"   Date range: {df[C_INVOICE_DATE].min():%Y-%m-%d} to {df[C_INVOICE_DATE].max():%Y-%m-%d}")
print(f"   Status: {df[C_STATUS].value_counts().to_dict()}")
print(f"   Deal Type: {df[C_DEAL_TYPE].value_counts().to_dict()}")
print(f"   Customers: {df[C_CUSTOMER_ID].nunique()}")
print(f"   Industries: {df[C_INDUSTRY].nunique()} unique, {df[C_INDUSTRY].isna().sum()} missing ({df[C_INDUSTRY].isna().mean()*100:.0f}%)")

# Numeric ranges
for col in [C_BILL, C_SALE_TOTAL, C_REALISED, C_RECEIVABLE, C_TENURE, C_TOTAL_YIELD]:
    vals = df[col].dropna()
    if len(vals):
        print(f"   {col}: min={vals.min():,.2f}, median={vals.median():,.2f}, max={vals.max():,.2f}")

# 2. SUMMARY
print(f"\n{SEP}")
print("2. SUMMARY")
s = compute_aajil_summary(df, mult=1, aux=aux)
check("summary", s['total_deals'] == 1245, f"Expected 1245 deals, got {s['total_deals']}")
check("summary", s['realised_count'] == 883, f"Expected 883 Realised, got {s['realised_count']}")
check("summary", s['accrued_count'] == 342, f"Expected 342 Accrued, got {s['accrued_count']}")
check("summary", s['written_off_count'] == 19, f"Expected 19 Written Off, got {s['written_off_count']}")
check("summary", s['total_customers'] == 227, f"Expected 227 customers, got {s['total_customers']}")
check("summary", 0 < s['collection_rate'] < 1, f"Collection rate out of range: {s['collection_rate']}")
check("summary", s['hhi_customer'] > 0, f"HHI should be > 0")
print(f"   Deals: {s['total_deals']}, Customers: {s['total_customers']}")
print(f"   GMV: SAR {s['total_bill_notional']:,.0f}, Outstanding: SAR {s['total_receivable']:,.0f}")
print(f"   Collection rate: {s['collection_rate']*100:.1f}%, WO rate: {s['write_off_rate']*100:.1f}%")
print(f"   EMI: {s['emi_count']} ({s['emi_pct']*100:.0f}%), Bullet: {s['bullet_count']} ({s['bullet_pct']*100:.0f}%)")
print(f"   Avg tenure: {s['avg_tenure']:.1f}mo, Avg yield: {s['avg_total_yield']*100:.3f}%")

# 3. TRACTION
print(f"\n{SEP}")
print("3. TRACTION")
t = compute_aajil_traction(df, mult=1, aux=aux)
check("traction", len(t['volume_monthly']) >= 45, f"Expected 45+ months, got {len(t['volume_monthly'])}")
check("traction", len(t['balance_monthly']) >= 45, f"Expected 45+ balance months, got {len(t['balance_monthly'])}")
check("traction", t['total_disbursed'] > 300_000_000, f"Total disbursed seems low: {t['total_disbursed']}")
check("traction", t['latest_balance'] > 0, f"Latest balance should be > 0")
# Verify balance is non-decreasing overall (it should grow)
bm = t['balance_monthly']
last_bal = bm[-1]['balance_sar'] if bm else 0
check("traction", last_bal > 50_000_000, f"Final balance seems low: {last_bal}")
print(f"   Volume months: {len(t['volume_monthly'])}, Balance months: {len(t['balance_monthly'])}")
print(f"   Total disbursed: SAR {t['total_disbursed']:,.0f}")
print(f"   Latest balance: SAR {t['latest_balance']:,.0f}")
print(f"   Growth: {t.get('volume_summary_stats', {})}")
print(f"   By type months: {len(t.get('volume_by_deal_type', []))}")

# 4. DELINQUENCY
print(f"\n{SEP}")
print("4. DELINQUENCY")
d = compute_aajil_delinquency(df, mult=1, aux=aux)
check("delinquency", len(d['buckets']) == 4, f"Expected 4 buckets, got {len(d['buckets'])}")
check("delinquency", d['total_active_balance'] > 0, "Active balance should be > 0")
bucket_sum = sum(b['count'] for b in d['buckets'])
check("delinquency", bucket_sum == 342, f"Bucket sum should be 342 (Accrued), got {bucket_sum}")
print(f"   Active balance: SAR {d['total_active_balance']:,.0f}")
print(f"   Overdue balance: SAR {d['total_overdue_balance']:,.0f}")
print(f"   PAR 1+: {d['par_1_inst']*100:.2f}%, PAR 2+: {d['par_2_inst']*100:.2f}%, PAR 3+: {d['par_3_inst']*100:.2f}%")
for b in d['buckets']:
    print(f"   {b['bucket']}: {b['count']} deals, SAR {b['balance']:,.0f}")
for bt in d['by_deal_type']:
    print(f"   {bt['deal_type']}: {bt['overdue_count']}/{bt['active_count']} overdue ({bt['overdue_pct']*100:.1f}%)")

# 5. COLLECTIONS
print(f"\n{SEP}")
print("5. COLLECTIONS")
c = compute_aajil_collections(df, mult=1, aux=aux)
check("collections", len(c['monthly']) >= 45, f"Expected 45+ months, got {len(c['monthly'])}")
check("collections", c['total_originated'] > 300_000_000, "Total originated seems low")
check("collections", c['total_collected'] > 0, "Total collected should be > 0")
check("collections", 0 < c['overall_rate'] <= 2, f"Overall rate out of range: {c['overall_rate']}")
print(f"   Months: {len(c['monthly'])}")
print(f"   Originated: SAR {c['total_originated']:,.0f}, Collected: SAR {c['total_collected']:,.0f}")
print(f"   Overall rate: {c['overall_rate']*100:.2f}%")
# Recent months
for m in c['monthly'][-5:]:
    rate_str = f"{m['collection_rate']*100:.1f}%" if m.get('collection_rate') else 'N/A'
    print(f"   {m['date']}: originated={m['originated']:,.0f}, collected={m['collected']:,.0f}, rate={rate_str}")

# 6. COHORTS
print(f"\n{SEP}")
print("6. COHORTS")
co = compute_aajil_cohorts(df, mult=1, aux=aux)
check("cohorts", len(co['cohorts']) >= 10, f"Expected 10+ cohorts, got {len(co['cohorts'])}")
total_deals_in_cohorts = sum(c['count'] for c in co['cohorts'])
check("cohorts", total_deals_in_cohorts == len(df), f"Cohort deal count mismatch: {total_deals_in_cohorts} vs {len(df)}")
print(f"   Cohort count: {len(co['cohorts'])}")
for c in co['cohorts']:
    wo_str = f" WO={c['written_off_count']}" if c['written_off_count'] > 0 else ""
    print(f"   {c['cohort']}: {c['count']} deals, SAR {c['original_balance']:,.0f}, rate={c['collection_rate']*100:.1f}%{wo_str}")

# 7. CONCENTRATION
print(f"\n{SEP}")
print("7. CONCENTRATION")
cn = compute_aajil_concentration(df, mult=1, aux=aux)
check("concentration", 0 < cn['hhi_customer'] < 1, f"HHI out of range: {cn['hhi_customer']}")
check("concentration", cn['top5_share'] < cn['top10_share'], "Top 5 should be < top 10")
check("concentration", len(cn['top_customers']) == 15, f"Expected 15 top customers")
check("concentration", len(cn['industries']) > 3, "Should have multiple industry buckets")
print(f"   HHI: {cn['hhi_customer']:.4f}, Top5: {cn['top5_share']*100:.1f}%, Top10: {cn['top10_share']*100:.1f}%")
print(f"   Industry unknown: {cn['industry_unknown_pct']*100:.0f}%")
print(f"   Top 5 customers:")
for c in cn['top_customers'][:5]:
    print(f"     #{c['customer_id']}: SAR {c['volume']:,.0f} ({c['share']*100:.1f}%), cum={c['cumulative']*100:.1f}%")
print(f"   Industries:")
for i in cn['industries']:
    print(f"     {i['industry']}: {i['count']} deals, SAR {i['volume']:,.0f} ({i['share']*100:.1f}%)")

# 8. UNDERWRITING
print(f"\n{SEP}")
print("8. UNDERWRITING DRIFT")
uw = compute_aajil_underwriting(df, mult=1, aux=aux)
check("underwriting", len(uw['vintages']) >= 10, f"Expected 10+ vintages")
print(f"   Vintages: {len(uw['vintages'])}")
for v in uw['vintages']:
    emi_str = f"{v['emi_pct']*100:.0f}%" if v['emi_pct'] is not None else "N/A"
    yield_str = f"{v['avg_yield']*100:.3f}%" if v['avg_yield'] is not None else "N/A"
    print(f"   {v['vintage']}: n={v['count']}, size=SAR {v['avg_deal_size']:,.0f}, tenure={v['avg_tenure']:.1f}mo, yield={yield_str}, EMI={emi_str}")

# 9. YIELD
print(f"\n{SEP}")
print("9. YIELD")
y = compute_aajil_yield(df, mult=1, aux=aux)
check("yield", y['total_revenue'] > 0, "Revenue should be > 0")
check("yield", y['avg_total_yield'] > 0, "Avg yield should be > 0")
print(f"   Margin: SAR {y['total_margin']:,.0f}, Fees: SAR {y['total_fees']:,.0f}")
print(f"   Revenue: SAR {y['total_revenue']:,.0f} ({y['revenue_over_gmv']*100:.2f}% of GMV)")
print(f"   Avg yield: {y['avg_total_yield']*100:.3f}%, Median: {y['median_total_yield']*100:.3f}%")
print(f"   Distribution: {y['yield_distribution']}")
for dt in y['by_deal_type']:
    print(f"   {dt['deal_type']}: yield={dt['avg_total_yield']*100:.3f}%, margin=SAR {dt['total_margin']:,.0f}, n={dt['count']}")

# 10. LOSS WATERFALL
print(f"\n{SEP}")
print("10. LOSS WATERFALL")
lw = compute_aajil_loss_waterfall(df, mult=1, aux=aux)
check("loss", lw['waterfall'][0]['count'] == len(df), "First stage should be all deals")
check("loss", lw['waterfall'][-1]['count'] == 19, "Written Off should be 19")
print(f"   Waterfall:")
for s in lw['waterfall']:
    print(f"     {s['stage']}: SAR {s['amount']:,.0f} ({s['count']} deals)")
print(f"   Written off: SAR {lw['written_off_amount']:,.0f}")
print(f"   VAT recovered: SAR {lw['vat_recovered']:,.0f}")
print(f"   Net loss: SAR {lw['net_loss']:,.0f}")
print(f"   Gross loss rate: {lw['gross_loss_rate']*100:.2f}%")
loss_v = [v for v in lw['by_vintage'] if v['wo_count'] > 0]
print(f"   Vintages with losses ({len(loss_v)}):")
for v in loss_v:
    print(f"     {v['vintage']}: {v['wo_count']} WO, SAR {v['written_off']:,.0f}, rate={v['loss_rate']*100:.2f}%")

# 11. SEGMENTS
print(f"\n{SEP}")
print("11. CUSTOMER SEGMENTS")
cs = compute_aajil_customer_segments(df, mult=1, aux=aux)
print(f"   By Deal Type:")
for s in cs['segments']['by_deal_type']:
    print(f"     {s['segment']}: {s['count']} deals, SAR {s['volume']:,.0f}, overdue={s['overdue_pct']*100:.1f}%, yield={s['avg_yield']*100:.3f}%, WO={s['wo_count']}")
print(f"   By Industry (top 5):")
for s in cs['segments']['by_industry'][:5]:
    rate_str = f"{s['collection_rate']*100:.1f}%" if s.get('collection_rate') else "N/A"
    print(f"     {s['segment']}: {s['count']} deals, SAR {s['volume']:,.0f}, rate={rate_str}")
print(f"   By Customer Size:")
for s in cs['segments']['by_customer_size']:
    print(f"     {s['segment']}: {s['customer_count']} customers, {s['deal_count']} deals, SAR {s['volume']:,.0f}")

# 12. SEASONALITY
print(f"\n{SEP}")
print("12. SEASONALITY")
se = compute_aajil_seasonality(df, mult=1, aux=aux)
print(f"   Years: {se['years']}")
for si in se['seasonal_index']:
    bar = '#' * int(si['index'] * 15) if si['index'] else ''
    mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][si['month']-1]
    print(f"     {mn}: {si['index']:.2f} {bar}")

# 13. AUX DATA
print(f"\n{SEP}")
print("13. AUXILIARY SHEETS")
print(f"   DPD Cohorts: {aux['dpd_cohorts'].shape}")
print(f"   Collections: {aux['collections'].shape}")
print(f"   Payments: {aux['payments'].shape}")
# Payments analysis
pay = aux['payments']
print(f"   Payment columns (first 15): {list(pay.columns[:15])}")

# SUMMARY
print(f"\n{SEP}")
print(f"AUDIT COMPLETE: {len(issues)} issues found")
for i, issue in enumerate(issues):
    print(f"  {i+1}. {issue}")
if not issues:
    print("  ALL CHECKS PASSED!")
