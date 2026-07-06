# Plugin Architecture Design

## Overview

Knowledge Sources is a plugin-based system that allows external data to contribute "virtual articles" to the WikiKnowledge knowledge graph. Each plugin type implements a common interface, and specific source instances are declared in a configuration file.

## Layered Architecture

```
┌─────────────────────────────────────────────────┐
│              WikiKnowledge Core                  │
│  (Storage, Index, Graph, MCP, API, Frontend)     │
├─────────────────────────────────────────────────┤
│           Knowledge Source Manager               │
│  (Loads config, instantiates plugins, merges     │
│   virtual articles into the index/graph)         │
├──────────┬──────────┬──────────┬────────────────┤
│ Source   │ Source   │ Remote   │  Future        │
│ Code     │ Code     │ Wiki     │  Plugins       │
│ Plugin   │ Plugin   │ Plugin   │  (API docs,    │
│ (Python) │ (JS)     │          │   DB schema,   │
│          │          │          │   etc.)         │
├──────────┴──────────┴──────────┴────────────────┤
│  d:\project-a   d:\project-b   http://other-wk  │
│  (Actual data sources on disk / network)         │
└─────────────────────────────────────────────────┘
```

## Key Concepts

### Virtual Articles

A "virtual article" is an `ArticleMeta` + content produced by a plugin from external source material. Virtual articles:

- Have IDs namespaced by their source: `src:wk/storage-contract` (source "wk", module path "storage-contract")
- Participate fully in the index: tags, categories, forward links, back links
- Are **read-only** from the wiki side — edits go to the source file
- Are **ephemeral** — they exist only while the source is connected; when disconnected, their links show a "disconnected" state instead of "broken"

### Source Identity

Each connected source has:
- **name**: A short identifier used in wiki links (e.g., `wk`, `myapp`, `frontend`)
- **type**: The plugin type (`source-code`, `remote-wiki`, etc.)
- **status**: `connected`, `disconnected`, `error`
- **config**: Plugin-specific settings (root directory, language, file patterns, etc.)

### Multi-KB Linking

A single source codebase can be connected to **multiple WikiKnowledge knowledge bases** simultaneously. This is common when:
- A project has separate KBs for architecture docs, API specs, and operations guides
- A shared library is documented across multiple product KBs
- An organization has per-team KBs that reference the same codebase

**Default behavior**: If a source is connected to only one KB, all `[[wiki-links]]` in its annotations resolve against that KB — no additional syntax needed.

**Multi-KB behavior**: When connected to multiple KBs, source annotations can use the `@kb-name` qualifier to target a specific KB: `[[article-id@kb-name]]`. The "default" KB (the one that loaded the source) needs no qualifier. See `link-syntax.md` for full specification.

### Plugin Interface (Conceptual)

Each plugin type must implement:

```python
class KnowledgeSourcePlugin(ABC):
    """Base interface for all knowledge source plugins."""
    
    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Connect to the source and prepare for article discovery."""
    
    @abstractmethod
    async def discover_articles(self) -> list[ArticleMeta]:
        """Scan the source and return metadata for all discoverable articles."""
    
    @abstractmethod
    async def get_article_content(self, article_id: str) -> str:
        """Read the full content of a virtual article."""
    
    @abstractmethod
    async def get_links(self) -> dict[str, list[WikiLink]]:
        """Extract all wiki links from all virtual articles."""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the source is currently reachable."""
    
    async def on_change(self, callback) -> None:
        """Optional: register a file-watcher callback for live updates."""
```

## Configuration (Two-Part Split)

Configuration is split into two files with distinct roles:

### 1. Declaration File: `knowledge/sources.json`

**Purpose**: Declares what sources exist, how to parse them, and their default location.  
**Versioned**: Yes — committed to the repo, travels with the knowledge base.  
**Scope**: Structural — defines the shape of the connection.

This file lives in the knowledge directory itself, alongside `articles/` and `categories/`. It is part of the KB's identity.

```json
{
  "sources": {
    "wk": {
      "type": "source-code",
      "default_path": "../",
      "description": "WikiKnowledge's own source code",
      "knowledge_bases": {
        "default": "self"
      },
      "languages": {
        "python": {
          "include": ["wikiknowledge/**/*.py"],
          "exclude": ["**/__pycache__/**", "**/.venv/**"]
        },
        "javascript": {
          "include": ["frontend/js/**/*.js"],
          "exclude": []
        }
      }
    },
    "my-app": {
      "type": "source-code",
      "default_path": "../../../Projects/MyApp",
      "description": "Main application codebase",
      "knowledge_bases": {
        "default": "self",
        "api-docs": { "url": "http://localhost:8002" }
      },
      "languages": {
        "python": {
          "include": ["src/**/*.py"],
          "exclude": ["**/tests/**"]
        }
      }
    },
    "partner-wiki": {
      "type": "remote-wiki",
      "default_path": null,
      "description": "Partner team's documentation",
      "url": "http://localhost:8003"
    }
  }
}
```

