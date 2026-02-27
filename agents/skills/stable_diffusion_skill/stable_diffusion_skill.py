# [FILE_ID]: stable_diffusion_skill/stable_diffusion_skill.py // VERSION: 2.0 // STATUS: STABLE
# // SIGNAL_RECOVERY: COMFYUI API INTEGRATION

import base64
import json
import os
import re
import shlex
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import request
from urllib.error import HTTPError, URLError


def _build_comfy_url(base_url: str, route: str) -> str:
    return f"{base_url.rstrip('/')}/{route.lstrip('/')}"


def _http_json(
    url: str,
    method: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 180,
) -> Dict[str, Any]:
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }

    req = request.Request(url=url, data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)


def _api_healthcheck(base_url: str, timeout: int = 5) -> bool:
    try:
        url = _build_comfy_url(base_url, "system_stats")
        _http_json(url=url, method="GET", timeout=timeout)
        return True
    except (HTTPError, URLError, TimeoutError, ValueError):
        return False


def _resolve_comfy_dir() -> Path:
    default_dir = Path.home() / "repos" / "ComfyUI"
    return Path(os.getenv("COMFYUI_DIR", str(default_dir))).expanduser()


def _sanitize_log_line(line: str, use_tilde_paths: bool) -> str:
    if not use_tilde_paths:
        return line
    home_prefix = str(Path.home())
    return line.replace(home_prefix, "~")


def _stream_output_to_log(
    process: subprocess.Popen,
    log_path: Path,
    use_tilde_paths: bool,
) -> None:
    stream = process.stdout
    if stream is None:
        return

    with log_path.open("a", encoding="utf-8", errors="ignore") as log_file:
        for line in stream:
            log_file.write(_sanitize_log_line(line, use_tilde_paths=use_tilde_paths))
            log_file.flush()


