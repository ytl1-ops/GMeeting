"""Persistance SQLite minimale (une réunion = une ligne)."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any

from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    meeting_date TEXT,
    location TEXT,
    participants TEXT,
    context TEXT,
    language TEXT,
    source_type TEXT,
    source_url TEXT,
    status TEXT NOT NULL,
    progress TEXT,
    error TEXT,
    duration REAL,
    transcript TEXT,
    analysis TEXT
);
"""

JSON_FIELDS = {"analysis"}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _lock, _conn() as c:
        c.executescript(SCHEMA)


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    for f in JSON_FIELDS:
        d[f] = json.loads(d[f]) if d.get(f) else None
    return d


def create(**fields: Any) -> dict[str, Any]:
    mid = uuid.uuid4().hex[:12]
    data = {
        "id": mid,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "pending",
        **fields,
    }
    cols = ", ".join(data)
    qs = ", ".join("?" for _ in data)
    with _lock, _conn() as c:
        c.execute(f"INSERT INTO meetings ({cols}) VALUES ({qs})", list(data.values()))
    return get(data["id"])  # type: ignore[return-value]  (l'appelant peut imposer son propre id)


def update(mid: str, **fields: Any) -> None:
    if not fields:
        return
    for f in JSON_FIELDS & fields.keys():
        fields[f] = json.dumps(fields[f], ensure_ascii=False) if fields[f] is not None else None
    sets = ", ".join(f"{k}=?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE meetings SET {sets} WHERE id=?", [*fields.values(), mid])


def get(mid: str) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        return _row(c.execute("SELECT * FROM meetings WHERE id=?", (mid,)).fetchone())


def list_all() -> list[dict[str, Any]]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT id,title,created_at,meeting_date,source_type,status,progress,error,duration "
            "FROM meetings ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete(mid: str) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM meetings WHERE id=?", (mid,))
