# /* [FILE_ID]: skills/OLLAMA_SKILL // VERSION: 1.0 // STATUS: STABLE */
# [NARRATIVE]: Local LLM inference via Ollama API.
#              Optimized for resource-constrained environments (RPi 5 8GB).
# [RESTRICTION]: NO_NANO_BANANA_GENERATION in effect

import os
import requests
from datetime import datetime
from typing import Optional, List, Dict

# ─── CONFIGURATION ─────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "900"))  # 15 min default for RPi


# Recommended models for Raspberry Pi 5 (8GB RAM)
# Ordered by capability/size trade-off (gemma2:2b is now default)
RECOMMENDED_MODELS = [
    "gemma2:2b",       # Default: Google's efficient 2B model
    "llama3.2:3b",    # Good balance of capability and resource usage
    "phi3:mini",      # Microsoft's small but capable model
    "tinyllama:1.1b", # Minimal footprint for constrained systems
    "qwen2.5:3b",     # Alibaba's efficient model
    "gemma3:4b",      # Larger, but may not fit in 8GB
]


def _ts() -> str:
    """Returns current timestamp for logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    """Prints a timestamped log message."""
    print(f"[{_ts()}] {msg}")


def check_ollama_connection() -> bool:
    """
    Verify Ollama service is running and accessible.
    """
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_available_models() -> List[str]:
    """
    Query Ollama for locally available models.
    Returns list of model names.
    """
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return models
        return []
    except requests.exceptions.RequestException as e:
        _log(f"[SYSTEM_WARNING]: Failed to list Ollama models: {e}")
        return []


def initialize_local_loom(model_name: Optional[str] = None) -> Optional[str]:
    """
    Initialize local Ollama connection and select model.
    Returns the model name to use, or None if unavailable.
    """
    if not check_ollama_connection():
        _log("[SYSTEM_WARNING]: Ollama service not reachable. Ensure it's running.")
        return None

    available = list_available_models()
    
    if not available:
        _log("[SYSTEM_WARNING]: No models available in Ollama. Pull a model first.")
        _log(f"[SYSTEM_HINT]: Try: ollama pull {RECOMMENDED_MODELS[0]}")
        return None

    # Use requested model if available
    if model_name:
        # Check exact match or partial match (e.g., "llama3.2" matches "llama3.2:3b")
        for m in available:
            if model_name in m or m in model_name:
                _log(f"[SYSTEM_LOG]: Local Loom Uplink Established with {m}")
                return m
        _log(f"[SYSTEM_WARNING]: Requested model '{model_name}' not found locally.")

    # Find first recommended model that's available
    for rec in RECOMMENDED_MODELS:
        base_name = rec.split(":")[0]  # e.g., "llama3.2" from "llama3.2:3b"
        for avail in available:
            if base_name in avail:
                _log(f"[SYSTEM_LOG]: Local Loom Uplink Established with {avail}")
                return avail

    # Fallback to first available model
    selected = available[0]
    _log(f"[SYSTEM_LOG]: Local Loom Uplink Established with {selected} (first available)")
    return selected


def generate_local_specimen_data(
    model_name: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    timeout: int = None,
) -> str:
    """
    Generate text using local Ollama model.
    Respects NO_NANO_BANANA_GENERATION protocol.
    """
    if timeout is None:
        timeout = OLLAMA_TIMEOUT
        
    # Protocol enforcement
    if "nano banana" in prompt.lower() and "override" not in prompt.lower():
        return "[ACCESS_DENIED]: Protocol [NO_NANO_BANANA_GENERATION] Active. Use override code."

    try:
        _log(f"[SYSTEM_LOG]: Invoking local synthesis via {model_name}...")
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=timeout,
        )

        if response.status_code == 200:
            data = response.json()
            text = data.get("response", "")
            if text:
                return text.strip()
            return "[SYSTEM_WARNING]: Empty response from model."
        else:
            return f"[SYSTEM_FAILURE]: Ollama returned status {response.status_code}: {response.text[:200]}"

    except requests.exceptions.Timeout:
        return "[SYSTEM_FAILURE]: Local inference timed out. Model may be too large for available resources."
    except requests.exceptions.RequestException as e:
        return f"[SYSTEM_FAILURE]: Local inference failed: {e}"


def pull_model(model_name: str) -> bool:
    """
    Pull a model from Ollama registry.
    This is a blocking operation that can take several minutes.
    """
    _log(f"[SYSTEM_LOG]: Pulling model {model_name}... This may take a while.")
    
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=3600,  # 1 hour timeout for large models
        )
        
        for line in response.iter_lines():
            if line:
                # Could parse progress here, but keeping simple for now
                pass
        
        # Verify model is now available
        available = list_available_models()
        if any(model_name in m for m in available):
            _log(f"[SYSTEM_SUCCESS]: Model {model_name} is now available.")
            return True
        else:
            _log(f"[SYSTEM_WARNING]: Pull completed but model not found in list.")
            return False
            
    except Exception as e:
        _log(f"[SYSTEM_FAILURE]: Failed to pull model: {e}")
        return False


if __name__ == "__main__":
    # Test local connection
    print("[SYSTEM_TEST]: Checking Ollama connectivity...")
    
    if check_ollama_connection():
        print("[SYSTEM_OK]: Ollama is running.")
        models = list_available_models()
        print(f"[SYSTEM_LOG]: Available models: {models}")
        
        model = initialize_local_loom()
        if model:
            result = generate_local_specimen_data(
                model,
                "Generate a two-word Industrial Noir textile pattern name.",
            )
            print(f"[SYSTEM_RESULT]: {result}")
    else:
        print("[SYSTEM_WARNING]: Ollama not running. Start with: ollama serve")
        print(f"[SYSTEM_HINT]: Recommended model for RPi 5: {RECOMMENDED_MODELS[0]}")
