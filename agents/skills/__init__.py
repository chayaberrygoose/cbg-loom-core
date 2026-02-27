# agents.skills package

from .stable_diffusion_skill import initialize_comfy_uplink, generate_specimen_image

__all__ = [
	"initialize_comfy_uplink",
	"generate_specimen_image",
]
