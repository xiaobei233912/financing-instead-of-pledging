"""Fixed, non-optimized validation set for source audit and operational policies."""
import concurrent.futures as cf
import datetime as dt
import json
import statistics
from pathlib import Path
from gated_engine import GateConfig, simulate_gate, load_rows

HERE=Path(__file__).resolve().parent
ROWS=None


def work(job):
    global ROWS
    if ROWS is None:ROWS=load_rows()
    label,start,end,kw=job
    r,_,_=simulate_gate(ROWS,GateConfig(**kw),start,end)
    r['experiment']=label
    return r


def main():
    rows=load_rows()
    results=[]
    base=dict(weight=.7,cash_yield=.02,interest=.028,guard_runway=3.)
    choices=[('A',dict(strategy='A')),
             ('D_hold',dict(strategy='D_hold',never_repay=True)),
             ('D_hang',dict(strategy='D_hang',pay_monthly_interest=False)),
             ('D_pay',dict(strategy='D_pay',pay_monthly_interest=True,refinance_interest=False)),
             ('D_refinance',dict(strategy='D_refinance',pay_monthly_interest=True,refinance_interest=True))]
    for cal in ['252','yearend']:
        for name,kw in choices:
            cfg=GateConfig(**base,**kw,rebal_calendar=cal)
            r,ledger,events=simulate_gate(rows,cfg,trace=True)
            r['experiment']='main_'+cal
            results.append(r)
            (HERE/'output'/f'strict_{name}_{cal}_daily.jsonl').write_text('\n'.join(json.dumps(x,allow_nan=False) for x in ledger),encoding='utf-8')
            (HERE/'output'/f'strict_{name}_{cal}_events.json').write_text(json.dumps(events,indent=2,allow_nan=False),encoding='utf-8')
            print('main',name,cal,r['failure'],r['final_net']/1e6,r['min_mmr'],r['min_runway'],flush=True)
    jobs=[]
    starts=[]
    seen=set()
    for r in rows:
        d=dt.date.fromisoformat(r['date'])
        if d.month in [1,4,7,10] and (d.year,d.month) not in seen:
            seen.add((d.year,d.month))
            if d<dt.date(2016,9,4):starts.append(str(d))
    for start in starts:
        for name,kw in choices:
            args={**base,**kw,'rebal_calendar':'yearend'}
            jobs.append(('rolling_to_end_min10y',start,'2026-09-04',args))
            d=dt.date.fromisoformat(start)
            end=dt.date(d.year+10,d.month,d.day)-dt.timedelta(days=1)
            jobs.append(('fixed10y',start,str(end),args))
    scenarios=[('rate4',{'interest':.04}),('rate56',{'interest':.056}),
               ('cash1',{'cash_yield':.01}),('cash3',{'cash_yield':.03}),
               ('cash15',{'cash_yield':.015}),('settlement3',{'settlement_days':3}),
               ('margin300',{'margin_requirement':3.}),('stock60',{'weight':.6}),
               ('stock80',{'weight':.8}),('inflation2',{'inflation':.02}),
               ('withdraw25',{'withdrawal':.025}),('withdraw3',{'withdrawal':.03}),
               ('renew160',{'renew_min_ratio':1.6}),('renew300',{'renew_min_ratio':3.}),
               ('deny_renew_2008',{'deny_renew_from':'2008-01-01'}),
               ('deny_renew_and_new_2008',{'deny_renew_from':'2008-01-01','block_new_from':'2008-01-01'}),
               ('joint_adverse',{'cash_yield':0.,'interest':.06,'inflation':.02}),
               ('no_runway_exit',{'guard_runway':0.}),('no_credit_switch',{'credit_switch':False}),
               ('rebalance_clear',{'liquidate_for_rebalance':True})]
    for name,kw in choices:
        for label,params in scenarios:
            jobs.append((label,'2000-03-27','2026-09-04',{**base,**kw,'rebal_calendar':'yearend',**params}))
    print('Queued',len(jobs),'jobs with',len(starts),'quarterly starts',flush=True)
    with cf.ProcessPoolExecutor(max_workers=6) as pool:
        for i,r in enumerate(pool.map(work,jobs,chunksize=2),1):
            results.append(r)
            if i%60==0:print('Completed',i,'/',len(jobs),flush=True)
    (HERE/'output/strict_results.json').write_text(json.dumps(results,indent=2,allow_nan=False),encoding='utf-8')
    groups=[]
    for horizon in ['rolling_to_end_min10y','fixed10y']:
        group=[r for r in results if r['experiment']==horizon]
        bases={r['start']:r for r in group if r['config']['strategy']=='A'}
        for strategy in ['A','D_hold','D_hang','D_pay','D_refinance']:
            rs=[r for r in group if r['config']['strategy']==strategy]
            advantage=[r['final_net']/bases[r['start']]['final_net']-1 for r in rs if not r['failure'] and not bases[r['start']]['failure']]
            mm=[r['min_mmr'] for r in rs if r['min_mmr'] is not None]
            groups.append(dict(horizon=horizon,strategy=strategy,n=len(rs),failures=sum(bool(r['failure']) for r in rs),
                               min_mmr=min(mm) if mm else None,min_runway=min(r['min_runway'] for r in rs),
                               median_advantage=statistics.median(advantage),win_fraction=sum(x>0 for x in advantage)/len(advantage),
                               min_weight=min(r['min_weight'] for r in rs),max_under_half_run=max(r['longest_under_half'] for r in rs)))
    (HERE/'output/strict_rolling_summary.json').write_text(json.dumps(groups,indent=2),encoding='utf-8')
    print('Done',len(results),'cases.',flush=True)


if __name__=='__main__':main()
