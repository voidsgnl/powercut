use chrono::Utc;
use clap::{Parser, Subcommand};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::{
    env, fs,
    path::{Path, PathBuf},
    process, thread,
    time::Duration,
};

#[derive(Parser)]
#[command(name = "powercut", version, about = "Power-loss protection for Linux")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}
#[derive(Subcommand)]
enum Command {
    Status,
    Log {
        #[arg(short, long, default_value_t = 20)]
        n: usize,
    },
    Daemon {
        #[arg(long, default_value_t = 5)]
        interval: u64,
    },
}
#[derive(Debug, Serialize, Deserialize)]
struct Marker {
    pid: u32,
    started_at: String,
    heartbeat: String,
}
#[derive(Debug)]
struct PowerState {
    on_ac: Option<bool>,
    battery: Option<u8>,
    status: Option<String>,
}
fn state_dir() -> PathBuf {
    if let Ok(v) = env::var("POWERCUT_STATE_DIR") {
        return v.into();
    }
    let base = env::var_os("XDG_STATE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env::var_os("HOME").unwrap_or_default()).join(".local/state")
        });
    base.join("powercut")
}
fn read(path: &Path) -> Option<String> {
    fs::read_to_string(path).ok().map(|s| s.trim().to_owned())
}
fn power_state(root: &Path) -> PowerState {
    let mut ac = None;
    let mut battery = None;
    let mut status = None;
    if let Ok(entries) = fs::read_dir(root) {
        for entry in entries.flatten() {
            let p = entry.path();
            let kind = read(&p.join("type"));
            if kind.as_deref() == Some("Mains") || kind.as_deref() == Some("USB") {
                if let Some(v) = read(&p.join("online")) {
                    ac = Some(ac.unwrap_or(false) || v == "1");
                }
            } else if kind.as_deref() == Some("Battery") {
                if read(&p.join("scope")).as_deref() == Some("Device") {
                    continue;
                }
                if battery.is_none() {
                    battery = read(&p.join("capacity"))
                        .and_then(|v| v.parse::<u8>().ok())
                        .map(|v| v.min(100));
                }
                if status.is_none() {
                    status = read(&p.join("status"));
                }
            }
        }
    }
    if ac.is_none() {
        ac = match status.as_deref() {
            Some("Discharging") => Some(false),
            Some("Charging" | "Full" | "Not charging") => Some(true),
            _ => None,
        };
    }
    PowerState {
        on_ac: ac,
        battery,
        status,
    }
}
fn db(path: &Path) -> rusqlite::Result<Connection> {
    if let Some(p) = path.parent() {
        fs::create_dir_all(p).ok();
    }
    let c = Connection::open(path)?;
    c.pragma_update(None, "journal_mode", "WAL")?;
    c.pragma_update(None, "synchronous", "FULL")?;
    c.execute_batch("CREATE TABLE IF NOT EXISTS outages(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT);")?;
    Ok(c)
}
fn now() -> String {
    Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}
