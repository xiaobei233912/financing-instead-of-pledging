"""Current report refresh with rate-specific data and explicit failed horizons."""
from pathlib import Path
import json,sys

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results/partial_living_cash1_rate3'
R=ROOT/'reports'
def read(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
main,rolling,stress,order,prior=[read(n+'.json') for n in ['main','rolling','stress','order_comparison','rate_comparison']]
names=['relay70','relay80','relay70_w3']
labels={'relay70':'70/30接力 · 2%','relay80':'80/20接力 · 2%','relay70_w3':'70/30接力 · 3%',
        'sale80':'80/20卖资产 · 2%','pal80':'80/20 PAL · 2%'}
def wan(v):return f'{v/10000:,.2f}'
def pct(v):return '—' if v is None else f'{v*100:.2f}%'
def status(r):return '完成' if not r['failure'] else ('支付失败' if r['failure']=='LiquidityFailure' else r['failure'])+' '+r['end_actual']
def table(h,rs):return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rs])
def get(n,start='2000-03-27'):return next(r for r in main if r['name']==n and r['start']==start)
f=get('relay70_w3')
t=['# 现金接力：部分融资规则更新（现金1%、融资3%）',
   '2026-09-15更新。数据截止2026-09-08。本报告和所链接逐年账均已按现金收益1%、接力融资3%单利重新计算；PAL为3%复利。先前现金2%/融资2.8%的结果单列作参数对照。',
   '## 本次结论',
   f'2000年高点起投，70/30提取2%和80/20提取2%完成；70/30提取3%在{f["end_actual"]}发生生活费支付失败。原来“3%通过但余量偏薄”的说法不适用于这组新利率。',
   f'两种2%配置的最低普通现金储备分别为{get("relay70")["min_cash_years"]:.2f}年和{get("relay80")["min_cash_years"]:.2f}年开销。不能沿用旧参数下8.31年和3.08年的安全余量。',
   '## 固定规则与本次范围',
   '初始100万元；70/30或80/20；年生活费为初始资产2%或3%，固定名义金额。现金（含现金类担保证券）年收益1%；接力融资3%单利挂息，不主动还本付息。PAL的3%仍为利息本金化的复利，两种计息方法不混同。',
   '维持率高于300%时，先转出可用自有担保品，再融资买回等额股票，允许部分融资，不足生活费由普通现金补足；年度先获取并支付生活费，再做比例再平衡。转出按已有债务审核，融资买回后的维持率允许低于300%。',
   '`融资额 = min(全年预算, max(0,信用资产−3×已有负债), 可转自有股票, max(0,保证金可用余额)/(股票折算率+融资保证金比例))`。已有负债包括未付利息。',
   '70/30买股现金底线30万元、80/20为20万元；只限制再平衡买股，生活费及补担保仍可动用。维持率低于160%时，用现金类证券补担保至200%，允许用全部普通现金；140%是研究停止线。股票折算率70%、现金类90%、融资保证金比例100%，其他交易与交收规则不变。',
   '本次重跑三种接力配置的五个历史起点、两个起点的卖资产/PAL对照、306个固定期限滚动窗口、24组压力情景和12组融资顺序对照。压力表中明确列出的0%现金、4%或6%融资利率属于敏感性覆盖，其余参数均从1%现金/3%融资基准出发。',
   '实盘边界：先转后借仍是本研究的执行假设，未增加券商按后续融资后的日终状态重新否决划转的机制；具体审核时点需以券商为准。公开规则依据仍见[上交所细则](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20250616_10782015.shtml)。',
   '## 2000年高点：现金接力、卖资产、PAL同口径比较',
   '起点2000-03-27，终点2026-09-08；下表四种策略均每年花初始资产2%，累计支付54万元。净资产已扣除全部本金和未付利息。卖资产和PAL每年恢复80/20，现金收益也统一为1%。',
   table(['策略','状态','期末净资产/万元','期末负债/万元','最低维持率','累计补担保/万元'],
         [[labels[n],status(r),wan(r['net']),wan(r['debt']),pct(r['min_mmr']),wan(r['rescue_cash_in'])] for n in ['sale80','relay70','relay80','pal80'] for r in [get(n)]])]
