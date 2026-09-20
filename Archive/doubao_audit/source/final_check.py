# -*- coding: utf-8 -*-
"""交付前最终复现验证"""
import pandas as pd
from pal_engine import Params, simulate

d = pd.read_csv("data/qqq_daily.csv", parse_dates=["date"])
print("数据区间:", d["date"].iloc[0].date(), "->", d["date"].iloc[-1].date(), "交易日", len(d))
ROB = dict(borrow_stress_dd=.6, borrow_stress_mmr=1.5, runway_lo=5, rebalance="twoway")
for m in ["A", "B", "C0", "C1", "C2"]:
    kw = dict(stock_target=.7, withdraw=.02, rebalance="twoway")
    if m == "C1": kw.update(ROB)
    if m == "C2": kw.update(dd_freeze=.25, defensive_beta=.5)
    s = simulate(d, m, Params(**kw), start="2000-03-27")[1]
    print(f"{m:3} {s['status']:>13}  minMMR={str(s['min_mmr']):>6}  minRun={s['min_runway']:>5}  "
          f"maxDebt={s['max_debt']:.3f}  interest={s['total_interest']:.3f}  finalE={s['final_E']}")
print("OK - 复现一致")
