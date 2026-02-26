````chatagent
# Agents read this

## Special Location

If you can see this file, it means you have access to a special location. tHE CBG folder google drive folder that is mounted in a folder on a local filesystem via rclone. 

### Google Drive direct access
It is possible you are a gemini running from a mobile or web app that can access this via google drive directly. In this case, you might only have read-only access, but you can ask to have things placed in the drive for you.

### Local Access
If you are running on the local filesystem, you may have read/write access possibly though copilot or gemini-cli.

## Company info
For information about the company see cbg.md

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
