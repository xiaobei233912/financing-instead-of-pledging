import unittest
from stage_research import plain
from risk_relay import synthetic

class StageTests(unittest.TestCase):
    def test_no_return_sales_spending_conservation(self):
        rows=synthetic([0.]*3)
        r,y,_,_=plain(rows,rows[0]['date'],rows[-1]['date'],.8,cash_yield=0)
        self.assertAlmostEqual(r['net'],940000)
        self.assertEqual(r['debt'],0)
        self.assertEqual(r['living_paid'],60000)
        for a in y:self.assertLess(abs(a['reconciliation_error']),.01)

    def test_sales_can_use_stocks_when_cash_runs_out(self):
        rows=synthetic([0.]*3)
        r,_,_,_=plain(rows,rows[0]['date'],rows[-1]['date'],1,cash_yield=0)
        self.assertIsNone(r['failure'])
        self.assertAlmostEqual(r['net'],940000)

    def test_pal_does_not_repay_on_rebalance(self):
        rows=synthetic([.1]*4)
        r,y,_,_=plain(rows,rows[0]['date'],rows[-1]['date'],.8,pal=True,interest=.03,compound=True,pal_rebalance=True)
        self.assertEqual(r['original_borrowed'],80000)
        self.assertGreater(r['principal'],80000)
        self.assertEqual(r['unpaid_interest'],0)
        self.assertAlmostEqual(r['principal'],r['original_borrowed']+r['capitalized_interest'])
        for a in y:self.assertLess(abs(a['reconciliation_error']),.01)

    def test_pal_compound_exact_effective_rate(self):
        rows=synthetic([0.]*2)
        r,_,_,_=plain(rows,rows[0]['date'],rows[-1]['date'],1,pal=True,interest=.03,compound=True)
        import datetime as dt
        d0=dt.date.fromisoformat(rows[0]['date']);end=dt.date.fromisoformat(rows[-1]['date'])
        d1=dt.date.fromisoformat(next(x['date'] for x in rows if x['date'].startswith('2001')))
        expected=sum(20000*1.03**((end-d).days/365) for d in [d0,d1])
        self.assertAlmostEqual(r['debt'],expected,places=6)

if __name__=='__main__':unittest.main()
