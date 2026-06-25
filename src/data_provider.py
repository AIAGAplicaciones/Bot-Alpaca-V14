from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv


@dataclass(frozen=True)
class PriceQuote:
    symbol: str
    price: float
    as_of: datetime


class PriceError(RuntimeError):
    """Raised when prices are missing, zero/negative, or stale."""


class AlpacaDataProvider:
    """Latest daily prices for the rebalancer.

    Uses Alpaca's market data API (the deploy host is blocked by Yahoo, so we
    do not use yfinance in production). The backtest, run locally, still uses
    yfinance separately.
    """

    def __init__(self, max_stale_days: int = 5):
        load_dotenv()
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.feed = os.getenv("ALPACA_DATA_FEED", "iex").lower()
        self.max_stale_days = max_stale_days

        if not self.api_key or not self.secret_key:
            raise PriceError("alpaca_data_credentials_missing")

        from alpaca.data.historical import StockHistoricalDataClient

        self.client = StockHistoricalDataClient(self.api_key, self.secret_key)

    def get_latest_prices(self, symbols: list[str]) -> dict[str, float]:
        """Return {symbol: last_close_usd}. Raises PriceError on any problem."""
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        start = datetime.now(timezone.utc) - timedelta(days=10)
        feed = DataFeed.IEX if self.feed == "iex" else DataFeed.SIP
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=start,
            feed=feed,
        )
        bars = self.client.get_stock_bars(request)
        df = bars.df

        prices: dict[str, float] = {}
        now = datetime.now(timezone.utc)
        for symbol in symbols:
            if df.empty or symbol not in df.index.get_level_values("symbol"):
                raise PriceError(f"missing_price:{symbol}")
            sub = df.xs(symbol, level="symbol")
            last_ts = sub.index[-1].to_pydatetime()
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            price = float(sub["close"].iloc[-1])
            if price <= 0:
                raise PriceError(f"invalid_price:{symbol}:{price}")
            if (now - last_ts).days > self.max_stale_days:
                raise PriceError(f"stale_price:{symbol}:{last_ts.date()}")
            prices[symbol] = price
        return prices
