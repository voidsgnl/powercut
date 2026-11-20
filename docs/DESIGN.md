# PowerCut design

## Architecture

```
powercutd (daemon)
  - Power monitor   (UPower / NUT / sysfs)
  - Session tracker (apps, files, working dirs, optional window layout)
  - Policy engine   (thresholds -> actions)
  - Recovery agent  (runs at login)

History store (PowerCut's own: manifests, file versions, outage log)

powercut CLI + small tray/GUI prompt
```

## Decisions

- **Language: Python 3, standard library only.** Fast to prototype, no dependencies to install on a machine that may be in trouble. Revisit Rust for the daemon if footprint becomes a problem.
- **Storage: SQLite for the outage log, JSON for manifests.** SQLite (WAL, `synchronous=FULL`) gives transactional safety for the log. Manifests stay as plain JSON written atomically, so they are easy to inspect and recover by hand.
- **Standalone.** PowerCut has its own history store and does not depend on any other project.

## Components

**Power monitor.** Reads battery and AC state from `/sys/class/power_supply` (Phase 1), with UPower over D-Bus and UPS support via NUT or apcupsd planned. Emits events: `ac_lost`, `ac_restored`, `battery_level(n)`. On machines with no power sensors (typical desktops) the state is `unknown` and live outage detection is unavailable; those outages are caught after the fact by unclean-shutdown detection.

**Session tracker.** Every 30-60 s writes a manifest of running GUI apps, their open files, and working directories. Writes atomically (temp file + fsync + rename + directory fsync) so a power cut never corrupts the manifest itself.

**Policy engine.** Maps events to actions using configurable tiers. Default: 20% notify, 10% snapshot, 5% hibernate.

**Recovery agent.** At login, checks for the clean-shutdown marker. If absent, shows the recovery prompt and offers restore.

## Unclean shutdown detection

On start, the daemon writes `running.marker` (pid, start time, heartbeat). It refreshes the heartbeat every poll. On clean exit it removes the marker. A marker present at start whose pid is not a live PowerCut process means the previous session ended uncleanly, and the heartbeat approximates when power was lost. PowerCut logs an `unclean_shutdown` outage from the last heartbeat to the current start.

## State directory

`$POWERCUT_STATE_DIR`, else `$XDG_STATE_HOME/powercut`, else `~/.local/state/powercut`. Contains `powercut.db`, `running.marker`, and later the manifests.

## Manifest (draft)

```json
{
  "version": 1,
  "saved_at": "2026-11-20T14:32:05Z",
  "power": { "source": "battery", "percent": 41 },
  "apps": [
    {
      "name": "libreoffice-writer",
      "exec": "libreoffice --writer",
      "files": ["/home/user/Documents/report.odt"],
      "cwd": "/home/user/Documents"
    }
  ]
}
```

## Open questions

- Per-app save hooks (D-Bus, CLI flags) and which apps to support first.
- System-wide daemon (`/var/lib/powercut`, root) vs per-user daemon.
