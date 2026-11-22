# Changelog

## 0.2.0 — 2026-10-28

- Support reusable JSON modules, source-record selection, cycle rejection and exact replay.
- Accept editable projects produced by the image-template toolchain; typesetting itself stays offline.
- Preserve source templates and occurrence-specific edits, including selection of an entire nested component.
- Add a module example and CLI-to-LaTeX integration guide. No claim of automatic character identification or general reconstruction accuracy.

## 0.1.0 — 2026-10-28

- First independent OpenGlyph LaTeX package, with namespace-aware font-backed glyph commands.
- Bundle 22,583 newly compiled GlyphWiki ebag_s forms and their source-program dependency subset under the retained data license.
- Add offline structural edits: replace, insert, drop, place, move and group; no model-authored raw KAGE required.
- Preserve exact component versions and stable, non-reused project PUA slots.
- Provide a complete Chinese paper example, four new-form examples, an offline glyph index, source and Overleaf-ready distributions.
- Explicit failures for unknown glyphs, font absence and duplicate aliases; no near-character substitution.
- No production website/PAI changes, no PyPI release, no CTAN submission in this release.

## 0.3.0 — 2026-11-22

- Import OpenGlyph-OCR-IDS TXT/JSON/DSH receipts, retaining Unicode, GlyphWiki markers, nested IDS and second choices separately.
- Resolve required forms through the authenticated lightweight client; use exact returned combined-font aliases, check cmap coverage and preserve source manifests.
- Emit relocatable LaTeX projects with real outline fonts, safe TeX escaping and ActualText for searchable/copyable GW/IDS source markup. Missing or incomplete forms fail explicitly.
