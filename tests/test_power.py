from powercut import power


def test_laptop_on_ac(sysfs, supply):
    supply(sysfs, "AC", type="Mains", online="1")
    supply(sysfs, "BAT0", type="Battery", capacity="80", status="Charging")
    s = power.read_power_state(sysfs)
    assert s.on_ac is True and s.battery_percent == 80 and s.source == "ac"


def test_laptop_on_battery(sysfs, supply):
    supply(sysfs, "AC", type="Mains", online="0")
    supply(sysfs, "BAT0", type="Battery", capacity="41", status="Discharging")
    s = power.read_power_state(sysfs)
    assert s.on_ac is False and s.battery_percent == 41 and s.source == "battery"


def test_no_mains_node_falls_back_to_battery_status(sysfs, supply):
    supply(sysfs, "BAT0", type="Battery", capacity="30", status="Discharging")
    assert power.read_power_state(sysfs).on_ac is False


def test_desktop_without_sensors_is_unknown(sysfs):
    s = power.read_power_state(sysfs)
    assert s.on_ac is None and s.source == "unknown"


def test_missing_sysfs_dir_is_unknown(tmp_path):
    assert power.read_power_state(tmp_path / "nope").on_ac is None


def test_peripheral_battery_ignored(sysfs, supply):
    supply(sysfs, "hid-mouse", type="Battery", capacity="5", scope="Device", status="Discharging")
    supply(sysfs, "BAT0", type="Battery", capacity="90", status="Full")
    assert power.read_power_state(sysfs).battery_percent == 90


def S(on_ac, pct=None):
    return power.PowerState(on_ac, pct, None)


def test_diff_ac_lost_and_restored():
    ev = power.diff_states(S(True, 100), S(False, 100))
    assert [e.kind for e in ev] == [power.AC_LOST]
    ev = power.diff_states(S(False, 50), S(True, 50))
    assert [e.kind for e in ev] == [power.AC_RESTORED]


def test_diff_battery_level_only_on_battery():
    assert [e.kind for e in power.diff_states(S(False, 21), S(False, 20))] == [power.BATTERY_LEVEL]
    assert power.diff_states(S(True, 20), S(True, 21)) == []


def test_diff_first_reading_has_no_events():
    assert power.diff_states(None, S(False, 10)) == []
