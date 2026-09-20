from pathlib import Path
import json,re,hashlib
ROOT=Path(__file__).resolve().parent.parent
P=ROOT/'results/partial_living_cash1_rate3'
def read(name):return json.loads((P/name).read_text(encoding='utf-8'))
main=read('main.json');rolling=read('rolling.json');order=read('order_comparison.json')
for r in main+rolling+order:
    assert r['config']['cash_yield']==.01 and r['config']['interest']==.03
for r in main:
    tag=r['name']+'_'+r['start']
    annual=read(tag+'_annual.json');daily=read(tag+'_daily.json')
    assert abs(sum(a['living_paid'] for a in annual)-r['living_paid'])<.01
    if r['name'].startswith('relay'):
        assert abs(sum(a['financed_amount'] for a in annual)-r['principal'])<.01
        assert r['interest_paid']==r['principal_repaid']==0
        for d in daily:
            assert abs(d['ordinary_total']+d['credit_total']+d['transit']-d['debt']-d['net'])<.01
    for a in annual:
        if not a['failure']:assert abs(a['reconciliation_error'])<.01
f=next(r for r in main if r['name']=='relay70_w3' and r['start']=='2000-03-27')
assert f['failure']=='LiquidityFailure' and f['end_actual']=='2017-01-05'
assert f['available_own_stock_transfer']==0 and abs(30000-f['bank_liquid']-3031.31678685224)<.01
assert len(main)==19 and len(rolling)==306 and len(order)==12
report=ROOT/'reports/现金接力_部分融资规则更新.md'
for p in [report,*list((ROOT/'reports').glob('现金接力部分融资_逐年账_*.md'))]:
    for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if not link.startswith(('http:','https:','#')):assert (p.parent/link).exists(),link
v=dict(status='passed',main_paths=19,rolling_windows=306,order_cases=12,
       failures=sum(bool(r['failure']) for r in rolling),accounting='annual living, principal, unpaid interest and double-account equity checked',
       report_sha256=hashlib.sha256(report.read_bytes()).hexdigest())
(P/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(v,indent=2))
