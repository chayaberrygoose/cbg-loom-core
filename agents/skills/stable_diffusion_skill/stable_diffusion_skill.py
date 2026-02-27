# [FILE_ID]: stable_diffusion_skill/stable_diffusion_skill.py // VERSION: 1.0 // STATUS: STABLE

import base64
import json
import os
import re
import shlex
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import request
from urllib.error import HTTPError, URLError


def _build_webui_url(base_url: str, route: str) -> str:
    return f"{base_url.rstrip('/')}/{route.lstrip('/')}"


def _build_auth_header() -> Dict[str, str]:
    auth = os.getenv("SD_WEBUI_AUTH", "").strip()
    if not auth:
        return {}

    encoded = base64.b64encode(auth.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}


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
        **_build_auth_header(),
    }

    req = request.Request(url=url, data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)


def _api_healthcheck(base_url: str, timeout: int = 5) -> bool:
    try:
        url = _build_webui_url(base_url, "/sdapi/v1/options")
        _http_json(url=url, method="GET", timeout=timeout)
        return True
    except (HTTPError, URLError, TimeoutError, ValueError):
        return False


def _resolve_webui_dir() -> Path:
    default_dir = Path.home() / "repos" / "stable-diffusion-webui"
    return Path(os.getenv("SD_WEBUI_DIR", str(default_dir))).expanduser()


def _sanitize_log_line(line: str, use_tilde_paths: bool) -> str:
    if not use_tilde_paths:
        return line
    home_prefix = str(Path.home())
    return line.replace(home_prefix, "~")


