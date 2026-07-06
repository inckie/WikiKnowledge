---
categories:
- knowledge-sources
created: '2026-07-06T05:59:41.059450+00:00'
id: source-code-plugin
modified: '2026-07-06T05:59:41.059467+00:00'
tags:
- knowledge-sources
- source-code
- annotations
- multi-language
- plugin
title: Source Code Plugin
type: leaf
---

# Source Code Plugin

The Source Code Plugin allows developers to embed WikiKnowledge metadata directly into their source code documentation (like Python docstrings or JavaScript JSDoc blocks). 

This allows the codebase to act as a direct participant in the knowledge graph, without requiring sidecar files or duplicating information in the wiki.

## What Gets Captured

The plugin is designed to capture **architectural "forest" knowledge**, not code-level "trees".
- **Captured**: Module-level architectural descriptions, inter-module relationships, and design rationale.
- **Not Captured**: Detailed class hierarchies, method signatures, parameter lists, or inheritance trees. (Use dedicated code indexing tools for these).

## Annotation Conventions

Annotations use existing documentation conventions extended with `wk-` metadata fields. This means developers who don't use WikiKnowledge just see well-documented code.

### Python
Use module-level docstrings with RST-style fields:

```python
"""In-memory knowledge index for fast lookups.

:wk-id: index-engine
:wk-tags: architecture, index
:wk-categories: system-architecture

The indexing engine that makes the [[storage-abstraction]] queryable.
"""
```

### JavaScript
Use file-level JSDoc blocks with `@wk-*` tags:

```javascript
/**
 * Main Application Controller.
 *
 * @wk-id frontend-app
 * @wk-tags frontend, routing
 * @wk-categories system-architecture
 *
 * Coordinates views like [[markdown-viewer]].
 */
```

## Configuration

Source code bases are declared in `knowledge/sources.json`. This versioned file specifies the source name, plugin type, and language-specific include/exclude patterns:

```json
{
  "sources": {
    "wk": {
      "type": "source-code",
      "default_path": "../",
      "description": "WikiKnowledge's own source code",
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
    }
  }
}
```

Machine-specific path overrides can be placed in `.settings/sources.json` (which is typically gitignored), separating the structural definition of the source from its local path on a developer's machine.

## Self-Annotation Example
WikiKnowledge annotates its own source code as a dogfooding example. Modules like `wikiknowledge/storage/base.py` define their architectural role in the knowledge graph, allowing AI agents and developers to trace from high-level wiki categories directly into the source code modules that implement them.