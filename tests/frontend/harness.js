/**
 * Test harness: loads the real browser scripts (frontend/js/utils.js + viewer.js)
 * into a jsdom window together with marked, KaTeX and Mermaid from npm, mirroring
 * the CDN libraries used by frontend/index.html.
 */
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..');
export const kbArticlesDir = path.join(repoRoot, 'knowledge', 'articles');

/** Absolute path of a file inside a locally installed npm package (bypasses exports maps). */
const nm = (...parts) => path.join(here, 'node_modules', ...parts);
const read = (p) => readFileSync(p, 'utf8');

/**
 * @param {object} [opts]
 * @param {boolean} [opts.katex=true]   expose window.katex
 * @param {boolean} [opts.mermaid=true] expose window.mermaid
 * @param {string[]} [opts.articles]    known article ids for wiki-link resolution
 */
export function createViewerEnv({ katex = true, mermaid = true, articles = [] } = {}) {
    const dom = new JSDOM(
        '<!DOCTYPE html><body><div id="article-toc"></div><div id="article-body"></div></body>',
        { runScripts: 'outside-only', pretendToBeVisual: true, url: 'http://127.0.0.1/' },
    );
    const { window } = dom;

    // marked (UMD build exposes window.marked)
    window.eval(read(nm('marked', 'lib', 'marked.umd.js')));
    if (katex) window.eval(read(nm('katex', 'dist', 'katex.min.js')));
    if (mermaid) {
        new vm.Script(read(nm('mermaid', 'dist', 'mermaid.min.js'))).runInContext(dom.getInternalVMContext());
        window.mermaid.initialize({ startOnLoad: false, theme: 'default' });
    }

    // Top-level `const` in classic scripts is not a window property; re-export explicitly.
    window.eval(read(path.join(repoRoot, 'frontend', 'js', 'utils.js')) + '\nwindow.Utils = Utils;');
    window.eval(read(path.join(repoRoot, 'frontend', 'js', 'viewer.js')) + '\nwindow.Viewer = Viewer;');

    window.Viewer.setKnownArticles(articles.map((id) => ({ id })));
    return { window, Viewer: window.Viewer, document: window.document };
}
