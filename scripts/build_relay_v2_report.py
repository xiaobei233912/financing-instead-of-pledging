from pathlib import Path
import json

ROOT=Path(__file__).parent.parent
OUT=ROOT/'results'/'7030_relay_v2'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))

stress=read('stress.json');rolling=read('rolling_summary.json');sens=read('sensitivity.json')
r=next(x for x in stress if x['start']=='2000-03-27')
events=read('cash_trigger_30_2000-03-27_events.json')
daily=read('cash_trigger_30_2000-03-27_daily.json')
annual=read('cash_trigger_30_2000-03-27_annual.json')
paused=[x['date'] for x in events if x['kind']=='finance_paused']
sales=[x for x in events if x['kind']=='rebalance_transfer_sell']
partial_sales=[x for x in sales if x.get('remaining',0)>.01]
assert all(x['credit_cash_assets']==0 for x in daily)
lines=['# 7030现金接力：现金底仓版（R7030-300-15-v2）', '',
'2026-09-11，按用户最新澄清重跑。此版本替代上一轮“双向暂停再平衡”的解释；旧结果保留，不能用于代表本策略。', '',
'## 确认的交易规则', '',
'设初始净资产为 E0，当前总资产为 A，股票市值为 S，普通现金为 C，现金门槛 F=30%×E0。主案例E0=100万元，F=30万元，固定年度生活费2万元。当前总资产A未扣融资负债；净资产另列A−本金−未付息。', '',
'1. 初始70%股票放信用账户，30%现金类资产放普通账户。信用账户持有自有股票和融资买入股票；不配置现金类资产。',
'2. 每年年末再平衡。若S>70%×A，可以卖出超配股票补普通现金，即使C<F也允许；实际转出仍受担保品可提额度、自有股票库存、保证金及300%约束。额度不足只完成允许部分，不主动卖信用证券还款。',
'3. 若C>F且C>30%×A，才允许用现金补股票。买入额=min(C−F，70%×A−S)，并以已到账可交易现金为限。这样既保留初始资产30%的现金，也不会买到超过当前总资产70%的股票。生活支出可以突破现金门槛，买股再平衡不可以。',
'4. 每年筹备生活费时审核融资。维持率不高于300%时暂停；后来恢复后可再次申请，并非永久停止。即使融资前高于300%，新增债务及转出后仍须不低于300%，并满足保证金及可转自有担保品条件。',
'5. 具体动作是融资买股票，同时转出等额自有股票担保品，到普通账户卖出支付生活费；不直接提现融资款。无法完成时使用普通现金支付年度生活费。',
'6. 允许长期挂息：本金按2.8%年利率、ACT/365单利计息；未付息进入总债务，不自动滚入计息本金。现金类收益为确定年率2%。无主动还本、付息或补担保。', '',
'例：初始100万元，现在股票20万元、现金35万元。目标买入额18.5万元，但现金门槛只允许动用5万元，因此只买5万元，保留30万元现金。若现在股票130万元、现金70万元，只需买10万元恢复70/30，而不是把超过初始门槛的40万元全部买入。', '',
'## 2000年高点起步', '',
f"窗口{r['start']}—{r['end_actual']}；状态：{r['failure'] or '未触发模型失败线'}。", '',
'| 指标 | 结果 |','| --- | ---: |',
f"| 期末净资产 | {r['final_net']/10000:.2f}万元 |",
f"| 期末负债 | {r['final_debt']/10000:.2f}万元 |",
f"| 本金 / 未付息 | {r['principal']/10000:.2f} / {r['interest']/10000:.2f}万元 |",
f"| 期末普通现金 | {r['final_cash']/10000:.2f}万元 |",
f"| 累计生活费 | {r['living_paid']/10000:.2f}万元 |",
f"| 融资支付 / 自有现金支付 | {r['financed_years']}年 / {r['cash_years']}年 |",
f"| 最低信用维持率 | {r['min_mmr']*100:.2f}%（{r['min_mmr_date']}） |",
f"| 最低普通现金 | {r['min_cash']/10000:.2f}万元，{r['min_cash_years']:.2f}年开销 |",
f"| 股票占总资产区间 | {r['min_weight']*100:.2f}%—{r['max_weight']*100:.2f}% |",
f"| 净资产最大回撤（包含生活费流出） | {r['max_drawdown_with_spending']*100:.2f}% |",
f"| 累计还本 / 付息 | {r['principal_repaid']:.2f} / {r['interest_paid']:.2f}元 |",
'| 信用账户现金类资产 | 全程0 |', '',
'融资暂停的筹备日：'+('、'.join(paused) or '无')+'。', '',
f'现金不足而跳过买股的年末次数：{r["skipped_rebalances"]}。卖股再平衡尝试{len(sales)}次，其中因转出额度或自有担保品库存不足而未达到目标的有{len(partial_sales)}次。部分买股未达70%可能是主动保留现金门槛，并非操作失败。', '',
'信用账户只持股票是本模型的实际结果，已经逐日断言检查：现金类证券、融资买入现金类证券以及信用闲置现金合计始终为零。证券和卖款可能跨日交收，在途资产单独核算，不提前算入信用担保。', '',
'## 多起点结果', '',
'全部截至2026-09-08，投资期限不同，终值不能横向排名。', '',
'| 起点 | 净资产/万元 | 最低维持率 | 最低现金/年 | 融资/现金年数 | 失败 |',
'| --- | ---: | ---: | ---: | ---: | --- |']
for x in stress:
    lines.append(f"| {x['start']} | {x['final_net']/10000:.2f} | {x['min_mmr']*100:.2f}% | {x['min_cash_years']:.2f} | {x['financed_years']}/{x['cash_years']} | {x['failure'] or '无'} |")
