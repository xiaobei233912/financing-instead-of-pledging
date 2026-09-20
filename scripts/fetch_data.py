"""Download and audit QQQ OHLC/adjusted closes; Python standard library only."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://query1.finance.yahoo.com/v8/finance/chart/QQQ?period1=915148800&period2=1788912000&interval=1d&events=div%2Csplits'


def main():
    p = ROOT / 'data'
    p.mkdir(exist_ok=True)
    raw = p / 'yahoo_qqq_raw.json'
    if not raw.exists():
        raw.write_bytes(urllib.request.urlopen(urllib.request.Request(
            URL, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read())
    blob = raw.read_bytes()
    src = json.loads(blob)['chart']['result'][0]
    q = src['indicators']['quote'][0]
    adj = src['indicators']['adjclose'][0]['adjclose']
    rows = []
    for i, t in enumerate(src['timestamp']):
        date = dt.datetime.fromtimestamp(t, dt.UTC).date().isoformat()
        if date > '2026-09-08':
            continue
        assert all(q[k][i] is not None and q[k][i] > 0 for k in ['open', 'high', 'low', 'close']), date
        assert adj[i] and adj[i] > 0
        factor = adj[i] / q['close'][i]
        row = {'date': date, 'adj_close': adj[i], 'volume': q['volume'][i]}
        for k in ['open', 'high', 'low', 'close']:
            row[k] = q[k][i]
            row['adj_' + k] = q[k][i] * factor
        assert row['low'] <= min(row['open'], row['close']) + 1e-5
        assert row['high'] >= max(row['open'], row['close']) - 1e-5
        rows.append(row)
    dates = [r['date'] for r in rows]
    assert dates == sorted(set(dates))
    peak = max((r for r in rows if '2000-03-01' <= r['date'] <= '2000-03-31'), key=lambda r: r['close'])
    peak_value = rows[0]['adj_close']
    worst = (0, dates[0])
    for r in rows:
        peak_value = max(peak_value, r['adj_close'])
        worst = min(worst, (r['adj_close'] / peak_value - 1, r['date']))
    gaps = [(a, b, (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days)
            for a, b in zip(dates, dates[1:])
            if (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days > 4]
    refpath = ROOT / 'reference/clec-strategy-backtest/data/qqq-history.json'
    comparison = {}
    if refpath.exists():
        ref = json.loads(refpath.read_text(encoding='utf-8'))
        month_close = {r['date'][:7]: r['close'] for r in rows}
        diffs = [{'month': r['month'], 'reference': r['close'], 'yahoo': month_close[r['month']],
                  'relative_error': abs(r['close'] / month_close[r['month']] - 1)}
                 for r in ref if r['month'] in month_close and r['month'] < dates[-1][:7]]
        comparison = {'months': len(diffs), 'max_relative_error': max(x['relative_error'] for x in diffs),
                      'over_0_1pct': [x for x in diffs if x['relative_error'] > .001]}
    annual = {}
    for year in range(2000, 2026):
        prev = [r for r in rows if r['date'] < f'{year}-01-01'][-1]
        end = [r for r in rows if r['date'] < f'{year+1}-01-01'][-1]
        annual[str(year)] = end['adj_close']/prev['adj_close']-1
    audit = {'download_url': URL, 'audited_at': dt.datetime.now(dt.UTC).isoformat(),
             'raw_sha256': hashlib.sha256(blob).hexdigest(), 'rows': len(rows),
             'start': dates[0], 'end': dates[-1], 'march_2000_peak_close': peak,
             'worst_adjusted_close_drawdown': worst, 'gaps_over_four_calendar_days': gaps,
             'clec_monthly_close_crosscheck': comparison, 'calendar_year_total_returns': annual,
             'notes': ['Adjusted OHLC = raw OHLC times daily adjusted-close/close factor.',
                       'Main path approximates automatic dividend reinvestment in a total-return QQQ proxy.',
                       'Raw-close sensitivity excludes dividends, not a dividend-cash account simulation.',
                       'Yahoo is a third-party vendor. CLEC raw HTML is also Yahoo-derived; crosscheck is not independent.']}
    (p/'qqq_daily.json').write_text(json.dumps(rows, separators=(',', ':')), encoding='utf-8')
    (p/'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in audit.items() if k not in ['march_2000_peak_close', 'calendar_year_total_returns']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
