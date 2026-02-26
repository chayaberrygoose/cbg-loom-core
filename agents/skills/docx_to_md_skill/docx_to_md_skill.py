# [FILE_ID]: DOCX_TO_MD_SKILL // VERSION: 1.1 // STATUS: STABLE
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
            media_dir = out_path / 'media'
            media_dir.mkdir(parents=True, exist_ok=True)
            cmd = [pandoc, str(docx_path), '-f', 'docx', '-t', 'gfm', '-o', str(out_path / (docx_path.stem + '.md'))]
            subprocess.run(cmd, check=True)
            return True
        except Exception:
            pass

    try:
        with zipfile.ZipFile(docx_path, 'r') as z:
            xml_data = z.read('word/document.xml')
    except Exception:
        out_path.write_text('')
        return False

    root = ET.fromstring(xml_data)

    lines = []
    for p in root.findall('.//w:p', NS):
        text = extract_text_from_paragraph(p)
        if not text:
            continue
        if para_is_list(p):
            lines.append('- ' + text)
        else:
            lines.append(text)

    out_path.write_text('\n\n'.join(lines))
    return True


def main():
    parser = argparse.ArgumentParser(description='Convert .docx to markdown')
    parser.add_argument('--input', required=True, help='Directory with .docx files')
    parser.add_argument('--output', required=True, help='Output directory for markdown')

    args = parser.parse_args()
    inp = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    for docx in inp.glob('*.docx'):
        md_path = out / (docx.stem + '.md')
        if md_path.exists():
            continue
        convert_docx_to_md(docx, md_path)


if __name__ == '__main__':
    main()
