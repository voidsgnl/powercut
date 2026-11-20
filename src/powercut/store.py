"""Outage log, stored in SQLite (stdlib, transactional, power-cut safe)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .util import iso, parse_iso

# Power dropped while we were watching (battery / UPS event).
KIND_AC_LOSS = "ac_loss"
# Daemon vanished without a clean exit; start time is the last heartbeat.
KIND_UNCLEAN = "unclean_shutdown"

SCHEMA = """
CREATE TABLE IF NOT EXISTS outages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT
);
"""


@dataclass(frozen=True)
class Outage:
    id: int
    kind: str
    started_at: datetime
    ended_at: Optional[datetime]

    @property
    def duration_seconds(self) -> Optional[int]:
        if self.ended_at is None:
            return None
        return int((self.ended_at - self.started_at).total_seconds())


class OutageLog:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        self._db.close()

    def start(self, kind: str, at: datetime) -> int:
        with self._db:
            cur = self._db.execute(
                "INSERT INTO outages (kind, started_at) VALUES (?, ?)",
                (kind, iso(at)),
            )
        return int(cur.lastrowid)

    def record(self, kind: str, started: datetime, ended: datetime) -> int:
        with self._db:
            cur = self._db.execute(
                "INSERT INTO outages (kind, started_at, ended_at) VALUES (?, ?, ?)",
                (kind, iso(started), iso(ended)),
            )
        return int(cur.lastrowid)

    def has_open(self) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM outages WHERE ended_at IS NULL LIMIT 1"
        ).fetchone()
        return row is not None

    def end_open(self, at: datetime) -> int:
        """Close every open outage. Returns how many were closed."""
        with self._db:
            cur = self._db.execute(
                "UPDATE outages SET ended_at = ? WHERE ended_at IS NULL", (iso(at),)
            )
        return cur.rowcount

    def recent(self, limit: int = 20) -> List[Outage]:
        rows = self._db.execute(
            "SELECT id, kind, started_at, ended_at FROM outages "
            "ORDER BY started_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            Outage(
                id=r[0],
                kind=r[1],
                started_at=parse_iso(r[2]),
                ended_at=parse_iso(r[3]) if r[3] else None,
            )
            for r in rows
        ]
