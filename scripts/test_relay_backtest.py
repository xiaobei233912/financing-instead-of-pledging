import datetime as dt
import unittest
from backtest import Account, Loan, add_months
from relay_backtest import RelayConfig, borrow_and_transfer, rebalance


class RelayTests(unittest.TestCase):
    def account(self):
        a=Account(RelayConfig(),dt.date(2000,1,3),100)
        a.cq,a.oq=a.oq,0
        a.trace=True
        return a

    def test_finance_is_not_cash_withdrawal(self):
        a=self.account();equity=a.total()-a.debt();stock=a.stock()
        self.assertTrue(borrow_and_transfer(a,20000))
        self.assertAlmostEqual(a.total()-a.debt(),equity)
        self.assertAlmostEqual(a.stock(),stock+20000)
        self.assertEqual(a.liquid,0)
        self.assertAlmostEqual(a.pending[0][2]*a.p,20000)
        self.assertAlmostEqual(a.oc*a.cp,300000)

    def test_post_transfer_ratio_not_just_current_ratio(self):
        a=self.account()
        a.loans=[Loan('q',0,220000,0,a.date,add_months(a.date,6))]
        self.assertGreater(a.ratio(),3)
        self.assertFalse(borrow_and_transfer(a,20000))
        self.assertEqual(a.principal(),220000)

    def test_cash_gate_blocks_both_directions(self):
        for cq in [1000,10000]:
            a=self.account();a.oc=299000;a.cq=cq
            a.cfg.gate='both'
            before=(a.oc,a.cq)
            rebalance(a,20000)
            self.assertEqual(before,(a.oc,a.cq))
            self.assertEqual(a.events[-1]['kind'],'rebalance_skip_cash')

    def test_low_cash_allows_stock_sale_but_blocks_stock_buy(self):
        a=self.account();a.oc=200000;a.cq=10000
        rebalance(a,20000)
        self.assertGreater(a.pending[0][2],0)
        self.assertEqual(a.events[-1]['kind'],'rebalance_transfer_sell')
        a=self.account();a.oc=200000;a.cq=1000
        rebalance(a,20000)
        self.assertFalse(a.pending)
        self.assertEqual(a.events[-1]['kind'],'rebalance_skip_cash')

    def test_literal_seventy_percent_cash_trigger_is_distinct(self):
        a=self.account();a.oc=400000;a.cq=6000
        a.cfg.buy_cash_weight=.7
        rebalance(a,20000)
        self.assertFalse(a.pending)
        a=self.account();a.oc=400000;a.cq=6000
        rebalance(a,20000)
        self.assertGreater(a.pending[0][2],0)

    def test_simple_interest_and_transfer_conservation(self):
        a=self.account();self.assertTrue(borrow_and_transfer(a,20000))
        a.accrue(365);a.accrue(365)
        self.assertAlmostEqual(a.accrued(),1120)
        self.assertAlmostEqual(a.principal(),20000)
        before=a.total();a.step=1;a.settle()
        self.assertAlmostEqual(a.total(),before)

    def test_buy_keeps_initial_cash_floor_and_does_not_overshoot_target(self):
        a=self.account();a.oc=350000;a.cq=2000
        rebalance(a,20000)
        self.assertAlmostEqual(a.oc*a.cp,300000)
        self.assertAlmostEqual(a.pending[0][2]*a.p,50000)
        a=self.account();a.oc=700000;a.cq=13000
        rebalance(a,20000)
        self.assertAlmostEqual(a.oc*a.cp,600000)
        self.assertAlmostEqual(a.stock()/a.total(),.7)


if __name__=='__main__':unittest.main()
