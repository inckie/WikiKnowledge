# Source Code Annotation Conventions

## Guiding Principle

Use **existing documentation conventions** for each programming language, extended with a small set of `wk:`-prefixed metadata fields. Developers who don't use WikiKnowledge see well-documented code. AI agents and the WikiKnowledge parser see structured article metadata.

## Annotation Placement

Annotations go in **module-level / file-level** documentation blocks only. We do NOT annotate individual classes, functions, or methods — that's the domain of code indexing tools (language servers, Codebase Memory MCP, etc.).

One file = at most one virtual article.

## Python Convention

Use the **module-level docstring** (the first string literal in the file). WikiKnowledge metadata uses RST-style field list syntax (`:field-name: value`), which is a standard Python documentation convention used by Sphinx.

### Format

```python
"""Short title of this module.

:wk-id: source-name/module-path
:wk-tags: tag1, tag2, tag3
:wk-categories: category-id-1, category-id-2

Architectural description of what this module does, how it fits
into the broader system, and why it exists.

Can contain [[wiki-links]] to other articles and
[[src:source-name/other-module]] links to other source modules.

Can use full markdown formatting including headers, lists,
code blocks, etc. — same as wiki article content.
"""
```

### Example (from WikiKnowledge's own codebase)

```python
"""In-memory knowledge index for fast lookups.

:wk-id: wk/index-engine
:wk-tags: architecture, index, search, graph
:wk-categories: system-architecture

The indexing engine that makes the [[storage-abstraction|storage layer]]
queryable without touching the filesystem. On startup, it ingests all
article metadata and wiki links from [[src:wk/markdown-storage]], then
builds four inverted indices:

- **Forward links**: article → outgoing wiki links
- **Back links**: article → incoming wiki links ("what links here")
- **Tag index**: tag → set of article IDs
- **Category index**: category → set of member article IDs

The index supports both full rebuilds (on startup) and incremental
single-article updates (on save/delete), keeping the system responsive
during editing without requiring a restart.

The [[src:wk/graph-builder]] consumes this index to produce the D3.js
visualization data, and the [[src:wk/mcp-interface]] exposes index
queries as MCP tools for AI agents.
"""
```

### Parsing Rules for Python

