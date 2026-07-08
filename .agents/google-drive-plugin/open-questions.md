# Google Drive Plugin — Open Questions

Design decisions that need user input before proceeding. These are recorded here for persistence across sessions.

---

## 1. Initial Sync on First Launch

**Question**: When the plugin is configured but no cache exists yet, should `initialize()` perform an automatic sync, or should the user manually trigger the first sync?

**Option A — Auto-sync on first launch**:
- Pro: Plugin "just works" after configuration
- Con: Could be slow if the folder has many documents; delays app startup

**Option B — Manual first sync**:
- Pro: Predictable startup time; user controls when API calls happen
- Con: Plugin appears empty until user clicks "Rescan"

**Recommendation**: Option B (manual first sync) — consistent with the "sync on demand only" philosophy. The settings panel can show a prominent "Sync Now" button and a message like "No cached data — click Sync to import documents from Google Drive."

**Status**: ✅ Resolved — configurable via `auto_sync` field in `sources.json`, defaults to `false` (manual). When `true`, plugin runs initial sync automatically on first launch if no cache exists.

---

## 2. Markdown Export Quality

**Question**: Google Drive's `text/markdown` export is relatively new and may produce suboptimal results for complex formatting. Should we:

**Option A — Use markdown export directly**, accepting formatting limitations?

**Option B — Use HTML export + `markdownify` conversion** for better fidelity?

**Option C — Try markdown first, fall back to HTML+markdownify** if the result looks broken (heuristic: empty output, very short output relative to HTML version)?

**Recommendation**: Option C — try markdown first for speed and simplicity, fall back when needed. Add `markdownify` as an optional dependency.

**Status**: ✅ Resolved — Option C. Try `text/markdown` export first, fall back to HTML + `markdownify` if output is empty or suspiciously short. `markdownify` is an optional dependency.

---

## 3. Virtual Article ID Stability

**Question**: Virtual article IDs are `src:<source-name>/<google-doc-id>`. Google Doc IDs are globally unique and stable across renames/moves. However, if the user reconfigures the source with a different `source-name`, all article IDs change. Should we:

**Option A — Use source name in ID** (current design): `src:design-docs/1aBcDeFg...`
- Pro: Clear provenance, no collisions between sources
- Con: Renaming a source breaks all links to its articles

**Option B — Use only doc ID**: `gdrive:1aBcDeFg...`  
- Pro: Stable even if source is renamed
- Con: If two sources contain the same doc (shared), ambiguity

**Recommendation**: Option A — consistent with existing `SourceCodePlugin` convention. Source renaming should be a rare operation.

**Status**: ✅ Resolved — Option B. Article IDs use `gdrive:<google-doc-id>` format. Globally stable across source renames. If two sources contain the same shared doc, first-registered wins.

---

## 4. Handling Non-Google-Docs Files

**Question**: The configured folder may contain non-Google-Docs files (PDFs, images, spreadsheets, etc.). Should we:

**Option A — Ignore them entirely** (only process `application/vnd.google-apps.document`)?

**Option B — List them but serve their metadata only** (title, type, link to Drive) without content?

**Option C — Support additional types** like Google Sheets (as tables) and uploaded markdown files?

**Recommendation**: Option A for v1 — keep scope tight. The `include_mime_types` config field allows future expansion without architecture changes.

**Status**: ✅ Resolved — Option A. Only `application/vnd.google-apps.document` (Google Docs) for v1. The `include_mime_types` config field is ready for future expansion.

---

## 5. Folder ID vs. Folder Name in Config

**Question**: Should the configuration reference Google Drive folders by ID or by name/path?

**Option A — Folder ID** (current design): `"folder_id": "1ABCxyz..."`
- Pro: Globally unique, stable across renames
- Con: Not human-readable, user needs to extract from URL

**Option B — Folder path**: `"folder_path": "My Drive/Design Docs"`
- Pro: Human-readable
- Con: Ambiguous (multiple folders can have the same name), fragile across renames

**Option C — Both**: Accept either `folder_id` or `folder_path`, preferring ID if both given.

**Recommendation**: Option A (ID only) — the ID is easily extracted from the Google Drive URL (`https://drive.google.com/drive/folders/<ID>`), and stability is more important than readability in a config file.

**Status**: ✅ Resolved — Option A. Folder referenced by ID only (`folder_id` field). Extracted from Drive URL.

---

## 6. Where to Store Locally-Modified Metadata

**Question**: When the user updates tags/categories on a Google Drive virtual article via the WikiKnowledge UI, where should the changes be persisted before the next sync pushes them to Drive?

**Option A — In the manifest.json** (add `metadata_dirty` flag)
- Pro: Simple, all cache data in one place
- Con: Manifest grows more complex

**Option B — In a separate `metadata_overrides.json`** file in the cache directory
- Pro: Clean separation of cached vs. modified data
- Con: More files to manage

**Recommendation**: Option A — keep it simple. The manifest is already per-source, and dirty flags are lightweight.

**Status**: ✅ Resolved — Option A. Dirty metadata stored in `manifest.json` with `metadata_dirty` flag per article.

---

## 7. Scope of Drive Permissions for Bidirectional Mode

**Question**: Bidirectional mode requires `drive` scope (full access) instead of `drive.readonly`. Should we:

**Option A — Request full `drive` scope always**, regardless of `bidirectional` setting?
- Pro: Simpler code
- Con: Over-privileged when not needed

**Option B — Request `drive.readonly` by default, upgrade to `drive` only when `bidirectional: true`**?
- Pro: Principle of least privilege
- Con: Requires recreating credentials/service if user later enables bidirectional

**Recommendation**: Option B — use the minimum required scope. Document that changing bidirectional mode may require updating the service account's shared permissions.

**Status**: ✅ Resolved — Option B. Use `drive.readonly` scope by default; upgrade to `drive` scope only when `bidirectional: true`.
