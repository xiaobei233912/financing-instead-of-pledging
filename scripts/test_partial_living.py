import datetime as dt
import unittest
from dataclasses import replace
from backtest import Account, Loan, add_months
from smart_relay import SmartConfig, finance_living
from collateral_relay import run, RescueSettings
from risk_relay import synthetic


class PartialLivingTests(unittest.TestCase):
    def account(self, assets=310000, debt=100000, mode='partial_transfer_first'):
        c=SmartConfig(strategy='proportional',living_finance_mode=mode,cash_yield=0,interest=0)
        a=Account(c,dt.date(2000,1,3),100)
        a.oq=0;a.cq=assets/100;a.trace=True
        # Financed holdings sold at a loss in an illustrative balance sheet;
        # zero units still retain principal, to test conservative margin usage.
        a.loans=[Loan('q',0,debt,0,a.date,add_months(a.date,6))]
        return a

    def test_partial_transfer_before_finance_can_end_below_300(self):
        a=self.account();before=a.total()-a.debt()
        amount,_=finance_living(a,20000)
        self.assertEqual(amount,10000)
        self.assertAlmostEqual(a.ratio(),310000/110000)
        self.assertAlmostEqual(a.total()-a.debt(),before)
        self.assertEqual(a.principal(),110000)
        transfer=next(e for e in a.events if e['kind']=='living_collateral_transfer')
        self.assertAlmostEqual(transfer['ratio'],3)
        self.assertGreaterEqual(a.margin(),0)

    def test_exactly_300_does_not_borrow(self):
        a=self.account(300000)
        self.assertEqual(finance_living(a,20000)[0],0)

    def test_full_budget_and_unpaid_interest_counted(self):
        a=self.account(340000)
        self.assertEqual(finance_living(a,20000)[0],20000)
        a=self.account(340000);a.loans[0].interest=12000
        self.assertAlmostEqual(finance_living(a,20000)[0],4000)

    def test_margin_limits_transfer_even_when_maintenance_above_300(self):
        a=self.account(310000);a.cfg.stock_haircut=.69
        # Existing underwater financing makes margin only 13900 here.
        expected=a.margin()/(1+.69)
        self.assertLess(expected,10000)
        self.assertAlmostEqual(finance_living(a,20000)[0],expected)
        self.assertAlmostEqual(a.margin(),0,places=7)

    def test_own_inventory_limits_partial_finance(self):
        a=self.account(310000);a.cq=50;a.cc=305000
        self.assertEqual(finance_living(a,20000)[0],5000)

    def test_archived_policy_is_still_all_or_none(self):
        a=self.account(mode='full_post300')
        self.assertEqual(finance_living(a,20000)[0],0)
        a=self.account(mode='partial_post300')
        self.assertAlmostEqual(finance_living(a,20000)[0],10000/3)
        self.assertAlmostEqual(a.ratio(),3)

    def test_yearly_cashflow_reconciles_and_living_precedes_rebalance(self):
        rows=synthetic([0.]*12)
        c=SmartConfig(strategy='proportional',living_finance_mode='partial_transfer_first',
                      withdrawal=.023,reserve_years=.3/.023,cash_yield=0,interest=0,renewal_floor=1.4)
        r,y,d,e=run(rows,c,RescueSettings(trigger=1.6,target=2),rows[0]['date'],rows[-1]['date'],True)
        self.assertIsNone(r['failure'])
        self.assertEqual(r['living_paid'],276000)
        self.assertAlmostEqual(r['net'],724000)
        self.assertEqual(r['principal_repaid']+r['interest_paid'],0)
        self.assertGreater(r['partial_finance_years'],0)
        for year in y:
            self.assertAlmostEqual(year['financed_amount']+year['cash_topup_planned'],23000)
            self.assertLess(abs(year['reconciliation_error']),.01)
            events=[x['kind'] for x in e if x['date'][:4]==str(year['year'])]
            if 'rebalance_decision' in events:
                self.assertLess(events.index('living_payment'),events.index('rebalance_decision'))


if __name__=='__main__':unittest.main()