fn marker_path(sd: &Path) -> PathBuf {
    sd.join("running.marker")
}
fn write_marker(path: &Path, started: &str) -> std::io::Result<()> {
    let m = Marker {
        pid: process::id(),
        started_at: started.to_owned(),
        heartbeat: now(),
    };
    let tmp = path.with_extension("tmp");
    let encoded = serde_json::to_vec(&m)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    fs::write(&tmp, encoded)?;
    let f = fs::OpenOptions::new().read(true).open(&tmp)?;
    f.sync_all()?;
    fs::rename(tmp, path)?;
    if let Some(p) = path.parent() {
        fs::File::open(p)?.sync_all()?;
    }
    Ok(())
}
fn open_outage(c: &Connection, kind: &str, at: &str) -> rusqlite::Result<()> {
    let exists: i64 = c.query_row(
        "SELECT count(*) FROM outages WHERE ended_at IS NULL",
        [],
        |r| r.get(0),
    )?;
    if exists == 0 {
        c.execute(
            "INSERT INTO outages(kind,started_at) VALUES(?1,?2)",
            params![kind, at],
        )?;
    }
    Ok(())
}
fn close_outages(c: &Connection, at: &str) -> rusqlite::Result<()> {
    c.execute(
        "UPDATE outages SET ended_at=?1 WHERE ended_at IS NULL",
        [at],
    )?;
    Ok(())
}
fn record_transition(
    c: &Connection,
    previous: Option<bool>,
    current: Option<bool>,
    at: &str,
) -> rusqlite::Result<()> {
    match (previous, current) {
        (Some(true), Some(false)) | (None, Some(false)) => open_outage(c, "ac_loss", at)?,
        (Some(false), Some(true)) => close_outages(c, at)?,
        _ => {}
    }
    Ok(())
}
fn daemon(sd: &Path, interval: u64) -> Result<(), Box<dyn std::error::Error>> {
    fs::create_dir_all(sd)?;
    let mp = marker_path(sd);
    if let Ok(raw) = fs::read(&mp) {
        if let Ok(old) = serde_json::from_slice::<Marker>(&raw) {
            if Path::new(&format!("/proc/{}", old.pid)).exists() {
                eprintln!("powercut: daemon may already be running (pid {})", old.pid);
                process::exit(1);
            }
            let c = db(&sd.join("powercut.db"))?;
            close_outages(&c, &old.heartbeat)?;
            c.execute(
                "INSERT INTO outages(kind,started_at,ended_at) VALUES('unclean_shutdown',?1,?2)",
                params![old.heartbeat, now()],
            )?;
        }
    }
    let c = db(&sd.join("powercut.db"))?;
    let started = now();
    let mut previous: Option<bool> = None;
    let root = Path::new("/sys/class/power_supply");
    loop {
        let s = power_state(root);
        let at = now();
        record_transition(&c, previous, s.on_ac, &at)?;
        previous = s.on_ac;
        write_marker(&mp, &started)?;
        thread::sleep(Duration::from_secs(interval.max(1)));
    }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let sd = state_dir();
    match cli.command {
        Command::Status => {
            let s = power_state(Path::new("/sys/class/power_supply"));
            println!(
                "Power source : {}",
                match s.on_ac {
                    Some(true) => "AC",
                    Some(false) => "battery",
                    None => "unknown",
                }
            );
            if let Some(v) = s.battery {
                println!(
                    "Battery      : {}% ({})",
                    v,
                    s.status.as_deref().unwrap_or("unknown")
                );
            }
            if s.on_ac.is_none() {
                println!("Note         : no AC sensor found; live outage detection unavailable.");
            }
            let mp = marker_path(&sd);
            if let Ok(raw) = fs::read(mp) {
                if let Ok(m) = serde_json::from_slice::<Marker>(&raw) {
                    println!(
                        "Daemon       : marker present (pid {}, heartbeat {})",
                        m.pid, m.heartbeat
                    );
                }
            }
            if sd.join("powercut.db").exists() {
                let c = db(&sd.join("powercut.db"))?;
                let row: Option<(String, String, Option<String>)> = c
                    .query_row(
                        "SELECT kind,started_at,ended_at FROM outages ORDER BY id DESC LIMIT 1",
                        [],
                        |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
                    )
                    .ok();
                if let Some((k, t, e)) = row {
                    println!(
                        "Last outage  : {} at {} ({})",
                        k,
                        t,
                        e.unwrap_or_else(|| "ongoing".into())
                    );
                }
            }
        }
        Command::Log { n } => {
            if !sd.join("powercut.db").exists() {
                println!("No outages recorded yet.");
                return Ok(());
            }
            let c = db(&sd.join("powercut.db"))?;
            let mut q=c.prepare("SELECT kind,started_at,ended_at FROM outages ORDER BY started_at DESC,id DESC LIMIT ?1")?;
            let rows = q.query_map([n as i64], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, Option<String>>(2)?,
                ))
            })?;
            println!("{:<20} {:<20} DURATION", "WHAT", "WHEN (UTC)");
            for r in rows {
                let (k, t, e) = r?;
                println!(
                    "{:<20} {:<20} {}",
                    k,
                    t,
                    e.unwrap_or_else(|| "ongoing".into())
                );
            }
        }
        Command::Daemon { interval } => daemon(&sd, interval)?,
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    fn temp_dir(label: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock should be after epoch")
            .as_nanos();
        let path = env::temp_dir().join(format!("powercut-{label}-{}-{nonce}", process::id()));
        fs::create_dir_all(&path).expect("create test directory");
        path
    }

    fn put(root: &Path, relative: &str, value: &str) {
        let path = root.join(relative);
        fs::create_dir_all(path.parent().expect("fixture has parent")).unwrap();
        fs::write(path, value).unwrap();
    }

    #[test]
    fn detects_ac_and_battery_from_sysfs_fixture() {
        let root = temp_dir("sysfs-ac");
        put(&root, "AC/type", "Mains\n");
        put(&root, "AC/online", "1\n");
        put(&root, "BAT0/type", "Battery\n");
        put(&root, "BAT0/capacity", "73\n");
        put(&root, "BAT0/status", "Charging\n");

        let state = power_state(&root);
        assert_eq!(state.on_ac, Some(true));
        assert_eq!(state.battery, Some(73));
        assert_eq!(state.status.as_deref(), Some("Charging"));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn detects_battery_operation_when_ac_sensor_is_missing() {
        let root = temp_dir("sysfs-fallback");
        put(&root, "BAT0/type", "Battery\n");
        put(&root, "BAT0/capacity", "42\n");
        put(&root, "BAT0/status", "Discharging\n");

        let state = power_state(&root);
        assert_eq!(state.on_ac, Some(false));
        assert_eq!(state.battery, Some(42));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn ignores_device_scope_batteries_and_clamps_capacity() {
        let root = temp_dir("sysfs-device-battery");
        put(&root, "BAT0/type", "Battery\n");
        put(&root, "BAT0/scope", "Device\n");
        put(&root, "BAT0/capacity", "99\n");
        put(&root, "BAT1/type", "Battery\n");
        put(&root, "BAT1/capacity", "140\n");
        put(&root, "BAT1/status", "Full\n");

        let state = power_state(&root);
        assert_eq!(state.battery, Some(100));
        assert_eq!(state.on_ac, Some(true));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn reports_unknown_when_power_supply_directory_is_empty() {
        let root = temp_dir("sysfs-unknown");
        let state = power_state(&root);
        assert_eq!(state.on_ac, None);
        assert_eq!(state.battery, None);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn records_ac_loss_once_and_closes_it_on_restoration() {
        let root = temp_dir("transitions");
        let connection = db(&root.join("powercut.db")).unwrap();

        record_transition(&connection, Some(true), Some(false), "t1").unwrap();
        record_transition(&connection, Some(false), Some(false), "t2").unwrap();
        let open_count: i64 = connection
            .query_row(
                "SELECT count(*) FROM outages WHERE ended_at IS NULL",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(open_count, 1);

        record_transition(&connection, Some(false), Some(true), "t3").unwrap();
        let row: (String, Option<String>) = connection
            .query_row("SELECT kind, ended_at FROM outages", [], |row| {
                Ok((row.get(0)?, row.get(1)?))
            })
            .unwrap();
        assert_eq!(row.0, "ac_loss");
        assert_eq!(row.1.as_deref(), Some("t3"));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn unknown_power_reading_does_not_close_an_open_outage() {
        let root = temp_dir("unknown-transition");
        let connection = db(&root.join("powercut.db")).unwrap();
        record_transition(&connection, Some(true), Some(false), "t1").unwrap();
        record_transition(&connection, Some(false), None, "t2").unwrap();

        let ended: Option<String> = connection
            .query_row("SELECT ended_at FROM outages", [], |row| row.get(0))
            .unwrap();
        assert_eq!(ended, None);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn writes_a_valid_atomic_running_marker() {
        let root = temp_dir("marker");
        let path = marker_path(&root);
        write_marker(&path, "started").unwrap();
        let raw = fs::read(&path).unwrap();
        let marker: Marker = serde_json::from_slice(&raw).unwrap();
        assert_eq!(marker.pid, process::id());
        assert_eq!(marker.started_at, "started");
        assert!(!marker.heartbeat.is_empty());
        assert!(!path.with_extension("tmp").exists());
        fs::remove_dir_all(root).unwrap();
    }
}
