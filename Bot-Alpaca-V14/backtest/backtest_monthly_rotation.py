from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.config import load_config
from src.strategy import MonthlyMomentumStrategy


def download(symbols: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for symbol in symbols:
        df = yf.download(symbol, period="5y", interval="1d", auto_adjust=False, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        df = df.rename(columns={"Adj Close": "Adj_Close"}).dropna()
        out[symbol] = df
    return out


def month_end_dates(df: pd.DataFrame) -> list[pd.Timestamp]:
    grouped = df.groupby([df.index.year, df.index.month])
    return [group.index[-1] for _, group in grouped]


def slice_until(data: dict[str, pd.DataFrame], date: pd.Timestamp) -> dict[str, pd.DataFrame]:
    return {symbol: df.loc[df.index <= date].copy() for symbol, df in data.items()}


def main() -> None:
    config = load_config(ROOT / "config.yaml")
    strategy = MonthlyMomentumStrategy(config)
    data = download(config.symbols)
    dates = month_end_dates(data[config.symbols[0]])

    portfolio_value = 0.0
    cash_pnl = 0.0
    holdings: dict[str, float] = {}
    last_prices: dict[str, float] = {}
    rows = []

    for date in dates:
        available = slice_until(data, date)
        if min(len(df) for df in available.values()) < max(config.sma_period, config.return_6m_sessions) + 1:
            continue

        # Mark-to-market before rebalance.
        month_value = 0.0
        for symbol, shares in holdings.items():
            price = float(available[symbol]["Adj_Close"].iloc[-1])
            month_value += shares * price
        if holdings:
            pnl = month_value - portfolio_value
            cash_pnl += pnl
        else:
            pnl = 0.0

        targets, signals = strategy.select_targets(available)

        # Rebalance into equal fixed EUR proxy positions, treating EUR=USD for simple backtest.
        holdings = {}
        for symbol in targets:
            price = float(available[symbol]["Adj_Close"].iloc[-1])
            holdings[symbol] = config.capital_per_etf_eur / price
            last_prices[symbol] = price
        portfolio_value = len(targets) * config.capital_per_etf_eur

        rows.append({
            "date": date.date(),
            "targets": ",".join(targets) if targets else "cash",
            "monthly_pnl_eur_proxy": round(pnl, 2),
            "cumulative_pnl_eur_proxy": round(cash_pnl, 2),
        })

    results = pd.DataFrame(rows)
    print(results.tail(36).to_string(index=False))
    if not results.empty:
        print("\nResumen")
        print("Beneficio total proxy:", round(float(results["cumulative_pnl_eur_proxy"].iloc[-1]), 2), "EUR")
        print("Media mensual proxy:", round(float(results["monthly_pnl_eur_proxy"].mean()), 2), "EUR")
        print("Peor mes proxy:", round(float(results["monthly_pnl_eur_proxy"].min()), 2), "EUR")
        print("Mejor mes proxy:", round(float(results["monthly_pnl_eur_proxy"].max()), 2), "EUR")


if __name__ == "__main__":
    main()
