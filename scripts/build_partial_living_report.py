"""Human-readable summary and separate yearly two-account ledgers."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results/partial_living'
REPORTS=ROOT/'reports'
main=json.loads((OUT/'main.json').read_text(encoding='utf-8'))
oldnew=json.loads((OUT/'old_vs_new.json').read_text(encoding='utf-8'))
rolling=json.loads((OUT/'rolling.json').read_text(encoding='utf-8'))
stress=json.loads((OUT/'stress.json').read_text(encoding='utf-8'))
labels={'relay70':'70/30 · 2%','relay80':'80/20 · 2%','relay70_w3':'70/30 · 3%',
        'sale80':'80/20卖资产 · 2%','pal80':'80/20 PAL · 2%'}
names=['relay70','relay80','relay70_w3']
def wan(v):return f'{v/10000:,.2f}'
def pct(v):return '—' if v is None else f'{v*100:.2f}%'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])

text=['# 现金接力：部分融资与先取生活费规则更新',
      '研究日期：2026-09-15。QQQ复权数据仍截止2026-09-08；原始行情及旧研究结果保持原状。',
      '## 执行规则和核对结果',
      '原模型已按“年初准备生活费 → 担保品到账卖出 → 生活费到账并支付 → 比例再平衡”执行，默认 `rebalance_first=False`。本次没有改变这个先后顺序；初始建仓年度仍不额外再平衡。',
      '原模型的限制是：必须一次融资够全年开销，并且融资买入、担保品划出后仍达到300%；否则全年完全不融资。新规则改为部分融资，不足部分用普通现金补足。',
      '要让融资后允许低于300%，本次明确采用先划出担保品、再融资买回等额股票的研究顺序。设信用资产A、已有负债D（含未付利息）、年预算B、自有可转股票S、保证金可用余额G、股票折算率h、融资保证金比例r，则：',
      '`本次融资额 x = min(B, max(0,A−3D), S, max(0,G)/(h+r))`。当前维持率不高于300%时x=0；其余开销为B−x。',
      '先划出x后，信用维持率为(A−x)/D，仍不得低于300%；随后融资买回x，信用资产回到A，债务变为D+x，维持率A/(D+x)可以低于300%。并非无视可用保证金、可转自有证券库存或300%转出限制。',
      '例：信用资产31万元、旧负债10万元、全年需2万元。在其他额度足够时，可先转出1万元，使维持率达到300%，再融资买回1万元，维持率变为281.82%；其余1万元生活费由普通现金补足。',
      '执行边界：上交所现行细则仍要求提取担保物后的维持比例不低于300%。本回测将转出资格检查放在后续融资之前，没有模拟券商用新增借款后的日终状态重新审核或撤销划转。是否允许这种顺序需要券商按具体审核时点确认；不能仅据本回测断言实盘可执行。[上交所现行细则第44条](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/specific/margin/c/c_20250616_10782015.shtml)',
      '统一假设：初始100万元，年开销为初始资产2%或3%，现金收益2%，融资2.8%单利长期挂息；比例按总资产计算；股票折算率70%、现金类90%、融资保证金比例100%；160%触发现金类证券补担保至200%，可用全部普通现金，140%为研究停止线，主版本不还本、不付息。70/30买股现金底线30万元，80/20为20万元；3%版本的30万元相当10年开销。',
      '## 2000年高点起投：旧规则与新规则',
      '起点2000-03-27，终点2026-09-08；三种新配置均完成主路径。2%版本累计花54万元，3%花81万元，因此跨提取率的净资产差额不是纯投资收益差。所有净资产已扣本金及未付利息。']
pairs=[x for x in oldnew if x['start']=='2000-03-27']
text.append(table(['配置','旧期末净资产/万','新期末净资产/万','增量/万','旧→新负债/万'],
                  [[labels[x['name']],wan(x['old']['net']),wan(x['new']['net']),wan(x['new']['net']-x['old']['net']),
                    wan(x['old']['debt'])+' → '+wan(x['new']['debt'])] for x in pairs]))
text.append(table(['配置','旧→新最低普通现金/年开销','新最低普通现金/万','旧→新最低维持率','新累计补担保/万','全额/部分/纯现金年份'],
                  [[labels[x['name']],f'{x["old"]["min_cash_years"]:.2f} → {x["new"]["min_cash_years"]:.2f}',wan(x['new']['min_cash']),
                    pct(x['old']['min_mmr'])+' → '+pct(x['new']['min_mmr']),wan(x['new']['rescue_cash_in']),
                    f'{x["new"]["full_finance_years"]} / {x["new"]["partial_finance_years"]} / {x["new"]["cash_only_years"]}'] for x in pairs]))
text += ['关键变化：70/30提取2%从未触发补担保，变为2008年累计补入5.53万元现金类证券。最低维持率降至151.59%，最低普通现金从9.25年降至8.31年。收益小幅增加，不能据此说风险也改善。',
         '70/30提取3%期末净资产从213.08万上升至325.58万，但最低普通现金仅约1.17年开销；80/20提取2%约3.08年，70/30提取2%约8.31年。3%版本仍不宜因主路径通过就视为高安全余量配置。',
         '全额/部分按新增融资本金与年度预算比较；“普通现金补足”是预算减融资额的计划拆分。担保品到账卖出时价格可能变化，因此实际动用现金可有小额差异。累计补担保是累计转入额，不等于期末被锁定金额。',
         '![最低现金余量](assets/cash_relay_article/02_cash_cushion.png)',
         '## 部分融资发生在哪些年份']
partial=[]
for n in names:
    for a in json.loads((OUT/f'{n}_2000-03-27_annual.json').read_text(encoding='utf-8')):
        if a['finance_status']=='partial':partial.append([labels[n],a['year'],f'{a["financed_amount"]:,.2f}',f'{a["cash_topup_planned"]:,.2f}'])
text.append(table(['配置','年份','融资额/元','计划用普通现金/元'],partial))
text+=['## 2009年低点起投与卖资产、PAL对照',
       '2009-03-09至2026-09-08的三种接力配置，全部18年仍是全额融资，没有部分融资，结果与旧版相同。2%版本累计花36万元，3%版本花54万元。']
text.append(table(['配置','期末净资产/万','期末负债/万','最低普通现金/年开销','累计生活费/万'],
                  [[labels[r['name']],wan(r['net']),wan(r['debt']),f'{r["min_cash_years"]:.2f}',wan(r['living_paid'])]
                   for r in main if r['start']=='2009-03-09']))
text+=['2000年同期开销2%的80/20卖资产仍为213.14万元净资产、PAL为572.76万元。新70/30接力高于卖资产77.8%，新80/20接力高103.8%。2009年同为80/20时，接力领先卖资产8.4%，PAL领先8.2%；70/30接力仍低于80/20卖资产。PAL对照仍是年度恢复80/20、3%复利本息不付的理想化模型。',
       '## 滚动历史窗口和压力测试',
       '每季度首个交易日起投，固定10年/20年窗口每配置分别71/31个，三配置共306个，均完成。重叠窗口并非独立样本，不能把零失败解释为未来失败概率为零。']
text.append(table(['配置','年限','窗口数','失败数','最低维持率','最低现金/年开销'],
                  [[labels[n],years,len(g),sum(bool(r['failure']) for r in g),pct(min(r['min_mmr'] for r in g)),f'{min(r["min_cash_years"] for r in g):.2f}']
                   for n in names for years in [10,20] for g in [[r for r in rolling if r['name']==n and r['years']==years]]]))
scenario_labels={'cash0':'现金收益0%','rate4':'融资利率4%','rate6':'融资利率6%','inflation2':'生活费每年增加2%',
                 'extra_drop20':'2008低位额外永久跌20%','flat40':'人工：股票40年横盘',
                 'bear_then5_40':'人工：先10年每年跌5%，后30年每年涨5%',
                 'combined':'利率4%+现金0%+年开销增2%+股票年损耗1%'}
def outcome(r):return '完成' if not r['failure'] else f'支付失败 {r["end_actual"]}'
text.append(table(['情景']+[labels[n] for n in names],
                  [[label]+[outcome(next(r for r in stress if r['name']==n and r['scenario']==scenario)) for n in names]
                   for scenario,label in scenario_labels.items()]))
text+=['“支付失败”表示按当前规则在计划日不能支付整年预算，不是净资产归零。本次所有压力失败都是生活流动性失败。已另查失败时的可转担保品：例如3%现金零收益时缺约1,036元、维持率299.34%、无可转出自有股票；3%利率6%时缺约1.19万元、维持率290.16%，信用账户仍有现金类担保证券却不能按300%条件转出。',
       '3%支出年增2%的失败时，维持率约300.54%，普通现金缺约6,309元，自有股票可转额仅约642元，另有约181元现金类证券，也不足以补齐。因此不能简单说这些失败只要当天提前再平衡就都能解决；改变更早的交易路径或启用还款应急方案，属于新的策略分支。',
       '新规则下70/30的额外20%下跌压力路径反而能完成，而旧规则曾触及140%停止线；原因是此前债务和补担保时点发生变化。与此同时，人工先跌后涨路径的新70/30在2034年出现支付失败，而旧2%版本完成。这再次说明风险不随“允许多借”单调变化。',
       '## 如果券商要求按融资完成后的状态审核划转',
       '另算“允许部分融资，但融资并转出后仍须300%”分支，容量为min(B, A/3−D, 库存与保证金限制)。它区别于旧版的全额或零融资，也区别于本次先转后借主版本。']
text.append(table(['配置','先转后借净资产/万','融资完成后仍300%净资产/万','该分支最低现金/年开销'],
                  [[labels[n],wan(next(r for r in main if r['name']==n and r['start']=='2000-03-27')['net']),wan(r['net']),f'{r["min_cash_years"]:.2f}']
                   for n in names for r in stress if r['name']==n and r['scenario']=='partial_post300' and r['start']=='2000-03-27']))
text+=['## 逐年双账户明细与复现',
       '下面的独立明细逐年列出融资状态和金额、普通现金及普通账户总值、信用股票和现金类担保品、本金、未付利息、期末及年内最低维持率、净资产与补担保金额。账户数值以年末为准；最低维持率含日内低价观察，不能与年末维持率混用。']
for n in names:
    path=REPORTS/f'现金接力部分融资_逐年账_{n}.md'
    sections=[f'# {labels[n]}：部分融资版逐年双账户账',
              '金额单位万元。年内生活费先支付，再做比例再平衡；融资状态为全额、部分或纯现金。现金补足为计划金额，未调整交收期间证券价格变化。普通现金不包含信用账户现金类担保品；总资产还含在途资产，净资产已扣全部负债。']
    for start in ['2000-03-27','2009-03-09']:
        annual=json.loads((OUT/f'{n}_{start}_annual.json').read_text(encoding='utf-8'))
        sections.append(f'## {start}入场')
        sections.append(table(['年','融资状态','融资','现金补足','普通现金','普通总值','信用股票','信用现金类','本金','未付息','期末维持率','年内最低维持率','净资产','本年补担保'],
                       [[a['year'],{'full':'全额','partial':'部分','cash_only':'纯现金'}[a['finance_status']],wan(a['financed_amount']),wan(a['cash_topup_planned']),
                         wan(a['ordinary_cash']),wan(a['ordinary_total']),wan(a['credit_stock']),wan(a['credit_cash']),wan(a['principal']),wan(a['unpaid_interest']),
                         pct(a['mmr']),pct(a['min_mmr']),wan(a['net']),wan(a['rescue_cash_in'])] for a in annual]))
        sections.append(f'[完整年度JSON](../results/partial_living/{n}_{start}_annual.json) · [日频双账户账](../results/partial_living/{n}_{start}_daily.json) · [交易事件](../results/partial_living/{n}_{start}_events.json)')
    path.write_text('\n\n'.join(sections)+'\n',encoding='utf-8')
    text.append(f'- [{labels[n]}逐年账]({path.name})')
text += ['复现：`python scripts/run_partial_living.py`；支付失败诊断：`python scripts/diagnose_partial_living.py`；报告：`python scripts/build_partial_living_report.py`；文章图：`python scripts/build_cash_relay_article_figures.py`。',
         '验证：15条旧主路径与原结果逐项复现，卖资产/PAL对照一致；核对新路径的双账户恒等式、逐年损益、零还款、保证金和转出限制、先支付后再平衡顺序；50项单元测试通过。',
         '数据仍是QQQ复权代理，未纳入境内ETF汇率、溢折价、税费、实际合同变动及银行理财赎回限制。本次结果是明确执行假设下的研究结果。']
(REPORTS/'现金接力_部分融资规则更新.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8')
print('Summary and three yearly ledgers written.')
