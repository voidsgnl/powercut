# PowerCut design

## Architecture

```
powercutd (Rust daemon)
  - Power monitor   (sysfs / UPower / NUT)
  - Session tracker (apps, files, working dirs, optional window layout)
  - Policy engine   (thresholds -> actions)
  - Recovery agent  (runs at login)

PowerCut history store (manifests, file versions, outage log)

powercut CLI (Rust) + optional tray/GUI prompt
```

## Technology decisions

- **Primary language: Rust.** The production daemon, CLI, power monitoring, policy engine, session tracking, and recovery components will be implemented in Rust. This gives PowerCut a small, self-contained executable, predictable resource use, and memory safety for a long-running system utility.
- **Python is transitional.** The existing Python Phase 1 implementation is a working prototype and behavioral reference. Keep it available while the Rust implementation reaches feature parity; do not silently break existing users or discard validated behavior.
- **Storage: SQLite and JSON.** Use SQLite for the outage log with WAL mode and `synchronous=FULL`. Keep session manifests as versioned JSON written atomically (temporary file, fsync, rename, and directory fsync) so they remain inspectable and recoverable by hand.
- **Linux-first integration.** Read basic power information from `/sys/class/power_supply`; add UPower over D-Bus and UPS support through NUT or apcupsd. Keep platform-specific integration behind small interfaces.
- **Standalone.** PowerCut has its own history store and does not depend on UndoOS or another project.

## Rust project layout (target)

```
powercut/
  Cargo.toml
  crates/
    powercut-core/       # policies, events, shared domain types
    powercut-platform/   # sysfs, UPower, UPS integrations
    powercut-store/      # SQLite, manifests, atomic writes
    powercut-daemon/     # monitoring loop and lifecycle
    powercut-cli/        # status, log, daemon, restore
  src/                   # transitional Python prototype
  tests/
```

The workspace can start smaller if splitting crates adds friction. Keep module boundaries clear without overengineering the first Rust milestone.

## Components

**Power monitor.** Reads battery and AC state from `/sys/class/power_supply` (implemented in the Python Phase 1 prototype), with UPower over D-Bus and UPS support via NUT or apcupsd planned for the Rust implementation. Emits events: `ac_lost`, `ac_restored`, and `battery_level(n)`. On machines with no power sensors (typical desktops) the state is `unknown`; live outage detection is unavailable and those outages are caught after the fact by unclean-shutdown detection.

**Session tracker.** Every 30-60 seconds writes a manifest of running GUI apps, their open files, and working directories. Writes atomically so a power cut does not corrupt the manifest itself.

**Policy engine.** Maps events to actions using configurable tiers. Initial defaults may be 20% notify, 10% snapshot, and 5% hibernate. Thresholds must be configurable and actions must be safe to repeat.

**Recovery agent.** At login, checks for the clean-shutdown marker. If absent, shows a plain-language recovery prompt and offers restore.

## Unclean shutdown detection

The daemon writes `running.marker` (PID, start time, heartbeat) on start and refreshes the heartbeat on each poll. On clean exit it removes the marker. If a marker remains at the next start and its recorded process is no longer alive, PowerCut records an unclean shutdown. The last heartbeat approximates when power was lost.

## State directory

`$POWERCUT_STATE_DIR`, else `$XDG_STATE_HOME/powercut`, else `~/.local/state/powercut`. Contains `powercut.db`, `running.marker`, and session manifests.

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

Keep the manifest schema language-neutral so the Python prototype and Rust implementation can read the same data during migration.

## Migration requirements

1. Create the Rust workspace and implement shared domain types and configuration parsing.
2. Reimplement Phase 1 power detection, outage logging, and unclean-shutdown detection in Rust.
3. Verify behavior against the Python prototype using the same test scenarios and state fixtures.
4. Preserve the SQLite schema, state-directory paths, CLI behavior, and JSON manifest compatibility.
5. Switch the documented/default executable to Rust only after Rust Phase 1 passes the test suite. Retain a documented path to inspect or migrate existing user data.

## Open questions

- Per-app save hooks (D-Bus, CLI flags) and which apps to support first.
- System-wide daemon (`/var/lib/powercut`, root) vs per-user daemon.
- Exact Rust crate choices for D-Bus, SQLite, CLI parsing, and notifications; choose maintained crates when each integration is implemented.
