import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createViewerEnv } from './harness.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = (name) => readFileSync(path.join(here, 'fixtures', name), 'utf8');

/** Extract the first fenced ```mermaid block's code from markdown. */
const mermaidFence = (md) => md.match(/```mermaid\n([\s\S]*?)```/)[1];

/** Render markdown, mount in the DOM, return the decoded source of each .mermaid block. */
function mermaidSourcesOf(env, markdown) {
    env.document.getElementById('article-body').innerHTML = env.Viewer.render(markdown);
    return Array.from(env.document.querySelectorAll('.mermaid')).map((el) => env.Viewer._mermaidSourceFromElement(el));
}

describe('mermaid: live-tiles-agentic regression', () => {
    let env;
    before(() => { env = createViewerEnv({ articles: ['vm-agent-workers', 'panorama-pattern'] }); });

    it('the raw diagram really is rejected by Mermaid (unquoted parentheses in an edge label)', async () => {
        // Guards the root-cause analysis: if Mermaid ever accepts this, the repair becomes a no-op.
        const raw = mermaidFence(fixture('live-tiles-agentic.md'));
        assert.equal(await env.window.mermaid.parse(raw, { suppressErrors: true }), false);
    });

    it('survives the markdown -> HTML -> decode round trip with <b>, <br/> and <--> intact', () => {
        const [src] = mermaidSourcesOf(env, fixture('live-tiles-agentic.md'));
        assert.equal(src, mermaidFence(fixture('live-tiles-agentic.md')).trim());
        assert.match(src, /<b>Autonomous Agent Scout \(in VM\)<\/b><br\/>/);
        assert.match(src, /Front <-->\|/);
    });

    it('is repaired and parses', async () => {
        const [src] = mermaidSourcesOf(env, fixture('live-tiles-agentic.md'));
        const res = await env.Viewer.resolveMermaidSource(src);
        assert.equal(res.ok, true, res.error);
        assert.match(res.source, /<-->\|"3D Y-Axis Flip \(Periodic or Tap\)"\|/);
        assert.match(res.source, /<b>Autonomous Agent Scout/, 'formatting tags must be preserved');
    });
});

describe('mermaid: valid diagrams are never altered', () => {
    let env;
    before(() => { env = createViewerEnv(); });

    const valid = {
        flowchart: 'flowchart TD\n    A[Start] --> B{Is it working?};\n    B -- Yes --> C[Great!];\n    B -- No --> D[Debug];',
        quotedParens: 'flowchart LR\n    A["Node (with parens)"] -->|"edge (quoted)"| B',
        formatting: 'flowchart LR\n    A["<b>bold</b><br/>line two"] --> B',
        bidirectional: 'flowchart LR\n    A <-->|sync| B',
        sequence: 'sequenceDiagram\n    Alice->>Bob: Hello (hi)\n    Bob-->>Alice: Hi',
        stateChoice: 'stateDiagram-v2\n    state fork <<choice>>\n    [*] --> fork\n    fork --> A\n    fork --> B',
        classInterface: 'classDiagram\n    class Shape {\n        <<interface>>\n        +draw()\n    }',
    };

    for (const [name, src] of Object.entries(valid)) {
        it(`${name}: resolves to the identical source`, async () => {
            const res = await env.Viewer.resolveMermaidSource(src);
            assert.equal(res.ok, true, res.error);
            assert.equal(res.source, src);
        });
    }
});

describe('mermaid: pseudo-tag escaping', () => {
    let env;
    before(() => { env = createViewerEnv(); });

    it('escapes unknown tags like <appId> and generics', () => {
        const out = env.Viewer.escapeMermaidPseudoTags('A["id=<appId>, List<int>, </foo>"]');
        assert.equal(out, 'A["id=#lt;appId#gt;, List#lt;int#gt;, #lt;/foo#gt;"]');
    });

    it('keeps real formatting tags and mermaid arrows/stereotypes', () => {
        const src = 'A["<b>x</b><br/><br>y<i>z</i>"] <--> B\nstate f <<choice>>\n<<interface>>';
        assert.equal(env.Viewer.escapeMermaidPseudoTags(src), src);
    });

    it('a diagram with <appId> placeholders parses', async () => {
        const res = await env.Viewer.resolveMermaidSource('flowchart LR\n    A["GET /apps/<appId>/tiles"] --> B["<b>ok</b>"]');
        assert.equal(res.ok, true, res.error);
        assert.match(res.source, /#lt;appId#gt;/);
    });
});

describe('mermaid: repairMermaidSource', () => {
    let env;
    before(() => { env = createViewerEnv(); });

    it('quotes unquoted node labels containing parentheses (rect and diamond)', async () => {
        const src = 'flowchart TD\n    A[Start (now)] --> B{Ready (yes/no)?}';
        assert.equal(await env.window.mermaid.parse(src, { suppressErrors: true }), false);
        const fixed = env.Viewer.repairMermaidSource(src);
        assert.equal(fixed, 'flowchart TD\n    A["Start (now)"] --> B{"Ready (yes/no)?"}');
        assert.ok(await env.window.mermaid.parse(fixed, { suppressErrors: true }));
    });

    it('leaves special shapes and already-quoted labels alone', () => {
        const src = 'flowchart TD\n    A[(Database)] --> B[[Sub]] --> C[/Trap/] --> D["q (x)"]';
        assert.equal(env.Viewer.repairMermaidSource(src), src);
    });

    it('does not touch non-flowchart diagrams', () => {
        const src = 'sequenceDiagram\n    A->>B: call(x) |pipe (y)|';
        assert.equal(env.Viewer.repairMermaidSource(src), src);
    });
});

describe('mermaid: unfixable diagrams', () => {
    let env;
    before(() => { env = createViewerEnv(); });

    it('reports ok=false with a message', async () => {
        const res = await env.Viewer.resolveMermaidSource('flowchart LR\n    A --> --> ((( B');
        assert.equal(res.ok, false);
        assert.ok(res.error.length > 0);
    });

    it('renderMermaid shows an error box (not a bomb) and still renders sibling diagrams', async () => {
        const md = '```mermaid\nflowchart LR\n    A --> --> ((( B\n```\n\ntext\n\n```mermaid\nflowchart LR\n    X --> Y\n```';
        env.document.getElementById('article-body').innerHTML = env.Viewer.render(md);
        // jsdom has no layout (getBBox), so stub the SVG step; parse/repair run for real.
        env.window.mermaid.render = async (id, text) => ({ svg: `<svg data-src="${text.length}"></svg>` });

        await env.Viewer.renderMermaid();

        const blocks = env.document.querySelectorAll('.mermaid');
        assert.equal(blocks.length, 2);
        assert.ok(blocks[0].classList.contains('mermaid-failed'));
        assert.ok(blocks[0].querySelector('.mermaid-error-msg').textContent.length > 0);
        assert.match(blocks[0].querySelector('.mermaid-error-src').textContent, /A --> --> \(\(\( B/);
        assert.ok(blocks[1].querySelector('svg'), 'valid sibling diagram must render');
    });

    it('renderMermaid is idempotent (does not re-process rendered blocks)', async () => {
        let calls = 0;
        env.document.getElementById('article-body').innerHTML = env.Viewer.render('```mermaid\nflowchart LR\n    A --> B\n```');
        env.window.mermaid.render = async () => { calls++; return { svg: '<svg></svg>' }; };
        await env.Viewer.renderMermaid();
        await env.Viewer.renderMermaid();
        assert.equal(calls, 1);
    });
});
