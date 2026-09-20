"""Refresh deterministic scenarios after tightening their end to 40 calendar years."""
from risk_relay import *

stress=json.loads((OUT/'stress.json').read_text(encoding='utf-8'))
scens={label:(rows,chg) for label,rows,chg in scenario_set(load_rows())}
for idx,x in enumerate(stress):
    if x['scenario'] not in ['flat40','smooth3_40','bear_then5_40']:continue
    rows,changes=scens[x['scenario']]
    r,_,_,_=simulate(rows,replace(CANDIDATES[x['candidate']],**changes),'2000-01-03',rows[-1]['date'])
    stress[idx]=dict(candidate=x['candidate'],scenario=x['scenario'],**compact(r))
save('stress.json',stress);save('failure_diagnostics.json',failure_diagnostics(stress))
r,annual,_,_=simulate(load_rows(),replace(BASE,financing=False))
save('no_finance_benchmark.json',dict(result=compact(r),annual=annual))
print('Synthetic endpoints and no-finance benchmark saved.')
