from __future__ import annotations

import argparse
from pathlib import Path

from src.broker_alpaca import AlpacaBroker, calculate_quantity
from src.config import load_config
from src.data_provider import YahooDataProvider
from src.logger import JsonlLogger
from src.portfolio import build_rebalance_plan
from src.risk import RiskManager
from src.scheduler import is_last_trading_day_of_month
from src.strategy import MonthlyMomentumStrategy


def run(dry_run: bool = False, force: bool = False) -> None:
    config = load_config(Path(__file__).with_name("config.yaml"))
    logger = JsonlLogger(Path(__file__).parent / config.log_dir)
    data_provider = YahooDataProvider()
    strategy = MonthlyMomentumStrategy(config)
    risk = RiskManager(config)
    broker = AlpacaBroker(config)

    symbols_to_download = config.symbols + ([config.defensive_asset] if not config.use_cash_defensive else [])

    try:
        data = data_provider.download_daily(symbols_to_download, min_days=max(config.sma_period, 252))
        latest_date = next(iter(data.values())).index[-1]

        if not force and not is_last_trading_day_of_month(latest_date):
            logger.info({"event": "not_rebalance_day", "latest_date": str(latest_date)})
            print(f"No es último día bursátil de mes. Última fecha: {latest_date}. Usa --force para probar.")
            return

        targets, signals = strategy.select_targets(data)
        for signal in signals:
            logger.signal(signal.to_dict())

        target_check = risk.validate_targets(targets)
        if not target_check.ok:
            logger.error({"event": "risk_target_failed", "reason": target_check.reason})
            print(f"Risk check failed: {target_check.reason}")
            return

        current_positions = broker.get_current_positions()
        current_symbols = [p.symbol for p in current_positions]
        current_check = risk.validate_current_positions(current_symbols)
        if not current_check.ok:
            logger.error({"event": "risk_current_positions_failed", "reason": current_check.reason})
            print(f"Risk check failed: {current_check.reason}")
            return

        plan = build_rebalance_plan(current_symbols, targets)
        logger.portfolio(plan.__dict__)

        print("Target positions:", plan.target_positions)
        print("Sell:", plan.positions_to_sell)
        print("Buy:", plan.positions_to_buy)

        if dry_run or config.mode == "paper":
            logger.info({"event": "paper_or_dry_run_no_real_orders", "dry_run": dry_run, "mode": config.mode})
            print("Modo paper/dry-run: no se envían órdenes reales.")
            return

        real_check = risk.can_send_real_orders()
        if not real_check.ok:
            logger.error({"event": "real_order_blocked", "reason": real_check.reason})
            print(f"Orden real bloqueada: {real_check.reason}")
            return

        open_order_symbols = broker.get_open_order_symbols()

        for symbol in plan.positions_to_sell:
            if symbol in open_order_symbols:
                logger.order({"symbol": symbol, "side": "sell", "status": "blocked_duplicate_order"})
                continue
            position = next((p for p in current_positions if p.symbol == symbol), None)
            if position is None:
                continue
            last_price = float(data[symbol]["Adj_Close"].iloc[-1])
            limit_price = last_price * (1 - config.sell_limit_buffer)
            order = broker.submit_limit_order(symbol, "sell", abs(position.qty), limit_price)
            logger.order({"symbol": symbol, "side": "sell", "qty": position.qty, "limit_price": limit_price, "status": str(order.status)})

        for symbol in plan.positions_to_buy:
            if symbol in open_order_symbols:
                logger.order({"symbol": symbol, "side": "buy", "status": "blocked_duplicate_order"})
                continue
            last_price = float(data[symbol]["Adj_Close"].iloc[-1])
            qty = calculate_quantity(config.capital_per_etf_eur, last_price, config)
            if qty <= 0:
                logger.order({"symbol": symbol, "side": "buy", "status": "blocked_insufficient_capital"})
                continue
            limit_price = last_price * (1 + config.buy_limit_buffer)
            order = broker.submit_limit_order(symbol, "buy", qty, limit_price)
            logger.order({"symbol": symbol, "side": "buy", "qty": qty, "limit_price": limit_price, "status": str(order.status)})

    except Exception as exc:
        logger.error({"event": "fatal_error", "message": str(exc)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Calcula señales sin enviar órdenes.")
    parser.add_argument("--force", action="store_true", help="Ejecuta aunque no sea último día bursátil de mes.")
    args = parser.parse_args()
    run(dry_run=args.dry_run, force=args.force)
