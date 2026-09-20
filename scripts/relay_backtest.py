"""7030 cash relay. Reuses the audited per-loan account ledger.
Run: python relay_backtest.py. No external packages required.
"""
from backtest import Account, Config, Loan, add_months, load_rows, EPS
from dataclasses import dataclass, asdict, replace
from pathlib import Path
import datetime as dt
import json
import math
import hashlib

OUT = Path(__file__).parent.parent / 'results' / '7030_relay'


@dataclass
class RelayConfig(Config):
    weight: float = .7
    cash_yield: float = .02
    interest_mode: str = 'accrue_unpaid'
    reserve_years: float = 15
    gate: str = 'buy_only_floor'  # both, buy_only, buy_only_floor, post_floor, none
    buy_cash_weight: float = .3
    permanent_stop: bool = False
    financing: bool = True
    renewal_floor: float = 0  # conditional indefinite renewal; sensitivity separately


def borrow_and_transfer(a, amount):
    """Finance QQQ then transfer equal own collateral, never financing cash out."""
    c = a.cfg
    if a.ratio() <= 3 or a.cq*a.p < amount-EPS:
        return False
    if a.margin() < c.margin_requirement*amount+c.stock_haircut*amount-EPS:
        return False
    if a.credit() < 3*(a.debt()+amount)-EPS:
        return False
    a.loans.append(Loan('q',amount/a.p,amount,0,a.date,add_months(a.date,6)))
    a.borrowed += amount
    a.borrowed_living += amount
    a.cq -= amount/a.p
    a.queue('ordinary',q=amount/a.p)
    a.log('finance_and_transfer',amount,ratio=a.ratio(),margin=a.margin())
    assert a.ratio() >= 3-EPS and a.margin() >= -EPS
    return True


def rebalance(a, budget):
    reserve=a.oc*a.cp+a.liquid
    delta=a.stock()-a.cfg.weight*a.total()
    floor=a.cfg.reserve_years*budget
    if reserve < floor-EPS and (a.cfg.gate in ('both','post_floor') or
                                (a.cfg.gate in ('buy_only','buy_only_floor') and delta<0)):
        a.log('rebalance_skip_cash',reserve,delta=delta)
        return
    if delta<0:
        if reserve <= a.cfg.buy_cash_weight*a.total()+EPS:
            a.log('rebalance_skip_weight',reserve,delta=delta)
            return
        amount=min(-delta,a.oc*a.cp)
        if a.cfg.gate in ('post_floor','buy_only_floor'):amount=min(amount,max(0,reserve-floor))
        a.oc-=amount/a.cp
        a.cq+=amount/a.p
        a.log('rebalance_buy',amount,remaining=-delta-amount)
        # Settled cash buys in ordinary; newly purchased shares transfer T+1.
        a.cq-=amount/a.p
        a.queue('credit',q=amount/a.p)
    elif delta>EPS:
        amount=min(delta,a.available_out(),a.cq*a.p)
        a.cq-=amount/a.p
        a.queue('ordinary',q=amount/a.p)
        a.log('rebalance_transfer_sell',amount,remaining=delta-amount)
    # No credit sale repayment, no automatic refinancing to fake rebalancing.


