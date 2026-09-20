"""Calendar-year comparison of proportional versus profit-harvest rebalancing.
Accounting uses backtest.Account; the original v2 engine is left unchanged.
"""
from backtest import Account, Loan, add_months, EPS, load_rows
from relay_backtest import RelayConfig, borrow_and_transfer
from dataclasses import dataclass, asdict, replace
from pathlib import Path
import datetime as dt
import json
import math
import hashlib

OUT=Path(__file__).parent.parent/'results'/'smart_relay'

@dataclass
class SmartConfig(RelayConfig):
    strategy: str = 'smart'
    harvest: float = .5
    borrow_ratio: float = 3.
    sell_ratio: float = 3.
    own_reserve_years: float = 0.
    compound_interest: bool = False
    rebalance_first: bool = False
    living_finance_mode: str = 'full_post300'


def finance_reason(a,budget):
    c=a.cfg
    if not c.financing:return '未启用融资'
    if c.block_new_from and str(a.date)>=c.block_new_from:return '停止新增授信'
    if a.ratio()<=3:return '维持率不高于300%'
    if a.cq*a.p<budget-EPS:return '可转自有股票不足一年开销'
    if a.margin()<(c.margin_requirement+c.stock_haircut)*budget-EPS:return '融资并转出后保证金余额不足'
    if a.credit()<c.borrow_ratio*(a.debt()+budget)-EPS:return '融资并转出后不足目标维持率'
    return None


def finance_living(a, budget):
    """Keep archived all-or-none policy; new policy transfers before borrowing.

    Transfer-first is an explicit execution assumption, not a claim about a
    broker's end-of-day transfer approval. Equal financing replaces only the
    own shares released. No post-financing 300% test in that branch.
    """
    mode = a.cfg.living_finance_mode
    if mode == 'full_post300':
        reason = finance_reason(a, budget)
        ok = reason is None and borrow_and_transfer(a, budget)
        return (budget if ok else 0.), reason
    if mode not in ('partial_transfer_first', 'partial_post300'):
        raise ValueError('Unknown living finance mode: ' + mode)
    c = a.cfg
    if not c.financing:return 0., '未启用融资'
    if c.block_new_from and str(a.date) >= c.block_new_from:return 0., '停止新增授信'
    if a.ratio() <= c.transfer_ratio:return 0., '维持率不高于300%'
    before = a.total() - a.debt()
    capacity = (a.credit()-c.transfer_ratio*a.debt() if mode == 'partial_transfer_first'
                else a.credit()/c.transfer_ratio-a.debt())
    limits = dict(budget=budget, transfer=max(0., capacity), own_stock=max(0., a.cq*a.p),
                  margin=max(0., a.margin())/(c.margin_requirement+c.stock_haircut))
    amount = min(limits.values())
    if amount <= EPS:return 0., '无可用转出或融资额度'
    ratio_before = a.ratio()
    if mode == 'partial_transfer_first':
        a.cq -= amount/a.p
        a.queue('ordinary', q=amount/a.p)
        ratio_transfer = a.ratio()
        assert ratio_transfer >= c.transfer_ratio-EPS and a.margin() >= -EPS
        a.log('living_collateral_transfer', amount, ratio=None if math.isinf(ratio_transfer) else ratio_transfer)
        a.loans.append(Loan('q', amount/a.p, amount, 0., a.date, add_months(a.date,6)))
        a.borrowed += amount
        a.borrowed_living += amount
    else:
        assert borrow_and_transfer(a,amount)
    assert a.margin() >= -EPS
    assert abs(a.total()-a.debt()-before) < .01
    a.log('living_finance_decision', amount, mode=mode, budget=budget,
          cash_topup_planned=budget-amount, limits=limits,
          ratio_before=None if math.isinf(ratio_before) else ratio_before,
          ratio_after=a.ratio(), margin_after=a.margin())
    return amount, ('部分融资，受限于'+min(limits,key=limits.get)) if amount<budget-.005 else None


