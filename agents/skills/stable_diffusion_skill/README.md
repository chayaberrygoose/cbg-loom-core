# Stable Diffusion Skill

Agent skill for sending prompt payloads to an Automatic1111 Stable Diffusion WebUI instance over API (`/sdapi/v1/txt2img`).

## Usage

```python
from agents.skills.stable_diffusion_skill import initialize_diffusion_uplink, generate_specimen_image

ok, message = initialize_diffusion_uplink()
print(message)

if ok:
    result = generate_specimen_image(
        prompt="Industrial Noir schematic textile, obsidian + phosphor accents, seamless tile",
        negative_prompt="blurry, low detail",
        width=320,
        height=320,
        steps=6,
        graphic_type_override="tiles",  # optional: standalone|textures|tiles
    )
    print(result["message"])
    print(result["files"])
```

If the API is offline, the skill will auto-start WebUI by default and wait until it becomes reachable.
If a generation request returns CUDA out-of-memory, the skill automatically retries smaller fallback profiles by default.

Outputs are routed into `artifacts/graphics/<type>/...` based on graphic type definitions in `artifacts/graphics/README.md`.
Each generation run creates a subfolder that includes generated image file(s) and `prompt.txt` containing the prompt and parameters.
You can force the type explicitly using `graphic_type_override`.

CLI note: `scripts/generate_sd_image.py` supports `--type auto|standalone|textures|tiles` (default: `auto`).

Style notes:
- `--style realism` for photoreal scenes.
- `--style textile` for repeatable fabric/surface patterns; with `--type auto`, this style routes output to `tiles` by default.

Example:

```bash
python3 scripts/generate_sd_image.py "photorealistic office tower at dusk" --style realism --type standalone --quality safe
```

```bash
python3 scripts/generate_sd_image.py "paisley floral repeat with clean linework" --style textile --type auto --quality safe
```

## Environment Variables

- `SD_WEBUI_URL` (default: `http://127.0.0.1:7860`)
- `SD_WEBUI_TIMEOUT` (default: `180` seconds)
- `SD_WEBUI_AUTH` (optional basic auth as `username:password`)
- `SD_GRAPHICS_README` (default: `artifacts/graphics/README.md`)
- `SD_GRAPHICS_ROOT` (default: `artifacts/graphics`)
- `SD_WEBUI_AUTO_START` (default: `1`)
- `SD_WEBUI_DIR` (default: `~/repos/stable-diffusion-webui`)
- `SD_WEBUI_START_CMD` (default: `./webui.sh --api`)
- `SD_WEBUI_START_TIMEOUT` (default: `240` seconds)
- `SD_WEBUI_START_LOG` (default: `artifacts/generated/stable-diffusion/webui.log`)
- `SD_WEBUI_AUTO_FALLBACK_OOM` (default: `1`)

## WebUI Requirement

Run WebUI with API enabled:

```bash
./webui.sh --api
```
