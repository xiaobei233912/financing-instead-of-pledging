from stage_research import *
main=json.loads((OUT/'main.json').read_text(encoding='utf-8'))
pal=json.loads((OUT/'pal_main.json').read_text(encoding='utf-8'))
rolling=json.loads((OUT/'rolling.json').read_text(encoding='utf-8'))
palrolling=json.loads((OUT/'pal_rolling.json').read_text(encoding='utf-8'))
names=list(configs())+['sale70','sale80','sale100','sale_floor70','sale_floor80','pal80']
main=[r for r in main+pal if r['name'] in names]
rolling=[r for r in rolling+palrolling if r['name'] in names]
maxerr=0.;years=days=0
for r in main:
    tag=r['name']+'_'+r['start']
    yy=json.loads((OUT/(tag+'_annual.json')).read_text(encoding='utf-8'))
    dd=json.loads((OUT/(tag+'_daily.json')).read_text(encoding='utf-8'))
    for y in yy:
        if not y['failure']:
            err=abs(y['reconciliation_error']);maxerr=max(maxerr,err);assert err<.01
    for d in dd:
        assert abs(d['total_assets']-d['debt']-d['net'])<.01
        assert min(d['ordinary_cash'],d['principal'],d['unpaid_interest'])>-.01
    assert r['principal_repaid']==r['interest_paid']==0
    years+=len(yy);days+=len(dd)
save('report_main.json',main);save('report_rolling.json',rolling)
save('verification.json',dict(annual_records=years,daily_records=days,max_annual_reconciliation_error=maxerr,
    source_hash=hashlib.sha256((ROOT/'data/qqq_daily.json').read_bytes()).hexdigest(),
    confirmed_pal=dict(weight=.8,annual_target_rebalance=True,withdrawal=.02,interest=.03,compound=True,
        interest_convention='3% effective annual, natural days/365, interest capitalized',
        collateral='whole 80/20 portfolio',liquidity='direct cash lending, no mainland 300% transfer rule',
        maintenance='hypothetical 140% common research floor, not a verified PAL product limit'),
    confirmed_relay_rescue=asdict(RESCUE)))
print('verified',len(main),'main comparisons',len(rolling),'rolling windows',years,'annual records',days,'daily records',maxerr)
