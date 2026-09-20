import unittest
from dataclasses import replace
from smart_relay import SmartConfig,finance_reason,operate,simulate
from risk_relay import synthetic
import test_smart_relay

class RiskTests(unittest.TestCase):
    def test_stronger_borrow_target_rejects_before_legal_limit(self):
        a=test_smart_relay.SmartTests().account()
        from backtest import Loan,add_months
        a.loans=[Loan('q',0,170000,0,a.date,add_months(a.date,6))]
        self.assertIsNone(finance_reason(a,20000))
        a.cfg.borrow_ratio=4
        self.assertIsNotNone(finance_reason(a,20000))

    def test_own_collateral_reserve_limits_sale_without_repaying(self):
        a=test_smart_relay.SmartTests().account();a.cfg.own_reserve_years=3
        _,sale,_=operate(a,2e6,20000)
        self.assertAlmostEqual(sale,640000)
        self.assertAlmostEqual(a.cq*a.p,60000)
        self.assertEqual(a.principal_repaid,0)

    def test_spending_inflation_and_block_new_are_live_parameters(self):
        rows=synthetic([0.]*3)
        c=SmartConfig(strategy='proportional',interest=0,cash_yield=0,inflation=.1,block_new_from='2001-01-01')
        r,y,_,_=simulate(rows,c,rows[0]['date'],rows[-1]['date'])
        self.assertAlmostEqual(r['living_paid'],20000+22000+24200)
        self.assertEqual([x['financed'] for x in y],[True,False,False])
        self.assertAlmostEqual(r['net'],1000000-r['living_paid'])

    def test_renewal_denial_is_a_contract_conflict_not_market_failure(self):
        rows=synthetic([0.]*2)
        r,_,_,_=simulate(rows,SmartConfig(strategy='proportional',deny_renew_from='2000-01-01'),rows[0]['date'],rows[-1]['date'])
        self.assertEqual(r['failure'],'ContractFailure')
        self.assertGreater(r['ordinary_cash'],r['debt'])

if __name__=='__main__':unittest.main()
