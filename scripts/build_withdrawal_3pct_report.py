from pathlib import Path
import json,sys,datetime as dt
ROOT=Path(__file__).parent.parent;P=ROOT/'results'/'withdrawal_3pct'
def read(n):return json.loads((P/n).read_text(encoding='utf-8'))
main=read('main.json');rolling=read('rolling.json');stress=read('stress.json');diagnostics=read('failure_diagnostics.json')
def m(v):return f'{v/10000:,.2f}'
def pc(v):return '—' if v is None else f'{v*100:.2f}%'
def get(n,start='2000-03-27'):return next(r for r in main if r['name']==n and r['start']==start)
names={'w2':'2%开销，30%现金底线','w25':'2.5%开销，30%现金底线','w3':'3%开销，30%现金底线','w3_floor15':'3%开销，45%买股现金门槛'}
def table(head,rs):return ['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rs]
sys.path.insert(0,str(ROOT/'results'/'smart_relay_python'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False,'font.size':10})
fig,axs=plt.subplots(2,2,figsize=(13,8),layout='constrained')
for name,color in [('w2','#16728b'),('w3','#d77331')]:
    d=read(name+'_2000-03-27_daily.json');x=[dt.date.fromisoformat(r['date']) for r in d]
    for ax,key,scale,title in [(axs[0,0],'ordinary_cash',10000,'普通现金（万元）'),(axs[0,1],'net',10000,'净资产（万元，已扣生活费和负债）'),(axs[1,0],'mmr',.01,'信用维持率（%，显示140%-500%）'),(axs[1,1],'credit_cash',10000,'信用现金类担保品（万元）')]:
        ax.plot(x,[r[key]/scale if r[key] is not None else float('nan') for r in d],label='年开销'+('2%' if name=='w2' else '3%'),color=color,lw=1.4)
        ax.set_title(title,loc='left');ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
axs[0,0].legend(frameon=False)
axs[1,0].set_ylim(140,500)
for v in [140,160,200,300]:axs[1,0].axhline(v,color='#777',ls='--',lw=.6)
fig.suptitle('70/30现金接力：年开销2%与3%\n2000-03-27至2026-09-08｜单利挂息｜160%触发、补到200%',fontsize=14)
fig.savefig(P/'comparison.png',dpi=160);plt.close(fig)

a,b=get('w2'),get('w3')
lines=['# 70/30现金接力：年度3%提取的风险测试','',
'研究日期：2026-09-15。沿用上一阶段QQQ数据快照，截止2026-09-08；没有更新或拼接新行情。',
'', '**结论应同时看完整主路径、不同起点和压力情景。2000年高点主路径虽完成，3%版本普通现金最低不足一年开销，不能直接把3%称为已验证安全的提取率。**','',
'## 本次变更与固定条件','',
'- 将年度融资目标和年度生活支出同时提高至初始资产3%，即初始100万元每年花3万元。不是借3万元、只花2万元。融资仍可暂停，不能理解为每年必定拿得到贷款。',
'- 初始仍70万元股票放信用、30万元现金放普通；买股底线主版本仍是初始30万元，现相当10年开销。另测15年开销门槛，即现金必须超过45万元才允许补股票；它不等于把初始配比改成55/45。',
'- 比例再平衡按总资产而非净资产；2.8%单利长期挂息；现金及抽象现金类担保证券年收益2%；160%触发补担保到200%，可以用尽普通现金；主版本不主动还本或付息。',
'- 300%转出约束、融资保证金与可转自有股票检查不变；年度开始融资，两交收环节后付全年生活费，再调仓。140%是研究停止线，并非对国信实际即时强平线的重新认定。',
'- 价格是QQQ复权代理，未计人民币汇率、三只境内ETF溢折价、实际税费与银行理财赎回限制。现金类证券资格及收益留在证券中的处理仍属模型假设。','',
'## 2000年高点起投：与原2%版本比较','']
metrics=[('实际运行截止','end_actual',str),('期末净资产/万元','net',m),('期末总负债/万元','debt',m),('累计生活支出/万元','living_paid',m),('实际融资年数','financed_years',str),('最低普通现金/万元','min_cash',m),('最低普通现金/年开销','min_cash_years',lambda x:f'{x:.2f}'),('最低信用维持率','min_mmr',pc),('净资产最大回撤','max_drawdown',pc),('累计补担保/万元','rescue_cash_in',m)]
lines+=table(['指标','原2%','新3%'],[[label,f(a[k]),f(b[k])] for label,k,f in metrics])
lines+=['',f'3%版本最低现金发生在{b["min_cash_date"]}，约{b["min_cash"]:,.0f}元。它是日频序列的低点，不能据此说当年已经付不起生活费；本条路径确实付满了27年的81万元。相比之下，2%版本支出54万元，因此不能将两者期末净资产差额全部解释为投资收益差。',
'','3%版本的期末负债反而略少，并不代表更安全：融资金额变大后，操作后300%的要求更难满足，更多年份被迫使用普通现金。本次主路径3%只融资11年，其余16年靠现金支付；2%融资18年，其余9年用现金。','',
'![账户风险对比](../results/withdrawal_3pct/comparison.png)','',
'## 其他历史起点','']
lines+=table(['起点','运行截止','3%状态','期末净资产/万元','最低普通现金/年开销','最低维持率'],[
    [r['start'],r['end_actual'],r['failure'] or '完成',m(r['net']),f"{r['min_cash_years']:.2f}",pc(r['min_mmr'])] for r in main if r['name']=='w3'])
lines+=['','同一行才是同一持有期限。上涨起点能通过，并不能抵消较早起点遭遇多年下跌和现金耗尽的风险。','',
'## 滚动窗口','',
'每季度首个可用交易日起投，分别持有固定10年、20年。另列至少持有5年至同一数据末日的观察，不将其和固定期限合并。窗口重叠，失败占比不是未来失败概率。','']
rollrows=[]
for horizon in [10,20,'to_end_min5']:
    for name in names:
        group=[r for r in rolling if r['name']==name and r['years']==horizon]
        rollrows.append([names[name],str(horizon),len(group),sum(bool(r['failure']) for r in group),pc(min(r['min_mmr'] for r in group)),f"{min(r['min_cash_years'] for r in group):.2f}"])
lines+=table(['版本','持有期限','窗口数','失败数','最低维持率','最低现金/年开销'],rollrows)
if diagnostics:
    lines+=['','### 3%版本的失败起点与账户状态','']
    lines+=table(['起点','首次失败日','失败类型','剩余净资产/万元','普通现金/万元','信用现金类/万元','维持率'],[
        [r['start'],r['end_actual'],r['failure'],m(r['net']),m(r['ordinary_cash']),m(r['credit_cash']),pc(r['mmr'])] for r in diagnostics])
else:lines+=['','本次所测历史滚动起点未出现3%主版本失败，但这不构成其他价格路径或制度条件下的保证。']
lines+=['','## 压力测试','']
labels={'cash0':'现金收益0%','rate4':'融资利率4%','rate6':'融资利率6%','inflation2':'生活费每年增长2%','extra_drop20':'2008低位额外永久跌20%','flat40':'人工：40年股票价格不变','bear_then5_40':'人工：先10年每年跌5%，后30年涨5%','combined':'利率4%＋现金0%＋生活费年增2%＋股票每年额外损耗1%'}
lines+=table(['情景','原2%','新3%','新3%首次失败/期末日期'],[
    [label,x['failure'] or '完成',y['failure'] or '完成',y['end_actual']] for key,label in labels.items()
    for x in [next(r for r in stress if r['name']=='w2' and r['scenario']==key)] for y in [next(r for r in stress if r['name']=='w3' and r['scenario']==key)]])
lines+=['','LiquidityFailure：按当前年度执行顺序，到支出日无法支付整年生活费；不是资产一定归零。MarginFailure：信用维持率触及140%研究停止线；不是对实际券商何时卖出证券的预测。人为路径不代表未来概率。通胀分支沿用原模型：现金补仓门槛也随当年预算增长。','',
'## 重要区分：支付顺序问题与担保品无法释放','',
'不能仅凭LiquidityFailure就判断经济上破产。现金收益0%的失败时点，信用维持率348.46%，可转担保品约5.57万元，足以覆盖1.65万元的现金缺口；先付生活费、后调仓的顺序阻止了当年卖股补款。这主要是提前安排变现的问题。',
'', '开销年增2%的原失败时点则不同：虽然维持率414.47%，自有可转股票库存已经为0，剩余股票属于融资持仓，不能假定全部都可划出。这是库存与执行路径的约束，而不是仅检查维持率就能发现的问题。',
'', '另做“年初先再平衡，再安排融资及生活费”的完整路径对照，上述两种场景均能完成。因此，它们不是3%在任何执行方式下必然断供的证据；但该对照改变了整个历史中的调仓、融资和库存路径，并非到了失败当天调整一下顺序就一定能挽救。未用该对照替换当前主规则。','']
diags=read('liquidity_diagnostics.json');seq=read('sequence_sensitivity.json')
lines+=table(['原失败场景','失败时维持率','现金缺口/万元','当时可转担保/万元','改为先调仓后的结果'],[
    [labels[r['scenario']],pc(r['mmr']),m(r['nominal_cash_shortfall']),m(r['withdrawable_collateral']),
     ('完成至'+z['end_actual']) if not z['failure'] else z['end_actual']+'仍失败']
    for r in diags for z in [next(x for x in seq if x['scenario']==r['scenario'])]])
lines+=['','可转金额是失败当日按模型计算的容量，不保证之前就有同样容量，也不保证能即时到账。2008低位额外跌20%、40年横盘、前10年每年跌5%等场景，即使先调仓仍会失败；当时维持率低于300%，原有净资产并不能自由变成普通账户生活现金。这些是当前零主动还款规则下更实质的流动性风险。','',
'## 15年门槛能否解决问题','']
lines+=table(['主路径设定','期末净资产/万元','最低现金/年开销','最低维持率','融资年数'],[[names[n],m(r['net']),f"{r['min_cash_years']:.2f}",pc(r['min_mmr']),r['financed_years']] for n in names for r in [get(n)]])
lines+=['','提高买股票的现金门槛只会减少补仓，并不会凭空多出15年的储备。现金初始依然只有30万元；生活费和救险都可以继续消耗这笔钱。因此，需要结合实际失败数和压力路径判断，不能仅把参数改回“15年”就称为恢复安全。','',
'## 逐年执行明细：3%版本，2000年起投','', '金额万元，最后一年截至2026-09-08。融资列指实际是否融资。','']
ys=read('w3_2000-03-27_annual.json')
lines+=table(['年','融资','普通现金','信用股票','信用现金类','本金','未付息','年内最低M','净资产'],[
    [r['year'],'是' if r['financed'] else '否',m(r['ordinary_cash']),m(r['credit_stock']),m(r['credit_cash']),m(r['principal']),m(r['unpaid_interest']),pc(r['min_mmr']),m(r['net'])] for r in ys])
lines+=['','完整配置、数据哈希、年度/日频账和失败诊断保存在results/withdrawal_3pct。所有正常年度做资产变动对账，本息实际偿还均为0。2.5%只是同底线的中间敏感性，不是据本轮结果给出的安全提取率承诺。']
(ROOT/'reports'/'7030现金接力_年度3%提取风险测试.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Report and figure complete')
