# -*- coding: utf-8 -*-
"""grid_fast.py —— 精简参数网格（半年滚动起始），用全历史最差情形(minimax)选稳健参数"""
import pandas as pd, numpy as np
from pal_engine import Params, simulate

data=pd.read_csv("data/qqq_daily.csv",parse_dates=["date"])
starts=[data["date"].iloc[i] for i in range(126, len(data)-2520, 126)]
print("滚动起始点数:",len(starts))

rows=[]
for sdd in [0.4,0.5,0.6]:
  for smmr in [1.4,1.5]:
    for rlo in [2,3,5]:
      for beta in [0.7,0.6]:
        kw=dict(stock_target=beta,withdraw=0.02,rebalance="twoway",
                borrow_stress_dd=sdd,borrow_stress_mmr=smmr,runway_lo=rlo)
        _,s0=simulate(data,"C1",Params(**kw),start="2000-03-27")
        rr=[]
        for st in starts:
            _,ss=simulate(data,"C1",Params(**kw),start=st); rr.append(ss)
        nf=sum(1 for x in rr if x["status"]!="ok")
        rows.append(dict(beta=beta,sdd=sdd,smmr=smmr,rlo=rlo,
            s2000=s0["status"],r2000=round(s0["min_runway"],2),mmr2000=s0["min_mmr"],
            fE2000=round(s0["final_E"],3),roll_fail=nf,
            roll_minrun=round(min(x["min_runway"] for x in rr),2),
            roll_minmmr=round(min(x["min_mmr"] for x in rr),3),
            medE=round(np.median([x["final_E"] for x in rr]),3)))
g=pd.DataFrame(rows)
pd.set_option("display.width",200)
print(g.to_string(index=False))
g.to_csv("data/results_paramgrid_fast.csv",index=False,encoding="utf-8-sig")
