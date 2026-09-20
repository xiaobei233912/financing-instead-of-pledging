"""Confirmed asymmetric rebalancing with initial-asset cash floor."""
from relay_backtest import RelayConfig, simulate, load_rows, add_months
from dataclasses import replace
from pathlib import Path
import datetime as dt
import json
import hashlib

OUT=Path(__file__).parent.parent/'results'/'7030_relay_v2'

def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=load_rows();cases=[];rolling=[];sensitivity=[]
    for trigger in [.3]:
        cfg=RelayConfig(buy_cash_weight=trigger)
        tag=f'cash_trigger_{round(trigger*100)}'
        for start in ['1999-03-10','2000-03-27','2007-10-31','2020-02-19','2021-11-19']:
            r,ledger,events,annual=simulate(rows,cfg,start,trace=True)
            r['branch']=tag;cases.append(r)
            save(f'{tag}_{start}_daily.json',ledger)
            save(f'{tag}_{start}_events.json',events)
            save(f'{tag}_{start}_annual.json',annual)
            assert all(d['credit_cash_assets']==0 for d in ledger)
        starts={}
        for r in rows:
            d=dt.date.fromisoformat(r['date']);starts.setdefault((d.year,(d.month-1)//3),d)
        for years in [10,20]:
            for d in starts.values():
                end=add_months(d,years*12)-dt.timedelta(days=1)
                if str(end)>rows[-1]['date']:continue
                r,_,_,_=simulate(rows,cfg,str(d),str(end));r.update(years=years,branch=tag);rolling.append(r)
        for label,c in [('cash_0',replace(cfg,cash_yield=0)),('rate_4',replace(cfg,interest=.04)),
                        ('rate_6',replace(cfg,interest=.06)),('settlement_3',replace(cfg,settlement_days=3)),
                        ('precheck_only',replace(cfg,gate='buy_only')),
                        ('renewal_200',replace(cfg,renewal_floor=2))]:
            r,_,_,_=simulate(rows,c,'2000-03-27');r.update(variant=label,branch=tag);sensitivity.append(r)
        print(tag,'done',flush=True)
    summary=[]
    for tag in ['cash_trigger_30']:
        for years in [10,20]:
            group=[r for r in rolling if r['branch']==tag and r['years']==years]
            summary.append(dict(branch=tag,years=years,n=len(group),failures=sum(bool(r['failure']) for r in group),
                                min_net=min(r['final_net'] for r in group),min_mmr=min(r['min_mmr'] for r in group),
                                min_cash_years=min(r['min_cash_years'] for r in group),
                                failed=[dict(start=r['start'],date=r['end_actual'],reason=r['failure']) for r in group if r['failure']]))
    save('stress.json',cases);save('rolling.json',rolling);save('rolling_summary.json',summary);save('sensitivity.json',sensitivity)
    save('provenance.json',dict(data_sha256=hashlib.sha256((Path(__file__).parent.parent/'data/qqq_daily.json').read_bytes()).hexdigest(),
                               rows=len(rows),start=rows[0]['date'],end=rows[-1]['date']))
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