sale=get('sale80')['net']
t += [f'相对80/20卖资产，70/30接力期末净资产高{(get("relay70")["net"]/sale-1)*100:.1f}%，80/20接力高{(get("relay80")["net"]/sale-1)*100:.1f}%，PAL高{(get("pal80")["net"]/sale-1)*100:.1f}%。70/30与80/20目标股票配比不同，不能把差额全部归因于借款方式。PAL是整体组合直接担保借出现金的理想化对照，不受大陆担保品转出300%约束。',
      '![2000年同开销净资产对比](assets/partial_living_rates/2000_comparison.png)',
      '## 三种接力配置的现金余量和参数变化',
      table(['配置','新状态','旧参数期末净资产/万','新参数期末或终止净资产/万','最低普通现金/年开销','最低维持率','累计补担保/万'],
            [[labels[n],status(r),wan(next(x for x in prior if x['name']==n and x['start']=='2000-03-27')['old']['net']),wan(r['net']),f'{r["min_cash_years"]:.2f}',pct(r['min_mmr']),wan(r['rescue_cash_in'])] for n in names for r in [get(n)]]),
      '旧参数指同样先转后借/部分融资，但现金2%、融资2.8%。失败配置的资产为终止当天余额，不能当作2026年期末值，也不能与完整期限直接比较收益。',
      table(['配置','全额融资年','部分融资年','纯现金决策年','累计已付生活费/万'],[[labels[n],r['full_finance_years'],r['partial_finance_years'],r['cash_only_years'],wan(r['living_paid'])] for n in names for r in [get(n)]]),
      '融资年份统计包含最终失败年度的融资决策，不表示该年预算已支付；逐年账另列实际已付生活费。最低普通现金不含在途资产，因此出现0并不代表所有可变现资产归零。',
      '## 70/30提取3%：失败当天发生了什么',
      f'2017年1月3日，信用账户维持率约302.55%，按新规则划转并融资约6,683.48元；转出股票次日卖得约6,705.89元。连同原普通现金，支出日可用现金共{f["ordinary_cash"]:,.2f}元，距离3万元全年预算仍差{30000-f["bank_liquid"]:,.2f}元。',
      f'2017年1月5日维持率约{f["mmr"]*100:.2f}%，低于300%，可转自有股票额度为0。此时仍有约{wan(f["credit_stock"])}万元信用股票，净资产约{wan(f["net"])}万元，问题是按当前规则无法释放足够现金支付全年预算。已经支付2000—2016年的51万元；2017年整年预算未支付。',
      '最低普通现金记录为0，发生在1月4日现金已转为在途待到账时；1月5日到账现金为上述2.70万元，不能把“0年现金”解读为失败日一分钱都没有。',
      '这属于当前年度支付规则下的流动性失败，不是净资产归零，也未触及140%研究停止线。失败日先调仓也无法凭空解除300%转出限制；改成更早准备现金、分月支出、还款救险或修改既往融资路径，属于另外的策略分支。',
      '## 2009年低点起投',
      table(['策略','状态','期末净资产/万','期末负债/万','累计生活费/万'],[[labels[n],status(r),wan(r['net']),wan(r['debt']),wan(r['living_paid'])] for n in ['sale80','relay70','relay80','pal80','relay70_w3'] for r in [get(n,'2009-03-09')]])]
gs=get('sale80','2009-03-09')['net']
t += [f'2009起点同为80/20时，接力比卖资产高{(get("relay80","2009-03-09")["net"]/gs-1)*100:.1f}%，PAL高{(get("pal80","2009-03-09")["net"]/gs-1)*100:.1f}%；70/30接力仍低于80/20卖资产。3%版本支付54万元，其他四个2%版本支付36万元，跨开销比较需区分。',
      '## 其他历史起点',
      table(['起点','配置','状态','期末或终止净资产/万','最低现金/年开销'],[[r['start'],labels[r['name']],status(r),wan(r['net']),f'{r["min_cash_years"]:.2f}'] for r in main if r['name'] in names and r['start'] not in ['2000-03-27','2009-03-09']]),
      '## 10年/20年滚动窗口',
      table(['配置','年限','窗口数','失败数','最低维持率','最低普通现金/年开销'],[[labels[n],years,len(g),sum(bool(x['failure']) for x in g),pct(min(x['min_mmr'] for x in g)),f'{min(x["min_cash_years"] for x in g):.2f}'] for n in names for years in [10,20] for g in [[x for x in rolling if x['name']==n and x['years']==years]]]),
      '起点为季度首个可用交易日；窗口相互重叠，不是独立样本，历史失败占比不是未来失败概率。2000-03-27主路径与季度首日的起点不同，不应以滚动窗口取代高点主路径。']
fail=[r for r in rolling if r['failure']]
if fail:t.append(table(['失败配置','起点','年限','终止日期','类型'],[[labels[r['name']],r['start'],r['years'],r['end_actual'],r['failure']] for r in fail]))
sl={'cash0':'现金0%（融资3%）','rate4':'融资4%（现金1%）','rate6':'融资6%（现金1%）','inflation2':'生活费年增2%',
    'extra_drop20':'2008低位额外永久跌20%','flat40':'人工40年横盘','bear_then5_40':'人工先10年每年跌5%，后30年每年涨5%',
    'combined':'融资4%+现金0%+开销年增2%+股票年损耗1%'}