**Key fields per source**:

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Plugin type: `source-code`, `remote-wiki`, etc. |
| `default_path` | No | Default location relative to `knowledge/` dir. For same-repo sources, this is typically `../` or `../../path`. If null, must be specified in settings. |
| `description` | No | Human-readable description of the source. |
| `knowledge_bases` | No | Map of KB names this source can link to. `"default": "self"` means the current KB. Omit entirely for single-KB (default behavior). |
| `languages` | For `source-code` | Per-language include/exclude patterns. |
| `url` | For `remote-wiki` | URL of the remote WikiKnowledge instance. |

### 2. Settings Override: `knowledge/.settings/sources.json`

**Purpose**: Machine-specific path overrides for sources whose actual location differs from the declaration's `default_path`.  
**Versioned**: No — `.settings/` is typically gitignored. Each developer/machine has their own.  
**Scope**: Operational — says where things are *right now* on this machine.

```json
{
  "my-app": {
    "path": "d:\\Work\\Projects\\MyApp"
  },
  "partner-wiki": {
    "url": "http://192.168.1.50:8003"
  }
}
```

Only sources that need an override appear here. For same-repo sources where `default_path` is correct (e.g., WikiKnowledge annotating itself with `"default_path": "../"`), no entry is needed.

### Resolution Order

When the source manager needs the actual path for a source:

1. Check `knowledge/.settings/sources.json` for an override → use it if present
2. Fall back to `default_path` from `knowledge/sources.json` (resolved relative to `knowledge/` dir)
3. If neither exists → source is `disconnected` (not an error — the source may not be on this machine)

## Integration Points

### With KnowledgeIndex

The index currently builds from `all_meta` and `all_links` dicts. Virtual articles would be merged into these dicts before building:

```python
# Pseudocode in lifespan / initialization
all_meta = dict(storage._meta_cache)
all_links = storage.get_all_links()

for source_name, plugin in source_manager.plugins.items():
    if plugin.is_available():
        virtual_meta = await plugin.discover_articles()
        virtual_links = await plugin.get_links()
        all_meta.update({m.id: m for m in virtual_meta})
        all_links.update(virtual_links)

index.build(all_meta=all_meta, all_links=all_links, ...)
```

### With KnowledgeGraph

No changes needed — the graph already reads from the index, which will contain virtual articles.

### With MCP Server

The `get_article`, `list_articles`, `search` tools would need to check both storage and source plugins. Virtual articles would be marked as read-only in their output.

### With Frontend

Virtual articles would render with a visual indicator (e.g., a source icon, different color in the graph) to distinguish them from native wiki articles. The editor would be disabled or show a "view source" link.

### With Parser

The existing `extract_wiki_links()` function would need to understand:
- `[[src:...]]` link syntax for source-qualified links
- `[[...@kb-name]]` syntax for KB-qualified links (see `link-syntax.md`)

## Disconnection Behavior

When a source becomes unavailable (directory removed, server down):

1. The source manager marks it as `disconnected`
2. Virtual articles from that source are removed from the index
3. Links pointing TO those virtual articles are marked as "disconnected" (visually distinct from "broken" — they are expected to return)
4. Links FROM those virtual articles (in wiki articles' backlink lists) are removed
5. On reconnection, the source is re-scanned and re-integrated

This is different from broken links (which indicate an error in the content) — disconnected links indicate a temporarily absent source.

The same principle applies to KB-qualified links (`[[article@kb-name]]`) when the target KB is unreachable — they degrade to "disconnected", not "broken".

## Future Plugin Types

The architecture is designed to accommodate:

- **Remote WikiKnowledge**: Connects to another WikiKnowledge instance's API, importing its articles as virtual articles in this graph
- **API Documentation**: Parses OpenAPI specs, gRPC proto files, or GraphQL schemas
- **Database Schema**: Reads schema definitions and produces articles describing tables/collections
- **Issue Trackers**: Connects to GitHub Issues, Jira, etc. to surface project context
