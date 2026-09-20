"""Append the explicit larger shock without re-running unchanged rolling windows."""
from collateral_relay import *
stress=json.loads((OUT/'stress.json').read_text(encoding='utf-8'))
stress=[r for r in stress if r['scenario']!='extra_drop40']
rows=transformed(load_rows(),shock_date='2008-11-20',shock=.4)
for weight,floor,label in [(.7,15,'70'),(.8,10,'80')]:
    cfg=SmartConfig(strategy='proportional',weight=weight,reserve_years=floor,buy_cash_weight=1-weight,renewal_floor=1.4)
    for mode,s in {'none':None,'a180':RescueSettings(),'auto180':RescueSettings(auto_interest=True,security=False),'a160':RescueSettings(trigger=1.6,target=2),'a200':RescueSettings(trigger=2,target=2.4)}.items():
        r,_,_,_=run(rows,cfg,s)
        r.update(name=label+'_'+mode,scenario='extra_drop40',rescue=asdict(s) if s else None)
        stress.append(r)
save('stress.json',stress)