t += ['## 压力测试（除明确覆盖项外均为现金1%、融资3%）',
      table(['情景']+[labels[n] for n in names],[[label]+[status(next(x for x in stress if x['name']==n and x['scenario']==s)) for n in names] for s,label in sl.items()]),
      '失败类型按模型原样报告。支付失败仅表示当日无法支付整年预算；维持率失败是触及140%的研究停止线。压力路径是人为情景，不代表未来概率；完整失败余额、可转额度和现金缺口见结果目录的 failure_diagnostics.json。',
      '## 融资操作顺序对照（同为现金1%、融资3%）',
      '下表全部从2000-03-27开始，先付生活费再再平衡不变。仅对照全额或零融资、部分融资但完成后仍300%、部分融资先转后借。失败时余额不与2026年终值作收益排名。',
      table(['配置','融资规则','状态','期末或终止净资产/万','最低现金/年开销'],[[labels[n],label,status(r),wan(r['net']),f'{r["min_cash_years"]:.2f}'] for n in names for mode,label in [('full_post300','全额或零，完成后300%'),('partial_post300','部分融资，完成后300%'),('partial_transfer_first','部分融资，先转后借')] for r in ([get(n)] if mode=='partial_transfer_first' else [x for x in order if x['name']==n and x['start']=='2000-03-27' and x['mode']==mode])]),
      '## 逐年双账户账与验证']
for n in names:
    sections=[f'# {labels[n]}逐年账（现金1%、融资3%）','金额单位万元；维持率分期末及年内最低。普通现金不含在途资产。失败年度明确显示实际已付生活费为0。']
    for start in ['2000-03-27','2009-03-09']:
        annual=read(f'{n}_{start}_annual.json')
        sections += [f'## {start}入场',table(['年','融资状态','融资额','现金补足计划','实际已付生活费','普通现金','普通总值','信用股票','信用现金类','本金','未付息','期末维持率','年内最低','净资产','补担保','失败'],
            [[a['year'],{'full':'全额','partial':'部分','cash_only':'纯现金'}.get(a.get('finance_status'),'未执行'),wan(a['financed_amount']),wan(a.get('cash_topup_planned',0)),wan(a['living_paid']),wan(a['ordinary_cash']),wan(a['ordinary_total']),wan(a['credit_stock']),wan(a['credit_cash']),wan(a['principal']),wan(a['unpaid_interest']),pct(a['mmr']),pct(a['min_mmr']),wan(a['net']),wan(a['rescue_cash_in']),a['failure'] or '—'] for a in annual]),
            f'[年度JSON](../results/partial_living_cash1_rate3/{n}_{start}_annual.json) · [日频账](../results/partial_living_cash1_rate3/{n}_{start}_daily.json) · [事件](../results/partial_living_cash1_rate3/{n}_{start}_events.json)']
    path=R/f'现金接力部分融资_逐年账_{n}.md';path.write_text('\n\n'.join(sections)+'\n',encoding='utf-8')
    t.append(f'- [{labels[n]}逐年账]({path.name})')
t += ['所有主路径核对逐年损益、双账户资产负债恒等式、零还款、融资及转出限额、生活费先于再平衡。失败路径终止年度未付款不计入累计生活费。',
      '复现：`python scripts/run_partial_living_rates.py`；生成本报告：`python scripts/build_partial_living_rates_report.py`。数据目录：`results/partial_living_cash1_rate3/`。原参数数据仍在 `results/partial_living/`；报告更新前备份在 `tmp/partial_living_before_rate_update/`。',
      '本文为QQQ复权代理回测，不是境内ETF人民币实盘结果；未计汇率、溢折价、税费、实际合同变动和理财赎回限制。现金1%与融资3%是本次指定研究参数，不是市场报价。']
(R/'现金接力_部分融资规则更新.md').write_text('\n\n'.join(t)+'\n',encoding='utf-8')

sys.path.insert(0,str(ROOT/'results/smart_relay_python'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False})
fig,ax=plt.subplots(figsize=(10,5.5),dpi=160);fig.subplots_adjust(left=.26,right=.94,top=.77,bottom=.25)
ns=['sale80','relay70','relay80','pal80'];vs=[get(n)['net']/10000 for n in ns]
ax.barh(range(4),vs,color=['#89969F','#267A70','#416C92','#807391'],height=.55)
ax.set_yticks(range(4),[labels[n] for n in ns],fontsize=12);ax.invert_yaxis();ax.set_xlim(0,max(vs)*1.35)
for i,v in enumerate(vs):ax.text(v+8,i,f'{v:,.2f}万',va='center',fontsize=12)
ax.set_xlabel('期末净资产（万元，已扣全部负债）',fontsize=11)
for sp in ax.spines.values():sp.set_visible(False)
ax.tick_params(length=0);ax.set_axisbelow(True);ax.grid(axis='x',alpha=.15)
fig.text(.05,.91,'2000年高点入场：现金1%，借款3%',fontsize=20,weight='bold')
fig.text(.05,.84,'初始100万元，每年花2万元；2000-03-27至2026-09-08',fontsize=11)
fig.text(.05,.08,'均已支付54万元生活费；接力3%单利，PAL 3%复利；QQQ复权代理。\n接力采用先转后借、部分融资；实际划转审核时点仍需券商确认。',fontsize=10,color='#53616A')
assets=R/'assets/partial_living_rates';assets.mkdir(parents=True,exist_ok=True);fig.savefig(assets/'2000_comparison.png');plt.close(fig)
print('Report, three annual ledgers, comparison chart updated.')