def simulate(rows,cfg,start,end='2026-09-08',trace=False):
    chosen=[r for r in rows if start<=r['date']<=end]
    dates=[dt.date.fromisoformat(r['date']) for r in chosen]
    a=Account(cfg,dates[0],chosen[0]['adj_close']);a.trace=True
    a.cq,a.oq=a.oq,0
    budget=cfg.initial*cfg.withdrawal
    lag=cfg.settlement_days
    due={2*lag:budget}  # entry investment, first withdrawal after actual settlement
    for y in range(1,100):
        target=add_months(dates[0],12*y)
        if target>dates[-1]:break
        due[next(i for i,d in enumerate(dates) if d>=target)]=budget
    prep={max(0,i-max(8,2*lag)):i for i in due}
    yearends={}
    for r in rows:
        if r['date'][5:7]=='12':yearends[r['date'][:4]]=r['date']
    active=None;stopped=False;financed=0;first_no=None
    min_m=math.inf;min_m_date=None;min_cash=math.inf;max_weight=0;min_weight=1
    peak=cfg.initial;drawdown=0;ledger=[];annual=[];last_year=None

    def observe(price,phase):
        nonlocal min_m,min_m_date
        m=a.ratio(price)
        if m<min_m:min_m,min_m_date=m,str(a.date)+':'+phase
        if m<cfg.safe_ratio-EPS:
            a.p=price;a.fail('MarginFailure')

    for i,r in enumerate(chosen):
        a.step,a.date=i,dates[i]
        elapsed=(dates[i]-dates[i-1]).days if i else 0
        a.cp*=(1+cfg.cash_yield)**(elapsed/365)
        a.p=r['adj_open'] if i else r['adj_close']
        a.settle();a.accrue(elapsed)
        observe(a.p,'open')
        if a.failure:break
        before=a.total()-a.debt();spent=a.spent
        if cfg.permanent_stop and a.ratio()<=3:stopped=True
        for lot in a.loans:
            if a.date>=lot.maturity:
                if a.ratio()<cfg.renewal_floor:
                    a.fail('ContractFailure');break
                lot.maturity=add_months(lot.maturity,6);a.renewals+=1
        if a.failure:break
        # All arrived ordinary QQQ is earmarked for sale (living or rebalance).
        if a.oq>EPS:
            v=a.oq*a.p;a.oq=0;a.oc+=v/a.cp
            a.log('ordinary_collateral_sale',v)
        if i in prep:
            ok=cfg.financing and not stopped and borrow_and_transfer(a,budget)
            if ok:financed+=1
            elif cfg.financing:
                first_no=first_no or str(a.date)
                a.log('finance_paused',budget,ratio=None if math.isinf(a.ratio()) else a.ratio())
            active=(prep[i],i+lag if ok else i)
        if active and i>=active[1]:
            pending=sum(x[4] for x in a.pending if x[1]=='ordinary')
            shortage=max(0,budget-a.liquid-pending)
            a.sell_ordinary_to_bank(shortage,'c')
        if i in due:
            if a.liquid<budget-.005:a.fail('LiquidityFailure')
            else:
                a.liquid-=budget;a.spent+=budget;a.log('living_payment',budget)
            active=None
        if r['date'] in yearends.values() and not a.failure:rebalance(a,budget)
        assert abs(a.total()-a.debt()-before+a.spent-spent)<.03,(a.date,'equity')
        assert min(a.oq,a.oc,a.cq,a.cc,a.credit_cash,a.liquid)>-.01
        assert abs(a.borrowed-a.principal_repaid-a.principal())<.03
        assert abs(a.total_interest-a.interest_paid-a.accrued())<.03
        assert abs(a.cc*a.cp+a.credit_cash+sum(x.units*a.cp for x in a.loans if x.asset=='c'))<.01
        observe(a.p,'after_actions')
        if a.failure:break
        if i:observe(r['adj_low'],'low')
        if a.failure:break
        a.p=r['adj_close'];observe(a.p,'close')
        equity=a.total()-a.debt();peak=max(peak,equity);drawdown=max(drawdown,1-equity/peak)
        cash=a.oc*a.cp+a.liquid;min_cash=min(min_cash,cash)
        weight=a.stock()/a.total();min_weight=min(min_weight,weight);max_weight=max(max_weight,weight)
        item=dict(date=str(a.date),net=equity,ordinary_cash=cash,credit=a.credit(),
                  credit_cash_assets=a.cc*a.cp+a.credit_cash+sum(x.units*a.cp for x in a.loans if x.asset=='c'),
                  principal=a.principal(),interest=a.accrued(),debt=a.debt(),
                  mmr=None if math.isinf(a.ratio()) else a.ratio(),stock_weight=weight,
                  net_stock_exposure=a.stock()/equity,spent=a.spent,financed_years=financed)
        if trace:ledger.append(item)
        if last_year!=a.date.year:
            if last_year is not None:annual.append(previous)
            last_year=a.date.year
        previous=item
        if a.failure:break
    if 'previous' in locals():annual.append(previous)
    events=a.events
    result=dict(config=asdict(cfg),start=str(dates[0]),end_actual=str(a.date),end_requested=str(dates[-1]),
                failure=a.failure or None,final_net=a.total()-a.debt(),final_debt=a.debt(),
                final_cash=a.oc*a.cp+a.liquid,principal=a.principal(),interest=a.accrued(),
                living_paid=a.spent,financed_years=financed,cash_years=round(a.spent/budget)-financed,
                first_finance_pause=first_no,min_mmr=None if math.isinf(min_m) else min_m,
                min_mmr_date=min_m_date,min_cash=min_cash,min_cash_years=min_cash/budget,
                max_drawdown_with_spending=drawdown,min_weight=min_weight,max_weight=max_weight,
                skipped_rebalances=sum(e['kind']=='rebalance_skip_cash' for e in events),
                partial_rebalances=sum(e.get('remaining',0)>.01 for e in events),
                principal_repaid=a.principal_repaid,interest_paid=a.interest_paid)
    return result,ledger,events,annual


