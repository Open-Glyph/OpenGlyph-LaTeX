"""Compile relocated fixtures; errors must fail rather than silently substitute."""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=['tectonic','xelatex','lualatex'],default='tectonic');p.add_argument('--output',default='build/tex-tests.json');args=p.parse_args()
    if not shutil.which(args.engine):raise SystemExit('Selected TeX engine not installed')
    fixture={
      'mixed':(True,r'\OpenGlyphLoad{custom}\begin{document}Text \gwglyph{my:n1}, \gwglyph{my:n2}.\footnote{\gwglyph{my:n3}}\section{Heading \gwglyph{my:n4}}\end{document}'),
      'repeat-load':(True,r'\OpenGlyphLoad{custom}\OpenGlyphLoad{custom}\OpenGlyphAlias{short}{my:n1}\begin{document}\gwglyph{short}\OpenGlyphSequence{my:n2,my:n3}\end{document}'),
      'unknown':(False,r'\OpenGlyphLoad{custom}\begin{document}\gwglyph{missing}\end{document}'),
      'duplicate':(False,r'\OpenGlyphLoad{custom}\OpenGlyphAlias{my:n1}{my:n2}\begin{document}x\end{document}'),
      'missing-font':(False,r'\OpenGlyphDeclareFont{bad}{no-such-font.otf}\begin{document}x\end{document}'),
      'missing-cmap':(False,r'\OpenGlyphLoad{custom}\OpenGlyphDeclare{bad}{my}{0041}\begin{document}\gwglyph{bad}\end{document}'),
      'bad-id':(False,r'\OpenGlyphLoad{custom}\OpenGlyphAlias{bad/id}{my:n1}\begin{document}x\end{document}'),
      'existence':(True,r'\OpenGlyphLoad{custom}\begin{document}\OpenGlyphIfExistsTF{my:n1}{YES}{\errmessage{miss}}\OpenGlyphIfExistsTF{missing}{\errmessage{unexpected}}{NO}\end{document}'),
      'namespaces':(True,r'\OpenGlyphLoad{custom}\OpenGlyphLoad{second}\begin{document}\gwglyph{my:n1}\gwglyph{second:n1}\end{document}')}
    expected_errors={'unknown':'Unknown glyph','duplicate':'already defined','missing-font':'Cannot find',
                     'missing-cmap':'does not contain glyph','bad-id':'Invalid ASCII identifier'}
    results=[]
    with tempfile.TemporaryDirectory(prefix='openglyph-tex-') as tmp:
        root=Path(tmp)/'moved project with spaces';root.mkdir()
        shutil.copyfile(ROOT/'openglyph.sty',root/'openglyph.sty')
        shutil.copytree(ROOT/'examples/myglyphs',root/'custom')
        shutil.copytree(ROOT/'examples/myglyphs',root/'second')
        text=(root/'second/catalog.tex').read_text().replace('{my}','{second}').replace('{my:','{second:')
        (root/'second/catalog.tex').write_text(text)
        for name,(success,body) in fixture.items():
            tex=root/(name+'.tex');tex.write_text(r'\documentclass{article}\usepackage{openglyph}\usepackage[unicode]{hyperref}'+body,encoding='utf-8')
            cmd=[args.engine,'--keep-logs',tex.name] if args.engine=='tectonic' else [args.engine,'-interaction=nonstopmode','-halt-on-error','-no-shell-escape',tex.name]
            start=time.perf_counter();proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True,timeout=90)
            got=proc.returncode==0
            diagnostic=re.sub(r'\s+',' ',proc.stdout+proc.stderr)
            passed=got==success and (success or expected_errors[name] in diagnostic)
            results.append(dict(case=name,expected_success=success,success=got,passed=passed,seconds=time.perf_counter()-start,
                expected_error=expected_errors.get(name),diagnostic='' if passed else diagnostic[-5000:]))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(dict(engine=args.engine,tests=results),indent=2))
    print(json.dumps(results,indent=2))
    if not all(r['passed'] for r in results):raise SystemExit(1)

if __name__=='__main__':main()
