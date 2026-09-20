"""Read-only observations of current engines, snapshots and original provenance."""
import csv
import hashlib
import json
from pathlib import Path
import gated_engine as ge

HERE=Path(__file__).resolve().parent
OUT=HERE/'output'
Base=ge.GateAccount


class Observed(Base):
    def rebalance_gated(self,budget):
        result=super().rebalance_gated(budget)
        self.log('rebalance_observation',completed=result,beta=self.stock()/self.total())
        return result


def main():
    ge.GateAccount=Observed
    analyses=[]
    rows=ge.load_rows()
    for name,kw in [('D_hold',dict(never_repay=True)),('D_hang',{})]:
        cfg=ge.GateConfig(strategy=name,rebal_calendar='yearend',guard_runway=3,**kw)
        result,ledger,events=ge.simulate_gate(rows,cfg,trace=True)
        failed=[e for e in events if e['kind']=='rebalance_observation' and not e['completed']]
        paid=[e for e in events if e['kind']=='credit_sale_repay']
        analyses.append(dict(strategy=name,result=result,unfinished_attempts=len(failed),
                             first_unfinished=failed[0] if failed else None,
                             last_unfinished=failed[-1] if failed else None,
                             max_beta_after_unfinished=max([e['beta'] for e in failed],default=None),
                             first_repayment=paid[0] if paid else None,
                             last_ledger=ledger[-1],
                             minimum_cash_runway_row=min(ledger,key=lambda x:x['o_c']+x['withdrawable'])))
        (OUT/f'{name}_rebalance_observations.json').write_text(json.dumps(failed,indent=2),encoding='utf-8')
    (OUT/'path_inspection.json').write_text(json.dumps(analyses,indent=2),encoding='utf-8')
    provenance=[]
    source=HERE/'source'
    external=Path(r'D:\临时\豆包\融资')
    for p in sorted(source.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        rel=p.relative_to(source)
        other=external/rel
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        originalsha=hashlib.sha256(other.read_bytes()).hexdigest() if other.is_file() else None
        provenance.append(dict(file=rel.as_posix(),copied_sha256=sha,external_sha256=originalsha,identical=sha==originalsha))
    original=list(csv.DictReader((source/'data/qqq_daily.csv').open(encoding='utf-8-sig')))
    ours={r['date']:r for r in rows}
    base_date=original[0]['date']
    scale=ours[base_date]['adj_close']/float(original[0]['adj'])
    errors=[abs(ours[r['date']]['adj_close']/float(r['adj'])/scale-1) for r in original if r['date'] in ours]
    data_summary=dict(original_rows=len(original),first=original[0],last=original[-1],
                      shared_dates=len(errors),normalized_close_max_relative_error=max(errors))
    (OUT/'provenance.json').write_text(json.dumps(dict(files=provenance,data_summary=data_summary),indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(analyses,indent=2))
    print('External originals match snapshots:',all(x['identical'] for x in provenance),'files:',len(provenance))


if __name__=='__main__':main()
