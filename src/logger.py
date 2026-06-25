from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonlLogger:
    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _write(self, filename: str, payload: dict[str, Any]) -> None:
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with open(self.log_dir / filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    def signal(self, payload: dict[str, Any]) -> None:
        self._write("signals.jsonl", payload)

    def portfolio(self, payload: dict[str, Any]) -> None:
        self._write("portfolio.jsonl", payload)

    def order(self, payload: dict[str, Any]) -> None:
        self._write("orders.jsonl", payload)

    def error(self, payload: dict[str, Any]) -> None:
        self._write("errors.jsonl", payload)

    def info(self, payload: dict[str, Any]) -> None:
        self._write("info.jsonl", payload)
