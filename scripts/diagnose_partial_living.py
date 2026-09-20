"""Inspect payment failures without equating a missed payment with insolvency."""
from dataclasses import replace
import json
from run_partial_living import OUT,CONFIGS,RESCUE,save,load_rows,run
from risk_relay import transformed,synthetic

rows=load_rows()
scenarios={
    'cash0':(rows,dict(cash_yield=0)),
    'rate6':(rows,dict(interest=.06)),
    'inflation2':(rows,dict(inflation=.02)),
    'extra_drop20':(transformed(rows,shock_date='2008-11-20',shock=.2),{}),
    'flat40':(synthetic([0.]*40),{}),
    'bear_then5_40':(synthetic([-.05]*10+[.05]*30),{}),
    'combined':(transformed(rows,drag=.01),dict(cash_yield=0,interest=.04,inflation=.02)),
}
diagnostics=[]
for old in json.loads((OUT/'stress.json').read_text(encoding='utf-8')):
    if not old['failure']:continue
    prices,changes=scenarios[old['scenario']]
    r,y,d,e=run(prices,replace(CONFIGS[old['name']],**changes),RESCUE,old['start'],prices[-1]['date'],True)
    assert r['failure']==old['failure'] and abs(r['net']-old['net'])<.01
    r.update(name=old['name'],scenario=old['scenario'],
             payment_budget=y[-1].get('budget'),
             shortfall=max(0,y[-1].get('budget',0)-r['bank_liquid']),
             last_events=e[-12:])
    diagnostics.append(r)
save('failure_diagnostics.json',diagnostics)
print(json.dumps([{k:r[k] for k in ['name','scenario','date','mmr','ordinary_cash','credit_cash',
                                 'available_own_stock_transfer','shortfall']} for r in diagnostics],indent=2))
