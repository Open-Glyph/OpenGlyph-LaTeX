# Releasing

No production service or model is needed. From the repository root:

```sh
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python scripts/verify_bundle.py ebag
python scripts/verify_bundle.py examples/myglyphs
python tests/run_tex_tests.py --engine tectonic
tectonic --keep-logs main.tex
tectonic --keep-logs -o doc openglyph-doc.tex
python scripts/build_index.py
python scripts/package_release.py
```

The full OTF must have all 22,583 advertised mappings and nonempty outlines, and all referenced files and licenses must be present. This does not establish scholarly identity or source-image equivalence.

Before publishing, scan the staged tree for credentials, absolute local paths and private source material. Include only the selected public GlyphWiki data, the license notices, source code, generated fonts, examples and documentation.

`scripts/build_ebag.py -o build/rebuilt-ebag` rebuilds the large font from the compressed program subset; `data/ebag-addresses.json` is the permanent address registry and must travel with future releases. Do not renumber old glyphs or reuse retired addresses. Changes to source data, normalization or rendering settings require new source hashes and a release note.

CTAN submission is a separate maintainer action. Do not state that GitHub publication means CTAN/TeX Live/MiKTeX inclusion. The package name, maintainer contact, mixed licenses, TDS layout and current CTAN requirements should be checked before submission.
