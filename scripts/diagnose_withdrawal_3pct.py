from run_withdrawal_3pct import *
from collateral_relay import CashRescue
from smart_relay import simulate

class Capture(CashRescue):
    account=None
    def open(self,a,new_year,budget):
        self.account=a
        return super().open(a,new_year,budget)

rows=load_rows();out=[];alternatives=[]
scenarios=[('historical',rows,{}),('cash0',rows,dict(cash_yield=0)),('inflation2',rows,dict(inflation=.02)),
    ('extra_drop20',transformed(rows,shock_date='2008-11-20',shock=.2),{}),
    ('flat40',synthetic([0.]*40),{}),('bear_then5_40',synthetic([-.05]*10+[.05]*30),{}),
    ('combined',transformed(rows,drag=.01),dict(cash_yield=0,interest=.04,inflation=.02))]
for label,prices,changes in scenarios:
    start='2000-01-03' if label in ['flat40','bear_then5_40'] else '2000-03-27'
    cfg=replace(CONFIGS['w3'],**changes)
    policy=Capture(RESCUE)
    r,_,_,_=simulate(prices,cfg,start,prices[-1]['date'],policy=policy)
    a=policy.account
    budget=cfg.initial*cfg.withdrawal*(1+cfg.inflation)**(int(r['end_actual'][:4])-int(start[:4]))
    if r['failure']:
        capacity=a.available_out()
        out.append(dict(scenario=label,date=r['end_actual'],failure=r['failure'],budget=budget,
            ordinary_cash=r['ordinary_cash'],settled_bank_cash=a.liquid,
            nominal_cash_shortfall=max(0,budget-r['ordinary_cash']),
            credit_total=a.credit(),credit_cash=r['credit_cash'],credit_own_stock=r['credit_own_stock'],debt=a.debt(),
            mmr=a.ratio(),available_margin=a.margin(),withdrawable_collateral=capacity,
            capacity_covers_shortfall=capacity>=max(0,budget-r['ordinary_cash'])-.01,
            warning='capacity is measured on failure date, not guaranteed obtainable in advance or settled for that payment'))
    r,_,_,_=run(prices,replace(cfg,rebalance_first=True),RESCUE,start,prices[-1]['date'])
    r.update(scenario=label,name='w3_rebalance_first');alternatives.append(r)
save('liquidity_diagnostics.json',out);save('sequence_sensitivity.json',alternatives)
print(json.dumps([dict(scenario=x['scenario'],failure=x['failure'],end=x['end_actual']) for x in alternatives],ensure_ascii=False))
