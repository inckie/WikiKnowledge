---
categories:
- knowledge-sources
created: '2026-07-08T13:00:00.000000+00:00'
id: google-drive-plugin
modified: '2026-07-08T13:00:00.000000+00:00'
tags:
- knowledge-sources
- google-drive
- plugin
- sync
- cache
title: Google Drive Plugin
type: leaf
---

# Google Drive Plugin

The Google Drive Plugin connects WikiKnowledge to one or more Google Drive folders via a service account, discovering Google Docs and making their content available as **virtual articles** in the knowledge graph. Documents are exported as markdown and cached locally for fast startup; the cache is refreshed on demand via a manual sync.

This complements the [[source-code-plugin|Source Code Plugin]] — where the source-code plugin captures architectural knowledge embedded in code, the Drive plugin captures knowledge that lives in collaborative documents.

## What Gets Captured

- **Google Docs** (`application/vnd.google-apps.document`) within the configured folder tree
- Content is exported as markdown (with HTML + `markdownify` fallback for complex formatting)
- Optional **tags and categories** stored as Google Drive `properties` (`wk_tags`, `wk_categories`), readable and writable by WikiKnowledge when `bidirectional` mode is enabled

Other file types (Sheets, PDFs, images) are ignored in v1. Non-Docs files will be supported in a future release via the `include_mime_types` config field.

## Configuration

### 1. Declare the source in `knowledge/sources.json`

```json
{
  "sources": {
    "my-drive": {
      "type": "google-drive",
      "description": "Shared team knowledge in Google Drive",
      "folder_id": "1ABCxyz...",
      "bidirectional": false,
      "auto_sync": false,
      "recursive": true,
      "include_mime_types": [
        "application/vnd.google-apps.document"
      ],
      "knowledge_bases": {
        "default": "self"
      }
    }
  }
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `type` | ✓ | — | Must be `"google-drive"` |
| `folder_id` | ✓ | — | Google Drive folder ID (from the Drive URL) |
| `description` | — | `""` | Human-readable label shown in the UI |
| `bidirectional` | — | `false` | If `true`, tags/categories are synced back to Drive via custom `properties` |
| `auto_sync` | — | `false` | If `true`, automatically sync on first launch when no cache exists |
| `recursive` | — | `true` | Whether to scan subfolders recursively |
| `include_mime_types` | — | Google Docs only | Additional MIME types to include |
| `exclude_patterns` | — | `[]` | Glob patterns to exclude files or folders by path |

### 2. Set the credentials path in `knowledge/.settings/sources.json`

This file is **machine-local** (gitignored) and holds the path to your service account JSON key:

```json
{
  "my-drive": {
    "credentials_file": "/path/to/service-account-key.json"
  }
}
```

### 3. Getting the folder ID

Open the target folder in Google Drive and extract the ID from the URL:

```
https://drive.google.com/drive/folders/1CF4hdB2reTiplbsV6pPEtGgq9ZBFa4R1
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        this is the folder_id
```

### 4. Service Account Setup

1. Create a **Google Cloud project** and enable the **Google Drive API**
2. Create a **Service Account** and download its JSON key file
3. **Share the target Drive folder** with the service account's email address (at least Viewer access; Editor required for bidirectional mode)

The plugin requests only the minimum required OAuth scope:
- `drive.readonly` — when `bidirectional: false`
- `drive` (full) — when `bidirectional: true`

## Virtual Article IDs

Google Drive articles use the `gdrive:` ID prefix. The Google Doc ID is used directly, making article IDs **globally stable** regardless of document renames, folder moves, or source name changes:

```
gdrive:1AxAubXmVpPNOHFANk_1shZcE_3zKxUQtM5INMLw3404
```

This differs from the [[source-code-plugin|Source Code Plugin]] which uses `src:<source-name>/<path>`. Because Google Doc IDs are already globally unique, there is no need to namespace them by source name.

## Local Cache

The plugin caches all content locally in `knowledge/.index/<source-name>/` (gitignored):

```
knowledge/.index/my-drive/
  manifest.json          ← sync metadata, timestamps, tags/categories per doc
  articles/
    1AxAubXmV....md      ← exported markdown, one file per Google Doc
```

On startup, the plugin loads the manifest and article files into memory — **no Google API calls are made**. API calls only happen during an explicit sync triggered by:
- Clicking **"Sync Now"** in the settings panel (per-source button)
- Clicking **"Re-scan Sources"** (rescans all sources)
- The `rescan_sources` MCP tool
- `auto_sync: true` on first launch (no cache exists)

### Delta Sync

Each sync compares the remote `modifiedTime` with the cached value:

| Change | Action |
|---|---|
| New document | Export, cache, add to index |
| Modified document | Re-export, update cache and manifest |
| Deleted document | Remove from cache and index |
| Unchanged document | Load from cache, no API call |

## Bi-Directional Metadata

When `bidirectional: true`, WikiKnowledge can write category and tag assignments back to Google Drive via the file's **`properties`**. This uses the Drive API's custom file properties, which are durable, public to apps, and persist across different credentials. 

To easily view and edit these metadata properties directly from within the Google Doc UI, you can install the [[google-docs-extension|Google Docs Extension]].

### Reading metadata from Drive

During sync, `properties.wk_tags` and `properties.wk_categories` are read as comma-separated strings and used to populate the article's tags and categories. (Note: for legacy support, it falls back to `appProperties` if `properties` is empty).

### Writing metadata to Drive

When tags or categories are updated on a Drive article via the API or frontend UI:

```http
PUT /api/sources/my-drive/articles/gdrive:1AxA.../metadata
Content-Type: application/json

{ "tags": ["architecture", "design"], "categories": ["knowledge-sources"] }
```

The change is pushed immediately to Drive via `files.update(properties={...})`. As a fallback (if the API call fails due to a network error), the change is persisted locally and marked `metadata_dirty: true` in the manifest to be pushed on the next sync.

> **Limit**: Google Drive `properties` values are capped at approximately 124 characters per field. Tags or categories strings exceeding this limit will be truncated and a warning logged.

## Content Export Pipeline

```
Google Doc (native format)
  → Drive API export (MIME: text/markdown)
  → If empty or < 20 chars:
      → Retry with text/html export
      → Convert to markdown via markdownify
  → Post-processing:
      • Ensure H1 heading matches document title
      • Append "View in Google Drive" footer link
  → Store as .md in local cache
  → Serve as virtual article content
```

## Multiple Accounts / Folders

Multiple Google Drive sources can be configured independently in `sources.json`, each with its own source name, folder, credentials file, and bidirectional setting:

```json
{
  "sources": {
    "team-docs": {
      "type": "google-drive",
      "folder_id": "1AAA...",
      ...
    },
    "client-drive": {
      "type": "google-drive",
      "folder_id": "1BBB...",
      ...
    }
  }
}
```

Each source gets its own cache directory (`knowledge/.index/team-docs/`, `knowledge/.index/client-drive/`) and its own credentials file, allowing connections to different Google accounts simultaneously.

## Related

- [[google-docs-extension|Google Docs Extension]] — Apps Script extension for editing metadata inside Google Docs
- [[source-code-plugin|Source Code Plugin]] — the other built-in knowledge source plugin
- [[source-link-syntax|Source Link Syntax]] — how to link to virtual articles in wiki text
- [[knowledge-sources|Knowledge Sources]] — the plugin architecture overview
