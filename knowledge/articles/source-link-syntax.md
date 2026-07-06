---
categories:
- markup-conventions
- knowledge-sources
created: '2026-07-06T05:59:43.142031+00:00'
id: source-link-syntax
modified: '2026-07-06T05:59:43.142047+00:00'
tags:
- wiki-links
- syntax
- knowledge-sources
- source-code
- navigation
title: Source Link Syntax
type: leaf
---

# Source Link Syntax

WikiKnowledge extends the standard [[wiki-link-syntax|wiki link syntax]] to support references to virtual articles provided by external knowledge sources.

## Source-Qualified Links

To link to an article provided by an external source (like the [[source-code-plugin|Source Code Plugin]]), use the `src:` prefix:

```markdown
[[src:source-name/module-path]]
[[src:source-name/module-path|Display Text]]
```

### Resolution Rules

1. `source-name` maps to a source configured in `knowledge/sources.json` (e.g., `wk`).
2. `module-path` is the developer-chosen ID defined in the source file's metadata (e.g., `storage-contract`).
3. If the source is connected, it resolves normally and displays a small source icon.
4. **Disconnection Behavior**: If the source is disconnected (e.g. the path is unavailable), the link degrades gracefully. It appears in a muted/gray style with a disconnected icon (⊘), rather than as a standard red "broken" link. This indicates the target exists conceptually but the source is currently unreachable.

## Multi-KB Links

A single source codebase might be connected to **multiple WikiKnowledge knowledge bases** simultaneously. When a source annotation contains a wiki link, it needs to know which KB to resolve against.

If there is only a single default KB, no extra syntax is needed. However, you can explicitly target a non-default KB using the `@kb-name` qualifier:

```markdown
[[article-id@kb-name]]
[[src:source-name/module-path@kb-name]]
```

For example, in a Python docstring:
```python
"""
See the API spec in [[auth-spec@api-docs]].
"""
```

KB names like `api-docs` are mapped to actual connections (e.g. URLs) in the source's configuration entry. If the target KB is unreachable, cross-KB links also degrade to the "disconnected" state.