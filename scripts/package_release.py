#!/usr/bin/env python3
"""Create reproducible source and paper-ready ZIPs, no credentials or caches."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0'
EXCLUDE={'.git','build','dist','__pycache__','.venv'}
SUFFIXES={'.aux','.log','.out','.toc','.xdv','.pyc','.fls','.fdb_latexmk'}

def archive(path,items,prefix=''):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for relative,file in sorted(items):
            name=prefix+relative
            if name.startswith('/') or '..' in Path(name).parts:raise ValueError('Unsafe archive entry')
            info=zipfile.ZipInfo(name,date_time=(2026,10,28,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16;z.writestr(info,file.read_bytes())

def main():
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    required=['openglyph.sty','ebag/OpenGlyphEbag.otf','ebag/catalog.tex','data/glyphwiki-ebag.kage.jsonl.gz',
        'data/ebag-addresses.json','licenses/GlyphWiki.txt','vendor/kage-engine/COPYING','main.pdf','doc/openglyph-doc.pdf']
    for name in required:
        if not (ROOT/name).is_file():raise ValueError('Release lacks '+name)
    items=[]
    for file in ROOT.rglob('*'):
        rel=file.relative_to(ROOT)
        if not file.is_file() or any(part in EXCLUDE for part in rel.parts) or file.suffix in SUFFIXES or file.name=='.DS_Store':continue
        if file.is_symlink():raise ValueError('No symlinks in distribution')
        items.append((rel.as_posix(),file))
    archive(dist/f'openglyph-v{VERSION}.zip',items,prefix='openglyph/')
    chosen=[]
    for relative,file in items:
        if relative in {'main.tex','main.pdf','openglyph.sty','README.md','THIRD-PARTY-NOTICES.md','LICENSE','字形索引.html','examples/newforms.json','doc/openglyph-doc.pdf','docs/使用指南.md'} or relative.startswith(('ebag/','examples/myglyphs/','licenses/')):
            chosen.append((relative,file))
    archive(dist/f'openglyph-overleaf-v{VERSION}.zip',chosen)
    for source,target in [('main.pdf','openglyph-example.pdf'),('doc/openglyph-doc.pdf','openglyph-manual.pdf')]:
        shutil.copyfile(ROOT/source,dist/target)
    checks=[]
    for file in sorted(dist.iterdir()):
        if file.name=='SHA256SUMS.txt' or not file.is_file():continue
        checks.append(hashlib.sha256(file.read_bytes()).hexdigest()+'  '+file.name)
    (dist/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='ascii')
    print(json.dumps(dict(files=[dict(name=p.name,bytes=p.stat().st_size) for p in sorted(dist.iterdir()) if p.is_file()]),indent=2))

if __name__=='__main__':main()
