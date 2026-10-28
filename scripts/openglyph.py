#!/usr/bin/env python3
"""Build/inspect named glyphs offline; ordinary LaTeX users need no Python."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
from oglib import __version__
from oglib.project import allocate,catalog_tex,read_json,validate_project

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def compile_project(manifest,output,allocation=None):
    from oglib.catalog import Catalog
    from oglib.template_modules import compile_modular as compile_program
    from oglib.kage import KageRenderer
    from oglib.font import outline,write_font
    start=time.perf_counter();project=validate_project(read_json(Path(manifest)))
    output=Path(output).resolve()
    if output.exists():raise ValueError('Output already exists; choose a new folder to preserve earlier glyphs')
    catalog=Catalog(ROOT/'data/glyphwiki-ebag.kage.jsonl.gz')
    old=read_json(Path(allocation)) if allocation else None
    slots=allocate([r['id'] for r in project['glyphs']],old)
    jobs=[];table={};compiled={}
    for row in project['glyphs']:
        program=dict(schema='guwenzi.template-program.v1',**{k:v for k,v in row.items() if k!='id'})
        recipe,info=compile_program(catalog,program);compiled[row['id']]=(recipe,info)
        for name,data in recipe['table'].items():
            if name in table and table[name]!=data:raise ValueError('Conflicting program dependency')
            table[name]=data
        jobs.append(dict(key=row['id'],name=recipe['root']))
    rendered=KageRenderer(str(ROOT/'vendor/kage-engine')).render(jobs,table,curve=True,strict_versions=True)
    rows={}
    for row in project['glyphs']:
        key=row['id'];svg=rendered.get(key)
        if not svg:raise ValueError('Rendering failed: '+key)
        rows[key]={**outline(svg),'codepoint':slots['addresses'][key]}
    identity=hashlib.sha256(json.dumps([(k,v['codepoint'],v['outline_sha256']) for k,v in sorted(rows.items())]).encode()).hexdigest()[:12]
    family='OpenGlyph-'+identity;filename=family+'.otf'
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.openglyph-',dir=output.parent) as temporary:
        work=Path(temporary);(work/'sources').mkdir()
        license_text=(ROOT/'licenses/GlyphWiki.txt').read_text(encoding='utf-8-sig')
        font_sha=write_font(rows,work/filename,family,license_text=license_text,license_url='https://glyphwiki.org/')
        metadata=[]
        for key,row in rows.items():
            recipe,info=compiled[key]
            (work/'sources'/f'{key}.svg').write_text(rendered[key],encoding='utf-8')
            dump(work/'sources'/f'{key}.program.json',info['program'])
            dump(work/'sources'/f'{key}.kage.json',recipe)
            metadata.append({k:v for k,v in row.items() if k!='charstring'}|dict(id=key,alias=project['namespace']+':'+key,
                program_sha256=info['program_sha256'],glyph_identity='gwz:sha256:'+row['outline_sha256'],scholarly_identity_verified=False))
        (work/'catalog.tex').write_text(catalog_tex(project['namespace'],filename,{k:r['codepoint'] for k,r in rows.items()}),encoding='ascii')
        dump(work/'allocation.json',slots);dump(work/'project.json',project)
        report=dict(schema='openglyph.bundle.v1',version=__version__,namespace=project['namespace'],font_file=filename,font_sha256=font_sha,
            glyphs=metadata,pua_scope='font-local, not character identity',source_equivalence_verified=False,
            review_policy='human scholarly review; generation is not acceptance',seconds=time.perf_counter()-start)
        dump(work/'manifest.json',report)
        shutil.copyfile(ROOT/'licenses/GlyphWiki.txt',work/'GLYPHWIKI-LICENSE.txt')
        shutil.copytree(work,output)
    return report

def inspect(base,node='root',output=None):
    from oglib.catalog import Catalog,hash_json
    from oglib.template_program import TemplateProgram
    catalog=Catalog(ROOT/'data/glyphwiki-ebag.kage.jsonl.gz')
    program=TemplateProgram(catalog,base);result=program.describe(node)
    if output is not None:
        from oglib.kage import KageRenderer
        folder=Path(output).resolve()
        if folder.exists():raise ValueError('Preview output already exists')
        table=dict(program.table);container=program.root.container(node)
        jobs=[dict(key='whole',name=program.root.emit(table)),dict(key='parent',name=container.emit(table))]
        labels={'whole':'Whole glyph','parent':'Current parent: '+node}
        for i,record in enumerate(container.records):
            if record['fields'][0] in ('','0'):continue
            data=':'.join(record['fields']);name='openglyph-preview-'+hash_json(data);table[name]=data
            key='node-'+str(i);jobs.append(dict(key=key,name=name));labels[key]=result['nodes'][i]['node']
        rendered=KageRenderer(str(ROOT/'vendor/kage-engine')).render(jobs,table,curve=True,strict_versions=True)
        if any(not rendered[j['key']] for j in jobs):raise ValueError('Incomplete component preview')
        folder.mkdir(parents=True,exist_ok=False);cards=[]
        for job in jobs:
            key=job['key'];(folder/(key+'.svg')).write_text(rendered[key],encoding='utf-8')
            cards.append('<figure>'+rendered[key]+'<figcaption>'+html.escape(labels[key])+'</figcaption></figure>')
        (folder/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>OpenGlyph components</title>'
            '<style>body{font:16px/1.7 sans-serif;padding:24px}main{display:flex;flex-wrap:wrap;gap:16px}figure{padding:16px;border:1px solid #ddd}svg{width:220px;height:220px;overflow:visible}</style>'
            '<h1>Component occurrence IDs</h1><p>Independent previews may differ in stroke avoidance; check the whole glyph after editing.</p><main>'+''.join(cards)+'</main>',encoding='utf-8')
        result['preview']='index.html';dump(folder/'inspection.json',result)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build',help='Compile edited forms to an OTF + LaTeX catalogue')
    b.add_argument('project');b.add_argument('-o','--output',required=True);b.add_argument('--allocation')
    s=sub.add_parser('inspect',help='Return component occurrence IDs, not guessed stroke programs')
    s.add_argument('base');s.add_argument('--node',default='root');s.add_argument('-o','--output')
    args=p.parse_args()
    try:
        result=compile_project(args.project,args.output,args.allocation) if args.command=='build' else inspect(args.base,args.node,args.output)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,RuntimeError,ImportError) as exc:
        print('OpenGlyph: '+str(exc),file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
