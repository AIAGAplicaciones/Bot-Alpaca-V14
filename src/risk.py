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

    def validate_current_positions(self, current_symbols: Iterable[str]) -> RiskCheck:
        allowed = set(self.config.symbols)
        unexpected = sorted(set(current_symbols) - allowed)
        if unexpected:
            return RiskCheck(False, f"unexpected_position:{unexpected}")
        return RiskCheck(True)

    def validate_exposure(self, projected_total_eur: float) -> RiskCheck:
        # Small tolerance so float rounding does not trip the limit.
        if projected_total_eur > self.config.max_total_exposure_eur * 1.0001:
            return RiskCheck(False, "max_exposure_reached")
        return RiskCheck(True)

    def can_trade(self, broker_is_paper: bool) -> RiskCheck:
        """Decide whether and where orders may be sent.

        - mode=paper -> trade ONLY against an Alpaca paper account (fake money).
          If the account is live, refuse (avoids real money in "paper" mode).
        - mode=real  -> trade only if real_trading_enabled. Real money only when
          the account is live (ALPACA_PAPER=false); otherwise it is Alpaca paper.
        """
        if self.config.mode == "paper":
            if not broker_is_paper:
                return RiskCheck(False, "paper_mode_requires_paper_account")
            return RiskCheck(True, "alpaca_paper")
        if self.config.mode == "real":
            if not self.config.real_trading_enabled:
                return RiskCheck(False, "real_trading_disabled")
            return RiskCheck(True, "alpaca_paper" if broker_is_paper else "live")
        return RiskCheck(False, "unknown_mode")

    def evaluate_kill_switch(
        self,
        *,
        data_missing: bool = False,
        price_stale: bool = False,
        broker_unreachable: bool = False,
        unexpected_positions: bool = False,
        order_error_count: int = 0,
        prev_total_eur: float | None = None,
        current_total_eur: float | None = None,
        week_total_eur: float | None = None,
    ) -> RiskCheck:
        ks = self.config.kill_switch
        if not ks.get("enabled", False):
            return RiskCheck(True, "kill_switch_disabled")

        if ks.get("stop_if_data_missing", True) and data_missing:
            return RiskCheck(False, "kill_switch:data_missing")
        if ks.get("stop_if_price_stale", True) and price_stale:
            return RiskCheck(False, "kill_switch:price_stale")
        if ks.get("stop_if_broker_unreachable", True) and broker_unreachable:
            return RiskCheck(False, "kill_switch:broker_unreachable")
        if ks.get("stop_if_unexpected_position", True) and unexpected_positions:
            return RiskCheck(False, "kill_switch:unexpected_position")

        max_errors = ks.get("max_order_error_count")
        if max_errors is not None and order_error_count >= max_errors:
            return RiskCheck(False, "kill_switch:order_error_count")

        max_daily = ks.get("max_daily_loss_eur")
        if (
            max_daily is not None
            and prev_total_eur is not None
            and current_total_eur is not None
            and (prev_total_eur - current_total_eur) > max_daily
        ):
            return RiskCheck(False, "kill_switch:max_daily_loss")

        max_weekly = ks.get("max_weekly_loss_eur")
        if (
            max_weekly is not None
            and week_total_eur is not None
            and current_total_eur is not None
            and (week_total_eur - current_total_eur) > max_weekly
        ):
            return RiskCheck(False, "kill_switch:max_weekly_loss")

        return RiskCheck(True)
