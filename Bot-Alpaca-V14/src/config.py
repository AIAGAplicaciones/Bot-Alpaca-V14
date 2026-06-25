from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BotConfig:
    raw: dict[str, Any]

    @property
    def mode(self) -> str:
        return str(self.raw["bot"]["mode"])

    @property
    def real_trading_enabled(self) -> bool:
        return bool(self.raw["bot"].get("real_trading_enabled", False))

    @property
    def symbols(self) -> list[str]:
        return list(self.raw["universe"]["risk_etfs"])

    @property
    def defensive_asset(self) -> str:
        return str(self.raw["universe"].get("defensive_asset", "SHY"))

    @property
    def use_cash_defensive(self) -> bool:
        return bool(self.raw["defensive_mode"].get("use_cash", True))

    @property
    def max_positions(self) -> int:
        return int(self.raw["strategy"]["max_positions"])

    @property
    def capital_per_etf_eur(self) -> float:
        return float(self.raw["capital"]["capital_per_etf_eur"])

    @property
    def max_total_exposure_eur(self) -> float:
        return float(self.raw["capital"]["max_total_exposure_eur"])

    @property
    def allow_fractional_shares(self) -> bool:
        return bool(self.raw["capital"].get("allow_fractional_shares", True))

    @property
    def fallback_fx_rate(self) -> float:
        return float(self.raw["capital"].get("fallback_fx_rate", 1.08))

    @property
    def sma_period(self) -> int:
        return int(self.raw["indicators"]["sma_trend_period"])

    @property
    def return_3m_sessions(self) -> int:
        return int(self.raw["indicators"]["return_3m_sessions"])

    @property
    def return_6m_sessions(self) -> int:
        return int(self.raw["indicators"]["return_6m_sessions"])

    @property
    def momentum_6m_weight(self) -> float:
        return float(self.raw["indicators"]["momentum_formula"]["return_6m_weight"])

    @property
    def momentum_3m_weight(self) -> float:
        return float(self.raw["indicators"]["momentum_formula"]["return_3m_weight"])

    @property
    def buy_limit_buffer(self) -> float:
        return float(self.raw["orders"]["buy_limit_buffer"])

    @property
    def sell_limit_buffer(self) -> float:
        return float(self.raw["orders"]["sell_limit_buffer"])

    @property
    def log_dir(self) -> Path:
        return Path(str(self.raw["logging"].get("directory", "logs")))


def load_config(path: str | Path = "config.yaml") -> BotConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return BotConfig(raw=raw)
