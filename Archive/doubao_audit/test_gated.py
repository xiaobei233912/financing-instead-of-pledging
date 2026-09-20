import datetime as dt
import unittest
from gated_engine import GateConfig,GateAccount,Loan,simulate_gate


class GatedTests(unittest.TestCase):
    def test_unpaid_interest_does_not_compound_or_get_paid(self):
        a=GateAccount(GateConfig(never_repay=True),dt.date(2000,1,3),100)
        a.cc=23000
        a.new_loan(20000,'q','living',20000)
        a.accrue(365)
        a.accrue(365)
        self.assertEqual(a.principal(),20000)
        self.assertAlmostEqual(a.accrued(),1120)
        self.assertEqual(a.interest_paid,0)
        self.assertEqual(a.cfg.interest_mode,'accrue_unpaid')

    def test_never_repay_policy_stops_instead_of_silently_repaying(self):
        a=GateAccount(GateConfig(never_repay=True),dt.date(2000,1,3),100)
        a.cc=23000
        a.new_loan(20000,'q','living',20000)
        self.assertFalse(a.clear_credit('renewal_denied'))
        self.assertEqual(a.failure,'RepaymentRequired')
        self.assertEqual(a.principal_repaid,0)

    def test_losing_financing_consumes_available_margin(self):
        a=GateAccount(GateConfig(stock_haircut=1,cash_haircut=1),dt.date(2000,1,3),100)
        a.cc=40000
        a.loans=[Loan('q',100,20000,500,a.date,dt.date(2000,7,3))]
        self.assertEqual(a.margin(),9500)
        self.assertFalse(a.new_loan(20000,'q','living',20000))

    def test_new_loan_does_not_require_300_mmr(self):
        a=GateAccount(GateConfig(),dt.date(2000,1,3),100)
        a.cc=23000
        self.assertTrue(a.new_loan(20000,'q','living',20000))
        self.assertAlmostEqual(a.ratio(),2.15)
        self.assertEqual(a.available_out(),0.)

    def test_cash_loan_refinances_only_when_eligible(self):
        a=GateAccount(GateConfig(),dt.date(2000,1,3),100)
        a.cc=23000
        self.assertTrue(a.new_loan(20000,'q','living',20000))
        a.accrue(30)
        cost=a.accrued()
        net_before=a.total()-a.debt()
        a.sell_credit(cost)
        self.assertTrue(a.new_loan(cost,'c','interest',20000))
        self.assertAlmostEqual(a.total()-a.debt(),net_before)
        self.assertAlmostEqual(a.principal(),20000+cost)
        self.assertEqual(a.accrued(),0)

    def test_oversized_sale_never_negative_principal(self):
        a=GateAccount(GateConfig(),dt.date(2000,1,3),100)
        a.loans=[Loan('q',400,20000,5000,a.date,dt.date(2000,7,3))]
        before=a.total()-a.debt()
        a.sell_credit(30000,preference='q')
        self.assertEqual(a.principal(),0)
        self.assertEqual(a.accrued(),0)
        self.assertAlmostEqual(a.total()-a.debt(),before)
        self.assertAlmostEqual(a.credit_cash,5000)

    def test_no_future_returns_used(self):
        rows=[]
        for i in range(1400):
            d=dt.date(2000,1,3)+dt.timedelta(days=i)
            if d.weekday()<5:rows.append(dict(date=str(d),adj_open=100.,adj_close=100.,adj_low=99.))
        cfg=GateConfig(refinance_interest=True)
        _,before,_=simulate_gate(rows,cfg,start='2000-01-03',trace=True)
        changed=[dict(r) for r in rows]
        for r in changed[600:]:r.update(adj_open=500.,adj_close=500.,adj_low=499.)
        _,after,_=simulate_gate(changed,cfg,start='2000-01-03',trace=True)
        self.assertEqual(before[:600],after[:600])


if __name__=='__main__':unittest.main()
