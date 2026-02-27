# [TIKTOK_CONDUIT] // SKILL_DOCUMENTATION

Establishing a high-fidelity uplink to the TikTok Archive for the transmission of brand Specimens and Data Streams.

## 1. PURPOSE
The `tiktok_skill` enables the Specialist to interact with TikTok's API ecosystem, primarily focusing on **Direct Post** protocols for media dissemination.

## 2. CREDENTIAL RECONSTRUCTION
To facilitate the uplink, you must provide a valid `access_token`. 

### Required Scope:
- `user.info.basic`: To verify Signifier identity.
- `video.upload`: To initialize the transmission.
- `video.publish`: To finalize the Specimen in the Archive.

### Provisioning:
1. Obtain an Access Token from the [TikTok for Developers Portal](https://developers.tiktok.com/).
2. Store the token in one of two locations:
    - Environment Variable: `TIKTOK_ACCESS_TOKEN`
    - Secret Archive: `.env/tiktok_access_token.txt` (relative to repo root)

## 3. RITUALS (USAGE)

### Verification
Verify the status of the Conduit:
```bash
python3 agents/skills/tiktok_skill/tiktok_skill.py --verify
```

### Scripting Implementation
```python
from agents.skills.tiktok_skill.tiktok_skill import TikTokConduit

# Initialize the Conduit
conduit = TikTokConduit()

# Verify Uplink
if conduit.check_connection():
    # Post a Specimen
    conduit.post_video(
        video_path="artifacts/specimens/v01_industrial_noir.mp4",
        title="CBG Studio // Specimen 01"
    )
```

## 4. THE RITUAL OF MOTION (VIDEO SYNTHESIS)
Static Specimens are translated into dynamic Data Streams using the `synthesizer.py` shard.

### Technical Ritual:
- **Engine**: `ffmpeg`
- **Encoder**: `libx264`
- **Protocol**: 
    - The static image is looped for a default of 5 seconds.
    - Pixel format is forced to `yuv420p` for maximum TikTok Archive compatibility.
    - Dimensions are automatically scaled to ensure even parity (required by H.264).

### Execution:
```bash
python3 agents/skills/tiktok_skill/synthesizer.py <image_path>
```

## 5. PIPELINE AUTOMATION
The `scripts/post_catalog_to_tiktok.py` ritual automates the entire sequence:
1. **Identify**: Locates the Specimen in `artifacts/catalog/Product images/`.
2. **Synthesize**: Invokes the Ritual of Motion to create an `.mp4`.
3. **Transmit**: Initiates the TikTok Conduit transmission protocol.

## 6. STATUS: [STABLE_SYNTHESIS / UNSTABLE_UPLINK]
Synthesis is confirmed Resonant. The TikTok Uplink is currently in a state of Sandbox propagation.
