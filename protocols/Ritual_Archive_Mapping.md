# Ritual: Archive Mapping (RClone)

This Ritual defines the process for anchoring an external cloud storage (The Archive) to the local filesystem in a repeatable, persistent way using systemd user services.

## Prerequisites

1.  **RClone Installed:** Ensure `rclone` is installed (`rclone version`).
2.  **Remote Configured:** The remote must be configured via `rclone config`. (Requires one-time interactive OAuth).

## Enacting the Ritual

To anchor a new section of The Archive, use the `setup_rclone_mount.sh` script:

```bash
~/repos/cbg-loom-core/scripts/setup_rclone_mount.sh <remote_name> <mount_path>
```

### Example

Mapping the `cbg-share` remote to `~/repos/cbg-drive`:

```bash
~/repos/cbg-loom-core/scripts/setup_rclone_mount.sh cbg-share ~/repos/cbg-drive
```

## How It Works

The script performs the following actions:
1.  Creates the target mount directory.
2.  Generates a unique systemd user service file in `~/.config/systemd/user/`.
3.  Configures the service to:
    *   Mount the remote with `--vfs-cache-mode writes`.
    *   Auto-restart on failure.
    *   Start automatically on boot (once the user logs in).
4.  Reloads the systemd daemon.
5.  Enables and starts the service.

## Managing Mounts

*   **Check Status:** `systemctl --user status rclone-<service-name>`
*   **Stop Mount:** `systemctl --user stop rclone-<service-name>`
*   **Restart Mount:** `systemctl --user restart rclone-<service-name>`
*   **Remove Mount:** 
    1.  Stop and disable the service.
    2.  Delete the service file in `~/.config/systemd/user/`.
    3.  Run `systemctl --user daemon-reload`.
