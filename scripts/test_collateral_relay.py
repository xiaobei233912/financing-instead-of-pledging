import unittest, datetime as dt
from dataclasses import replace
from backtest import Account, Loan, add_months
from collateral_relay import CashRescue,RescueSettings,rescue_amounts,run
from smart_relay import SmartConfig,simulate
from risk_relay import synthetic

class CollateralTests(unittest.TestCase):
    def account(self):
        cfg=SmartConfig(strategy='proportional')
        day=dt.date(2000,1,3);a=Account(cfg,day,100)
        a.oq=0;a.cq=1700;a.oc=300000;a.trace=True
        a.loans=[Loan('q',0,90000,10000,day,add_months(day,6))]
        a.total_interest=10000;a.borrowed=90000
        return a

    def test_same_target_amounts(self):
        x=rescue_amounts(180,100,2.2)
        self.assertAlmostEqual(x['a'],40)
        self.assertAlmostEqual(x['b'],40/2.2)
        self.assertAlmostEqual(x['c'],40/1.2)

    def test_pending_cash_not_credit_and_no_duplicate_topup(self):
        a=self.account();p=CashRescue(RescueSettings());net=a.total()-a.debt()
        p.open(a,False,20000);p.close(a,20000)
        self.assertAlmostEqual(a.oc,250000)
        self.assertAlmostEqual(a.ratio(),1.7)
        self.assertEqual(len(a.pending),1)
        self.assertAlmostEqual(a.total()-a.debt(),net)
        a.step=1;a.settle()
        self.assertAlmostEqual(a.ratio(),2.2)
        self.assertEqual(a.interest_paid,0)

    def test_all_cash_can_be_used_and_target_not_faked(self):
        a=self.account();a.oc=10000
        p=CashRescue(RescueSettings(delay=0));p.open(a,False,20000)
        self.assertEqual(a.oc,0)
        self.assertAlmostEqual(a.ratio(),1.8)
        self.assertEqual(a.principal_repaid+a.interest_paid,0)

    def test_auto_interest_is_repayment_not_expense_twice(self):
        a=self.account();net=a.total()-a.debt()
        p=CashRescue(RescueSettings(delay=0,auto_interest=True,security=False))
        p.open(a,False,20000);p.close(a,20000)
        self.assertEqual(a.interest_paid,10000)
        self.assertEqual(a.principal_repaid,0)
        self.assertAlmostEqual(a.credit_cash,40000)
        self.assertAlmostEqual(a.total()-a.debt(),net)
        self.assertAlmostEqual(a.ratio(),210000/90000)

    def test_cash_release_preserves_transfer_floor(self):
        a=self.account();a.cq=4000;a.cc=50000
        p=CashRescue(RescueSettings());p.open(a,True,20000)
        self.assertEqual(a.cc,0)
        self.assertAlmostEqual(a.ratio(),4)
        self.assertEqual(a.pending[0][3],50000)

    def test_no_trigger_reproduces_original_and_flows_reconcile(self):
        rows=synthetic([0.]*4);cfg=SmartConfig(strategy='proportional')
        r,y,_,_=run(rows,cfg,RescueSettings(),rows[0]['date'])
        old,_,_,_=simulate(rows,cfg,rows[0]['date'],rows[-1]['date'])
        self.assertAlmostEqual(r['net'],old['net'])
        self.assertEqual(r['rescue_cash_in'],0)
        for year in y:self.assertLess(abs(year['reconciliation_error']),.01)

    def test_security_income_and_transit_reconcile(self):
        rows=synthetic([-.1]*5+[.1]*5)
        cfg=SmartConfig(strategy='proportional',cash_yield=.02)
        r,y,d,_=run(rows,cfg,RescueSettings(trigger=35,target=36),rows[0]['date'],trace=True)
        self.assertGreater(r['rescue_cash_in'],0)
        self.assertEqual(r['interest_paid']+r['principal_repaid'],0)
        self.assertTrue(any(day['credit_cash']>0 for day in d))
        for year in y:
            if not year['failure']:self.assertLess(abs(year['reconciliation_error']),.01)

if __name__=='__main__':unittest.main()
