# Google Drive Plugin — Architecture

## Overview

The Google Drive plugin is a `KnowledgeSourcePlugin` implementation that connects to Google Drive folders, discovers Google Docs, exports their content as markdown, and serves them as virtual articles in the WikiKnowledge knowledge graph. It supports optional bi-directional metadata synchronization.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      WikiKnowledge Core                             │
│           (Storage, Index, Graph, MCP, API, Frontend)               │
├─────────────────────────────────────────────────────────────────────┤
│                    Knowledge Source Manager                          │
│       (Loads config, instantiates plugins, merges virtual           │
│        articles into the index/graph)                               │
├──────────────┬──────────────┬───────────────────────────────────────┤
│  Source Code  │ Google Drive │  Future Plugins                      │
│  Plugin       │ Plugin       │  (Remote Wiki, API docs, ...)        │
│  (existing)   │ (NEW)        │                                      │
├──────────────┴──────────────┴───────────────────────────────────────┤
│  Local files    Google Drive API     Other data sources              │
│                 (Docs, Sheets, etc.)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

## Plugin Lifecycle

```
                    ┌──────────────────────┐
                    │    initialize()       │
                    │  - Load credentials   │
                    │  - Connect to Drive   │
                    │  - Load local cache   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  discover_articles()  │
                    │  - Check local cache  │
                    │  - Return cached data │
                    │  (fast startup)       │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  sync() (on demand)   │
                    │  - List Drive folder  │
                    │  - Compare modifiedAt │
                    │  - Export changed Docs │
                    │  - Update local cache │
                    │  - Optionally push    │
                    │    metadata back      │
                    └──────────────────────┘
```

### Startup (Fast Path — Cache Hit)

1. `initialize()` loads the service account credentials and validates the connection to Google Drive
2. `discover_articles()` reads `knowledge/.index/<source-name>/manifest.json` — if it exists and is recent enough, returns the cached article metadata immediately
3. `get_article_content(id)` reads from `knowledge/.index/<source-name>/articles/<doc-id>.md`
4. No Google API calls are made unless a sync is explicitly triggered

### Startup (No Cache — First Launch)

Behavior is controlled by the `auto_sync` config field (defaults to `false`):
- If `auto_sync: false` — plugin starts with no articles; user must trigger sync manually
- If `auto_sync: true` — plugin runs a full sync during `initialize()` on first launch (no cache exists)

### Sync (On Demand)

Sync is triggered by:
- The user clicking "Rescan" in the frontend settings panel
- The `rescan_sources` MCP tool
- The `/api/sources/rescan` REST endpoint

Sync procedure:
1. Call Google Drive API to list all files in the configured folder (recursive)
2. For each Google Doc, compare `modifiedTime` against the cached value in `manifest.json`
3. For changed/new docs: export as markdown via Google Docs export API, update local cache
4. For deleted docs: remove from cache
5. If `bidirectional: true`, push any locally-set `wk-categories` and `wk-tags` back to the Google Doc as custom `appProperties`
6. Save updated `manifest.json`

## Configuration

### In `knowledge/sources.json` (versioned)

