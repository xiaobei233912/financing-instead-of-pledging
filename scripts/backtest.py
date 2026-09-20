"""Auditable two-account PAL approximation. Standard library, no web UI.

Prices are total-return proxy units. Ordinary cash ETF units, settled bank cash,
credit collateral, financing lots, receivables and liabilities remain separate.
Read MODEL.md for scope, ordering, settlement and broker-specific assumptions.
"""
from dataclasses import dataclass, asdict
import calendar
import copy
import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPS = 1e-7


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


@dataclass
class Config:
    strategy: str = 'C1'
    weight: float = .6
    withdrawal: float = .02
    initial: float = 1_000_000
    interest: float = .028
    cash_yield: float = .015
    inflation: float = 0
    margin_requirement: float = 1
    stock_haircut: float = .7
    cash_haircut: float = .9
    safe_ratio: float = 1.4
    transfer_ratio: float = 3
    settlement_days: int = 1
    interest_mode: str = 'monthly_pay'
    renew_min_ratio: float = 2
    deny_renew_from: str = ''
    block_new_from: str = ''
    price_mode: str = 'adjusted'
    cap_override: float = 0


@dataclass
class Loan:
    asset: str
    units: float
    principal: float
    interest: float
    opened: dt.date
    maturity: dt.date


class Account:
    def __init__(self, cfg, date, price):
        self.cfg, self.date, self.p, self.cp = cfg, date, price, 1.
        self.oq = cfg.initial * cfg.weight / price
        self.oc = cfg.initial * (1 - cfg.weight)
        self.liquid = 0.
        self.cq = self.cc = self.credit_cash = 0.
        self.loans = []
        self.pending = []  # (arrival step, destination, stock units, cash ETF units, raw cash)
        self.events = []
        self.trace = False
        self.step = 0
        self.total_interest = self.interest_paid = self.principal_repaid = 0.
        self.borrowed = self.borrowed_living = self.spent = 0.
        self.clear_count = self.borrow_rejections = self.renewals = 0
        self.failure = ''
        self.failed_date = ''
        self.borrow_continuity_date = ''

    def log(self, kind, amount=0., **kw):
        if self.trace:
            self.events.append({'date': str(self.date), 'kind': kind, 'amount': amount, **kw})

    def debt(self):
        return sum(x.principal + x.interest for x in self.loans)

    def principal(self):
        return sum(x.principal for x in self.loans)

    def accrued(self):
        return sum(x.interest for x in self.loans)

    def ord_value(self):
        return self.oq*self.p + self.oc*self.cp + self.liquid

    def credit(self, price=None):
        p = self.p if price is None else price
        return self.cq*p + self.cc*self.cp + self.credit_cash + sum(
            x.units*(p if x.asset == 'q' else self.cp) for x in self.loans)

    def stock(self):
        return (self.oq+self.cq+sum(x.units for x in self.loans if x.asset == 'q')
                + sum(x[2] for x in self.pending))*self.p

    def total(self):
        return self.ord_value()+self.credit()+sum(q*self.p+c*self.cp+b for _, _, q, c, b in self.pending)

    def ratio(self, price=None):
        return self.credit(price)/self.debt() if self.debt() > EPS else math.inf

    def margin(self):
        c = self.cfg
        v = self.credit_cash+self.cq*self.p*c.stock_haircut+self.cc*self.cp*c.cash_haircut-self.accrued()
        for x in self.loans:
            gain = x.units*(self.p if x.asset == 'q' else self.cp)-x.principal
            v += gain * ((c.stock_haircut if x.asset == 'q' else c.cash_haircut) if gain > 0 else 1)
            v -= c.margin_requirement*x.principal
        return v

    def fail(self, kind):
        if not self.failure:
            self.failure, self.failed_date = kind, str(self.date)
            self.log('failure', reason=kind)

    def settle(self):
        remaining = []
        for arrival, dest, q, c, b in self.pending:
            if arrival > self.step:
                remaining.append((arrival, dest, q, c, b))
            elif dest == 'credit':
                self.cq += q
                self.cc += c
                self.credit_cash += b
            else:
                self.oq += q
                self.oc += c
                self.liquid += b
        self.pending = remaining

    def queue(self, dest, q=0., c=0., b=0.):
        self.pending.append((self.step+self.cfg.settlement_days, dest, q, c, b))

    def transfer_in(self, amount, cash_only=False):
        cash = min(amount, self.oc*self.cp)
        stock = amount-cash
        if stock > self.oq*self.p+EPS or (cash_only and stock > EPS):
            return False
        self.oc -= cash/self.cp
        self.oq -= stock/self.p
        self.queue('credit', q=stock/self.p, c=cash/self.cp)
        self.log('collateral_in', amount)
        return True

    def available_out(self):
        if self.debt() <= EPS:
            return self.cq*self.p+self.cc*self.cp+self.credit_cash
        capacity = max(0., self.credit()-self.cfg.transfer_ratio*self.debt())
        margin = max(0., self.margin())
        total = 0.
        for value, haircut in [(self.credit_cash, 1.), (self.cc*self.cp, self.cfg.cash_haircut),
                               (self.cq*self.p, self.cfg.stock_haircut)]:
            take = min(value, capacity, margin/haircut)
            capacity -= take
            margin -= take*haircut
            total += take
        return total

    def transfer_out(self):
        remaining = self.available_out()
        original = remaining
        b = min(self.credit_cash, remaining)
        self.credit_cash -= b
        remaining -= b
        c = min(self.cc, remaining/self.cp)
        self.cc -= c
        remaining -= c*self.cp
        q = min(self.cq, remaining/self.p)
        self.cq -= q
        if original > EPS:
            self.queue('ordinary', q=q, c=c, b=b)
            self.log('collateral_out', original)
            assert self.debt() < EPS or self.ratio() >= self.cfg.transfer_ratio-1e-6

    def accrue(self, elapsed):
        for x in self.loans:
            interest = x.principal*self.cfg.interest*elapsed/365
            x.interest += interest
            self.total_interest += interest

    def repay(self, amount):
        # Interest first, then FIFO principal. Repaid loan-linked securities
        # become owned collateral; repayment does not itself sell them.
        for x in self.loans:
            take = min(amount, x.interest)
            x.interest -= take
            amount -= take
            self.interest_paid += take
        for x in self.loans:
            take = min(amount, x.principal)
            if take > EPS:
                units = x.units*take/x.principal
                if x.asset == 'q':
                    self.cq += units
                else:
                    self.cc += units
                x.units -= units
                x.principal -= take
                amount -= take
                self.principal_repaid += take
        self.loans = [x for x in self.loans if x.principal+x.interest > EPS]
        self.credit_cash += max(0., amount)

    def sell_credit(self, amount, preference='c'):
        amount = min(amount, self.credit())
        remaining = amount
        take = min(remaining, self.credit_cash)
        remaining -= take
        self.credit_cash -= take
        for asset in [preference, 'q' if preference == 'c' else 'c']:
            p = self.p if asset == 'q' else self.cp
            own = self.cq if asset == 'q' else self.cc
            units = min(own, remaining/p)
            if asset == 'q':
                self.cq -= units
            else:
                self.cc -= units
            remaining -= units*p
            for x in self.loans:
                if x.asset == asset:
                    units = min(x.units, remaining/p)
                    x.units -= units
                    remaining -= units*p
        actual = amount-remaining
        self.repay(actual)
        self.log('credit_sale_repay', actual)
        return actual

    def clear_credit(self, reason):
        debt = self.debt()
        if debt <= EPS:
            self.transfer_out()
            return True
        before = self.total()-debt
        self.sell_credit(debt)
        if self.debt() > .01:
            self.fail('ContractFailure' if reason == 'renewal' else 'InsolvencyFailure')
            return False
        self.clear_count += 1
        self.log('clear_credit', debt, reason=reason)
        self.transfer_out()
        assert abs(self.total()-self.debt()-before) < .001
        return True

    def sell_ordinary_to_bank(self, amount, asset=None):
        available = self.oq*self.p+self.oc*self.cp
        amount = min(amount, available)
        remaining = amount
        for kind in ([asset] if asset else ['c', 'q']):
            if kind == 'c':
                take = min(remaining, self.oc*self.cp)
                self.oc -= take/self.cp
            else:
                take = min(remaining, self.oq*self.p)
                self.oq -= take/self.p
            remaining -= take
        actual = amount-remaining
        if actual > EPS:
            self.queue('ordinary', b=actual)
            self.log('ordinary_sale_for_cash', actual, asset=asset or 'cash_then_stock')
        return actual

    def rebalance(self):
        # Pending security transfers remain exposure but cannot be traded.
        delta = self.cfg.weight*self.total()-self.stock()
        if delta > 0:
            take = min(delta, self.oc*self.cp)
            self.oc -= take/self.cp
            self.oq += take/self.p
        else:
            take = min(-delta, self.oq*self.p)
            self.oq -= take/self.p
            self.oc += take/self.cp
        if abs(self.cfg.weight*self.total()-self.stock()) > .01:
            if self.debt() > EPS:
                self.clear_credit('rebalance_inventory')
            # With multi-day settlement, debt can already be zero while the
            # released inventory is still in transit. Keep the rebalance
            # pending until inventory is usable; do not silently abandon it.
            return False
        self.log('rebalance', self.stock()/self.total() if self.total() > EPS else 0)
        return True

    def candidates(self):
        if self.cfg.strategy == 'C1':
            return 'c', self.cfg.cap_override or .10, .15
        if self.cfg.strategy == 'C2':
            return 'c', self.cfg.cap_override or .20, .25
        return 'q', self.cfg.cap_override or .15, .20

    def can_borrow(self, amount, budget, with_transfer=False):
        c = self.cfg
        if c.block_new_from and str(self.date) >= c.block_new_from:
            return False, 0.
        asset, cap, _ = self.candidates()
        if c.strategy == 'N':
            cap = math.inf
        # Matched ordinary sale leaves gross investment assets unchanged.
        if (self.debt()+amount)/max(EPS, self.total()) > cap:
            return False, 0.
        available_asset = self.oc*self.cp if asset == 'c' else self.oq*self.p
        if available_asset < amount-EPS:
            return False, 0.
        new_debt = self.debt()+amount
        # Staging headroom is operational, not path-fitted: collateral settles
        # later and interest keeps accruing. At actual execution enforce 300%.
        target_ratio = 3.1 if with_transfer else 3.
        interest_buffer = self.principal()*c.interest*14/365 if with_transfer else 0.
        shortage_ratio = max(0., target_ratio*(new_debt+interest_buffer)-self.credit()-amount)
        shortage_margin = max(0., c.margin_requirement*amount+interest_buffer-self.margin())
        collateral = max(shortage_ratio, shortage_margin/c.cash_haircut)
        if asset == 'q':
            stress = self.credit(self.p*.5)+amount*.5
            collateral = max(collateral, 1.6*new_debt-stress)
        if not with_transfer:
            return collateral < .005, 0.
        if c.strategy != 'N':
            after_ordinary = self.ord_value()-amount-collateral
            after_cash = self.oc*self.cp+self.liquid-collateral-(amount if asset == 'c' else 0)
            if after_ordinary < 3*budget or after_cash < budget:
                return False, 0.
        if collateral > self.oc*self.cp+EPS:
            return False, 0.
        return True, collateral

    def borrow(self, amount, budget):
        ok, _ = self.can_borrow(amount, budget)
        if not ok:
            self.borrow_rejections += 1
            return False
        asset = self.candidates()[0]
        p = self.p if asset == 'q' else self.cp
        before = self.total()-self.debt()
        self.loans.append(Loan(asset, amount/p, amount, 0., self.date, add_months(self.date, 6)))
        self.borrowed += amount
        assert self.margin() >= -.01
        sold = self.sell_ordinary_to_bank(amount, asset)
        assert abs(sold-amount) < .01
        self.borrowed_living += amount
        self.log('borrow_for_living', amount, asset=asset)
        assert abs(self.total()-self.debt()-before) < .001
        return True


