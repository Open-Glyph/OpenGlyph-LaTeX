#!/usr/bin/env python3
"""Verify every bundled mapping and actual outline; not scholarly acceptance."""
from pathlib import Path
import argparse
import hashlib
import json
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

def verify(folder):
    folder=Path(folder);manifest=json.loads((folder/'manifest.json').read_text())
    path=folder/manifest['font_file'];sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if sha!=manifest['font_sha256']:raise ValueError('Font checksum mismatch')
    rows=manifest['glyphs'];ids=[r['id'] for r in rows];cps=[r['codepoint'] for r in rows]
    if len(ids)!=len(set(ids)) or len(cps)!=len(set(cps)):raise ValueError('Duplicate ID/address')
    source=(folder/'catalog.tex').read_text();checked=0
    with TTFont(path) as font:
        cmap=font.getBestCmap();gs=font.getGlyphSet()
        for row in rows:
            cp=row['codepoint'];name=cmap.get(cp)
            if not name or name=='.notdef':raise ValueError('Missing cmap: '+row['id'])
            pen=BoundsPen(gs);gs[name].draw(pen)
            if not pen.bounds or pen.bounds[0]>=pen.bounds[2] or pen.bounds[1]>=pen.bounds[3]:raise ValueError('Blank outline: '+row['id'])
            line='\\OpenGlyphDeclare{'+row['alias']+'}{'+manifest['namespace']+'}{'+f'{cp:04X}'+'}'
            if line not in source and line.replace('\\OpenGlyphDeclare{','\\OpenGlyphDeclareEntry{') not in source:raise ValueError('TeX/font mapping mismatch: '+row['id'])
            checked+=1
        if any(t in font for t in ('SVG ','sbix','CBDT')):raise ValueError('Unexpected image font')
    return dict(glyphs=checked,all_cmap_and_outline_entries_present=True,font_sha256=sha,not_scholarly_acceptance=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle');args=p.parse_args()
    print(json.dumps(verify(args.bundle),indent=2))
