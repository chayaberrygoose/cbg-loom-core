````chatagent
# Agents read this

## docx → Markdown Skill

There's a reusable skill for converting `.docx` files in `artifacts/chathistories` to Markdown.

- **Location:** `agents/skills/docx_to_md_skill/docx_to_md_skill.py`
- **Usage:**

```bash
python3 agents/skills/docx_to_md_skill/docx_to_md_skill.py --input artifacts/chathistories --output artifacts/chathistories_md
```

- Notes:
	- If `pandoc` is installed the skill will use it and extract images; images are consolidated into `artifacts/chathistories_md/media/`.
	- Filenames and first heading are prefixed with the document timestamp (`YYYYMMDD HH:MM:SS`).

````
