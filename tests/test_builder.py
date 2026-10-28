import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from oglib.catalog import Catalog
from oglib.template_program import compile_program
from openglyph import compile_project,inspect

class BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.catalog=Catalog(ROOT/'data/glyphwiki-ebag.kage.jsonl.gz')

    def test_pinned_edit_replay_and_source_isolation(self):
        source=self.catalog.resolve('ebag:s030-067')
        project=json.loads((ROOT/'examples/newforms.json').read_text())
        original=copy.deepcopy(source)
        for row in project['glyphs']:
            program=dict(schema='guwenzi.template-program.v1',base=row['base'],edits=row['edits'])
            recipe,info=compile_program(self.catalog,program)
            self.assertEqual((recipe,info),compile_program(self.catalog,json.loads(json.dumps(info['program']))))
            self.assertNotEqual(recipe['root'],source['name'])
        self.assertEqual(self.catalog.resolve('ebag:s030-067'),original)

    def test_all_source_dependencies_exist_and_versions_do_not_fallback(self):
        from oglib.catalog import refs
        for name,data in self.catalog.table.items():
            for child in refs(data):self.assertIn(child,self.catalog.table,name)
        with self.assertRaises(ValueError):self.catalog.resolve('u81e3@999999')

    def test_build_is_deterministic_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=compile_project(ROOT/'examples/newforms.json',root/'first')
            second=compile_project(ROOT/'examples/newforms.json',root/'second')
            self.assertEqual(first['font_sha256'],second['font_sha256'])
            self.assertEqual(first['glyphs'],second['glyphs'])
            original=(root/'first'/first['font_file']).read_bytes()
            with self.assertRaises(ValueError):compile_project(ROOT/'examples/newforms.json',root/'first')
            self.assertEqual((root/'first'/first['font_file']).read_bytes(),original)

    def test_each_exported_char_has_a_real_outline(self):
        from fontTools.ttLib import TTFont
        from fontTools.pens.boundsPen import BoundsPen
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'output';result=compile_project(ROOT/'examples/newforms.json',folder)
            with TTFont(folder/result['font_file']) as font:
                cmap=font.getBestCmap();gs=font.getGlyphSet()
                for row in result['glyphs']:
                    name=cmap[row['codepoint']];pen=BoundsPen(gs);gs[name].draw(pen)
                    self.assertIsNotNone(pen.bounds)
                self.assertNotIn('SVG ',font);self.assertNotIn('sbix',font)

    def test_removed_ids_keep_slots_on_revision(self):
        project=json.loads((ROOT/'examples/newforms.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=compile_project(ROOT/'examples/newforms.json',root/'first')
            project['glyphs']=project['glyphs'][1:];project['glyphs'].append(dict(id='new',base='ebag:s030-067',edits=[]))
            manifest=root/'project.json';manifest.write_text(json.dumps(project))
            second=compile_project(manifest,root/'second',root/'first/allocation.json')
            before={r['id']:r['codepoint'] for r in first['glyphs']};after={r['id']:r['codepoint'] for r in second['glyphs']}
            for key in ('n2','n3','n4'):self.assertEqual(before[key],after[key])
            self.assertNotIn(after['new'],before.values())

    def test_inspection_produces_numbered_actual_vector_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'preview';result=inspect('ebag:s030-067','r4',folder)
            self.assertEqual(len(result['nodes']),4)
            page=(folder/'index.html').read_text()
            for row in result['nodes']:self.assertIn(row['node'],page)
            self.assertEqual(len(list(folder.glob('*.svg'))),6)
            with self.assertRaises(ValueError):inspect('ebag:s030-067','r4',folder)

if __name__=='__main__':unittest.main()
