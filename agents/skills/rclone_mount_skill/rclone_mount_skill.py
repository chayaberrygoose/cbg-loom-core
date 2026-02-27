# [FILE_ID]: RCLONE_MOUNT_SKILL // VERSION: 1.0 // STATUS: OPERATIONAL
#!/usr/bin/env python3
"""Skill: Anchor a remote Archive (rclone) to the local filesystem.

Usage:
  python3 rclone_mount_skill.py --remote <remote_name> --path <mount_path>

This skill formalizes the anchoring of external cloud storage into the CBG ecosystem.
It creates a persistent systemd user service to manage the mount.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, shell=False):
    """Utility to run shell commands and return output/error."""
    try:
        result = subprocess.run(cmd, shell=shell, check=True, capture_output=True, text=True)
        return result.stdout.strip(), None
    except subprocess.CalledProcessError as e:
        return None, e.stderr.strip()

def setup_rclone_mount(remote_name, mount_path):
    print(f"--- [RITUAL: ANCHORING {remote_name}] ---")
    
    # 1. Ensure mount path exists
    path = Path(mount_path).expanduser().resolve()
    print(f"Preparing anchor point: {path}")
    path.mkdir(parents=True, exist_ok=True)

    # 2. Define Service Name and File
    # Convert path to a safe string for service naming: ~/repos/drive -> home-user-repos-drive
    safe_path = str(path).strip("/").replace("/", "-")
    service_name = f"rclone-{safe_path}"
    service_file = Path(f"~/.config/systemd/user/{service_name}.service").expanduser()
    
    # Ensure systemd user directory exists
    service_file.parent.mkdir(parents=True, exist_ok=True)

    # 3. Create Service Content
    content = f"""[Unit]
Description=RClone mount for {remote_name} at {path}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/rclone mount {remote_name}: {path} --vfs-cache-mode writes
ExecStop=/bin/fusermount -u {path}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""

    print(f"Writing Ritual logic to {service_file}...")
    service_file.write_text(content)

    # 4. Activate the Ritual
    print("Activating systemd service...")
    _, err = run_command(["systemctl", "--user", "daemon-reload"])
    if err:
        print(f"Error reloading daemon: {err}")
        return False

    _, err = run_command(["systemctl", "--user", "enable", service_name])
    if err:
        print(f"Error enabling service: {err}")
        return False

    _, err = run_command(["systemctl", "--user", "restart", service_name])
    if err:
        print(f"Error starting service: {err}")
        return False

    print(f"SUCCESS: {remote_name} is now anchored at {path}")
    print(f"Monitor status with: systemctl --user status {service_name}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CBG RClone Mount Skill")
    parser.add_argument("--remote", required=True, help="RClone remote name")
    parser.add_argument("--path", required=True, help="Local mount path")

    args = parser.parse_args()
    
    if setup_rclone_mount(args.remote, args.path):
        sys.exit(0)
    else:
        sys.exit(1)
