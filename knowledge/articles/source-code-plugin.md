---
categories:
- knowledge-sources
created: '2026-07-06T05:59:41.059450+00:00'
id: source-code-plugin
modified: '2026-07-18T07:04:08.027708+00:00'
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

The Source Code Plugin allows developers to embed WikiKnowledge articles directly into their source code documentation (like Python docstrings or JavaScript JSDoc blocks). 

This allows the codebase to act as a direct participant in the knowledge graph, eliminating data duplication and context-switching.

## The Three Tiers of AI-Driven Knowledge

In an AI-driven development environment, knowledge is strictly separated into three layers. The Source Code Plugin is critical for handling the final tier:

1. **Human Functional Requirements (The "What")**: The top-level specifications defined by humans in the wiki.
2. **Implementation Overview (The "Broad Stroke")**: The wiki category overviews detailing how tasks are decomposed using architectural multipliers.
3. **Source Code Short Articles (The "How")**: The specific interfaces and implementation details. Instead of duplicating this in the wiki, this knowledge lives directly inside the source code as detailed docstring articles (similar to JavaDoc). 

By extracting these short articles directly from the code, AIs don't need to waste thousands of tokens trying to parse function bodies to reverse-engineer the system. They simply read the parsed `wk-` article block.

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