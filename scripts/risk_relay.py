"""Predefined stress/robustness checks; no parameter maximization or live trading."""
from smart_relay import SmartConfig,simulate,load_rows,add_months
from dataclasses import replace,asdict
from pathlib import Path
import datetime as dt
import json,math,hashlib

OUT=Path(__file__).parent.parent/'results'/'relay_risk'
BASE=SmartConfig(strategy='proportional')
CANDIDATES={
    'base':BASE,
    'borrow350':replace(BASE,borrow_ratio=3.5),
    'borrow400':replace(BASE,borrow_ratio=4),
    'both350':replace(BASE,borrow_ratio=3.5,sell_ratio=3.5),
    'own3years':replace(BASE,own_reserve_years=3),
    'cashfloor20':replace(BASE,reserve_years=20),
}

def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def transformed(rows,drag=0,shock_date=None,shock=0):
    out=[];d0=dt.date.fromisoformat(rows[0]['date'])
    for r in rows:
        t=(dt.date.fromisoformat(r['date'])-d0).days/365
        factor=(1-drag)**t*(1-shock if shock_date and r['date']>=shock_date else 1)
        x=dict(r)
        for key in ['adj_open','adj_close','adj_low','adj_high']:
            if key in x:x[key]*=factor
        out.append(x)
    return out

def synthetic(rates):
    """Deterministic counterexamples, never historical data or forecasts."""
    d=dt.date(2000,1,3);end=dt.date(1999+len(rates),12,31);last=d;p=100.;out=[]
    while d<=end:
        if d.weekday()<5:
            rate=rates[min(len(rates)-1,d.year-2000)]
            old=p;p*=(1+rate)**((d-last).days/365)
            out.append(dict(date=str(d),adj_open=p,adj_close=p,adj_low=p,adj_high=p))
            last=d
        d+=dt.timedelta(days=1)
    return out

def scenario_set(rows):
    return [
        ('historical',rows,{}),('rate4',rows,dict(interest=.04)),('rate6',rows,dict(interest=.06)),
        ('rate8',rows,dict(interest=.08)),('cash0',rows,dict(cash_yield=0)),
        ('cash1',rows,dict(cash_yield=.01)),('inflation2',rows,dict(inflation=.02)),
        ('inflation3',rows,dict(inflation=.03)),('cost_drag1',transformed(rows,drag=.01),{}),
        ('cost_drag2',transformed(rows,drag=.02),{}),('compound_daily',rows,dict(compound_interest=True)),
        ('renew200',rows,dict(renewal_floor=2)),('renew300',rows,dict(renewal_floor=3)),
        ('deny_renew_2008',rows,dict(deny_renew_from='2008-01-01')),
        ('block_new_2008',rows,dict(block_new_from='2008-01-01')),
        ('settlement3',rows,dict(settlement_days=3)),('rebalance_first',rows,dict(rebalance_first=True)),
        ('stock_haircut50',rows,dict(stock_haircut=.5)),
        ('extra_drop10',transformed(rows,shock_date='2008-11-20',shock=.1),{}),
        ('extra_drop20',transformed(rows,shock_date='2008-11-20',shock=.2),{}),
        ('combined',transformed(rows,drag=.01),dict(interest=.06,cash_yield=0,inflation=.02)),
        ('flat40',synthetic([0.]*40),{}),('smooth3_40',synthetic([.03]*40),{}),
        ('bear_then5_40',synthetic([-.05]*10+[.05]*30),{}),
    ]

def compact(r):
    return {k:r[k] for k in ['start','end_requested','end_actual','failure','net','ordinary_cash','credit_stock',
                              'credit_own_stock','debt','min_mmr','min_cash_years','financed_years','living_paid',
                              'max_drawdown','max_weight','max_net_stock_exposure']}

def failure_diagnostics(stress):
    diagnostics=[]
    for x in stress:
        if x['failure']:
            ac=x['credit_stock'];debt=x['debt'];cash=x['ordinary_cash']
            diagnostics.append(dict(candidate=x['candidate'],scenario=x['scenario'],failure=x['failure'],date=x['end_actual'],
                                    debt=debt,credit=ac,cash=cash,
                                    cash_repay_to200=max(0,debt-ac/2),
                                    stock_sale_repay_to200=max(0,2*debt-ac),
                                    cash_covers_all_debt=cash>=debt))
    return diagnostics

def main():
    OUT.mkdir(parents=True,exist_ok=True);rows=load_rows();scenarios=scenario_set(rows)
    stress=[];roll=[];main=[];cfgs={}
    for name,cfg in CANDIDATES.items():
        cfgs[name]=asdict(cfg)
        for label,prices,changes in scenarios:
            # Full sensitivity for original, common adversarial set for every candidate.
            if name!='base' and label not in ['historical','rate6','cash0','inflation2','extra_drop20','combined','flat40','bear_then5_40']:continue
            start='2000-01-03' if label in ['flat40','smooth3_40','bear_then5_40'] else '2000-03-27'
            r,annual,daily,events=simulate(prices,replace(cfg,**changes),start,prices[-1]['date'],trace=label=='historical')
            item=dict(candidate=name,scenario=label,**compact(r));stress.append(item)
            if label=='historical':
                main.append(item);save(name+'_annual.json',annual);save(name+'_daily.json',daily);save(name+'_events.json',events)
        starts={}
        for x in rows:
            d=dt.date.fromisoformat(x['date']);starts.setdefault((d.year,(d.month-1)//3),d)
        for years in [10,20]:
            for d in starts.values():
                end=add_months(d,12*years)-dt.timedelta(days=1)
                if str(end)>rows[-1]['date']:continue
                r,_,_,_=simulate(rows,cfg,str(d),str(end));roll.append(dict(candidate=name,years=years,**compact(r)))
        save('stress.json',stress);save('rolling.json',roll);print(name,'done',flush=True)
    save('main.json',main);save('configs.json',cfgs)
    # Failure-time liquidity and solvency diagnostic, no unmodelled rescue applied.
    save('failure_diagnostics.json',failure_diagnostics(stress))
    save('provenance.json',dict(source='data/qqq_daily.json',sha256=hashlib.sha256((Path(__file__).parent.parent/'data/qqq_daily.json').read_bytes()).hexdigest(),
                               baseline_reproduced=3723873.3692729925,synthetic='Deterministic scenarios, not historical data or forecasts'))

if __name__=='__main__':main()
