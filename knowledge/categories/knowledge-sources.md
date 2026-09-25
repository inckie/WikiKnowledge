---
categories:
- system-architecture
created: '2026-07-06T05:59:38.961944+00:00'
id: knowledge-sources
modified: '2026-09-25T11:02:30.072562+00:00'
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

The initial plugin implementations include the [[source-code-plugin|Source Code Plugin]], the [[markdown-files-plugin|Markdown Files Plugin]], and the [[google-drive-plugin|Google Drive Plugin]]. The architecture is also designed to support:
- **Remote WikiKnowledge**: Importing articles from another WikiKnowledge instance.
- **API Documentation**: Parsing OpenAPI specs or GraphQL schemas into the graph.
- **Database Schema**: Documenting tables and collections automatically.

This system is explicitly *not* a code indexing tool (like a language server or Codebase Memory MCP). It is designed to capture the **architectural "forest"**, not the code-level "trees".
<!-- human:end -->

## Articles in This Category

<!-- ai:start -->
### [[source-code-plugin|Source Code Plugin]]
Details how source code files can participate in the knowledge graph. Explains the annotation format for different programming languages (Python RST docstrings, JavaScript/TypeScript JSDoc, Java/Kotlin), what knowledge gets captured (module-level architecture), and configuration formats. Includes a self-annotation example from WikiKnowledge's own codebase.

### [[source-link-syntax|Source Link Syntax]]
Documents the extended wiki-link syntax used to reference external source articles. Explains the `[[src:source-name/module-path]]` and `[[gdrive:doc-id]]` formats, multi-KB `@kb-name` qualifiers, resolution rules within source codebases, and how disconnected sources degrade gracefully.

### [[markdown-files-plugin|Markdown Files Plugin]]
Covers importing an existing markdown documentation tree (Docusaurus, MkDocs, Docsify, or plain `docs/` folders) with zero annotations required: folders become category articles, dash-concatenated relative paths become article IDs, relative markdown links and images are rewritten on serving, and include/exclude globs control what is indexed.

### [[src:wikiknowledge/markdown-files-plugin|Markdown Files Plugin (Source Implementation)]]
The backend Python source module (`markdown_files.py`) implementing the Markdown Files Plugin. Handles discovering filesystem directory trees, creating virtual categories and leaves, rewriting relative links into wiki-links, and safely serving static assets like images.

### [[google-drive-plugin|Google Drive Plugin]]
Covers the Google Drive knowledge source plugin: service account authentication, folder configuration, virtual article IDs (`gdrive:<doc-id>`), local caching with on-demand sync, folder hierarchy mirroring, markdown export pipeline, and bidirectional tag/category metadata synchronization via Drive properties.

### [[google-docs-extension|Google Docs Extension for WikiKnowledge]]
A setup guide for creating a Google Docs Apps Script extension (`Code.gs` and `Sidebar.html`). Provides an in-editor sidebar allowing authors to view and update WikiKnowledge tags (`wk_tags`) and categories (`wk_categories`) directly within Google Docs, respecting backend property length limits.

### [[gdrive:1AxAubXmVpPNOHFANk_1shZcE_3zKxUQtM5INMLw3404|WikiKnowledge Google Drive]]
A sample Google Doc virtual article integrated via the Google Drive plugin demonstrating live document rendering. Documents Google Drive API custom property constraints and acts as a template for authoring new Google Docs for WikiKnowledge.
<!-- ai:end -->