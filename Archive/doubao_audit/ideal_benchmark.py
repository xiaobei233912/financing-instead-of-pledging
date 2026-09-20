"""Ideal PAL: unrestricted borrowing, simple accrued interest by default.
Same one-year pre-funded startup, anniversary spending and year-end weights as D.
No ordinary/credit split: intentionally an unattainable mainland upper benchmark.
"""
import datetime as dt
import json
from pathlib import Path
from gated_engine import GateConfig, load_rows, add_months


def ideal(rows, cfg, start='2000-03-27', end='2026-09-04'):
    selected=[r for r in rows if start<=r['date']<=end]
    dates=[dt.date.fromisoformat(r['date']) for r in selected]
    due={0:cfg.initial*cfg.withdrawal}
    for y in range(1,100):
        d=add_months(dates[0],12*y)
        if d>dates[-1]:break
        j=next(i for i,x in enumerate(dates) if x>=d)
        due[j]=cfg.initial*cfg.withdrawal*(1+cfg.inflation)**y
    yearends={}
    for r in rows:
        if r['date'][5:7]=='12':yearends[r['date'][:4]]=r['date']
    q=cfg.initial*cfg.weight/selected[0]['adj_close']
    cash=cfg.initial*(1-cfg.weight)
    principal=interest=interest_total=spent=0.
    mmr=float('inf'); max_debt=0.;monthly=None;failure=None
    for i,(r,d) in enumerate(zip(selected,dates)):
        elapsed=(d-dates[i-1]).days if i else 0
        cash*=(1+cfg.cash_yield)**(elapsed/365)
        cost=principal*cfg.interest*elapsed/365
        interest+=cost;interest_total+=cost
        p=r['adj_open'] if i else r['adj_close']
        for price in [p]:
            if principal+interest:
                mmr=min(mmr,(q*price+cash)/(principal+interest))
        if mmr<cfg.safe_ratio:failure='MarginFailure';break
        month=(d.year,d.month)
        if cfg.pay_monthly_interest and d.day>=21 and month!=monthly:
            principal+=interest;interest=0.;monthly=month
        if i in due:
            spent+=due[i]
            if i==0:cash-=due[i]
            else:principal+=due[i]
        if i==0 or str(d) in yearends.values():
            assets=q*p+cash;q=cfg.weight*assets/p;cash=(1-cfg.weight)*assets
        if principal+interest:
            mmr=min(mmr,(q*(r['adj_low'] if i else p)+cash)/(principal+interest))
        max_debt=max(max_debt,principal+interest)
        if mmr<cfg.safe_ratio:failure='MarginFailure';p=r['adj_low'];break
        p=r['adj_close']
    return dict(strategy='B_ideal',start=str(dates[0]),end_actual=str(d),failure=failure,
                final_net=q*p+cash-principal-interest,final_debt=principal+interest,
                interest=interest_total,living=spent,min_mmr=mmr,max_debt=max_debt,
                convention='startup self-funded; later anniversary spending; '+('monthly interest capitalization' if cfg.pay_monthly_interest else 'simple unpaid accrued interest')+'; calendar year-end rebalancing')


if __name__=='__main__':
    results={name:ideal(load_rows(),GateConfig(pay_monthly_interest=flag))
             for name,flag in [('B_hang',False),('B_capitalize',True)]}
    Path(__file__).with_name('output').joinpath('ideal_benchmark.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
