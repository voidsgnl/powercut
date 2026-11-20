# PowerCut roadmap

PowerCut is built in phases. Each phase ships something usable on its own.

## Phase 1: Detect and log (done)
- Power monitor reading `/sys/class/power_supply` (AC, battery level).
- Outage log in SQLite.
- Unclean shutdown detection via `running.marker` with a heartbeat.
- CLI: `powercut status`, `powercut log`, `powercut daemon`.

## Phase 2: Prepare
- Session tracker: running GUI apps, their open files, working directories.
- Manifest written atomically every 30-60 s (format in DESIGN.md).
- Manifest history so the last good one survives a bad write.

## Phase 3: Survive
- Policy engine: tiered thresholds (default 20% notify, 10% snapshot, 5% hibernate), configurable.
- Desktop notifications.
- Flush, snapshot, then hibernate or shut down cleanly. Check swap size first and explain if hibernate is not possible.
- UPower over D-Bus as the preferred source, sysfs as fallback.

## Phase 4: Recover
- Recovery agent at login: detect unclean shutdown, show a plain-language prompt.
- `powercut restore`: relaunch apps with the same files.

## Phase 5: Continuous protection
- Lightweight versioned copies of files being actively edited.
- Offer the last good version of damaged files on recovery.
- Filesystem hygiene checks (journaling, periodic `sync`).

## Phase 6: Polish
- UPS support via NUT or apcupsd.
- Tray / small GUI prompt.
- systemd service, packaging, window layout restore on X11.