1. Read the module-level docstring (first expression if it's a string literal)
2. Extract `:wk-*:` fields from the docstring body using RST field list regex
3. The first line (before any blank line) becomes the article title
4. Everything after the `:wk-*:` fields block is the article content
5. If no `:wk-id:` is present, the file is not a virtual article — skip it

### Existing Convention Compatibility

- `:wk-*:` fields coexist with standard RST fields like `:param:`, `:returns:`, `:raises:`
- Sphinx and other doc tools ignore unknown field names
- Type checkers and linters ignore docstring contents
- The format is valid RST — no syntax errors in existing tooling

---

## JavaScript Convention

Use the **file-level JSDoc block** (first `/** ... */` comment in the file). WikiKnowledge metadata uses `@wk-*` tags, following JSDoc's `@tag` convention.

### Format

```javascript
/**
 * Short title of this module.
 *
 * @wk-id source-name/module-path
 * @wk-tags tag1, tag2, tag3
 * @wk-categories category-id-1, category-id-2
 *
 * Architectural description of what this module does.
 *
 * Can contain [[wiki-links]] and [[src:source-name/module]] links.
 */
```

### Example (from WikiKnowledge's own frontend)

```javascript
/**
 * WikiKnowledge — Main Application Controller.
 *
 * @wk-id wk/frontend-app
 * @wk-tags frontend, routing, spa, controller
 * @wk-categories system-architecture
 *
 * The single-page application shell that orchestrates all frontend
 * modules. Manages hash-based routing (#view/article-id, #edit/article-id,
 * #graph), sidebar article list, and view transitions.
 *
 * Consumes the REST API served by [[src:wk/api-app]] via the Api
 * module ([[src:wk/frontend-api]]).
 *
 * Coordinates three main views:
 * - **Viewer** ([[src:wk/markdown-viewer]]): renders articles with
 *   live wiki-link resolution
 * - **Editor** ([[src:wk/frontend-editor]]): split-pane markdown editing
 * - **Graph** ([[src:wk/graph-visualization]]): D3.js knowledge graph
 */
```

### Parsing Rules for JavaScript

1. Find the first `/** ... */` block at file scope
2. Extract `@wk-*` tags using JSDoc tag regex
3. The first line of the comment (stripping `* ` prefix) becomes the title
4. Everything after the `@wk-*` tags block is the article content
5. Standard JSDoc tags (`@param`, `@returns`, `@module`, etc.) are ignored
6. If no `@wk-id` is present, skip the file

### Existing Convention Compatibility

- `@wk-*` tags coexist with standard JSDoc tags
- JSDoc generators ignore unknown tags (or can be configured to do so)
- ESLint and TypeScript ignore JSDoc content
- The format is valid JSDoc — no tooling breaks

---

## Other Languages (Future)

The pattern extends naturally:

### Java / Kotlin
```java
/**
 * Module Title.
 *
 * @wk-id source/module-path
 * @wk-tags tag1, tag2
 * @wk-categories category-id
 *
 * Architectural description...
 */
package com.example.mymodule;
```

### Rust
```rust
//! Module Title.
//!
//! :wk-id: source/module-path
//! :wk-tags: tag1, tag2
//! :wk-categories: category-id
//!
//! Architectural description with [[wiki-links]]...
```

### Go
```go
// Package mypackage provides...
//
// :wk-id: source/module-path
// :wk-tags: tag1, tag2
// :wk-categories: category-id
//
// Architectural description with [[wiki-links]]...
package mypackage
```

### C# / C++
```csharp
/// <summary>
/// Module Title.
/// </summary>
/// <remarks>
/// <wk-id>source/module-path</wk-id>
/// <wk-tags>tag1, tag2</wk-tags>
/// <wk-categories>category-id</wk-categories>
///
/// Architectural description with [[wiki-links]]...
/// </remarks>
```

Each language would have its own parser in the source-code plugin, but all produce the same `ArticleMeta` + content output.

---

## Metadata Field Reference

| Field | Required | Format | Description |
|-------|----------|--------|-------------|
| `wk-id` | Yes | `source-name/module-path` | Unique article ID. Source name must match config. |
| `wk-tags` | No | Comma-separated | Tags for indexing. Merged with any source-level default tags. |
| `wk-categories` | No | Comma-separated article IDs | Category memberships. Can reference both wiki and source articles. Use `@kb-name` suffix for multi-KB targets. |
| `wk-title` | No | Free text | Override title (default: first line of docstring). |

## ID Format

Article IDs for source-code articles follow the pattern: `source-name/module-path`

- `source-name` matches the key in the sources configuration (e.g., `wk`)
- `module-path` is a developer-chosen slug (e.g., `index-engine`, `storage-contract`)
- The full ID used in wiki links and the index is `src:source-name/module-path`

This namespacing prevents collisions between:
- Different sources that might have similar module names
- Source articles and native wiki articles

## Multi-KB Annotations

When a source codebase is connected to **multiple WikiKnowledge knowledge bases**, annotations can reference articles in different KBs using the `@kb-name` qualifier.

### Default (Single-KB) — No Extra Syntax

If a source is connected to only one KB, everything works without qualification:

```python
"""Auth Service.

:wk-id: myapp/auth-service
:wk-categories: system-architecture

Implements authentication. See [[security-overview]] for the design.
"""
```

`system-architecture` and `[[security-overview]]` resolve against the single connected KB.

### Multi-KB — Use `@kb-name` for Non-Default KBs

When connected to multiple KBs, unqualified references resolve against the **default** KB (declared as `"default": "self"` in `knowledge/sources.json`). To target a different KB, append `@kb-name`:

```python
"""Auth Service.

:wk-id: myapp/auth-service
:wk-categories: system-architecture, api-endpoints@api-docs

Implements authentication per the spec in [[auth-spec@api-docs]].
For the overall security design, see [[security-overview]].
"""
```

Here:
- `system-architecture` → default KB's category
- `api-endpoints@api-docs` → category in the "api-docs" KB
- `[[auth-spec@api-docs]]` → article in the "api-docs" KB
- `[[security-overview]]` → article in the default KB

### KB Name Resolution

KB names are declared in the source's entry in `knowledge/sources.json`:

```json
{
  "myapp": {
    "knowledge_bases": {
      "default": "self",
      "api-docs": { "url": "http://localhost:8002" }
    }
  }
}
```

If `knowledge_bases` is omitted, only the current KB is connected — no `@` syntax needed.
