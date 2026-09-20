import datetime as dt
import unittest
from backtest import Account, Config, Loan, simulate


class AccountingTests(unittest.TestCase):
    def account(self, **kw):
        return Account(Config(**kw), dt.date(2000, 1, 3), 100.)

    def test_ordinary_assets_not_margin_collateral(self):
        a = self.account()
        a.loans = [Loan('q', 200, 20000, 0, a.date, dt.date(2000, 7, 3))]
        self.assertAlmostEqual(a.ratio(), 1.)
        self.assertEqual(a.margin(), -20000)

    def test_initial_margin_211_percent_cash(self):
        a = self.account()
        a.cc = 20000/.9
        a.loans = [Loan('c', 20000, 20000, 0, a.date, dt.date(2000, 7, 3))]
        self.assertAlmostEqual(a.margin(), 0.)
        self.assertAlmostEqual(a.ratio(), 1+1/.9)

    def test_transfer_settlement_and_conservation(self):
        a = self.account()
        before = a.total()
        a.transfer_in(40000)
        self.assertEqual(a.credit(), 0)
        self.assertAlmostEqual(a.total(), before)
        a.step = 1
        a.settle()
        self.assertAlmostEqual(a.credit(), 40000)

    def test_transfer_300_and_margin_constraints(self):
        a = self.account()
        a.cc = 100000
        a.loans = [Loan('c', 20000, 20000, 0, a.date, dt.date(2000, 7, 3))]
        self.assertAlmostEqual(a.available_out(), 60000)
        a.transfer_out()
        self.assertAlmostEqual(a.ratio(), 3.)
        self.assertEqual(a.available_out(), 0.)

    def test_below_300_can_repay_and_release_equity(self):
        a = self.account()
        a.cc = 20000
        a.loans = [Loan('c', 20000, 20000, 0, a.date, dt.date(2000, 7, 3))]
        before = a.total()-a.debt()
        self.assertEqual(a.ratio(), 2.)
        self.assertEqual(a.available_out(), 0.)
        a.clear_credit('test')
        self.assertAlmostEqual(a.debt(), 0.)
        self.assertAlmostEqual(a.total(), before)
        self.assertAlmostEqual(sum(x[3] for x in a.pending), 20000)

    def test_simple_interest_not_automatic_compound(self):
        a = self.account()
        a.loans = [Loan('q', 200, 20000, 0, a.date, dt.date(2000, 7, 3))]
        a.accrue(365)
        a.accrue(365)
        self.assertAlmostEqual(a.accrued(), 1120.)

    def test_credit_interest_sale_conserves_equity(self):
        a = self.account()
        a.cc = 40000
        a.loans = [Loan('q', 200, 20000, 500, a.date, dt.date(2000, 7, 3))]
        before = a.total()-a.debt()
        a.sell_credit(500)
        self.assertAlmostEqual(a.total()-a.debt(), before)
        self.assertEqual(a.principal(), 20000)
        self.assertEqual(a.accrued(), 0)

    def test_losing_security_sale_and_fifo_repayment(self):
        a = self.account()
        a.cc = 10000
        a.loans = [Loan('q', 200, 40000, 1000, a.date, dt.date(2000, 7, 3))]
        before = a.total()-a.debt()
        a.sell_credit(10000, preference='q')
        self.assertAlmostEqual(a.total()-a.debt(), before)
        self.assertAlmostEqual(a.debt(), 31000)
        self.assertAlmostEqual(a.cq+sum(x.units for x in a.loans), 100)

    def test_no_unconditional_reborrowing(self):
        a = self.account(strategy='C3')
        a.oq = 1000
        a.oc = 0
        a.cq = 0
        a.cc = 0
        a.loans = [Loan('q', 100000, 9000000, 0, a.date, dt.date(2000, 7, 3))]
        a.clear_credit('test')
        a.step = 1
        a.settle()
        can, _ = a.can_borrow(9000000, 20000, with_transfer=True)
        self.assertFalse(can)

    def test_financed_living_preserves_total_exposure_until_spent(self):
        a = self.account(strategy='C3')
        a.cc = 50000
        stock_before = a.stock()
        net_before = a.total()-a.debt()
        self.assertTrue(a.borrow(20000, 20000))
        self.assertAlmostEqual(a.stock(), stock_before)
        self.assertAlmostEqual(a.total()-a.debt(), net_before)
        self.assertEqual(a.liquid, 0)
        a.step = 1
        a.settle()
        self.assertAlmostEqual(a.liquid, 20000)

    def test_negative_floating_profit_haircut_is_one(self):
        a = self.account()
        a.cc = 30000
        a.loans = [Loan('q', 100, 20000, 0, a.date, dt.date(2000, 7, 3))]
        self.assertAlmostEqual(a.margin(), -3000)

    def test_future_prices_do_not_change_prefix(self):
        rows = []
        for i in range(800):
            d = dt.date(2000, 1, 3)+dt.timedelta(days=i)
            if d.weekday() < 5:
                rows.append({'date': str(d), 'adj_open': 100., 'adj_close': 100., 'adj_low': 99.})
        cfg = Config(strategy='C3')
        _, ledger1, _ = simulate(rows, cfg, start=rows[0]['date'], trace=True)
        changed = [dict(x) for x in rows]
        for r in changed[400:]:
            r.update(adj_open=1000., adj_close=1000., adj_low=999.)
        _, ledger2, _ = simulate(changed, cfg, start=rows[0]['date'], trace=True)
        self.assertEqual(ledger1[:399], ledger2[:399])

    def test_intraday_breach_is_not_repaired_by_close(self):
        rows = []
        for i in range(800):
            d = dt.date(2000, 1, 3)+dt.timedelta(days=i)
            if d.weekday() < 5:
                rows.append({'date': str(d), 'adj_open': 100., 'adj_close': 100., 'adj_low': 100.})
        # PAL is enough to isolate event ordering: by year two debt is 4%.
        rows[400]['adj_low'] = .01
        result, _, _ = simulate(rows, Config(strategy='B', weight=.999), start=rows[0]['date'])
        self.assertEqual(result['failure'], 'MarginFailure')
        self.assertEqual(result['end_actual'], rows[400]['date'])

    def flat_rows(self, days=1600):
        rows = []
        for i in range(days):
            d = dt.date(2000, 1, 3)+dt.timedelta(days=i)
            if d.weekday() < 5:
                rows.append({'date': str(d), 'adj_open': 100., 'adj_close': 100., 'adj_low': 100.})
        return rows

    def test_annual_cash_failure_is_distinct_from_margin(self):
        r, _, _ = simulate(self.flat_rows(), Config(strategy='A', withdrawal=.4, cash_yield=0), start='2000-01-03')
        self.assertEqual(r['failure'], 'LiquidityFailure')
        self.assertIsNone(r['min_margin_ratio'])
        self.assertEqual(r['cumulative_living'], 800000)

    def test_refused_renewal_liquidates_and_does_not_invent_credit(self):
        r, _, _ = simulate(self.flat_rows(), Config(strategy='C1', deny_renew_from='2001-06-01',
            block_new_from='2001-06-01'), start='2000-01-03')
        self.assertIsNone(r['failure'])
        self.assertEqual(r['credit_clearances'], 1)
        self.assertEqual(r['final_debt'], 0)
        self.assertEqual(r['financed_living'], 20000)

    def test_rebalance_waits_for_released_inventory(self):
        a = self.account(weight=.7, settlement_days=3)
        a.oq, a.oc = 100, 0
        a.pending = [(3, 'ordinary', 0, 100000, 0)]
        self.assertFalse(a.rebalance())
        a.step = 1
        a.settle()
        self.assertFalse(a.rebalance())
        a.step = 3
        a.settle()
        self.assertTrue(a.rebalance())
        self.assertAlmostEqual(a.stock()/a.total(), .7)


if __name__ == '__main__':
    unittest.main()
