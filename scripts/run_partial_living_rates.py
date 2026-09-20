"""Refresh all current-report cases: cash 1%, financing 3% simple unpaid."""
from dataclasses import replace,asdict
import datetime as dt
import json
import hashlib
import run_partial_living as p
from stage_research import plain
from risk_relay import transformed,synthetic

OLD=p.OUT
p.OUT=p.ROOT/'results/partial_living_cash1_rate3'
CONFIGS={n:replace(c,cash_yield=.01,interest=.03) for n,c in p.CONFIGS.items()}

def main():
    rows=p.load_rows();end=rows[-1]['date'];main=[];rolling=[];stress=[];prior=[];order=[]
    old=json.loads((OLD/'main.json').read_text(encoding='utf-8'))
    for n,c in CONFIGS.items():
        for start in ['2000-03-27','2009-03-09','2007-10-31','2020-02-19','2021-11-19']:
            r=p.checked(rows,c,n,start,end,True);main.append(r)
            prior.append(dict(name=n,start=start,old=next(x for x in old if x['name']==n and x['start']==start),new=r))
        for start in ['2000-03-27','2009-03-09']:
            for mode in ['full_post300','partial_post300']:
                r=p.checked(rows,replace(c,living_finance_mode=mode),n,start,end)
                r['mode']=mode;order.append(r)
        print(n,'main done',flush=True)
    for start in ['2000-03-27','2009-03-09']:
        for n in ['sale80','pal80']:
            r,y,d,e=plain(rows,start,end,.8,pal=n=='pal80',cash_yield=.01,interest=.03,
                          compound=n=='pal80',pal_rebalance=n=='pal80')
            r['name']=n;main.append(r)
            prior.append(dict(name=n,start=start,old=next(x for x in old if x['name']==n and x['start']==start),new=r))
            tag=n+'_'+start;p.save(tag+'_annual.json',y);p.save(tag+'_daily.json',d)
    p.save('main.json',main);p.save('rate_comparison.json',prior);p.save('order_comparison.json',order)
    starts={}
    for row in rows:
        day=dt.date.fromisoformat(row['date']);starts.setdefault((day.year,(day.month-1)//3),day)
    scenarios=[('cash0',rows,dict(cash_yield=0)),('rate4',rows,dict(interest=.04)),('rate6',rows,dict(interest=.06)),
               ('inflation2',rows,dict(inflation=.02)),('extra_drop20',transformed(rows,shock_date='2008-11-20',shock=.2),{}),
               ('flat40',synthetic([0.]*40),{}),('bear_then5_40',synthetic([-.05]*10+[.05]*30),{}),
               ('combined',transformed(rows,drag=.01),dict(cash_yield=0,interest=.04,inflation=.02))]
    diagnostics=[]
    for n,c in CONFIGS.items():
        for years in [10,20]:
            for day in starts.values():
                stop=p.add_months(day,years*12)-dt.timedelta(days=1)
                if str(stop)>end:continue
                r=p.checked(rows,c,n,str(day),str(stop));r['years']=years;rolling.append(r)
        for label,prices,changes in scenarios:
            start='2000-01-03' if label in ['flat40','bear_then5_40'] else '2000-03-27'
            r=p.checked(prices,replace(c,**changes),n,start,prices[-1]['date']);r['scenario']=label;stress.append(r)
            if r['failure']:
                r['shortfall']=max(0,replace(c,**changes).initial*c.withdrawal*(1+changes.get('inflation',0))**(int(r['date'][:4])-int(start[:4]))-r['bank_liquid'])
                diagnostics.append(r)
        print(n,'rolling and stress done',flush=True)
    p.save('rolling.json',rolling);p.save('stress.json',stress);p.save('failure_diagnostics.json',diagnostics)
    p.save('provenance.json',dict(data_end=end,data_sha256=hashlib.sha256((p.ROOT/'data/qqq_daily.json').read_bytes()).hexdigest(),
        configurations={n:asdict(c) for n,c in CONFIGS.items()},rescue=asdict(p.RESCUE),
        benchmarks='cash 1%; sale80 no borrowing; PAL 3% effective compound unpaid; annual 80/20, 2% initial living',
        counts=dict(main=len(main),rolling=len(rolling),stress=len(stress),order=len(order)),
        sensitivity='Stress overrides labeled explicitly; all unspecified parameters use cash 1%, financing 3%.'))
    print('Finished',len(main),len(rolling),len(stress),len(order),flush=True)

if __name__=='__main__':main()
