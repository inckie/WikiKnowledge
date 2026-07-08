# Google Drive Plugin — Implementation Plan

## Phase 1: Core Plugin Implementation ✅ COMPLETE

**Goal**: Create a working `GoogleDrivePlugin` that can connect to Google Drive, list documents, export content, cache locally, and serve virtual articles.

### Step 1.1: Add Dependencies

- [x] Add `google-api-python-client>=2.100.0` and `google-auth>=2.23.0` to `pyproject.toml`
- [x] Run `uv sync` to update the lock file
- [x] Verify import works: `from googleapiclient.discovery import build`

### Step 1.2: Create `GoogleDrivePlugin` Class

File: `wikiknowledge/core/plugins/google_drive.py`

- [x] Create `GoogleDrivePlugin(KnowledgeSourcePlugin)` class
- [x] Implement `__init__(source_name, kb_name, kb_dir)` — set up instance variables
- [x] Implement `initialize(config)`:
  - Load service account credentials from `config["credentials_file"]`
  - Build `drive_service` using `googleapiclient.discovery.build`
  - Select OAuth scopes based on `bidirectional` flag: `drive.readonly` (default) or `drive` (bidirectional)
  - Validate connection by attempting to get folder metadata
  - Load local cache from `.index/<source-name>/manifest.json` if exists
  - If `auto_sync: true` and no cache exists, run initial sync automatically
  - Set `_available` based on success/failure
- [x] Implement `is_available()` — return `self._available`

### Step 1.3: Implement Cache Layer

- [x] Create `_load_cache()` method
- [x] Create `_write_manifest()` / `_read_manifest()` with atomic write (temp file + rename)
- [x] Create `_cache_dir` property returning `Path(kb_dir) / ".index" / source_name`
- [x] Implement `discover_articles()` — returns from in-memory cache (no API calls)
- [x] Implement `get_article_content(article_id)` — from memory, falls back to disk

### Step 1.4: Implement Sync Logic

- [x] Create `async sync()` method — delta sync (compare `modifiedTime`, new/updated/deleted/unchanged)
- [x] Create `_list_folder_recursive(folder_id, path, recursive, include_mime_types)` — pagination + exclude patterns
- [x] Create `_export_doc(doc_id, title, web_view_link)` — markdown first, HTML+markdownify fallback
- [x] Create article IDs using `gdrive:<doc-id>` format
- [x] Implement `get_links()` — return `_links` dict (populated during sync)
- [x] Implement `has_article(article_id)` — for routing in SourceManager

### Step 1.5: Register in SourceManager

File: `wikiknowledge/core/plugins/manager.py`

- [x] Import `GoogleDrivePlugin` (lazy, inside branch)
- [x] Add `elif plugin_type == "google-drive":` branch in `initialize()`
- [x] Pass `credentials_file` from machine-local settings into config dict
- [x] Update `get_article_content()` routing to handle `gdrive:` prefix
- [x] Richer `get_status()` — includes `last_sync`, `article_count`, `sync_status` for Drive sources

### Step 1.6: Extend SourceManager for Sync

- [x] Add `async sync_all()` — calls `plugin.sync()` on all Google Drive plugins
- [x] Update `rescan_sources` API endpoint (`sources.py`) to call `sync_all()` and return per-source results
- [x] Update `rescan_sources` MCP tool (`mcp_server.py`) to call `sync_all()`

### Step 1.7: Update `.gitignore`

- [x] Added `knowledge/.index/` and `knowledge/.settings/` to `.gitignore`

---

## Phase 2: Bi-Directional Metadata ✅ COMPLETE (implemented alongside Phase 1)

**Implemented in `google_drive.py` and `sources.py`.**

### Step 2.1: Read Metadata from Drive

- [x] During sync, read `appProperties.wk_tags` and `appProperties.wk_categories` from file metadata
- [x] Parse comma-separated values into lists
- [x] Populate `ArticleMeta.tags` and `ArticleMeta.categories`
- [x] Store in cache manifest

