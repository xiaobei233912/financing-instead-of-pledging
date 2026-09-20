"""Run fixed protocol cases and write JSON results + Markdown tables."""
import concurrent.futures as cf
import datetime as dt
import json
from pathlib import Path
from statistics import median
from backtest import Config, ROOT, load_rows, simulate, add_months

_ROWS = None


def worker(job):
    global _ROWS
    if _ROWS is None:
        _ROWS = load_rows()
    label, start, end, kwargs = job
    r, _, _ = simulate(_ROWS, Config(**kwargs), start, end)
    r['experiment'] = label
    return r


def save(name, data):
    p = ROOT/'results'
    p.mkdir(exist_ok=True)
    (p/name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def main():
    rows = load_rows()
    peak = max([r for r in rows if '2000-03-01' <= r['date'] <= '2000-03-31'], key=lambda r: r['close'])['date']
    strategies = ['A', 'B', 'C1', 'C2', 'C3', 'N']
    weights = [.5, .6, .7, .8]
    cases = []
    for start in ['2000-03-10', peak]:
        for w in weights:
            for s in strategies:
                r, ledger, events = simulate(rows, Config(strategy=s, weight=w), start, trace=True)
                cases.append(r)
                tag = f'{s}_{w:.2f}_{start}'
                # JSON Lines keep auditable daily output small and streamable.
                p = ROOT/'results/traces'
                p.mkdir(parents=True, exist_ok=True)
                (p/(tag+'_daily.jsonl')).write_text('\n'.join(json.dumps(x, allow_nan=False) for x in ledger), encoding='utf-8')
                (p/(tag+'_events.json')).write_text(json.dumps(events, indent=2, allow_nan=False), encoding='utf-8')
    save('stress_cases.json', cases)
    print(f'Stress cases done: {len(cases)}; March peak {peak}', flush=True)
    starts = []
    seen = set()
    for r in rows:
        d = dt.date.fromisoformat(r['date'])
        if d.month in [1, 4, 7, 10] and (d.year, d.month) not in seen:
            starts.append(r['date'])
            seen.add((d.year, d.month))
    jobs = []
    last = dt.date.fromisoformat(rows[-1]['date'])
    for s in strategies:
        for w in weights:
            for start in starts:
                begin = dt.date.fromisoformat(start)
                if add_months(begin, 12) <= last:
                    jobs.append(('to_end_min1y', start, None, {'strategy': s, 'weight': w}))
                # Common full horizons, excluding short censored runs.
                for years in [5, 10, 20]:
                    end = add_months(begin, years*12)-dt.timedelta(days=1)
                    if end <= last:
                        jobs.append((f'fixed_{years}y', start, str(end), {'strategy': s, 'weight': w}))
    for s in ['A', 'B', 'C1', 'C2', 'C3']:
        for w in [.6, .7, .8]:
            tests = [('cash0', {'cash_yield': 0}), ('cash3', {'cash_yield': .03}),
                     ('rate4', {'interest': .04}), ('rate6', {'interest': .06}),
                     ('withdraw3', {'withdrawal': .03}), ('inflation2', {'inflation': .02}),
                     ('raw_no_dividend', {'price_mode': 'raw'}), ('settlement3', {'settlement_days': 3})]
            if s.startswith('C'):
                tests += [('deny_renew_2008', {'deny_renew_from': '2008-01-01'}),
                          ('deny_and_no_new_2008', {'deny_renew_from': '2008-01-01', 'block_new_from': '2008-01-01'}),
                          ('deferred_simple_interest', {'interest_mode': 'deferred'}),
                          ('haircuts_lower', {'stock_haircut': .5, 'cash_haircut': .7}),
                          ('margin120', {'margin_requirement': 1.2})]
            for label, extra in tests:
                jobs.append((label, peak, None, {'strategy': s, 'weight': w, **extra}))
    # Matched paid-interest ideal PAL isolates capitalization assumptions.
    for w in weights:
        jobs.append(('ideal_paid_interest', peak, None, {'strategy': 'B_cash', 'weight': w}))
    results = []
    print(f'Batch experiments queued: {len(jobs)}', flush=True)
    with cf.ProcessPoolExecutor(max_workers=6) as pool:
        for i, r in enumerate(pool.map(worker, jobs, chunksize=8), 1):
            results.append(r)
            if i % 500 == 0:
                print(f'Completed {i}/{len(jobs)}', flush=True)
    save('experiments.json', results)
    groups = []
    for horizon in ['to_end_min1y', 'fixed_5y', 'fixed_10y', 'fixed_20y']:
        for w in weights:
            comparator = {r['start']: r for r in results if r['experiment'] == horizon and r['config']['strategy'] == 'A' and r['config']['weight'] == w}
            for s in strategies:
                group = [r for r in results if r['experiment'] == horizon and r['config']['strategy'] == s and r['config']['weight'] == w]
                failures = [r for r in group if r['failure']]
                margin = [r['min_margin_ratio'] for r in group if r['min_margin_ratio'] is not None]
                pair = [r['final_net_assets']/comparator[r['start']]['final_net_assets']-1
                        for r in group if not r['failure'] and not comparator[r['start']]['failure']]
                groups.append({'horizon': horizon, 'strategy': s, 'weight': w, 'n': len(group),
                               'failures': len(failures), 'margin_failures': sum(r['failure'] == 'MarginFailure' for r in group),
                               'liquidity_failures': sum(r['failure'] == 'LiquidityFailure' for r in group),
                               'other_failures': sum(r['failure'] not in [None, 'MarginFailure', 'LiquidityFailure'] for r in group),
                               'min_margin': min(margin) if margin else None,
                               'min_runway': min(r['min_ordinary_runway'] for r in group),
                               'min_cash_runway': min(r['min_ordinary_cash_runway'] for r in group),
                               'median_final_net': median(r['final_net_assets'] for r in group),
                               'min_final_net': min(r['final_net_assets'] for r in group),
                               'median_advantage_over_A_survivors': median(pair) if pair else None,
                               'fraction_beating_A_survivors': sum(x > 0 for x in pair)/len(pair) if pair else None,
                               'median_financed_fraction': median(r['financed_fraction'] for r in group),
                               'failure_details': [{'start': r['start'], 'failure': r['failure'], 'date': r['failure_date']} for r in failures]})
    save('rolling_summary.json', groups)
    print('All experiments complete.', flush=True)


if __name__ == '__main__':
    main()