```json
{
  "sources": {
    "design-docs": {
      "type": "google-drive",
      "description": "Team design documents on Google Drive",
      "folder_id": "1ABCxyz...",
      "bidirectional": true,
      "auto_sync": false,
      "export_format": "text/markdown",
      "recursive": true,
      "include_mime_types": [
        "application/vnd.google-apps.document"
      ],
      "exclude_patterns": [
        "Archive/*",
        "DRAFT *"
      ],
      "knowledge_bases": {
        "default": "self"
      }
    },
    "specs": {
      "type": "google-drive",
      "description": "Product specs from a different Drive account",
      "folder_id": "1DEFabc...",
      "bidirectional": false,
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

### In `knowledge/.settings/sources.json` (gitignored, per-machine)

```json
{
  "design-docs": {
    "credentials_file": "d:\\secrets\\wikiknowledge-sa.json"
  },
  "specs": {
    "credentials_file": "d:\\secrets\\other-sa.json"
  }
}
```

The service account JSON file is **never** stored in the repo. The `credentials_file` path in settings points to the actual file on this machine.

### Configuration Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `type` | Yes | — | Must be `"google-drive"` |
| `folder_id` | Yes | — | Google Drive folder ID to start scanning from |
| `description` | No | `""` | Human-readable description |
| `credentials_file` | Settings | — | Path to service account JSON (in `.settings/sources.json`) |
| `bidirectional` | No | `false` | If `true`, push `wk-categories` and `wk-tags` as custom properties on Google Docs |
| `auto_sync` | No | `false` | If `true`, automatically sync on first launch when no cache exists |
| `recursive` | No | `true` | Whether to scan subfolders |
| `export_format` | No | `"text/markdown"` | MIME type for Google Docs export. Falls back to `text/html` + `markdownify` if markdown export fails |
| `include_mime_types` | No | `["application/vnd.google-apps.document"]` | Which Google file types to include |
| `exclude_patterns` | No | `[]` | Glob-style patterns to exclude files/folders by path |
| `knowledge_bases` | No | `{"default": "self"}` | KB mapping (same as source-code plugin) |

## Virtual Article ID Format

Google Drive virtual articles use the `gdrive:` prefix — **not** the `src:<source-name>/` convention used by the source-code plugin. This makes IDs globally stable regardless of source name changes:

```
gdrive:<google-doc-id>
```

Examples:
- `gdrive:1aBcDeFgHiJkLmNoPqRsT`
- `gdrive:0xYzAbCdEfGhIjKlMn`

The Google Doc ID is globally unique and stable across renames/moves. If two sources happen to contain the same shared document, the first-registered source wins.

> **Note**: This differs from `SourceCodePlugin` which uses `src:<name>/<path>`. The `gdrive:` prefix was chosen because Google Doc IDs are already globally unique, and tying them to a source name would make all wiki-links break if a source is renamed.

## Article Metadata Mapping

| WikiKnowledge field | Google Drive source |
|---------------------|---------------------|
| `id` | `gdrive:<doc-id>` |
| `title` | Document title from Drive API |
| `type` | Always `ArticleType.LEAF` |
| `tags` | From `appProperties.wk_tags` (comma-separated) if bidirectional; empty otherwise |
| `categories` | From `appProperties.wk_categories` (comma-separated) if bidirectional; empty otherwise |
| `created` | `createdTime` from Drive API |
| `modified` | `modifiedTime` from Drive API |
| `content` | Exported markdown + footer with Drive link |

## Bi-Directional Metadata Flow

When `bidirectional: true`:

### Read (Drive → WikiKnowledge)

On sync, the plugin reads Google Docs `appProperties`:
- `wk_tags`: comma-separated tag list (e.g., `"architecture, design, api"`)
- `wk_categories`: comma-separated category list (e.g., `"system-architecture, api-docs"`)

These are mapped to `ArticleMeta.tags` and `ArticleMeta.categories`.

### Write (WikiKnowledge → Drive)

When a user sets categories or tags on a virtual article through the WikiKnowledge UI or MCP tools, the plugin:
1. Updates the local cache immediately
2. On next sync, calls `files.update()` with the new `appProperties`

This **does not modify the document content** — only the custom metadata fields. Document content remains read-only from WikiKnowledge's perspective.

### appProperties vs. properties

Google Drive offers two types of custom metadata:
- `properties`: Visible to all apps, max 30 key-value pairs, 124 bytes per key, 124 bytes per value
- `appProperties`: Private to the app that set them, same limits

We use `appProperties` because:
- They won't interfere with other apps using the same documents
- They're automatically scoped to our service account's project
- The size limits are adequate for tag/category lists

## Content Export Pipeline

```
Google Doc (native format)
  → Drive API export (MIME: text/markdown)
  → If empty or suspiciously short:
      → Retry with text/html export
      → Convert to markdown via markdownify
  → Post-processing:
      1. Clean up any formatting artifacts
      2. Extract [[wiki-links]] if present in the document
      3. Append footer with source link to original Google Doc
  → Store as .md in local cache
  → Serve as virtual article content
```

### Post-Processing Rules

1. **Title normalization**: If the first line of the exported markdown is a heading matching the document title, keep it. Otherwise, prepend `# <title>` as the first line.
2. **Wiki-link extraction**: Run the existing `extract_wiki_links()` parser on the exported content. Authors can use `[[wiki-links]]` directly in their Google Docs.
3. **Footer injection**: Append a horizontal rule and a link back to the original Google Doc:
   ```markdown
   ---
   🔌 **Source**: [View in Google Drive](https://docs.google.com/document/d/<doc-id>/edit)
   ```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid credentials | Plugin marked `unavailable`, logged at startup |
| Folder not found | Plugin marked `unavailable`, logged at startup |
| Network error during sync | Sync fails gracefully, cached data preserved, error reported to user |
| Single doc export fails | Skip doc, log warning, continue with rest |
| Rate limiting (429) | Exponential backoff with jitter, retry up to 3 times |
| Quota exhausted | Sync aborted, cached data preserved, error reported |

## Integration with Existing Codebase

### SourceManager (`manager.py`)

Add a new branch in `initialize()`:

```python
elif plugin_type == "google-drive":
    plugin = GoogleDrivePlugin(source_name, kb_alias)
    
    # Resolve credentials path from settings
    source_settings = settings.get(source_name, {})
    credentials_file = source_settings.get("credentials_file")
    decl["credentials_file"] = credentials_file
    
    await plugin.initialize(decl)
    self.plugins[source_name] = plugin
```

The `get_article_content()` routing in `SourceManager` must be updated to handle both `src:` and `gdrive:` prefixes:

```python
async def get_article_content(self, article_id: str) -> str:
    if article_id.startswith("gdrive:"):
        # Route to whichever Google Drive plugin owns this doc
        doc_id = article_id[7:]  # strip "gdrive:"
        for plugin in self.plugins.values():
            if isinstance(plugin, GoogleDrivePlugin) and plugin.has_article(article_id):
                return await plugin.get_article_content(article_id)
        raise KeyError(f"Google Drive article '{article_id}' not found")
    elif article_id.startswith("src:"):
        # Existing routing for source-code plugin
        ...
```

### Dependencies

New Python packages required:
- `google-api-python-client` — Google Drive API client
- `google-auth` — Service account authentication (dependency of the above)
- `markdownify` — Convert HTML to markdown (fallback if native markdown export quality is insufficient)

### File Structure (New Files)

```
wikiknowledge/core/plugins/
├── base.py                     # Existing — no changes
├── manager.py                  # Modify — add google-drive type branch
├── source_code.py              # Existing — no changes
└── google_drive.py             # NEW — GoogleDrivePlugin implementation
```
