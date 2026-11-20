"""powercut command line."""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from typing import List, Optional

from . import __version__, power
from .daemon import AlreadyRunning, run_forever
from .marker import RunningMarker, daemon_running
from .store import KIND_AC_LOSS, KIND_UNCLEAN, OutageLog
from .util import state_dir, utcnow

KIND_LABELS = {KIND_AC_LOSS: "power lost", KIND_UNCLEAN: "unclean shutdown"}


def fmt_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "ongoing"
    return str(timedelta(seconds=seconds))


def cmd_status(args) -> int:
    sd = state_dir()
    state = power.read_power_state()
    marker = RunningMarker(sd)
    m = marker.read()

    print(f"Power source : {state.source}")
    if state.battery_percent is not None:
        print(f"Battery      : {state.battery_percent}% ({state.battery_status or 'unknown'})")
    if state.on_ac is None:
        print("Note         : no AC sensor found; live outage detection is unavailable here.")
        print("               Outages are still caught after the fact via unclean-shutdown detection.")

    if daemon_running(m):
        age = int((utcnow() - m.heartbeat).total_seconds())
        print(f"Daemon       : running (pid {m.pid}, last heartbeat {age}s ago)")
    elif marker.exists():
        print("Daemon       : not running (stale marker: last session ended uncleanly)")
    else:
        print("Daemon       : not running")

    db = sd / "powercut.db"
    if db.exists():
        log = OutageLog(db)
        try:
            recent = log.recent(1)
        finally:
            log.close()
        if recent:
            o = recent[0]
            print(
                f"Last outage  : {KIND_LABELS.get(o.kind, o.kind)} at "
                f"{o.started_at:%Y-%m-%d %H:%M:%S} UTC ({fmt_duration(o.duration_seconds)})"
            )
    return 0


def cmd_log(args) -> int:
    db = state_dir() / "powercut.db"
    if not db.exists():
        print("No outages recorded yet.")
        return 0
    log = OutageLog(db)
    try:
        outages = log.recent(args.n)
    finally:
        log.close()
    if not outages:
        print("No outages recorded yet.")
        return 0
    print(f"{'WHEN (UTC)':<20} {'WHAT':<18} DURATION")
    for o in outages:
        print(
            f"{o.started_at:%Y-%m-%d %H:%M:%S}  "
            f"{KIND_LABELS.get(o.kind, o.kind):<18} {fmt_duration(o.duration_seconds)}"
        )
    return 0


def cmd_daemon(args) -> int:
    try:
        run_forever(poll_interval=args.interval)
    except AlreadyRunning as e:
        print(f"powercut: {e}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="powercut", description=__doc__)
    p.add_argument("--version", action="version", version=f"powercut {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="power state, daemon health, last outage").set_defaults(func=cmd_status)

    lg = sub.add_parser("log", help="outage history")
    lg.add_argument("-n", type=int, default=20, help="how many entries (default 20)")
    lg.set_defaults(func=cmd_log)

    d = sub.add_parser("daemon", help="run the monitor in the foreground")
    d.add_argument("--interval", type=float, default=5.0, help="poll seconds (default 5)")
    d.set_defaults(func=cmd_daemon)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
