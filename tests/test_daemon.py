import json
from datetime import datetime, timedelta, timezone

from powercut.daemon import Daemon
from powercut.store import KIND_AC_LOSS, KIND_UNCLEAN, OutageLog
from powercut.util import iso

T0 = datetime(2026, 11, 20, 14, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def advance(self, s):
        self.now += timedelta(seconds=s)


def make(tmp_path, sysfs, clock):
    return Daemon(state_dir=tmp_path / "state", sysfs_root=sysfs, clock=clock)


def set_ac(sysfs, supply, online):
    import shutil

    shutil.rmtree(sysfs / "AC", ignore_errors=True)
    supply(sysfs, "AC", type="Mains", online=online)


def test_clean_start_stop_leaves_no_marker(tmp_path, sysfs):
    d = make(tmp_path, sysfs, Clock())
    assert d.start().unclean_shutdown is False
    assert d.marker.exists()
    d.stop()
    assert not d.marker.exists()


def test_unclean_shutdown_detected_and_logged(tmp_path, sysfs):
    clock = Clock()
    d1 = make(tmp_path, sysfs, clock)
    d1.start()
    clock.advance(30)
    d1.tick()  # heartbeat at T0+30
    # Simulated power cut: no stop(). Marker points at a dead pid.
    m = d1.marker.path
    data = json.loads(m.read_text())
    data["pid"] = 2**22 + 12345
    m.write_text(json.dumps(data))
    d1.log.close()

    clock.advance(600)
    d2 = make(tmp_path, sysfs, clock)
    report = d2.start()
    assert report.unclean_shutdown is True
    assert report.last_seen == T0 + timedelta(seconds=30)
    out = d2.log.recent(1)[0]
    assert out.kind == KIND_UNCLEAN
    assert out.duration_seconds == 600
    d2.stop()


def test_ac_loss_and_restore_logged(tmp_path, sysfs, supply):
    clock = Clock()
    set_ac(sysfs, supply, "1")
    d = make(tmp_path, sysfs, clock)
    d.start()
    d.tick()
    clock.advance(60)
    set_ac(sysfs, supply, "0")
    d.tick()
    assert d.log.has_open()
    clock.advance(120)
    set_ac(sysfs, supply, "1")
    d.tick()
    o = d.log.recent(1)[0]
    assert o.kind == KIND_AC_LOSS and o.duration_seconds == 120
    d.stop()


def test_booting_on_battery_starts_outage(tmp_path, sysfs, supply):
    set_ac(sysfs, supply, "0")
    d = make(tmp_path, sysfs, Clock())
    d.start()
    d.tick()
    assert d.log.has_open()
    d.stop()


def test_outage_log_roundtrip(tmp_path):
    log = OutageLog(tmp_path / "x.db")
    log.record("ac_loss", T0, T0 + timedelta(seconds=90))
    log.start("ac_loss", T0 + timedelta(hours=1))
    rows = log.recent()
    assert rows[0].ended_at is None and rows[1].duration_seconds == 90
    assert iso(rows[1].started_at) == "2026-11-20T14:00:00Z"
