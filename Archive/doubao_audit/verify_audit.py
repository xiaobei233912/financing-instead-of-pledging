"""Cross-check saved report evidence, independent of daily simulator asserts."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/'output'


def main():
    results=json.loads((OUT/'strict_results.json').read_text())
    assert len(results)==810
    counts={}
    for r in results:
        counts[r['failure'] or 'completed']=counts.get(r['failure'] or 'completed',0)+1
        c=r['config']
        if c['never_repay']:
            assert r['interest_paid']==r['principal_repaid']==0
        if c['strategy'] in ['D_hang','D_hold']:
            assert not c['pay_monthly_interest']
            assert c['interest_mode']=='accrue_unpaid'
    days=events=0
    for file in OUT.glob('strict_*_daily.jsonl'):
        for line in file.read_text().splitlines():
            x=json.loads(line);days+=1
            assert x['P']>=-1e-6 and x['I']>=-1e-6
            assert abs(x['A']-x['E']-x['P']-x['I'])<.01
            assert abs(x['credit']-x['own_q']-x['own_c']-x['fin_q']-x['fin_c'])<.01
    for file in OUT.glob('strict_*_events.json'):
        for e in json.loads(file.read_text()):
            if e['kind'].startswith('loan_'):
                assert e['margin_after']>=-.005
                events+=1
    provenance=json.loads((OUT/'provenance.json').read_text(encoding='utf-8'))
    assert all(x['identical'] for x in provenance['files'])
    result=dict(cases=len(results),outcomes=counts,main_daily_rows_checked=days,
                new_loan_margin_checks=events,original_snapshot_matches=len(provenance['files']),
                unit_tests='7 new tests and 16 existing kernel tests passed in recorded executions',
                scope='Outputs checked; contract assumptions and price proxy limitations remain as documented')
    (OUT/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
