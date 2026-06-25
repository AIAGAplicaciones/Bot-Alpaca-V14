from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv


@dataclass(frozen=True)
class DataValidationResult:
    ok: bool
    reason: str = "ok"


class AlpacaDataProvider:
    """Daily OHLCV bars from Alpaca's market data API.

    Replaces the previous Yahoo Finance source, which Yahoo blocks from cloud
    datacenter IPs (the deploy host), returning empty bodies and JSONDecodeError.
    """

    def __init__(self, years: int = 5):
        load_dotenv()
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        # Free Alpaca accounts only have access to the IEX feed.
        self.feed = os.getenv("ALPACA_DATA_FEED", "iex").lower()
        self.years = years

        if not self.api_key or not self.secret_key:
            raise RuntimeError("alpaca_data_credentials_missing")

        from alpaca.data.historical import StockHistoricalDataClient

        self.client = StockHistoricalDataClient(self.api_key, self.secret_key)

    def download_daily(self, symbols: list[str], min_days: int = 252) -> dict[str, pd.DataFrame]:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        start = datetime.now(timezone.utc) - timedelta(days=self.years * 365)
        feed = DataFeed.IEX if self.feed == "iex" else DataFeed.SIP

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=start,
            # Split- and dividend-adjusted, matching the previous Adj_Close usage.
            adjustment=Adjustment.ALL,
            feed=feed,
        )
        bars = self.client.get_stock_bars(request)
        raw = bars.df  # MultiIndex (symbol, timestamp)

        data: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            if raw.empty or symbol not in raw.index.get_level_values("symbol"):
                continue
            df = raw.xs(symbol, level="symbol").copy()
            # Use the actual US trading date as a tz-naive DatetimeIndex.
            df.index = pd.DatetimeIndex(
                df.index.tz_convert("America/New_York").normalize().tz_localize(None)
            )
            df = df.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
            )
            # Bars are already adjusted; the latest bar's adjusted close equals the
            # raw last price, so order pricing stays accurate.
            df["Adj_Close"] = df["Close"]
            df = df[["Open", "High", "Low", "Close", "Adj_Close", "Volume"]]
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
