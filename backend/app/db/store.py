"""Small SQLite-backed state store for the single-user local MVP."""

import json
import sqlite3
from typing import Any

from app.core.config import DB_PATH


class LocalStateStore:
    def __init__(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )

    @staticmethod
    def _connect() -> sqlite3.Connection:
        connection = sqlite3.connect(DB_PATH, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def get(self, key: str, default: Any = None) -> Any:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO app_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, serialized),
            )


store = LocalStateStore()
