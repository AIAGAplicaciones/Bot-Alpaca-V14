from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd

from .config import BotConfig


@dataclass(frozen=True)
class Signal:
    symbol: str
    close: float
    sma200: float
    return_3m: float
    return_6m: float
    momentum_score: float
    trend_filter: bool
    momentum_filter: bool
    eligible: bool
    rank: int | None = None
    decision: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class MonthlyMomentumStrategy:
    def __init__(self, config: BotConfig):
        self.config = config

    def calculate_signal(self, symbol: str, df: pd.DataFrame) -> Signal:
        adjusted_close = df["Adj_Close"].dropna()
        min_len = max(self.config.sma_period, self.config.return_6m_sessions) + 1
        if len(adjusted_close) < min_len:
            raise ValueError(f"not_enough_data_for_signal:{symbol}")

        close = float(adjusted_close.iloc[-1])
        sma200 = float(adjusted_close.iloc[-self.config.sma_period:].mean())
        close_3m_ago = float(adjusted_close.iloc[-1 - self.config.return_3m_sessions])
        close_6m_ago = float(adjusted_close.iloc[-1 - self.config.return_6m_sessions])

        return_3m = close / close_3m_ago - 1
        return_6m = close / close_6m_ago - 1
        momentum_score = (
            self.config.momentum_6m_weight * return_6m
            + self.config.momentum_3m_weight * return_3m
        )
        trend_filter = close > sma200
        momentum_filter = momentum_score > 0
        eligible = trend_filter and momentum_filter

        if not trend_filter:
            reason = "close_below_or_equal_sma200"
        elif not momentum_filter:
            reason = "momentum_not_positive"
        else:
            reason = "eligible"

        return Signal(
            symbol=symbol,
            close=close,
            sma200=sma200,
            return_3m=return_3m,
            return_6m=return_6m,
            momentum_score=momentum_score,
            trend_filter=trend_filter,
            momentum_filter=momentum_filter,
            eligible=eligible,
            reason=reason,
        )

    def select_targets(self, data: dict[str, pd.DataFrame]) -> tuple[list[str], list[Signal]]:
        signals = [self.calculate_signal(symbol, data[symbol]) for symbol in self.config.symbols]
        eligible = [signal for signal in signals if signal.eligible]
        ranked = sorted(eligible, key=lambda s: s.momentum_score, reverse=True)

        rank_by_symbol = {signal.symbol: idx + 1 for idx, signal in enumerate(ranked)}
        final_signals: list[Signal] = []
        top_symbols = [signal.symbol for signal in ranked[: self.config.max_positions]]

        for signal in signals:
            decision = "buy_or_hold" if signal.symbol in top_symbols else "ignore_or_sell"
            final_signals.append(
                Signal(
                    **{**signal.to_dict(), "rank": rank_by_symbol.get(signal.symbol), "decision": decision}
                )
            )

        if not top_symbols and not self.config.use_cash_defensive:
            return [self.config.defensive_asset], final_signals
        return top_symbols, final_signals