def start_comfy_if_needed(
    base_url: Optional[str] = None,
    startup_timeout: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Starts ComfyUI in the background if API is not reachable.

    Env vars:
    - COMFYUI_DIR (default: ~/repos/ComfyUI)
    - COMFYUI_START_CMD (default: ./start_comfy.sh)
    - COMFYUI_START_TIMEOUT (default: 240)
    - COMFYUI_START_LOG (default: artifacts/generated/stable-diffusion/comfy.log)
    - COMFY_LOG_TILDE_PATHS (default: 1)
    """
    resolved_base_url = (base_url or os.getenv("COMFYUI_URL") or "http://127.0.0.1:8188").strip()
    resolved_startup_timeout = startup_timeout or int(os.getenv("COMFYUI_START_TIMEOUT", "240"))

    if _api_healthcheck(resolved_base_url, timeout=5):
        return True, f"[SYSTEM_LOG]: ComfyUI API already online at {resolved_base_url}"

    comfy_dir = _resolve_comfy_dir()
    if not comfy_dir.exists():
        return False, f"[SYSTEM_ERROR]: COMFYUI_DIR not found: {comfy_dir}"

    command = os.getenv("COMFYUI_START_CMD", "./start_comfy.sh").strip()
    if not command:
        return False, "[SYSTEM_ERROR]: COMFYUI_START_CMD is empty."

    log_path = Path(
        os.getenv(
            "COMFYUI_START_LOG",
            str(Path("artifacts") / "generated" / "stable-diffusion" / "comfy.log"),
        )
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    use_tilde_paths = os.getenv("COMFY_LOG_TILDE_PATHS", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    process = subprocess.Popen(
        shlex.split(command),
        cwd=str(comfy_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    thread = threading.Thread(
        target=_stream_output_to_log,
        args=(process, log_path, use_tilde_paths),
        daemon=True,
    )
    thread.start()

    deadline = time.time() + resolved_startup_timeout
    while time.time() < deadline:
        if _api_healthcheck(resolved_base_url, timeout=5):
            return True, f"[SYSTEM_LOG]: ComfyUI API online at {resolved_base_url}"
        time.sleep(2)

    return False, (
        f"[SYSTEM_ERROR]: Timed out waiting for ComfyUI at {resolved_base_url}. "
        f"Check startup log: {log_path}"
    )


def initialize_comfy_uplink(
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    auto_start: Optional[bool] = None,
) -> Tuple[bool, str]:
    """
    Validates ComfyUI API connectivity.

    Env vars:
    - COMFYUI_URL (default: http://127.0.0.1:8188)
    - COMFYUI_TIMEOUT (default: 180)
    - COMFYUI_AUTO_START (default: 1)
    """
    resolved_base_url = (base_url or os.getenv("COMFYUI_URL") or "http://127.0.0.1:8188").strip()
    resolved_timeout = timeout or int(os.getenv("COMFYUI_TIMEOUT", "180"))
    resolved_auto_start = (
        auto_start
        if auto_start is not None
        else os.getenv("COMFYUI_AUTO_START", "1").strip().lower() in {"1", "true", "yes", "on"}
    )

    if not _api_healthcheck(resolved_base_url, timeout=5) and resolved_auto_start:
        started, status = start_comfy_if_needed(base_url=resolved_base_url)
        if not started:
            return False, status

    try:
        url = _build_comfy_url(resolved_base_url, "system_stats")
        _http_json(url=url, method="GET", timeout=resolved_timeout)
        return True, f"[SYSTEM_LOG]: ComfyUI Uplink Established at {resolved_base_url}"
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return False, f"[SYSTEM_ERROR]: ComfyUI Uplink failed: {exc}"


def _decode_b64_image(image_b64: str) -> bytes:
    clean_data = image_b64.split(",", 1)[1] if "," in image_b64 else image_b64
    return base64.b64decode(clean_data)


def _graphics_readme_path() -> Path:
    return Path(os.getenv("SD_GRAPHICS_README", str(Path("artifacts") / "graphics" / "README.md")))


def _graphics_root_dir() -> Path:
    return Path(os.getenv("SD_GRAPHICS_ROOT", str(Path("artifacts") / "graphics")))


def _load_graphic_type_definitions() -> Dict[str, str]:
    readme_path = _graphics_readme_path()
    if not readme_path.exists():
        return {
            "standalone": "standalone images",
            "textures": "textures for trim or overlays",
            "tiles": "graphics meant to be tiled",
        }

    content = readme_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    definitions: Dict[str, str] = {}
    current_key: Optional[str] = None
    current_lines: List[str] = []

    for line in content:
        heading_match = re.match(r"^##\s+(.+)$", line.strip(), flags=re.IGNORECASE)
        if heading_match:
            if current_key is not None:
                definitions[current_key] = " ".join(current_lines).strip()
            current_key = heading_match.group(1).strip().lower()
            current_lines = []
            continue

        if current_key is not None and line.strip():
            current_lines.append(line.strip())

    if current_key is not None:
        definitions[current_key] = " ".join(current_lines).strip()

    if not definitions:
        definitions = {
            "standalone": "standalone images",
            "textures": "textures for trim or overlays",
            "tiles": "graphics meant to be tiled",
        }

    if "anchors" in definitions and "standalone" not in definitions:
        definitions["standalone"] = definitions["anchors"]

    # Ensure we never write to the logos folder
    if "logos" in definitions:
        del definitions["logos"]

    return definitions


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _classify_graphic_type(prompt: str) -> str:
    definitions = _load_graphic_type_definitions()
    prompt_lower = prompt.lower()
    prompt_tokens = set(_tokenize(prompt))

    forced_tiles = {"tile", "tiles", "tiled", "tiling", "seamless", "repeat", "repeatable"}
    if prompt_tokens.intersection(forced_tiles):
        if "tiles" in definitions:
            return "tiles"

    scored: List[Tuple[str, int]] = []
    for graphic_type, description in definitions.items():
        score = 0
        candidate_tokens = set(_tokenize(graphic_type)) | set(_tokenize(description))
        candidate_tokens = {token for token in candidate_tokens if len(token) >= 4}

        for token in candidate_tokens:
            if token in prompt_tokens:
                score += 2
            elif token in prompt_lower:
                score += 1

        scored.append((graphic_type, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    best_type, best_score = scored[0]

    if best_score <= 0:
        if "standalone" in definitions:
            return "standalone"
        if "anchors" in definitions:
            return "anchors"
        return best_type

    return best_type


def _slugify_prompt(prompt: str, max_words: int = 8) -> str:
    words = _tokenize(prompt)
    if not words:
        return "specimen"
    return "-".join(words[:max_words])[:80].strip("-") or "specimen"


def _resolve_run_output_dir(prompt: str, graphic_type_override: Optional[str] = None) -> Tuple[str, Path]:
    definitions = _load_graphic_type_definitions()
    override = (graphic_type_override or "").strip().lower()
    if override == "anchors":
        override = "standalone"
    graphic_type = override if override in definitions else _classify_graphic_type(prompt)
    root = _graphics_root_dir()
    type_dir = root / graphic_type
    type_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = _slugify_prompt(prompt)
    run_dir = type_dir / f"{stamp}__{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return graphic_type, run_dir


def _write_prompt_file(
    run_dir: Path,
    prompt: str,
    negative_prompt: str,
    payload: Dict[str, Any],
) -> None:
    prompt_file = run_dir / "prompt.txt"
    lines = [
        f"prompt: {prompt}",
        f"negative_prompt: {negative_prompt}",
        "",
        "parameters:",
        json.dumps(payload, indent=2),
        "",
    ]
    prompt_file.write_text("\n".join(lines), encoding="utf-8")


def _round_to_64(value: int) -> int:
    return max(64, (value // 64) * 64)


def _get_flux_workflow(
    prompt: str,
    width: int,
    height: int,
    steps: int,
    seed: int,
    model_name: str = "flux1-schnell-fp8.safetensors",
    clip_name: str = "clip_l.safetensors",
    t5_name: str = "t5xxl_fp8_e4m3fn.safetensors",
    vae_name: str = "ae.safetensors",
) -> Dict[str, Any]:
    # Specialized FLUX.1 Schnell workflow for ComfyUI API (Low-VRAM optimized)
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": model_name, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": clip_name,
                "clip_name2": t5_name,
                "type": "flux",
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": prompt},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": _round_to_64(height),
                "width": _round_to_64(width),
            },
        },
        "5": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "guider": ["6", 0],
                "latent_image": ["4", 0],
                "noise": ["7", 0],
                "sampler": ["8", 0],
                "sigmas": ["9", 0],
            },
        },
        "6": {
            "class_type": "BasicGuider",
            "inputs": {"conditioning": ["3", 0]},
        },
        "7": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed if seed >= 0 else int(uuid.uuid4().int >> 96)},
        },
        "8": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "9": {
            "class_type": "FluxDirectAlphaSchedule",
            "inputs": {
                "denoise": 1.0,
                "max_shift": 1.15,
                "model": ["1", 0],
                "steps": steps,
            },
        },
        "10": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["10", 0]},
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "FluxSpecimen", "images": ["11", 0]},
        },
    }


def _get_default_workflow(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    cfg_scale: float,
    sampler_name: str,
    seed: int,
    batch_size: int,
    ckpt_name: str = "v1-5-pruned-emaonly.safetensors",
) -> Dict[str, Any]:
    # Standard SD 1.5 / SDXL workflow structure for ComfyUI API
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": cfg_scale,
                "denoise": 1,
                "latent_image": ["5", 0],
                "model": ["4", 0],
                "negative": ["7", 0],
                "positive": ["6", 0],
                "sampler_name": sampler_name.lower().replace(" ", "_"),
                "scheduler": "normal",
                "seed": seed if seed >= 0 else int(uuid.uuid4().int >> 96),
                "steps": steps,
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt_name},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": batch_size,
                "height": _round_to_64(height),
                "width": _round_to_64(width),
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": prompt},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["4", 1], "text": negative_prompt},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "LoomSpecimen", "images": ["8", 0]},
        },
    }


def _queue_prompt(base_url: str, prompt_workflow: Dict[str, Any]) -> str:
    url = _build_comfy_url(base_url, "prompt")
    payload = {"prompt": prompt_workflow, "client_id": str(uuid.uuid4())}
    res = _http_json(url, "POST", payload)
    return res.get("prompt_id", "")


def _poll_history(base_url: str, prompt_id: str, timeout: int) -> Optional[Dict[str, Any]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        url = _build_comfy_url(base_url, f"history/{prompt_id}")
        history = _http_json(url, "GET")
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(2)
    return None


def generate_specimen_image(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    sampler_name: str = "euler_ancestral",
    seed: int = -1,
    batch_size: int = 1,
    n_iter: int = 1,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    auto_start: Optional[bool] = None,
    auto_fallback_on_oom: Optional[bool] = None,
    graphic_type_override: Optional[str] = None,
    model_type: str = "sd15",  # Options: "sd15", "sdxl", "flux"
) -> Dict[str, Any]:
    """
    Sends a prompt to ComfyUI API and saves generated image(s).
    """
    if not prompt or not prompt.strip():
        return {
            "ok": False,
            "files": [],
            "message": "[SYSTEM_ERROR]: Empty prompt is not allowed.",
            "info": {},
        }

    resolved_base_url = (base_url or os.getenv("COMFYUI_URL") or "http://127.0.0.1:8188").strip()
    resolved_timeout = timeout or int(os.getenv("COMFYUI_TIMEOUT", "300"))

    uplink_ok, uplink_status = initialize_comfy_uplink(
        base_url=resolved_base_url,
        timeout=resolved_timeout,
        auto_start=auto_start,
    )
    if not uplink_ok:
        return {
            "ok": False,
            "files": [],
            "message": uplink_status,
            "info": {},
        }

    # Model selection from env or default based on model_type
    ckpt_name = os.getenv("COMFYUI_CKPT")
    if not ckpt_name:
        if model_type == "flux":
            ckpt_name = "flux1-schnell-fp8.safetensors"
        elif model_type == "sdxl":
            ckpt_name = "sd_xl_base_1.0.safetensors"
        else:
            ckpt_name = "v1-5-pruned-emaonly.safetensors"

    if model_type == "flux":
        workflow = _get_flux_workflow(
            prompt=prompt,
            width=width,
            height=height,
            steps=steps or 4,  # Schnell usually only needs 4 steps
            seed=seed,
            model_name=ckpt_name,
        )
    else:
        workflow = _get_default_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            sampler_name=sampler_name,
            seed=seed,
            batch_size=batch_size,
            ckpt_name=ckpt_name,
        )

    try:
        prompt_id = _queue_prompt(resolved_base_url, workflow)
        if not prompt_id:
            return {
                "ok": False,
                "files": [],
                "message": "[SYSTEM_ERROR]: Failed to queue prompt in ComfyUI.",
                "info": {},
            }

        history = _poll_history(resolved_base_url, prompt_id, resolved_timeout)
        if not history:
            return {
                "ok": False,
                "files": [],
                "message": "[SYSTEM_ERROR]: Timed out waiting for ComfyUI task completion.",
                "info": {},
            }

        # Retrieve images from history
        saved_files: List[str] = []
        outputs = history.get("outputs", {})
        
        graphic_type, output_dir = _resolve_run_output_dir(
            prompt,
            graphic_type_override=graphic_type_override,
        )

        for node_id, output in outputs.items():
            if "images" in output:
                for img_info in output["images"]:
                    filename = img_info["filename"]
                    subfolder = img_info["subfolder"]
                    img_type = img_info["type"]
                    
                    # Fetch binary from /view
                    view_url = _build_comfy_url(
                        resolved_base_url, 
                        f"view?filename={filename}&subfolder={subfolder}&type={img_type}"
                    )
                    
                    req = request.Request(view_url)
                    with request.urlopen(req) as response:
                        img_data = response.read()
                        
                    file_path = output_dir / f"specimen_{prompt_id}_{filename}"
                    file_path.write_bytes(img_data)
                    saved_files.append(str(file_path))

        _write_prompt_file(output_dir, prompt, negative_prompt, workflow)

        return {
            "ok": True,
            "files": saved_files,
            "message": f"[SYSTEM_LOG]: Generated {len(saved_files)} specimen image(s) via ComfyUI.",
            "info": history,
        }

    except Exception as exc:
        return {
            "ok": False,
            "files": [],
            "message": f"[SYSTEM_ERROR]: ComfyUI generation failed: {exc}",
            "info": {},
        }


if __name__ == "__main__":
    sample_prompt = (
        "Industrial Noir textile pattern, obsidian field with phosphor green circuit anchors, "
        "high-detail technical weave, seamless tile"
    )

    use_flux = os.getenv("USE_FLUX", "0") in {"1", "true", "yes"}
    model_type = "flux" if use_flux else "sd15"

    healthy, status = initialize_comfy_uplink()
    print(status)
    if healthy:
        result = generate_specimen_image(
            prompt=sample_prompt,
            model_type=model_type,
            width=1024 if use_flux else 512,
            height=1024 if use_flux else 512,
            steps=4 if use_flux else 20
        )
        print(result["message"])
        for file_path in result["files"]:
            print(f"[SYSTEM_LOG]: {file_path}")
