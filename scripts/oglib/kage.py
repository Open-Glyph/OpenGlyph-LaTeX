"""KAGE rendering via the kage-engine JavaScript engine.

The kage-engine program is GPL-3.0; the GlyphWiki data has its own usage
license. Node executes the engine as a separate tool. Keep the applicable
licenses with source artifacts; this process boundary is not a license ruling.
"""
from __future__ import annotations
import json, math, os, shutil, subprocess, tempfile
from typing import Dict, List, Optional

JS_RUNNER = r'''
const fs=require('fs');
const path=require('path');
const renderDir=process.argv[2];
const payload=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));

const ctx={console}; const vm=require('vm'); vm.createContext(ctx);
for (const f of ['2d.js','buhin.js','curve.js','kage.js','kagecd.js','kagedf.js','polygon.js','polygons.js'])
  vm.runInContext(fs.readFileSync(path.join(renderDir,f),'utf8'), ctx, {filename:f});

const table=new Map();
for (const entry of payload.table) table.set(entry[0], entry[1]);

const kage=new ctx.Kage();
for (const [key,value] of Object.entries(payload.settings || {})) kage[key]=value;
kage.kBuhin.search=(n)=>{ n=(n||'').trim(); return table.get(n) ?? (payload.strict_versions ? '' : table.get(n.split('@')[0])) ?? ''; };

const out={};
for (const req of payload.jobs){
  try{
    const polys=new ctx.Polygons();
    kage.makeGlyph(polys, req.name);
    out[req.key]=polys.generateSVG(req.curve===true);
  }catch(e){ out[req.key]=null; }
}
process.stdout.write(JSON.stringify(out));
'''


class KageRenderer:
    def __init__(self, engine_dir: Optional[str] = None):
        self.engine_dir = engine_dir or self._find_engine()

    @staticmethod
    def _find_engine() -> Optional[str]:
        env = os.environ.get('GWZ_KAGE_ENGINE')
        if env and os.path.isdir(env):
            return env
        for c in [
            os.path.expanduser('~/.cache/guwenzi/kage-engine'),
            '/tmp/glyph-research/run',
        ]:
            if os.path.isdir(c) and os.path.exists(os.path.join(c, 'kage.js')):
                return c
        return None

    def available(self) -> bool:
        return bool(self.engine_dir and shutil.which('node'))

    def render(self, jobs: List[dict], table: Dict[str, str],
               curve: bool = False, strict_versions: bool = False,
               settings: Optional[dict] = None) -> Dict[str, Optional[str]]:
        """jobs: [{'key':..., 'name':...}]  ->  {key: svg-or-None}"""
        settings=settings or {}
        if not isinstance(settings,dict) or set(settings)-{'kMinWidthY','kMinWidthU','kMinWidthT','kWidth'}:
            raise ValueError('Only explicit KAGE stroke-width settings are supported')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in settings.values()):
            raise ValueError('KAGE stroke widths must be finite positive numbers')
        if not self.available():
            raise RuntimeError(
                'kage engine not found.  Set GWZ_KAGE_ENGINE to a directory '
                'containing the kage-engine .js files (2d.js, buhin.js, ...), '
                'and make sure `node` is on PATH.')
        with tempfile.TemporaryDirectory() as td:
            runner = os.path.join(td, 'run.js')
            with open(runner, 'w') as file:
                file.write(JS_RUNNER)
            # only ship the parts we actually need
            parts, invalid, memo = set(), set(), {}
            def need(n, visiting):
                s = n if n in table else (None if strict_versions else n.split('@')[0])
                if not s or s not in table or s in visiting:
                    return False
                if s in memo:
                    return memo[s]
                parts.add(s)
                visiting.add(s)
                valid = True
                for frag in table[s].split('$'):
                    c = frag.split(':')
                    if len(c) > 7 and c[0].strip() == '99':
                        # Every branch matters: a missing second component can
                        # otherwise silently produce a plausible partial glyph.
                        valid = need(c[7].strip(), visiting) and valid
                visiting.remove(s)
                memo[s] = valid
                return valid
            for j in jobs:
                if not need(j['name'], set()):
                    invalid.add(j['key'])
            payload = dict(table=[[k, table[k]] for k in parts if k in table],
                           jobs=[dict(j, curve=j.get('curve', curve)) for j in jobs if j['key'] not in invalid],
                           strict_versions=strict_versions,settings=settings)
            pj = os.path.join(td, 'payload.json')
            with open(pj, 'w') as file:
                json.dump(payload, file)
            node_bin = shutil.which('node') or shutil.which('nodejs')
            if not node_bin:
                raise RuntimeError('node/nodejs not found on PATH')
            r = subprocess.run([node_bin, runner, self.engine_dir, pj],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f'kage engine failed: {r.stderr[:400]}')
            result = json.loads(r.stdout)
            result.update({key: None for key in invalid})
            return result
