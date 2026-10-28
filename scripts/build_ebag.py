#!/usr/bin/env python3
"""Rebuild the bundled ebag_s font solely from the licensed source subset."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time

from oglib.catalog import Catalog,refs,hash_json
from oglib.font import outline,write_font
from oglib.kage import KageRenderer
from oglib.project import catalog_tex

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('-o','--output',default='build/ebag');args=p.parse_args()
    output=Path(args.output).resolve()
    if output.exists():raise ValueError('Use a fresh output directory')
    source=ROOT/'data/glyphwiki-ebag.kage.jsonl.gz';catalog=Catalog(source)
    names=sorted(n for n in catalog.table if n.startswith('ebag_s') and '@' not in n)
    address_file=ROOT/'data/ebag-addresses.json'
    addresses=json.loads(address_file.read_text())['addresses'] if address_file.exists() else {}
    if len(addresses)!=len(set(addresses.values())) or any(type(cp) is not int or not 0xF0000<=cp<=0xFFFFD for cp in addresses.values()):
        raise ValueError('Invalid permanent ebag address registry')
    used=set(addresses.values());free=(cp for cp in range(0xF0000,0xFFFFE) if cp not in used)
    for name in names:
        key=name.removeprefix('ebag_')
        if key not in addresses:addresses[key]=next(free)
    renderer=KageRenderer(str(ROOT/'vendor/kage-engine'));rows={};meta=[];errors=[];start=time.perf_counter()
    for offset in range(0,len(names),300):
        batch=names[offset:offset+300]
        rendered=renderer.render([dict(key=n,name=n) for n in batch],catalog.table,curve=True,strict_versions=True)
        for index,name in enumerate(batch,offset):
            try:
                svg=rendered.get(name)
                if not svg:raise ValueError('KAGE failed to render the complete program')
                record=outline(svg);key=name.removeprefix('ebag_');cp=addresses[key]
                rows[key]={**record,'codepoint':cp}
                closure=catalog.resolve(name)
                meta.append(dict(id=key,alias='ebag:'+key,codepoint=cp,hex=f'U+{cp:05X}',
                    glyphwiki_name=name,source_url='https://glyphwiki.org/wiki/'+name,
                    closure_sha256=closure['closure_sha256'],outline_sha256=record['outline_sha256'],
                    components=sorted(set(n for n in closure['table'] if n!=name)),
                    unicode_identity_verified=False,source_equivalence_verified=False))
            except Exception as exc:errors.append(dict(name=name,type=type(exc).__name__,message=str(exc)))
        if offset%1500==0 or offset+300>=len(names):
            print(json.dumps(dict(completed=min(offset+300,len(names)),total=len(names),errors=len(errors),seconds=round(time.perf_counter()-start,2))),flush=True)
    output.mkdir(parents=True,exist_ok=False)
    if errors:
        (output/'errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
        raise ValueError('Cannot publish an incomplete font; see errors.json')
    license_text=(ROOT/'licenses/GlyphWiki.txt').read_text(encoding='utf-8-sig')
    filename='OpenGlyphEbag.otf'
    font_sha=write_font(rows,output/filename,'OpenGlyphEbag-0.1.0',license_text=license_text,license_url='https://glyphwiki.org/')
    (output/'catalog.tex').write_text(catalog_tex('ebag',filename,{k:r['codepoint'] for k,r in rows.items()},trusted_entries=True),encoding='ascii')
    (output/'addresses.json').write_text(json.dumps(dict(schema='openglyph.ebag-addresses.v1',addresses=addresses),sort_keys=True,indent=2)+'\n',encoding='utf-8')
    report=dict(schema='openglyph.bundle.v1',version='0.1.0',namespace='ebag',font_file=filename,font_sha256=font_sha,
        glyph_count=len(rows),glyphs=meta,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        pua_scope='Supplementary PUA-A, project addresses only; not SEAL legacy addresses or standard Unicode identity',
        source_equivalence_verified=False,review_policy='human scholarly review; compilation is not acceptance',
        generated_from='GlyphWiki ebag_s snapshot and pinned component dependencies',seconds=time.perf_counter()-start)
    (output/'manifest.json').write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    (output/'README.md').write_text('# ebag_s font bundle\n\n22,583 GlyphWiki source glyphs, preserving their IDs.\n'
        'Font addresses are local PUA-A, not global character identity or SEAL legacy codes.\n'
        'Use \\OpenGlyphLoad{ebag} and \\ebag{s030-067}.\n'
        'See ../licenses/GlyphWiki.txt and ../THIRD-PARTY-NOTICES.md.\n',encoding='utf-8')
    print(json.dumps(dict(font=str(output/filename),glyphs=len(rows),bytes=(output/filename).stat().st_size,seconds=time.perf_counter()-start)),flush=True)

if __name__=='__main__':main()
