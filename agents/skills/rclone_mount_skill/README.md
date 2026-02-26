````markdown
# RClone Mount Skill

This skill formalizes the anchoring of external cloud storage (The Archive) into the CBG ecosystem using persistent `systemd` user services.

## Usage

Run the ritual from the skill directory or workspace root:

```bash
python3 agents/skills/rclone_mount_skill/rclone_mount_skill.py --remote <remote_name> --path <mount_path>
```

## Parameters

- `--remote`: The name of the rclone remote (as configured in `rclone config`).
- `--path`: The absolute path where the remote should be anchored.

## Example

```bash
python3 agents/skills/rclone_mount_skill/rclone_mount_skill.py --remote cbg-share --path /home/cbg/repos/cbg-share
```

## Logic (The Ritual)

1.  **Preparation:** Ensures the target mount directory exists.
2.  **Configuration:** Generates a unique `systemd` user service file (`~/.config/systemd/user/rclone-*.service`).
3.  **Activation:** Reloads the user systemd daemon, enables the service for boot persistence, and restarts it to establish the mount immediately.
4.  **Resilience:** Configured with `Restart=on-failure` and `RestartSec=10` to handle network instability.

````
