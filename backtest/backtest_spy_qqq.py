"""Backtest for the active strategy: 50/50 SPY-QQQ, threshold +/-5% rebalance.

Compares against SPY buy&hold, QQQ buy&hold, 50/50 buy&hold and 50/50 annual.
Daily adjusted data, costs = 0.1% commission + 0.1% slippage per leg.

Run locally (uses yfinance; Yahoo blocks the cloud host, so production uses
Alpaca instead):

    python backtest/backtest_spy_qqq.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

INITIAL = 400.0
SLIP = 0.001
COMM = 0.001
COST = SLIP + COMM
THRESHOLD = 0.05
START, END = "2011-02-01", "2026-06-25"
TD = 252


def download(symbols):
    out = {}
    for s in symbols:
        df = yf.download(s, start="2010-06-01", end=END, interval="1d",
                         auto_adjust=False, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        out[s] = df.rename(columns={"Adj Close": "Adj_Close"}).dropna()
    return out


def metrics(curve):
    rets = curve.pct_change().dropna()
    years = (curve.index[-1] - curve.index[0]).days / 365.25
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (1 / years) - 1
    dd = curve / curve.cummax() - 1
    vol = rets.std() * np.sqrt(TD)
    sharpe = (rets.mean() * TD) / vol if vol > 0 else float("nan")
    ye = pd.concat([pd.Series([curve.iloc[0]], index=[curve.index[0]]),
                    curve.resample("YE").last()]).pct_change().dropna()
    return dict(final=curve.iloc[-1], cagr=cagr, vol=vol, sharpe=sharpe,
                max_dd=dd.min(), worst=ye.min(), worst_y=ye.idxmin().year)


def main():
    data = download(["SPY", "QQQ"])
    base = data["SPY"].index
    days = base[(base >= pd.Timestamp(START)) & (base <= pd.Timestamp(END))]
    px = pd.DataFrame({s: data[s]["Adj_Close"] for s in ("SPY", "QQQ")}).reindex(base).ffill()
    first = days[0]

    def p(s, d):
        return float(px.at[d, s])

    me = [g.index[-1] for _, g in pd.Series(days, index=days).groupby([days.year, days.month])]
    annual_dates = {base[base > d][0] for d in me if d.month == 12 and len(base[base > d])}

    def run(mode):
        inv = INITIAL * (1 - COST)
        sh = {"SPY": (inv / 2) / p("SPY", first), "QQQ": (inv / 2) / p("QQQ", first)}
        legs = 2
        eq = {}
        for day in days:
            v_spy, v_qqq = sh["SPY"] * p("SPY", day), sh["QQQ"] * p("QQQ", day)
            do = False
            if mode == "annual":
                do = day in annual_dates
            elif mode == "threshold":
                w = v_spy / (v_spy + v_qqq)
                do = abs(w - 0.5) > THRESHOLD
            if do:
                total = v_spy + v_qqq
                target = total / 2
                turnover = abs(v_spy - target) + abs(v_qqq - target)
                if turnover > 1e-9:
                    t2 = (total - turnover * COST) / 2
                    sh["SPY"], sh["QQQ"] = t2 / p("SPY", day), t2 / p("QQQ", day)
                    legs += 2
            eq[day] = sh["SPY"] * p("SPY", day) + sh["QQQ"] * p("QQQ", day)
        return pd.Series(eq), legs

    def buyhold(weights):
        sh = {s: (INITIAL * w * (1 - COST)) / p(s, first) for s, w in weights.items()}
        return pd.Series({day: sum(x * p(s, day) for s, x in sh.items()) for day in days}), len(weights)

    cols = {
        "50/50 umbral 5%": run("threshold"),
        "50/50 anual": run("annual"),
        "50/50 buy&hold": buyhold({"SPY": 0.5, "QQQ": 0.5}),
        "SPY buy&hold": buyhold({"SPY": 1.0}),
        "QQQ buy&hold": buyhold({"QQQ": 1.0}),
    }
    names = list(cols)
    M = {n: metrics(c) for n, (c, _) in cols.items()}

    print(f"Estrategia activa: 50/50 SPY-QQQ, rebalanceo umbral +/-{THRESHOLD:.0%}")
    print(f"Periodo: {first.date()} -> {days[-1].date()} ({len(days)} sesiones)\n")
    print("=" * 92)
    print(f"{'':18}" + "".join(f"{n:>15}" for n in names))
    print("=" * 92)
    for label, key, fmt in [("Equity final (EUR)", "final", "{:.0f}"),
                            ("CAGR", "cagr", "{:+.2%}"),
                            ("Volatilidad", "vol", "{:.2%}"),
                            ("Sharpe", "sharpe", "{:.3f}"),
                            ("Max drawdown", "max_dd", "{:.2%}")]:
        print(f"{label:18}" + "".join(f"{fmt.format(M[n][key]):>15}" for n in names))
    print(f"{'Peor año':18}" + "".join(f"{(str(round(M[n]['worst']*100,1))+'% (' + str(M[n]['worst_y'])[2:] + ')'):>15}" for n in names))
    print(f"{'Nº operaciones':18}" + "".join(f"{cols[n][1]:>15}" for n in names))
    print("=" * 92)


if __name__ == "__main__":
    main()
