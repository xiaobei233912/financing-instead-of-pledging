from pathlib import Path
import json,sys,statistics,html
ROOT=Path(__file__).parent.parent;P=ROOT/'results'/'collateral_relay'
sys.path.insert(0,str(ROOT/'results'/'smart_relay_python'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False,'font.size':11})
def read(name):return json.loads((P/name).read_text(encoding='utf-8'))
main=read('main.json');stress=read('stress.json');rolling=read('rolling.json');by={r['name']:r for r in main}
def m(x):return f'{x/10000:.2f}'
def pct(x):return '—' if x is None else f'{x*100:.2f}%'
def table(head,rows):
    return ['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows]
names={'none':'不补担保','a180':'现金类证券：180→220','auto180':'原始现金：自动扣息','a160':'现金类证券：160→200','a200':'现金类证券：200→240'}
fig,axs=plt.subplots(2,2,figsize=(15,9),layout='constrained')
for label,color in [('70','#176b9c'),('80','#e47932')]:
    d=read(label+'_a180_daily.json');x=[__import__('datetime').date.fromisoformat(r['date']) for r in d]
    for ax,key,scale,title in [(axs[0,0],'net',10000,'总净资产（万元）'),(axs[0,1],'ordinary_cash',20000,'普通账户现金（年开销）'),(axs[1,0],'credit_cash',10000,'信用账户现金类担保品（万元）'),(axs[1,1],'mmr',.01,'维持担保比例（%，显示至500%）')]:
        ax.plot(x,[r[key]/scale if r[key] is not None else float('nan') for r in d],color=color,label=label+'/'+str(100-int(label)),lw=1.5)
        ax.set_title(title,loc='left');ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
axs[1,1].set_ylim(130,500)
for v in [140,180,220,300]:axs[1,1].axhline(v,color='#777',lw=.6,ls='--')
axs[0,0].legend(frameon=False)
fig.suptitle('现金接力 · 比例再平衡｜现金类证券补担保示例（180%→220%）\nQQQ历史代理，初始100万元，每年开销2万元；非三只境内ETF实盘回测',fontsize=15)
fig.savefig(P/'comparison.png',dpi=160);plt.close(fig)

lines=['# 70/30与80/20现金接力：现金类证券补担保对比','',
'研究日期：2026-09-12。金额按初始100万元归一化；2万元等于一年开销。',
'', '**结论：80/20提高股票敞口，也减少可供生活与补担保共用的现金。补担保改善信用账户维持率，但不创造净资产，也不保证普通账户始终有钱生活。**','',
'## 已确认的规则与本次假设','',
'- 采用用户向国信客户经理确认的当前条件：长期挂息、未付利息不计息、维持率高于140%可以展期。140%同时保留为研究停止线；不把它称为已核实的国信强平线，也不推定政策永不变化。',
'- 每年生活费固定为初始资产2%；利率沿用2.8%单利。70/30买股现金底线15年开销，80/20底线10年。只用高于底线的部分补仓，卖股补现金不受该底线限制。',
'- 配比按股票市值÷总资产计算，负债另列。总资产含普通、信用与在途资产，净资产=总资产−本金−未付利息。80/20并不保证股票÷净资产仅为80%。',
'- 融资生活仍通过融资买股、转出等值自有股票、普通账户卖出实现；同时检查可转自有股票、保证金余额和操作后300%维持率。暂停后满足条件可以恢复，逐年记录是否实际融资。',
'- 根据用户最新确认，补担保可以用尽全部普通现金；再平衡的15/10年底线不限制救险。主版本在普通账户买现金类证券再划转，信用内不卖出、不主动还本付息。b、c不是自动兜底：否则会把“零还款失败”伪装成成功。',
'- 主版本现金类证券假设总收益年化2%、无价格波动、收益留在证券中、担保折算率90%，与普通现金同收益。它是抽象资产，不代表某只ETF的净值、分红或国信资格已核实；原始信用现金收益为0。',
'- 补担保触发参数未确定，比较160→200、180→220、200→240三组百分比。逐年明细以180→220为示例，不能据此认定为最优参数。',
'- 开盘与收盘观察并发起补担保，默认下一交易日到账；在途资产不计信用维持率。日内最低价跌破140%立即记研究风险失败，不假装能在该最低价成交补救。风险操作是年度例行操作之外的例外。',
'- 补担保后信用现金类证券可留存。作为明确的测试假设，每年例行操作时先将合法可转出的现金类担保品退回普通账户，再考虑卖股；转出后至少300%，保证金余额非负。另测试不退回版本。',
'- 默认现金已可购买证券；银行理财须先赎回，额外等待通过0/3/5交易日补担保延迟分支测试。此简化未模拟节假日错配或产品暂停赎回。','',
'## 主历史路径','',
'2000-03-27至2026-09-08，QQQ复权日线代理。沿用既有数据，未把159501、513100、159696拼接为2000年可交易产品。未计人民币汇率、境内ETF溢折价、实际费税、不同交易时段和基金跟踪差异。现金为平滑收益假设。2000与2026是不完整年度，但各支取全年2万元，合计27笔。','']
lines+=table(['方案','期末净资产/万元','最低维持率','普通现金最低/年','净资产最大回撤','融资年数','补担保累计/万元','还本/付息/万元'],[
    [r['name'][:2]+'/'+str(100-int(r['name'][:2]))+' '+names[r['name'][3:]],m(r['net']),pct(r['min_mmr']),f"{r['min_cash_years']:.2f}",pct(r['max_drawdown']),r['financed_years'],m(r['rescue_cash_in']),m(r['principal_repaid'])+' / '+m(r['interest_paid'])]
    for r in main if r['name'].endswith(('none','a180'))])
lines+=['','![账户与风险对比](../results/collateral_relay/comparison.png)','',
'最大回撤根据扣除生活支出后的账户净资产日终序列计算，含支出影响；不是时间加权投资收益的回撤。最低维持率还包含日内最低价观察，因此不一定落在图示的收盘曲线上。补担保累计是历次转入之和，可能包含后续转出再转入，不等于永久占用。','',
'本条历史路径中，同一配比的证券补担保与不补担保期末净资产恰好相同：移入移出不改变总资产，两处现金类收益相同，担保品随后退回且未改变年度股票买卖和融资结果。这不是普遍结论；普通现金枯竭、担保品收益差异或长期不能退回都会改变结果。','',
'## 触发阈值敏感性','']
lines+=table(['配比','触发→目标','期末净资产/万元','最低维持率','最低普通现金/年','累计补担保/万元','失败'],[
    [r['name'][:2],names[r['name'][3:]],m(r['net']),pct(r['min_mmr']),f"{r['min_cash_years']:.2f}",m(r['rescue_cash_in']),r['failure'] or '无']
    for r in main if r['name'][3:] in ['a160','a180','a200']])
lines+=['','## 三种救险方式的效率','',
'设信用资产A、负债D，动用相同金额x，不考虑价格波动和费用：','',
'- a 补入担保品：(A+x)/D。现金类证券按当时市值进入维持率分子，折算率作用于保证金可用余额，不能把两种指标混用。',
'- b 普通现金还款：A/(D−x)。',
'- c 信用卖券还款：(A−x)/(D−x)。','',
'当A>D、0<x<D时，b的维持率提升大于a和c；a与c没有固定顺序，c优于a当且仅当A/D>2−x/D。小额操作时，约以200%为分界。你的a优先，体现的是保留负债与股票的目标，不是每元资金提升维持率最多。','',
'例如信用资产180万元、负债100万元，要达到220%：a需补40万元；b需还18.18万元；c需卖券还33.33万元。若将全部可用普通现金先用于a，b将没有普通现金可用；再启动还款必须明确允许动用已转入的担保品，或预先保留还款资金。','',
'本次主版本坚持a且不主动还款，耗尽现金或触及风险线即报告失败。b/c属于改变目标后的救险分支，没有自动混入结果。','',
'## 多起点滚动检查','',
'按每季度首个可用交易日起投，分别持有10年、20年；相同起点成对比较，窗口重叠，样本失败率不能解释为未来失败概率。','']
rows=[]
for years in [10,20]:
    for label in ['70_none','80_none','70_a180','80_a180']:
        rs=[r for r in rolling if r['years']==years and r['name']==label]
        rows.append([label,years,len(rs),sum(bool(r['failure']) for r in rs),pct(min(r['min_mmr'] for r in rs)),f"{min(r['min_cash_years'] for r in rs):.2f}"])
lines+=table(['方案','持有年数','窗口数','失败数','跨窗口最低维持率','跨窗口最低普通现金/年'],rows)
labels={'extra_drop20':'2008-11-20起额外永久跌20%','extra_drop40':'2008-11-20起额外永久跌40%','rate6':'融资利率6%','cash0':'现金类收益0%','inflation2':'年开销每年增长2%','flat40':'人工路径：40年价格不变','bear_then5_40':'人工路径：前10年每年跌5%、后30年涨5%'}
lines+=['','## 压力路径','', '额外跌幅和40年平滑价格均为人为反例，不是发生概率或市场预测。失败时净资产可能仍为正，信用安全与生活流动性必须分开判断。','']
lines+=table(['情景','配比','停止/期末日期','状态','净资产/万元','普通现金/年','信用现金类担保/万元'],[
    [labels[r['scenario']],r['name'][:2],r['end_actual'],r['failure'] or '完成',m(r['net']),f"{r['ordinary_cash']/20000:.2f}",m(r['credit_cash'])]
    for r in stress if r['name'] in ['70_a180','80_a180'] and r['scenario'] in labels])
lines+=['','上表“普通现金/年”统一按初始2万元为展示单位；通胀情景的实际剩余生活年数更少。MarginFailure表示触及研究140%停止线；LiquidityFailure表示到期无法支付生活费；ContractFailure表示展期条件不满足。','',
'## 自动扣息、流动性与担保品退回','',
'国信公开旧版手册说明信用账户可用现金会优先偿还已结算未付利息。这并不否定用户确认的长期单利挂息。本次将“原始现金自动扣息”作为不同合约行为对照，按每月首个交易日结息、日终现金优先支付已结算利息，不还本金。','']
lines+=table(['配比','分支','期末净资产/万元','累计付息/万元','最低普通现金/年'],[
    [r['name'][:2],names[r['name'][3:]],m(r['net']),m(r['interest_paid']),f"{r['min_cash_years']:.2f}"]
    for r in main if r['name'][3:] in ['a180','auto180']])
lines+=['','现金类证券主版本与原始现金分支同时存在收益2%与0%的差异，表中净资产差异不能全部归因于扣息。现金类ETF也未必不派现；必须确认具体产品的收益分配方式、国信可充抵资格及折算率。“可两融”本身不等于低风险现金资产。','']
lines+=table(['分支','期末净资产/万元','最低维持率','最低普通现金/年','状态'],[
    [r['name'],m(r['net']),pct(r['min_mmr']),f"{r['min_cash_years']:.2f}",r['failure'] or '完成']
    for r in stress if r['scenario'] in ['delay','no_return']])
lines+=['','## 逐年双账户明细','',
'单位万元；“信用现金类”在主版本中全部为证券市值，非可用现金。普通账户转入救险后不再拥有同一份现金。期末净资产包含少量可能在途资产；完整记录另列在途、股票损益、现金收益、利息费用、支出和逐年对账差额。最低维持率为该年日内观察最低值，非年末值。最后一年截至2026-09-08。','']
for label in ['70','80']:
    y=read(label+'_a180_annual.json')
    lines+=['',f'### {label}/{100-int(label)}：180%补到220%示例','']
    lines+=table(['年','融资','普通现金','信用股票','信用现金类','本金','未付息','年末维持率','年内最低','净资产','补担保/退回'],[
        [r['year'],'是' if r['financed'] else '否',m(r['ordinary_cash']),m(r['credit_stock']),m(r['credit_cash']),m(r['principal']),m(r['unpaid_interest']),pct(r['mmr']),pct(r['min_mmr']),m(r['net']),m(r['rescue_cash_in'])+'/'+m(r['rescue_cash_return'])] for r in y])
    lines+=['','未融资年份及原因：'+ '；'.join(str(r['year'])+'：'+str(r['finance_rejection']) for r in y if not r['financed'])+'。']
lines+=['','## 结果可靠性的边界与下一步','',
'优先选择参数在多种起点和压力环境下是否稳健，不以这一条历史路径的最高期末净资产选80/20。若坚持永久零还款，必须接受零还款策略可能先耗尽可花现金；净资产高或信用账户有担保品，不等于这些资产能立即转出来生活。',
'', '本次未确认具体现金类证券、实际分红与划转资格，也未回测三只境内纳指ETF的真实人民币价格。因此，这是沿用既有QQQ框架的规则对比，不是国信账户实盘可执行性的完整认证。','',
'来源：[国信交易手册（旧版，第12页）](https://www3.guosen.com.cn/guosen/uploadfiles/_1375663786440_%E8%9E%8D%E8%B5%84%E8%9E%8D%E5%88%B8%E4%BA%A4%E6%98%93%E8%BD%AF%E4%BB%B6%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E%E4%B9%A60805.pdf)；[上交所货币ETF说明](https://etf.sse.com.cn/fund/learning/knowledge/c/5704294.shtml)；[上交所标的与可充抵证券列表](https://big5.sse.com.cn/site/cht/www.sse.com.cn/services/tradingservice/margin/info/againstmargin/)。',
'', '数据与审计：results/collateral_relay保留完整配置、价格数据哈希、10套历史逐年账和日账、压力场景、滚动窗口。主版本年度净资产变动应等于股票损益+现金类收益−新增利息费用−生活支出；补担保与归还担保品不是收入或费用。']
(ROOT/'reports/7030与8020现金接力_现金类担保品对比.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('report and chart saved')