lines += ['', '## 固定期限滚动测试', '',
'各季度首个可用交易日起步；首个样本始于1999-03-10。窗口结束于起点加10或20周年的前一天，避免多领取一次下一年的生活费。', '',
'| 年限 | 窗口数 | 失败数 | 最低期末净资产/万元 | 最低维持率 | 最低现金/年 |',
'| --- | ---: | ---: | ---: | ---: | ---: |']
for x in rolling:
    lines.append(f"| {x['years']} | {x['n']} | {x['failures']} | {x['min_net']/10000:.2f} | {x['min_mmr']*100:.2f}% | {x['min_cash_years']:.2f} |")
lines += ['', '窗口高度重叠；零失败不等于未来失败概率为零。', '',
'## 参数敏感性：2000高点起步', '',
'| 变更项 | 净资产/万元 | 最低维持率 | 最低现金/年 | 状态/结束日 |',
'| --- | ---: | ---: | ---: | --- |']
names={'cash_0':'现金收益0%','rate_4':'融资利率4%','rate_6':'融资利率6%',
       'settlement_3':'各交收环节3交易日','renewal_200':'续约最低维持率200%',
       'precheck_only':'旧歧义对照：只检查买股前现金，买股后不保留门槛'}
for x in sens:
    lines.append(f"| {names[x['variant']]} | {x['final_net']/10000:.2f} | {x['min_mmr']*100:.2f}% | {x['min_cash_years']:.2f} | {x['failure'] or '完成'}/{x['end_actual']} |")
lines += ['', '对照分支仅用于解释规则差异，不是本轮确认的主策略。若有失败，失败日净资产不与完整终值比较。', '',
'## 年度账表', '',
'年内最后收盘；2026年为样本截止日，当日发起的调仓可能仍在途。', '',
'| 日期 | 净资产/万元 | 普通现金/万元 | 债务/万元 | 股票占比 | 累计融资年数 |',
'| --- | ---: | ---: | ---: | ---: | ---: |']
for x in annual:
    lines.append(f"| {x['date']} | {x['net']/10000:.2f} | {x['ordinary_cash']/10000:.2f} | {x['debt']/10000:.2f} | {x['stock_weight']*100:.2f}% | {x['financed_years']} |")
lines += ['', '## 数据与执行边界', '',
'使用项目既有QQQ复权日频OHLC快照，1999-03-10—2026-09-08共6917行，哈希记录于results/7030_relay_v2/provenance.json。不补造上市前行情。现金收益2%为固定收益代理，并非实际现金ETF历史。', '',
'延续上一轮每年年末开盘再平衡、周年支付生活费、提前8个交易日筹备、主情景划转T+1及卖款可提现T+1。第一年即融资，但在两个交收周期后支付首年预算。只在年度筹备时申请生活融资，非盘中每日借款。', '',
'主场景假设券商允许长期挂息及每六个月续约，不另设续约门槛；200%续约门槛列敏感性。检查开盘、操作后、日内最低价和收盘，信用维持率低于140%即记MarginFailure，不能靠随后价格恢复掩盖；周年现金不足记LiquidityFailure。140%为项目研究参数。忽略汇率、国内ETF折溢价、税费、国内节假日差异和成交障碍。这是合同假设下的历史模拟。', '',
'验证：每日核对净资产守恒、本金借还勾稽、利息勾稽、非负库存及信用现金为零。23项单元测试通过，新增覆盖现金不足仍可卖股、买股保留初始现金门槛、买股不超过70%目标。', '',
'复现命令：`python -m unittest test_relay_backtest test_backtest -v`，`python run_relay_v2.py`，`python build_relay_v2_report.py`。日账、事件、年度表、102个滚动窗口和6个参数分支存于results/7030_relay_v2。', '']
(ROOT/'reports/7030现金接力策略回测报告_v2.md').write_text('\n'.join(lines),encoding='utf-8-sig')
print(json.dumps(r,ensure_ascii=False,indent=2))
