"""Create article figures from the existing, verified research snapshots."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'results' / 'smart_relay_python'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT / 'reports' / 'assets' / 'cash_relay_article'
OUT.mkdir(parents=True, exist_ok=True)
main = json.loads((ROOT / 'results/partial_living_cash1_rate3/main.json').read_text(encoding='utf-8'))

def get(rows, name, start, allow_failure=False):
    matches = [r for r in rows if r['name'] == name and r['start'] == start]
    assert len(matches) == 1, (name, start, len(matches))
    assert allow_failure or matches[0]['failure'] is None
    return matches[0]

plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei'], 'axes.unicode_minus': False,
                     'font.size': 13, 'text.color': '#27333A', 'axes.labelcolor': '#53616A',
                     'axes.edgecolor': '#D9DFE2', 'xtick.color': '#53616A',
                     'ytick.color': '#27333A', 'savefig.facecolor': 'white'})
TEAL, BLUE, GRAY, PURPLE, ORANGE = '#267A70', '#416C92', '#89969F', '#807391', '#C78045'

def bars(filename, title, subtitle, labels, values, colors, unit, annotations, footer, xmax=None):
    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=180)
    fig.subplots_adjust(left=.29, right=.94, top=.73, bottom=.31)
    fig.text(.06, .925, title, fontsize=21, weight='bold')
    fig.text(.06, .85, subtitle, fontsize=11.5, color='#53616A')
    ax.barh(range(len(labels)), values, height=.49, color=colors)
    ax.set_yticks(range(len(labels)), labels, fontsize=13)
    ax.invert_yaxis()
    ax.set_xlim(0, xmax or max(values)*1.38)
    ax.set_xlabel(unit, fontsize=11, labelpad=9)
    ax.set_axisbelow(True)
    ax.grid(axis='x', alpha=.15)
    ax.tick_params(axis='both', length=0, pad=9)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for i, (value, note) in enumerate(zip(values, annotations)):
        ax.text(value + ax.get_xlim()[1]*.022, i, note, va='center', fontsize=13, weight='bold')
    fig.text(.06, .083, footer, fontsize=10, color='#65727A', linespacing=1.7)
    fig.savefig(OUT / filename)
    plt.close(fig)

bad = {n: get(main, n, '2000-03-27') for n in ('relay70', 'relay80', 'sale80', 'pal80')}
good = {n: get(main, n, '2009-03-09') for n in ('relay70', 'relay80', 'sale80', 'pal80')}
w3 = get(main, 'relay70_w3', '2000-03-27', allow_failure=True)
assert w3['failure']=='LiquidityFailure' and w3['end_actual']=='2017-01-05'
names = ('sale80', 'relay70', 'relay80', 'pal80')
vals = [bad[n]['net']/10000 for n in names]
bars('01_2000_net_assets.png', '2000年高点入场：借款与现金接力的价值',
     '初始100万元，每年花2万元；2000-03-27至2026-09-08',
     ['80/20 卖资产', '70/30 现金接力', '80/20 现金接力', '80/20 理想化PAL'], vals, [GRAY, TEAL, BLUE, PURPLE],
     '期末净资产（万元）', [f'{v:,.2f}万' for v in vals],
     '均已支付54万元生活费，净资产已扣全部债务；接力采用先转后借、允许部分融资。\nQQQ复权代理；接力3%单利，PAL 3%复利，现金收益1%；配比并不完全相同。')
risk = [bad['relay70'], w3, bad['relay80']]
vals = [r['min_cash_years'] for r in risk]
bars('02_cash_cushion.png', '现金余量与支付结果：提取3%未能完成',
     '同样从2000-03-27起投；两种2%路径完成，3%路径在2017年支付失败',
     ['70/30 · 每年2%', '70/30 · 每年3%', '80/20 · 每年2%'], vals, [TEAL, ORANGE, BLUE],
     '最低普通现金 ÷ 各自一年的生活费（年）',
     [f'{v:.2f}年 / {r["min_cash"]/10000:.2f}万' if not r['failure'] else '0.00年*（支付失败）' for v,r in zip(vals,risk)],
     '* 0为现金在途时的最低值；2017-01-05到账2.70万元，未能付足全年3万元生活费。\n现金收益1%，接力3%单利；两种2%路径完成至2026-09-08。普通现金不含在途资产。', xmax=12)
names = ('sale80', 'relay70', 'relay80', 'pal80')
vals = [good[n]['net']/10000 for n in names]
bars('03_2009_net_assets.png', '2009年低点入场：同配比的收益差距缩小',
     '初始100万元，每年花2万元；2009-03-09至2026-09-08',
     ['80/20 卖资产', '70/30 现金接力', '80/20 现金接力', '80/20 理想化PAL'], vals,
     [GRAY, TEAL, BLUE, PURPLE], '期末净资产（万元）', [f'{v:,.2f}万' for v in vals],
     '均已支付36万元生活费，并扣除全部负债；现金收益1%，接力3%单利，PAL 3%复利。\n同为80/20：现金接力比卖资产高约8.3%，PAL高约8.2%；70/30接力低于80/20卖资产。')
print(json.dumps({'output': str(OUT), 'bad_relay70_vs_sale_pct': (bad['relay70']['net']/bad['sale80']['net']-1)*100,
                  'bad_relay80_vs_sale_pct': (bad['relay80']['net']/bad['sale80']['net']-1)*100,
                  'bad_pal_vs_sale_pct': (bad['pal80']['net']/bad['sale80']['net']-1)*100,
                  'good_relay80_vs_sale_pct': (good['relay80']['net']/good['sale80']['net']-1)*100,
                  'good_pal_vs_sale_pct': (good['pal80']['net']/good['sale80']['net']-1)*100}, ensure_ascii=False, indent=2))
