"""2026-09-15: partial financing, transfer first, living before rebalance.

Historical result folders are not overwritten. Broker approval timing remains
an execution assumption; partial_post300 isolates a stricter alternative.
"""
from pathlib import Path
from dataclasses import replace,asdict
import datetime as dt
import hashlib
import json
from collateral_relay import run,SmartConfig,RescueSettings,load_rows,clean,add_months
from risk_relay import transformed,synthetic
from stage_research import dispatch

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results'/'partial_living'
RESCUE=RescueSettings(trigger=1.6,target=2)
CONFIGS={name:SmartConfig(strategy='proportional',weight=w,withdrawal=b,
                         reserve_years=(1-w)/b,buy_cash_weight=1-w,renewal_floor=1.4,
                         living_finance_mode='partial_transfer_first')
         for name,w,b in [('relay70',.7,.02),('relay80',.8,.02),('relay70_w3',.7,.03)]}

def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def checked(rows,cfg,name,start,end,trace=False):
    r,y,d,e=run(rows,cfg,RESCUE,start,end,trace)
    r.update(name=name,rescue=asdict(RESCUE))
    assert r['interest_paid']==r['principal_repaid']==0
    for a in y:
        if not a['failure']:assert abs(a['reconciliation_error'])<.01
        if 'budget' in a:
            assert abs(a['financed_amount']+a['cash_topup_planned']-a['budget'])<.01
            assert -.01<=a['financed_amount']<=a['budget']+.01
    if trace:
        for a in d:
            assert abs(a['ordinary_total']+a['credit_total']+a['transit']-a['debt']-a['net'])<.01
            assert min(a['ordinary_cash'],a['credit_cash'],a['principal'],a['unpaid_interest'],a['credit_own_stock'])>-.01
        for a in y:
            kinds=[x['kind'] for x in e if x['date'][:4]==str(a['year'])]
            if 'rebalance_decision' in kinds:
                assert kinds.index('living_payment')<kinds.index('rebalance_decision')
        for event in e:
            if event['kind']=='living_collateral_transfer':assert event['ratio'] is None or event['ratio']>=3-1e-7
            if event['kind']=='living_finance_decision':assert event['margin_after']>=-1e-7
        if d:r['min_cash_date']=min(d,key=lambda x:x['ordinary_cash'])['date']
        r['financing_ends_below300']=sum(x['kind']=='living_finance_decision' and x['ratio_after']<3-1e-7 for x in e)
        tag=name+'_'+start
        save(tag+'_annual.json',y);save(tag+'_daily.json',d);save(tag+'_events.json',e)
    return r

def main():
    rows=load_rows();end=rows[-1]['date'];main=[];comparisons=[];rolling=[];stress=[]
    old_stage=json.loads((ROOT/'results/cash_relay_stage/report_main.json').read_text(encoding='utf-8'))
    old_w3=json.loads((ROOT/'results/withdrawal_3pct/main.json').read_text(encoding='utf-8'))
    for name,cfg in CONFIGS.items():
        for start in ['2000-03-27','2009-03-09','2007-10-31','2020-02-19','2021-11-19']:
            r=checked(rows,cfg,name,start,end,True);main.append(r)
            old_name='w3' if name=='relay70_w3' else name
            src=old_w3 if name=='relay70_w3' else old_stage
            old=next(x for x in src if x['name']==old_name and x['start']==start)
            reproduced=checked(rows,replace(cfg,living_finance_mode='full_post300'),name,start,end)
            for key in ['net','debt','min_mmr','min_cash_years','living_paid','rescue_cash_in']:
                assert abs(old[key]-reproduced[key])<.005,(name,start,key,old[key],reproduced[key])
            comparisons.append(dict(name=name,start=start,old=old,new=r))
        print(name,'main and old regression passed',flush=True)
    for start in ['2000-03-27','2009-03-09']:
        for name in ['sale80','pal80']:
            r,y,d,e=dispatch(rows,name,start,end,trace=True);r['name']=name
            old=next(x for x in old_stage if x['name']==name and x['start']==start)
            assert abs(old['net']-r['net'])<.005
            main.append(r)
        for name,cfg in CONFIGS.items():
            r=checked(rows,replace(cfg,living_finance_mode='partial_post300'),name,start,end)
            r['scenario']='partial_post300';stress.append(r)
    save('main.json',main);save('old_vs_new.json',comparisons)
    starts={}
    for row in rows:
        day=dt.date.fromisoformat(row['date']);starts.setdefault((day.year,(day.month-1)//3),day)
    for name,cfg in CONFIGS.items():
        for years in [10,20]:
            for day in starts.values():
                stop=add_months(day,years*12)-dt.timedelta(days=1)
                if str(stop)>end:continue
                r=checked(rows,cfg,name,str(day),str(stop));r['years']=years;rolling.append(r)
        print(name,'rolling done',flush=True)
        for label,prices,changes in [
            ('cash0',rows,dict(cash_yield=0)),('rate4',rows,dict(interest=.04)),('rate6',rows,dict(interest=.06)),
            ('inflation2',rows,dict(inflation=.02)),('extra_drop20',transformed(rows,shock_date='2008-11-20',shock=.2),{}),
            ('flat40',synthetic([0.]*40),{}),('bear_then5_40',synthetic([-.05]*10+[.05]*30),{}),
            ('combined',transformed(rows,drag=.01),dict(cash_yield=0,interest=.04,inflation=.02))]:
            start='2000-01-03' if label in ['flat40','bear_then5_40'] else '2000-03-27'
            r=checked(prices,replace(cfg,**changes),name,start,prices[-1]['date']);r['scenario']=label;stress.append(r)
        print(name,'stress done',flush=True)
    save('rolling.json',rolling);save('stress.json',stress)
    save('provenance.json',dict(research_date='2026-09-15',data_end=end,
        data_sha256=hashlib.sha256((ROOT/'data/qqq_daily.json').read_bytes()).hexdigest(),
        configurations={k:asdict(v) for k,v in CONFIGS.items()},rescue=asdict(RESCUE),
        operation='transfer eligible own securities first at existing debt; finance equal amount; sell transferred securities after settlement; pay living; rebalance',
        capacity='min(budget, credit_assets - 3*existing_debt, own_stock, margin_available/(stock_haircut+financing_margin_ratio))',
        execution_assumption='transfer eligibility judged before the subsequent financing, not rechecked at end of day using the new loan',
        cash_topup_planned='annual budget minus new loan principal; actual sale proceeds can differ due to settlement price movement',
        validation='old results reproduced; double-account equity and annual P&L reconciled; no repayment; margin and transfer constraints; living precedes rebalancing',
        counts=dict(main=len(main),rolling=len(rolling),stress=len(stress))))
    print('Complete',len(main),len(rolling),len(stress),flush=True)

if __name__=='__main__':main()