def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=load_rows();cfg=RelayConfig(gate='both')  # Reproduce original, superseded interpretation.
    cases=[]
    for start in ['1999-03-10','2000-03-27','2007-10-31','2020-02-19','2021-11-19']:
        r,ledger,events,annual=simulate(rows,cfg,start,trace=True)
        cases.append(r)
        save(start+'_daily.json',ledger);save(start+'_events.json',events);save(start+'_annual.json',annual)
    save('stress.json',cases)
    variants=[]
    for label,c in [('main',cfg),('cash_zero',replace(cfg,cash_yield=0)),
                    ('interest_4',replace(cfg,interest=.04)),('interest_6',replace(cfg,interest=.06)),
                    ('buy_only_gate',replace(cfg,gate='buy_only')),
                    ('post_trade_cash_floor',replace(cfg,gate='post_floor')),
                    ('no_cash_gate',replace(cfg,gate='none')),
                    ('permanent_stop',replace(cfg,permanent_stop=True)),
                    ('settlement_3',replace(cfg,settlement_days=3)),
                    ('renewal_200',replace(cfg,renewal_floor=2)),
                    ('no_financing',replace(cfg,financing=False))]:
        r,_,_,_=simulate(rows,c,'2000-03-27');r['variant']=label;variants.append(r)
    save('sensitivity.json',variants)
    starts={}
    for r in rows:
        d=dt.date.fromisoformat(r['date']);starts.setdefault((d.year,(d.month-1)//3),d)
    rolling=[]
    for years in [10,20]:
        for d in starts.values():
            end=add_months(d,years*12)-dt.timedelta(days=1)
            if str(end)>rows[-1]['date']:continue
            r,_,_,_=simulate(rows,cfg,str(d),str(end));r['years']=years;rolling.append(r)
    save('rolling.json',rolling)
    summary=[]
    for years in [10,20]:
        group=[r for r in rolling if r['years']==years]
        summary.append(dict(years=years,n=len(group),failures=sum(bool(r['failure']) for r in group),
                            min_net=min(r['final_net'] for r in group),
                            min_mmr=min(r['min_mmr'] for r in group),
                            min_cash_years=min(r['min_cash_years'] for r in group),
                            failed_starts=[{'start':r['start'],'failure':r['failure'],'date':r['end_actual']} for r in group if r['failure']]))
    save('rolling_summary.json',summary)
    save('provenance.json',dict(data_sha256=hashlib.sha256((Path(__file__).parent.parent/'data/qqq_daily.json').read_bytes()).hexdigest(),
                               rows=len(rows),start=rows[0]['date'],end=rows[-1]['date']))
    print(json.dumps(dict(stress=cases,sensitivity=variants,rolling=summary),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
