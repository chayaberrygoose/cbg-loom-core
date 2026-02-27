# [FILE_ID]: scripts/generate_sd_image.py // VERSION: 1.0 // STATUS: STABLE

import argparse
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(repo_root)

from agents.skills.stable_diffusion_skill import initialize_diffusion_uplink, generate_specimen_image


QUALITY_PRESETS = {
    "safe": {"width": 320, "height": 320, "steps": 6},
    "balanced": {"width": 384, "height": 384, "steps": 8},
}

GRAPHIC_TYPES = ["standalone", "logos", "textures", "tiles"]

STYLE_PRESETS = {
    "none": {
        "prompt_suffix": "",
        "negative": "",
        "cfg_scale": 7.0,
        "sampler": "Euler a",
        "default_type": "auto",
    },
    "realism": {
        "prompt_suffix": "photorealistic, realistic lighting, detailed materials, natural color grading",
        "negative": "cartoon, anime, illustration, painting, drawing, cgi, 3d render, lowres, blurry, deformed, bad anatomy",
        "cfg_scale": 6.5,
        "sampler": "Euler a",
        "default_type": "auto",
    },
    "textile": {
        "prompt_suffix": "seamless tileable textile pattern, uniform repeat, edge-to-edge pattern swatch, surface design",
        "negative": "single centered object, logo, text, letters, watermark, portrait, scene, perspective, border frame",
        "cfg_scale": 6.5,
        "sampler": "Euler a",
        "default_type": "tiles",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate image(s) through Stable Diffusion WebUI API")
    parser.add_argument("prompt", help="Prompt text sent to txt2img")
    parser.add_argument("--negative", default="", help="Negative prompt")
    parser.add_argument(
        "--type",
        choices=["auto", *GRAPHIC_TYPES],
        default="auto",
        help="Output graphic type folder (auto uses README-based classification)",
    )
    parser.add_argument(
        "--style",
        choices=sorted(STYLE_PRESETS.keys()),
        default="none",
        help="Optional style preset (realism tuned for current VRAM limits)",
    )
    parser.add_argument("--quality", choices=sorted(QUALITY_PRESETS.keys()), default="safe", help="Preset profile for resolution/steps")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--cfg", type=float, default=None, dest="cfg_scale")
    parser.add_argument("--sampler", default=None)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--n-iter", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preset = QUALITY_PRESETS[args.quality]
    style_preset = STYLE_PRESETS[args.style]

    resolved_width = args.width if args.width is not None else preset["width"]
    resolved_height = args.height if args.height is not None else preset["height"]
    resolved_steps = args.steps if args.steps is not None else preset["steps"]
    resolved_cfg = args.cfg_scale if args.cfg_scale is not None else style_preset["cfg_scale"]
    resolved_sampler = args.sampler if args.sampler is not None else style_preset["sampler"]

    resolved_prompt = args.prompt
    if style_preset["prompt_suffix"]:
        resolved_prompt = f"{resolved_prompt}, {style_preset['prompt_suffix']}"

    resolved_negative = args.negative
    if style_preset["negative"]:
        resolved_negative = (
            f"{resolved_negative}, {style_preset['negative']}"
            if resolved_negative
            else style_preset["negative"]
        )

    resolved_type = args.type
    if resolved_type == "auto" and style_preset.get("default_type") == "tiles":
        resolved_type = "tiles"

    ok, status = initialize_diffusion_uplink()
    print(status)
    if not ok:
        return 1

    result = generate_specimen_image(
        prompt=resolved_prompt,
        negative_prompt=resolved_negative,
        width=resolved_width,
        height=resolved_height,
        steps=resolved_steps,
        cfg_scale=resolved_cfg,
        sampler_name=resolved_sampler,
        seed=args.seed,
        batch_size=args.batch_size,
        n_iter=args.n_iter,
        graphic_type_override=None if resolved_type == "auto" else resolved_type,
    )

    print(result["message"])
    for file_path in result.get("files", []):
        print(file_path)

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
