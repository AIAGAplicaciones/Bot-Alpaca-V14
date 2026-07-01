from __future__ import annotations

import json
import os
import ssl
import time
from typing import Any, Optional
from urllib.parse import urlparse


class NullStore:
    """Used when no DATABASE_URL is set or the DB is unreachable.

    The bot stays fully functional; persistence falls back to the JSONL logs.
    """

    enabled = False

    def init_schema(self) -> None:
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


SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS bot_runs (
        id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        mode TEXT, strategy_name TEXT, status TEXT, detail JSONB )""",
    """CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        mode TEXT, strategy_name TEXT, total_value DOUBLE PRECISION,
        rebalance_needed BOOLEAN, reason TEXT, detail JSONB )""",
    """CREATE TABLE IF NOT EXISTS bot_orders (
        id SERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        symbol TEXT, side TEXT, qty DOUBLE PRECISION, limit_price DOUBLE PRECISION,
        status TEXT, broker_order_id TEXT, reason TEXT, detail JSONB )""",
    """CREATE TABLE IF NOT EXISTS known_positions (
        symbol TEXT PRIMARY KEY, qty DOUBLE PRECISION,
        market_value DOUBLE PRECISION, updated_at TIMESTAMPTZ NOT NULL DEFAULT now() )""",
    """CREATE TABLE IF NOT EXISTS state_kv (
        key TEXT PRIMARY KEY, value JSONB, updated_at TIMESTAMPTZ NOT NULL DEFAULT now() )""",
]


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _connect(dsn: str):
    """Connect with pg8000 (pure Python — no libpq needed).

    Tries with/without SSL (Railway internal is usually plain, public needs SSL)
    and retries a couple of times so cold-start private networking has a moment
    to come up.
    """
    import pg8000.dbapi

    u = urlparse(dsn)
    base = dict(
        user=u.username or "postgres",
        password=u.password or "",
        host=u.hostname or "localhost",
        port=u.port or 5432,
        database=(u.path or "").lstrip("/") or "railway",
    )
    internal = "railway.internal" in (u.hostname or "")
    ssl_order = [None, _ssl_context()] if internal else [_ssl_context(), None]

    last: Exception | None = None
    for attempt in range(3):
        for ctx in ssl_order:
            try:
                conn = pg8000.dbapi.connect(ssl_context=ctx, **base)
                return conn
            except Exception as exc:  # noqa: BLE001
                last = exc
        time.sleep(2)
    raise last if last else RuntimeError("db_connect_failed")


class PostgresStore:
    enabled = True

    def __init__(self, dsn: str):
        self.conn = _connect(dsn)

    def _write(self, sql: str, params: tuple, returning: bool = False):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone() if returning else None
        self.conn.commit()
        cur.close()
        return row

    def init_schema(self) -> None:
        cur = self.conn.cursor()
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
        self.conn.commit()
        cur.close()

    def record_run(self, payload: dict[str, Any]) -> Optional[int]:
        row = self._write(
            "INSERT INTO bot_runs (mode, strategy_name, status, detail) "
            "VALUES (%s, %s, %s, %s::jsonb) RETURNING id",
            (payload.get("mode"), payload.get("strategy_name"),
             payload.get("status"), json.dumps(payload, default=str)),
            returning=True,
        )
        return int(row[0]) if row else None

    def save_snapshot(self, payload: dict[str, Any]) -> None:
        self._write(
            "INSERT INTO portfolio_snapshots "
            "(mode, strategy_name, total_value, rebalance_needed, reason, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
            (payload.get("mode"), payload.get("strategy_name"),
             payload.get("total_value"), payload.get("rebalance_needed"),
             payload.get("reason"), json.dumps(payload, default=str)),
        )

    def save_order(self, payload: dict[str, Any]) -> None:
        self._write(
            "INSERT INTO bot_orders "
            "(symbol, side, qty, limit_price, status, broker_order_id, reason, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (payload.get("symbol"), payload.get("side"), payload.get("qty"),
             payload.get("limit_price"), payload.get("status"),
             payload.get("broker_order_id"), payload.get("reason"),
             json.dumps(payload, default=str)),
        )

    def upsert_known_positions(self, positions: list[dict[str, Any]]) -> None:
        for p in positions:
            self._write(
                "INSERT INTO known_positions (symbol, qty, market_value, updated_at) "
                "VALUES (%s, %s, %s, now()) "
                "ON CONFLICT (symbol) DO UPDATE SET "
                "qty = EXCLUDED.qty, market_value = EXCLUDED.market_value, updated_at = now()",
                (p.get("symbol"), p.get("qty"), p.get("market_value")),
            )

    def get_last_snapshot(self) -> Optional[dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT total_value, created_at FROM portfolio_snapshots "
                    "ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return {"total_value": row[0], "created_at": row[1]}

    def set_state(self, key: str, value: Any) -> None:
        self._write(
            "INSERT INTO state_kv (key, value, updated_at) VALUES (%s, %s::jsonb, now()) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (key, json.dumps(value, default=str)),
        )

    def get_state(self, key: str) -> Optional[Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM state_kv WHERE key = %s", (key,))
        row = cur.fetchone()
        cur.close()
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
    except Exception as exc:  # noqa: BLE001
        print(f"[db] PostgreSQL NO disponible -> usando solo logs JSONL. Motivo: {exc!r}")
        return NullStore()
