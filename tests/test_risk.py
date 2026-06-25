from __future__ import annotations

from src.config import BotConfig
from src.risk import RiskManager


def make_config(mode: str = "paper", real: bool = False) -> BotConfig:
    return BotConfig(raw={
        "bot": {"mode": mode, "real_trading_enabled": real},
        "strategy": {"name": "spy_qqq_threshold_rebalance"},
        "portfolio": {"target_weights": {"SPY": 0.50, "QQQ": 0.50}},
        "capital": {"total_target_exposure_eur": 400, "allow_fractional_shares": True,
                    "fallback_fx_rate": 1.08},
        "rebalance": {"threshold_absolute_weight": 0.05, "min_trade_value_eur": 10},
        "orders": {"buy_limit_buffer": 0.002, "sell_limit_buffer": 0.002},
        "risk": {"max_total_exposure_eur": 400, "max_symbols": ["SPY", "QQQ"]},
        "kill_switch": {
            "enabled": True,
            "stop_if_data_missing": True,
            "stop_if_broker_unreachable": True,
            "stop_if_unexpected_position": True,
            "max_daily_loss_eur": 20,
            "max_order_error_count": 1,
        },
        "logging": {"directory": "logs"},
    })


def test_rejects_unexpected_position():
    risk = RiskManager(make_config())
    assert not risk.validate_current_positions(["SPY", "BTC"]).ok


def test_accepts_expected_positions():
    risk = RiskManager(make_config())
    assert risk.validate_current_positions(["SPY", "QQQ"]).ok


def test_exposure_limit():
    risk = RiskManager(make_config())
    assert risk.validate_exposure(400).ok
    assert not risk.validate_exposure(500).ok


def test_paper_mode_trades_on_paper_account():
    risk = RiskManager(make_config(mode="paper"))
    assert risk.can_trade(broker_is_paper=True).ok


def test_paper_mode_refuses_live_account():
    risk = RiskManager(make_config(mode="paper"))
    result = risk.can_trade(broker_is_paper=False)
    assert not result.ok
    assert result.reason == "paper_mode_requires_paper_account"


def test_real_mode_blocked_without_flag():
    risk = RiskManager(make_config(mode="real", real=False))
    assert not risk.can_trade(broker_is_paper=False).ok


def test_real_mode_live_when_enabled_and_not_paper():
    risk = RiskManager(make_config(mode="real", real=True))
    result = risk.can_trade(broker_is_paper=False)
    assert result.ok
    assert result.reason == "live"


def test_kill_switch_data_missing():
    risk = RiskManager(make_config())
    assert not risk.evaluate_kill_switch(data_missing=True).ok


def test_kill_switch_unexpected_position():
    risk = RiskManager(make_config())
    assert not risk.evaluate_kill_switch(unexpected_positions=True).ok


def test_kill_switch_daily_loss():
    risk = RiskManager(make_config())
    # Lost 30 EUR vs limit of 20 -> halt.
    assert not risk.evaluate_kill_switch(prev_total_eur=400, current_total_eur=370).ok


def test_kill_switch_passes_when_quiet():
    risk = RiskManager(make_config())
    assert risk.evaluate_kill_switch(prev_total_eur=400, current_total_eur=395).ok
