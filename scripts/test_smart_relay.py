import unittest
import datetime as dt
from dataclasses import replace
from backtest import Account,Loan,add_months
from smart_relay import SmartConfig,operate,simulate

class SmartTests(unittest.TestCase):
    def account(self):
        a=Account(SmartConfig(),dt.date(2000,1,3),100)
        a.oq,a.cq=0,a.oq;a.trace=True
        return a

    def test_down_year_buys_only_excess_above_fifteen_years(self):
        a=self.account();a.oc=310000
        b,s,_=operate(a,-100000,20000)
        self.assertEqual(b,10000);self.assertEqual(s,0)
        self.assertAlmostEqual(a.oc*a.cp,300000)
        a=self.account();a.oc=500000
        self.assertEqual(operate(a,-100000,20000)[0],20000)

    def test_profit_harvest_and_300_transfer_capacity(self):
        a=self.account()
        a.loans=[Loan('q',0,200000,0,a.date,add_months(a.date,6))]
        # 700k assets / 200k debt = 350%, hence only 100k can leave.
        before=a.total()-a.debt()
        b,s,requested=operate(a,300000,20000)
        self.assertEqual(requested,150000);self.assertEqual(s,100000)
        self.assertAlmostEqual(a.ratio(),3)
        self.assertAlmostEqual(a.total()-a.debt(),before)
        self.assertEqual(a.principal(),200000)

    def test_no_sale_below_300(self):
        a=self.account();a.loans=[Loan('q',0,250000,0,a.date,add_months(a.date,6))]
        self.assertEqual(operate(a,100000,20000)[1],0)

    def test_constant_prices_finance_is_not_profit_and_no_future_leak(self):
        rows=[]
        d=dt.date(2000,12,20)
        while d<=dt.date(2001,1,15):
            if d.weekday()<5:rows.append(dict(date=str(d),adj_open=100.,adj_close=100.,adj_low=100.))
            d+=dt.timedelta(days=1)
        c=SmartConfig(cash_yield=0,interest=0)
        r,y,l,e=simulate(rows,c,'2000-12-20','2001-01-15',True)
        self.assertAlmostEqual(r['net'],960000)
        self.assertTrue(all(abs(x['stock_profit'])<.001 for x in y))
        self.assertTrue(all(abs(x['reconciliation_error'])<.001 for x in y))
        self.assertEqual(sum(x['buy']+x['sale_transfer'] for x in y),0)
        changed=[dict(x) for x in rows]
        for x in changed:
            if x['date']>'2001-01-08':x.update(adj_open=200.,adj_close=200.,adj_low=200.)
        _,_,l2,e2=simulate(changed,c,'2000-12-20','2001-01-15',True)
        self.assertEqual([x for x in l if x['date']<='2001-01-08'],[x for x in l2 if x['date']<='2001-01-08'])

if __name__=='__main__':unittest.main()
