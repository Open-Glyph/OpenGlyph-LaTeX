import json
from pathlib import Path
import random
import re
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from oglib.project import allocate,catalog_tex,identifier,private,read_json,validate_project

class ProjectProperties(unittest.TestCase):
    def test_addresses_survive_append_remove_and_restore(self):
        rng=random.Random(20261028)
        for _ in range(200):
            keys=['g'+str(n) for n in rng.sample(range(2000),rng.randint(1,60))]
            old=allocate(keys);remaining=keys[::2];added=['new'+str(i) for i in range(10)]
            new=allocate(remaining+added,old)
            self.assertEqual({k:new['addresses'][k] for k in keys},old['addresses'])
            self.assertEqual(len(new['addresses']),len(set(new['addresses'].values())))
            self.assertTrue(all(private(v) for v in new['addresses'].values()))
            restored=allocate(keys+added,new)
            self.assertEqual(restored['addresses'],new['addresses'])
            self.assertEqual(restored['retired_keys'],[])

    def test_allocation_and_tex_are_order_independent(self):
        rng=random.Random(14)
        for _ in range(100):
            keys=['k'+str(n) for n in rng.sample(range(10000),rng.randint(1,80))]
            expected=allocate(keys);rng.shuffle(keys)
            self.assertEqual(allocate(keys),expected)
            items=list(expected['addresses'].items());rng.shuffle(items)
            self.assertEqual(catalog_tex('paper','test.otf',dict(items)),catalog_tex('paper','test.otf',expected['addresses']))

    def test_tex_mapping_roundtrip_is_lossless(self):
        rng=random.Random(73)
        pattern=re.compile(r'\\OpenGlyphDeclare\{([^}]+)\}\{([^}]+)\}\{([0-9A-F]+)\}')
        for _ in range(150):
            keys=['s'+str(n)+'-x.y_z' for n in rng.sample(range(1000),30)]
            points=rng.sample(range(0xF0000,0xFFFFE),len(keys));source=dict(zip(keys,points))
            decoded={alias.removeprefix('test:'):int(cp,16) for alias,namespace,cp in pattern.findall(catalog_tex('test','f.otf',source)) if namespace=='test'}
            self.assertEqual(decoded,source)

    def test_pua_boundaries_and_retired_slots(self):
        for cp in (0xE000,0xF8FF,0xF0000,0xFFFFD,0x100000,0x10FFFD):self.assertTrue(private(cp))
        for cp in (True,0,0xDFFF,0xF900,0xEFFFF,0xFFFFE,0x10FFFE,0x110000):self.assertFalse(private(cp))
        old={'schema':'openglyph.allocation.v1','addresses':{'retired':0xE000}}
        self.assertEqual(allocate(['new'],old)['addresses']['new'],0xE001)

    def test_invalid_names_cannot_generate_tex(self):
        for text in ('','123','x}\\input{secret}','x%y','a/b','x\ny','x y','x\\y','甲','x#1','../x'):
            with self.assertRaises(ValueError):identifier(text)
            with self.assertRaises(ValueError):catalog_tex('valid','font.otf',{text:0xE000})
        for filename in ('../f.otf','f.otf}\\input{x}','/tmp/font.otf','f%20.otf'):
            with self.assertRaises(ValueError):catalog_tex('x',filename,{'a':0xE000})

    def test_json_roundtrip_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'project.json'
            source={'schema':'openglyph.project.v1','namespace':'paper','glyphs':[{'id':'n1','base':'ebag:s030-067','edits':[]}]}
            path.write_text(json.dumps(source));self.assertEqual(validate_project(read_json(path)),source)
            for bad in ('{"x":1,"x":2}','{"x":NaN}'):
                path.write_text(bad)
                with self.assertRaises(ValueError):read_json(path)

    def test_duplicate_conflicts_and_schema_errors(self):
        with self.assertRaises(ValueError):allocate(['a','a'])
        with self.assertRaises(ValueError):allocate(['a'],{'schema':'openglyph.allocation.v1','addresses':{'a':0xE000,'b':0xE000}})
        for bad in ({},[],{'schema':'other'},{'schema':'openglyph.project.v1','namespace':'x','glyphs':[]}):
            with self.assertRaises(ValueError):validate_project(bad)

if __name__=='__main__':unittest.main()
