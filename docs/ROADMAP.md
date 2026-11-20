# PowerCut roadmap

PowerCut is built in phases. Each phase should ship something usable on its own. The production implementation is Rust; the existing Python Phase 1 remains a working prototype until Rust reaches feature parity.

## Phase 1: Detect and log (Python prototype complete)
- Power monitor reading `/sys/class/power_supply` (AC, battery level).
- Outage log in SQLite.
- Unclean shutdown detection via `running.marker` with a heartbeat.
- CLI: `powercut status`, `powercut log`, `powercut daemon`.

## Phase 1R: Rust core and parity (next)
- Establish the Rust Cargo workspace and crate/module boundaries.
- Implement power-source detection from sysfs.
- Implement outage logging with the existing SQLite data model.
- Implement running-marker heartbeat and unclean-shutdown detection.
- Match the existing CLI behavior for `status`, `log`, and `daemon`.
- Test Rust behavior against the Python prototype and shared state fixtures.
- Preserve existing user data and state-directory compatibility before making Rust the default.

## Phase 2: Prepare
- Session tracker: running GUI apps, their open files, and working directories.
- Manifest written atomically every 30-60 seconds (format in DESIGN.md).
- Manifest history so the last good one survives a bad write.

## Phase 3: Survive
- Policy engine: tiered thresholds (initial defaults: 20% notify, 10% snapshot, 5% hibernate), configurable.
- Desktop notifications.
- Flush, snapshot, then hibernate or shut down cleanly. Check swap size first and explain if hibernate is not possible.
- UPower over D-Bus as the preferred source, sysfs as fallback.

## Phase 4: Recover
- Recovery agent at login: detect unclean shutdown and show a plain-language prompt.
- `powercut restore`: relaunch apps with the same files.

## Phase 5: Continuous protection
- Lightweight versioned copies of files being actively edited.
- Offer the last good version of damaged files on recovery.
- Filesystem hygiene checks (journaling, periodic `sync`).

## Phase 6: Polish
- UPS support via NUT or apcupsd.
- Tray / small GUI prompt.
- systemd service, packaging, and window-layout restore on X11.
