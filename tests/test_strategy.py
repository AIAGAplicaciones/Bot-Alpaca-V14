from __future__ import annotations

import pandas as pd

from src.config import BotConfig
from src.strategy import MonthlyMomentumStrategy


def make_config() -> BotConfig:
    return BotConfig(raw={
        "bot": {"mode": "paper", "real_trading_enabled": False},
        "universe": {"risk_etfs": ["AAA", "BBB", "CCC"], "defensive_asset": "SHY"},
        "defensive_mode": {"use_cash": True},
        "strategy": {"max_positions": 2},
        "capital": {"capital_per_etf_eur": 200, "max_total_exposure_eur": 400, "allow_fractional_shares": True},
        "indicators": {
            "sma_trend_period": 200,
            "return_3m_sessions": 63,
            "return_6m_sessions": 126,
            "momentum_formula": {"return_6m_weight": 0.6, "return_3m_weight": 0.4},
        },
        "orders": {"buy_limit_buffer": 0.002, "sell_limit_buffer": 0.002},
        "logging": {"directory": "logs"},
    })


def make_df(start: float, end: float, periods: int = 260) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=periods)
    values = pd.Series([start + (end - start) * i / (periods - 1) for i in range(periods)], index=idx)
    return pd.DataFrame({
        "Open": values,
        "High": values,
        "Low": values,
        "Close": values,
        "Adj_Close": values,
        "Volume": 1_000_000,
    })


def test_selects_top_two_positive_momentum_above_sma200():
    config = make_config()
    strategy = MonthlyMomentumStrategy(config)
    data = {
        "AAA": make_df(100, 160),
        "BBB": make_df(100, 130),
        "CCC": make_df(100, 110),
    }
    targets, signals = strategy.select_targets(data)
    assert targets == ["AAA", "BBB"]
    assert len(signals) == 3


def test_returns_cash_when_no_symbol_is_eligible():
    config = make_config()
    strategy = MonthlyMomentumStrategy(config)
    data = {
        "AAA": make_df(160, 100),
        "BBB": make_df(130, 100),
        "CCC": make_df(110, 100),
    }
    targets, _ = strategy.select_targets(data)
    assert targets == []
