---
categories:
- ai-integration
created: '2026-07-06T08:08:08.414776+00:00'
id: ai-source-code-annotations
modified: '2026-07-06T08:08:08.414810+00:00'
tags:
- ai
- code-generation
- metadata
- knowledge-sources
title: AI Source Code Annotations Guide
type: leaf
---

This guide instructs AI agents on how to correctly annotate source code when writing or modifying code within projects tracked by WikiKnowledge's Source Code Plugin.

When an AI writes or updates a source code module, it **must** include a metadata block in the file's primary docstring or top-level block comment. This metadata exposes the module as a "virtual article" in the WikiKnowledge graph.

## Annotation Syntax

Depending on the programming language, place the following annotations at the top of the file.

### Python (`.py`)
Use RST-style field lists in the module-level `"""` docstring:
```python
"""
Short description of the module.
:wk-id: source_name/module-name
:wk-tags: python, tagging, example
:wk-categories: system-architecture

Detailed architectural context and relationships...
Links to: [[wiki-link-target]], [[src:wikiknowledge/wk/other-module]]
"""
```

### JavaScript / TypeScript (`.js`, `.ts`)
Use JSDoc `@` tags in the file-level `/** ... */` block comment:
```javascript
/**
 * Short description of the module.
 * 
 * @wk-id source_name/module-name
 * @wk-tags javascript, frontend, example
 * @wk-categories system-architecture
 *
 * Detailed architectural context and relationships...
 * Links to: [[wiki-link-target]], [[src:wikiknowledge/wk/other-module]]
 */
```

## Required Fields
1. **`wk-id`**: A unique ID scoped to the project source name (e.g., `wk/my-module`).
2. **`wk-tags`**: A comma-separated list of tags.
3. **`wk-categories`**: A comma-separated list of categories the virtual article belongs to (e.g., `system-architecture`).

## Best Practices for AI Agents
- Always preserve existing `wk-` annotations if they already exist.
- Ensure the description clearly explains how the module fits into the broader system architecture.
- Use Wiki Links (`[[article-id]]` or `[[src:source/module]]`) to connect the source code to broader architectural concepts or related source files in the graph.