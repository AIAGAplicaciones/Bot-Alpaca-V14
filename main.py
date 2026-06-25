from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.broker_alpaca import AlpacaBroker, calculate_quantity, get_eurusd_rate
from src.config import load_config
from src.data_provider import AlpacaDataProvider, PriceError
from src.db import get_store
from src.logger import JsonlLogger
from src.risk import RiskManager
from src.strategy import ThresholdRebalanceStrategy


def run(dry_run: bool = False, force: bool = False) -> None:
    config = load_config(Path(__file__).with_name("config.yaml"))
    logger = JsonlLogger(Path(__file__).parent / config.log_dir)
    store = get_store(os.getenv("DATABASE_URL"))
    strategy = ThresholdRebalanceStrategy(config)
    risk = RiskManager(config)
    broker = AlpacaBroker(config)

    fx = get_eurusd_rate(config)
    base = {"mode": config.mode, "strategy_name": strategy.name}
    store.record_run({**base, "status": "started", "force": force, "dry_run": dry_run})

    try:
        # 1-4. Prices for SPY and QQQ (USD). Raises on missing/zero/stale.
        try:
            prices = AlpacaDataProvider().get_latest_prices(config.symbols)
            data_missing = False
        except PriceError as exc:
            prices = {}
            data_missing = True
            logger.error({"event": "price_error", "message": str(exc)})

        # 5. Current positions (Alpaca is the source of truth).
        broker_unreachable = False
        positions = []
        try:
            positions = broker.get_current_positions()
        except Exception as exc:  # noqa: BLE001 - broker reachability check
            broker_unreachable = True
            logger.error({"event": "broker_unreachable", "message": str(exc)})

        position_symbols = [p.symbol for p in positions]
        unexpected = sorted(set(position_symbols) - set(config.symbols))

        # Kill switch (loss limits use the previous persisted snapshot if any).
        prev = store.get_last_snapshot()
        prev_total = float(prev["total_value"]) if prev and prev.get("total_value") else None
        ks = risk.evaluate_kill_switch(
            data_missing=data_missing,
            price_stale=data_missing,
            broker_unreachable=broker_unreachable,
            unexpected_positions=bool(unexpected),
            prev_total_eur=prev_total,
        )
        if not ks.ok:
            logger.error({"event": "kill_switch", "reason": ks.reason, "unexpected": unexpected})
            store.record_run({**base, "status": "halted", "reason": ks.reason})
            print(f"Kill switch activado: {ks.reason}")
            return

        # 6. Weights from current market values, converted USD -> EUR.
        values_eur = {p.symbol: p.market_value / fx for p in positions if p.symbol in config.symbols}
        store.upsert_known_positions(
            [{"symbol": p.symbol, "qty": p.qty, "market_value": p.market_value} for p in positions]
        )

        # 7. Decide.
        decision = strategy.decide(values_eur)
        decision_log = {**base, **decision.to_log(), "fx_eurusd": fx}
        logger.portfolio(decision_log)
        store.save_snapshot({**base, **decision.to_log()})
        current_total = decision.total_value if values_eur else prev_total
        if current_total is not None:
            store.set_state("last_total_value_eur", current_total)

        print(f"Estrategia: {strategy.name} | {decision.reason}")
        for symbol in config.symbols:
            print(f"  {symbol}: {decision.weights.get(symbol, 0.0):.1%} "
                  f"(objetivo {decision.target_weights[symbol]:.0%})")

        if not decision.rebalance_needed:
            logger.portfolio({**base, "event": "no_action", "reason": decision.reason})
            print(f"Sin acción: {decision.reason}")
            store.record_run({**base, "status": "no_action", "reason": decision.reason})
            return

        print("Órdenes planificadas:", [(a.symbol, a.side, round(a.value_eur, 2)) for a in decision.actions])

        # Exposure check (matters for the initial allocation).
        projected = decision.total_value if decision.reason != "initial_allocation" else config.total_target_exposure_eur
        exp = risk.validate_exposure(projected)
        if not exp.ok:
            logger.rejected({**base, "reason": exp.reason, "projected_eur": projected})
            print(f"Bloqueado por exposición: {exp.reason}")
            store.record_run({**base, "status": "blocked", "reason": exp.reason})
            return

        # Paper / dry-run: compute and log only, never submit.
        real = risk.can_send_real_orders()
        if dry_run or not real.ok:
            reason = "dry_run" if dry_run else real.reason
            logger.portfolio({**base, "event": "no_real_orders", "reason": reason})
            print(f"Modo paper/dry-run: no se envían órdenes reales ({reason}).")
            store.record_run({**base, "status": "simulated", "reason": reason})
            return

        # Real path (mode=real AND real_trading_enabled). Sells first, then buys.
        open_order_symbols = broker.get_open_order_symbols() if config.prevent_duplicate_orders else set()
        order_error_count = 0
        executed = 0
        sells = [a for a in decision.actions if a.side == "sell"]
        buys = [a for a in decision.actions if a.side == "buy"]

        for action in sells + buys:
            if executed >= config.max_orders_per_run:
                logger.rejected({**base, "symbol": action.symbol, "reason": "max_orders_per_run"})
                break
            if action.symbol in open_order_symbols:
                logger.order({**base, "symbol": action.symbol, "side": action.side,
                              "status": "blocked_duplicate_order"})
                continue
            if action.value_eur < config.min_trade_value_eur:
                logger.rejected({**base, "symbol": action.symbol, "reason": "below_min_trade_value"})
                continue
            price = prices[action.symbol]
            qty = calculate_quantity(action.value_eur, price, config)
            if qty <= 0:
                logger.order({**base, "symbol": action.symbol, "side": action.side,
                              "status": "blocked_zero_qty"})
                continue
            buffer = config.buy_limit_buffer if action.side == "buy" else -config.sell_limit_buffer
            limit_price = price * (1 + buffer)
            try:
                order = broker.submit_limit_order(action.symbol, action.side, qty, limit_price)
                payload = {**base, "symbol": action.symbol, "side": action.side, "qty": qty,
                           "limit_price": round(limit_price, 2), "status": str(order.status),
                           "broker_order_id": str(getattr(order, "id", ""))}
                logger.order(payload)
                store.save_order(payload)
                executed += 1
            except Exception as exc:  # noqa: BLE001
                order_error_count += 1
                logger.error({**base, "event": "order_error", "symbol": action.symbol, "message": str(exc)})
                ks2 = risk.evaluate_kill_switch(order_error_count=order_error_count)
                if not ks2.ok:
                    logger.error({**base, "event": "kill_switch", "reason": ks2.reason})
                    print(f"Kill switch por errores de orden: {ks2.reason}")
                    break

        store.record_run({**base, "status": "executed", "orders_executed": executed})
        print(f"Órdenes ejecutadas: {executed}")

    except Exception as exc:
        logger.error({"event": "fatal_error", "message": str(exc)})
        store.record_run({**base, "status": "fatal_error", "message": str(exc)})
        raise
    finally:
        store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Calcula y registra sin enviar órdenes.")
    parser.add_argument("--force", action="store_true", help="Reservado para pruebas manuales.")
    args = parser.parse_args()
    run(dry_run=args.dry_run, force=args.force)
