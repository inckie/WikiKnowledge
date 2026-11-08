/**
 * Guards against encoding corruption of the frontend sources (e.g. a tool re-saving UTF-8
 * as ANSI, turning "—" into "вЂ”" / "â€”"). Fails on mojibake or invalid UTF-8.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'frontend');
const files = [
    'index.html',
    ...readdirSync(path.join(frontend, 'js')).map((f) => `js/${f}`),
    ...readdirSync(path.join(frontend, 'css')).map((f) => `css/${f}`),
];

// UTF-8 punctuation/emoji lead bytes misread as Windows-1251 / Windows-1252 / Latin-1.
const MOJIBAKE = /вЂ[”“™›‹¦¢\u0098\u009c\u009d]|рџ|в[ЂќљњќћќЏ]|â€|â†|â˜|âœ|Ã[\u0080-\u00bf]|ðŸ/;

describe('frontend sources are clean UTF-8', () => {
    for (const rel of files) {
        it(rel, () => {
            const buf = readFileSync(path.join(frontend, rel));
            const text = new TextDecoder('utf-8', { fatal: true }).decode(buf); // throws on invalid UTF-8
            const hit = text.split('\n').findIndex((l) => MOJIBAKE.test(l));
            assert.equal(hit, -1, `${rel}:${hit + 1} looks double-encoded: ${text.split('\n')[hit]?.trim()}`);
            assert.notEqual(text.charCodeAt(0), 0xfeff, 'unexpected BOM');
        });
    }
});
