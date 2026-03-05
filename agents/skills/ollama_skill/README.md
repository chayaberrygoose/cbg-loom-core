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