def operate(a, prior_profit, budget):
    """Orders after the year's living payment settles, using prior-year signal."""
    cash=a.oc*a.cp+a.liquid
    surplus=max(0,cash-a.cfg.reserve_years*budget)
    if a.cfg.strategy=='proportional':
        delta=a.cfg.weight*a.total()-a.stock()
        buy=min(max(0,delta),surplus,a.oc*a.cp)
        requested=max(0,-delta)
    else:
        buy=min(budget,surplus,a.oc*a.cp) if prior_profit < -EPS else 0
        requested=max(0,prior_profit)*a.cfg.harvest
    if buy>EPS:
        a.oc-=buy/a.cp;a.queue('credit',q=buy/a.p)
        a.log('rebalance_buy',buy,prior_profit=prior_profit)
    sale=0
    if requested>EPS and a.ratio()>a.cfg.sell_ratio:
        sale=min(requested,a.available_out(),max(0,a.credit()-a.cfg.sell_ratio*a.debt()),
                 max(0,a.cq*a.p-a.cfg.own_reserve_years*budget))
        if sale>EPS:
            a.cq-=sale/a.p;a.queue('ordinary',q=sale/a.p)
        assert a.ratio()>=a.cfg.sell_ratio-EPS
    a.log('rebalance_decision',sale,buy=buy,requested_sale=requested,
          unfilled_sale=max(0,requested-sale),prior_profit=prior_profit,
          cash_before=cash,ratio_after=None if math.isinf(a.ratio()) else a.ratio())
    assert buy<=surplus+.01
    return buy,sale,requested


