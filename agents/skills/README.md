````markdown
# docx_to_md Skill

Lightweight skill to convert `.docx` files to Markdown (`.md`).

Usage

Run from the workspace root:

```bash
python3 agents/skills/docx_to_md_skill/docx_to_md_skill.py --input artifacts/chathistories --output artifacts/chathistories_md
```

Notes

- This script does not require external Python packages.
- For richer conversions (styles, images), consider installing `pandoc` or using `mammoth`.
 - If `pandoc` is installed, the skill will use it automatically. `pandoc` preserves headings, tables, lists and can extract images.

Pandoc example (what the skill runs):

```bash
python3 agents/skills/docx_to_md_skill/docx_to_md_skill.py --input artifacts/chathistories --output artifacts/chathistories_md_pandoc
```

This will create `*.md` files and a `<filename>_media/` folder per document containing extracted images.
With the updated skill, all images are consolidated into a single `media/` folder inside the output directory and filenames/first headings are prefixed with the document timestamp (creation time where available, otherwise modification time) in the format `YYYYMMDD HH:MM:SS` (four-digit year).

Incremental behavior

- The skill now skips any `.docx` that already has a corresponding `.md` in the output directory. This allows you to add new `.docx` files and re-run the skill — only the new documents will be converted. Removing a `.docx` file does not delete its `.md` equivalent.

# Skills Index

*   **[docx_to_md_skill](./docx_to_md_skill/)**: Convert Word documents to Markdown.
*   **[rclone_mount_skill](./rclone_mount_skill/)**: Anchor cloud Archives to the local filesystem.

````
