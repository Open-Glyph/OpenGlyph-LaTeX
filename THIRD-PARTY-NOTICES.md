# Third-party components and provenance

The repository-level MIT license covers OpenGlyph's new LaTeX, Python and documentation code. It does not relicense third-party sources.

## GlyphWiki data and ebag_s-derived font

- Source: https://glyphwiki.org/dump.tar.gz ; project: https://glyphwiki.org/
- The retained upstream license is [licenses/GlyphWiki.txt](licenses/GlyphWiki.txt).
- It explicitly permits use, copying and redistribution, with or without modification, commercially or non-commercially, without warranty.
- `data/glyphwiki-ebag.kage.jsonl.gz` contains the 22,583 unversioned `ebag_s` master entries and their exact dependencies, 38,462 programs in total. Snapshot and engine hashes are retained in `data/provenance.json`.
- `ebag/OpenGlyphEbag.otf` is newly compiled from that source, **not** a repackaged local SEAL font. `ebag/manifest.json` preserves source IDs, program-closure hashes, source links and font-local addresses.
- Credit: the GlyphWiki project and its contributors, including the ebag_s contributors. OpenGlyph does not claim original authorship of those glyph designs or scholarly confirmation of their readings.
- The generated ebag font and included illustrative derivatives are distributed under the same permissive GlyphWiki data grant. No additional restriction on use in papers is imposed by OpenGlyph.
- The local PNG collection, standalone SEAL fonts, unverified local IDS annotation table, private publications and scans are not redistributed here. Public accessibility alone was not used as a licensing determination.

## KAGE engine

- Source: https://github.com/kamichikoichi/kage-engine
- License: GNU GPL v3, retained in [vendor/kage-engine/COPYING](vendor/kage-engine/COPYING).
- The eight unmodified JavaScript source files required to render the snapshot are provided under `vendor/kage-engine/`, with file hashes in `data/provenance.json`.
- They run in a local Node process when the optional font builder is used. They are not executed by LaTeX and are not needed to compile a paper with prebuilt fonts.
- Retain the GPL notice and corresponding source when redistributing that engine. Nothing here represents the engine as MIT licensed.

## Optional build dependencies

FontTools and skia-pathops are installed separately by the user from their distributions. The source repository does not vendor their binaries. Normal paper compilation requires a Unicode LaTeX engine and `fontspec`; the Chinese example also uses `ctex` and its Fandol font set.
