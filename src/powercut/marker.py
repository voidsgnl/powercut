"""Unclean shutdown detection via running.marker.

The daemon writes the marker on start and refreshes it every tick (the
heartbeat). A clean exit removes it. A marker found at start means the last
session ended without a clean exit, and its heartbeat tells us roughly when
the machine went down.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .util import atomic_write, iso, parse_iso, utcnow


@dataclass(frozen=True)
class Marker:
    pid: int
    started_at: datetime
    heartbeat: datetime


class RunningMarker:
    def __init__(self, state_dir: Path):
        self.path = Path(state_dir) / "running.marker"

    def read(self) -> Optional[Marker]:
        try:
            data = json.loads(self.path.read_text())
            return Marker(
                pid=int(data["pid"]),
                started_at=parse_iso(data["started_at"]),
                heartbeat=parse_iso(data["heartbeat"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def exists(self) -> bool:
        return self.path.exists()

    def write(self, started_at: datetime, now: Optional[datetime] = None) -> None:
        now = now or utcnow()
        atomic_write(
            self.path,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "started_at": iso(started_at),
                    "heartbeat": iso(now),
                }
            ),
        )

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def daemon_running(marker: Optional[Marker]) -> bool:
    """True if the marker belongs to a live PowerCut process.

    Guards against pid reuse after a reboot by checking the command line
    when /proc is available.
    """
    if marker is None or not pid_alive(marker.pid):
        return False
    try:
        with open(f"/proc/{marker.pid}/cmdline", "rb") as f:
            return b"powercut" in f.read()
    except OSError:
        return True
