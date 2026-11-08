import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { createViewerEnv } from './harness.js';

describe('math rendering (KaTeX)', () => {
    let env;
    const html = (md) => env.Viewer.render(md);
    const dom = (md) => {
        const el = env.document.createElement('div');
        el.innerHTML = html(md);
        return el;
    };
    before(() => { env = createViewerEnv({ mermaid: false }); });

    it('renders the $$ display block from live-tiles-agentic', () => {
        const tex = String.raw`\text{transform: } \text{scale}(0.97) \,\, \text{perspective}(600\text{px}) \,\, \text{rotateX}(4^\circ)`;
        const el = dom(`Tilts into the 3D plane:\n$$${tex}$$\nThis micro-interaction originated...`);
        assert.equal(el.querySelectorAll('.katex-display').length, 1);
        assert.equal(el.querySelector('.katex-error'), null, 'KaTeX must not report an error');
        assert.equal(el.querySelector('annotation').textContent, tex);
        assert.doesNotMatch(el.textContent, /\$\$/);
    });

    it('renders multi-line $$ blocks', () => {
        const el = dom('$$\n\\frac{a}{b}\n$$');
        assert.equal(el.querySelectorAll('.katex-display').length, 1);
    });

    it('renders inline math, including ones that look like markdown (underscores, backslashes)', () => {
        const el = dom(String.raw`Small ($1\times 1$), norm $L_2$, flip $\leftrightarrow$ and $a_b + c_d$.`);
        assert.equal(el.querySelectorAll('.katex').length, 4);
        assert.equal(el.querySelector('em'), null, 'underscores in math must not become <em>');
        assert.equal(el.querySelector('.katex-display'), null);
    });

    it('does not treat prices as math', () => {
        const el = dom('It costs $5 and $10, or between $5 and $ 10.');
        assert.equal(el.querySelector('.katex'), null);
        assert.match(el.textContent, /\$5 and \$10/);
    });

    it('treats \\$ as a literal dollar sign', () => {
        const el = dom(String.raw`Pay \$3 then \$4 later`);
        assert.equal(el.querySelector('.katex'), null);
        assert.match(el.textContent, /Pay \$3 then \$4 later/);
    });

    it('leaves math syntax inside inline code and fenced code untouched', () => {
        const el = dom('Use `$x^2$` in text.\n\n```latex\n$$\\alpha + \\beta$$\n```\n\n~~~\n$y$\n~~~');
        assert.equal(el.querySelector('.katex'), null);
        const codes = Array.from(el.querySelectorAll('code')).map((c) => c.textContent);
        assert.ok(codes.includes('$x^2$'));
        assert.ok(codes.some((c) => c.includes('$$\\alpha + \\beta$$')));
        assert.ok(codes.some((c) => c.includes('$y$')));
    });

    it('does not leak placeholders', () => {
        assert.doesNotMatch(html('$$x$$ and $y$ and $$z$$'), /WKMATHPH/);
    });

    it('coexists with wiki-links on the same line', () => {
        const el = dom('See [[some-article]] where $E=mc^2$ holds.');
        assert.equal(el.querySelectorAll('.katex').length, 1);
        assert.equal(el.querySelectorAll('a.wiki-link').length, 1);
    });

    it('headings with math keep a stable slug and a clean ToC label', () => {
        env.document.getElementById('article-body').innerHTML =
            env.Viewer.render('## Intro\n\n### A. Flip (Front $\\leftrightarrow$ Back)\n\ntext');
        env.Viewer._setupHeadersAndToc('demo');

        const h3 = env.document.querySelector('#article-body h3');
        assert.equal(h3.id, env.window.Utils.slugify('A. Flip (Front $\\leftrightarrow$ Back)'),
            'slug is derived from the original markdown, as before KaTeX');
        const labels = Array.from(env.document.querySelectorAll('.toc-link')).map((a) => a.textContent.trim());
        assert.equal(labels.length, 2);
        assert.doesNotMatch(labels[1], /\\leftrightarrow|\$/, 'ToC must not show raw TeX or hidden MathML text');
        assert.match(labels[1], /^A\. Flip \(Front .* Back\)$/);
    });

    it('falls back to escaped source when KaTeX is unavailable (e.g. CDN blocked)', () => {
        const noKatex = createViewerEnv({ katex: false, mermaid: false });
        const out = noKatex.Viewer.render('Inline $a<b$ and\n$$x^2$$');
        assert.match(out, /math-fallback/);
        assert.match(out, /\$a&lt;b\$/);
        assert.match(out, /\$\$x\^2\$\$/);
        assert.doesNotMatch(out, /WKMATHPH/);
    });
});
