from __future__ import annotations

from src.config import BotConfig
from src.risk import RiskManager


def make_config() -> BotConfig:
    return BotConfig(raw={
        "bot": {"mode": "paper", "real_trading_enabled": False},
        "universe": {"risk_etfs": ["SPY", "QQQ"], "defensive_asset": "SHY"},
        "defensive_mode": {"use_cash": True},
        "strategy": {"max_positions": 2},
        "capital": {"capital_per_etf_eur": 200, "max_total_exposure_eur": 400, "allow_fractional_shares": True},
        "indicators": {"sma_trend_period": 200, "return_3m_sessions": 63, "return_6m_sessions": 126, "momentum_formula": {"return_6m_weight": 0.6, "return_3m_weight": 0.4}},
        "orders": {"buy_limit_buffer": 0.002, "sell_limit_buffer": 0.002},
        "logging": {"directory": "logs"},
    })


def test_rejects_too_many_targets():
    risk = RiskManager(make_config())
    result = risk.validate_targets(["SPY", "QQQ", "SHY"])
    assert not result.ok


def test_rejects_unexpected_position():
    risk = RiskManager(make_config())
    result = risk.validate_current_positions(["SPY", "BTC"])
    assert not result.ok