def simulate(rows,cfg,start='2000-03-27',end='2026-09-08',trace=False,policy=None):
    rows=[r for r in rows if start<=r['date']<=end]
    dates=[dt.date.fromisoformat(r['date']) for r in rows]
    a=Account(cfg,dates[0],rows[0]['adj_close']);a.oq,a.cq=0,a.oq;a.trace=True
    budget=cfg.initial*cfg.withdrawal;lag=cfg.settlement_days
    ledger=[];annual=[];current=None;due=None;signal=None
    prev_close=a.p;peak=cfg.initial;max_dd=0;min_m=math.inf;min_cash=math.inf
    max_weight=0;min_weight=1;max_net_beta=0;financed=0

    def observe(price,phase):
        nonlocal min_m
        m=a.ratio(price)
        if m<current['min_mmr']:
            current['min_mmr']=m;current['min_mmr_date']=str(a.date)+':'+phase
        min_m=min(min_m,m)
        if m<cfg.safe_ratio-EPS:a.p=price;a.fail('MarginFailure')

    def snapshot():
        cash=a.oc*a.cp+a.liquid
        transit=sum(q*a.p+c*a.cp+b for _,_,q,c,b in a.pending)
        own=a.cq*a.p;fin=sum(x.units*a.p for x in a.loans)
        return dict(date=str(a.date),ordinary_cash=cash,ordinary_stock=a.oq*a.p,
                    ordinary_total=a.ord_value(),credit_stock=own+fin,credit_own_stock=own,
                    credit_total=a.credit(),credit_financed_stock=fin,credit_cash=a.credit_cash+a.cc*a.cp,principal=a.principal(),
                    unpaid_interest=a.accrued(),debt=a.debt(),credit_net=a.credit()-a.debt(),
                    transit=transit,total_assets=a.total(),net=a.total()-a.debt(),
                    mmr=None if math.isinf(a.ratio()) else a.ratio(),stock_weight=a.stock()/a.total(),
                    net_stock_exposure=a.stock()/(a.total()-a.debt()),spent=a.spent)

    def finish_year():
        s=snapshot();current.update(s)
        current['net_change']=s['net']-current['opening_net']
        current['reconciliation_error']=current['net_change']-(current['stock_profit']+current['cash_income']-current['interest_expense']-current['living_paid'])
        if not a.failure:assert abs(current['reconciliation_error'])<.05,(current['year'],current['reconciliation_error'])
        if math.isinf(current['min_mmr']):current['min_mmr']=None
        current['failure']=a.failure or None
        for kind in ['rescue_cash_in','rescue_cash_return','auto_interest_payment']:
            current[kind]=sum(e['amount'] for e in a.events if e['kind']==kind and int(e['date'][:4])==current['year'])
        current['interest_paid_cumulative']=a.interest_paid
        current['principal_repaid_cumulative']=a.principal_repaid
        annual.append(current.copy())

    for i,r in enumerate(rows):
        new_year=current is None or dates[i].year!=current['year']
        if new_year:
            if current is not None:
                signal=current['stock_profit'];finish_year()
            budget=cfg.initial*cfg.withdrawal*(1+cfg.inflation)**(dates[i].year-dates[0].year)
            current=dict(year=dates[i].year,opening_net=a.total()-a.debt(),opening_cash=a.oc*a.cp+a.liquid,
                         opening_credit=a.credit(),opening_debt=a.debt(),stock_profit=0.,cash_income=0.,
                         interest_expense=0.,living_paid=0.,financed_amount=0.,financed=False,
                         finance_date=None,finance_rejection=None,buy=0.,sale_transfer=0.,requested_sale=0.,
                         rebalance_date=None,signal_year=dates[i].year-1 if signal is not None else None,
                         prior_year_profit=signal,min_mmr=math.inf,min_mmr_date=None,min_cash=math.inf)
        a.step,a.date=i,dates[i]
        elapsed=(dates[i]-dates[i-1]).days if i else 0
        open_price=r['adj_open'] if i else r['adj_close']
        units=a.stock()/a.p
        current['stock_profit']+=units*(open_price-prev_close)
        yield_units=a.oc+a.cc+sum(x[3] for x in a.pending)
        old_cash=yield_units*a.cp
        a.cp*=(1+cfg.cash_yield)**(elapsed/365)
        current['cash_income']+=yield_units*a.cp-old_cash
        old_interest=a.accrued()
        if cfg.compound_interest:
            for lot in a.loans:
                extra=lot.interest*cfg.interest*elapsed/365
                lot.interest+=extra;a.total_interest+=extra
        a.accrue(elapsed)
        current['interest_expense']+=a.accrued()-old_interest
        a.p=open_price;a.settle()
        observe(a.p,'open')
        if a.failure:break
        before=a.total()-a.debt();spent=a.spent
        if policy is not None:policy.open(a,new_year,budget)
        for lot in a.loans:
            if a.date>=lot.maturity:
                if a.ratio()<=cfg.renewal_floor or (cfg.deny_renew_from and str(a.date)>=cfg.deny_renew_from):a.fail('ContractFailure');break
                lot.maturity=add_months(lot.maturity,6);a.renewals+=1
        if a.failure:break
        if a.oq>EPS:
            value=a.oq*a.p;a.oq=0;a.oc+=value/a.cp
            a.log('ordinary_sale',value)
        if new_year:
            if cfg.rebalance_first and signal is not None:
                buy,sale,requested=operate(a,signal,budget)
                current.update(buy=buy,sale_transfer=sale,requested_sale=requested,rebalance_date=str(a.date))
            amount,rejection=finance_living(a,budget)
            ok=amount>EPS
            current['financed']=ok;current['financed_amount']=amount
            current['budget']=budget
            current['cash_topup_planned']=budget-amount
            current['finance_status']='full' if amount>=budget-.005 else ('partial' if ok else 'cash_only')
            current['finance_limit_reason']=rejection
            current['finance_date']=str(a.date)
            if ok:financed+=1
            else:
                current['finance_rejection']=rejection
                a.log('finance_paused',budget,ratio=None if math.isinf(a.ratio()) else a.ratio())
            due=i+2*lag
        if due is not None and i>=due-lag:
            pending=sum(x[4] for x in a.pending if x[1]=='ordinary')
            a.sell_ordinary_to_bank(max(0,budget-a.liquid-pending),'c')
        if due==i:
            if a.liquid<budget-.005:a.fail('LiquidityFailure')
            else:
                a.liquid-=budget;a.spent+=budget;current['living_paid']+=budget
                a.log('living_payment',budget)
            if signal is not None and not a.failure and not cfg.rebalance_first:
                buy,sale,requested=operate(a,signal,budget)
                current.update(buy=buy,sale_transfer=sale,requested_sale=requested,rebalance_date=str(a.date))
            due=None
        assert abs(a.total()-a.debt()-before+a.spent-spent)<.05
        assert min(a.oq,a.oc,a.cq,a.cc,a.liquid,a.credit_cash)>-.01
        assert abs(a.borrowed-a.principal_repaid-a.principal())<.05
        assert abs(a.total_interest-a.interest_paid-a.accrued())<.05
        assert all(x.asset=='q' for x in a.loans)
        if policy is None:assert a.cc==a.credit_cash==0
        if a.failure:break
        observe(a.p,'after_actions')
        if a.failure:break
        if i:observe(r['adj_low'],'low')
        if a.failure:
            current['stock_profit']+=(a.stock()/a.p)*(a.p-open_price)
            break
        current['stock_profit']+=(a.stock()/a.p)*(r['adj_close']-open_price)
        a.p=r['adj_close']
        if policy is not None:
            policy.close(a,budget)
            assert min(a.oq,a.oc,a.cq,a.cc,a.liquid,a.credit_cash)>-.01
            assert abs(a.borrowed-a.principal_repaid-a.principal())<.05
            assert abs(a.total_interest-a.interest_paid-a.accrued())<.05
        observe(a.p,'close');prev_close=a.p
        s=snapshot();peak=max(peak,s['net']);max_dd=max(max_dd,1-s['net']/peak)
        min_cash=min(min_cash,s['ordinary_cash']);current['min_cash']=min(current['min_cash'],s['ordinary_cash'])
        max_weight=max(max_weight,s['stock_weight']);min_weight=min(min_weight,s['stock_weight'])
        max_net_beta=max(max_net_beta,s['net_stock_exposure'])
        if trace:ledger.append(s)
        if a.failure:break
    finish_year()
    result=dict(config=asdict(cfg),start=rows[0]['date'],end_requested=rows[-1]['date'],end_actual=str(a.date),
                failure=a.failure or None,**snapshot(),living_paid=a.spent,financed_years=financed,
                cash_years=sum(x['living_paid']>0 and not x['financed'] for x in annual),min_mmr=None if math.isinf(min_m) else min_m,
                min_cash=min_cash,min_cash_years=min(x['min_cash']/(cfg.initial*cfg.withdrawal*(1+cfg.inflation)**(x['year']-dates[0].year)) for x in annual),max_drawdown=max_dd,
                max_weight=max_weight,min_weight=min_weight,max_net_stock_exposure=max_net_beta,
                rebalance_buys=sum(x['buy'] for x in annual),rebalance_sales=sum(x['sale_transfer'] for x in annual))
    result.update(interest_paid=a.interest_paid,principal_repaid=a.principal_repaid,
                  rescue_cash_in=sum(x['rescue_cash_in'] for x in annual),
                  rescue_cash_return=sum(x['rescue_cash_return'] for x in annual))
    result.update(full_finance_years=sum(x.get('finance_status')=='full' for x in annual),
                  partial_finance_years=sum(x.get('finance_status')=='partial' for x in annual),
                  cash_only_years=sum(x.get('finance_status')=='cash_only' for x in annual),
                  cash_topup_years=sum(x.get('cash_topup_planned',0)>.005 for x in annual),
                  financed_amount_total=sum(x['financed_amount'] for x in annual))
    result.update(available_margin=a.margin(), bank_liquid=a.liquid,
                  available_own_stock_transfer=min(max(0,a.cq*a.p),max(0,a.credit()-cfg.transfer_ratio*a.debt()),
                                                   max(0,a.margin())/cfg.stock_haircut) if a.ratio()>cfg.transfer_ratio else 0.)
    return result,annual,ledger,a.events


