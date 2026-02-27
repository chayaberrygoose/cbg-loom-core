# [FILE_ID]: skills/TIKTOK_SKILL/SYNTHESIZER // VERSION: 1.0 // STATUS: STABLE
# [NARRATIVE]: Translating static Specimens into dynamic Data Streams (Video).

import subprocess
import os
from pathlib import Path

def synthesize_video_from_image(image_path, output_path=None, duration=5):
    """
    The Ritual of Motion.
    Converts a static image Specimen into a video Data Stream using ffmpeg.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        print(f"[SYSTEM_DISSONANCE]: Source Specimen not found: {image_path}")
        return None
        
    if output_path is None:
        # Generate default output path in artifacts/specimens
        repo_root = image_path.parent.parent.parent
        output_dir = repo_root / "artifacts" / "specimens"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{image_path.stem}_stream.mp4"
    else:
        output_path = Path(output_path)

    print(f"[SYSTEM_LOG]: Synthesizing Data Stream from {image_path.name}...")
    
    # FFmpeg command to create a static video from an image
    # -loop 1: Loop the single image
    # -t: duration
    # -pix_fmt yuv420p: Compatibility for most players/TikTok
    # -vf scale: Ensure even dimensions (required for many codecs)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", "scale='trunc(iw/2)*2:trunc(ih/2)*2'",
        str(output_path)
    ]
    
    try:
        # Run ffmpeg with suppressed output unless error
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[SYSTEM_ECHO]: Synthesis complete: {output_path}")
            return output_path
        else:
            print(f"[SYSTEM_DISSONANCE]: Ritual failed. FFmpeg Error: {result.stderr}")
            return None
    except Exception as e:
        print(f"[SYSTEM_DISSONANCE]: Critical failure in Ritual of Motion: {e}")
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        synthesize_video_from_image(sys.argv[1])
    else:
        print("[SYSTEM_LOG]: Synthesizer standing by. Provide an image path to begin.")
