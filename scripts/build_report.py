"""Render the first-stage Chinese research report from saved results."""
import json
from pathlib import Path
from backtest import ROOT


def read(name):
    return json.loads((ROOT/'results'/name).read_text(encoding='utf-8'))


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])


def money(v):
    return f'{v/10000:.2f}'


def ratio(v):
    return '不适用' if v is None else f'{v*100:.2f}%'


def main():
    stress, rolling, ex, extra = [read(n) for n in ['stress_cases.json', 'rolling_summary.json', 'experiments.json', 'additional_stresses.json']]
    peak = [r for r in stress if r['start'] == '2000-03-27']
    mainrows = [r for r in peak if r['config']['weight'] == .7 and r['config']['strategy'] != 'N']
    detail = table(['策略', '担保失败', '现金流失败', '最低担保比例', '最低普通总 runway/年', '最低普通现金 runway/年', '最高债务/万元', '累计利息/万元', '期末净资产/万元'],
                   [[r['config']['strategy'], '否' if r['failure'] != 'MarginFailure' else '是', '否' if r['failure'] != 'LiquidityFailure' else '是', ratio(r['min_margin_ratio']), f"{r['min_ordinary_runway']:.2f}", f"{r['min_ordinary_cash_runway']:.2f}", money(r['max_debt']), money(r['cumulative_interest']), money(r['final_net_assets'])] for r in mainrows])
    finance = table(['策略', '累计生活费/万元', '其中融资/万元', '融资生活费占比', '累计还本金/万元', '清偿次数', '期末负债/万元'],
                    [[r['config']['strategy'], money(r['cumulative_living']), money(r['financed_living']), ratio(r['financed_fraction']), money(r['principal_repaid']), r['credit_clearances'], money(r['final_debt'])] for r in mainrows])
    crossbeta = table(['目标 Nasdaq 权重', 'A 净资产/万元', 'B 净资产/万元', 'C1 净资产/万元', 'C2 净资产/万元', 'C3 净资产/万元'],
                      [[ratio(w)]+[money(next(r for r in peak if r['config']['weight']==w and r['config']['strategy']==s)['final_net_assets']) for s in ['A','B','C1','C2','C3']] for w in [.5,.6,.7,.8]])
    rolltable = table(['完整窗口', '季度起点数/每策略', 'C1 失败', 'C2 失败', 'C3 失败', 'C1 最低担保比例', 'C1 相对 A 期末净资产优势中位数', 'C1 胜过 A 的窗口比例'],
                     [[h, next(r for r in rolling if r['horizon']==h)['n']]+
                      [next(r for r in rolling if r['horizon']==h and r['weight']==.7 and r['strategy']==s)['failures'] for s in ['C1','C2','C3']]+
                      [ratio(next(r for r in rolling if r['horizon']==h and r['weight']==.7 and r['strategy']=='C1')[k]) for k in ['min_margin','median_advantage_over_A_survivors','fraction_beating_A_survivors']]
                      for h in ['fixed_5y','fixed_10y','fixed_20y','to_end_min1y']])
    sensrows = []
    labels = [('主场景', None), ('现金收益 0%', 'cash0'), ('现金收益 3%', 'cash3'), ('融资利率 4%', 'rate4'), ('融资利率 6%', 'rate6'), ('生活费年增 2%', 'inflation2'), ('提取率 3%', 'withdraw3'), ('不含红利价格', 'raw_no_dividend'), ('结算延迟 3 日', 'settlement3'), ('2008 起拒绝展期', 'deny_renew_2008'), ('2008 起拒绝展期及新贷', 'deny_and_no_new_2008'), ('现金 0%+融资 6%+生活通胀 2%', 'joint_cash0_rate6_inflation2'), ('券商融资保证金 300%', 'broker_margin300')]
    for label, tag in labels:
        line = [label]
        for s in ['A','C1','C3']:
            found = [r for r in (peak if tag is None else ex+extra) if r['config']['weight']==.7 and r['config']['strategy']==s and (tag is None or r['experiment']==tag)]
            if not found and s == 'A' and tag in ['deny_renew_2008','deny_and_no_new_2008','broker_margin300']:
                found = [r for r in peak if r['config']['strategy']=='A' and r['config']['weight']==.7]
            line.append(money(found[0]['final_net_assets']) if found else '—')
        line.append('均无两类失败')
        sensrows.append(line)
    sensitivity = table(['情景', 'A 净资产/万元', 'C1 净资产/万元', 'C3 净资产/万元', '该行 70/30 结果'], sensrows)
    failtable = table(['情景', '策略/权重', '失败', '日期'],
                      [[r['experiment'], r['config']['strategy']+'/'+ratio(r['config']['weight']), r['failure'], r['failure_date']] for r in ex+extra if r['failure']])
    beta = table(['目标配置', 'C1 高点路径最低股票权重', '低于 50% 交易日数', '最长连续交易日数'],
                 [[ratio(r['config']['weight']), ratio(r['min_gross_stock_weight']),r['days_gross_weight_under_half'],r['longest_days_under_half']] for r in peak if r['config']['strategy']=='C1'])
    file = ROOT/'results/traces/C1_0.70_2000-03-27_daily.jsonl'
    ledger = [json.loads(x) for x in file.read_text().splitlines()]
    milestones=[]
    for date in ['2000-03-27','2002-10-09','2009-03-09','2020-03-23','2022-10-14','2026-09-08']:
        r = [r for r in ledger if r['date'] <= date][-1]
        milestones.append([r['date'], money(r['ordinary_stock']+r['ordinary_cash_asset']+r['withdrawable_cash']),
                           money(r['credit_own_stock']+r['credit_own_cash_asset']+r['credit_financed_stock']+r['credit_financed_cash_asset']+r['credit_cash']),
                           money(r['debt']), ratio(r['margin_ratio']), f"{r['ordinary_runway']:.2f}", money(r['net_assets'])])
    milestone_table=table(['日期', '普通账户/万元', '信用账户/万元', '债务/万元', '信用担保比例', '普通 runway/年', '净资产/万元'],milestones)
    march10 = table(['策略/70%权重','3月10日起期末净资产/万元','最低担保比例','是否失败'],
                    [[r['config']['strategy'],money(r['final_net_assets']),ratio(r['min_margin_ratio']),r['failure'] or '否'] for r in stress if r['start']=='2000-03-10' and r['config']['weight']==.7 and r['config']['strategy']!='N'])
    text = f'''# 大陆券商融资模拟 PAL：第一阶段研究与实际回测

研究日期：2026-09-09。金额以初始净资产 100 万元为尺度。报告由保存的回测结果生成；完整会计模型见 [MODEL.md](../docs/MODEL.md)，预先固定方案见 [RESEARCH_PROTOCOL.md](../docs/RESEARCH_PROTOCOL.md)。

## 结论与推荐

**本次研究找到了在明确假设下通过历史测试的混合策略，不能得出“2% 提取率必然不可行”的结论；也没有证明大陆融资可以替代永续 PAL。** 可行方案的核心是控制债务、给普通账户留储备，并接受按月卖少量资产付息、暂停新增融资及必要时还本金。

在用户“年末再平衡、长期 Nasdaq 目标不低于 50%”的配置口径下，优先推荐继续核实 **C1：70% Nasdaq / 30% 现金类资产，年度固定生活费 2%，融资债务新增上限为总资产 10%**。信用账户以现金类资产为主，减少它对 Nasdaq 大跌的直接敏感度。它不是期末净资产最高的候选，但信用账户风险更易控制。

2000-03-27 高点进入、至 2026-09-08：C1 没有担保失败或现金流失败；最低担保比例 299.74%，期末净资产约 269.08 万元，比同配置直接卖资产的 245.46 万元高约 9.62%。约 26.45 年累计预付 27 笔全年预算、共 54 万元生活费，其中只有 22 万元来自配对融资，另外 32 万元直接来自自有资产；累计还本金 4 万元。因此这不是“全程不卖、不还”的包装版本。

**配置口径限制必须单独说明：** 年末目标 70% 不等于每一瞬间股票权重都不低于 50%。C1 在高点路径最低日收盘权重约 51.42%；季度滚动路径最低约 49.60%，最长连续 2 个交易日低于 50%。如果把 beta≥0.5 解释为任何时刻的硬下限，本研究不把 70/30 标为已经满足。预设的 80/20 候选在已测日收盘权重上符合更高下限，但 C1 高点终值反而低于直接卖资产，不能据此推荐加大股票风险。

推荐是模型条件下的候选排序，不是某一家券商的实盘审批结论。具体费率、标的保证金、授信、合约和结算规则未获得用户实际券商确认；在这些条件未知时，A“直接卖资产生活”仍是可执行性更清楚的默认基准。

## 一、对原问题的理解与逻辑审查

任务不是证明借款一定优于卖资产，而是检验：把信用账户融资买入和普通账户等额卖出配对，能否在普通投资者的融资规则下长期得到初始资产每年 2% 的生活费，同时保留有意义的 Nasdaq 敞口。研究必须分别追踪两个账户，并识别“跌破安全线”和“到期生活费付不出”这两种失败。

以下区分事实、假设与待核实规则。

| 原设想 | 审查结果 | 本研究处理 |
| --- | --- | --- |
| 信用融资只能买证券，不能直接提现 | 与融资业务基本定义一致；普通账户资金独立 | 配对卖出款必须进入普通账户并完成交收 |
| 同时融资买入和普通账户卖出同一资产，保持总体敞口 | 忽略交易摩擦时会计上成立 | 逐笔验证配对交易前后净资产守恒；支出时才减少净资产 |
| 这种组合操作已经确认合规 | 现有公开材料不足以替用户的具体合同背书 | 不判定违法，也不把合规当成已核实结论；需券商按完整交易与用途确认 |
| 140% 可作为融资起步所需担保水平 | 不成立：初始保证金和维持担保比例不同 | 100% 保证金、90% 折算率、首次借款，买入后约需 211.11% 比例；不能忽略保证金 |
| 150/140/130 是普遍固定线 | 当前规则由会员结合情况与客户约定最低维持比例 | 140% 是用户指定研究失败线；不把 130% 宣称为所有券商统一强平线 |
| 300% 以上可转出超额担保品 | 大方向正确，但还受保证金可用余额和证券属性限制 | 同时检查两项约束，并保守只转出自有担保品 |
| 信用账户卖出“自有”同代码证券可避免还款 | 证券取得来源不一定能规避同证券负债的还款规则 | 主动信用卖出按先息后本处理，不依赖这种来源区分套利 |
| 利息单利、半年展期，可以永远不付息 | 单利不等于可以无限延期支付；公开合同有按月结息和逾期机制 | 主场景逐日单利、按月真实卖券付息；延期单利仅作条件敏感性 |
| 清偿贷款以后随时借回原规模 | 错误 | 还款后重新借入仍须检查保证金、担保比例及储备，不自动恢复贷款 |
| 信用账户低于 300% 且普通账户不足，就是无解现金流破产 | 若坚持永不还本金会受困；允许还款则不一定 | 先测试能否卖券偿债、释放信用净资产，再判定生活费失败 |
| 20万×(154%−140%)≈2.8万 | 算术成立，前提未被双账户模型确认 | 忽略了融资准入保证金、利息和转账时序；不能作为已验证安全储备 |
| 长期资产增长高于债务增长就安全 | 缺少路径、现金流和期限条件 | 检查每日风险、到期付款和条件展期；平均回报不能替代这些检查 |

基本账户、交易和担保关系依据 [证监会《证券公司融资融券业务管理办法》](https://www.csrc.gov.cn/csrc/c106256/c1654005/content.shtml)。维持比例与转出要求参考 [上交所 2023 年实施细则](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20250616_10782015.shtml)及其[券商转载全文](https://www3.guosen.com.cn/guosen/newxwfiles/upload/2023/09/15/cb8a43cf.pdf)。

**不能忽略保证金是第一项实质性纠错。** 例如借 2 万，担保品需约 2/0.9=2.222 万，买入后信用资产约 4.222 万，比例约 211.11%。这是本研究按公式的推算，并非券商报价。上交所自 2026-01-19 起融资保证金最低比例为 100%，具体券商可更严格；我们还查到券商曾对 511360、513100 公告过 300% 保证金，因此追加了 300% 情景。[上交所 2026 年通知](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20260114_10805174.shtml)、[东北证券公告](https://www.nesc.cn/main/a/20251015/80963.shtml)。

**单利也不等于永续欠息。** 国泰海通公开合同列有月度扣息及息费偿还次序；展期风险揭示也明确，资金、市场和客户条件变化可能导致拒绝。实际 2.8% 报价与 ACT/360 或 ACT/365 日计息基准仍需确认。[合同](https://www.htsec.com/jfimg/colimg/upload/20250407/1743983223138032839.pdf)、[风险揭示书](https://www.htsec.com/jfimg/colimg/upload/20250407/1743983223172069269.pdf)。

传统股票质押“至少 500 万、全部 Nasdaq ETF 不可用”等背景未被本阶段证明为所有产品通行规则；本研究无需依赖这项普遍否定，只研究任务指定的融资融券路线。

## 二、账户模型与 300% 问题的数学出口

普通账户资产 `Ao`、信用账户资产 `Ac`、在途资产 `T`、本金 `P`、应计利息 `I` 分开记录：

`总资产 A=Ao+Ac+T`；`债务 D=P+I`；`净资产 E=A-D`；`信用担保比例 M=Ac/D`。

普通资产不计入 `M`。可提现生活款、现金 ETF、正在结算的款项分别记账。详细份额、合约、保证金、偿债优先级、交易顺序和失败状态见 [MODEL.md](../docs/MODEL.md)，可执行实现见 [backtest.py](../scripts/backtest.py)。

300% 转出线约束“在不还债的情况下直接转出”。若信用资产为 `Ac`、负债为 `D`，卖券还款 `r` 后，比例为 `(Ac-r)/(D-r)`。在信用账户净资产为正时，它随着还款提高；恢复到 300% 所需还款为 `r≥(3D-Ac)/2`。全部清偿后原则上可释放 `Ac-D`。这来自会计关系，不是对未来市场的预测。

例如 `Ac=40万、D=20万`：直接转出为零；还款 10 万后比例恢复到 300%；全还 20 万后剩余 20 万成为无债务资产，可按结算规则转出。真正的限制转为“能否及时卖出、清偿并交收”，而非 300% 本身永远堵死现金流。若证券停牌或流动性不足，该出口仍可能失效。

这并没有免费获得现金：还款缩小投资组合，未来收益和借款能力下降。程序明确记录卖出、还款与释放，不用无条件重新融资抹掉代价。

## 三、候选规则——事先固定，可机械执行

年度预算 `W=初始净资产×2%`，主场景名义金额固定；不根据当年市值下调。所有候选总资产目标分别测试 50%、60%、70%、80% Nasdaq，其余现金。共同年末再平衡；不买杠杆 ETF。

| 条件 | C1：低债务现金融资 | C2：提高现金融资参与度 | C3：融资买 Nasdaq |
| --- | --- | --- | --- |
| 信用融资买入 | 现金类 ETF | 现金类 ETF | Nasdaq 代理 ETF |
| 首选新增担保品 | 现金类 ETF | 现金类 ETF | 现金类 ETF |
| 新借后 `(D+W)/A` 上限 | 10% | 20% | 15% |
| 存量债务超过何值退出 | 15% | 25% | 20% |
| 新借后信用比例 | ≥300% | ≥300% | ≥300% |
| Nasdaq 再跌 50% 的信用压力比例 | ≥160% | ≥160% | ≥160% |
| 新借后普通账户总储备 | ≥3 年生活费 | 同左 | 同左 |
| 新借后普通现金类储备 | ≥1 年生活费 | 同左 | 同左 |
| 普通账户配对卖出 | 等额现金 ETF | 等额现金 ETF | 等额 Nasdaq |

共同流程：

1. 首年生活费来自已有现金资产；从第二年起，在周年前至少 5 个交易日准备资金。仅使用当前已知价格和账户信息。
2. 检查新借约束和保证金余额；按 310% 目标提前转入担保品，另留 14 天存量利息余量。隔结算期后用最新价格重新审核，成交后至少 300%。如果现金担保品不足，不通过无限转入股票强行借款。
3. 获准则信用买入 `W`，普通卖出等额同类资产，交收后提现；未获准则普通现金→普通股票的顺序直接支付。不削减生活费。
4. 每日开盘，如担保比例低于 220%、信用股票再跌 50% 后压力比例低于 160%、债务超过退出上限、普通账户资产不足 2 年预算，则清偿信用债务并转出余额。已经跌破 140% 的开盘或日内行情必须先判失败，不能事后补救成成功。
5. 月度先从信用现金类证券卖出付息。年末优先在普通账户再平衡；若无法完成，清偿信用债务释放库存，交收后继续调回目标。再平衡可能使普通现金储备低于新借时的一年门槛，日表不会把它隐藏。
6. 半年合约提前评估。主假设允许符合条件的展期；被拒即清偿。只有下次年度预算窗口满足全部条件时才考虑新贷款，不自动恢复原债务规模。

这些规则是公开、固定的阈值，没有使用 2000 顶部或未来底部作交易信号。选择历史最高日只是压力测试起点，不是策略判断信号。阈值没有经过全历史最优搜索；代码开发中仅增加了交收期间计息的预留，以及守恒检查。追加的较高保证金、组合不利情景和 8%/12% 债务上限仅作敏感性，不据此重选“最优参数”。

现金类融资标的并非纯粹假想：上交所 2026-07-13 生效名单含 511360 短融 ETF 和 513100 纳指 ETF。但交易所资格不等于券商当天一定提供贷款，短融 ETF 也不是保本现金。主回测按任务许可采用确定现金收益代理。[交易所名单](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20260710_10825136.shtml)。

## 四、数据、基准与实验范围

- QQQ 数据：1999-03-10 至 2026-09-08，共 6,917 个交易日。原始响应、标准化日数据及 SHA-256 见 [data/audit.json](../data/audit.json)。来源为 [Yahoo QQQ 历史页](https://finance.yahoo.com/quote/QQQ/history/)对应 chart 接口。发行人确认 QQQ 始于 1999-03-10。[Invesco](https://www.invesco.com/qqq-etf/en/home.html)。
- 主价格采用股息复权日行情，近似股息再投资的 QQQ 风险资产。它不是逐笔分红到账和中国 ETF 价格重建；另测裸价格、不含红利。主现金收益 1.5%，融资 2.8%，ACT/365。
- 数据检查包括唯一日期、正值、OHLC 一致性和长休市缺口。2001-09-10 到 09-17 等缺口保留，不用插值伪造交易日。复权收盘最大历史回撤约 82.96%，在 2002-10-09 达到。
- CLEC 项目以 commit `f31ee2b9e22b37b100f4b2eb75e81de415ae3bb7` 留存参考；其价格文件是月频，不能直接承担本研究的日内账户检查。315 个共同完整月份对比，只有 2026-03 的差异超过 0.1%，参考仓库可能是月内截取。它与本研究数据同属 Yahoo 上游，**不能算独立双源验证**。[参考源码](https://github.com/yutaofr/clec-strategy-backtest)。
- A：零融资，年末同样回到配置目标，提前卖资产准备生活费。B：理想合并抵押 PAL，所有年度生活费可借出、利息资本化，无 300% 转出限制，仍检查 140%。另设 `B_cash` 用资产付息帮助识别比较差异。
- 高点压力：固定 2000-03-10 和 2000 年 3 月 QQQ 最高收盘日 2000-03-27，两组起点各测六种模式、四档配置，共 48 例。
- 季度滚动：每策略/配置有 106 个至少一年、截至数据末日的路径；完整 5 年 90 个、10 年 70 个、20 年 30 个。24 种组合共 7,104 条滚动路径。另有 169 条预设及 30 条追加敏感性，总计 7,351 次实验。
- 因中国融资业务和相关 ETF 在 2000 年并不存在，这是将当前假设规则作用于历史 QQQ 风险路径的反事实模拟。不能称为过去真实可成交业绩。

## 五、2000-03-27 高点进入的结果

以下主表均为 **70/30、每年 2 万生活费、融资 2.8%、现金收益 1.5%**，期间至 2026-09-08。所有表中“万元”都是同一初始 100 万单位，未调整通胀。

{detail}

最低担保比例包含日内最低价估值；runway 为每日收盘最低值。B 的“普通 runway”只是合并抵押资产的类比读数，不受大陆普通账户提现约束，不能直接拿它的储备衡量信用账户安全。C1/C2/C3 的普通现金 runway 曾为零，表示现金类资产被再平衡或划转用尽，不表示普通股票、未来收入或整个普通账户也为零；它们仍按提前准备流程完成支付。

{finance}

在高点路径，C1 相对 A 的累计终值优势约 9.62%；C3 约 19.60%。C3 借款参与更多，但信用股票价格波动直接影响安全边界。B 的优势很大，原因同时包含利息资本化、始日即可借款、无普通库存限制、无本研究主动债务上限等；**不能把 B−C 的全部差额归因于 300% 一条规则**。同样用资产支付利息的理想 PAL `B_cash` 在 70/30 下期末约 453.40 万元，仍然远高于三套大陆混合候选。

各配置的期末净资产：

{crossbeta}

这说明提高融资比例或股票权重不会机械地提高最终净资产。C1/C2 的 80/20 在此路径均约 212.97 万，低于 A 的 223.39 万；C2 在 70/30 也落后于 C1。没有理由仅因“能多借”就采用更高债务上限。

C1 70/30 的关键历史截面：

{milestone_table}

现金信用账户的担保比例较稳定，不代表整个组合没有大回撤。其普通股票和净资产仍经历了互联网泡沫与金融危机的损失。维持比例只衡量信用抵押池，不是整个投资者的财富稳定程度。

指定 2000-03-10 起点也已单独完成：

{march10}

## 六、滚动起点，而非仅检验一条路径

以下为 70/30，同日期、同期限配对比较终值；优势为“融资策略期末净资产/A期末净资产−1”的中位数，不是年化超额收益。

{rolltable}

主设定下，所有四档配置的 A/B/C1/C2/C3/N 在所测滚动窗口均没有担保或现金流失败。窗口高度重叠；零失败不能换算成“未来成功率 100%”。尤其“至末日”把长短期限混在一起，只作描述，不作为推荐的唯一证据。

完整 20 年窗口中，70/30 的 C1 相对 A 终值优势中位数约 7.45%，90% 窗口胜过 A；C3 的对应值约 8.22%、96.67%。这种幅度可能被实盘摩擦、利率变化、税制和执行差异侵蚀，不能只看一条高点路径的终值。

## 七、敏感性和失败案例

所有行都是 2000-03-27 起，除注明外维持主参数；这里不对失败案例给出可与完整期限混比的终值排名。

{sensitivity}

关键含义：

- C1 70/30 的融资利率变为 6% 后，期末仅约 247.93 万，对 A 的优势几乎消失。
- 2008 年起拒绝展期时，C1 可以通过还款继续生活，但期末约 229.43 万，低于 A 的 245.46 万。**避免破产不等于融资有收益优势。** 该情景仍允许新贷款，所以会出现多次借入后半年内再偿清；同时关闭新贷的独立情景也已测试。
- 现金收益 0%、融资 6%、生活费每年涨 2% 的组合不利情景中，C1 70/30 约 147.88 万，略低于 A 的 148.53 万。策略并不在所有假设下占优。
- 提取率从 2% 改成 3% 时，C1 70/30 虽未失败，却显著落后于直接卖资产。因此本阶段推荐没有顺势提高到 3%。
- 8%/12% 新增债务上限的 C1 70/30 终值约 272.89/257.12 万，均通过本高点测试；没有把较优的 8% 事后升级成经过验证的最优值。

实际出现的失败：

{failtable}

C3 80/20、3% 提取的现金流失败发生时债务已经为零，账户剩余约 0.75 万，无法再支付 3 万年预算。这属于资产耗尽导致的生活费失败，**不是被 300% 锁住而不能转出**。日表和事件流保留了这一差别，避免误诊失败原因。

股票权重的漂移也必须披露：

{beta}

60/40 高点路径曾连续 108 个交易日低于 50%，所以如果用户不接受持续数月的低权重，不应把 60/40 作为“任何时候 beta 都至少 0.5”的达标方案。70/30 更接近原偏好，但仍不能承诺日内永不越界。把现金安全垫纳入净资产后，负债还会提高净资产 beta，详细读数在日表。

## 八、下一步实盘核实条件与最终取舍

可以保留继续研究的两套方案：

1. **优先 C1 70/30、2% 固定名义预算**：融资参与适中，信用账户主要是现金类资产；样本中安全余量大。愿意接受借款中断、付息卖券和必要还本金，是方案成立的前提。
2. **C3 70/30 作为替代候选**：若现金 ETF 融资不可得、Nasdaq 融资条件更适合，或愿意承担更高信用账户波动，可进一步核实。历史终值更高，但结算延迟敏感性更明显，不以此直接宣布最优。

C2 没有展现足以补偿额外融资规模的稳定优势，不列为优先。若要求永远不还本金、永远不卖任何投资资产或所有利息都靠续借，该要求没有被本研究验证为可执行方案。若利率明显高于主假设，或展期、新贷条件不稳定，直接卖资产更有说服力。

用户实际券商仍需给出：513100/拟用现金 ETF 的当日融资资格和逐证券保证金/折算率；2.8% 有效期、计息基准、扣息及逾期条款；普通与信用账户同证券卖出规则及完整配对交易的合同适用性；担保品和卖出款到账时序；半年展期的明确条件、授信上限和被拒后的处理。以上不是让用户再次批准研究，而是本任务要求区分的尚未确认规则。

本阶段没有证明未来无限期安全，也没有完成全市场、全部券商和所有可能固定规则的最优化。已经完成的是：纠正关键逻辑、建立可审计状态模型、固定三套候选、用真实日行情运行高点与滚动测试，并公开成功条件、失败案例和融资不划算的情景。

## 九、文件与复现

Python 3.11+，仅标准库，无第三方依赖。已在本机 Python 3.14.3 实际运行。

```powershell
python fetch_data.py
python -m unittest -v
python run_research.py
python verify_results.py
python build_report.py
```

单独复现推荐候选：

```powershell
python backtest.py --strategy C1 --weight 0.7 --start 2000-03-27 --trace
```

- [backtest.py](../scripts/backtest.py)：状态、交易和日频循环。
- [test_backtest.py](../scripts/test_backtest.py)：16 项测试，涵盖账户分离、初始保证金、转账延迟、300% 转出、还款释放、单利、FIFO、不能无条件重借、配对融资守恒、未来数据不影响历史前缀、日内先失败和展期拒绝。
- [data/audit.json](../data/audit.json)：数据来源、覆盖、原始哈希、缺口和参考数据差异。
- [results/stress_cases.json](../results/stress_cases.json)：48 个高点压力结果。
- [results/experiments.json](../results/experiments.json)：7,273 个滚动及预设敏感性结果。
- [results/rolling_summary.json](../results/rolling_summary.json)：各策略、权重、期限分组统计。
- [results/additional_stresses.json](../results/additional_stresses.json)：30 个追加敏感性结果。
- [results/traces](../results/traces)：全部高点案例逐日账户与交易事件流。

验证结果：16 项测试全部通过；48 个保存的高点结果在加入每日交易净资产守恒检查后逐字段完全复现；本金、利息和非负库存检查在日循环中运行。停止于失败日的结果保留 `end_actual`，不会冒充持有到样本末日的完整收益。
'''
    (ROOT/'reports/第一阶段研究报告.md').write_text(text, encoding='utf-8')
    print('Report written: 第一阶段研究报告.md')


if __name__ == '__main__':
    main()
