from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RebalancePlan:
    current_positions: list[str]
    target_positions: list[str]
    positions_to_sell: list[str]
    positions_to_buy: list[str]


def build_rebalance_plan(current_positions: list[str], target_positions: list[str]) -> RebalancePlan:
    current = list(dict.fromkeys(current_positions))
    target = list(dict.fromkeys(target_positions))
    positions_to_sell = [symbol for symbol in current if symbol not in target]
    positions_to_buy = [symbol for symbol in target if symbol not in current]
    return RebalancePlan(
        current_positions=current,
        target_positions=target,
        positions_to_sell=positions_to_sell,
        positions_to_buy=positions_to_buy,
    )
