---
categories: []
created: '2026-06-19T21:00:00+00:00'
id: system-architecture
modified: '2026-07-06T06:00:43.691904+00:00'
tags:
- architecture
- overview
- design
title: System Architecture
type: category
---

# System Architecture

<!-- human:start -->
WikiKnowledge is a knowledge graph construction system built on three pillars:

1. **Storage** — An abstracted persistence layer that reads and writes markdown articles with YAML frontmatter. The initial implementation uses flat files on disk, but the interface is designed for alternative backends (databases, git-backed stores).

2. **Index** — An in-memory engine that parses wiki links, tags, and categories to build inverted indices. These indices power fast lookups: "what links here?", "what articles have this tag?", "what belongs to this category?" — without touching the filesystem.

3. **Interface** — A FastAPI backend serves a REST API consumed by a vanilla JavaScript frontend. The frontend provides a markdown viewer with live wiki-link resolution and inline Mermaid diagram rendering, a split-pane editor with metadata chip controls and live previews, and a D3.js force-directed graph visualization.

The system is designed to be self-documenting: its own development knowledge is stored as articles within the knowledge base it manages. This creates a bootstrapping feedback loop where building the system also builds the content that tests it.

### Data Flow

```
Markdown Files on Disk
        ↓ (startup: parse frontmatter + extract links)
  Storage Backend
        ↓ (build indices)
  In-Memory Index
        ↓ (serve via REST)
  FastAPI API Layer
        ↓ (fetch + render)
  JavaScript Frontend
```

### Design Philosophy

- **Files are the source of truth** — everything is rebuildable from the `.md` files
- **No build step for frontend** — plain HTML/CSS/JS loaded via ES modules and CDN
- **Safe by default** — unmarked content in category articles is treated as human-written
- **Incremental updates** — editing one article only rebuilds its portion of the index
<!-- human:end -->

## Articles in This Category

<!-- ai:start -->
### [[storage-abstraction|Storage Abstraction Layer]]
Defines the abstract `StorageBackend` interface with CRUD operations and query methods (by tag, by category, backlinks). The markdown backend implementation maps articles to flat files in `knowledge/articles/` and `knowledge/categories/`, using `python-frontmatter` for parsing and atomic writes for safety.

### [[in-memory-index|In-Memory Index]]
The core indexing engine that builds forward-link, back-link, tag, and category indices on startup. Supports incremental updates when individual articles change. Provides the graph data export consumed by the D3.js visualization.

### [[fastapi-backend|FastAPI Backend]]
The REST API layer serving article CRUD, search/discovery, and graph endpoints. Mounts the static frontend and initializes the storage + index on startup via FastAPI's lifespan handler. Auto-generates OpenAPI documentation at `/docs`.

### [[local-setup-and-mcp|Local Setup and MCP Configuration]]
Guide for installing dependencies, configuring the Model Context Protocol (MCP) server, and running the knowledge base locally. Covers environment variables, database initialization, and development workflow tips.

### [[markup-conventions|Markup Conventions]]
Documentation of the markdown and wiki-link conventions used across the knowledge base. Includes frontmatter schema, tag syntax, category declarations, and linking style guidelines.

### [[knowledge-sources|Knowledge Sources]]
A plugin system that allows external data sources (like source code repositories) to contribute "virtual articles" to the knowledge graph. This prevents knowledge duplication by letting the codebase act as a direct participant in the architecture documentation.
<!-- ai:end -->