# -*- coding: utf-8 -*-
"""
prepare_data.py
将 Yahoo Finance chart API 下载的原始 JSON 清洗为日频数据集。

QQQ: 使用 adjclose（向后复权，含分红再投资）作为 Nasdaq-100 总回报代理。
^IRX: 13 周美债年化收益率(%)，作为现金类资产真实收益率序列（敏感性分析用）。
主回测默认使用参数化恒定现金收益率，IRX 序列仅用于对照。
"""
import json, os, datetime as dt
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))


def parse_yahoo(path):
    j = json.load(open(path, encoding="utf-8"))
    r = j["chart"]["result"][0]
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
    df = pd.DataFrame({
        "date": [dt.datetime.utcfromtimestamp(t).date() for t in ts],
        "close": q["close"],
        "adj": adj,
    }).dropna()
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def main():
    qqq = parse_yahoo(os.path.join(BASE, "qqq_yahoo.json"))
    qqq["qqq_ret"] = qqq["adj"].pct_change().fillna(0.0)

    # ^IRX 年化收益率（百分数 -> 小数），按日期对齐并向前填充
    irx = parse_yahoo(os.path.join(BASE, "irx_yahoo.json"))
    irx = irx.rename(columns={"close": "irx_yield"})[["date", "irx_yield"]]
    irx["irx_yield"] = pd.to_numeric(irx["irx_yield"], errors="coerce").ffill() / 100.0

    df = qqq.merge(irx, on="date", how="left")
    df["irx_yield"] = df["irx_yield"].ffill().bfill()
    # 日化现金收益率（按 252 交易日折算）
    df["cash_ret_irx"] = (1.0 + df["irx_yield"]) ** (1.0 / 252.0) - 1.0

    out = df[["date", "close", "adj", "qqq_ret", "irx_yield", "cash_ret_irx"]]
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    out_path = os.path.join(BASE, "data", "qqq_daily.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")

    # ---------- sanity statistics ----------
    s = out.set_index("date")
    print("交易日数:", len(s), s.index[0].date(), "->", s.index[-1].date())
    # 2000 年高点（adjclose）
    seg = s["adj"][:"2003-12-31"]
    peak_date = seg.idxmax(); peak = seg.max()
    # 高点之后的最低点（至 2006）
    after = s.loc[peak_date:"2006-12-31", "adj"]
    trough_date = after.idxmin(); trough = after.min()
    print(f"2000 泡沫顶点(复权): {peak_date.date()}  价格 {peak:.2f}")
    print(f"随后最低点(复权):    {trough_date.date()}  价格 {trough:.2f}  最大跌幅 {trough/peak-1:.1%}")
    # 2007-2009
    g = s["adj"]["2007": "2011"]
    p07 = g[:"2008-09-30"].max(); t09 = g["2008-09":"2009-12-31"].min()
    print(f"2008 金融危机回撤: {t09/p07-1:.1%}")
    # 回到 2000 顶点的日期
    recovered = s.loc[s.index > peak_date]
    rec_date = recovered.index[recovered["adj"] >= peak]
    print("首次收复 2000 顶点(复权含分红):", rec_date[0].date() if len(rec_date) else "未收复")
    # 全样本最大回撤
    cummax = s["adj"].cummax()
    dd = s["adj"] / cummax - 1
    i = dd.idxmin()
    print(f"全样本最大回撤: {dd.min():.1%} 触底日 {i.date()}")
    print("已写出:", out_path)


if __name__ == "__main__":
    main()
