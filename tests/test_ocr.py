import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from oglib.ocr_markup import parse, render, requirements, validate_ids, load_ocr
from oglib.ocr_project import build, plan, remote_resolution

ROOT = Path(__file__).resolve().parents[1]


class OCRProperties(unittest.TestCase):
    def test_generated_nested_ids_and_marker_roundtrip(self):
        rng = random.Random(20261122)
        def tree(depth):
            if not depth or rng.random() < .4:
                return rng.choice('木日月艹𤪷𠮷氵火')
            op = rng.choice('⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻')
            return op + ''.join(tree(depth - 1) for _ in range(3 if op in '⿲⿳' else 2))
        for _ in range(300):
            ids = '⿱' + tree(3) + tree(3)
            validate_ids(ids)
            text = '甲󠄀&%\\{}\n<gw:ebag_s093-073><ids>' + ids + '</ids>𤪷'
            parsed = parse(text)
            restored = ''.join(row['text'] if row['kind'] == 'text' else row['source'] for row in parsed)
            self.assertEqual(restored, text)
            aliases = {'gw:ebag_s093-073': 'pack:g2', 'ids:' + ids: 'pack:g1'}
            body, refs = render(text, aliases)
            self.assertEqual([r['alias'] for r in refs], ['pack:g2', 'pack:g1'])
            self.assertIn('甲󠄀', body)
            self.assertIn(r'\&\%\textbackslash{}\{\}', body)
            self.assertNotIn('<ids>', body)

    def test_invalid_or_incomplete_forms_fail(self):
        for value in ('', '⿱木', '⿱木火日', '木', '⿱木A', '⿱木<gw:a>'):
            with self.assertRaises(ValueError):
                validate_ids(value)
        for text in ('<ids>⿰木火', '</ids>', '<gw:a', '<gw:a/b>', '<ids>⿰木</ids>', '<ids><ids>木</ids></ids>'):
            with self.assertRaises(ValueError):
                parse(text)
        for component in ('⿱⼀﨑', '⿱⼀丽'):
            validate_ids(component)
        with self.assertRaises(ValueError):
            validate_ids('⿱⼀㇯')
        with self.assertRaises(ValueError):
            render('<gw:ebag_s093-073>', {})
        with self.assertRaises(ValueError):
            render('<gw:a>', {'gw:a': 'x}\\input{x}'})

    def test_requirements_keep_exact_keys_and_unicode_fallbacks(self):
        text = '甲𤪷<gw:ebag_s093-073><ids>⿱艹⿰日月</ids><gw:ebag_s093-073>'
        rows = requirements(text, {ord('甲')})
        self.assertEqual([r['key'] for r in rows], ['unicode:𤪷', 'gw:ebag_s093-073', 'ids:⿱艹⿰日月'])
        self.assertEqual(rows[0]['arguments']['unicode_codepoint'], 'U+24AB7')
        with self.assertRaises(ValueError):
            requirements('甲󠄀', {ord('甲')})

    def test_dsh_receipt_uses_main_text_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'receipt.json'
            result = {'text': '甲<ids>⿱木火</ids>', 'lines': [{'options': [{'text': '乙'}]}]}
            path.write_text(json.dumps({'schema': 'openglyph.dsh.receipt.v1', 'envelope': {'result': result}}))
            # The DSH envelope is preserved; no choice text enters the body.
            text, _, _ = load_ocr(path)
            self.assertEqual(text, result['text'])

    def test_project_keeps_exact_markers_and_checks_real_font_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / 'ocr.json'
            text = '<gw:ebag_s093-073><ids>⿱艹⿰日月</ids>'
            source.write_text(json.dumps({'result': {'text': text, 'complete': True,
                'lines': [{'options': [{'text': '乙'}]}]}}), encoding='utf-8')
            # Existing sample outlines stand in for a downloaded bundle here;
            # this test checks the handoff and cmap, not the identity of shapes.
            sample = ROOT / 'examples/myglyphs'
            face = next(sample.glob('*.otf'))
            bundle = folder / 'font.zip'
            with zipfile.ZipFile(bundle, 'w') as archive:
                for file in sample.iterdir():
                    if file.is_file():
                        archive.write(file, file.name)
            aliases = {'gw:ebag_s093-073': 'my:n1', 'ids:⿱艹⿰日月': 'my:n2'}
            resolution = {'aliases': aliases, 'bundles': [{'path': str(bundle), 'aliases': list(aliases.values())}]}
            report = build(ROOT, source, folder / 'paper', resolution, face)
            self.assertTrue(report['font_coverage_checked'])
            self.assertEqual((folder / 'paper/text.txt').read_bytes(), text.encode('utf-8'))
            self.assertEqual((folder / 'paper/ocr-original.json').read_bytes(), source.read_bytes())
            self.assertNotIn('乙', (folder / 'paper/body.tex').read_text())
            with self.assertRaisesRegex(ValueError, 'exactly every'):
                build(ROOT, source, folder / 'missing-alias', text_font=face)
            bad = {'aliases': {k: 'my:absent' for k in aliases},
                   'bundles': [{'path': str(bundle), 'aliases': ['my:absent']}]}
            with self.assertRaisesRegex(ValueError, 'does not declare'):
                build(ROOT, source, folder / 'missing-font-entry', bad, face)
            expected = plan(source, face)
            source.write_text(json.dumps({'text': text + '<gw:u4e00>'}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'changed after planning'):
                build(ROOT, source, folder / 'changed', resolution, face, expected)
            source.write_text(json.dumps({'text': text, 'complete': False}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                plan(source, face)

    def test_composition_resumes_accepted_job_and_maps_by_item_index(self):
        class Client:
            endpoint = 'https://test.invalid'

            def __init__(self):
                self.posts = 0
                self.interrupt = True

            def submit(self, tool, args):
                self.posts += 1
                return {'job_id': 'j' + 'a' * 32}

            def wait(self, job_id):
                if self.interrupt:
                    raise RuntimeError('connection interrupted')
                return {'result': {'all_ok': True, 'items': [
                    {'index': 1, 'ok': True, 'result': {'gwz_code': 'gwz:two'}},
                    {'index': 0, 'ok': True, 'result': {'gwz_code': 'gwz:one'}}],
                    'print_font': {'status': 'ready', 'all_items_included': True,
                        'latex_aliases': [{'code': 'gwz:one', 'alias': 'pack:g1'},
                                          {'code': 'gwz:two', 'alias': 'pack:g2'}],
                        'bundle_asset': {'asset_id': 'asset:' + 'b' * 64}}}}

            def download(self, asset_id, path):
                path.write_bytes(b'test bundle: not used for rendering')

        current = {'requirements': requirements('<gw:ebag_s093-073><ids>⿱艹⿰日月</ids>')}
        with tempfile.TemporaryDirectory() as tmp:
            client = Client()
            with self.assertRaises(RuntimeError):
                remote_resolution(client, current, tmp)
            client.interrupt = False
            result = remote_resolution(client, current, tmp)
            self.assertEqual(client.posts, 1)
            self.assertEqual(result['aliases'], {'gw:ebag_s093-073': 'pack:g1', 'ids:⿱艹⿰日月': 'pack:g2'})
