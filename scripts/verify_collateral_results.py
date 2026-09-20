from collateral_relay import *
main=json.loads((OUT/'main.json').read_text(encoding='utf-8'))
max_error=0.;days=0;years=0
for r in main:
    name=r['name']
    annual=json.loads((OUT/(name+'_annual.json')).read_text(encoding='utf-8'))
    daily=json.loads((OUT/(name+'_daily.json')).read_text(encoding='utf-8'))
    events=json.loads((OUT/(name+'_events.json')).read_text(encoding='utf-8'))
    for d in daily:
        assert abs(d['credit_stock']+d['credit_cash']-d['credit_total'])<.01
        assert abs(d['ordinary_total']+d['credit_total']+d['transit']-d['total_assets'])<.01
        assert abs(d['net']-d['total_assets']+d['principal']+d['unpaid_interest'])<.01
        assert min(d['ordinary_cash'],d['credit_cash'],d['principal'],d['unpaid_interest'])>-.01
    for y in annual:
        max_error=max(max_error,abs(y['reconciliation_error']))
        assert abs(y['reconciliation_error'])<.01
        assert y['financed_amount']==(20000 if y['financed'] else 0)
    for e in events:
        if e['kind']=='rebalance_decision':
            assert e['buy']<=max(0,e['cash_before']-r['config']['reserve_years']*20000)+.01
    if r['rescue'] and r['rescue']['security']:
        assert r['principal_repaid']==r['interest_paid']==0
    days+=len(daily);years+=len(annual)
for weight,n,name in [(.7,15,'70'),(.8,10,'80')]:
    cfg=SmartConfig(strategy='proportional',weight=weight,reserve_years=n,buy_cash_weight=1-weight,renewal_floor=1.4)
    for mode,s in [('none',None),('a180',RescueSettings())]:
        fresh,_,_,_=run(load_rows(),cfg,s)
        old=next(r for r in main if r['name']==name+'_'+mode)
        for key in ['net','min_mmr','min_cash_years','rescue_cash_in','rescue_cash_return']:
            assert abs(fresh[key]-old[key])<1e-6,(name,mode,key)
save('verification.json',dict(historical_daily_rows=days,historical_annual_rows=years,max_annual_reconciliation_error=max_error,
    fresh_baselines_reproduced=True,credit_cash_not_double_counted=True,zero_voluntary_repayment_checked=True))
print('Verified',days,'daily rows,',years,'annual rows; max reconciliation error',max_error)
