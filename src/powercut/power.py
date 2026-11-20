"""Power monitor: read AC/battery state and turn changes into events.

Phase 1 reads /sys/class/power_supply directly. UPower (D-Bus) and UPS
support (NUT / apcupsd) come later behind the same PowerState interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

DEFAULT_SYSFS = Path("/sys/class/power_supply")

AC_LOST = "ac_lost"
AC_RESTORED = "ac_restored"
BATTERY_LEVEL = "battery_level"


@dataclass(frozen=True)
class PowerState:
    # True/False when known. None means no mains sensor exists (typical
    # desktop), so PowerCut cannot see outages live on this machine.
    on_ac: Optional[bool]
    battery_percent: Optional[int]
    battery_status: Optional[str]

    @property
    def source(self) -> str:
        if self.on_ac is None:
            return "unknown"
        return "ac" if self.on_ac else "battery"


@dataclass(frozen=True)
class Event:
    kind: str
    percent: Optional[int] = None


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text().strip()
    except (OSError, UnicodeDecodeError):
        return None


def read_power_state(sysfs_root: Path = DEFAULT_SYSFS) -> PowerState:
    on_ac: Optional[bool] = None
    percent: Optional[int] = None
    status: Optional[str] = None

    try:
        entries = sorted(Path(sysfs_root).iterdir())
    except OSError:
        entries = []

    for entry in entries:
        kind = _read(entry / "type")
        if kind in ("Mains", "USB"):
            online = _read(entry / "online")
            if online is not None:
                # Any online mains source means we are on AC.
                on_ac = bool(on_ac) or online == "1"
        elif kind == "Battery":
            # Skip peripheral batteries (mice, keyboards).
            if _read(entry / "scope") == "Device":
                continue
            cap = _read(entry / "capacity")
            if cap is not None and percent is None:
                try:
                    percent = max(0, min(100, int(cap)))
                except ValueError:
                    pass
            if status is None:
                status = _read(entry / "status")

    # Laptops without a Mains node still report Charging/Discharging.
    if on_ac is None and status is not None:
        if status == "Discharging":
            on_ac = False
        elif status in ("Charging", "Full", "Not charging"):
            on_ac = True

    return PowerState(on_ac=on_ac, battery_percent=percent, battery_status=status)


def diff_states(prev: Optional[PowerState], cur: PowerState) -> List[Event]:
    """Events produced by moving from prev to cur."""
    events: List[Event] = []
    if prev is not None:
        if prev.on_ac is True and cur.on_ac is False:
            events.append(Event(AC_LOST, cur.battery_percent))
        elif prev.on_ac is False and cur.on_ac is True:
            events.append(Event(AC_RESTORED, cur.battery_percent))
        if (
            cur.on_ac is False
            and cur.battery_percent is not None
            and prev.battery_percent != cur.battery_percent
        ):
            events.append(Event(BATTERY_LEVEL, cur.battery_percent))
    return events
