from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class DataValidationResult:
    ok: bool
    reason: str = "ok"


class YahooDataProvider:
    def download_daily(self, symbols: list[str], min_days: int = 252) -> dict[str, pd.DataFrame]:
        data: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            df = yf.download(symbol, period="5y", interval="1d", auto_adjust=False, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            df = df.rename(columns={"Adj Close": "Adj_Close"})
            data[symbol] = df.dropna()
        self.validate(data, min_days=min_days, require_symbols=symbols)
        return data

    @staticmethod
    def validate(data: dict[str, pd.DataFrame], min_days: int, require_symbols: list[str]) -> DataValidationResult:
        for symbol in require_symbols:
            if symbol not in data:
                raise ValueError(f"missing_data_for_symbol:{symbol}")
            df = data[symbol]
            if len(df) < min_days:
                raise ValueError(f"insufficient_history:{symbol}:{len(df)}")
            required_cols = {"Open", "High", "Low", "Close", "Adj_Close", "Volume"}
            missing = required_cols - set(df.columns)
            if missing:
                raise ValueError(f"missing_columns:{symbol}:{sorted(missing)}")
            latest = df.iloc[-1]
            if latest["Adj_Close"] <= 0 or latest["Close"] <= 0:
                raise ValueError(f"invalid_price:{symbol}")
            if latest["Volume"] <= 0:
                raise ValueError(f"invalid_volume:{symbol}")
        return DataValidationResult(ok=True)