def _stream_webui_output_to_log(
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


def start_diffusion_webui_if_needed(
    base_url: Optional[str] = None,
    startup_timeout: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Starts Stable Diffusion WebUI in the background if API is not reachable.

    Env vars:
    - SD_WEBUI_DIR (default: ~/repos/stable-diffusion-webui)
    - SD_WEBUI_START_CMD (default: ./webui.sh --api)
    - SD_WEBUI_START_TIMEOUT (default: 240)
    - SD_WEBUI_START_LOG (default: artifacts/generated/stable-diffusion/webui.log)
    - SD_WEBUI_LOG_TILDE_PATHS (default: 1)
    """
    resolved_base_url = (base_url or os.getenv("SD_WEBUI_URL") or "http://127.0.0.1:7860").strip()
    resolved_startup_timeout = startup_timeout or int(os.getenv("SD_WEBUI_START_TIMEOUT", "240"))

    if _api_healthcheck(resolved_base_url, timeout=5):
        return True, f"[SYSTEM_LOG]: Diffusion API already online at {resolved_base_url}"

    webui_dir = _resolve_webui_dir()
    if not webui_dir.exists():
        return False, f"[SYSTEM_ERROR]: SD_WEBUI_DIR not found: {webui_dir}"

    command = os.getenv("SD_WEBUI_START_CMD", "./webui.sh --api").strip()
    if not command:
        return False, "[SYSTEM_ERROR]: SD_WEBUI_START_CMD is empty."

    log_path = Path(
        os.getenv(
            "SD_WEBUI_START_LOG",
            str(Path("artifacts") / "generated" / "stable-diffusion" / "webui.log"),
        )
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    use_tilde_paths = os.getenv("SD_WEBUI_LOG_TILDE_PATHS", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    process = subprocess.Popen(
        shlex.split(command),
        cwd=str(webui_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    thread = threading.Thread(
        target=_stream_webui_output_to_log,
        args=(process, log_path, use_tilde_paths),
        daemon=True,
    )
    thread.start()

    deadline = time.time() + resolved_startup_timeout
    while time.time() < deadline:
        if _api_healthcheck(resolved_base_url, timeout=5):
            return True, f"[SYSTEM_LOG]: Diffusion API online at {resolved_base_url}"
        time.sleep(2)

    return False, (
        f"[SYSTEM_ERROR]: Timed out waiting for Diffusion API at {resolved_base_url}. "
        f"Check startup log: {log_path}"
    )


def initialize_diffusion_uplink(
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    auto_start: Optional[bool] = None,
) -> Tuple[bool, str]:
    """
    Validates Stable Diffusion WebUI API connectivity.

    Env vars:
    - SD_WEBUI_URL (default: http://127.0.0.1:7860)
    - SD_WEBUI_TIMEOUT (default: 180)
    - SD_WEBUI_AUTH (optional basic auth string: username:password)
    - SD_WEBUI_AUTO_START (default: 1)
    """
    resolved_base_url = (base_url or os.getenv("SD_WEBUI_URL") or "http://127.0.0.1:7860").strip()
    resolved_timeout = timeout or int(os.getenv("SD_WEBUI_TIMEOUT", "180"))
    resolved_auto_start = (
        auto_start
        if auto_start is not None
        else os.getenv("SD_WEBUI_AUTO_START", "1").strip().lower() in {"1", "true", "yes", "on"}
    )

    if not _api_healthcheck(resolved_base_url, timeout=5) and resolved_auto_start:
        started, status = start_diffusion_webui_if_needed(base_url=resolved_base_url)
        if not started:
            return False, status

    try:
        url = _build_webui_url(resolved_base_url, "/sdapi/v1/options")
        _http_json(url=url, method="GET", timeout=resolved_timeout)
        return True, f"[SYSTEM_LOG]: Diffusion Uplink Established at {resolved_base_url}"
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return False, f"[SYSTEM_ERROR]: Diffusion Uplink failed: {exc}"


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


def _build_oom_fallback_ladder(width: int, height: int, steps: int) -> List[Tuple[int, int, int]]:
    rung_1 = (
        min(max(_round_to_64(width), 256), 384),
        min(max(_round_to_64(height), 256), 384),
        min(max(steps, 4), 8),
    )
    rung_2 = (
        min(max(_round_to_64(width), 256), 320),
        min(max(_round_to_64(height), 256), 320),
        min(max(steps, 4), 6),
    )
    rung_3 = (256, 256, min(max(steps, 4), 6))
    rung_4 = (256, 256, 4)
    return [rung_1, rung_2, rung_3, rung_4]


def _txt2img_request(
    base_url: str,
    payload: Dict[str, Any],
    timeout: int,
) -> Tuple[Optional[Dict[str, Any]], str, bool]:
    txt2img_url = _build_webui_url(base_url, "/sdapi/v1/txt2img")
    try:
        response = _http_json(
            url=txt2img_url,
            method="POST",
            payload=payload,
            timeout=timeout,
        )
        return response, "", False
    except HTTPError as exc:
        error_payload = ""
        error_text = str(exc)
        try:
            error_payload = exc.read().decode("utf-8", errors="ignore")
            parsed = json.loads(error_payload) if error_payload else {}
            if isinstance(parsed, dict):
                error_text = parsed.get("errors") or parsed.get("error") or error_payload or error_text
            elif error_payload:
                error_text = error_payload
        except Exception:
            pass

        combined = f"{error_text} {error_payload}".lower()
        is_oom = "outofmemoryerror" in combined or "cuda out of memory" in combined
        return None, error_text, is_oom
    except (URLError, TimeoutError, ValueError) as exc:
        return None, str(exc), False


def generate_specimen_image(
    prompt: str,
    negative_prompt: str = "",
    width: int = 320,
    height: int = 320,
    steps: int = 6,
    cfg_scale: float = 7.0,
    sampler_name: str = "Euler a",
    seed: int = -1,
    batch_size: int = 1,
    n_iter: int = 1,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    auto_start: Optional[bool] = None,
    auto_fallback_on_oom: Optional[bool] = None,
    graphic_type_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends a txt2img prompt to Stable Diffusion WebUI API and saves generated image(s).

    Returns:
      {
        "ok": bool,
        "files": ["/path/to/image.png", ...],
        "message": str,
        "info": dict | str
      }
    """
    if not prompt or not prompt.strip():
        return {
            "ok": False,
            "files": [],
            "message": "[SYSTEM_ERROR]: Empty prompt is not allowed.",
            "info": {},
        }

    resolved_base_url = (base_url or os.getenv("SD_WEBUI_URL") or "http://127.0.0.1:7860").strip()
    resolved_timeout = timeout or int(os.getenv("SD_WEBUI_TIMEOUT", "180"))
    resolved_auto_fallback_on_oom = (
        auto_fallback_on_oom
        if auto_fallback_on_oom is not None
        else os.getenv("SD_WEBUI_AUTO_FALLBACK_OOM", "1").strip().lower() in {"1", "true", "yes", "on"}
    )

    uplink_ok, uplink_status = initialize_diffusion_uplink(
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

    attempt_dims: List[Tuple[int, int, int]] = [(width, height, steps)]
    if resolved_auto_fallback_on_oom:
        attempt_dims.extend(_build_oom_fallback_ladder(width=width, height=height, steps=steps))

    unique_attempts: List[Tuple[int, int, int]] = []
    for dims in attempt_dims:
        if dims not in unique_attempts:
            unique_attempts.append(dims)

    last_error = ""
    last_info: Any = {}

    for attempt_index, (attempt_width, attempt_height, attempt_steps) in enumerate(unique_attempts, start=1):
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": attempt_width,
            "height": attempt_height,
            "steps": attempt_steps,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
            "seed": seed,
            "batch_size": batch_size,
            "n_iter": n_iter,
        }

        response, error_text, is_oom = _txt2img_request(
            base_url=resolved_base_url,
            payload=payload,
            timeout=resolved_timeout,
        )

        if response is None:
            last_error = error_text
            if is_oom and resolved_auto_fallback_on_oom and attempt_index < len(unique_attempts):
                continue
            return {
                "ok": False,
                "files": [],
                "message": f"[SYSTEM_ERROR]: txt2img request failed: {error_text}",
                "info": {},
            }

        image_blobs = response.get("images", [])
        if not image_blobs:
            last_info = response.get("info", {})
            return {
                "ok": False,
                "files": [],
                "message": "[SYSTEM_ERROR]: txt2img returned no images.",
                "info": last_info,
            }

        graphic_type, output_dir = _resolve_run_output_dir(
            prompt,
            graphic_type_override=graphic_type_override,
        )
        _write_prompt_file(
            run_dir=output_dir,
            prompt=prompt,
            negative_prompt=negative_prompt,
            payload=payload,
        )

        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        saved_files: List[str] = []

        for index, image_b64 in enumerate(image_blobs, start=1):
            image_bytes = _decode_b64_image(image_b64)
            file_name = f"specimen_{stamp}_{index:02d}.png"
            file_path = output_dir / file_name
            file_path.write_bytes(image_bytes)
            saved_files.append(str(file_path))

        parsed_info: Any = response.get("info", {})
        if isinstance(parsed_info, str):
            try:
                parsed_info = json.loads(parsed_info)
            except json.JSONDecodeError:
                pass

        fallback_note = ""
        if attempt_index > 1:
            fallback_note = (
                f" Fallback profile used: {attempt_width}x{attempt_height} @ {attempt_steps} steps."
            )

        return {
            "ok": True,
            "files": saved_files,
            "message": f"[SYSTEM_LOG]: Generated {len(saved_files)} specimen image(s) in {graphic_type}/{output_dir.name}.{fallback_note}",
            "info": parsed_info,
        }

    return {
        "ok": False,
        "files": [],
        "message": f"[SYSTEM_ERROR]: txt2img failed after fallback attempts. Last error: {last_error}",
        "info": last_info,
    }


if __name__ == "__main__":
    sample_prompt = (
        "Industrial Noir textile pattern, obsidian field with phosphor green circuit anchors, "
        "high-detail technical weave, seamless tile"
    )

    healthy, status = initialize_diffusion_uplink()
    print(status)
    if healthy:
        result = generate_specimen_image(prompt=sample_prompt)
        print(result["message"])
        for file_path in result["files"]:
            print(f"[SYSTEM_LOG]: {file_path}")
