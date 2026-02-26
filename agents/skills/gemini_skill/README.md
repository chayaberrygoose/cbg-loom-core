# Gemini Skill

This skill provides an interface to the Google Gemini Synthesis Engine (LLM).

## Usage

```python
from agents.skills.gemini_skill import initialize_loom_uplink, generate_specimen_data

model = initialize_loom_uplink()
result = generate_specimen_data(model, "Generate a specimen description for...")
print(result)
```

## Configuration

Requires `GOOGLE_API_KEY` in `.env` or environment variables.

## Protocols

- Adheres to `[NO_NANO_BANANA_GENERATION]` unless overridden with `override` keyword.
