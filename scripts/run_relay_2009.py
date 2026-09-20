"""Change only the starting date; apply the selected 160% -> 200% rescue rule."""
from collateral_relay import run,RescueSettings,SmartConfig,load_rows,clean
from dataclasses import asdict
from pathlib import Path
import json,hashlib,sys,datetime as dt

ROOT=Path(__file__).parent.parent;OUT=ROOT/'results'/'relay_2009';OUT.mkdir(parents=True,exist_ok=True)
rows=load_rows();low=min((r for r in rows if r['date'].startswith('2009')),key=lambda r:r['adj_close'])
start=low['date'];end=rows[-1]['date'];settings=RescueSettings(trigger=1.6,target=2.)
def save(name,data):(OUT/name).write_text(json.dumps(clean(data),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
results=[];annuals={};dailies={}
for label,weight,floor in [('70/30',.7,15),('80/20',.8,10)]:
    cfg=SmartConfig(strategy='proportional',weight=weight,reserve_years=floor,buy_cash_weight=1-weight,renewal_floor=1.4)
    r,y,d,e=run(rows,cfg,settings,start,end,trace=True)
    assert not r['failure']
    assert r['interest_paid']==r['principal_repaid']==0
    for item in y:assert abs(item['reconciliation_error'])<.01
    for item in d:
        assert abs(item['total_assets']-item['ordinary_total']-item['credit_total']-item['transit'])<.01
        assert abs(item['net']-item['total_assets']+item['debt'])<.01
    r['label']=label;r['rescue']=asdict(settings)
    span=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days/365.25
    r['net_balance_annualized']=(r['net']/cfg.initial)**(1/span)-1
    results.append(r);annuals[label]=y;dailies[label]=d
    prefix=label.replace('/','')
    save(prefix+'_annual.json',y);save(prefix+'_daily.json',d);save(prefix+'_events.json',e)
save('summary.json',results)
save('provenance.json',dict(start=start,end=end,start_rule='2009 lowest QQQ adjusted daily close, ex-post scenario',
    chosen_rule=asdict(settings),data_sha256=hashlib.sha256((ROOT/'data'/'qqq_daily.json').read_bytes()).hexdigest(),
    max_annual_reconciliation_error=max(abs(y['reconciliation_error']) for ys in annuals.values() for y in ys)))

sys.path.insert(0,str(ROOT/'results'/'smart_relay_python'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False,'font.size':11})
fig,axes=plt.subplots(1,2,figsize=(13,4.6),layout='constrained')
for label,color in [('70/30','#176b9c'),('80/20','#e47932')]:
    d=dailies[label];x=[dt.date.fromisoformat(v['date']) for v in d]
    for ax,key,title in [(axes[0],'net','总净资产（万元，已扣生活支出及负债）'),(axes[1],'ordinary_cash','普通账户现金（万元）')]:
        ax.plot(x,[v[key]/10000 for v in d],label=label,color=color,lw=1.6)
        ax.set_title(title,loc='left');ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
axes[0].legend(frameon=False)
fig.suptitle(f'2009年低点起投：70/30与80/20现金接力\n{start}—{end}｜初始100万元，每年花2万元｜160%触发，补到200%',fontsize=14)
fig.savefig(OUT/'comparison.png',dpi=150);plt.close(fig)

def m(v):return f'{v/10000:.2f}'
def pct(v):return '—' if v is None else f'{v*100:.2f}%'
def table(head,body):return ['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+['| '+' | '.join(map(str,row))+' |' for row in body]
a,b=results
lines=['# 2009年低点起投：70/30与80/20现金接力','',f'区间：{start}收盘起投，至{end}。只更改起点，并统一使用用户选定的160%触发、200%目标补担保规则。',
'',f'**80/20期末净资产比70/30多{m(b["net"]-a["net"])}万元（高{(b["net"]/a["net"]-1)*100:.2f}%）。**','',
'本地QQQ日线中，2009年最低收盘、最低复权收盘和最低复权日内价都发生在2009-03-09。本次使用该日收盘价，不使用日内最低价作为成交价。这是按用户要求事后选取的有利起点，不代表当时能识别底部。纳斯达克也将2009年3月描述为该轮危机低点：[Nasdaq历史回顾](https://indexes.nasdaq.com/docs/Nasdaq-100_A%20Tale%20of%20Three%20Crises%20over%20Two%20Decades.pdf)。','',
'初始100万元；生活费固定每年2万元；融资2.8%单利挂息；普通现金/现金类证券收益2%；买股分别只使用超过15年/10年开销的普通现金；总资产配比再平衡。补担保可用尽普通现金，优先现金类证券划转，次交易日到账；主版本不主动还本付息。其余融资资格、交收、300%转出门槛、年度操作顺序均沿用前次模型。','',
'使用QQQ复权历史代理，未计人民币汇率和三只境内ETF溢折价、实际费税；数据截止沿用上一轮，未更新行情。2009和2026均不完整年度，模型仍各支取全年预算，共18次、36万元。','']
metrics=[('期末净资产/万元','net',m),('普通账户现金/万元','ordinary_cash',m),('信用股票/万元','credit_stock',m),('信用现金类担保品/万元','credit_cash',m),('融资本金/万元','principal',m),('未付利息/万元','unpaid_interest',m),('负债合计/万元','debt',m),('实际融资年数','financed_years',str),('累计生活支出/万元','living_paid',m),('最低普通现金/年开销','min_cash_years',lambda v:f'{v:.2f}'),('最低维持率','min_mmr',pct),('净资产最大回撤','max_drawdown',pct),('补担保累计/万元','rescue_cash_in',m),('付息/万元','interest_paid',m),('还本/万元','principal_repaid',m)]
lines+=table(['指标','70/30','80/20'],[[title,fmt(a[key]),fmt(b[key])] for title,key,fmt in metrics])
lines+=['','![净资产与现金对比](../results/relay_2009/comparison.png)','',
'最大回撤按扣除生活支出后的日终净资产计算，包含支出影响。最低维持率则包括日内最低价。未发生补担保时，不能用本次表现证明160%/200%的救险参数更优。','',
'## 逐年净资产与融资','']
lines+=table(['年','70/30净资产/万元','80/20净资产/万元','80/20多出/万元','70/30融资','80/20融资'],[
    [x['year'],m(x['net']),m(y['net']),m(y['net']-x['net']),'是' if x['financed'] else '否','是' if y['financed'] else '否']
    for x,y in zip(annuals['70/30'],annuals['80/20'])])
for label in ['70/30','80/20']:
    lines+=['',f'## {label}逐年账户明细（万元）','']
    lines+=table(['年','普通现金','信用股票','信用现金类','本金','未付息','年末维持率','年内最低维持率'],[
        [y['year'],m(y['ordinary_cash']),m(y['credit_stock']),m(y['credit_cash']),m(y['principal']),m(y['unpaid_interest']),pct(y['mmr']),pct(y['min_mmr'])] for y in annuals[label]])
    failed=[str(y['year'])+'：'+str(y['finance_rejection']) for y in annuals[label] if not y['financed']]
    lines+=['','未融资原因：'+('；'.join(failed) if failed else '每年都实际融资')+'。']
lines+=['','校验：两套逐年资产变化均与股票损益、现金收益、利息费用和生活支出对账一致；信用现金类担保品未重复计入普通账户；本息实际偿还均为0。完整配置、日账和事件记录保存在results/relay_2009。']
(ROOT/'reports/现金接力_2009低点起投对比.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps([{k:r[k] for k in ['label','net','ordinary_cash','credit_stock','principal','unpaid_interest','debt','financed_years','min_mmr','min_cash_years','max_drawdown','rescue_cash_in','living_paid']} for r in results],ensure_ascii=False,indent=2))
