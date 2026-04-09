# Sentinel Daemon (macOS)

LaunchDaemon that runs the Sentinel backend as root on boot, so it can enforce
`/etc/hosts` blocks and survive user logouts.

## Files

- `com.sentinel.daemon.plist` — LaunchDaemon template. `install.sh` patches the
  wrapper path into `ProgramArguments` before copying it into
  `/Library/LaunchDaemons/`.
- `sentinel-wrapper.sh` — shell wrapper that sets `PATH`, activates a venv if
  present, and execs `python3 -m sentinel serve`. Output is appended to
  `/var/log/sentinel.log`.
- `install.sh` — copies the rendered plist into place and loads it with
  `launchctl load -w`. Also backs up `/etc/hosts` to
  `/etc/hosts.sentinel-backup`.
- `uninstall.sh` — unloads the daemon, removes the plist, and restores the
  `/etc/hosts` backup.

## Install

```sh
sudo ./install.sh
```

Post-install checks:

```sh
launchctl list | grep sentinel
tail -f /var/log/sentinel.log
```

## Uninstall

```sh
sudo ./uninstall.sh
```

## Tamper detection

Once the daemon is running, `sentinel.persistence` starts a background thread
that re-applies the `/etc/hosts` block every few seconds if the Sentinel
markers disappear (so users can't simply delete them).
