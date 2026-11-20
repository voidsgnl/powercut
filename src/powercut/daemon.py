"""powercutd: the long-running monitor.

Phase 1 scope: watch power state, keep the outage log, and detect unclean
shutdowns. The session tracker, policy engine and recovery agent plug into
tick() in later phases.
"""

from __future__ import annotations

import signal
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from . import power
from .marker import RunningMarker, daemon_running
from .store import KIND_AC_LOSS, KIND_UNCLEAN, OutageLog
from .util import state_dir as default_state_dir
from .util import utcnow


class AlreadyRunning(RuntimeError):
    pass


@dataclass(frozen=True)
class StartupReport:
    unclean_shutdown: bool
    last_seen: Optional[datetime] = None


class Daemon:
    def __init__(
        self,
        state_dir: Optional[Path] = None,
        sysfs_root: Path = power.DEFAULT_SYSFS,
        poll_interval: float = 5.0,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.state_dir = Path(state_dir) if state_dir else default_state_dir()
        self.sysfs_root = Path(sysfs_root)
        self.poll_interval = poll_interval
        self.clock = clock
        self.marker = RunningMarker(self.state_dir)
        self.log = OutageLog(self.state_dir / "powercut.db")
        self.started_at: Optional[datetime] = None
        self._prev: Optional[power.PowerState] = None

    def start(self) -> StartupReport:
        old = self.marker.read()
        if daemon_running(old):
            raise AlreadyRunning(f"powercut daemon already running (pid {old.pid})")

        now = self.clock()
        self.started_at = now

        if self.marker.exists():
            # Previous session never cleaned up: unclean shutdown.
            last_seen = old.heartbeat if old else now
            self.log.end_open(last_seen)
            self.log.record(KIND_UNCLEAN, last_seen, now)
            report = StartupReport(True, last_seen)
        else:
            self.log.end_open(now)
            report = StartupReport(False)

        self.marker.write(now, now)
        return report

    def tick(self) -> List[power.Event]:
        now = self.clock()
        state = power.read_power_state(self.sysfs_root)
        events = power.diff_states(self._prev, state)

        # Booted while already on battery: that is an outage in progress.
        if self._prev is None and state.on_ac is False and not self.log.has_open():
            self.log.start(KIND_AC_LOSS, now)

        for ev in events:
            if ev.kind == power.AC_LOST and not self.log.has_open():
                self.log.start(KIND_AC_LOSS, now)
            elif ev.kind == power.AC_RESTORED:
                self.log.end_open(now)

        self._prev = state
        self.marker.write(self.started_at or now, now)
        return events

    def stop(self) -> None:
        """Clean shutdown: remove the marker so the next start is not 'unclean'."""
        self.marker.clear()
        self.log.close()

    def run(self, stop_event: Optional[threading.Event] = None) -> None:
        stop_event = stop_event or threading.Event()
        self.start()
        try:
            while not stop_event.is_set():
                self.tick()
                stop_event.wait(self.poll_interval)
        finally:
            self.stop()


def run_forever(**kwargs) -> None:
    """Run until SIGINT/SIGTERM, then shut down cleanly."""
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    Daemon(**kwargs).run(stop)
