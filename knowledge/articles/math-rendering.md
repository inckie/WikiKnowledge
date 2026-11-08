---
categories:
- markup-conventions
created: '2026-11-08T05:08:29.973512+00:00'
id: math-rendering
modified: '2026-11-08T05:08:29.973532+00:00'
tags:
- markup
- math
- katex
- ui
- testing
title: Math Rendering (KaTeX)
type: leaf
---

# Math Rendering (KaTeX)

The article viewer and editor preview render LaTeX math with [KaTeX](https://katex.org) (loaded from the CDN in `frontend/index.html`, alongside `marked.js` and `mermaid.js`).

## Syntax

| Form | Example | Result |
|------|---------|--------|
| Display | `$$\text{scale}(0.97) \,\, \text{rotateX}(4^\circ)$$` | Centered block (may span several lines) |
| Inline | `$1\times 1$`, `$L_2$` | Flows with the text |
| Literal dollar | `\$5` | Plain `$5` |

Inline math follows Pandoc's rules so prices are not misread: the opening `$` must not be followed by whitespace, the closing `$` must not be preceded by whitespace or followed by a digit. `$5 and $10` therefore stays plain text.

## How it works

`Viewer.render()` in `frontend/js/viewer.js`:

1. Protects fenced code and inline code first, so math syntax inside code is never touched.
2. `_extractMath()` swaps `$$...$$` / `$...$` for placeholders (`WKMATHPH<n>PH`) **before** wiki-link processing and `marked`, so LaTeX backslashes and underscores are not mangled into Markdown.
3. After every other HTML post-processing pass, `_restoreMath()` replaces placeholders with `katex.renderToString(..., { throwOnError: false })` output.

If KaTeX is not loaded (CDN blocked) the original `$...$` text is shown in a `.math-fallback` span, so no content is lost. Invalid TeX is displayed by KaTeX in its red error style rather than breaking the page.

### Headings containing math

The heading slug (anchor id) is computed from the original markdown (`$\leftrightarrow$` stays as text), so anchors are stable. The table of contents shows only the visible glyphs, not KaTeX's hidden MathML.

## Frontend tests

The renderer is covered by headless tests in `tests/frontend/` (Node's built-in test runner + jsdom, with `marked`, `katex` and `mermaid` from npm pinned to the same majors as the CDN tags):

```bash
cd tests/frontend
npm install   # first time only
npm test
```

- `math.test.js` covers display/inline math, prices, escapes, code protection, headings and the no-KaTeX fallback.
- `mermaid.test.js` covers the Mermaid fallback chain described in [[mermaid-diagrams]].
- `mermaid-links.test.js` covers `[[links]]` inside diagrams: all link flavors, links combined with auto-repair and pseudo-tag escaping, links in edge labels / subgraph titles / sequence diagrams, and the markup actually handed to `mermaid.render()`.
- `kb-articles.test.js` renders every article of this knowledge base and asserts that markup *examples* ([[human-protected-blocks]], [[wiki-link-syntax]], [[ai-interaction-guide]]) stay literal code and that diagrams still parse.

jsdom has no layout engine, so these tests exercise Mermaid's parser and the repair logic but stub the final SVG step; the SVG output itself is checked in a real browser.