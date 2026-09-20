from pathlib import Path
from dataclasses import replace,asdict
import datetime as dt,json,hashlib,math
from collateral_relay import run,SmartConfig,RescueSettings,load_rows,clean,add_months
from risk_relay import transformed,synthetic

ROOT=Path(__file__).parent.parent;OUT=ROOT/'results'/'withdrawal_3pct';OUT.mkdir(parents=True,exist_ok=True)
RESCUE=RescueSettings(trigger=1.6,target=2)
BASE=SmartConfig(strategy='proportional',renewal_floor=1.4)
CONFIGS={'w2':replace(BASE,withdrawal=.02,reserve_years=15),
         'w25':replace(BASE,withdrawal=.025,reserve_years=12),
         'w3':replace(BASE,withdrawal=.03,reserve_years=10),
         'w3_floor15':replace(BASE,withdrawal=.03,reserve_years=15)}
def save(name,data):(OUT/name).write_text(json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def traced(rows,cfg,name,start,end):
    r,y,d,e=run(rows,cfg,RESCUE,start,end,True)
    for a in y:
        if not a['failure']:assert abs(a['reconciliation_error'])<.01
        assert a['financed_amount'] in [0,cfg.initial*cfg.withdrawal*(1+cfg.inflation)**(a['year']-int(start[:4]))]
    for a in d:
        assert abs(a['ordinary_total']+a['credit_total']+a['transit']-a['debt']-a['net'])<.01
        assert min(a['ordinary_cash'],a['credit_cash'],a['principal'],a['unpaid_interest'])>-.01
    assert r['principal_repaid']==r['interest_paid']==0
    tag=name+'_'+start
    save(tag+'_annual.json',y);save(tag+'_daily.json',d);save(tag+'_events.json',e)
    minimum=min(d,key=lambda x:x['ordinary_cash']) if d else None
    r.update(name=name,rescue=asdict(RESCUE),min_cash_date=minimum['date'] if minimum else None)
    return r
def main():
    rows=load_rows();end=rows[-1]['date'];main=[];rolling=[];stress=[]
    for name,cfg in CONFIGS.items():
        for start in ['2000-03-27','2009-03-09','2007-10-31','2020-02-19','2021-11-19']:
            main.append(traced(rows,cfg,name,start,end))
    save('main.json',main);print('Main cases done',flush=True)
    starts={}
    for row in rows:
        day=dt.date.fromisoformat(row['date']);starts.setdefault((day.year,(day.month-1)//3),day)
    for name,cfg in CONFIGS.items():
        for years in [10,20]:
            for day in starts.values():
                stop=add_months(day,years*12)-dt.timedelta(days=1)
                if str(stop)>end:continue
                r,_,_,_=run(rows,cfg,RESCUE,str(day),str(stop));r.update(name=name,years=years);rolling.append(r)
        # Additional full-to-end observation, separate from fixed horizon counts.
        for day in starts.values():
            if str(add_months(day,60))>end:continue
            r,_,_,_=run(rows,cfg,RESCUE,str(day),end);r.update(name=name,years='to_end_min5');rolling.append(r)
        print(name,'rolling done',flush=True)
    save('rolling.json',rolling)
    for name in ['w2','w3','w3_floor15']:
        for label,prices,changes in [
            ('cash0',rows,dict(cash_yield=0)),('rate4',rows,dict(interest=.04)),('rate6',rows,dict(interest=.06)),
            ('inflation2',rows,dict(inflation=.02)),('extra_drop20',transformed(rows,shock_date='2008-11-20',shock=.2),{}),
            ('flat40',synthetic([0.]*40),{}),('bear_then5_40',synthetic([-.05]*10+[.05]*30),{}),
            ('combined',transformed(rows,drag=.01),dict(cash_yield=0,interest=.04,inflation=.02))]:
            start='2000-01-03' if label in ['flat40','bear_then5_40'] else '2000-03-27'
            r,_,_,_=run(prices,replace(CONFIGS[name],**changes),RESCUE,start,prices[-1]['date'])
            r.update(name=name,scenario=label);stress.append(r)
    save('stress.json',stress)
    failures=[r for r in rolling if r['name']=='w3' and r['failure']]
    diagnostics=[]
    for start in sorted({r['start'] for r in failures}):
        r=traced(rows,CONFIGS['w3'],'failure_w3',start,end);diagnostics.append(r)
    save('failure_diagnostics.json',diagnostics)
    save('provenance.json',dict(research_date='2026-09-15',data_start=rows[0]['date'],data_end=end,rows=len(rows),
        data_sha256=hashlib.sha256((ROOT/'data'/'qqq_daily.json').read_bytes()).hexdigest(),
        configurations={k:asdict(v) for k,v in CONFIGS.items()},rescue=asdict(RESCUE),
        interpretation='annual borrowing budget and living spending both increase to 3%; baseline buy floor stays at 30% initial assets',
        failure_definitions=dict(LiquidityFailure='unable to pay full annual living budget on scheduled date',MarginFailure='credit maintenance below 140% research line')))
    print('Complete',len(main),len(rolling),len(stress),'failure starts',len(diagnostics),flush=True)

if __name__=='__main__':main()
