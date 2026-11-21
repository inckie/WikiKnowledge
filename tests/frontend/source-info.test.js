import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..');
const utilsSrc = readFileSync(path.join(repoRoot, 'frontend', 'js', 'utils.js'), 'utf8');

function loadUtils() {
    const dom = new JSDOM('<!DOCTYPE html><body></body>', { runScripts: 'outside-only' });
    dom.window.eval(utilsSrc + '\nwindow.Utils = Utils;');
    return dom.window.Utils;
}

describe('Utils.getSourceInfo', () => {
    const Utils = loadUtils();

    it('maps canonical source_type values to badge info', () => {
        assert.deepEqual({ ...Utils.getSourceInfo({ id: 'a1', type: 'leaf', source_type: 'native' }) }, {
            type: 'native',
            badgeClass: 'native',
            badgeText: 'Wiki',
            icon: '📄',
            label: 'Wiki Article',
        });

        assert.deepEqual({ ...Utils.getSourceInfo({ id: 'c1', type: 'category', source_type: 'native' }) }, {
            type: 'native',
            badgeClass: 'native',
            badgeText: 'Wiki',
            icon: '📁',
            label: 'Wiki Article',
        });

        assert.deepEqual({ ...Utils.getSourceInfo({ id: 'src:app/mod', source_type: 'code' }) }, {
            type: 'code',
            badgeClass: 'code',
            badgeText: 'Code',
            icon: '💻',
            label: 'Source Code',
        });

        assert.deepEqual({ ...Utils.getSourceInfo({ id: 'src:docs/readme', source_type: 'markdown' }) }, {
            type: 'markdown',
            badgeClass: 'markdown',
            badgeText: 'Markdown',
            icon: '📄',
            label: 'Markdown Document',
        });

        assert.deepEqual({ ...Utils.getSourceInfo({ id: 'gdrive:123', source_type: 'drive' }) }, {
            type: 'drive',
            badgeClass: 'drive',
            badgeText: 'Drive',
            icon: '☁️',
            label: 'Google Drive Document',
        });
    });

    it('falls back to native when source_type is missing and source for unknown values', () => {
        assert.equal(Utils.getSourceInfo({ id: 'src:docs/readme' }).type, 'native');
        assert.equal(Utils.getSourceInfo(null).type, 'native');

        assert.deepEqual({ ...Utils.getSourceInfo({ id: 'custom:1', source_type: 'jira' }) }, {
            type: 'source',
            badgeClass: 'source',
            badgeText: 'Source',
            icon: '🔌',
            label: 'External Source',
        });
    });

    it('ignores misleading tags and IDs in favor of source_type', () => {
        const mdWithCodeTags = Utils.getSourceInfo({
            id: 'src:docs/api',
            tags: ['python', 'javascript', 'code', 'java'],
            source_type: 'markdown',
        });
        assert.equal(mdWithCodeTags.type, 'markdown');
        assert.equal(mdWithCodeTags.badgeClass, 'markdown');

        const codeWithGuidesId = Utils.getSourceInfo({
            id: 'src:repo/guides/docs',
            tags: ['markdown', 'md'],
            source_type: 'code',
        });
        assert.equal(codeWithGuidesId.type, 'code');
        assert.equal(codeWithGuidesId.badgeClass, 'code');

        const nativeWithSrcPrefix = Utils.getSourceInfo({
            id: 'gdrive:fake',
            tags: ['python'],
            source_type: 'native',
        });
        assert.equal(nativeWithSrcPrefix.type, 'native');
    });
});
