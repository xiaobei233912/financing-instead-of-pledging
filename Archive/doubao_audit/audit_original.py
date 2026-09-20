"""Read-only reproduction of the copied Doubao engine, with observational probes.
Source folder is a snapshot, original external workspace is never imported.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def module(name, code):
    path = HERE/'output'/f'{name}.py'
    path.write_text(code, encoding='utf-8')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    src = (HERE/'source/pal_engine.py').read_text(encoding='utf-8')
    # These probes do not modify trading decisions or account values.
    probed = src.replace('    rec = []', '    rec = []\n    audit = []')
    probed = probed.replace('        # 普通账户卖出等额 QQQ 并提现消费',
        '''        audit.append(dict(date=str(df["date"].iloc[i].date()), kind="new_loan",
                          P=a.P, I=a.I, G=a.credit_assets()-2*a.P-a.I))
        # 普通账户卖出等额 QQQ 并提现消费''')
    probed = probed.replace('                    a.fin_q-=x; a.P-=x; delta-=x',
        '''                    audit.append(dict(date=str(df["date"].iloc[i].date()), kind="sell_financed",
                                      proceeds=x, P_before=a.P, I_before=a.I))
                    a.fin_q-=x; a.P-=x; delta-=x''')
    probed = probed.replace('                        a.P+=x; a.fin_c+=x',
        '''                        a.P+=x; a.fin_c+=x
                        audit.append(dict(date=str(df["date"].iloc[i].date()), kind="refinance_cash",
                                          P=a.P, I=a.I, G=a.credit_assets()-2*a.P-a.I))''')
    probed = probed.replace('        # ---- 年度事件 ----',
        '        before_action_mmr = eff_mmr()\n        # ---- 年度事件 ----')
    probed = probed.replace('            "dd": dd,',
        '''            "dd": dd, "before_action_mmr": before_action_mmr,
            "own_c": a.own_c, "own_q": a.own_q, "fin_q": a.fin_q, "fin_c": a.fin_c,
            "o_c": a.o_c, "o_q": a.o_q, "G_haircuts1": a.credit_assets()-2*a.P-a.I,''')
    probed = probed.replace('    if return_events: return out, summary, events',
        '    summary["audit"] = audit\n    if return_events: return out, summary, events')
    mod = module('instrumented_original', probed)
    original = module('unmodified_original', src)
    data = pd.read_csv(HERE/'source/data/qqq_daily.csv', parse_dates=['date'])
    records = []
    for mode in ['A', 'B', 'C0', 'C1', 'C2']:
        kw = dict(dd_freeze=.25, defensive_beta=.5) if mode == 'C2' else {}
        out, result, events = mod.simulate(data, mode, mod.Params(**kw), start='2000-03-27', return_events=True)
        _, check = original.simulate(data, mode, original.Params(**kw), start='2000-03-27')
        for k, v in check.items():
            assert v == result[k] or (isinstance(v, float) and np.isnan(v)), (mode, k)
        audit = result.pop('audit')
        negative = out[out.P < -1e-10]
        violations = [r for r in audit if r['kind'] in ['new_loan','refinance_cash'] and r['G'] < -1e-9]
        oversized = [r for r in audit if r['kind']=='sell_financed' and r['proceeds']>r['P_before']+1e-9]
        result.update(negative_principal_days=len(negative), min_principal=float(out.P.min()),
                      first_negative_day=str(negative.date.iloc[0].date()) if len(negative) else None,
                      first_day_assets=float(out.A.iloc[0]),
                      before_action_min_mmr=float(out.before_action_mmr.min()),
                      hidden_pre_action_breaches=int(((out.before_action_mmr<1.4)&(out.MMR>=1.4)).sum()),
                      topups=sum(e[1]=='topup' for e in events),
                      invalid_margin_orders=violations, oversized_repayments=oversized,
                      annual_borrow_events=sum(e[1]=='living' and e[3]=='borrow' for e in events))
        out.to_json(HERE/'output'/f'original_{mode}_daily.jsonl', orient='records', lines=True, date_format='iso')
        (HERE/'output'/f'original_{mode}_events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')
        records.append(result)
    (HERE/'output/original_audit.json').write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=True), encoding='utf-8')
    # Exact start counts from the supplied scripts, rather than report prose.
    semi = list(range(126,len(data)-2520,126))
    quarter = list(range(126,len(data)-2520,63))
    comparable = {'halfyear_count':len(semi), 'quarter_count_same_bounds':len(quarter),
                  'first_start': str(data.date.iloc[semi[0]].date()), 'last_halfyear_start':str(data.date.iloc[semi[-1]].date()),
                  'last_quarter_start':str(data.date.iloc[quarter[-1]].date())}
    (HERE/'output/start_counts.json').write_text(json.dumps(comparable, indent=2), encoding='utf-8')
    for r in records:
        print(r['mode'], r['status'], r['final_E'], 'negative_P_days',r['negative_principal_days'],
              'bad_margin_orders',len(r['invalid_margin_orders']), 'oversized',len(r['oversized_repayments']),
              'hidden_breach',r['hidden_pre_action_breaches'])
    print(comparable)


if __name__ == '__main__':
    main()
