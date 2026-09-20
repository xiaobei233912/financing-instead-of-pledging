from pathlib import Path
import sys,json,statistics,html
ROOT=Path(__file__).parent.parent
sys.path.insert(0,str(ROOT/'results'/'smart_relay_python'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, NullFormatter
P=ROOT/'results'/'smart_relay'
def read(n):return json.loads((P/n).read_text(encoding='utf-8'))
labels={'proportional':'比例再平衡','smart':'智能再平衡（50%）'}
colors={'proportional':'#2563A6','smart':'#D26525'}
annual={k:read(f'{k}_2000-03-27_annual.json') for k in labels}
stress=read('stress.json');roll=read('rolling.json');sens=read('harvest_sensitivity.json')
main={k:next(r for r in stress if r['start']=='2000-03-27' and r['config']['strategy']==k) for k in labels}
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})

fig,axes=plt.subplots(3,2,figsize=(13,12),layout='constrained')
panels=[('ordinary_cash','普通账户现金','万元',1e4),('credit_stock','信用账户股票总市值','万元',1e4),
        ('debt','信用账户债务（含挂息）','万元',1e4),('net','合计净资产','万元',1e4),
        ('mmr','年末信用维持率','%',.01),('min_mmr','年内最低信用维持率','%',.01)]
for ax,(field,title,unit,div) in zip(axes.flat,panels):
    for k,ys in annual.items():
        ax.plot([y['year'] for y in ys],[y[field]/div for y in ys],label=labels[k],color=colors[k],marker='o',markersize=3,linewidth=1.7)
    if 'mmr' in field:
        ax.set_yscale('log');ax.set_yticks([140,300,600,1200,2400]);ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'{x:g}'));ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_ylim(130,max(y[field]*100 for ys in annual.values() for y in ys)*1.2)
        ax.axhline(140,color='#BD3636',linestyle=':',linewidth=1);ax.axhline(300,color='#888888',linestyle='--',linewidth=1)
        title+='（对数轴）'
    if field=='ordinary_cash':ax.axhline(30,color='#888888',linestyle='--',linewidth=1)
    ax.set(title=title,xlabel='年份（2026截至9月8日）',ylabel=unit);ax.grid(alpha=.2)
axes[0,0].legend(frameon=False)
fig.suptitle('70/30现金接力：双账户逐年对比\n2000-03-27起步，初始100万元，年开销2万元',fontsize=15)
fig.savefig(P/'accounts_comparison.png',dpi=160);fig.savefig(P/'accounts_comparison.svg');plt.close(fig)

fig,axes=plt.subplots(3,1,figsize=(14,9),layout='constrained')
years=[y['year'] for y in annual['smart']]
for offset,k in enumerate(labels):
    ys=annual[k];x=[y+(-.19 if offset==0 else .19) for y in years]
    axes[0].bar(x,[y['financed_amount']/10000 for y in ys],width=.36,color=colors[k],label=labels[k])
    axes[1].bar(x,[y['buy']/10000 for y in ys],width=.36,color=colors[k])
    axes[2].bar(x,[y['sale_transfer']/10000 for y in ys],width=.36,color=colors[k])
for ax,title in zip(axes,['当年融资生活费：有柱=融资2万元，无柱=使用自有现金','当年现金补仓股票','当年卖股补现金（划转时金额）']):
    ax.set(title=title,xlabel='操作年份',ylabel='万元');ax.set_xticks(years);ax.tick_params(axis='x',rotation=60);ax.grid(axis='y',alpha=.2)
axes[0].set_ylim(0,2.6);axes[0].legend(frameon=False);fig.savefig(P/'annual_actions.png',dpi=160);fig.savefig(P/'annual_actions.svg');plt.close(fig)

groups=[]
for label in ['proportional','smart_0.25','smart_0.375','smart_0.5','smart_0.625','smart_0.75']:
    for years in [10,20]:
        g=[r for r in roll if r['label']==label and r['years']==years]
        base={r['start']:r for r in roll if r['label']=='proportional' and r['years']==years}
        groups.append(dict(label=label,years=years,n=len(g),failures=sum(bool(r['failure']) for r in g),
                           min_net=min(r['net'] for r in g),median_net=statistics.median(r['net'] for r in g),
                           min_mmr=min(r['min_mmr'] for r in g),min_cash_years=min(r['min_cash_years'] for r in g),
                           beats_proportional=sum(r['net']>base[r['start']]['net'] for r in g),
                           median_relative_net=statistics.median(r['net']/base[r['start']]['net']-1 for r in g)))
(P/'rolling_summary.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf-8')