def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def main():
    OUT.mkdir(parents=True,exist_ok=True);rows=load_rows()
    cases=[];roll=[];sens=[];cfg=SmartConfig()
    for strategy in ['proportional','smart']:
        c=replace(cfg,strategy=strategy)
        for start in ['1999-03-10','2000-03-27','2007-10-31','2020-02-19','2021-11-19']:
            r,years,daily,events=simulate(rows,c,start,trace=True);cases.append(r)
            save(f'{strategy}_{start}_annual.json',years);save(f'{strategy}_{start}_daily.json',daily);save(f'{strategy}_{start}_events.json',events)
    save('stress.json',cases)
    starts={}
    for r in rows:
        d=dt.date.fromisoformat(r['date']);starts.setdefault((d.year,(d.month-1)//3),d)
    configs=[replace(cfg,strategy='proportional')]+[replace(cfg,harvest=x) for x in [.25,.375,.5,.625,.75]]
    for c in configs:
        label=c.strategy if c.strategy=='proportional' else f'smart_{c.harvest}'
        r,_,_,_=simulate(rows,c);r['label']=label;sens.append(r)
        for years in [10,20]:
            for d in starts.values():
                end=add_months(d,12*years)-dt.timedelta(days=1)
                if str(end)>rows[-1]['date']:continue
                r,_,_,_=simulate(rows,c,str(d),str(end));r.update(years=years,label=label);roll.append(r)
        print(label,'done',flush=True)
    save('rolling.json',roll);save('harvest_sensitivity.json',sens)
    save('provenance.json',dict(source='data/qqq_daily.json',sha256=hashlib.sha256((Path(__file__).parent.parent/'data/qqq_daily.json').read_bytes()).hexdigest(),
                               start=rows[0]['date'],end=rows[-1]['date'],rows=len(rows)))

if __name__=='__main__':main()
