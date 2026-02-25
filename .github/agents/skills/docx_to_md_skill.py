/* [FILE_ID]: DOCX_TO_MD_SKILL // VERSION: 1.1 // STATUS: STABLE */
#!/usr/bin/env python3
"""Skill: Convert .docx files to Markdown

Usage:
  python3 docx_to_md_skill.py --input /path/to/docx_dir --output /path/to/md_out

This is a lightweight fallback converter that does not require external packages.
It creates empty `.md` placeholders for empty or unreadable `.docx` files.
"""
import argparse
import zipfile
import xml.etree.ElementTree as ET
import shutil
import subprocess
import os
from datetime import datetime
from pathlib import Path

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def extract_text_from_paragraph(p):
    texts = []
    for node in p.findall('.//w:r', NS):
        for t in node.findall('w:t', NS):
            if t.text:
                texts.append(t.text)
        for br in node.findall('w:br', NS):
            texts.append('\n')
    return ''.join(texts).strip()


def para_is_list(p):
    return p.find('.//w:numPr', NS) is not None


def para_style(p):
    st = p.find('.//w:pPr/w:pStyle', NS)
    if st is not None:
        return st.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
    return None


def convert_docx_to_md(docx_path: Path, out_path: Path) -> bool:
    # If pandoc is available, prefer it for higher-fidelity conversion and media extraction
    pandoc = shutil.which('pandoc')
    if pandoc:
        try:
            # Use a single shared media folder inside the output directory
            shared_media = out_path.parent / 'media'
            shared_media.mkdir(parents=True, exist_ok=True)
            # Ask pandoc to extract media into a temporary per-file folder, we'll consolidate afterwards
            temp_media = out_path.parent / f"{docx_path.stem}_media"
            temp_media.mkdir(parents=True, exist_ok=True)
            cmd = [pandoc, '-s', str(docx_path), '-t', 'gfm', '-o', str(out_path), '--extract-media', str(temp_media)]
            res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Move extracted media into shared_media, avoiding name collisions
            for root, dirs, files in os.walk(str(temp_media)):
                for fname in files:
                    src = Path(root) / fname
                    dest = shared_media / fname
                    if dest.exists():
                        # avoid collision
                        dest = shared_media / (f"{docx_path.stem}_" + fname)
                    shutil.move(str(src), str(dest))
            # remove the temporary media folder (empty dirs)
            try:
                shutil.rmtree(str(temp_media))
            except Exception:
                pass
            # update image links in the generated markdown to point to the shared media folder
            try:
                text = out_path.read_text(encoding='utf-8')
                # pandoc typically prefixes media links with '<stem>_media/' when using per-file folders
                text = text.replace(f"{docx_path.stem}_media/", "media/")
                out_path.write_text(text, encoding='utf-8')
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[WARN] pandoc failed for {docx_path.name}: {e}")
            # fall through to lightweight fallback

    try:
        if docx_path.stat().st_size == 0:
            out_path.write_text('', encoding='utf-8')
            return True
        with zipfile.ZipFile(docx_path) as zf:
            xml = zf.read('word/document.xml')
    except Exception as e:
        print(f"[WARN] Failed to read {docx_path.name}: {e}")
        try:
            out_path.write_text('', encoding='utf-8')
            return True
        except Exception:
            return False

    root = ET.fromstring(xml)
    paras = root.findall('.//w:body/w:p', NS)
    md_lines = []

    for p in paras:
        text = extract_text_from_paragraph(p)
        if not text:
            continue
        style = para_style(p)
        if style and style.lower().startswith('heading'):
            digits = ''.join(c for c in style if c.isdigit())
            level = int(digits) if digits.isdigit() else 1
            md_lines.append('#' * level + ' ' + text)
        elif para_is_list(p):
            lines = text.split('\n')
            for ln in lines:
                if ln.strip():
                    md_lines.append('- ' + ln.strip())
        else:
            md_lines.append(text)

    md = '\n\n'.join(md_lines).strip() + '\n'
    out_path.write_text(md, encoding='utf-8')
    return True


def timestamp_for_path(p: Path) -> str:
    st = p.stat()
    # Prefer creation time if available, otherwise modification time
    ts = None
    if hasattr(st, 'st_birthtime'):
        ts = st.st_birthtime
    else:
        ts = st.st_mtime
    return datetime.fromtimestamp(ts).strftime('%Y%m%d %H:%M:%S')


def has_existing_md(output_dir: Path, stem: str) -> bool:
    """Return True if an .md file already exists for the given docx stem.

    Matches both timestamp-prefixed names like `260215 09:48:18 name.md`
    and plain `name.md`.
    """
    for p in output_dir.glob('*.md'):
        if p.name.endswith(f"{stem}.md"):
            return True
    return False


def run(input_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_files = sorted(input_dir.glob('*.docx'))
    if not docx_files:
        print(f'No .docx files found in {input_dir}')
        return
    print(f'Converting {len(docx_files)} files from {input_dir} -> {output_dir}')
    ok = 0
    for f in docx_files:
        # skip conversion if an .md already exists for this docx stem
        if has_existing_md(output_dir, f.stem):
            print(f'[SKIP] {f.name} -> existing markdown found')
            continue

        # create a temporary output path; we'll rename with timestamp after conversion
        temp_out = output_dir / (f.stem + '.md')
        if convert_docx_to_md(f, temp_out):
            # determine timestamp from source file (creation if available, else modified)
            ts = timestamp_for_path(f)
            # prefix top-level heading in the markdown (if present) or insert one
            try:
                txt = temp_out.read_text(encoding='utf-8')
                lines = txt.splitlines()
                if lines and lines[0].lstrip().startswith('#'):
                    # prefix timestamp after hashes
                    hashes, rest = lines[0].split(' ', 1) if ' ' in lines[0] else (lines[0], '')
                    lines[0] = f"{hashes} {ts} {rest}".rstrip()
                else:
                    # insert a level-1 heading with the timestamp and original title
                    title = f.stem
                    lines.insert(0, f"# {ts} {title}")
                temp_out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            except Exception:
                pass

            # rename file to prefix timestamp in filename
            safe_name = f"{ts} {f.stem}.md"
            dest = output_dir / safe_name
            try:
                temp_out.rename(dest)
                print(f'[OK] {f.name} -> {dest.name}')
            except Exception:
                print(f'[OK] {f.name} -> {temp_out.name} (rename failed)')
            ok += 1
        else:
            print(f'[FAIL] {f.name}')
    print(f'Converted {ok}/{len(docx_files)} files')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Convert .docx to Markdown (lightweight)')
    p.add_argument('--input', '-i', type=Path, default=Path(__file__).resolve().parents[2] / 'chathistories')
    p.add_argument('--output', '-o', type=Path, default=Path(__file__).resolve().parents[2] / 'chathistories_md')
    args = p.parse_args()
    run(args.input, args.output)
