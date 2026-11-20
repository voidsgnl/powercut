# PowerCut design

## Architecture

```
powercutd (daemon)
  - Power monitor   (UPower / NUT / sysfs)
  - Session tracker (apps, files, working dirs, optional window layout)
  - Policy engine   (thresholds -> actions)
  - Recovery agent  (runs at login)

Shared history store (from UndoOS)

powercut CLI + small tray/GUI prompt
```

## Components

**Power monitor.** Reads battery and AC state from UPower over D-Bus, falling back to `/sys/class/power_supply`. UPS support via NUT or apcupsd. Emits events: `ac_lost`, `ac_restored`, `battery_level(n)`.

**Session tracker.** Every 30-60 s writes a manifest of running GUI apps, their open files, and working directories. Writes atomically (temp file + rename + fsync) so a power cut never corrupts the manifest itself.

**Policy engine.** Maps events to actions using configurable tiers. Default: 20% notify, 10% snapshot, 5% hibernate.

**Recovery agent.** At login, checks for the clean-shutdown marker. If absent, shows the recovery prompt and offers restore.

## Unclean shutdown detection

On start, the daemon writes `running.marker`. On clean exit (shutdown hook) it removes it. A marker present at boot means the previous session ended uncleanly. The last power event timestamp comes from the outage log.

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

- Storage: SQLite vs JSON for manifests and outage log.
- How to share the UndoOS history store without tight coupling.
- Per-app save hooks (D-Bus, CLI flags) and which apps to support first.
- Language: Rust (small, safe daemon) or Python for a fast prototype.
