"""Tests of user-selected 3% spending using the unchanged relay engine."""
import unittest
from dataclasses import replace
from collateral_relay import run,SmartConfig,RescueSettings
from risk_relay import synthetic

class WithdrawalTests(unittest.TestCase):
    def test_three_percent_budget_and_fixed_initial_cash_floor(self):
        rows=synthetic([.05]*3)
        cfg=SmartConfig(strategy='proportional',withdrawal=.03,reserve_years=10,renewal_floor=1.4)
        r,y,_,e=run(rows,cfg,RescueSettings(trigger=1.6,target=2),rows[0]['date'],rows[-1]['date'])
        self.assertIsNone(r['failure'])
        self.assertEqual(r['living_paid'],90000)
        self.assertEqual(cfg.initial*cfg.withdrawal*cfg.reserve_years,300000)
        self.assertEqual(r['interest_paid']+r['principal_repaid'],0)
        for a in y:
            self.assertEqual(a['living_paid'],30000)
            self.assertIn(a['financed_amount'],[0,30000])
            self.assertLess(abs(a['reconciliation_error']),.01)
        for event in e:
            if event['kind']=='rebalance_decision':
                self.assertLessEqual(event['buy'],max(0,event['cash_before']-300000)+.01)

if __name__=='__main__':unittest.main()
