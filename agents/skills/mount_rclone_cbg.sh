#!/usr/bin/env bash
set -euo pipefail

# Mount an rclone remote into the repo's directory.
# Usage:
#  ./mount_rclone_cbg.sh [remote_path] [action]
# Examples:
#  ./mount_rclone_cbg.sh start                # mounts default remote `cbg-share:` into cbg/
#  ./mount_rclone_cbg.sh cbg-share:SubFolder start
#  ./mount_rclone_cbg.sh stop
#  ./mount_rclone_cbg.sh status

# If script is in /home/cbg/repos/cbg/mount_rclone_cbg.sh
# then dirname $0 is /home/cbg/repos/cbg
MOUNT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$MOUNT_DIR/.rclone_cbg_mount.pid"
LOGFILE="$MOUNT_DIR/.rclone_cbg_mount.log"

if [ "$#" -eq 0 ]; then
  ACTION="start"
  REMOTE_PATH="cbg-share:"
else
  if [[ "$1" == "start" || "$1" == "stop" || "$1" == "status" ]]; then
    ACTION="$1"
    REMOTE_PATH="${2:-cbg-share:}"
  else
    REMOTE_PATH="$1"
    ACTION="${2:-start}"
  fi
fi

function start_mount() {
  command -v rclone >/dev/null 2>&1 || { echo "rclone not found in PATH" >&2; exit 1; }
  mkdir -p "$MOUNT_DIR"

  if mountpoint -q "$MOUNT_DIR"; then
    echo "$MOUNT_DIR is already a mountpoint"
    exit 0
  fi

  echo "Mounting '$REMOTE_PATH' -> $MOUNT_DIR"
  # start rclone in background and capture pid
  rclone mount "$REMOTE_PATH" "$MOUNT_DIR" --allow-other --vfs-cache-mode writes --log-file="$LOGFILE" --log-level=INFO &
  echo $! > "$PIDFILE"
  sleep 1

  if mountpoint -q "$MOUNT_DIR"; then
    echo "Mounted. pid=$(cat $PIDFILE)"
  else
    echo "Mount may have failed; check $LOGFILE" >&2
    exit 1
  fi
}

function stop_mount() {
  if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE")
    echo "Stopping rclone (pid $pid)"
    kill "$pid" 2>/dev/null || true
    rm -f "$PIDFILE"
  fi

  if mountpoint -q "$MOUNT_DIR"; then
    echo "Unmounting $MOUNT_DIR"
    fusermount -u "$MOUNT_DIR" 2>/dev/null || umount "$MOUNT_DIR" 2>/dev/null || true
  fi
  echo "Stopped"
}

function status() {
  if mountpoint -q "$MOUNT_DIR"; then
    echo "$MOUNT_DIR is mounted"
  else
    echo "$MOUNT_DIR is not mounted"
  fi
  if [ -f "$PIDFILE" ]; then
    echo "PIDFILE: $(cat "$PIDFILE")"
  fi
}

case "$ACTION" in
  start)
    start_mount
    ;;
  stop)
    stop_mount
    ;;
  status)
    status
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    echo "Usage: $0 [remote_path] [start|stop|status]" >&2
    exit 2
    ;;
esac
