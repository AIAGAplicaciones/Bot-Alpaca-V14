from __future__ import annotations

import math
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .config import BotConfig


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    qty: float
    market_value: float


class AlpacaBroker:
    def __init__(self, config: BotConfig):
        load_dotenv()
        self.config = config
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"

        if not self.api_key or not self.secret_key:
            self.client = None
            return

        from alpaca.trading.client import TradingClient

        self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)

    def get_current_positions(self) -> list[BrokerPosition]:
        if self.client is None:
            return []
        positions = self.client.get_all_positions()
        return [
            BrokerPosition(
                symbol=p.symbol,
                qty=float(p.qty),
                market_value=float(p.market_value),
            )
            for p in positions
        ]

    def get_open_order_symbols(self) -> set[str]:
        if self.client is None:
            return set()
        orders = self.client.get_orders()
        return {order.symbol for order in orders}

    def submit_limit_order(self, symbol: str, side: str, qty: float, limit_price: float):
        if self.client is None:
            raise RuntimeError("alpaca_client_not_configured")

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
        )
        return self.client.submit_order(order)


def get_eurusd_rate(config: BotConfig) -> float:
    raw = os.getenv("EURUSD_RATE")
    if raw:
        return float(raw)
    return config.fallback_fx_rate


def calculate_quantity(target_value_eur: float, price_usd: float, config: BotConfig) -> float:
    target_value_usd = target_value_eur * get_eurusd_rate(config)
    if price_usd <= 0:
        raise ValueError("invalid_price_for_quantity")
    qty = target_value_usd / price_usd
    if config.allow_fractional_shares:
        return round(qty, 6)
    return float(math.floor(qty))
