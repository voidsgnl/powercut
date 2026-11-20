# PowerCut roadmap

The production implementation is Rust. The original Python Phase 1 is retained temporarily as a behavioral reference and will be removed after parity and migration checks.

## Phase 1R: Rust foundation (in progress)
- [x] Establish Cargo project and Rust CLI.
- [x] Implement sysfs AC/battery detection.
- [x] Implement SQLite outage logging using the existing schema.
- [x] Implement running marker and unclean-shutdown recording.
- [x] Implement status, log, and foreground daemon commands.
- [x] Add automated Rust tests for sysfs fixtures, power-state fallbacks, outage transitions, unknown readings, and marker writes.
- [ ] Add exclusive daemon lock and reliable SIGINT/SIGTERM cleanup.
- [ ] Verify Python-created database and marker fixtures against Rust.
- [ ] Switch packaging and CI fully to Rust after parity.

## Phase 2: Prepare
- Session tracker: running GUI apps, open files, and working directories.
- Atomic manifest every 30-60 seconds with versioned history.

## Phase 3: Survive
- Configurable warning/snapshot/hibernate thresholds.
- Desktop notifications.
- Safe flush and hibernate, with swap checks.
- UPower integration, sysfs fallback.

## Phase 4: Recover
- Detect unclean shutdown at login.
- Plain-language recovery prompt and app relaunch.

## Phase 5: Continuous protection
- Lightweight versions of actively edited files.
- Last-good-version recovery and filesystem hygiene checks.

## Phase 6: Polish
- UPS support via NUT or apcupsd.
- Tray / small GUI prompt.
- systemd service, packaging, and X11 window-layout restore.
