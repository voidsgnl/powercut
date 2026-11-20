# PowerCut

> Power-loss protection for Linux: continuously protects your work, reacts to low-battery or UPS alerts, and helps restore your session after an unexpected shutdown.

**Status:** pre-alpha. The production CLI and monitor are now implemented in Rust. The former Python Phase 1 implementation is retained temporarily as a migration reference.

## Technology

PowerCut is a Rust application. Its first Rust milestone uses:
- Rust standard library for Linux sysfs power detection, filesystem operations, and the monitoring loop.
- SQLite via rusqlite with the bundled SQLite build.
- Clap for CLI parsing.
- Serde/serde_json for the crash marker.
- Chrono for UTC timestamps.

The bundled SQLite feature avoids requiring users to install SQLite development headers. Rust dependencies are compiled into the executable; users do not need Python or a Python virtual environment.

## Build and run

Install Rust using your distribution's package manager or rustup, then:

```bash
cargo build --release
sudo install -m 0755 target/release/powercut /usr/local/bin/powercut
powercut status
powercut log
powercut daemon
```

The daemon runs in the foreground. Stop it with Ctrl+C. A systemd service and clean signal handling are planned.

## State and compatibility

PowerCut stores data in `$POWERCUT_STATE_DIR`, else `$XDG_STATE_HOME/powercut`, else `~/.local/state/powercut`. The Rust implementation preserves the existing SQLite `outages` table and JSON `running.marker` fields so existing Phase 1 data remains readable.

## Current Rust scope

- Read AC and battery state from `/sys/class/power_supply`.
- Record AC loss and restoration in SQLite.
- Detect a stale daemon marker on next startup.
- Provide `powercut status`, `powercut log`, and `powercut daemon`.

UPower, UPS integrations, session snapshots, recovery prompts, robust daemon locking, and systemd packaging remain future work. Do not run multiple daemon instances against the same state directory.

## Development

```bash
cargo test
cargo clippy --all-targets -- -D warnings
```

The Python prototype and its tests remain under `src/powercut` and `tests` during migration. They are not the production entry point.

## License

MIT. See [LICENSE](LICENSE).
