/**
 * Renders every real article of the project's own knowledge base and asserts structural
 * invariants, so docs that *show* markup examples (human/AI markers, wiki links, mermaid)
 * keep displaying them as examples rather than interpreting them.
 */
import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { createViewerEnv, kbArticlesDir } from './harness.js';

const files = readdirSync(kbArticlesDir).filter((f) => f.endsWith('.md'));
const read = (id) => readFileSync(path.join(kbArticlesDir, `${id}.md`), 'utf8').replace(/^---[\s\S]*?\n---\n/, '');

describe('own knowledge base renders', () => {
    let env;
    const mount = (md) => {
        const el = env.document.getElementById('article-body');
        el.innerHTML = env.Viewer.render(md);
        return el;
    };
    before(() => { env = createViewerEnv({ articles: files.map((f) => f.replace(/\.md$/, '')) }); });

    for (const file of files) {
        const id = file.replace(/\.md$/, '');
        it(`${id}: renders without leaking placeholders; all mermaid blocks parse`, async () => {
            const el = mount(read(id));
            assert.ok(el.innerHTML.length > 0);
            assert.doesNotMatch(el.innerHTML, /WKMATHPH\d+PH|__WK_CODE_\d+__/);
            for (const block of el.querySelectorAll('.mermaid')) {
                const res = await env.Viewer.resolveMermaidSource(env.Viewer._mermaidSourceFromElement(block));
                assert.equal(res.ok, true, `${id}: ${res.error}`);
            }
        });
    }

    it('ai-interaction-guide: marker examples in code fences stay literal code', () => {
        const el = mount(read('ai-interaction-guide'));
        assert.equal(el.querySelectorAll('pre .block-human, pre .block-ai, pre .block-badge').length, 0);
        const code = Array.from(el.querySelectorAll('pre code')).map((c) => c.textContent).join('\n');
        assert.match(code, /<!-- human:start -->/);
        assert.match(code, /<!-- ai:end -->/);
        assert.ok(el.querySelector('pre code.language-python'), 'python example keeps its language class');
    });

    it('human-protected-blocks: examples (incl. nested-marker error example) stay literal code', () => {
        const el = mount(read('human-protected-blocks'));
        assert.equal(el.querySelectorAll('pre .block-human, pre .block-ai').length, 0);
        const code = Array.from(el.querySelectorAll('pre code')).map((c) => c.textContent).join('\n');
        assert.match(code, /<!-- human:start -->\s*\n.*\n<!-- human:start -->\s+← ERROR: nested open/s);
        assert.match(code, /### \[\[rigid-body-dynamics\|Rigid Body Dynamics\]\]/, 'wiki link in an example is not resolved');
    });

    it('wiki-link-syntax: [[links]] shown in code fences are not turned into anchors', () => {
        const el = mount(read('wiki-link-syntax'));
        assert.equal(el.querySelectorAll('pre a, code a').length, 0);
        const code = Array.from(el.querySelectorAll('pre code')).map((c) => c.textContent).join('\n');
        assert.match(code, /\[\[/);
        assert.doesNotMatch(code, /<a /);
    });

    it('real (unfenced) human/ai blocks are still decorated', () => {
        const el = mount('<!-- human:start -->\nHello\n<!-- human:end -->\n\n<!-- ai:start -->\nWorld\n<!-- ai:end -->');
        assert.equal(el.querySelectorAll('.block-human').length, 1);
        assert.equal(el.querySelectorAll('.block-ai').length, 1);
    });

    it('mermaid-diagrams: wiki links inside diagram nodes are resolved and the diagram parses', async () => {
        const linked = createViewerEnv({
            articles: [
                'src:wikiknowledge/fastapi-backend', 'src:wikiknowledge/kb-mcp',
                'src:wikiknowledge/in-memory-index', 'src:wikiknowledge/storage-abstraction',
            ],
        });
        const el = linked.document.getElementById('article-body');
        el.innerHTML = linked.Viewer.render(read('mermaid-diagrams'));
        const blocks = Array.from(el.querySelectorAll('.mermaid'));
        assert.equal(blocks.length, 2);
        assert.equal(blocks[1].querySelectorAll('a.wiki-link').length, 4);
        const res = await linked.Viewer.resolveMermaidSource(linked.Viewer._mermaidSourceFromElement(blocks[1]));
        assert.equal(res.ok, true, res.error);
    });

    it('embedding-search: its $$ equation renders as KaTeX', () => {
        const el = mount(read('embedding-search'));
        assert.ok(el.querySelectorAll('.katex-display').length >= 1);
        assert.equal(el.querySelector('.katex-error'), null);
    });
});
