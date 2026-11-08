/**
 * Links inside Mermaid diagrams. The viewer turns [[...]] into <a>/<span> markup *before*
 * Mermaid sees the source, so every pre-processing step (pseudo-tag escaping, syntax repair,
 * entity round trip) has to leave that markup intact.
 */
import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { createViewerEnv } from './harness.js';

const diagram = (body) => '```mermaid\n' + body + '\n```';

describe('mermaid: links inside diagrams', () => {
    let env;
    const mount = (md) => {
        const el = env.document.getElementById('article-body');
        el.innerHTML = env.Viewer.render(md);
        return Array.from(el.querySelectorAll('.mermaid'));
    };
    const sourceOf = (block) => env.Viewer._mermaidSourceFromElement(block);

    before(() => {
        env = createViewerEnv({
            articles: [
                'plain-article',
                'src:mysrc/module',
                'gdrive:doc123',
            ],
        });
        env.Viewer.setKnownResources([
            { id: 'spec-pdf', title: 'Spec', mime_type: 'application/pdf', description: 'The spec' },
        ]);
        env.Viewer._currentArticleId = 'current-article';
    });

    it('every link flavor resolves and the diagram still parses', async () => {
        const [block] = mount(diagram([
            'flowchart TD',
            '    A["[[plain-article]]"] --> B["[[plain-article|Display Text]]"]',
            '    B --> C["[[plain-article#some-section|Anchored]]"]',
            '    C --> D["[[#local-section|Same page]]"]',
            '    D --> E["[[src:mysrc/module|Source code]]"]',
            '    E --> F["[[gdrive:doc123|Drive doc]]"]',
            '    F --> G["[[src:gone/thing|Disconnected source]]"]',
            '    G --> H["[[no-such-article|Missing]]"]',
            '    H --> I["[[file:spec-pdf|The spec]]"]',
            '    I --> J["[[file:nope|Missing file]]"]',
        ].join('\n')));

        const hrefs = Array.from(block.querySelectorAll('a[href]')).map((a) => a.getAttribute('href'));
        assert.deepEqual(hrefs.filter((h) => h.startsWith('#/article/')), [
            '#/article/plain-article',
            '#/article/plain-article',
            '#/article/plain-article#some-section',
            '#/article/current-article#local-section',
            '#/article/src%3Amysrc%2Fmodule',
            '#/article/gdrive%3Adoc123',
            '#/article/no-such-article',
        ]);
        assert.ok(block.querySelector('a.wiki-link.missing'), 'missing target is flagged');
        assert.ok(block.querySelector('span.wiki-link.disconnected'), 'disconnected source rendered as span');
        assert.ok(block.querySelector('a.file-link[href="/api/resources/spec-pdf/file"]'));

        const res = await env.Viewer.resolveMermaidSource(sourceOf(block));
        assert.equal(res.ok, true, res.error);
    });

    it('pre-processing leaves the link markup byte-for-byte intact for valid diagrams', async () => {
        const [block] = mount(diagram('flowchart LR\n    A["Go to [[plain-article|Plain]]<br/>and [[src:mysrc/module|Src]]"] --> B'));
        const src = sourceOf(block);
        const res = await env.Viewer.resolveMermaidSource(src);
        assert.equal(res.ok, true, res.error);
        assert.equal(res.source, src, 'no escaping/repair may touch <a>/<span>/<br/>');
        assert.equal((res.source.match(/<a /g) || []).length, 2);
        assert.match(res.source, /href="#\/article\/plain-article"/);
    });

    it('links survive together with auto-repair of an unquoted edge label', async () => {
        const [block] = mount(diagram([
            'flowchart LR',
            '    A["[[plain-article|Start]]"] -->|Flip (Periodic or Tap)| B["<b>[[src:mysrc/module|Back]]</b>"]',
        ].join('\n')));
        const src = sourceOf(block);
        assert.equal(await env.window.mermaid.parse(src, { suppressErrors: true }), false, 'precondition: broken as written');

        const res = await env.Viewer.resolveMermaidSource(src);
        assert.equal(res.ok, true, res.error);
        assert.match(res.source, /\|"Flip \(Periodic or Tap\)"\|/);
        assert.match(res.source, /href="#\/article\/plain-article"/);
        assert.match(res.source, /href="#\/article\/src%3Amysrc%2Fmodule"/);
        assert.match(res.source, /<b><a /);
    });

    it('links survive together with pseudo-tag escaping', async () => {
        const [block] = mount(diagram('flowchart LR\n    A["GET /apps/<appId> -> [[plain-article|docs]]"] --> B'));
        const res = await env.Viewer.resolveMermaidSource(sourceOf(block));
        assert.equal(res.ok, true, res.error);
        assert.match(res.source, /#lt;appId#gt;/);
        assert.match(res.source, /<a class="wiki-link" href="#\/article\/plain-article"/);
    });

    it('a link in an edge label parses', async () => {
        const [block] = mount(diagram('flowchart LR\n    A -->|"see [[plain-article|docs]]"| B'));
        const res = await env.Viewer.resolveMermaidSource(sourceOf(block));
        assert.equal(res.ok, true, res.error);
        assert.match(res.source, /<a class="wiki-link"/);
    });

    it('a link in a subgraph title parses', async () => {
        const [block] = mount(diagram('flowchart TD\n    subgraph S["Group: [[plain-article|Plain]]"]\n        A --> B\n    end'));
        const res = await env.Viewer.resolveMermaidSource(sourceOf(block));
        assert.equal(res.ok, true, res.error);
    });

    it('links in other diagram types (sequence participants/messages) parse', async () => {
        const [block] = mount(diagram('sequenceDiagram\n    participant A as [[plain-article|Plain]]\n    A->>B: see [[src:mysrc/module|code]]'));
        const res = await env.Viewer.resolveMermaidSource(sourceOf(block));
        assert.equal(res.ok, true, res.error);
    });

    it('renderMermaid hands Mermaid the link markup and keeps what Mermaid returns', async () => {
        mount(diagram('flowchart LR\n    A["[[plain-article|Plain]]"] --> B'));
        let received = '';
        env.window.mermaid.render = async (id, text) => {
            received = text;
            return { svg: '<svg><a href="#/article/plain-article"><text>Plain</text></a></svg>' };
        };
        await env.Viewer.renderMermaid();
        assert.match(received, /<a class="wiki-link" href="#\/article\/plain-article"/);
        assert.equal(env.document.querySelectorAll('.mermaid svg a[href="#/article/plain-article"]').length, 1);
        assert.equal(env.document.querySelectorAll('.mermaid-failed').length, 0);
    });

    it('link syntax in the *editor preview* mode (isPreview=true) also works', async () => {
        const html = env.Viewer.render(diagram('flowchart LR\n    A["[[plain-article|Plain]]"] --> B["![[embedded]]"]'), true);
        const el = env.document.createElement('div');
        el.innerHTML = html;
        const block = el.querySelector('.mermaid');
        assert.ok(block.querySelector('a.wiki-link'));
        const res = await env.Viewer.resolveMermaidSource(sourceOf(block));
        assert.equal(res.ok, true, res.error);
    });
});
