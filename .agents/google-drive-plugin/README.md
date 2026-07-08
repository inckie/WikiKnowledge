# Google Drive Plugin — Working Notes

**Status**: Phase 0 — Design & Documentation (complete, all open questions resolved)  
**Created**: 2026-07-08  
**Last updated**: 2026-07-08

## What This Folder Is

Persistent working-state notes for the Google Drive Knowledge Source plugin. Designed to survive AI context drops and session splits — any AI agent should be able to read these files and resume work.

## File Index

| File | Purpose |
|------|---------|
| `README.md` | This file — overview and navigation |
| `architecture.md` | Technical design of the Google Drive plugin, caching, bi-directional metadata |
| `implementation-plan.md` | Step-by-step execution plan with checklists |
| `google-api-reference.md` | Google Drive & Docs API specifics: auth, export, custom properties |
| `caching-strategy.md` | Local `.index/` cache design, sync protocol, conflict handling |
| `open-questions.md` | Unresolved design decisions awaiting user input |

## Quick Context

WikiKnowledge has an existing plugin system (`KnowledgeSourcePlugin` base class) that allows external sources to contribute "virtual articles" to the knowledge graph. The `SourceCodePlugin` is the first implementation (parsing annotated Python/JS source files). This feature adds a **Google Drive plugin** that:

- Connects to one or more Google Drive accounts/folders via service account credentials
- Discovers Google Docs inside the configured folder trees
- Exports Google Docs content as markdown and serves them as virtual articles
- Optionally writes WikiKnowledge metadata (categories, tags) back to Google Docs via custom properties (bi-directional)
- Caches all data locally in `.index/<plugin-id>/` for fast startup; syncs on demand only

**Key design decisions made**:
- Authentication uses Google **service account** JSON credentials (no OAuth flow needed)
- Multiple Google Drive sources can be configured independently (different accounts, different folders)
- Cache lives in `knowledge/.index/<source-name>/` — gitignored, rebuilt on demand
- Bi-directionality is **optional per source** — when enabled, the plugin writes `wk-categories` and `wk-tags` as custom properties on Google Docs
- Content is **read-only** from the wiki side (documents cannot be edited via WikiKnowledge, only metadata is written back)
- Google Docs are exported as markdown via the Google Docs export API (with HTML+markdownify fallback)
- Article IDs use `gdrive:<doc-id>` format — globally stable, not tied to source name
- Initial sync behavior is configurable via `auto_sync` field (defaults to manual)
- OAuth scopes are minimal: `drive.readonly` by default, `drive` only when `bidirectional: true`

## How to Resume Work

1. Read `architecture.md` for the overall technical design
2. Read `implementation-plan.md` for the "how" — it has checklists with completion status
3. Read `google-api-reference.md` for Google API specifics
4. Read `caching-strategy.md` for the local cache design
5. Check `open-questions.md` for any unresolved decisions
6. For broader codebase context, read `.agents/knowledge-sources-feature/codebase-context.md`

## Key Tools Available

- **MCP tools** (via `mcp-host-http` server): `wikiknowledge_*` group — full CRUD for articles, resources, search, graph queries
- **Source code**: workspace at `d:\Work\Tools\AI\WikiKnowledge`
- **Codebase Memory MCP**: `codebase-memory-mcp` server for code graph queries

## Related Files in the Codebase

| File | Role |
|------|------|
| `wikiknowledge/core/plugins/base.py` | `KnowledgeSourcePlugin` ABC — the interface this plugin must implement |
| `wikiknowledge/core/plugins/manager.py` | `SourceManager` — loads config, instantiates plugins, routes article requests |
| `wikiknowledge/core/plugins/source_code.py` | `SourceCodePlugin` — reference implementation to follow |
| `knowledge/sources.json` | Declaration file where Google Drive sources will be configured |
| `knowledge/.settings/sources.json` | Machine-specific credential path overrides |
| `wikiknowledge/api/sources.py` | REST API for source status and rescan |
| `wikiknowledge/api/app.py` | FastAPI lifespan — where plugins are initialized |
