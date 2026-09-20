"""Cash collateral rescue, isolated from the original no-rescue policy.

No discretionary repayments. Automatic settled-interest deduction is a separate
contract branch. Open/close monitoring; no fictitious fills at intraday lows.
"""
from dataclasses import dataclass, asdict, replace
from pathlib import Path
import datetime as dt
import json, hashlib, math
from smart_relay import SmartConfig, simulate, load_rows, add_months
from risk_relay import transformed, synthetic
from backtest import EPS

OUT=Path(__file__).parent.parent/'results'/'collateral_relay'

@dataclass
class RescueSettings:
    trigger: float=1.8
    target: float=2.2
    delay: int=1
    auto_interest: bool=False
    annual_return: bool=True
    security: bool=True

class CashRescue:
    def __init__(self,settings):
        self.settings=settings
        self.settled_interest=0.
        self.month=None

    def topup(self,a):
        s=self.settings
        if a.ratio()>=s.trigger or a.failure:return
        pending=sum(b+c*a.cp for _,dest,_,c,b in a.pending if dest=='credit')
        need=max(0,s.target*a.debt()-a.credit()-pending)
        amount=min(need,a.oc*a.cp+a.liquid)
        if amount<=EPS:return
        before=a.total()-a.debt()
        take=min(amount,a.liquid);a.liquid-=take
        a.oc-=(amount-take)/a.cp
        if s.security:
            if s.delay==0:a.cc+=amount/a.cp
            else:a.pending.append((a.step+s.delay,'credit',0.,amount/a.cp,0.))
        else:
            if s.delay==0:a.credit_cash+=amount
            else:a.pending.append((a.step+s.delay,'credit',0.,0.,amount))
        a.log('rescue_cash_in',amount,target=s.target,arrival_step=a.step+s.delay)
        assert abs(a.total()-a.debt()-before)<.01

    def open(self,a,new_year,budget):
        if new_year and self.settings.annual_return:
            # Annual cash-first release: only already settled collateral, with
            # post-release maintenance >=300% and nonnegative margin available.
            s=self.settings
            value=a.cc*a.cp if s.security else a.credit_cash
            haircut=a.cfg.cash_haircut if s.security else 1
            amount=min(value,max(0,a.credit()-3*a.debt()),max(0,a.margin())/haircut)
            if amount>EPS:
                if s.security:
                    a.cc-=amount/a.cp;a.queue('ordinary',c=amount/a.cp)
                else:
                    a.credit_cash-=amount;a.queue('ordinary',b=amount)
                a.log('rescue_cash_return',amount)
        self.topup(a)

    def close(self,a,budget):
        self.topup(a)
        month=(a.date.year,a.date.month)
        if month!=self.month:
            self.settled_interest=a.accrued();self.month=month
        if self.settings.auto_interest:
            amount=min(a.credit_cash,self.settled_interest,a.accrued())
            if amount>EPS:
                before=a.total()-a.debt()
                a.credit_cash-=amount;a.repay(amount)
                self.settled_interest-=amount
                a.log('auto_interest_payment',amount)
                assert abs(a.total()-a.debt()-before)<.01

def rescue_amounts(asset,debt,target):
    gap=max(0,target*debt-asset)
    return dict(a=gap,b=gap/target,c=gap/(target-1))

def clean(x):
    if isinstance(x,float) and not math.isfinite(x):return None
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    return x

def save(name,data):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def run(rows,cfg,setting,start='2000-03-27',end=None,trace=False):
    return simulate(rows,cfg,start,end or rows[-1]['date'],trace=trace,
                    policy=CashRescue(setting) if setting else None)

def main():
    rows=load_rows();main=[];stress=[];rolling=[]
    modes={'none':None,'a180':RescueSettings(),'auto180':RescueSettings(auto_interest=True,security=False),
           'a160':RescueSettings(trigger=1.6,target=2),'a200':RescueSettings(trigger=2,target=2.4)}
    cases=[('historical',rows,{}),('extra_drop20',transformed(rows,shock_date='2008-11-20',shock=.2),{}),
           ('extra_drop40',transformed(rows,shock_date='2008-11-20',shock=.4),{}),
           ('rate6',rows,{'interest':.06}),('cash0',rows,{'cash_yield':0}),
           ('inflation2',rows,{'inflation':.02}),
           ('flat40',synthetic([0.]*40),{}),('bear_then5_40',synthetic([-.05]*10+[.05]*30),{})]
    for weight,floor,label in [(.7,15,'70'),(.8,10,'80')]:
        cfg=SmartConfig(strategy='proportional',weight=weight,reserve_years=floor,
                        buy_cash_weight=1-weight,renewal_floor=1.4)
        for mode,setting in modes.items():
            name=label+'_'+mode
            for scenario,prices,changes in cases:
                start='2000-01-03' if scenario in ['flat40','bear_then5_40'] else '2000-03-27'
                r,y,d,e=run(prices,replace(cfg,**changes),setting,start,trace=scenario=='historical')
                r.update(name=name,scenario=scenario,rescue=asdict(setting) if setting else None)
                stress.append(r)
                if scenario=='historical':
                    main.append(r);save(name+'_annual.json',y);save(name+'_daily.json',d);save(name+'_events.json',e)
            if mode in ['none','a180','auto180']:
                starts={}
                for row in rows:
                    day=dt.date.fromisoformat(row['date']);starts.setdefault((day.year,(day.month-1)//3),day)
                for years in [10,20]:
                    for day in starts.values():
                        end=add_months(day,years*12)-dt.timedelta(days=1)
                        if str(end)>rows[-1]['date']:continue
                        r,_,_,_=run(rows,cfg,setting,str(day),str(end))
                        r.update(name=name,years=years);rolling.append(r)
            print(name,'done',flush=True)
        # A transfer-delay sensitivity without assuming bank wealth is liquid.
        for delay in [0,3,5]:
            r,_,_,_=run(rows,cfg,RescueSettings(delay=delay))
            r.update(name=label+'_a180_delay'+str(delay),scenario='delay');stress.append(r)
        r,_,_,_=run(rows,cfg,RescueSettings(annual_return=False))
        r.update(name=label+'_a180_no_return',scenario='no_return');stress.append(r)
    save('main.json',main);save('stress.json',stress);save('rolling.json',rolling)
    save('provenance.json',dict(source='data/qqq_daily.json',sha256=hashlib.sha256((Path(__file__).parent.parent/'data/qqq_daily.json').read_bytes()).hexdigest(),
        rows=len(rows),data_start=rows[0]['date'],data_end=rows[-1]['date'],
        cash_rescue_floor=0,credit_security_yield=.02,credit_raw_cash_yield=0,repayment_policy='no voluntary repayment; auto deduction separately',
        warning='140% is a research stop line and user-reported renewal condition, not verified broker liquidation line'))

if __name__=='__main__':main()
