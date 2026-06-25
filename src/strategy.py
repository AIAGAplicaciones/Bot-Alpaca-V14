from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .config import BotConfig

EPSILON = 1e-9


@dataclass(frozen=True)
class RebalanceAction:
    symbol: str
    side: str  # "buy" | "sell"
    value_eur: float


@dataclass(frozen=True)
class RebalanceDecision:
    strategy_name: str
    rebalance_needed: bool
    reason: str
    total_value: float
    values: dict[str, float]
    weights: dict[str, float]
    target_weights: dict[str, float]
    actions: list[RebalanceAction] = field(default_factory=list)

    def to_log(self) -> dict:
        payload = {
            "strategy_name": self.strategy_name,
            "total_value": round(self.total_value, 4),
            "rebalance_needed": self.rebalance_needed,
            "reason": self.reason,
            "orders_planned": [asdict(a) for a in self.actions],
        }
        for symbol in self.target_weights:
            payload[f"{symbol.lower()}_value"] = round(self.values.get(symbol, 0.0), 4)
            payload[f"{symbol.lower()}_weight"] = round(self.weights.get(symbol, 0.0), 6)
            payload[f"target_{symbol.lower()}_weight"] = self.target_weights[symbol]
        return payload


class ThresholdRebalanceStrategy:
    """Fixed-allocation rebalancer.

    Holds the target weights (e.g. 50% SPY / 50% QQQ) and only trades when a
    position drifts outside the allowed band (target +/- threshold). No
    momentum, no SMA, no ranking — deliberately simple.

    All values are in a single currency (the caller decides which); the
    rebalance/no-trade decision depends only on weights, which are
    currency-invariant.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.name = str(config.raw.get("strategy", {}).get("name", "threshold_rebalance"))
        self.weights = config.target_weights
        self.threshold = config.rebalance_threshold
        self.min_trade = config.min_trade_value_eur
        self.total_target = config.total_target_exposure_eur

    def decide(self, position_values: dict[str, float]) -> RebalanceDecision:
        symbols = list(self.weights)
        values = {s: float(position_values.get(s, 0.0)) for s in symbols}
        total = sum(values.values())

        # ---- Empty portfolio: create the initial 50/50 allocation ----
        if total <= EPSILON:
            actions = [
                RebalanceAction(s, "buy", self.total_target * self.weights[s])
                for s in symbols
            ]
            weights = {s: self.weights[s] for s in symbols}
            return RebalanceDecision(
                strategy_name=self.name,
                rebalance_needed=True,
                reason="initial_allocation",
                total_value=0.0,
                values=values,
                weights=weights,
                target_weights=self.weights,
                actions=actions,
            )

        weights = {s: values[s] / total for s in symbols}
        out_of_band = any(abs(weights[s] - self.weights[s]) > self.threshold for s in symbols)

        if not out_of_band:
            return RebalanceDecision(
                strategy_name=self.name,
                rebalance_needed=False,
                reason="within_band",
                total_value=total,
                values=values,
                weights=weights,
                target_weights=self.weights,
                actions=[],
            )

        targets = {s: total * self.weights[s] for s in symbols}
        deltas = {s: targets[s] - values[s] for s in symbols}
        trade_size = max((abs(d) for d in deltas.values()), default=0.0)

        if trade_size < self.min_trade:
            return RebalanceDecision(
                strategy_name=self.name,
                rebalance_needed=False,
                reason="below_min_trade_value",
                total_value=total,
                values=values,
                weights=weights,
                target_weights=self.weights,
                actions=[],
            )

        actions: list[RebalanceAction] = []
        for s in symbols:
            d = deltas[s]
            if d > EPSILON:
                actions.append(RebalanceAction(s, "buy", d))
            elif d < -EPSILON:
                actions.append(RebalanceAction(s, "sell", -d))

        return RebalanceDecision(
            strategy_name=self.name,
            rebalance_needed=True,
            reason="out_of_band",
            total_value=total,
            values=values,
            weights=weights,
            target_weights=self.weights,
            actions=actions,
        )
