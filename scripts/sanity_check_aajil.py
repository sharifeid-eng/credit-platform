#!/usr/bin/env python3
"""Sanity check every calculation in the Aajil analysis module."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd, numpy as np
from core.loader import load_aajil_snapshot
from core.analysis_aajil import *
from core.validation_aajil import validate_aajil_tape

df, aux = load_aajil_snapshot('data/Aajil/KSA/2026-04-13_aajil_ksa.xlsx')
errors = []
SEP = "=" * 80

def chk(name, cond, msg):
    if not cond:
        errors.append(f"[{name}] {msg}")
        print(f"  !! {msg}")

print(SEP)
print("SANITY CHECK: EVERY CALCULATION")
print(SEP)

# Manual reference values
manual_bill = df[C_BILL].sum()
manual_realised = df[C_REALISED].fillna(0).sum()
manual_receivable = df[C_RECEIVABLE].fillna(0).sum()
manual_wo = df[C_WRITTEN_OFF].fillna(0).sum()
manual_margin = df[C_MARGIN].fillna(0).sum()
manual_fees = df[C_ORIG_FEE].fillna(0).sum()
r_count = len(df[df[C_STATUS] == 'Realised'])
a_count = len(df[df[C_STATUS] == 'Accrued'])
w_count = len(df[df[C_STATUS] == 'Written Off'])

# ── SUMMARY ──
print("\n--- SUMMARY ---")
s = compute_aajil_summary(df, mult=1, aux=aux)
chk("sum", s["total_deals"] == len(df), f"deals {s['total_deals']} vs {len(df)}")
chk("sum", s["realised_count"] == r_count, f"realised {s['realised_count']} vs {r_count}")
chk("sum", s["accrued_count"] == a_count, f"accrued {s['accrued_count']} vs {a_count}")
chk("sum", s["written_off_count"] == w_count, f"wo {s['written_off_count']} vs {w_count}")
chk("sum", s["total_customers"] == df[C_CUSTOMER_ID].nunique(), "customer count")
chk("sum", abs(s["total_bill_notional"] - manual_bill) < 1, "bill total")
chk("sum", abs(s["total_realised"] - manual_realised) < 1, "realised total")
chk("sum", abs(s["total_receivable"] - manual_receivable) < 1, "receivable total")
cr = manual_realised / (manual_realised + manual_receivable)
chk("sum", abs(s["collection_rate"] - cr) < 0.001, f"collection rate {s['collection_rate']:.4f} vs {cr:.4f}")
shares = df.groupby(C_CUSTOMER_ID)[C_BILL].sum()
hhi = ((shares / shares.sum()) ** 2).sum()
chk("sum", abs(s["hhi_customer"] - hhi) < 0.0001, f"HHI {s['hhi_customer']:.4f} vs {hhi:.4f}")
print(f"  All {len(df)} deals, SAR {manual_bill:,.0f} bill, {cr*100:.1f}% rate, HHI={hhi:.4f} OK")

# ── TRACTION ──
print("\n--- TRACTION ---")
t = compute_aajil_traction(df, mult=1, aux=aux)
vol_sum = sum(v["disbursed_sar"] for v in t["volume_monthly"])
chk("tract", abs(vol_sum - manual_bill) < 1, f"vol sum {vol_sum:,.0f} vs {manual_bill:,.0f}")
vol_cnt = sum(v.get("count", 0) for v in t["volume_monthly"])
chk("tract", vol_cnt == len(df), f"vol count {vol_cnt} vs {len(df)}")
chk("tract", len(t["balance_monthly"]) == len(t["volume_monthly"]), "balance/volume month mismatch")
bal_last = t["balance_monthly"][-1]["balance_sar"]
chk("tract", bal_last > 0, f"last balance is 0")
print(f"  {len(t['volume_monthly'])} months, vol sum=SAR {vol_sum:,.0f}, bal last=SAR {bal_last:,.0f} OK")

# ── DELINQUENCY ──
print("\n--- DELINQUENCY ---")
d = compute_aajil_delinquency(df, mult=1, aux=aux)
active = df[df[C_STATUS] == "Accrued"]
bkt_sum = sum(b["count"] for b in d["buckets"])
chk("delinq", bkt_sum == len(active), f"bucket sum {bkt_sum} vs {len(active)}")
act_bal = active[C_RECEIVABLE].fillna(0).sum()
chk("delinq", abs(d["total_active_balance"] - act_bal) < 1, "active balance")
ovd_bal = active[C_SALE_OVERDUE].fillna(0).sum()
chk("delinq", abs(d["total_overdue_balance"] - ovd_bal) < 1, "overdue balance")
bt_sum = sum(bt["active_count"] for bt in d["by_deal_type"])
chk("delinq", bt_sum == len(active), f"by-type sum {bt_sum} vs {len(active)}")
print(f"  {bkt_sum}/{len(active)} bucketed, active=SAR {act_bal:,.0f}, overdue=SAR {ovd_bal:,.0f} OK")

# ── COLLECTIONS ──
print("\n--- COLLECTIONS ---")
c = compute_aajil_collections(df, mult=1, aux=aux)
chk("coll", abs(c["total_originated"] - manual_bill) < 1, "originated")
chk("coll", abs(c["total_collected"] - manual_realised) < 1, "collected")
rate = manual_realised / manual_bill
chk("coll", abs(c["overall_rate"] - rate) < 0.001, f"rate {c['overall_rate']:.4f} vs {rate:.4f}")
m_sum = sum(m["collected"] for m in c["monthly"])
chk("coll", abs(m_sum - manual_realised) < 1, f"monthly sum {m_sum:,.0f} vs {manual_realised:,.0f}")
print(f"  SAR {c['total_originated']:,.0f} orig, SAR {c['total_collected']:,.0f} coll, {rate*100:.1f}% OK")

# ── COHORTS ──
print("\n--- COHORTS ---")
co = compute_aajil_cohorts(df, mult=1, aux=aux)
co_deals = sum(c["count"] for c in co["cohorts"])
expected = len(df) - df[C_INVOICE_DATE].isna().sum()
chk("cohort", co_deals == expected, f"deals {co_deals} vs {expected}")
co_vol = sum(c["original_balance"] for c in co["cohorts"])
exp_vol = df.dropna(subset=[C_INVOICE_DATE])[C_BILL].sum()
chk("cohort", abs(co_vol - exp_vol) < 1, f"volume {co_vol:,.0f} vs {exp_vol:,.0f}")
print(f"  {len(co['cohorts'])} cohorts, {co_deals} deals, SAR {co_vol:,.0f} OK")

# ── CONCENTRATION ──
print("\n--- CONCENTRATION ---")
cn = compute_aajil_concentration(df, mult=1, aux=aux)
chk("conc", 0 < cn["hhi_customer"] < 1, "HHI range")
chk("conc", cn["top5_share"] <= cn["top10_share"], "top5 <= top10")
ind_vol = sum(i["volume"] for i in cn["industries"])
chk("conc", abs(ind_vol - manual_bill) < 1, f"industry vol {ind_vol:,.0f}")
dt_vol = sum(d["volume"] for d in cn["deal_type_mix"])
chk("conc", abs(dt_vol - manual_bill) < 1, f"deal type vol {dt_vol:,.0f}")
# Cumulative should be monotonic
for i in range(1, len(cn["top_customers"])):
    chk("conc", cn["top_customers"][i]["cumulative"] >= cn["top_customers"][i-1]["cumulative"] - 0.001, "cumulative not monotonic")
print(f"  HHI={cn['hhi_customer']:.4f}, top5={cn['top5_share']*100:.1f}%, industries sum OK")

# ── YIELD ──
print("\n--- YIELD ---")
y = compute_aajil_yield(df, mult=1, aux=aux)
chk("yield", abs(y["total_margin"] - manual_margin) < 1, "margin")
chk("yield", abs(y["total_fees"] - manual_fees) < 1, "fees")
chk("yield", abs(y["total_revenue"] - (manual_margin + manual_fees)) < 1, "revenue")
dt_margin = sum(d["total_margin"] for d in y["by_deal_type"])
chk("yield", abs(dt_margin - manual_margin) < 1, "by-type margin sum")
print(f"  Margin SAR {manual_margin:,.0f}, Fees SAR {manual_fees:,.0f}, Rev/GMV={y['revenue_over_gmv']*100:.2f}% OK")

# ── LOSS WATERFALL ──
print("\n--- LOSS WATERFALL ---")
lw = compute_aajil_loss_waterfall(df, mult=1, aux=aux)
chk("loss", lw["waterfall"][0]["count"] == len(df), "total count")
chk("loss", lw["waterfall"][1]["count"] == r_count, "realised count")
chk("loss", lw["waterfall"][2]["count"] == a_count, "accrued count")
chk("loss", lw["waterfall"][3]["count"] == w_count, "wo count")
chk("loss", abs(lw["waterfall"][0]["amount"] - manual_bill) < 1, "originated amount")
wo_bill = df[df[C_STATUS] == "Written Off"][C_BILL].sum()
chk("loss", abs(lw["gross_loss_rate"] - wo_bill / manual_bill) < 0.0001, "gross loss rate")
chk("loss", abs(lw["net_loss"] - (lw["written_off_amount"] - lw["vat_recovered"])) < 1, "net loss = wo - vat")
# Vintage loss deals should sum to 19
vint_wo = sum(v["wo_count"] for v in lw["by_vintage"])
chk("loss", vint_wo == w_count, f"vintage WO sum {vint_wo} vs {w_count}")
print(f"  {w_count} WO, gross rate={wo_bill/manual_bill*100:.2f}%, net loss=SAR {lw['net_loss']:,.0f} OK")

# ── SEGMENTS ──
print("\n--- SEGMENTS ---")
cs = compute_aajil_customer_segments(df, mult=1, aux=aux)
dt_cnt = sum(s["count"] for s in cs["segments"]["by_deal_type"])
chk("seg", dt_cnt == len(df) - df[C_DEAL_TYPE].isna().sum(), f"dt count {dt_cnt}")
ind_cnt = sum(s["count"] for s in cs["segments"]["by_industry"])
chk("seg", ind_cnt == len(df), f"industry count {ind_cnt} vs {len(df)}")
size_deals = sum(s["deal_count"] for s in cs["segments"]["by_customer_size"])
chk("seg", size_deals == len(df), f"size deals {size_deals} vs {len(df)}")
print(f"  By type: {dt_cnt}, by industry: {ind_cnt}, by size: {size_deals} OK")

# ── SEASONALITY ──
print("\n--- SEASONALITY ---")
se = compute_aajil_seasonality(df, mult=1, aux=aux)
avg_idx = np.mean([s["index"] for s in se["seasonal_index"] if s["index"]])
chk("season", abs(avg_idx - 1.0) < 0.1, f"seasonal avg {avg_idx:.3f}")
print(f"  {len(se['years'])} years, avg index={avg_idx:.3f} OK")

# ── VALIDATION ──
print("\n--- VALIDATION ---")
v = validate_aajil_tape(df)
print(f"  Critical: {v['critical']}")
print(f"  Warnings: {v['warnings']}")

# ── RESULT ──
print(f"\n{SEP}")
if errors:
    print(f"FAILED: {len(errors)} errors")
    for e in errors:
        print(f"  x {e}")
else:
    print("ALL CALCULATIONS VERIFIED - EVERY CHECK PASSED")
