---
categories:
- system-architecture
created: '2026-07-06T05:59:38.961944+00:00'
id: knowledge-sources
modified: '2026-07-06T05:59:38.961967+00:00'
tags:
- knowledge-sources
- plugins
- architecture
- extensibility
title: Knowledge Sources
type: category
---

# Knowledge Sources

<!-- human:start -->
Knowledge Sources is a plugin-based extensibility system that allows external data sources to contribute "virtual articles" to the WikiKnowledge knowledge graph.

When documenting software projects, a common problem is knowledge duplication between the codebase (module structures, interface descriptions, architectural rationale) and the wiki. This duplication creates a synchronization burden. Instead of copying knowledge from code into wiki articles, Knowledge Sources allows source code files and other external systems to **participate directly** in the knowledge graph.

### Plugin Architecture Overview

The system uses a layered plugin architecture:
1. **Source Declarations**: A `knowledge/sources.json` file declares available sources and how to parse them.
2. **Machine Settings**: A `.settings/sources.json` file provides local overrides for source paths.
3. **Plugins**: Language-specific or domain-specific plugins (e.g. Python, JS, remote-wiki) scan the external sources and produce `ArticleMeta` and content.

### Virtual Articles

External sources contribute **virtual articles**. These articles:
- Have unique IDs namespaced by their source (e.g., `src:wikiknowledge/wk/storage-contract`).
- Participate fully in the index: tags, categories, forward links, and back links.
- Are **read-only** from the wiki side — edits must go to the external source file.
- Are **ephemeral** — if the source is disconnected, links to them degrade gracefully to a "disconnected" state rather than a "broken" state.

### Forward-Looking Vision

While the initial focus is on the [[source-code-plugin|Source Code Plugin]], the architecture is designed to support:
- **Remote WikiKnowledge**: Importing articles from another WikiKnowledge instance.
- **API Documentation**: Parsing OpenAPI specs or GraphQL schemas into the graph.
- **Database Schema**: Documenting tables and collections automatically.

This system is explicitly *not* a code indexing tool (like a language server or Codebase Memory MCP). It is designed to capture the **architectural "forest"**, not the code-level "trees".
<!-- human:end -->

## Articles in This Category

<!-- ai:start -->
### [[source-code-plugin|Source Code Plugin]]
Details how source code files can participate in the knowledge graph. Explains the annotation format for different programming languages (Python RST docstrings, JavaScript JSDoc), what knowledge gets captured (module-level architecture), and configuration formats. Includes a self-annotation example from WikiKnowledge's own codebase.

### [[source-link-syntax|Source Link Syntax]]
Documents the extended wiki-link syntax used to reference source code articles. Explains the `[[src:source-name/module-path]]` format, multi-KB `@kb-name` qualifiers, resolution rules, and how disconnected sources are rendered differently from broken links.
<!-- ai:end -->