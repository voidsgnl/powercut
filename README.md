# PowerCut

> Power-loss protection for Linux: continuously saves your session, reacts to low battery or UPS alerts, and restores your work after an unexpected shutdown.

**Status:** early design / pre-alpha. Nothing here is usable yet.

## The problem

On unstable power, a sudden shutdown means lost work, corrupted files, and the "what was I doing?" problem on reboot. Most tools only handle the first part (save before shutdown). PowerCut handles the whole cycle: **prepare, survive, recover.**

## How it works

Laptops and desktops need different strategies:

| Situation | Warning you get | Strategy |
|---|---|---|
| Laptop on battery | Minutes | React to low battery, then save and hibernate cleanly |
| Desktop with UPS | Minutes, if the UPS reports to the OS | Same as laptop, via NUT or apcupsd |
| Desktop, no UPS | None | Continuously protect in the background and recover well afterward |

The last case is the most common where power is unreliable, and the one most tools ignore. PowerCut therefore has a **reactive mode** and a **continuous protection mode** sharing one history store.

### Prepare (continuous)
- Session manifest saved every 30-60 seconds: open apps, files, working directories.
- Lightweight versioned copies of files being actively edited.
- Filesystem hygiene checks (journaling, periodic `sync`).

### Survive (power loss detected)
- Watches power state via UPower (D-Bus) or `/sys/class/power_supply`.
- Tiered thresholds, e.g. 20% notify, 10% snapshot, 5% hibernate.
- Flush, snapshot, then hibernate or shut down cleanly.

### Recover (next boot)
- Detects an unclean shutdown.
- Plain-language recovery prompt: "Power was lost at 14:32. You had 6 apps and 4 files open. Restore?"
- Relaunches apps with the same files and offers the last good version of damaged files.

### Outage log
Records when power dropped and returned, and for how long, to reveal patterns over time.

## Honest limitations

- PowerCut cannot save text an app never wrote to disk. It relies on app autosave (LibreOffice, VS Code, browsers) and fills the gaps.
- Restoring full app state is unreliable; the plan is to relaunch apps with the same files, not checkpoint processes.
- Window layout restore works on X11; Wayland depends on the compositor.
- Hibernate needs swap at least as large as RAM. PowerCut will check and explain this.

## Planned CLI

```
powercut status     # power state, last manifest, daemon health
powercut log        # outage history
powercut restore    # restore the last session after an unclean shutdown
```

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/DESIGN.md](docs/DESIGN.md).

## Related

PowerCut is designed to share its history store with [UndoOS](https://github.com/voidsgnl/undoos).

## License

MIT. See [LICENSE](LICENSE).
