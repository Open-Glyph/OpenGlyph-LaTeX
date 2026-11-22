"""Lossless parser and LaTeX renderer for OpenGlyph-OCR-IDS markup."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

GW_NAME = re.compile(r'[a-z0-9_][a-z0-9_.-]*(?:@[0-9]+)?\Z')
ALIAS = re.compile(r'[A-Za-z][A-Za-z0-9._-]*:[A-Za-z][A-Za-z0-9._-]*\Z')


def parse(text):
    if not isinstance(text, str) or not text:
        raise ValueError('OCR text must be a non-empty string')
    rows = []
    plain = []

    def flush():
        if plain:
            rows.append({'kind': 'text', 'text': ''.join(plain)})
            plain.clear()

    i = 0
    while i < len(text):
        if text.startswith('<gw:', i):
            end = text.find('>', i + 4)
            if end < 0:
                raise ValueError('Unclosed <gw:...> marker')
            name = text[i + 4:end]
            if not GW_NAME.fullmatch(name):
                raise ValueError('Invalid GlyphWiki name')
            flush()
            rows.append({'kind': 'gw', 'value': name, 'source': text[i:end + 1]})
            i = end + 1
        elif text.startswith('<ids>', i):
            end = text.find('</ids>', i + 5)
            if end < 0:
                raise ValueError('Unclosed <ids> marker')
            value = text[i + 5:end]
            validate_ids(value)
            flush()
            rows.append({'kind': 'ids', 'value': value, 'source': text[i:end + 6]})
            i = end + 6
        elif text.startswith('</ids', i) or text.startswith('<ids', i) or text.startswith('<gw', i):
            raise ValueError('Malformed OpenGlyph OCR markup')
        else:
            if ord(text[i]) < 32 and text[i] not in '\n\r\t':
                raise ValueError('Unsupported control character in OCR text')
            if 0xD800 <= ord(text[i]) <= 0xDFFF:
                raise ValueError('OCR text contains a non-scalar codepoint')
            plain.append(text[i])
            i += 1
    flush()
    return rows


def render(text, aliases):
    rows = parse(text)
    if not isinstance(aliases, dict):
        raise ValueError('Aliases must be an object')
    body = []
    references = []
    for row in rows:
        if row['kind'] == 'text':
            escaped = []
            for char in row['text']:
                key = 'unicode:' + char
                if key in aliases:
                    alias = aliases[key]
                    if not isinstance(alias, str) or not ALIAS.fullmatch(alias):
                        raise ValueError('Invalid Unicode fallback alias')
                    escaped.append(actual_glyph(alias, char))
                    references.append({'kind': 'unicode', 'value': char, 'source': char, 'alias': alias})
                    continue
                escaped.append({
                    '\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '$': r'\$',
                    '&': r'\&', '#': r'\#', '%': r'\%', '_': r'\_',
                    '^': r'\textasciicircum{}', '~': r'\textasciitilde{}',
                    '<': r'\char"003C{}', '>': r'\char"003E{}',
                    '\t': r'\hspace*{2em}', '\r': '',
                }.get(char, '\\par{}\n' if char == '\n' else char))
            body.append(''.join(escaped))
            continue
        key = row['kind'] + ':' + row['value']
        alias = aliases.get(key)
        if not isinstance(alias, str) or not ALIAS.fullmatch(alias):
            raise ValueError('Missing or invalid LaTeX alias for ' + key)
        body.append(actual_glyph(alias, row['source']))
        references.append({'kind': row['kind'], 'value': row['value'], 'source': row['source'],
                           'alias': alias, 'latex': body[-1]})
    return ''.join(body), references


def actual_glyph(alias, source):
    # ActualText keeps copy/search semantics even for font-local PUA glyphs.
    encoded = source.encode('utf-16-be').hex().upper()
    return (r'\BeginAccSupp{method=hex,unicode,ActualText=' + encoded + r'}'
            + r'\gwglyph{' + alias + r'}\EndAccSupp{}\allowbreak{}')


def load_ocr(path):
    path = Path(path)
    data = path.read_bytes()
    raw = data.decode('utf-8')
    digest = hashlib.sha256(data).hexdigest()
    if path.suffix.lower() != '.json':
        return raw, {'text': raw}, digest
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ValueError('Invalid OCR JSON') from exc
    if isinstance(value, dict) and value.get('schema') == 'openglyph.dsh.receipt.v1':
        value = value.get('envelope')
    result = value.get('result', value) if isinstance(value, dict) else None
    if not isinstance(result, dict) or not isinstance(result.get('text'), str):
        raise ValueError('JSON must contain result.text')
    return result['text'], result, digest


def import_file(source, aliases_path, output):
    text, result, digest = load_ocr(source)
    aliases = json.loads(Path(aliases_path).read_text(encoding='utf-8')) if aliases_path else {}
    body, references = render(text, aliases)
    output = Path(output)
    if output.exists() or output.with_suffix(output.suffix + '.source.json').exists():
        raise ValueError('Output exists; choose a fresh path')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(body, encoding='utf-8')
    metadata = {'schema': 'openglyph.ocr-import.v1', 'ocr_sha256': digest, 'text': text,
                'references': references, 'ocr_options': {k: result[k] for k in
                ('layout', 'writing_mode', 'second_options', 'machine_reading', 'reading_verified') if k in result},
                'ocr_text_is_correction': False}
    output.with_suffix(output.suffix + '.source.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'tex_body': str(output.resolve()), 'source_manifest': str(output.with_suffix(output.suffix + '.source.json').resolve()),
            'source_sha256': digest, 'marker_count': len(references), 'references': references,
            'plain_text_preserved': True, 'unicode_normalization': None,
            'second_options_in_main_text': False}


def validate_ids(value):
    """Iterative prefix grammar; the model emits twelve IDC operators.

    Components can include radicals and compatibility ideographs; retain their
    exact codepoints rather than normalizing them to a unified ideograph.
    """
    if not value or value[0] not in '⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻':
        raise ValueError('IDS must start with a structural operator')
    need = 1
    for char in value:
        if need <= 0:
            raise ValueError('IDS has surplus components')
        if char in '⿰⿱⿴⿵⿶⿷⿸⿹⿺⿻':
            need += 1
        elif char in '⿲⿳':
            need += 2
        elif _is_ids_component(char):
            need -= 1
        else:
            raise ValueError('IDS has an unsupported component')
    if need:
        raise ValueError('IDS has missing components')


def _is_ids_component(char):
    point = ord(char)
    return any(lo <= point <= hi for lo, hi in (
        (0x3400, 0x4DBF),       # CJK Extension A
        (0x4E00, 0x9FFF),       # Unified Ideographs
        (0xF900, 0xFAFF),       # CJK compatibility ideographs
        (0x20000, 0x3347F),     # supplementary CJK ideographs
        (0x2E80, 0x2EFF),       # radicals and descriptions
        (0x2F00, 0x2FDF),       # Kangxi radicals
        (0x2F800, 0x2FA1F),     # compatibility ideographs supplement
        (0x31C0, 0x31EE),       # CJK strokes; U+31EF is an unsupported IDC
    ))


def requirements(text, coverage=None):
    """Deduplicate exact markers; never merge different source spellings."""
    found = {}
    for row in parse(text):
        if row['kind'] != 'text':
            key = row['kind'] + ':' + row['value']
            found[key] = {row['kind'] if row['kind'] == 'ids' else 'glyph': row['value']}
        elif coverage is not None:
            for char in row['text']:
                if 0xFE00 <= ord(char) <= 0xFE0F or 0xE0100 <= ord(char) <= 0xE01EF:
                    raise ValueError('Variation selector requires a verified sequence font; original text retained')
                if not char.isspace() and ord(char) not in coverage:
                    found['unicode:' + char] = {'glyph': char, 'unicode_codepoint': f'U+{ord(char):04X}'}
    return [{'key': key, 'arguments': value} for key, value in found.items()]
