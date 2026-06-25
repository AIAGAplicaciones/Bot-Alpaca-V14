from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BotConfig:
    raw: dict[str, Any]

    # ---- bot ----
    @property
    def name(self) -> str:
        return str(self.raw.get("bot", {}).get("name", "bot"))

    @property
    def mode(self) -> str:
        return str(self.raw["bot"]["mode"])

    @property
    def real_trading_enabled(self) -> bool:
        return bool(self.raw["bot"].get("real_trading_enabled", False))

    # ---- portfolio ----
    @property
    def target_weights(self) -> dict[str, float]:
        weights = self.raw["portfolio"]["target_weights"]
        return {str(k): float(v) for k, v in weights.items()}

    @property
    def symbols(self) -> list[str]:
        return list(self.target_weights.keys())

    # ---- capital ----
    @property
    def total_target_exposure_eur(self) -> float:
        return float(self.raw["capital"]["total_target_exposure_eur"])

    @property
    def allow_fractional_shares(self) -> bool:
        return bool(self.raw["capital"].get("allow_fractional_shares", True))

    @property
    def fallback_fx_rate(self) -> float:
        return float(self.raw["capital"].get("fallback_fx_rate", 1.08))

    # ---- rebalance ----
    @property
    def rebalance_threshold(self) -> float:
        return float(self.raw["rebalance"]["threshold_absolute_weight"])

    @property
    def min_trade_value_eur(self) -> float:
        return float(self.raw["rebalance"].get("min_trade_value_eur", 0.0))

    @property
    def check_frequency(self) -> str:
        return str(self.raw["rebalance"].get("check_frequency", "monthly"))

    # ---- orders ----
    @property
    def buy_limit_buffer(self) -> float:
        return float(self.raw["orders"]["buy_limit_buffer"])

    @property
    def sell_limit_buffer(self) -> float:
        return float(self.raw["orders"]["sell_limit_buffer"])

    @property
    def cancel_unfilled_end_of_day(self) -> bool:
        return bool(self.raw["orders"].get("cancel_unfilled_end_of_day", True))

    @property
    def prevent_duplicate_orders(self) -> bool:
        return bool(self.raw["orders"].get("prevent_duplicate_orders", True))

    # ---- risk ----
    @property
    def max_total_exposure_eur(self) -> float:
        return float(self.raw["risk"]["max_total_exposure_eur"])

    @property
    def max_orders_per_run(self) -> int:
        return int(self.raw["risk"].get("max_orders_per_run", 4))

    # ---- kill switch ----
    @property
    def kill_switch(self) -> dict[str, Any]:
        return dict(self.raw.get("kill_switch", {}))

    # ---- logging ----
    @property
    def log_dir(self) -> Path:
        return Path(str(self.raw.get("logging", {}).get("directory", "logs")))


def load_config(path: str | Path = "config.yaml") -> BotConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return BotConfig(raw=raw)
