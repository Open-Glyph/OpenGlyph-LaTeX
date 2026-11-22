"""OCR-to-font project handoff; remote work uses the ordinary account client."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import zipfile

from .ocr_markup import ALIAS, load_ocr, render, requirements


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def find_text_font(explicit=None):
    if explicit:
        path = Path(explicit).expanduser().resolve(strict=True)
        if path.suffix.lower() not in ('.otf', '.ttf'):
            raise ValueError('Text font must be a standalone OTF/TTF')
        return path
    caches = [Path.home()/'Library/Caches/TectonicProject.Tectonic/bundles/data',
              Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'Tectonic/bundles/data']
    for cache in caches:
        if cache.exists():
            matches = sorted(cache.glob('*/FandolSong-Regular.otf'))
            if matches:
                return matches[0]
    kpse = shutil.which('kpsewhich')
    if kpse:
        value = subprocess.run([kpse, 'FandolSong-Regular.otf'], capture_output=True, text=True, check=False)
        if value.returncode == 0 and Path(value.stdout.strip()).is_file():
            return Path(value.stdout.strip())
    raise ValueError('Provide --text-font PATH.otf; or initialize a TeX installation containing FandolSong-Regular.otf')


def plan(source, text_font=None):
    from fontTools.ttLib import TTFont
    text, result, digest = load_ocr(source)
    if result.get('complete') is False:
        raise ValueError('OCR reports incomplete output; review/finish it before typesetting')
    font = find_text_font(text_font)
    with TTFont(font) as face:
        coverage = set(face.getBestCmap() or {})
    return {'schema': 'openglyph.ocr-plan.v1', 'source_sha256': digest,
            'source': str(Path(source).resolve()), 'text': text,
            'text_font': str(font), 'text_font_sha256': hashlib.sha256(font.read_bytes()).hexdigest(),
            'requirements': requirements(text, coverage),
            'reading_verified': False, 'unicode_normalization': None}


def unpack(source, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Font bundle destination already exists')
    with zipfile.ZipFile(source) as archive:
        names = set()
        for item in archive.infolist():
            name = item.filename
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                    or '\0' in item.orig_filename or stat.S_ISLNK(item.external_attr >> 16)
                    or name in names or item.flag_bits & 1):
                raise ValueError('Unsafe font bundle path')
            names.add(name)
        if 'catalog.tex' not in names:
            raise ValueError('Font bundle has no catalog.tex')
        destination.mkdir(parents=True)
        for item in archive.infolist():
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source_file, target.open('xb') as out:
                    shutil.copyfileobj(source_file, out)


def check_aliases(folder, aliases):
    from fontTools.ttLib import TTFont
    from .project import identifier
    catalog = (folder / 'catalog.tex').read_text(encoding='utf-8')
    fonts = dict(re.findall(r'\\OpenGlyphDeclareFont\{([^}]+)\}\{([^}]+)\}', catalog))
    rows = {alias: (namespace, int(cp, 16)) for alias, namespace, cp in
            re.findall(r'\\OpenGlyphDeclare(?:Entry)?\{([^}]+)\}\{([^}]+)\}\{([A-Fa-f0-9]{4,6})\}', catalog)}
    for alias in aliases:
        if not ALIAS.fullmatch(alias) or alias not in rows:
            raise ValueError('Font bundle does not declare alias ' + alias)
        namespace, cp = rows[alias]
        identifier(namespace)
        filename = fonts.get(namespace, '')
        if not re.fullmatch(r'[A-Za-z0-9._-]+\.(otf|ttf)', filename):
            raise ValueError('Invalid bundle font filename')
        with TTFont(folder / filename) as face:
            if cp not in (face.getBestCmap() or {}):
                raise ValueError('Bundle font is missing codepoint for ' + alias)


def build(root, source, output, resolution=None, text_font=None, expected_plan=None):
    output = Path(output).resolve()
    if (output / 'main.tex').exists() or (output / 'body.tex').exists():
        raise ValueError('OCR project exists; use a fresh output directory')
    current = plan(source, text_font)
    if expected_plan and (current['source_sha256'] != expected_plan['source_sha256']
                          or current['text_font_sha256'] != expected_plan['text_font_sha256']):
        raise ValueError('OCR source or text font changed after planning')
    resolution = resolution or {'bundles': [], 'aliases': {}}
    if set(resolution.get('aliases', {})) != {r['key'] for r in current['requirements']}:
        raise ValueError('Resolution must include exactly every required GlyphWiki, IDS and Unicode fallback')
    body, refs = render(current['text'], resolution['aliases'])
    output.mkdir(parents=True, exist_ok=True)
    loads = []
    declared = set()
    for i, bundle in enumerate(resolution.get('bundles', [])):
        folder = output / ('font-' + str(i))
        unpack(bundle['path'], folder)
        check_aliases(folder, bundle['aliases'])
        declared.update(bundle['aliases'])
        loads.append(r'\OpenGlyphLoad{' + folder.name + '}')
    if set(resolution['aliases'].values()) - declared:
        raise ValueError('Some OCR aliases have no checked font bundle')
    font_name = 'text-font' + Path(current['text_font']).suffix.lower()
    shutil.copyfile(current['text_font'], output / font_name)
    shutil.copyfile(Path(root) / 'openglyph.sty', output / 'openglyph.sty')
    shutil.copyfile(source, output / ('ocr-original' + Path(source).suffix.lower()))
    (output / 'text.txt').write_bytes(current['text'].encode('utf-8'))
    (output / 'body.tex').write_text(body, encoding='utf-8')
    source_tex = (r'\documentclass[UTF8,fontset=none]{ctexart}' + '\n'
                  + r'\usepackage[a4paper,margin=25mm]{geometry}' + '\n'
                  + r'\usepackage{accsupp}' + '\n'
                  + r'\usepackage{openglyph}' + '\n'
                  + r'\setCJKmainfont[Path=./]{' + font_name + '}\n'
                  + r'\setmainfont[Path=./]{' + font_name + '}\n'
                  + '\n'.join(loads) + '\n'
                  + r'\begin{document}\input{body.tex}\end{document}' + '\n')
    (output / 'main.tex').write_text(source_tex, encoding='utf-8')
    report = {**current, 'schema': 'openglyph.ocr-project.v1', 'references': refs,
              'aliases': resolution['aliases'], 'project_dir': str(output), 'tex_file': str(output / 'main.tex'),
              'font_coverage_checked': True, 'source_equivalence_verified': False,
              'second_options_in_main_text': False, 'raster_glyphs_used': False}
    dump(output / 'ocr-manifest.json', report)
    return report


def remote_resolution(client, current, work):
    """Persist acceptance before waiting; an uncertain POST is never replayed."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    state_file = work / 'compose-state.json'
    if state_file.exists():
        state = json.loads(state_file.read_text())
        if state['endpoint'] != client.endpoint or state['plan'] != current:
            raise ValueError('Composition receipt belongs to another source, font or endpoint')
    else:
        state = {'endpoint': client.endpoint, 'plan': current}
        dump(state_file, state)
    needed = current['requirements']
    if not needed:
        return {'bundles': [], 'aliases': {}}
    if 'job_id' not in state:
        if state.get('pending'):
            raise ValueError('Composition acceptance unknown; inspect CLI receipts before any new submission')
        state['pending'] = True
        dump(state_file, state)
        accepted = client.submit('glyph_compose', {'items': [row['arguments'] for row in needed]})
        state.update(job_id=accepted['job_id'], pending=False)
        dump(state_file, state)
    envelope = client.wait(state['job_id'])
    dump(work / 'compose-result.json', envelope)
    result = envelope['result']
    pack = result.get('print_font', {})
    rows = result.get('items', [])
    if (result.get('all_ok') is not True or pack.get('status') != 'ready' or pack.get('all_items_included') is not True
            or len(rows) != len(needed) or {r.get('index') for r in rows} != set(range(len(needed)))
            or any(r.get('ok') is not True for r in rows)):
        raise ValueError('Composition is incomplete; per-item results retained in ' + str(work))
    codes = {row['code']: row['alias'] for row in pack['latex_aliases']}
    aliases = {needed[row['index']]['key']: codes[row['result']['gwz_code']] for row in rows}
    bundle = work / 'font-bundle.zip'
    client.download(pack['bundle_asset']['asset_id'], bundle)
    resolution = {'aliases': aliases, 'bundles': [{'path': str(bundle.resolve()), 'aliases': sorted(set(aliases.values()))}]}
    dump(work / 'resolution.json', resolution)
    return resolution
