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

CREATE_ATTACHMENTS = """
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    meeting_id TEXT,              -- NULL = déposée mais pas encore rattachée à une réunion (zone d'attente)
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    label TEXT,
    size INTEGER,
    created_at TEXT NOT NULL,
    included INTEGER NOT NULL DEFAULT 1,
    snippet TEXT,
    extract TEXT
);
CREATE INDEX IF NOT EXISTS idx_att_meeting ON attachments(meeting_id);
"""

JSON_FIELDS = {"analysis"}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _lock, _conn() as c:
        c.executescript(SCHEMA)
        c.executescript(CREATE_ATTACHMENTS)
        cols = {r[1] for r in c.execute("PRAGMA table_info(meetings)")}
        for col in ("analyzed_atts", "analyzed_at"):          # migration des bases existantes
            if col not in cols:
                c.execute(f"ALTER TABLE meetings ADD COLUMN {col} TEXT")


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


# ------------------------------------------------------------------ pièces jointes
def _att(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    d["extract"] = json.loads(d["extract"]) if d.get("extract") else {}
    d["included"] = bool(d["included"])
    return d


def att_create(**fields: Any) -> dict[str, Any]:
    aid = uuid.uuid4().hex[:12]
    data = {"id": aid, "created_at": datetime.now().isoformat(timespec="seconds"), **fields}
    if "extract" in data:
        data["extract"] = json.dumps(data["extract"], ensure_ascii=False)
    with _lock, _conn() as c:
        c.execute(f"INSERT INTO attachments ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})", list(data.values()))
    return att_get(aid)  # type: ignore[return-value]


def att_get(aid: str) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        return _att(c.execute("SELECT * FROM attachments WHERE id=?", (aid,)).fetchone())


def att_list(meeting_id: str) -> list[dict[str, Any]]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM attachments WHERE meeting_id=? ORDER BY created_at, rowid", (meeting_id,)).fetchall()
    return [_att(r) for r in rows]  # type: ignore[misc]


def att_count(meeting_id: str | None) -> int:
    with _lock, _conn() as c:
        if meeting_id is None:
            return c.execute("SELECT COUNT(*) FROM attachments WHERE meeting_id IS NULL").fetchone()[0]
        return c.execute("SELECT COUNT(*) FROM attachments WHERE meeting_id=?", (meeting_id,)).fetchone()[0]


def att_update(aid: str, **fields: Any) -> None:
    if "included" in fields:
        fields["included"] = 1 if fields["included"] else 0
    if "extract" in fields:
        fields["extract"] = json.dumps(fields["extract"], ensure_ascii=False)
    sets = ", ".join(f"{k}=?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE attachments SET {sets} WHERE id=?", [*fields.values(), aid])


def att_delete(aid: str) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM attachments WHERE id=?", (aid,))


def att_link(ids: list[str], meeting_id: str) -> list[str]:
    """Rattache à la réunion les pièces déposées en attente. Retourne celles réellement rattachées (ids inconnus/déjà pris ignorés)."""
    linked = []
    with _lock, _conn() as c:
        for aid in ids:
            cur = c.execute("UPDATE attachments SET meeting_id=? WHERE id=? AND meeting_id IS NULL", (meeting_id, aid))
            if cur.rowcount:
                linked.append(aid)
    return linked


def att_stale_staging(hours: int = 24) -> list[str]:
    """Pièces déposées mais jamais rattachées depuis plus de `hours` heures (à purger)."""
    limit = datetime.fromtimestamp(datetime.now().timestamp() - hours * 3600).isoformat(timespec="seconds")
    with _lock, _conn() as c:
        return [r[0] for r in c.execute("SELECT id FROM attachments WHERE meeting_id IS NULL AND created_at < ?", (limit,)).fetchall()]
