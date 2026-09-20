"""Generate explicit, reviewable accounting corrections to the source snapshot.
No edits in the original Doubao workspace. Policy thresholds are unchanged.
Aggregate financing positions are released proportionately when principal is paid;
this is a stated aggregate approximation, not per-contract broker FIFO.
"""
import json
import math
from pathlib import Path
import pandas as pd
from audit_original import HERE, module


def make_code(level=4, capitalize=False, cash_haircut=1., low_check=False):
    src = (HERE/'source/pal_engine.py').read_text(encoding='utf-8')
    src = src.replace('    rec = []', '    rec = []\n    interest_generated = 0.0\n    interest_paid = 0.0\n    refinance_interest = 0.0\n    min_opening_equity = float("inf")')
    src = src.replace('        if a.P > 0: a.I += a.P * p.margin_rate * days/365.0',
        '''        nonlocal interest_generated
        if a.P > 0:
            expense = a.P * p.margin_rate * days/365.0
            a.I += expense
            interest_generated += expense''')
    src = src.replace('            "dd": dd,',
        '''            "dd": dd, "own_c":a.own_c, "own_q":a.own_q,
            "fin_q":a.fin_q, "fin_c":a.fin_c, "o_c":a.o_c, "o_q":a.o_q,
            "interest_generated":interest_generated, "interest_paid":interest_paid,
            "refinance_interest":refinance_interest,''')
    src = src.replace('    if return_events: return out, summary, events',
        '''    summary["unpaid_interest"] = float(a.I)
    summary["total_interest"] = float(interest_generated)
    summary["interest_paid"] = float(interest_paid)
    summary["refinance_interest"] = float(refinance_interest)
    summary["min_principal"] = float(out.P.min())
    if return_events: return out, summary, events''')
    if level >= 1:
        src = src.replace('        mark(i, max(days,1))', '        if i > 0: mark(i, days)')
    helpers = '''
    def available_margin():
        # With unit haircuts this is exactly Ac - 2P - I. With differing
        # haircuts, allocate aggregate outstanding principal by financing
        # market value: retain this limitation explicitly in the report.
        financed = a.fin_q+a.fin_c
        bq = a.P*a.fin_q/financed if financed>1e-12 else 0.
        bc = a.P-bq
        gq, gc = a.fin_q-bq, a.fin_c-bc
        return a.own_haircut(p) + gq*(p.haircut_q if gq>0 else 1.) + gc*(p.haircut_c if gc>0 else 1.) - p.init_margin*a.P-a.I

    def repay_proceeds(amount):
        nonlocal interest_paid
        interest = min(amount, a.I)
        a.I -= interest
        interest_paid += interest
        amount -= interest
        principal = min(amount, a.P)
        if a.P>1e-12:
            fraction=principal/a.P
            q,c=a.fin_q*fraction,a.fin_c*fraction
            a.fin_q-=q; a.fin_c-=c; a.own_q+=q; a.own_c+=c
        a.P-=principal
        amount-=principal
        a.own_c+=amount

    def pay_interest():
        due=a.I
        remaining=due
        for attr in ('own_c','fin_c','own_q','fin_q'):
            take=min(remaining,getattr(a,attr))
            setattr(a,attr,getattr(a,attr)-take)
            remaining-=take
        repay_proceeds(due-remaining)
        return due-remaining
'''
    if level >= 2:
        src = src.replace('    def cash_ret(i):', helpers+'\n    def cash_ret(i):')
        src = src.replace('margin_gap = max(0.0, p.init_margin*D2 - own_after_haircut)',
            'margin_gap = max(0.0, p.init_margin*amount - available_margin() - need_c*p.haircut_c-need_q*p.haircut_q)')
        src = src.replace('mc = min(max(0,a.o_c-need_c), margin_gap); mq = (margin_gap-mc)/p.haircut_q',
            'mc = min(max(0,a.o_c-need_c), margin_gap/p.haircut_c); mq = (margin_gap-mc*p.haircut_c)/p.haircut_q')
        src = src.replace('if a.own_haircut(p) >= p.init_margin*(a.P+x)-1e-9:',
            'if available_margin() >= p.init_margin*x-1e-9:')
        # Sweep also constrained by usable margin at the selected haircuts.
        src = src.replace('x=min(removable,a.own_c);', 'x=min(removable,a.own_c,max(0,available_margin())/p.haircut_c);')
        src = src.replace('x=min(removable,a.own_q);', 'x=min(removable,a.own_q,max(0,available_margin())/p.haircut_q);')
    if level >= 3:
        src = src.replace('a.fin_q-=x; a.P-=x; delta-=x', 'a.fin_q-=x; repay_proceeds(x); delta-=x')
        src = src.replace('a.own_q-=x; a.P=max(0,a.P-x); delta-=x', 'a.own_q-=x; repay_proceeds(x); delta-=x')
    if level >= 4:
        src = src.replace('    prev_date = df["date"].iloc[0]', '    last_paid_month=None\n    prev_date = df["date"].iloc[0]')
        src = src.replace('        # ---- 年度事件 ----', '''
        current_date=df["date"].iloc[i]
        current_month=(current_date.year,current_date.month)
        if mode in ('C1','C2') and current_date.day>=21 and current_month!=last_paid_month:
            before=a.total_assets()-a.liab()
            paid=pay_interest()
            assert abs(a.total_assets()-a.liab()-before)<1e-8
            events.append((str(current_date.date()),'interest_paid',paid,'credit_sale'))
            last_paid_month=current_month
            CAPITALIZE_BLOCK
        # ---- 年度事件 ----''')
        block = 'pass'
        if capitalize:
            block = '''stress=a.own_c+a.fin_c+(1-p.borrow_stress_dd)*(a.own_q+a.fin_q)
            if (paid>1e-12 and available_margin()>=p.init_margin*paid-1e-9
                and (stress+paid)>=p.borrow_stress_mmr*(a.liab()+paid)-1e-9
                and a.o_q+a.o_c>=p.runway_lo*LIV):
                a.P+=paid; a.fin_c+=paid; refinance_interest+=paid
                events.append((str(current_date.date()),'interest_refinanced',paid,'cash_ETF'))'''
        src = src.replace('CAPITALIZE_BLOCK',block)
    if low_check:
        src = src.replace('        # ---- 年度事件 ----', '''
        low_factor = df['low_factor'].iloc[i]
        low_assets = a.own_c+a.fin_c+low_factor*(a.own_q+a.fin_q)
        if mode in ('C1','C2') and a.liab()>1e-12 and low_assets/a.liab()<p.mmr_fail:
            status,fail_date='margin_fail',df['date'].iloc[i]
        # ---- 年度事件 ----''')
        src = src.replace('if i % p.ann_step == 0:', 'if i % p.ann_step == 0 and status=="ok":')
    return src


