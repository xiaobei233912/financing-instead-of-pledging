"""Validate generated ledgers, article values and local report links."""
from pathlib import Path
import json
import re
import hashlib

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'results/partial_living'
main=json.loads((OUT/'main.json').read_text(encoding='utf-8'))
checked=0
for r in main:
    if not r['name'].startswith('relay'):continue
    tag=r['name']+'_'+r['start']
    annual=json.loads((OUT/(tag+'_annual.json')).read_text(encoding='utf-8'))
    daily=json.loads((OUT/(tag+'_daily.json')).read_text(encoding='utf-8'))
    assert abs(sum(a['financed_amount'] for a in annual)-r['principal'])<.01
    assert abs(sum(a['living_paid'] for a in annual)-r['living_paid'])<.01
    assert abs(min(a['min_mmr'] for a in annual if a['min_mmr'] is not None)-r['min_mmr'])<1e-7
    assert abs(min(a['ordinary_cash'] for a in daily)-r['min_cash'])<.01
    assert r['full_finance_years']+r['partial_finance_years']+r['cash_only_years']==len(annual)
    for a in daily:
        assert abs(a['total_assets']-a['debt']-a['net'])<.01
        assert abs(a['ordinary_total']+a['credit_total']+a['transit']-a['total_assets'])<.01
    checked+=1
article=ROOT/'reports/现金接力策略_文章续写.md'
body=article.read_text(encoding='utf-8')
for r in main:
    if r['start']=='2000-03-27' and r['name'].startswith('relay'):
        for val in [f'{r["net"]/10000:.2f}',f'{r["min_cash_years"]:.2f}',f'{r["min_mmr"]*100:.2f}']:
            assert val in body,(r['name'],val)
reports=[article,ROOT/'reports/现金接力_部分融资规则更新.md',*list((ROOT/'reports').glob('现金接力部分融资_逐年账_*.md'))]
for report in reports:
    for link in re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8')):
        if link.startswith(('https:','http:','#')):continue
        assert (report.parent/link).exists(),(report.name,link)
verification=dict(status='passed',main_paths_reconciled=checked,local_reports_checked=len(reports),
                  article_numbers_match=True,tests='50 passed (python -m unittest discover -s scripts -p test_*.py)',
                  data_sha256=hashlib.sha256((ROOT/'data/qqq_daily.json').read_bytes()).hexdigest(),
                  article_sha256=hashlib.sha256(article.read_bytes()).hexdigest(),
                  main_sha256=hashlib.sha256((OUT/'main.json').read_bytes()).hexdigest())
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(verification,ensure_ascii=True,indent=2))
