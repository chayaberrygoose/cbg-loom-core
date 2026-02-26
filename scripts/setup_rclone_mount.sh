#!/bin/bash

# setup_rclone_mount.sh
# A script to create a repeatable systemd service for mounting rclone remotes.

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <remote_name> <mount_path>"
    echo "Example: $0 cbg-share /home/cbg/repos/cbg-share"
    exit 1
fi

REMOTE_NAME=$1
MOUNT_PATH=$2
# Escape the path for the service name (replace / with -)
SERVICE_NAME="rclone-$(echo $MOUNT_PATH | sed 's|^/||;s|/|-|g')"

# Create mount directory if it doesn't exist
mkdir -p "$MOUNT_PATH"

SERVICE_FILE="$HOME/.config/systemd/user/${SERVICE_NAME}.service"

echo "Creating service file at $SERVICE_FILE..."

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=RClone mount for ${REMOTE_NAME} at ${MOUNT_PATH}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/rclone mount ${REMOTE_NAME}: ${MOUNT_PATH} --vfs-cache-mode writes
ExecStop=/bin/fusermount -u ${MOUNT_PATH}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

# Reload systemd user daemon
systemctl --user daemon-reload

# Enable and start the service
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"

echo "Service ${SERVICE_NAME} created, enabled, and started."
echo "You can check status with: systemctl --user status ${SERVICE_NAME}"
