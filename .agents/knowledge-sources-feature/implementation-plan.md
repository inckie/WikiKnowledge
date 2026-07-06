# Implementation Plan — Step by Step

## Phase 1: Documentation & Dogfooding (Current Phase)

**Goal**: Create wiki articles documenting the Knowledge Sources system, then annotate WikiKnowledge's own source code as a working example of the annotation conventions.

No runtime plugin code is built in this phase — only articles and source-code annotations.

### Step 1.1: Create Wiki Articles via MCP

- [x] **Create `knowledge-sources` category article**
  - Categories: `[system-architecture]`
  - Tags: `[knowledge-sources, plugins, architecture, extensibility]`
  - Content: motivation, plugin architecture overview, virtual articles concept, forward-looking vision
  - Use `<!-- human:start/end -->` for the core design narrative
  - Use `<!-- ai:start/end -->` for the sub-article summaries section

- [x] **Create `source-code-plugin` leaf article**
  - Categories: `[knowledge-sources]`
  - Tags: `[knowledge-sources, source-code, annotations, multi-language, plugin]`
  - Content: what gets captured vs. not, annotation format per language, multi-project support, configuration format, WikiKnowledge self-annotation example

- [x] **Create `source-link-syntax` leaf article**
  - Categories: `[markup-conventions, knowledge-sources]`
  - Tags: `[wiki-links, syntax, knowledge-sources, source-code, navigation]`
  - Content: current syntax recap, new `[[src:...]]` syntax, resolution rules, rendering states, disconnection behavior

### Step 1.2: Update Existing Articles via MCP

- [x] **Update `system-architecture`** — add `knowledge-sources` to the `<!-- ai:start/end -->` summaries section
- [x] **Update `overview`** — add a brief mention of Knowledge Sources in the data organization section

### Step 1.3: Annotate WikiKnowledge Source Code

Add or enhance module-level docstrings with `wk:` metadata. Each annotation should:
- Use the language-appropriate format (RST `:wk-*:` for Python, JSDoc `@wk-*` for JS)
- Include an architectural description (what the module does, how it fits)
- Contain `[[wiki-links]]` to relevant wiki articles
- Contain `[[src:wk/...]]` links to related source modules
- Preserve all existing docstring content and comments

#### Python files to annotate:

- [x] `wikiknowledge/storage/base.py` → `wk/storage-contract`
  - Storage abstraction contract. All backends implement this interface.
  - Links to: [[storage-abstraction]], [[src:wk/markdown-storage]], [[src:wk/data-models]]

- [x] `wikiknowledge/storage/models.py` → `wk/data-models`
  - Pydantic data model foundation: Article, ArticleMeta, WikiLink, Resource, ResourceMeta, ContentBlock.
  - Links to: [[markdown-frontmatter]], [[src:wk/storage-contract]]

- [x] `wikiknowledge/storage/markdown_backend.py` → `wk/markdown-storage`
  - File-system storage implementation. Maps articles to `knowledge/articles/*.md` with YAML frontmatter.
  - Links to: [[storage-abstraction]], [[src:wk/storage-contract]], [[src:wk/link-parser]], [[src:wk/data-models]]

- [x] `wikiknowledge/core/index.py` → `wk/index-engine`
  - In-memory inverted index engine. Builds forward/back links, tag index, category index.
  - Links to: [[in-memory-index]], [[src:wk/link-parser]], [[src:wk/graph-builder]]

- [x] `wikiknowledge/core/parser.py` → `wk/link-parser`
  - Wiki-link and content block parser. Extracts [[...]] links and human/AI markers.
  - Links to: [[wiki-link-syntax]], [[human-protected-blocks]], [[src:wk/index-engine]]

- [x] `wikiknowledge/core/graph.py` → `wk/graph-builder`
  - D3.js graph data generation. Produces nodes+links for full graph, subgraph, and category tree.
  - Links to: [[src:wk/index-engine]], [[src:wk/graph-visualization]]

- [x] `wikiknowledge/core/refactor.py` → `wk/refactoring`
  - Global rename operations with cross-article link updates.
  - Links to: [[src:wk/index-engine]], [[src:wk/markdown-storage]]

- [x] `wikiknowledge/core/ai_service.py` → `wk/ai-service`
  - AI integration: config management, OpenAI API model fetching, MCP tool calling loop.
  - Links to: [[ai-settings-and-mcp-binding]], [[src:wk/mcp-interface]]

- [x] `wikiknowledge/mcp_server.py` → `wk/mcp-interface`
  - 17-tool MCP server factory. Gives AI agents full CRUD + query access to the knowledge base.
  - Links to: [[ai-interaction-guide]], [[src:wk/index-engine]], [[src:wk/markdown-storage]]

#### JavaScript files to annotate:

- [x] `frontend/js/app.js` → `wk/frontend-app`
  - SPA controller: hash-based routing, sidebar management, view switching.
  - Links to: [[fastapi-backend]], [[src:wk/markdown-viewer]], [[src:wk/graph-visualization]]

- [x] `frontend/js/viewer.js` → `wk/markdown-viewer`
  - Markdown renderer with live wiki-link resolution and human/AI block indicators.
  - Links to: [[wiki-link-syntax]], [[human-protected-blocks]], [[src:wk/frontend-app]]

- [x] `frontend/js/graph.js` → `wk/graph-visualization`
  - D3.js force-directed graph rendering.
  - Links to: [[src:wk/graph-builder]], [[src:wk/frontend-app]]

### Step 1.4: Verification

- [ ] List all articles via MCP — confirm `knowledge-sources` appears under `system-architecture`
- [ ] Confirm the category tree has: `system-architecture → knowledge-sources → source-code-plugin`
- [ ] Verify `source-link-syntax` appears under both `markup-conventions` and `knowledge-sources`
- [ ] Confirm source code still runs without errors (annotations are in docstrings — no functional changes)
- [ ] Spot-check a few annotated files for readability

---

## Phase 2: Runtime Implementation (Completed)

**Implemented via MCP plugins system.**

- [x] Implement `KnowledgeSourcePlugin` base class in `wikiknowledge/core/`
- [x] Implement `SourceCodePlugin` with Python and JavaScript parsers
- [x] Create `SourceManager` that loads config and manages plugin lifecycle
- [x] Integrate virtual articles into `KnowledgeIndex.build()`
- [x] Add `src:` link type to `parser.py`
- [x] Update MCP tools to surface virtual articles (read-only)
- [x] Update frontend to render source links and virtual article indicators
- [x] Add configuration UI in the settings panel
- [x] Handle disconnection/reconnection gracefully

---

## Phase 3: Advanced Features (Current Phase)

- [ ] File watcher for live updates when source files change
- [ ] Remote WikiKnowledge plugin
- [ ] API documentation plugin (OpenAPI, gRPC)
- [ ] "Dirty" detection for source-linked categories (when source files change)
- [ ] Bidirectional editing hints (from wiki, open source file in IDE)
