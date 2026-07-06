# Knowledge Sources Feature — Working Notes

**Status**: Phase 1 — Design & Documentation (not yet started)  
**Created**: 2026-07-06  
**Last updated**: 2026-07-06

## What This Folder Is

Persistent working-state notes for the "Knowledge Sources" feature. Designed to survive AI context drops and session splits — any AI agent should be able to read these files and resume work.

## File Index

| File | Purpose |
|------|---------|
| `README.md` | This file — overview and navigation |
| `motivation.md` | Problem statement, design philosophy, and key insights |
| `architecture.md` | Technical design of the plugin system |
| `annotation-conventions.md` | Per-language source code annotation formats |
| `link-syntax.md` | Extended wiki-link syntax design |
| `implementation-plan.md` | Step-by-step execution plan with checklists |
| `open-questions.md` | Unresolved design decisions awaiting user input |
| `codebase-context.md` | WikiKnowledge architecture summary for quick onboarding |

## Quick Context

WikiKnowledge is a hierarchical knowledge graph built over markdown files. When used to document software projects, it duplicates information already present in source code (module structures, interface descriptions, architectural rationale). This feature adds a **plugin system** that lets external sources — starting with source codebases — contribute "virtual articles" to the knowledge graph, eliminating duplication and keeping things in sync.

**Key design decisions made**:
- A single source codebase can link to **multiple WikiKnowledge KBs**. Default (single-KB) case requires no extra syntax; multi-KB uses `@kb-name` qualifier in links and categories.
- Configuration is **split in two**: a versioned declaration file (`knowledge/sources.json`) defining what sources exist and how to parse them (with default relative paths for same-repo sources), and a gitignored settings file (`knowledge/.settings/sources.json`) for machine-specific path overrides.
- Source annotations use **existing language documentation conventions** extended with `wk:` metadata (`:wk-id:` in Python RST, `@wk-id` in JSDoc).
- The system captures **architectural "forest" knowledge**, not code-level "trees" — module roles and relationships, not class hierarchies or method signatures.

## How to Resume Work

1. Read `motivation.md` for the "why"
2. Read `architecture.md` for the "what"  
3. Read `implementation-plan.md` for the "how" — it has checklists with completion status
4. Check `open-questions.md` for any unresolved decisions
5. If you need WikiKnowledge codebase context, read `codebase-context.md`

## Key Tools Available

- **MCP tools** (via `mcp-host-http` server): `wikiknowledge_*` group — full CRUD for articles, resources, search, graph queries
- **Source code**: workspace at `d:\Work\Tools\AI\WikiKnowledge`
- **Codebase Memory MCP**: `codebase-memory-mcp` server for code graph queries
