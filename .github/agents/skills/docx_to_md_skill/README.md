# docx_to_md Skill

Lightweight skill to convert `.docx` files to Markdown (`.md`).

Location

The skill is now located at `.github/agents/skills/docx_to_md_skill/docx_to_md_skill.py`.

Usage

Run from the workspace root:

```bash
python3 .github/agents/skills/docx_to_md_skill/docx_to_md_skill.py --input artifacts/chathistories --output artifacts/chathistories_md
```

Notes

- If `pandoc` is installed the skill will use it automatically (preferred). `pandoc` preserves headings, tables and lists and extracts images.
- All images are consolidated into a single `media/` folder inside the output directory. The skill avoids filename collisions by prefixing duplicates with the document stem.
- Filenames and the top-level heading are prefixed with the document timestamp (creation time where available, otherwise modification time) in the format `YYYYMMDD HH:MM:SS`.
- The skill is incremental: it skips `.docx` files that already have a corresponding `.md` in the output directory.
