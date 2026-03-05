## Scheduled (Cron) Automation

To run lore generation automatically every hour (processing up to 3 new comments, one file per comment):

1. Create the cron script:
    ```bash
    echo '#!/bin/bash\ncd ~/repos/cbg-loom-core || exit 1\nsource .venv/bin/activate\npython scripts/generate_lore_from_comments.py --max-comments 3' > ~/repos/cbg-loom-core/scripts/generate_lore_cron.sh
    chmod +x ~/repos/cbg-loom-core/scripts/generate_lore_cron.sh
    ```

2. Add to your crontab (edit with `crontab -e`):
    ```cron
    30 * * * * ~/repos/cbg-loom-core/scripts/generate_lore_cron.sh
    ```

This will run the script at 30 minutes past every hour.

**To adjust:**
- Change the `--max-comments` value in the script for a different batch size.
- Change the cron schedule (e.g., `15 * * * *` for 15 minutes past the hour).
- For one file per comment, keep `MIN_COMMENTS_PER_LORE = 1` and `MAX_COMMENTS_PER_LORE = 1` in the script (default as of v2.0).
# Ollama Skill

Local LLM inference via Ollama API. Optimized for resource-constrained environments.

## Setup

1. Install Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Pull a recommended model:
   ```bash
   # For Raspberry Pi 5 (8GB RAM)
   ollama pull llama3.2:3b
   
   # Alternative lightweight options
   ollama pull gemma2:2b
   ollama pull phi3:mini
   ollama pull tinyllama:1.1b
   ```

3. Start Ollama service:
   ```bash
   ollama serve
   ```

## Usage

```python
from agents.skills.ollama_skill import (
    initialize_local_loom,
    generate_local_specimen_data,
)

model = initialize_local_loom()
if model:
    result = generate_local_specimen_data(
        model,
        "Your prompt here"
    )
    print(result)
```

## Configuration

| Environment Variable | Default                  | Description               |
|---------------------|--------------------------|---------------------------|
| `OLLAMA_HOST`       | `http://localhost:11434` | Ollama API endpoint       |
| `OLLAMA_TIMEOUT`    | `900`                    | Request timeout (seconds) |

## Recommended Models for RPi 5 (8GB)

| Model           | Size  | Notes                              |
|-----------------|-------|------------------------------------|
| `llama3.2:3b`   | ~2GB  | Best balance of capability/speed  |
| `gemma2:2b`     | ~1.5GB| Google's efficient model          |
| `phi3:mini`     | ~2GB  | Microsoft's capable small model   |
| `tinyllama:1.1b`| ~600MB| Minimal footprint, basic tasks    |
