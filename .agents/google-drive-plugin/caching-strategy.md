# Google Drive Plugin — Caching Strategy

## Overview

The Google Drive plugin uses a local file cache in `knowledge/.index/<source-name>/` to avoid hitting the Google Drive API on every application startup. The cache stores exported markdown content and metadata, enabling instant startup with stale-but-available data.

## Cache Directory Structure

```
knowledge/
└── .index/
    └── <source-name>/                # e.g., "design-docs"
        ├── manifest.json             # Index of all cached articles + sync metadata
        └── articles/
            ├── <doc-id-1>.md         # Exported markdown content
            ├── <doc-id-2>.md
            └── ...
```

The `.index/` directory should be gitignored (add to `.gitignore` if not already present).

## manifest.json Format

```json
{
  "source_name": "design-docs",
  "last_sync": "2026-07-08T04:30:00Z",
  "folder_id": "1ABCxyz...",
  "sync_status": "success",
  "articles": {
    "1aBcDeFgHiJkLmNoPqRsT": {
      "title": "Authentication Architecture",
      "drive_modified": "2026-07-07T15:23:00Z",
      "cached_at": "2026-07-08T04:30:12Z",
      "drive_created": "2026-06-15T10:00:00Z",
      "mime_type": "application/vnd.google-apps.document",
      "drive_path": "Design/Authentication Architecture",
      "web_view_link": "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsT/edit",
      "tags": ["architecture", "auth"],
      "categories": ["system-architecture"],
      "size_bytes": 4523
    },
    "0xYzAbCdEfGhIjKlMn": {
      "title": "API Rate Limiting Spec",
      "drive_modified": "2026-07-06T09:12:00Z",
      "cached_at": "2026-07-08T04:30:15Z",
      "drive_created": "2026-06-20T14:00:00Z",
      "mime_type": "application/vnd.google-apps.document",
      "drive_path": "Specs/API Rate Limiting Spec",
      "web_view_link": "https://docs.google.com/document/d/0xYzAbCdEfGhIjKlMn/edit",
      "tags": ["api", "rate-limiting"],
      "categories": ["api-docs"],
      "size_bytes": 2891
    }
  }
}
```

### Manifest Fields

| Field | Description |
|-------|-------------|
| `source_name` | Name of this source in `sources.json` |
| `last_sync` | ISO 8601 timestamp of the last successful full sync |
| `folder_id` | The root folder ID that was synced |
| `sync_status` | `"success"`, `"partial"` (some docs failed), or `"error"` |
| `articles.<doc-id>.title` | Document title from Google Drive |
| `articles.<doc-id>.drive_modified` | `modifiedTime` from Drive API at time of cache |
| `articles.<doc-id>.cached_at` | When this specific doc was last exported |
| `articles.<doc-id>.drive_created` | `createdTime` from Drive API |
| `articles.<doc-id>.drive_path` | Reconstructed path from folder hierarchy |
| `articles.<doc-id>.web_view_link` | Direct link to the document in Google Drive |
| `articles.<doc-id>.tags` | Current tags (may include locally-set values) |
| `articles.<doc-id>.categories` | Current categories (may include locally-set values) |
| `articles.<doc-id>.size_bytes` | Size of the cached markdown file |

## Sync Protocol

### Step 1: List Remote Files

```python
# Pseudocode
results = drive_service.files().list(
    q=f"'{folder_id}' in parents and trashed = false",
    fields="files(id, name, mimeType, modifiedTime, createdTime, webViewLink, appProperties)",
    pageSize=1000,
).execute()
```

If `recursive: true`, recursively list subfolders too.

### Step 2: Compute Delta

For each file returned by the API:
- **New doc** (not in manifest): Export and add to cache
- **Modified doc** (`modifiedTime` > `drive_modified` in manifest): Re-export and update cache
- **Unchanged doc**: Skip (keep cached version)
- **Deleted doc** (in manifest but not in API results): Remove from cache

### Step 3: Export Changed Docs

For each new/modified Google Doc:

```python
content = drive_service.files().export(
    fileId=doc_id,
    mimeType="text/markdown"  # or configured export_format
).execute()
```

Save to `articles/<doc-id>.md`.

### Step 4: Update Manifest

Write the updated `manifest.json` atomically (write to temp file, then rename).

### Step 5: Push Metadata (if bidirectional)

For docs with locally-modified tags/categories:

```python
drive_service.files().update(
    fileId=doc_id,
    body={
        "appProperties": {
            "wk_tags": ",".join(tags),
            "wk_categories": ",".join(categories)
        }
    }
).execute()
```

## Startup Behavior (Cache Hit vs. Miss)

### Cache Hit (Normal Startup)

1. `initialize()` checks if `knowledge/.index/<source-name>/manifest.json` exists
2. If yes, load manifest, set `_available = True`
3. `discover_articles()` iterates manifest entries, constructs `ArticleMeta` objects from cached data
4. `get_article_content()` reads from `articles/<doc-id>.md`
5. **No API calls made** — instant startup

### Cache Miss (First Run or Cache Cleared)

1. `initialize()` finds no manifest
2. Plugin is still marked as `_available = True` (credentials are valid)
3. `discover_articles()` returns empty list (no cached data)
4. User must trigger a sync (Rescan) to populate the cache
5. Alternatively: `initialize()` could do an initial sync automatically — see Open Questions

## Cache Invalidation

The cache is **never automatically invalidated**. It is only refreshed when:
1. User clicks "Rescan" in the settings panel
2. An MCP tool triggers `rescan_sources`
3. The REST API `/api/sources/rescan` is called

This is intentional — Google Drive API quotas are limited, and we don't want background polling. The user is in control of when to sync.

## Metadata Conflict Resolution

When `bidirectional: true`, metadata can be set from two sources:
1. **From Google Drive**: `appProperties` set directly on the doc (by another tool or manually)
2. **From WikiKnowledge**: User sets tags/categories via the wiki UI

### Resolution Rule: Last Write Wins

During sync:
1. Read `appProperties` from Drive
2. If Drive has tags/categories and they differ from cached values AND the document was modified since last sync → Drive values win (the author may have updated them intentionally)
3. If cached values were modified locally since last sync AND the document was NOT modified → Local values win (push to Drive)
4. If both were modified → Drive values win (document author takes precedence), but log a warning

This is a simple heuristic. We track "locally modified" metadata with a `metadata_dirty` flag per article in the manifest.

## Rate Limiting and Quotas

Google Drive API quotas (default):
- 20,000 queries per 100 seconds per project
- 10 queries per second per user

Our approach:
- Batch file listing with `pageSize=1000` to minimize calls
- Export only changed docs (delta sync)
- No background polling
- On 429 responses: exponential backoff (1s, 2s, 4s) with jitter, max 3 retries
- If quota is exhausted, abort sync gracefully and preserve cached data
