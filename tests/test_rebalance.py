from __future__ import annotations

from src.config import BotConfig
from src.risk import RiskManager
from src.strategy import ThresholdRebalanceStrategy


def make_config() -> BotConfig:
    return BotConfig(raw={
        "bot": {"mode": "paper", "real_trading_enabled": False},
        "strategy": {"type": "fixed_allocation_threshold_rebalance",
                     "name": "spy_qqq_threshold_rebalance"},
        "portfolio": {"target_weights": {"SPY": 0.50, "QQQ": 0.50}},
        "capital": {"total_target_exposure_eur": 400, "allow_fractional_shares": True,
                    "fallback_fx_rate": 1.08},
        "rebalance": {"threshold_absolute_weight": 0.05, "min_trade_value_eur": 10,
                      "check_frequency": "monthly"},
        "orders": {"buy_limit_buffer": 0.002, "sell_limit_buffer": 0.002},
        "risk": {"max_total_exposure_eur": 400, "max_symbols": ["SPY", "QQQ"]},
        "kill_switch": {"enabled": True, "stop_if_unexpected_position": True,
                        "max_daily_loss_eur": 20, "max_weekly_loss_eur": 40},
        "logging": {"directory": "logs"},
    })


def actions_by_symbol(decision):
    return {a.symbol: a for a in decision.actions}


def test_1_initial_allocation_when_empty():
    strategy = ThresholdRebalanceStrategy(make_config())
    decision = strategy.decide({})
    assert decision.rebalance_needed
    assert decision.reason == "initial_allocation"
    acts = actions_by_symbol(decision)
    assert acts["SPY"].side == "buy" and abs(acts["SPY"].value_eur - 200) < 1e-6
    assert acts["QQQ"].side == "buy" and abs(acts["QQQ"].value_eur - 200) < 1e-6


def test_2_within_band_no_trade():
    strategy = ThresholdRebalanceStrategy(make_config())
    decision = strategy.decide({"SPY": 210, "QQQ": 190})  # 52.5% / 47.5%
    assert not decision.rebalance_needed
    assert decision.reason == "within_band"
    assert decision.actions == []


def test_3_out_of_band_rebalances():
    strategy = ThresholdRebalanceStrategy(make_config())
    decision = strategy.decide({"SPY": 170, "QQQ": 260})  # 39.5% / 60.5%
    assert decision.rebalance_needed
    assert decision.reason == "out_of_band"
    acts = actions_by_symbol(decision)
    assert acts["QQQ"].side == "sell" and abs(acts["QQQ"].value_eur - 45) < 1e-6
    assert acts["SPY"].side == "buy" and abs(acts["SPY"].value_eur - 45) < 1e-6


def test_4_below_min_trade_value():
    strategy = ThresholdRebalanceStrategy(make_config())
    decision = strategy.decide({"SPY": 20, "QQQ": 30})  # out of band, but trade = 5 EUR
    assert not decision.rebalance_needed
    assert decision.reason == "below_min_trade_value"
    assert decision.actions == []


def test_5_unexpected_symbol_blocks():
    risk = RiskManager(make_config())
    result = risk.validate_current_positions(["SPY", "QQQ", "GLD"])
    assert not result.ok
    assert "unexpected_position" in result.reason


def test_paper_mode_uses_larger_capital():
    raw = make_config().raw
    raw["paper_mode"] = {"total_target_exposure_eur": 10000, "max_total_exposure_eur": 10000,
                         "max_daily_loss_eur": 1000, "max_weekly_loss_eur": 2000}
    # Paper mode -> overrides apply.
    paper = BotConfig(raw={**raw, "bot": {**raw["bot"], "mode": "paper"}})
    assert paper.total_target_exposure_eur == 10000
    assert paper.kill_switch["max_daily_loss_eur"] == 1000
    # Real mode -> base values.
    real = BotConfig(raw={**raw, "bot": {**raw["bot"], "mode": "real"}})
    assert real.total_target_exposure_eur == 400
    assert real.kill_switch["max_daily_loss_eur"] == 20
