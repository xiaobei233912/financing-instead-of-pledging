"""Matched stage-report comparisons. No changes to archived research outputs."""
from collateral_relay import run,RescueSettings,SmartConfig,load_rows,clean
from risk_relay import transformed,synthetic
from dataclasses import replace,asdict
from pathlib import Path
import datetime as dt,json,math,hashlib

ROOT=Path(__file__).parent.parent;OUT=ROOT/'results'/'cash_relay_stage';OUT.mkdir(parents=True,exist_ok=True)
RESCUE=RescueSettings(trigger=1.6,target=2)
def save(name,data):(OUT/name).write_text(json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def plain(rows,start,end,weight=.7,pal=False,floor=False,interest=.028,cash_yield=.02,compound=False,pal_rebalance=False):
    """Ordinary unlevered portfolio, or explicitly ideal direct-cash PAL.
    Same first-day price and living-payment day as the relay. Ordinary sales
    settle next trading day. PAL borrows at year opening, disburses living on
    day +2; lending capacity and research stop line are 140%, not 300%.
    """
    selected=[r for r in rows if start<=r['date']<=end]
    q=1e6*weight/selected[0]['adj_close'];c=1e6*(1-weight);bank=0.;pending=[]
    principal=unpaid=spent=capitalized=borrowed=0.;peak=1e6;drawdown=0.;min_m=math.inf;min_cash=math.inf
    annual=[];daily=[];events=[];current=None;prev_price=selected[0]['adj_close'];prev_date=None;due=None
    failure=None;fin_years=0;cash_floor=1e6*(1-weight) if floor else 0
    def state(price,date):
        total=q*price+c+bank+sum(v for _,v in pending)
        debt=principal+unpaid
        return dict(date=date,net=total-debt,total_assets=total,ordinary_cash=c+bank,
                    stock=q*price,credit_stock=q*price if pal else 0,credit_cash=c if pal else 0,
                    principal=principal,unpaid_interest=unpaid,debt=debt,capitalized_interest=capitalized,original_borrowed=borrowed,
                    mmr=(q*price+c)/debt if pal and debt>1e-7 else None,
                    transit=sum(v for _,v in pending),spent=spent)
    def finish(price,date):
        current.update(state(price,date),failure=failure)
        current['reconciliation_error']=current['net']-current['opening_net']-(current['stock_profit']+current['cash_income']-current['interest_expense']-current['living_paid'])
        assert abs(current['reconciliation_error'])<.02
        annual.append(current.copy())
    for i,row in enumerate(selected):
        date=dt.date.fromisoformat(row['date']);new=current is None or current['year']!=date.year
        if new:
            if current is not None:finish(prev_price,str(prev_date))
            current=dict(year=date.year,opening_net=state(prev_price,row['date'])['net'],stock_profit=0.,cash_income=0.,interest_expense=0.,living_paid=0.,financed=False)
            due=i+2
        elapsed=(date-prev_date).days if prev_date else 0
        p=row['adj_open'] if i else row['adj_close']
        current['stock_profit']+=q*(p-prev_price)
        gain=c*((1+cash_yield)**(elapsed/365)-1);c+=gain;current['cash_income']+=gain
        if compound:
            inc=principal*((1+interest)**(elapsed/365)-1);principal+=inc;capitalized+=inc
        else:
            inc=principal*interest*elapsed/365;unpaid+=inc
        current['interest_expense']+=inc
        arrived=sum(v for step,v in pending if step<=i);bank+=arrived
        pending=[(step,v) for step,v in pending if step>i]
        def observe(price):
            nonlocal min_m,failure
            if pal and principal+unpaid>1e-7:
                m=(q*price+c)/(principal+unpaid);min_m=min(min_m,m)
                if m<1.4-1e-7:failure='MarginFailure'
        observe(p)
        if not failure and new and pal:
            if (q*p+c)/(principal+unpaid+20000)<=1.4:
                failure='FinancingCapacityFailure'
            else:
                principal+=20000;borrowed+=20000;bank+=20000;current['financed']=True;fin_years+=1
        if not failure and not pal and due is not None and i>=due-1:
            need=max(0,20000-bank-sum(v for _,v in pending))
            take=min(need,c);c-=take;need-=take
            sold=min(need,q*p);q-=sold/p
            if take+sold>1e-7:pending.append((i+1,take+sold))
        if not failure and due==i:
            if bank<20000-.005:failure='LiquidityFailure'
            else:
                bank-=20000;spent+=20000;current['living_paid']=20000
                if len(annual)>0 and (not pal or pal_rebalance):
                    delta=weight*(q*p+c+bank+sum(v for _,v in pending))-q*p
                    if delta>0:
                        buy=min(delta,max(0,c+bank-cash_floor),c)
                        q+=buy/p;c-=buy
                    else:
                        q+=delta/p;c-=delta
                due=None
        observe(p)
        if not failure and i:observe(row['adj_low'])
        last_price=row['adj_low'] if failure=='MarginFailure' and (q*p+c)/(principal+unpaid)>=1.4 else p
        if not failure:last_price=row['adj_close'];observe(last_price)
        current['stock_profit']+=q*(last_price-p)
        s=state(last_price,row['date']);daily.append(s)
        peak=max(peak,s['net']);drawdown=max(drawdown,1-s['net']/peak);min_cash=min(min_cash,c+bank)
        assert min(q,c,bank,principal,unpaid)>-.01
        prev_price=last_price;prev_date=date
        if failure:break
    finish(prev_price,str(prev_date))
    r=dict(**state(prev_price,str(prev_date)),start=selected[0]['date'],end_requested=end,end_actual=str(prev_date),
           failure=failure,max_drawdown=drawdown,min_mmr=min_m if math.isfinite(min_m) else None,
           min_cash_years=min_cash/20000,financed_years=fin_years,living_paid=spent,
           rescue_cash_in=0,interest_paid=0,principal_repaid=0,
           config=dict(weight=weight,initial=1e6,withdrawal=.02,interest=interest,cash_yield=cash_yield,
                       pal=pal,floor=floor,compound=compound,pal_rebalance=pal_rebalance,safe_ratio=1.4,calendar='year opening, living on trading day +2'))
    return r,annual,daily,events

def configs():
    return {f'relay{int(w*100)}':SmartConfig(strategy='proportional',weight=w,reserve_years=(1-w)/.02,buy_cash_weight=1-w,renewal_floor=1.4) for w in [.5,.6,.7,.8,.9]}

def dispatch(rows,name,start,end,trace=False):
    if name.startswith('relay'):
        return run(rows,configs()[name],RESCUE,start,end,trace)
    if name=='mainland100':
        cfg=SmartConfig(strategy='proportional',weight=1,reserve_years=0,buy_cash_weight=0,renewal_floor=1.4)
        return run(rows,cfg,RESCUE,start,end,trace)
    if name=='pal100':return plain(rows,start,end,1,pal=True)
    if name in ['pal80','pal80_hold']:
        return plain(rows,start,end,.8,pal=True,interest=.03,compound=True,pal_rebalance=name=='pal80')
    if name.startswith('sale_floor'):return plain(rows,start,end,int(name[-2:])/100,floor=True)
    return plain(rows,start,end,int(name[4:])/100 if name!='sale100' else 1)

def main():
    rows=load_rows();end=rows[-1]['date'];main=[];rolling=[];stress=[]
    names=list(configs())+['sale70','sale80','sale100','sale_floor70','sale_floor80','pal100','mainland100']
    for start in ['2000-03-27','2009-03-09','2007-10-31','2020-02-19','2021-11-19']:
        for name in names:
            if start not in ['2000-03-27','2009-03-09'] and name not in ['relay70','relay80','sale70','sale80','pal100','mainland100']:continue
            r,y,d,e=dispatch(rows,name,start,end,trace=True);r.update(name=name,rescue=asdict(RESCUE) if name.startswith('relay') else None);main.append(r)
            tag=name+'_'+start;save(tag+'_annual.json',y);save(tag+'_daily.json',d)
            if e:save(tag+'_events.json',e)
        print(start,'main done',flush=True)
    save('main.json',main)
    starts={}
    for row in rows:
        day=dt.date.fromisoformat(row['date']);starts.setdefault((day.year,(day.month-1)//3),day)
    for name in ['relay50','relay60','relay70','relay80','relay90','sale70','sale80','pal100','mainland100']:
        for years in [10,20]:
            for day in starts.values():
                stop=dt.date(day.year+years,day.month,day.day)-dt.timedelta(days=1)
                if str(stop)>end:continue
                r,_,_,_=dispatch(rows,name,str(day),str(stop));r.update(name=name,years=years);rolling.append(r)
        print(name,'rolling done',flush=True)
    save('rolling.json',rolling)
    for name in ['relay70','relay80']:
        for label,prices,changes in [
            ('rate6',rows,dict(interest=.06)),('cash0',rows,dict(cash_yield=0)),('inflation2',rows,dict(inflation=.02)),
            ('extra_drop20',transformed(rows,shock_date='2008-11-20',shock=.2),{}),
            ('extra_drop40',transformed(rows,shock_date='2008-11-20',shock=.4),{}),
            ('flat40',synthetic([0.]*40),{}),('bear_then5_40',synthetic([-.05]*10+[.05]*30),{})]:
            start='2000-01-03' if label in ['flat40','bear_then5_40'] else '2000-03-27'
            r,y,d,e=run(prices,replace(configs()[name],**changes),RESCUE,start,prices[-1]['date'])
            r.update(name=name,scenario=label);stress.append(r)
        for label,changes in [('delay3',dict(delay=3)),('delay5',dict(delay=5)),('no_return',dict(annual_return=False))]:
            r,_,_,_=run(rows,configs()[name],replace(RESCUE,**changes),'2000-03-27',end)
            r.update(name=name,scenario=label);stress.append(r)
    save('stress.json',stress)
    save('provenance.json',dict(data='data/qqq_daily.json',sha256=hashlib.sha256((ROOT/'data/qqq_daily.json').read_bytes()).hexdigest(),
        source_start=rows[0]['date'],source_end=end,rescue=asdict(RESCUE),pal_definition='ideal direct-cash, 100% equity, 2.8% simple unpaid, 140% research floor',
        sale_definition='ordinary cash first for living, stocks if insufficient; annual target rebalancing; no debt; floor variant separate'))

if __name__=='__main__':main()
