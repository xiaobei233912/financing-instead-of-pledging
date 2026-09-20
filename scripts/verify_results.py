"""Verify saved stress results with transaction-level equity conservation;
run additional stresses motivated by source evidence, without tuning strategy.
"""
import json
from backtest import ROOT, load_rows, simulate, Config


def main():
    rows = load_rows()
    saved = json.loads((ROOT/'results/stress_cases.json').read_text())
    for old in saved:
        new, _, _ = simulate(rows, Config(**old['config']), old['start'])
        assert new == old, (old['start'], old['config'])
    print(f'{len(saved)} saved stress results reproduced exactly; daily equity checks passed.')
    extras = []
    for w in [.6, .7, .8]:
        for s in ['A', 'B', 'C1', 'C2', 'C3']:
            labels = [('joint_cash0_rate6_inflation2', dict(cash_yield=0, interest=.06, inflation=.02))]
            if s.startswith('C'):
                labels.append(('broker_margin300', dict(margin_requirement=3.)))
            if s == 'C1':
                labels.extend([('cap8', dict(cap_override=.08)), ('cap12', dict(cap_override=.12))])
            for label, kw in labels:
                r, _, _ = simulate(rows, Config(strategy=s, weight=w, **kw), '2000-03-27')
                r['experiment'] = label
                extras.append(r)
    (ROOT/'results/additional_stresses.json').write_text(json.dumps(extras, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Additional stresses: {len(extras)}')


if __name__ == '__main__':
    main()
