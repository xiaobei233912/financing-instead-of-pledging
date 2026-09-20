# -*- coding: utf-8 -*-
"""final_runs.py —— 用最终稳健参数(sdd0.6/smmr1.5/rlo5/twoway)产出最终对比与敏感性"""
import pandas as pd, numpy as np
from pal_engine import Params, simulate

data=pd.read_csv("data/qqq_daily.csv",parse_dates=["date"])
ROB=dict(borrow_stress_dd=0.6,borrow_stress_mmr=1.5,runway_lo=5,rebalance="twoway")
starts=[data["date"].iloc[i] for i in range(126,len(data)-2520,126)]  # 半年滚动

def one(mode,start="2000-03-27",**kw):
    return simulate(data,mode,Params(**kw),start=start)[1]
def roll(mode,**kw):
    rr=[simulate(data,mode,Params(**kw),start=st)[1] for st in starts]
    return (sum(1 for x in rr if x["status"]!="ok"),
            round(min(x["min_mmr"] for x in rr),3),
            round(min(x["min_runway"] for x in rr),2),
            round(np.median([x["final_E"] for x in rr]),3))

print("="*95)
print("【表1】2000-03-27 顶点压力测试 全模式对比 (w=2%)")
print("="*95)
rows=[]
for b in [0.7,0.6]:
  for m in ["A","B","C0","C1","C2"]:
    kw=dict(stock_target=b,withdraw=.02,rebalance="twoway")
    if m=="C1": kw.update(ROB)
    if m=="C2": kw.update(dd_freeze=.25,defensive_beta=.5,rebalance="twoway")
    s=one(m,**kw); s["beta"]=b; rows.append(s)
t1=pd.DataFrame(rows)
c=["beta","mode","status","fail_date","min_mmr","min_mmr_date","min_runway",
   "max_debt","total_interest","final_E","avg_wQ","y_wQ_lt_05"] if "y_wQ_lt_05" in t1 else \
  ["beta","mode","status","fail_date","min_mmr","min_mmr_date","min_runway",
   "max_debt","total_interest","final_E","avg_wQ"]
print(t1[["beta","mode","status","fail_date","min_mmr","min_runway","max_debt",
          "total_interest","final_E","avg_wQ"]].to_string(index=False))
t1.to_csv("data/final_table1_stress.csv",index=False,encoding="utf-8-sig")

print("\n"+"="*95)
print("【表2】稳健 C1：利率×现金收益 (2000顶点 beta0.7 w2%) + 半年滚动")
print("="*95)
rows=[]
for mr in [.028,.04,.056]:
  for cy in [.01,.02,.03]:
    kw=dict(stock_target=.7,withdraw=.02,margin_rate=mr,cash_yield=cy,**ROB)
    s=one("C1",**kw); nf,mm,mr2,me=roll("C1",**kw)
    rows.append((mr,cy,s["status"],s["min_mmr"],s["min_runway"],round(s["max_debt"],3),
                 round(s["total_interest"],3),round(s["final_E"],3),nf,mr2))
print(pd.DataFrame(rows,columns=["融资利率","现金收益","2000状态","minMMR","minRun",
  "maxDebt","利息","finalE","滚动失败","滚动最差MMR"]).to_string(index=False))

print("\n"+"="*95)
print("【表3】稳健 C1：提取率×beta (2000 + 滚动)")
print("="*95)
rows=[]
for w in [.02,.025,.03]:
  for b in [.7,.6,.5]:
    kw=dict(stock_target=b,withdraw=w,**ROB)
    s=one("C1",**kw); nf,mm,mrun,me=roll("C1",**kw)
    rows.append((w,b,s["status"],s["min_mmr"],s["min_runway"],round(s["final_E"],3),nf,mrun))
print(pd.DataFrame(rows,columns=["提取率","beta","2000状态","minMMR","minRun","finalE",
  "滚动失败","滚动最差run"]).to_string(index=False))

print("\n"+"="*95)
print("【表4】半年滚动起始(34个起点)全模式零失败验证 beta0.7 w2%")
print("="*95)
for m in ["A","B","C1","C2"]:
    kw=dict(stock_target=.7,withdraw=.02,rebalance="twoway")
    if m=="C1": kw.update(ROB)
    if m=="C2": kw.update(dd_freeze=.25,defensive_beta=.5)
    print(m, "->  失败数/最差MMR/最差run/期末E中位数 =", roll(m,**kw))

print("\n"+"="*95)
print("【表5】推荐 C1(beta0.7) 2000 起步 年度明细")
print("="*95)
out,s=simulate(data,"C1",Params(stock_target=.7,withdraw=.02,**ROB),start="2000-03-27")
out["y"]=out["date"].dt.year
yr=out.groupby("y").last()[["A","L","E","wQ","MMR","ordinary","runway","P","I"]].round(3)
print(yr.head(17).to_string())
yr.to_csv("data/final_table5_annual.csv",encoding="utf-8-sig")
print("\nDONE")
