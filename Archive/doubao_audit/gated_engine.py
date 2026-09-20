"""Independent operational implementation of the useful Doubao pressure/runway idea.
Uses the existing per-loan accounting kernel, not Doubao's merged principal ledger.
No requirement that new loans have 300% MMR: 300% is an OUTBOUND transfer rule.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import Account, Config, Loan, add_months, load_rows, EPS
from dataclasses import dataclass, asdict
import datetime as dt
import math
import json


@dataclass
class GateConfig(Config):
    strategy: str = 'D_gate'
    weight: float = .7
    cash_yield: float = .02
    stress_loss: float = .6
    stress_mmr: float = 1.5
    runway: float = 5.
    topup_line: float = 1.6
    topup_target: float = 2.
    refinance_interest: bool = False
    pay_monthly_interest: bool = False
    never_repay: bool = False
    rebal_calendar: str = '252'
    credit_switch: bool = True
    guard_runway: float = 0.
    liquidate_for_rebalance: bool = False
    monthly_interest_day: int = 21
    annual_step: int = 252

    def __post_init__(self):
        self.interest_mode = ('monthly_pay_and_refinance' if self.refinance_interest else 'monthly_pay') if self.pay_monthly_interest else 'accrue_unpaid'


class GateAccount(Account):
    def clear_credit(self, reason):
        if self.cfg.never_repay and self.debt()>EPS:
            self.fail('RepaymentRequired')
            self.log('repayment_conflicts_with_policy',reason=reason)
            return False
        return super().clear_credit(reason)

    def stress_assets(self):
        return self.credit(self.p*(1-self.cfg.stress_loss))

    def plan(self, amount, budget):
        c=self.cfg
        if c.block_new_from and str(self.date)>=c.block_new_from:
            return None
        buffer=self.principal()*c.interest*14/365
        sg=max(0., c.stress_mmr*(self.debt()+amount+buffer)-self.stress_assets()-(1-c.stress_loss)*amount)
        mg=max(0., c.margin_requirement*amount+buffer-self.margin())
        tc=min(self.oc*self.cp, max(sg,mg/c.cash_haircut))
        tq=max(0.,(sg-tc)/(1-c.stress_loss),(mg-tc*c.cash_haircut)/c.stock_haircut)
        if self.oq*self.p-tq<amount-EPS or self.ord_value()-tc-tq-amount<c.runway*budget-EPS:
            return None
        return tc,tq

    def transfer_planned(self, tc, tq):
        self.oc-=tc/self.cp; self.oq-=tq/self.p
        self.queue('credit',c=tc/self.cp,q=tq/self.p)
        self.log('planned_collateral',tc+tq,cash_part=tc,stock_part=tq)

    def new_loan(self, amount, asset, reason, budget):
        c=self.cfg
        if c.block_new_from and str(self.date)>=c.block_new_from:
            return False
        if self.margin()<c.margin_requirement*amount-.001:
            return False
        stress_add=amount if asset=='c' else (1-c.stress_loss)*amount
        if self.stress_assets()+stress_add<c.stress_mmr*(self.debt()+amount)-.001:
            return False
        if reason in ['living','interest'] and self.ord_value()-(amount if reason=='living' else 0)<c.runway*budget-EPS:
            return False
        if reason=='living' and self.oq*self.p<amount-EPS:
            return False
        self.loans.append(Loan(asset,amount/(self.p if asset=='q' else self.cp),amount,0.,self.date,add_months(self.date,6)))
        self.borrowed+=amount
        assert self.margin()>-.005
        self.log('loan_'+reason,amount,asset=asset,margin_after=self.margin())
        if reason=='living':
            sold=self.sell_ordinary_to_bank(amount,'q')
            assert abs(sold-amount)<.001
            self.borrowed_living+=amount
        return True

    def risk_transfer(self, target, budget, reason):
        pending=sum(q*self.p+c*self.cp+b for _,dest,q,c,b in self.pending if dest=='credit')
        need=max(0., target*self.debt()-self.credit()-pending)
        if need<EPS:return
        if self.ord_value()-need<self.cfg.guard_runway*budget:
            self.clear_credit(reason+'_exit')
        else:
            amount=min(need,self.oc*self.cp+self.oq*self.p)
            self.transfer_in(amount)
            self.log(reason,amount)

    def rebalance_gated(self, budget):
        # Ordinary trades first. Credit sales pay interest/FIFO principal,
        # followed by a separately eligible cash-ETF loan, if available.
        for _ in range(60):
            delta=self.stock()-self.cfg.weight*self.total()
            if abs(delta)<.005:return True
            if delta<0:
                value=min(-delta,self.oc*self.cp)
                self.oc-=value/self.cp;self.oq+=value/self.p
                if value<-delta-.005:
                    self.transfer_out()
                    if self.cfg.liquidate_for_rebalance and self.debt()>EPS:
                        self.clear_credit('rebalance_underweight')
                    return False
            else:
                value=min(delta,self.oq*self.p)
                self.oq-=value/self.p;self.oc+=value/self.cp;delta-=value
                if delta>.005:
                    if self.cfg.never_repay:
                        self.transfer_out()
                        return False
                    cq=(self.cq+sum(x.units for x in self.loans if x.asset=='q'))*self.p
                    if cq<EPS:return False
                    sale=min(delta,cq)
                    # Account.sell_credit normally consumes free cash first;
                    # force stock proceeds for a stock-to-cash reallocation.
                    cash=self.credit_cash;self.credit_cash=0.
                    self.sell_credit(sale,preference='q')
                    self.credit_cash+=cash
                    if self.cfg.credit_switch:
                        self.new_loan(sale,'c','rebalance',budget)
        return False


def simulate_gate(rows,cfg,start='2000-03-27',end='2026-09-04',trace=False):
    assert not (cfg.never_repay and cfg.pay_monthly_interest)
    full=rows
    selected=[r for r in full if r['date']>=start and (not end or r['date']<=end)]
    dates=[dt.date.fromisoformat(r['date']) for r in selected]
    a=GateAccount(cfg,dates[0],selected[0]['adj_close']);a.trace=trace
    due={i:cfg.initial*cfg.withdrawal*(1+cfg.inflation)**((dates[i]-dates[0]).days/365.25)
         for i in range(0,len(dates),cfg.annual_step)}
    if cfg.rebal_calendar in ['anniversary','yearend']:
        due={0:cfg.initial*cfg.withdrawal}
        for y in range(1,100):
            anniversary=add_months(dates[0],12*y)
            if anniversary>dates[-1]:break
            j=next(i for i,d in enumerate(dates) if d>=anniversary)
            due[j]=cfg.initial*cfg.withdrawal*(1+cfg.inflation)**y
    yearends={}
    for r in full:
        if r['date'][5:7]=='12':yearends[r['date'][:4]]=r['date']
    rebal_days=set(due) if cfg.rebal_calendar in ['252','anniversary'] else {i for i,d in enumerate(dates) if str(d) in yearends.values()}|{0}
    lead=max(8,3*cfg.settlement_days+2)
    prep={max(1,i-lead):(i,b) for i,b in due.items() if i}
    active=None;loan_pending=None;retry_rebal=False
    budget=cfg.initial*cfg.withdrawal
    min_m=math.inf;min_m_date=None;min_run=math.inf;min_cashrun=math.inf
    max_debt=max_debtratio=max_weight=0.;min_weight=math.inf;under=longest=current_under=0
    sum_weight=0.;nobs=0;refinanced_interest=0.;monthly=None;ledger=[]
    loan_count=swap_count=0;min_equity=math.inf

    def observe(price,phase):
        nonlocal min_m,min_m_date,max_debt,max_debtratio,min_equity
        m=a.ratio(price)
        if m<min_m:min_m,min_m_date=m,str(a.date)+':'+phase
        assets=a.total()+(price-a.p)*a.stock()/a.p
        max_debt=max(max_debt,a.debt());max_debtratio=max(max_debtratio,a.debt()/max(EPS,assets))
        min_equity=min(min_equity,assets-a.debt())
        if m<cfg.safe_ratio-EPS:a.fail('MarginFailure')

    for i,row in enumerate(selected):
        a.step,a.date=i,dates[i]
        elapsed=(dates[i]-dates[i-1]).days if i else 0
        a.cp*= (1+cfg.cash_yield)**(elapsed/365)
        a.p=row['adj_open'] if i else row['adj_close']
        a.settle();a.accrue(elapsed)
        observe(a.p,'open')
        if a.failure:break
        eq_before=a.total()-a.debt();spent_before=a.spent
        month=(a.date.year,a.date.month)
        if cfg.pay_monthly_interest and a.date.day>=cfg.monthly_interest_day and month!=monthly:
            amount=a.accrued()
            if amount>EPS:
                a.sell_credit(amount)
                if cfg.refinance_interest and a.new_loan(amount,'c','interest',budget):refinanced_interest+=amount
            monthly=month
        if cfg.guard_runway>0 and a.debt()>EPS and a.ord_value()<cfg.guard_runway*budget:
            a.clear_credit('ordinary_runway')
        if a.ratio()<cfg.topup_line:a.risk_transfer(cfg.topup_target,budget,'topup')
        for lot in list(a.loans):
            if a.date>=lot.maturity-dt.timedelta(days=10):
                if cfg.deny_renew_from and str(a.date)>=cfg.deny_renew_from:
                    a.clear_credit('renewal_denied');break
                if a.ratio()<cfg.renew_min_ratio+.05:
                    a.risk_transfer(cfg.renew_min_ratio+.05,budget,'renewal_topup')
                if a.date>=lot.maturity:
                    if a.ratio()<cfg.renew_min_ratio:
                        a.clear_credit('renewal_ratio');break
                    lot.maturity=add_months(lot.maturity,6);a.renewals+=1
        if a.failure:break
        if retry_rebal:
            retry_rebal=not a.rebalance_gated(budget)
        if i in prep:
            active=prep[i]
            a.transfer_out()
            # Wait for the outbound sweep before deciding whether new
            # collateral can be supplied; never reuse unsettled collateral.
            loan_pending=None if cfg.strategy=='A' else (i+cfg.settlement_days,'plan',active[1])
        if loan_pending and i>=loan_pending[0]:
            _,stage,amount=loan_pending
            if stage=='plan':
                plan=a.plan(amount,amount)
                if plan:
                    a.transfer_planned(*plan)
                    loan_pending=(i+cfg.settlement_days,'execute',amount)
                else:loan_pending=None
            else:
                if a.new_loan(amount,'q','living',amount):loan_count+=1
                else:a.borrow_rejections+=1
                loan_pending=None
        if active and loan_pending is None:
            due_i,amount=active
            bank_pending=sum(x[4] for x in a.pending if x[1]=='ordinary')
            shortage=max(0.,amount-a.liquid-bank_pending)
            if shortage>EPS:
                sold=a.sell_ordinary_to_bank(shortage)
                if sold<shortage-.001 and cfg.guard_runway>0 and a.debt()>EPS:
                    a.clear_credit('living_liquidity')
            if i>=due_i:active=None
        if i in due:
            budget=due[i]
            if i==0:
                # Pre-funded startup year: all future years explicitly settle.
                take=min(budget,a.oc*a.cp);a.oc-=take/a.cp
                a.oq-=(budget-take)/a.p;a.spent+=budget
            elif a.liquid>=budget-.005:
                a.liquid-=budget;a.spent+=budget;a.log('living_payment',budget)
            else:a.fail('LiquidityFailure')
        if i in rebal_days and not a.failure:
            retry_rebal=not a.rebalance_gated(budget)
        assert abs((a.total()-a.debt())-eq_before+(a.spent-spent_before))<.03,(a.date,'net equity')
        assert min(a.oq,a.oc,a.cq,a.cc,a.credit_cash,a.liquid)>-.01,(a.date,'inventory')
        assert a.principal()>=-EPS
        assert abs(a.borrowed-a.principal_repaid-a.principal())<.03
        assert abs(a.total_interest-a.interest_paid-a.accrued())<.03
        observe(a.p,'after_actions')
        if a.failure:break
        if i:observe(row['adj_low'],'intraday_low')
        if a.failure:a.p=row['adj_low'];break
        a.p=row['adj_close'];observe(a.p,'close')
        weight=a.stock()/a.total()
        min_weight=min(min_weight,weight);max_weight=max(max_weight,weight);sum_weight+=weight;nobs+=1
        if weight<.5:
            under+=1;current_under+=1;longest=max(longest,current_under)
        else:current_under=0
        min_run=min(min_run,a.ord_value()/budget)
        min_cashrun=min(min_cashrun,(a.oc*a.cp+a.liquid)/budget)
        if trace:
            ledger.append(dict(date=str(a.date),ordinary=a.ord_value(),o_q=a.oq*a.p,o_c=a.oc*a.cp,
                               withdrawable=a.liquid,credit=a.credit(),own_q=a.cq*a.p,own_c=a.cc*a.cp,
                               fin_q=sum(x.units*a.p for x in a.loans if x.asset=='q'),
                               fin_c=sum(x.units*a.cp for x in a.loans if x.asset=='c'),
                               P=a.principal(),I=a.accrued(),G=a.margin(),A=a.total(),E=a.total()-a.debt(),
                               MMR=None if not math.isfinite(a.ratio()) else a.ratio(),
                               beta=weight,beta_net=a.stock()/(a.total()-a.debt()),runway=a.ord_value()/budget,
                               spent=a.spent,interest=a.total_interest))
        if a.failure:break
    result=dict(config=asdict(cfg),start=str(dates[0]),end_requested=str(dates[-1]),end_actual=str(a.date),
                failure=a.failure or None,final_net=a.total()-a.debt(),final_debt=a.debt(),
                min_mmr=None if not math.isfinite(min_m) else min_m,min_mmr_date=min_m_date,
                min_runway=min_run,min_cash_runway=min_cashrun,max_debt=max_debt,max_debt_ratio=max_debtratio,
                min_equity=min_equity,interest=a.total_interest,interest_paid=a.interest_paid,
                interest_refinanced=refinanced_interest,living=a.spent,financed_living=a.borrowed_living,
                loan_living_years=loan_count,principal_repaid=a.principal_repaid,clearances=a.clear_count,
                renewals=a.renewals,min_weight=min_weight,max_weight=max_weight,avg_weight=sum_weight/nobs if nobs else None,
                days_under_half=under,longest_under_half=longest)
    return result,ledger,a.events


if __name__=='__main__':
    for cap in [False,True]:
        for cal in ['252','yearend']:
            r,_,_=simulate_gate(load_rows(),GateConfig(refinance_interest=cap,rebal_calendar=cal))
            print(cap,cal,r['failure'],r['final_net']/1e6,r['min_mmr'],r['min_runway'])