def load_rows():
    return json.loads((ROOT/'data/qqq_daily.json').read_text(encoding='utf-8'))


def simulate(rows, cfg, start='2000-03-10', end=None, trace=False):
    selected = [r for r in rows if r['date'] >= start and (end is None or r['date'] <= end)]
    if not selected:
        raise ValueError('Empty interval')
    prefix = 'adj_' if cfg.price_mode == 'adjusted' else ''
    dates = [dt.date.fromisoformat(r['date']) for r in selected]
    a = Account(cfg, dates[0], selected[0][prefix+'close'])
    a.trace = trace
    baseline = cfg.strategy in ['A', 'B', 'B_cash']
    budget0 = cfg.initial*cfg.withdrawal
    # Start with one year paid from own settled cash. Financing reimbursement,
    # if eligible, happens after the first collateral settlement. B borrows now.
    due_map = {0: budget0}
    for year in range(1, 100):
        anniversary = add_months(dates[0], 12*year)
        if anniversary > dates[-1]:
            break
        j = next(j for j, d in enumerate(dates) if d >= anniversary)
        due_map[j] = budget0*(1+cfg.inflation)**year
    preps = {max(0, j-max(5, cfg.settlement_days*3+1)): (j, b) for j, b in due_map.items() if j}
    min_ratio = math.inf
    min_ratio_date = ''
    min_runway = min_cash_runway = math.inf
    max_debt = min_beta = min_nav_beta = 0.
    min_beta = min_nav_beta = math.inf
    days_under_half = 0
    longest_under_half = current_under_half = 0
    max_debt_ratio = 0.
    ledger = []
    budget = budget0
    pending_loan = None
    active_due = None
    rebal_pending = False
    pal_debt = pal_interest = 0.
    final_interest = 0.
    first_no_borrow = ''
    last_month_paid = ''
    min_net = math.inf

    def observe(price, phase):
        nonlocal min_ratio, min_ratio_date, max_debt, max_debt_ratio, min_net
        if cfg.strategy.startswith('B'):
            ratio = (a.ord_value()+(price-a.p)*a.oq)/pal_debt if pal_debt > EPS else math.inf
            debt = pal_debt
        else:
            ratio, debt = a.ratio(price), a.debt()
        if ratio < min_ratio:
            min_ratio, min_ratio_date = ratio, str(a.date)+':'+phase
        if ratio < cfg.safe_ratio-EPS:
            a.fail('MarginFailure')
        max_debt = max(max_debt, debt)
        marked_total = a.total()+(price-a.p)*a.stock()/a.p
        max_debt_ratio = max(max_debt_ratio, debt/max(EPS, marked_total))
        min_net = min(min_net, marked_total-debt)

    for i, row in enumerate(selected):
        a.step, a.date = i, dates[i]
        days = (dates[i]-dates[i-1]).days if i else 0
        a.cp *= (1+cfg.cash_yield)**(days/365)
        a.p = row[prefix+('close' if i == 0 else 'open')]
        a.settle()
        if cfg.strategy.startswith('B'):
            interest = pal_debt*cfg.interest*days/365
            pal_interest += interest
            if cfg.strategy == 'B':
                pal_debt += interest
            else:
                # Ideal PAL with same paid-interest convention as C, sensitivity.
                take = min(a.oc*a.cp, interest)
                a.oc -= take/a.cp
                a.oq -= (interest-take)/a.p
        else:
            a.accrue(days)
        # An overnight breach cannot be repaired retroactively.
        observe(a.p, 'open')
        if a.failure:
            break
        before_action_equity = a.total()-(pal_debt if cfg.strategy.startswith('B') else a.debt())
        before_action_spent = a.spent
        if cfg.strategy == 'A' and i in preps:
            active_due = preps[i]
        if cfg.strategy == 'A' and active_due:
            due_step, amount = active_due
            bank_pending = sum(x[4] for x in a.pending if x[1] == 'ordinary')
            a.sell_ordinary_to_bank(max(0., amount-a.liquid-bank_pending))
            if i >= due_step:
                active_due = None
        if not baseline:
            # Existing cash ETF collateral pays interest on the first trading
            # day on/after the 21st. Sale proceeds go to interest before principal.
            month = str(a.date)[:7]
            if cfg.interest_mode == 'monthly_pay' and a.date.day >= 21 and month != last_month_paid:
                interest_due = a.accrued()
                if interest_due > EPS:
                    a.sell_credit(interest_due)
                    a.log('monthly_interest_settled', interest_due)
                last_month_paid = month
            _, _, exit_cap = a.candidates()
            if cfg.strategy != 'N' and a.debt() > EPS:
                reason = ''
                if a.ratio() < 2.2 or a.ratio(a.p*.5) < 1.6:
                    reason = 'credit_risk'
                elif a.debt()/a.total() > exit_cap:
                    reason = 'debt_cap'
                elif a.ord_value() < 2*budget:
                    reason = 'ordinary_runway'
                if reason:
                    a.clear_credit(reason)
            # Evaluate extensions 10 calendar days in advance. Denial triggers
            # repayment, never a free refinancing operation.
            for loan in list(a.loans):
                if a.date >= loan.maturity-dt.timedelta(days=10):
                    denied = bool(cfg.deny_renew_from and str(a.date) >= cfg.deny_renew_from)
                    if denied or a.ratio() < cfg.renew_min_ratio:
                        a.clear_credit('renewal')
                        break
                    if a.date >= loan.maturity:
                        loan.maturity = add_months(loan.maturity, 6)
                        a.renewals += 1
            if i and a.date.month == 12 and (i == len(selected)-1 or dates[i+1].year != a.date.year):
                a.transfer_out()
            if rebal_pending:
                rebal_pending = not a.rebalance()
            if i in preps:
                due_step, future_budget = preps[i]
                active_due = (due_step, future_budget)
                ok, collateral = a.can_borrow(future_budget, future_budget, with_transfer=True)
                if ok:
                    if collateral > EPS:
                        a.transfer_in(collateral, cash_only=True)
                    pending_loan = (i+cfg.settlement_days, future_budget)
                else:
                    a.borrow_rejections += 1
                    if not first_no_borrow:
                        first_no_borrow = str(a.date)
            if pending_loan and i >= pending_loan[0]:
                _, amount = pending_loan
                if not a.borrow(amount, amount) and not first_no_borrow:
                    first_no_borrow = str(a.date)
                pending_loan = None
            # Once the funding attempt has settled, bridge any shortfall with
            # ordinary sales; credit liquidation is an explicit permitted exit.
            if active_due and pending_loan is None:
                due_step, amount = active_due
                bank_pending = sum(x[4] for x in a.pending if x[1] == 'ordinary')
                shortfall = max(0., amount-a.liquid-bank_pending)
                if shortfall > EPS:
                    sold = a.sell_ordinary_to_bank(shortfall)
                    if sold < shortfall-.01 and a.debt() > EPS and cfg.strategy != 'N':
                        a.clear_credit('living_liquidity')
                if i >= due_step:
                    active_due = None
        if i in due_map:
            budget = due_map[i]
            if cfg.strategy.startswith('B'):
                pal_debt += budget
                a.spent += budget
            elif i == 0:
                # Initial assets are already owned and the initial cash bucket
                # can be liquid at inception. No credit financed cash withdrawal.
                if a.ord_value() < budget-EPS:
                    a.fail('LiquidityFailure')
                else:
                    take = min(a.oc*a.cp, budget)
                    a.oc -= take/a.cp
                    a.oq -= (budget-take)/a.p
                    a.spent += budget
            elif a.liquid < budget-.01:
                a.fail('LiquidityFailure')
            else:
                a.liquid -= budget
                a.spent += budget
                a.log('living_payment', budget)
        # Initial year uses own funds for all real-account strategies. This
        # avoids inventing same-day collateral and withdrawable sale proceeds.
        if i and a.date.month == 12 and (i == len(selected)-1 or dates[i+1].year != a.date.year):
            rebal_pending = not a.rebalance()
        action_equity = a.total()-(pal_debt if cfg.strategy.startswith('B') else a.debt())
        assert abs(action_equity-before_action_equity+a.spent-before_action_spent) < .02, (a.date, cfg.strategy, 'equity conservation')
        observe(a.p, 'after_actions')
        if a.failure:
            break
        if i:
            observe(row[prefix+'low'], 'intraday_low')
        if a.failure:
            a.p = row[prefix+'low']
            break
        a.p = row[prefix+'close']
        observe(a.p, 'close')
        total = a.total()
        debt = pal_debt if cfg.strategy.startswith('B') else a.debt()
        net = total-debt
        weight = a.stock()/total if total > EPS else 0.
        beta_nav = a.stock()/net if net > EPS else math.inf
        runway = a.ord_value()/budget
        cash_runway = (a.oc*a.cp+a.liquid)/budget
        min_runway, min_cash_runway = min(min_runway, runway), min(min_cash_runway, cash_runway)
        min_beta, min_nav_beta = min(min_beta, weight), min(min_nav_beta, beta_nav)
        if weight < .5-1e-5:
            days_under_half += 1
            current_under_half += 1
            longest_under_half = max(longest_under_half, current_under_half)
        else:
            current_under_half = 0
        # Every operation is self-financed. No negative security inventory.
        assert min(a.oq, a.oc, a.liquid, a.cq, a.cc, a.credit_cash) > -.01, (a.date, cfg)
        assert abs(a.borrowed-a.principal_repaid-a.principal()) < .02
        assert abs(a.total_interest-a.interest_paid-a.accrued()) < .02
        if trace:
            ledger.append({'date': str(a.date), 'ordinary_stock': a.oq*a.p,
                           'ordinary_cash_asset': a.oc*a.cp, 'withdrawable_cash': a.liquid,
                           'credit_own_stock': a.cq*a.p, 'credit_own_cash_asset': a.cc*a.cp,
                           'credit_financed_stock': sum(x.units*a.p for x in a.loans if x.asset == 'q'),
                           'credit_financed_cash_asset': sum(x.units*a.cp for x in a.loans if x.asset == 'c'),
                           'credit_cash': a.credit_cash, 'principal': a.principal(), 'accrued_interest': a.accrued(),
                           'pending_transfers': sum(q*a.p+c*a.cp+b for _, _, q, c, b in a.pending),
                           'total_assets': total, 'debt': debt, 'net_assets': net,
                           'margin_ratio': None if not math.isfinite(a.ratio()) else a.ratio(),
                           'margin_available': a.margin(), 'transferable_collateral': a.available_out(),
                           'weight': weight, 'beta_on_net': beta_nav, 'ordinary_runway': runway,
                           'ordinary_cash_runway': cash_runway, 'cumulative_living': a.spent})
        if a.failure:
            break
    final_debt = pal_debt if cfg.strategy.startswith('B') else a.debt()
    result = {'config': asdict(cfg), 'start': str(dates[0]), 'end_requested': str(dates[-1]),
              'end_actual': str(a.date), 'years_requested': (dates[-1]-dates[0]).days/365.25,
              'failure': a.failure or None, 'failure_date': a.failed_date or None,
              'min_margin_ratio': min_ratio if math.isfinite(min_ratio) else None,
              'min_margin_date': min_ratio_date or None, 'min_ordinary_runway': min_runway,
              'min_ordinary_cash_runway': min_cash_runway, 'max_debt': max_debt,
              'max_debt_to_gross': max_debt_ratio, 'cumulative_interest': pal_interest if cfg.strategy.startswith('B') else a.total_interest,
              'interest_paid': pal_interest if cfg.strategy == 'B_cash' else a.interest_paid,
              'final_debt': final_debt, 'final_net_assets': a.total()-final_debt,
              'min_observed_net_assets': min_net, 'cumulative_living': a.spent,
              'financed_living': a.borrowed_living if not cfg.strategy.startswith('B') else a.spent,
              'financed_fraction': (a.borrowed_living if not cfg.strategy.startswith('B') else a.spent)/a.spent if a.spent else 0,
              'principal_repaid': a.principal_repaid, 'credit_clearances': a.clear_count,
              'renewals': a.renewals, 'borrowing_rejections': a.borrow_rejections,
              'first_no_borrow': first_no_borrow or None,
              'min_gross_stock_weight': min_beta, 'min_net_stock_beta': min_nav_beta,
              'days_gross_weight_under_half': days_under_half, 'longest_days_under_half': longest_under_half}
    return result, ledger, a.events


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategy', default='C1', choices=['A', 'B', 'B_cash', 'C1', 'C2', 'C3', 'N'])
    ap.add_argument('--weight', type=float, default=.6)
    ap.add_argument('--withdrawal', type=float, default=.02)
    ap.add_argument('--interest', type=float, default=.028)
    ap.add_argument('--cash-yield', type=float, default=.015)
    ap.add_argument('--start', default='2000-03-10')
    ap.add_argument('--end', default=None)
    ap.add_argument('--trace', action='store_true')
    args = ap.parse_args()
    cfg = Config(strategy=args.strategy, weight=args.weight, withdrawal=args.withdrawal,
                 interest=args.interest, cash_yield=args.cash_yield)
    result, ledger, events = simulate(load_rows(), cfg, args.start, args.end, args.trace)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    if args.trace:
        p = ROOT/'results'
        p.mkdir(exist_ok=True)
        stem = f'{args.strategy}_{args.weight:.2f}_{args.start}'
        (p/(stem+'_daily.json')).write_text(json.dumps(ledger, separators=(',', ':'), allow_nan=False), encoding='utf-8')
        (p/(stem+'_events.json')).write_text(json.dumps(events, indent=2, allow_nan=False), encoding='utf-8')
