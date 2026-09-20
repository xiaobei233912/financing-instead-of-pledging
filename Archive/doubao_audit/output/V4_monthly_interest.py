# -*- coding: utf-8 -*-
"""
pal_engine.py  —— 大陆券商融资模拟 PAL：双账户逐日回测引擎（最小可运行、逻辑透明）

=====================================================================
账户模型（accounting model，全部以“当日收盘市值”计，单位：初始净资产=1）
---------------------------------------------------------------------
【普通账户 O】（资产可随时卖出提现）
  o_q   : 持有的 QQQ 市值
  o_c   : 现金类资产市值（按现金收益率增值）

【信用账户 C】（两融信用账户）
  own_c : 自有担保品-现金类（从普通账户转入）
  own_q : 自有担保品-QQQ（从普通账户转入）
  fin_q : 融资买入的 QQQ 市值
  fin_c : 融资买入的现金类资产市值（信用账户内再平衡时可能出现）
  P     : 融资本金（多笔合并；单利计息）
  I     : 累计应计利息（单利，不自动利滚利；计入 MMR 分母）

关键公式
  信用账户总资产  Ac = own_c + own_q + fin_q + fin_c
  总负债          L  = P + I
  维持担保比例 MMR = Ac / L                 （无负债时定义为 +inf）
  组合总资产 A = o_q+o_c+Ac； 净资产 E = A - L
  全组合 QQQ 总市值 Q = o_q+own_q+fin_q
  股票仓位(近似beta) wQ = Q / A
  普通账户 runway(年) = (o_q+o_c) / 年生活费LIV

大陆两融硬规则（参数化，主场景取值见 Params）
  * 融资款不可提现，只能买券；
  * 担保品转出：转出后 MMR 仍须 >= 3.0（300%），且只有【自有担保品】可转出；
  * 融资保证金比例 init_margin=1.0：新增融资 D，需自有担保品(按折算率)>= D*init_margin；
    => 100%初始保证金下，融资买入 D 的建仓瞬间 MMR 不可能低于 200%（折算率=1时）；
  * 信用账户内任何卖券所得优先偿还融资负债（卖券还款）；
  * MMR < mmr_fail(1.4) 任意一日 => Margin Failure；
  * 生活费到期、普通账户不足、无法融资、又无法转出担保品 => Liquidity Failure。

“融资模拟 PAL 提现”原子操作（敞口中性）：
  信用账户融资买入 LIV 的 QQQ（P+=LIV, fin_q+=LIV）
  + 普通账户卖出等额 LIV 的 QQQ（o_q-=LIV，所得现金提现消费）
  + 按需把自有担保品从普通转入信用（现金优先，作为稳定 MMR 压舱石）
  => 全组合 QQQ 总敞口不变，负债 +LIV，生活费到手。
=====================================================================
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class Params:
    E0: float = 1.0              # 初始净资产（归一化为 1）
    stock_target: float = 0.70   # 目标 QQQ 仓位（≈组合 beta）
    withdraw: float = 0.02       # 年生活费 = 初始净资产的固定比例（名义额固定，不逐年重算）
    margin_rate: float = 0.028   # 融资年利率（单利）
    cash_yield: float = 0.02     # 现金类资产恒定年收益率；若为 None 则用真实 ^IRX 序列
    mmr_fail: float = 1.40       # 安全失败线（保守取 140%）
    mmr_transfer: float = 3.00   # 担保品转出线 300%
    init_margin: float = 1.00    # 融资保证金比例
    haircut_q: float = 1.00      # QQQ 担保品折算率（主场景按任务要求忽略=1；敏感性可设0.8/0.9）
    haircut_c: float = 1.00      # 现金类担保品折算率
    ann_step: int = 252          # 每 252 个交易日为一个“年度”生活费事件
    rebalance: str = "twoway"    # oneway=仅股票超配时向下修剪(安全方向)；twoway=双向
    # —— 策略规则参数（minimax 全历史选参结果，见 results_paramgrid_fast.csv）——
    borrow_stress_dd: float = 0.60   # 借款前压力测试：假设 QQQ 从当前再跌 60%
    borrow_stress_mmr: float = 1.50  # 压力后 MMR 须 >= 1.5 才允许新增融资
    runway_lo: float = 5.0           # 借款后普通账户剩余 runway 不得低于 5 年
    topup_line: float = 1.60         # 日内 MMR 跌破 1.6 触发担保品回补
    topup_target: float = 2.00       # 回补目标 MMR=2.0
    dd_freeze: float = 1.0       # C2: 回撤超过该值则冻结新增融资（1=不启用）
    dd_resume: float = 0.10      # C2: 回撤回到该值以内恢复
    defensive_beta: float = 1.0  # C2: 冻结期防御性目标仓位（1=不启用）
    collateral_pref: str = "cash"    # 转入口径：cash=现金优先 / pro_rata=按持仓比例


class Account:
    __slots__ = ["o_q","o_c","own_c","own_q","fin_q","fin_c","P","I"]
    def __init__(self, p: Params):
        self.o_q = p.stock_target * p.E0
        self.o_c = (1 - p.stock_target) * p.E0
        self.own_c = 0.0; self.own_q = 0.0
        self.fin_q = 0.0; self.fin_c = 0.0
        self.P = 0.0; self.I = 0.0
    # ---- 汇总 ----
    def credit_assets(self): return self.own_c+self.own_q+self.fin_q+self.fin_c
    def liab(self): return self.P + self.I
    def mmr(self):
        L = self.liab(); return np.inf if L <= 1e-12 else self.credit_assets()/L
    def total_assets(self): return self.o_q+self.o_c+self.credit_assets()
    def total_q(self): return self.o_q+self.own_q+self.fin_q
    def own_haircut(self, p: Params):
        return self.own_c*p.haircut_c + self.own_q*p.haircut_q


def simulate(data: pd.DataFrame, mode: str, p: Params = Params(),
             start=None, horizon_days=None, return_events=False):
    """
    mode:
      'A'  直接卖资产生活（无融资，对照）
      'B'  理想 PAL（单一合并账户，无 300% 转出限制）
      'C0' 大陆两融-朴素法（只做最少担保、无动态规则，用于复现失败）
      'C1' 大陆两融-压力测试+runway 门控+自动回补/扫出（主候选）
      'C2' C1 + 回撤冻结 + 防御性降仓
    返回 (daily_df, summary_dict[, events])
    """
    df = data.reset_index(drop=True)
    if start is not None:
        if isinstance(start, str): start = pd.Timestamp(start)
        df = df[df["date"] >= start].reset_index(drop=True)
    if horizon_days: df = df.iloc[:horizon_days].reset_index(drop=True)
    n = len(df)
    LIV = p.withdraw * p.E0
    a = Account(p)
    events = []
    rec = []
    interest_generated = 0.0
    interest_paid = 0.0
    refinance_interest = 0.0
    min_opening_equity = float("inf")
    status = "ok"; fail_date = None
    frozen = False
    qqq_peak = df["adj"].iloc[0]


    def available_margin():
        # With unit haircuts this is exactly Ac - 2P - I. With differing
        # haircuts, allocate aggregate outstanding principal by financing
        # market value: retain this limitation explicitly in the report.
        financed = a.fin_q+a.fin_c
        bq = a.P*a.fin_q/financed if financed>1e-12 else 0.
        bc = a.P-bq
        gq, gc = a.fin_q-bq, a.fin_c-bc
        return a.own_haircut(p) + gq*(p.haircut_q if gq>0 else 1.) + gc*(p.haircut_c if gc>0 else 1.) - p.init_margin*a.P-a.I

    def repay_proceeds(amount):
        nonlocal interest_paid
        interest = min(amount, a.I)
        a.I -= interest
        interest_paid += interest
        amount -= interest
        principal = min(amount, a.P)
        if a.P>1e-12:
            fraction=principal/a.P
            q,c=a.fin_q*fraction,a.fin_c*fraction
            a.fin_q-=q; a.fin_c-=c; a.own_q+=q; a.own_c+=c
        a.P-=principal
        amount-=principal
        a.own_c+=amount

    def pay_interest():
        due=a.I
        remaining=due
        for attr in ('own_c','fin_c','own_q','fin_q'):
            take=min(remaining,getattr(a,attr))
            setattr(a,attr,getattr(a,attr)-take)
            remaining-=take
        repay_proceeds(due-remaining)
        return due-remaining

    def cash_ret(i):
        if p.cash_yield is None:
            return df["cash_ret_irx"].iloc[i]
        return (1+p.cash_yield)**(1/252) - 1

    def mark(i, days):
        # 1) 单利计息（按自然日）
        nonlocal interest_generated
        if a.P > 0:
            expense = a.P * p.margin_rate * days/365.0
            a.I += expense
            interest_generated += expense
        rq = df["qqq_ret"].iloc[i]; rc = cash_ret(i)
        a.o_q*= (1+rq); a.own_q*=(1+rq); a.fin_q*=(1+rq)
        a.o_c*= (1+rc); a.own_c*=(1+rc); a.fin_c*=(1+rc)

    def transfer_in_need(need, pref=None):
        """从普通账户向信用账户转入自有担保品 need（市值），现金优先。返回是否足额。"""
        pref = pref or p.collateral_pref
        if pref == "cash":
            x = min(need, a.o_c); a.o_c-=x; a.own_c+=x; need-=x
            x = min(need, a.o_q); a.o_q-=x; a.own_q+=x; need-=x
        else:
            tot = a.o_c+a.o_q
            if tot <= 0: return False
            tc = min(a.o_c, need*a.o_c/tot); tq = min(a.o_q, need-tc)
            a.o_c-=tc; a.own_c+=tc; a.o_q-=tq; a.own_q+=tq; need-=(tc+tq)
            if need > 1e-9:
                x=min(need,a.o_c); a.o_c-=x;a.own_c+=x;need-=x
                x=min(need,a.o_q); a.o_q-=x;a.own_q+=x;need-=x
        return need <= 1e-9

    def sweep_out():
        """MMR>300% 时把超额自有担保品最大化扫回普通账户（现金优先），扫出后 MMR=3.0。"""
        L = a.liab()
        if L <= 1e-12:  # 无负债：自有担保品全部可转回
            x=a.own_c; a.own_c=0; a.o_c+=x
            x=a.own_q; a.own_q=0; a.o_q+=x; return
        removable = a.credit_assets() - p.mmr_transfer*L
        if removable <= 1e-9: return
        x=min(removable,a.own_c,max(0,available_margin())/p.haircut_c); a.own_c-=x; a.o_c+=x; removable-=x
        x=min(removable,a.own_q,max(0,available_margin())/p.haircut_q); a.own_q-=x; a.o_q+=x

    def topup(i):
        """日内防守：MMR 跌破 topup_line 时，从普通账户回补担保品至 topup_target。"""
        L=a.liab()
        if L<=1e-12 or a.mmr()>=p.topup_line: return
        need = p.topup_target*L - a.credit_assets()
        if need>0:
            ok = transfer_in_need(need)
            events.append((str(df["date"].iloc[i].date()),"topup",round(need,4),
                           "足额" if ok else "普通账户不足"))

    def self_fund(amount, i):
        """暂停融资：用普通账户现金、再卖 QQQ 支付生活费。返回未付缺口。"""
        x=min(amount,a.o_c); a.o_c-=x; amount-=x
        x=min(amount,a.o_q); a.o_q-=x; amount-=x
        return amount

    def can_borrow_stress(amount):
        """借款门控：压力测试 + 初始保证金 + 普通账户 runway。返回(可否, 需要转入担保品)。"""
        D2 = a.P + amount; L2 = a.liab()+amount
        # 压力情景：QQQ 再跌 borrow_stress_dd，现金类不变
        sh = p.borrow_stress_dd
        stress_assets = (a.own_c+a.fin_c) + (1-sh)*(a.own_q+a.fin_q+amount)
        need_stress = max(0.0, p.borrow_stress_mmr*L2 - stress_assets)
        # 现金担保品 1:1 抵补，QQQ 担保品按 (1-sh) 抵补
        need_c = min(a.o_c, need_stress); need_q = (need_stress-need_c)/(1-sh)
        # 初始保证金硬约束
        own_after_haircut = (a.own_c+need_c)*p.haircut_c + (a.own_q+need_q)*p.haircut_q
        margin_gap = max(0.0, p.init_margin*amount - available_margin() - need_c*p.haircut_c-need_q*p.haircut_q)
        # 初始保证金缺口也优先用现金补
        mc = min(max(0,a.o_c-need_c), margin_gap/p.haircut_c); mq = (margin_gap-mc*p.haircut_c)/p.haircut_q
        tc, tq = need_c+mc, need_q+mq
        # 普通账户剩余：转入担保品 + 卖出等额QQQ之后
        ordinary_after = (a.o_c-tc) + (a.o_q-tq-amount)
        enough_q = (a.o_q - tq) >= amount
        runway_ok = ordinary_after >= p.runway_lo*LIV - 1e-9
        feasible = (ordinary_after >= -1e-9) and enough_q and (a.o_c-tc >= -1e-9)
        return feasible and runway_ok, tc, tq

    def do_borrow(amount, tc, tq, i):
        # 转入自有担保品
        a.o_c-=tc; a.own_c+=tc; a.o_q-=tq; a.own_q+=tq
        # 信用账户融资买入 QQQ
        a.P+=amount; a.fin_q+=amount
        # 普通账户卖出等额 QQQ 并提现消费
        a.o_q-=amount

    def rebalance(i, allow_buy):
        """全组合再平衡到 stock_target。C 模式：卖出优先普通账户，其次信用(卖券还款+尝试再融资现金ETF)。"""
        Q=a.total_q(); A=a.total_assets(); tgt=p.stock_target*A
        if Q > tgt + 1e-9:  # 股票超配 -> 卖股票换现金（必须恢复安全垫）
            delta = Q-tgt
            x=min(delta,a.o_q); a.o_q-=x; a.o_c+=x; delta-=x          # 普通账户优先
            if delta > 1e-9 and mode in ("C0","C1","C2"):
                x=min(delta,a.fin_q)                                  # 先卖融资买的QQQ(保自有担保品)
                if x>0:
                    a.fin_q-=x; repay_proceeds(x); delta-=x
                    # 尝试再融资买入等额现金类资产（维持债务结构、完成股->现金切换）
                    if available_margin() >= p.init_margin*x-1e-9:
                        a.P+=x; a.fin_c+=x
                    else:
                        events.append((str(df["date"].iloc[i].date()),"deleverage_irreversible",
                                       round(x,4),"卖券还款后无法再融资，债务永久下降"))
                x=min(delta,a.own_q)                                  # 再卖自有QQQ担保品
                if x>0:
                    a.own_q-=x; repay_proceeds(x); delta-=x
            elif delta>1e-9:  # A/B 合并账户
                x=min(delta,a.o_q); a.o_q-=x; a.o_c+=x; delta-=x
        elif Q < tgt - 1e-9 and allow_buy:  # 股票低配 -> 用现金回补（仅安全允许时）
            delta=tgt-Q
            x=min(delta, a.o_c); a.o_c-=x; a.o_q+=x

    def eff_mmr():
        # 理想 PAL(B) 为单一合并账户：MMR=总资产/负债；其余模式只计信用账户
        L=a.liab()
        if L<=1e-12: return np.inf
        return a.total_assets()/L if mode=="B" else a.credit_assets()/L

    # ====================== 主循环 ======================
    last_paid_month=None
    prev_date = df["date"].iloc[0]
    for i in range(n):
        days = (df["date"].iloc[i]-prev_date).days
        if i > 0: mark(i, days)
        prev_date = df["date"].iloc[i]
        qqq_peak = max(qqq_peak, df["adj"].iloc[i])
        dd = 1 - df["adj"].iloc[i]/qqq_peak


        current_date=df["date"].iloc[i]
        current_month=(current_date.year,current_date.month)
        if mode in ('C1','C2') and current_date.day>=21 and current_month!=last_paid_month:
            before=a.total_assets()-a.liab()
            paid=pay_interest()
            assert abs(a.total_assets()-a.liab()-before)<1e-8
            events.append((str(current_date.date()),'interest_paid',paid,'credit_sale'))
            last_paid_month=current_month
            pass
        # ---- 年度事件 ----
        if i % p.ann_step == 0:
            if mode in ("C0","C1","C2"):
                sweep_out()
            # C2 回撤冻结状态机
            if mode=="C2":
                if dd >= p.dd_freeze: frozen=True
                if dd <= p.dd_resume: frozen=False
            do_borrow_flag = False
            if mode=="A":
                short = self_fund(LIV, i)
                if short>1e-6: status, fail_date = "ruin", df["date"].iloc[i]
            elif mode=="B":
                # 理想 PAL：单一合并账户，借款现金直接提现消费，投资组合持仓不动、只增负债
                Apre=a.total_assets(); Lpre=a.liab()
                post_mmr=Apre/(Lpre+LIV)   # 担保资产继续持有，MMR=A/(旧债+新债)
                if post_mmr >= p.mmr_fail:
                    a.P+=LIV                # 只增加负债，持仓与敞口不变
                    do_borrow_flag=True
                else:
                    short=self_fund(LIV,i)
                    if short>1e-6: status,fail_date="liquidity_fail",df["date"].iloc[i]
            else:
                if mode=="C0":
                    # 朴素法：只按初始保证金最少转入，能借就借，无压力测试/runway门控/回补
                    D2=a.P+LIV
                    gap=max(0.0, p.init_margin*D2 - a.own_haircut(p))
                    ok=transfer_in_need(gap) and (a.o_q>=LIV)
                    if ok:
                        a.P+=LIV; a.fin_q+=LIV; a.o_q-=LIV; do_borrow_flag=True
                    else:
                        short=self_fund(LIV,i)
                        if short>1e-6: status,fail_date="liquidity_fail",df["date"].iloc[i]
                else:
                    gate_ok, tc, tq = can_borrow_stress(LIV)
                    c2_block = frozen if mode=="C2" else False
                    if gate_ok and not c2_block:
                        do_borrow(LIV, tc, tq, i); do_borrow_flag=True
                    else:
                        sweep_out()  # 再试一次扫出
                        short=self_fund(LIV,i)
                        if short>1e-6:
                            status,fail_date="liquidity_fail",df["date"].iloc[i]
            events.append((str(df["date"].iloc[i].date()),"living",round(LIV,4),
                           "borrow" if do_borrow_flag else status if status!="ok" else "self_fund"))
            # 再平衡
            if status=="ok":
                tgt_eff = p.stock_target
                if mode=="C2" and frozen and p.defensive_beta<1: tgt_eff=p.defensive_beta
                old=p.stock_target; p.stock_target=tgt_eff
                rebalance(i, allow_buy=(p.rebalance=="twoway"))
                p.stock_target=old

        # ---- 日内防守性回补（仅 C1/C2）----
        if status=="ok" and mode in ("C1","C2"):
            topup(i)

        # ---- 逐日失败检查 ----
        mmr = eff_mmr()
        if mode in ("B","C0","C1","C2") and mmr < p.mmr_fail and status=="ok":
            status, fail_date = "margin_fail", df["date"].iloc[i]
        rec.append({
            "date": df["date"].iloc[i],
            "A": a.total_assets(), "L": a.liab(), "E": a.total_assets()-a.liab(),
            "Q": a.total_q(), "wQ": a.total_q()/max(a.total_assets(),1e-12),
            "MMR": mmr, "ordinary": a.o_q+a.o_c,
            "runway": (a.o_q+a.o_c)/LIV, "P": a.P, "I": a.I,
            "dd": dd, "own_c":a.own_c, "own_q":a.own_q,
            "fin_q":a.fin_q, "fin_c":a.fin_c, "o_c":a.o_c, "o_q":a.o_q,
            "interest_generated":interest_generated, "interest_paid":interest_paid,
            "refinance_interest":refinance_interest,
        })
        if status!="ok":
            break

    out = pd.DataFrame(rec)
    last = out.iloc[-1]
    # 若提前失败，补齐统计到失败点
    ok_tail = out[out["MMR"]>=p.mmr_fail]
    summary = {
        "mode": mode, "status": status, "fail_date": str(fail_date.date()) if fail_date is not None else "",
        "years": round(len(out)/252,2),
        "min_mmr": round(float(out["MMR"].replace([np.inf],np.nan).min()),3),
        "min_mmr_date": str(out.loc[out["MMR"].replace([np.inf],np.nan).idxmin(),"date"].date()) if out["MMR"].replace([np.inf],np.nan).notna().any() else "",
        "min_runway": round(float(out["runway"].min()),2),
        "max_debt": round(float(out["L"].max()),4),
        "total_interest": round(float(last["I"]),4),
        "final_E": round(float(last["E"]),4),
        "final_A": round(float(last["A"]),4),
        "min_wQ": round(float(out["wQ"].min()),3),
        "avg_wQ": round(float(out["wQ"].mean()),3),
        "cum_living": round(LIV*min(len(out)//p.ann_step+1, 999),4),
    }
    summary["unpaid_interest"] = float(a.I)
    summary["total_interest"] = float(interest_generated)
    summary["interest_paid"] = float(interest_paid)
    summary["refinance_interest"] = float(refinance_interest)
    summary["min_principal"] = float(out.P.min())
    if return_events: return out, summary, events
    return out, summary
