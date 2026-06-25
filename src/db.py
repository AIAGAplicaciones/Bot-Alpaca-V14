from __future__ import annotations

import json
import os
from typing import Any, Optional


class NullStore:
    """Used when no DATABASE_URL is set or psycopg2 is unavailable.

    The bot stays fully functional; persistence simply falls back to the
    JSONL logs. Every method is a safe no-op.
    """

    enabled = False

    def init_schema(self) -> None:  # noqa: D401
        return None

    def record_run(self, payload: dict[str, Any]) -> Optional[int]:
        return None

    def save_snapshot(self, payload: dict[str, Any]) -> None:
        return None

    def save_order(self, payload: dict[str, Any]) -> None:
        return None

    def upsert_known_positions(self, positions: list[dict[str, Any]]) -> None:
        return None

    def get_last_snapshot(self) -> Optional[dict[str, Any]]:
        return None

    def set_state(self, key: str, value: Any) -> None:
        return None

    def get_state(self, key: str) -> Optional[Any]:
        return None

    def close(self) -> None:
        return None


SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_runs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode TEXT,
    strategy_name TEXT,
    status TEXT,
    detail JSONB
);
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode TEXT,
    strategy_name TEXT,
    total_value DOUBLE PRECISION,
    rebalance_needed BOOLEAN,
    reason TEXT,
    detail JSONB
);
CREATE TABLE IF NOT EXISTS bot_orders (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol TEXT,
    side TEXT,
    qty DOUBLE PRECISION,
    limit_price DOUBLE PRECISION,
    status TEXT,
    broker_order_id TEXT,
    reason TEXT,
    detail JSONB
);
CREATE TABLE IF NOT EXISTS known_positions (
    symbol TEXT PRIMARY KEY,
    qty DOUBLE PRECISION,
    market_value DOUBLE PRECISION,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS state_kv (
    key TEXT PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class PostgresStore:
    enabled = True

    def __init__(self, dsn: str):
        import psycopg2  # noqa: F401

        self._psycopg2 = psycopg2
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True

    def init_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(SCHEMA)

    def record_run(self, payload: dict[str, Any]) -> Optional[int]:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bot_runs (mode, strategy_name, status, detail) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (payload.get("mode"), payload.get("strategy_name"),
                 payload.get("status"), json.dumps(payload, default=str)),
            )
            return int(cur.fetchone()[0])

    def save_snapshot(self, payload: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO portfolio_snapshots "
                "(mode, strategy_name, total_value, rebalance_needed, reason, detail) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (payload.get("mode"), payload.get("strategy_name"),
                 payload.get("total_value"), payload.get("rebalance_needed"),
                 payload.get("reason"), json.dumps(payload, default=str)),
            )

    def save_order(self, payload: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bot_orders "
                "(symbol, side, qty, limit_price, status, broker_order_id, reason, detail) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (payload.get("symbol"), payload.get("side"), payload.get("qty"),
                 payload.get("limit_price"), payload.get("status"),
                 payload.get("broker_order_id"), payload.get("reason"),
                 json.dumps(payload, default=str)),
            )

    def upsert_known_positions(self, positions: list[dict[str, Any]]) -> None:
        with self.conn.cursor() as cur:
            for p in positions:
                cur.execute(
                    "INSERT INTO known_positions (symbol, qty, market_value, updated_at) "
                    "VALUES (%s, %s, %s, now()) "
                    "ON CONFLICT (symbol) DO UPDATE SET "
                    "qty = EXCLUDED.qty, market_value = EXCLUDED.market_value, updated_at = now()",
                    (p.get("symbol"), p.get("qty"), p.get("market_value")),
                )

    def get_last_snapshot(self) -> Optional[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT total_value, created_at FROM portfolio_snapshots "
                "ORDER BY created_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"total_value": row[0], "created_at": row[1]}

    def set_state(self, key: str, value: Any) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO state_kv (key, value, updated_at) VALUES (%s, %s, now()) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                (key, json.dumps(value, default=str)),
            )

    def get_state(self, key: str) -> Optional[Any]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT value FROM state_kv WHERE key = %s", (key,))
            row = cur.fetchone()
            return row[0] if row else None

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


def get_store(database_url: str | None = None) -> NullStore | PostgresStore:
    dsn = database_url if database_url is not None else os.getenv("DATABASE_URL")
    if not dsn:
        return NullStore()
    try:
        store = PostgresStore(dsn)
        store.init_schema()
        return store
    except Exception:
        # Connection or driver problem: degrade to JSONL-only logging.
        return NullStore()
