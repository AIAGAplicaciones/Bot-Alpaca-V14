from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .config import BotConfig


@dataclass(frozen=True)
class RiskCheck:
    ok: bool
    reason: str = "ok"


class RiskManager:
    def __init__(self, config: BotConfig):
        self.config = config

    def validate_targets(self, targets: list[str]) -> RiskCheck:
        if len(targets) > self.config.max_positions:
            return RiskCheck(False, "too_many_target_positions")
        expected_exposure = len(targets) * self.config.capital_per_etf_eur
        if expected_exposure > self.config.max_total_exposure_eur:
            return RiskCheck(False, "target_exposure_exceeds_limit")
        return RiskCheck(True)

    def validate_current_positions(self, current_symbols: Iterable[str]) -> RiskCheck:
        allowed = set(self.config.symbols + [self.config.defensive_asset])
        unexpected = sorted(set(current_symbols) - allowed)
        if unexpected:
            return RiskCheck(False, f"unexpected_position:{unexpected}")
        return RiskCheck(True)

    def can_send_real_orders(self) -> RiskCheck:
        if self.config.mode != "real":
            return RiskCheck(False, "mode_is_not_real")
        if not self.config.real_trading_enabled:
            return RiskCheck(False, "real_trading_disabled")
        return RiskCheck(True)
