---
categories:
- user-manual
created: '2026-07-06T08:08:08.414776+00:00'
id: ai-source-code-annotations
modified: '2026-07-18T07:23:55.710350+00:00'
tags:
- ai
- code-generation
- metadata
- knowledge-sources
title: AI Source Code Annotations Guide
type: leaf
---

# AI Source Code Annotations Guide

This guide instructs AI agents on how to correctly annotate source code when writing or modifying code within projects tracked by WikiKnowledge's [[source-code-plugin|Source Code Plugin]].

When an AI writes or updates a source code module, it **must** include a rich documentation block in the file's primary docstring or top-level block comment. 

These are not just metadata fields! They act as **short articles** directly embedded in the source code (similar to how Android documentation is built natively from JavaDoc). This ensures the implementation description lives close to the actual code, making it instantly accessible for humans and AIs without burning massive amounts of tokens trying to "recover" knowledge by parsing raw function bodies.

## Annotation Syntax

Depending on the programming language, place the following annotations at the top of the file alongside a comprehensive explanation of the module's exact interfaces and implementations.

### Python (`.py`)
Use RST-style field lists in the module-level `"""` docstring:
```python
"""
In-memory knowledge index for fast lookups.

:wk-id: source_name/module-name
:wk-tags: python, tagging, example
:wk-categories: system-architecture

This module implements the graph traversal logic using an adjacency list. 
It favors memory efficiency by storing node references rather than deep copies.
...
Links to: [[wiki-link-target]], [[src:wikiknowledge/wk/other-module]]
"""
```

### JavaScript / TypeScript (`.js`, `.ts`)
Use JSDoc `@` tags in the file-level `/** ... */` block comment:
```javascript
/**
 * Main Application Controller.
 * 
 * @wk-id source_name/module-name
 * @wk-tags javascript, frontend, example
 * @wk-categories system-architecture
 *
 * Implements the React state bindings for the main event loop.
 * Links to: [[wiki-link-target]]
 */
```

## Required Fields
1. **`wk-id`**: A unique ID scoped to the project source name (e.g., `wk/my-module`).
2. **`wk-tags`**: A comma-separated list of tags.
3. **`wk-categories`**: A comma-separated list of categories the virtual article belongs to (e.g., `system-architecture`).

## Best Practices for AI Agents
- **Avoid Duplication**: Never copy internal class details or specific interface layouts into the central WikiKnowledge UI. That information belongs strictly inside these source code short articles.
- **Explain the "How"**: The wiki explains the "What" (Functional Requirements). Your source code article must explain the "How" (Implementation Details and interface contracts).