def table(headers,rows):return ['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows]
def money(v):return f'{v/10000:.2f}'
def pct(v):return '—' if v is None else f'{v*100:.2f}%'
p,s=main['proportional'],main['smart']
lines=['# 70/30现金接力：智能再平衡与比例再平衡', '',
'记录日期：2026-09-12。主参数：上涨年股票投资盈利提取50%；下跌年最多补仓1年开销，且保留15年开销现金。', '',
f"同口径2000高点路径，智能版期末净资产{money(s['net'])}万元，比例版{money(p['net'])}万元。智能版最低现金储备更高，但融资年数更少；不能从策略名称推断其风险收益优于比例再平衡。", '',
'## 固定规则与本轮日历', '',
'- 年开销B=初始资产的2%，不随物价、股价或净资产变化。初始100万元，B=2万元，现金门槛15B=30万元。股票使用QQQ复权日频OHLC全收益代理，现金收益2%，融资利率2.8%，ACT/365单利长期挂账。利息计入负债、不成为计息本金。',
'- 普通账户保存现金类资产及可提现现金；信用账户保存自有股票及融资股票，不配置现金类资产。证券和现金在途单列，不提前算入信用担保。净资产=普通总资产+信用总资产+在途资产−本金−挂息；配置比例以总资产为分母。',
'- 两策略共同按自然年操作：年末收盘确认当年股票投资盈亏，下一年首个交易日先申请年度生活融资；划转T+1，普通卖款提现T+1，支付年度生活费后执行再平衡；卖股再平衡需另一次T+1转出。操作集中在年初几个交易日，不能在未看到年末收盘前使用全年收益。',
'- 首个不完整年度在入场日建仓并申请首年生活融资，首次生活费两交易日后支付，不做额外起始再平衡。以后每个自然年支付一次；2000主路径共27次、54万元。2000是入场至年末的不足一年，2026是截至9月8日的未完年度。2026年的操作依据2025盈利，2026未完年度盈利尚不触发调仓。',
'- 相比上一版的“入场周年融资＋年末开盘比例再平衡”，本轮统一为年度集中操作。因此比例版应采用本轮重跑的372.39万元；旧版380.11万元只作旧日历参考。其他核心经济参数不变。',
'- 年度股票盈利=sum(价格变化×该时段实际股票份额)，包含股票股息再投资代理收益，剔除融资买入、补仓和转出造成的本金流动；现金收益和融资利息单列。按你允许的近似，直接使用年初股票市值×全年收益率也接近，但本程序保留准确逐日计量。极接近零收益的年份可能因年初几天交易而改变盈亏符号。',
'- 智能版：上一年度股票亏损时，买入min(B，普通现金−15B)，下限0；上一年度股票盈利时，请求转出盈利的50%。维持率不高于300%则不转出；高于时仅卖出可转额度内的自有担保股票，不强制恢复70/30。',
'- 比例版：股票高于总资产70%时卖出超配部分，受同样转出限制；股票不足70%时只用高于15B的现金补足，买入不超过恢复70%的需要。',
'- 生活融资先执行，再平衡后执行。当前维持率高于300%并不保证融资成功，还须满足融资并转出后300%、完整保证金余额及足量自有担保品；不够借足1年则本年不借，使用普通现金。禁止把仍关联未偿融资的股票直接转出。',
'- 无主动还本付息、无补担保、无外部收入；主场景假定允许六个月一续及长期挂息。信用维持率低于140%记MarginFailure，生活费到期不足记LiquidityFailure，均停止；拒绝新融资本身不是失败。140%是模型压力线。', '',
'## 主路径结果', '']
metrics=[('期末净资产/万元','net',money),('普通现金/万元','ordinary_cash',money),('信用股票总市值/万元','credit_stock',money),
         ('信用自有股票/万元','credit_own_stock',money),('信用融资股票/万元','credit_financed_stock',money),
         ('信用债务含挂息/万元','debt',money),('期末信用净权益/万元','credit_net',money),
         ('最低维持率','min_mmr',pct),('最低现金/年开销','min_cash_years',lambda x:f'{x:.2f}'),
         ('融资年数','financed_years',str),('现金支付年数','cash_years',str),('含消费净资产最大回撤','max_drawdown',pct),
         ('股票占总资产最高比例','max_weight',pct),('股票占净资产最高比例','max_net_stock_exposure',pct),
         ('累计补仓/万元','rebalance_buys',money),('累计卖股划转/万元','rebalance_sales',money)]
lines+=table(['指标','比例再平衡','智能再平衡50%'],[[name,f(p[key]),f(s[key])] for name,key,f in metrics])
lines+=['', '![双账户年度对比](../results/smart_relay/accounts_comparison.png)', '',
'两种策略本息偿还均为0，信用现金类资产逐日均为0。年末普通账户没有滞留股票，年度合计账表仍列入在途资产以保证可勾稽。', '',
f"一个关键差异发生在2023年初：2022下跌后，比例版用现金买回约{money(next(x['buy'] for x in annual['proportional'] if x['year']==2023))}万元股票，智能版只买2万元。智能版此前上涨年持续提取盈利、下跌年补仓又受固定金额限制，这种不对称改变了后续股票持有规模。", '',
'智能版2024年将剩余自有担保股票转出后，自有库存归零；2025、2026年虽维持率恢复到300%以上，仍不能融资套现或再卖这部分融资股票。这是沿用本项目自有担保品限制的结果，不是“维持率低于300%”。若实际合同允许不同的债务关联解除机制，需要另立执行版本重测，不能直接把本结果套用。', '',
'## 普通账户：逐年比较', '',
'金额均为万元；收益为普通现金当年产生的收益。卖股列按发起划转时金额，到账实际成交差额进入当年股票盈亏。', '']
lines+=table(['年份','比例现金','智能现金','比例现金收益','智能现金收益','比例补仓','智能补仓','比例卖股','智能卖股'],
 [[x['year'],money(x['ordinary_cash']),money(y['ordinary_cash']),money(x['cash_income']),money(y['cash_income']),money(x['buy']),money(y['buy']),money(x['sale_transfer']),money(y['sale_transfer'])] for x,y in zip(annual['proportional'],annual['smart'])])
lines+=['', '## 信用账户：逐年比较', '', '金额均为万元；信用股票总市值=信用自有股票+信用融资股票。债务=本金+未付单利。', '']
lines+=table(['年份','比例股票','智能股票','比例自有股票','智能自有股票','比例债务','智能债务','比例信用净权益','智能信用净权益'],
 [[x['year'],money(x['credit_stock']),money(y['credit_stock']),money(x['credit_own_stock']),money(y['credit_own_stock']),money(x['debt']),money(y['debt']),money(x['credit_net']),money(y['credit_net'])] for x,y in zip(annual['proportional'],annual['smart'])])
lines+=['', '## 净资产和信用维持率：逐年比较', '', '年内最低值包含开盘、操作后、日内最低价及收盘；年末值不能代替年内风险。', '']
lines+=table(['年份','比例净资产/万','智能净资产/万','比例年末维持率','智能年末维持率','比例年内最低','智能年内最低'],
 [[x['year'],money(x['net']),money(y['net']),pct(x['mmr']),pct(y['mmr']),pct(x['min_mmr']),pct(y['min_mmr'])] for x,y in zip(annual['proportional'],annual['smart'])])
lines+=['', '## 每一年是否融资', '', '“是”表示该年新增生活融资本金2万元；“否”表示普通现金支付。下面是实际操作年份，调仓盈亏信号来自上一年度。', '']
lines+=table(['年份','比例融资','智能融资','比例未融资原因','智能未融资原因'],
 [[x['year'],'是' if x['financed'] else '否','是' if y['financed'] else '否',x['finance_rejection'] or '—',y['finance_rejection'] or '—'] for x,y in zip(annual['proportional'],annual['smart'])])
lines+=['', '![年度融资和再平衡](../results/smart_relay/annual_actions.png)', '',
'## 固定10年和20年滚动检验', '',
'季度首个可用交易日起步，首个不完整季度从1999-03-10开始，终点为起点加指定周年的前一天。因采用自然年支付生活费，跨非一月起点的10年窗口可能包含11次自然年度预算；两策略在同窗口完全一致。窗口高度重叠，不是独立样本的未来破产概率。', '']
lines+=table(['策略','期限','窗口数','失败数','最低期末净资产/万元','最低维持率','最低现金/年','智能终值高于比例的窗口数'],
 [[labels['proportional'] if x['label']=='proportional' else labels['smart'],x['years'],x['n'],x['failures'],money(x['min_net']),pct(x['min_mmr']),f"{x['min_cash_years']:.2f}",x['beats_proportional'] if x['label']!='proportional' else '—'] for x in groups if x['label'] in ['proportional','smart_0.5']])
lines+=['', '## 盈利提取比例x敏感性', '', '这里只测试预先选定的25%、37.5%、50%、62.5%、75%。不以2000高点终值单独寻找最优解。', '']
lines+=table(['x','2000起步期末净资产/万','最低维持率','最低现金/年','融资年数','10年优于比例窗口数','20年优于比例窗口数'],
 [[f"{x['config']['harvest']*100:g}%",money(x['net']),pct(x['min_mmr']),f"{x['min_cash_years']:.2f}",x['financed_years'],next(g['beats_proportional'] for g in groups if g['label']==x['label'] and g['years']==10),next(g['beats_proportional'] for g in groups if g['label']==x['label'] and g['years']==20)] for x in sens if x['label']!='proportional'])
lines+=['', '在这组候选中，25%在2000起点的终值最高，但没有据此证明最优；它的最低维持率仍需共同看待。降低提取比例会保留更多股票，同时让现金和担保安全的取舍改变。这里没有新增的独立样本外数据。', '',
'## 多个起点至同一终点', '', '期限不同，不可按终值比较起点优劣；同一起点的两策略可以配对。', '']
lines+=table(['起点','策略','净资产/万元','最低维持率','最低现金/年','融资年数','失败'],
 [[x['start'],labels[x['config']['strategy']],money(x['net']),pct(x['min_mmr']),f"{x['min_cash_years']:.2f}",x['financed_years'],x['failure'] or '无'] for x in sorted(stress,key=lambda x:(x['start'],x['config']['strategy']))])
lines+=['', '## 会计验证与可复现性', '',
'逐日验证交易前后净资产守恒、本金和利息勾稽、非负库存、信用账户无现金类资产。逐年核对：净资产变化=股票投资盈亏+现金收益−新增利息−生活支出。27项测试通过，包括现金底仓、300%转出限额、拒绝转出、融资不算盈利，以及改变未来行情不影响此前结果。', '',
'行情沿用data/qqq_daily.json，1999-03-10—2026-09-08共6917行，未联网更新。来源和SHA-256见本目录provenance.json及data/audit.json。现金收益是确定代理；忽略税费、汇率、QDII折溢价、国内节假日和成交失败，不补造QQQ上市前数据。结果以长期挂息及续约条件成立为前提。', '',
'结果文件在results/smart_relay：五个起点×两策略的日账、年度账、交易事件；6种策略参数×102个窗口=612个滚动场景。两主策略中每年是否融资、融资日期及未融资原因保存在annual.json。', '',
'复现：`python -m unittest test_smart_relay test_relay_backtest test_backtest -v`；`python smart_relay.py`；`python build_smart_report.py`。生成图表使用项目results/smart_relay_python中的matplotlib依赖。', '']
(ROOT/'reports/7030现金接力_智能与比例再平衡对比.md').write_text('\n'.join(lines),encoding='utf-8-sig')

# Offline HTML report with the same full tables; no network dependencies.
body=[];in_table=False
for line in lines:
    if line.startswith('|'):
        if line.startswith('| ---'):continue
        if not in_table:body.append('<div class="wide"><table>');in_table=True;tag='th'
        else:tag='td'
        body.append('<tr>'+''.join(f'<{tag}>{html.escape(c.strip())}</{tag}>' for c in line.strip('|').split('|'))+'</tr>')
        continue
    if in_table:body.append('</table></div>');in_table=False
    if line.startswith('!['):
        path=line.split('](')[1][:-1];body.append(f'<img src="{path}" alt="年度对比图">')
    elif line.startswith('# '):body.append('<h1>'+html.escape(line[2:])+'</h1>')
    elif line.startswith('## '):body.append('<h2>'+html.escape(line[3:])+'</h2>')
    elif line:body.append('<p>'+html.escape(line)+'</p>')
doc='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>7030现金接力策略对比</title><style>body{font:16px/1.7 system-ui,Microsoft YaHei,sans-serif;max-width:1280px;margin:30px auto;padding:0 20px;color:#203041;background:#fff}h1{font-size:28px}h2{font-size:22px;margin-top:36px}table{border-collapse:collapse;min-width:100%;font-size:14px}td,th{padding:8px 12px;border-bottom:1px solid #dce1e7;text-align:right;white-space:nowrap}td:first-child,th:first-child{text-align:left}th{background:#edf3f8}.wide{overflow-x:auto}img{max-width:100%;height:auto}p{max-width:1050px}</style>'+''.join(body)+'</html>'
(ROOT/'reports/7030现金接力_智能与比例再平衡对比.html').write_text(doc,encoding='utf-8')
view={k:[{f:round(x[f],5) if isinstance(x[f],float) else x[f] for f in ['year','ordinary_cash','credit_stock','credit_own_stock','credit_financed_stock','debt','credit_net','net','mmr','min_mmr','financed','finance_rejection','buy','sale_transfer','stock_profit','prior_year_profit']} for x in ys] for k,ys in annual.items()}
(P/'visual_data.json').write_text(json.dumps(view,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(json.dumps({'main':{k:{f:r[f] for f in ['net','debt','min_mmr','min_cash_years','financed_years']} for k,r in main.items()},'rolling':groups},ensure_ascii=False,indent=2))