### Step 2.2: Write Metadata to Drive

- [x] Track `metadata_dirty` flag per article in manifest
- [x] `update_article_metadata()` method — sets dirty flag locally
- [x] During sync, `_push_dirty_metadata()` calls `files.update()` with new `appProperties`
- [x] Clear `metadata_dirty` after successful push
- [x] Warn if `appProperties` value exceeds 120 chars

### Step 2.3: API for Metadata Updates

- [x] `PUT /api/sources/<source-id>/articles/<article-id>/metadata` endpoint
- [x] Accepts `{ "tags": [...], "categories": [...] }` body
- [x] Updates cached metadata, sets `metadata_dirty`, and updates in-memory index

### Step 2.4: Conflict Resolution

- [x] Last-write-wins: local changes are pushed on next sync, overwriting Drive values
- [x] `metadata_modified_locally` timestamp stored in manifest

---

## Phase 3: Frontend & UX Integration ✅ COMPLETE

**Goal**: Make Google Drive sources visible and manageable in the frontend.

### Step 3.1: Settings Panel

- [x] Google Drive sources rendered as rich cards with cyan left-border accent
- [x] Displays: source name, folder ID, connection status pill, document count, last sync time + status badge, read-only/bidirectional tag
- [x] Per-source **"Sync Now"** button (calls `rescanSources` and shows detailed results toast)
- [x] Source-code sources retain path-override row (type-aware rendering)

### Step 3.2: Virtual Article Rendering

- [x] `gdrive:` articles shown with teal `Drive` chip badge in sidebar list
- [x] `src:` articles shown with indigo `Code` chip badge in sidebar list
- [x] Edit/delete buttons hidden for `gdrive:` articles (read-only)
- [x] "View in Google Drive" footer link appended to every exported document

### Step 3.3: Configuration UI

- [x] `rescanSources()` toast shows per-source Drive sync stats (`+N new · N updated`)
- [ ] Add-new-source UI form (deferred — config is currently file-based via sources.json)

---

## Phase 4: Documentation & Knowledge Base Updates ✅ COMPLETE

**Goal**: Update the WikiKnowledge knowledge base to reflect the new plugin.

### Step 4.1: Create Wiki Articles

- [x] Created `google-drive-plugin` leaf article under `knowledge-sources` category
  - Setup guide, config reference, bidirectional metadata, caching, multi-account
- [x] Updated `knowledge-sources` category article to link and describe the Drive plugin
- [x] Updated `source-code-plugin` article with "See Also" cross-references to Drive plugin

### Step 4.2: Annotate New Source Code

- [x] `google_drive.py` docstring contains `:wk-id:`, `:wk-tags:`, `:wk-categories:` annotations

---

## Phase 5: Testing & Hardening

### Step 5.1: Unit Tests

- [ ] Test cache loading/saving with mock manifest
- [ ] Test `_list_folder_recursive` with mock Drive API responses
- [ ] Test `_export_doc` with sample markdown/HTML content
- [ ] Test metadata conflict resolution logic
- [ ] Test delta sync (new, modified, deleted, unchanged docs)
- [ ] Test error handling (invalid credentials, network errors, rate limits)

### Step 5.2: Integration Testing

- [ ] Set up a test Google Drive folder with sample docs
- [ ] Test full lifecycle: connect → sync → discover → read content → rescan
- [ ] Test bidirectional: set tags in WikiKnowledge → verify appProperties on Drive
- [ ] Test disconnection: remove folder sharing → verify graceful degradation
- [ ] Test multi-source: two different Drive folders/accounts simultaneously

### Step 5.3: Edge Cases

- [ ] Large folders (1000+ documents)
- [ ] Documents with no content
- [ ] Documents with complex formatting (tables, images, code blocks)
- [ ] Folder name changes (article IDs use doc ID, not path — should be stable)
- [ ] Documents moved between folders
- [ ] Concurrent sync requests
- [ ] Cache corruption recovery