def main():
    data=pd.read_csv(HERE/'source/data/qqq_daily.csv',parse_dates=['date'])
    raw=json.loads((HERE/'source/qqq_yahoo.json').read_text())['chart']['result'][0]
    low=raw['indicators']['quote'][0]['low']; close=raw['indicators']['quote'][0]['close']
    data['low_factor']=[l/c for l,c in zip(low,close)]
    results=[]
    for level,label,cap in [(0,'V0_original',False),(1,'V1_start_return_fixed',False),
                            (2,'V2_margin_fixed',False),(3,'V3_repayment_fixed',False),
                            (4,'V4_monthly_interest',False),(4,'V5_checked_interest_refinance',True)]:
        code=make_code(level,capitalize=cap)
        mod=module(label,code)
        for mode in (['A','B','C1'] if level in [0,1] else ['C1']):
            out,r,ev=mod.simulate(data,mode,mod.Params(),start='2000-03-27',return_events=True)
            r.update(variant=label, living_borrow_events=sum(e[1]=='living' and e[3]=='borrow' for e in ev))
            out.to_json(HERE/'output'/f'{label}_{mode}_daily.jsonl',orient='records',lines=True,date_format='iso')
            results.append(r)
            print(label,mode,r['status'],r['final_E'],r['min_mmr'],r['min_runway'],r['total_interest'])
    (HERE/'output/correction_ladder.json').write_text(json.dumps(results,indent=2,allow_nan=True),encoding='utf-8')


if __name__=='__main__':
    main()
