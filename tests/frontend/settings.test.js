import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..');
const read = (p) => readFileSync(p, 'utf8');

function createSettingsEnv({ sources, onUpdatePath, onRescan } = {}) {
    const dom = new JSDOM(
        `<!DOCTYPE html><body>
            <div id="sources-container"></div>
            <button id="btn-rescan-sources">🔄 Re-scan Sources</button>
            <div id="stats-overview-grid"></div>
        </body>`,
        { runScripts: 'outside-only', url: 'http://127.0.0.1/' },
    );
    const { window } = dom;

    let currentSources = structuredClone(sources || []);
    const calls = {
        updateSourcePath: [],
        rescanSources: 0,
        loadArticles: 0,
        loadSidebar: [],
        getStats: 0,
    };

    window.API = {
        async getSources() {
            return structuredClone(currentSources);
        },
        async updateSourcePath(id, newPath) {
            calls.updateSourcePath.push({ id, path: newPath });
            const resp = onUpdatePath
                ? onUpdatePath(id, newPath, currentSources)
                : { status: 'ok', source_id: id, path: newPath, available: true, virtual_articles_discovered: 3 };
            const idx = currentSources.findIndex((s) => s.id === id);
            if (idx !== -1 && resp.source) {
                currentSources[idx] = resp.source;
            }
            return resp;
        },
        async rescanSources() {
            calls.rescanSources += 1;
            return onRescan ? onRescan(currentSources) : { virtual_articles_discovered: 5, sync_results: {} };
        },
        async getStats() {
            calls.getStats += 1;
            return {
                total_articles: 10,
                native_articles: 5,
                external_articles: 5,
                total_links: 2,
                total_categories: 1,
                total_tags: 1,
                total_resources: 0,
                broken_links_count: 0,
                orphaned_pages_count: 0,
                broken_links: [],
                orphaned_pages: [],
            };
        },
    };

    window.App = {
        async _loadArticles() {
            calls.loadArticles += 1;
        },
        async _loadSidebarContent(view) {
            calls.loadSidebar.push(view);
        },
    };

    window.eval(read(path.join(repoRoot, 'frontend', 'js', 'utils.js')) + '\nwindow.Utils = Utils;');
    window.eval(read(path.join(repoRoot, 'frontend', 'js', 'settings.js')) + '\nwindow.Settings = Settings;');

    return { window, document: window.document, Settings: window.Settings, calls };
}

describe('Settings source path updates', () => {
    it('saves, applies, updates status immediately, and strips surrounding quotes', async () => {
        const { document, Settings, calls } = createSettingsEnv({
            sources: [
                { id: 'quickbrick', type: 'SourceCodePlugin', available: false, path: 'D:\\old\\qb' },
                { id: 'frameworks', type: 'SourceCodePlugin', available: true, path: 'D:\\old\\fw' },
            ],
            onUpdatePath: (id, newPath) => ({
                status: 'ok',
                source_id: id,
                path: newPath,
                available: true,
                virtual_articles_discovered: 12,
                source: { id, type: 'SourceCodePlugin', available: true, path: newPath },
            }),
        });

        await Settings.loadSources();

        const qbInput = document.getElementById('src-path-quickbrick');
        const fwInput = document.getElementById('src-path-frameworks');
        assert.equal(qbInput.value, 'D:\\old\\qb');

        // Edit sibling input without saving yet; it must not be wiped when quickbrick updates.
        fwInput.value = 'D:\\unsaved\\fw';
        qbInput.value = '"D:\\new\\qb"';

        await Settings.updateSourcePath('quickbrick');

        assert.deepEqual(calls.updateSourcePath, [{ id: 'quickbrick', path: 'D:\\new\\qb' }]);
        assert.equal(document.getElementById('src-path-quickbrick').value, 'D:\\new\\qb');
        assert.equal(document.getElementById('src-path-quickbrick').disabled, false);
        assert.equal(document.getElementById('btn-update-path-quickbrick').disabled, false);

        const qbCard = document.querySelector('[data-source-id="quickbrick"]');
        assert.match(qbCard.textContent, /● Connected/);
        assert.match(qbCard.querySelector('.source-card-subtitle').textContent, /D:\\new\\qb/);

        // Sibling unsaved edit is preserved
        assert.equal(document.getElementById('src-path-frameworks').value, 'D:\\unsaved\\fw');

        // App articles, sidebar, and stats were refreshed
        assert.equal(calls.loadArticles, 1);
        assert.deepEqual(calls.loadSidebar, ['articles']);
        assert.equal(calls.getStats, 1);

        const toast = document.querySelector('.toast');
        assert.ok(toast);
        assert.match(toast.className, /toast-success/);
        assert.match(toast.textContent, /Saved & applied/);
    });

    it('shows disconnected status and error toast when updated path does not exist', async () => {
        const { document, Settings } = createSettingsEnv({
            sources: [
                { id: 'docs', type: 'MarkdownFilesPlugin', available: true, path: 'D:\\docs' },
            ],
            onUpdatePath: (id, newPath) => ({
                status: 'ok',
                source_id: id,
                path: newPath,
                available: false,
                virtual_articles_discovered: 0,
                source: { id, type: 'MarkdownFilesPlugin', available: false, path: newPath },
            }),
        });

        await Settings.loadSources();
        document.getElementById('src-path-docs').value = 'D:\\missing';
        await Settings.updateSourcePath('docs');

        const docsCard = document.querySelector('[data-source-id="docs"]');
        assert.match(docsCard.textContent, /⊘ Disconnected/);
        assert.equal(document.getElementById('src-path-docs').value, 'D:\\missing');

        const toast = document.querySelector('.toast');
        assert.ok(toast);
        assert.match(toast.className, /toast-error/);
        assert.match(toast.textContent, /Disconnected/);
    });

    it('refreshes app articles, sidebar, and stats after rescanSources', async () => {
        const { Settings, calls } = createSettingsEnv({
            sources: [{ id: 'docs', type: 'MarkdownFilesPlugin', available: true, path: 'D:\\docs' }],
        });

        await Settings.loadSources();
        await Settings.rescanSources();

        assert.equal(calls.rescanSources, 1);
        assert.equal(calls.loadArticles, 1);
        assert.deepEqual(calls.loadSidebar, ['articles']);
        assert.equal(calls.getStats, 1);
    });
});
