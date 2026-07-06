# Motivation & Design Philosophy

## The Problem: Knowledge Duplication

When WikiKnowledge is used to document a software project, certain information must be duplicated:

- **Module structure**: The wiki describes how modules are organized, but this structure already exists in the code's directory layout and import graph.
- **Interface descriptions**: The wiki explains what each module provides, but this is already expressed in docstrings, type signatures, and API documentation within the source files.
- **Business logic explanations**: The wiki documents how components work together, but this knowledge is embedded in code comments, function names, and architectural decisions visible in the source.
- **Architectural rationale**: Design decisions documented in the wiki often mirror comments and docstrings already present in the code.

This duplication creates a **synchronization burden**: when the code changes, the wiki articles must be manually updated to match, and vice versa. In practice, they drift apart, making the wiki unreliable.

## The Insight: Source Code IS Knowledge

Source code files — particularly their module-level documentation — already contain high-level architectural knowledge. A well-documented Python module's docstring explains what it does, why it exists, and how it relates to other modules. A JSDoc file header describes a component's role in the broader system.

The problem is that this knowledge is:
1. **Scattered** across files without a navigable overview structure
2. **Invisible** to the wiki's graph, categories, and backlink features
3. **Disconnected** from the wiki articles that discuss the same concepts

## The Solution: Knowledge Sources

Instead of copying knowledge from code into wiki articles, we let source code files **participate directly** in the knowledge graph. A plugin system allows external sources — codebases, other WikiKnowledge instances, API documentation — to contribute "virtual articles" that:

- Appear in the category tree alongside native wiki articles
- Participate in wiki-link resolution and backlink tracking
- Show up in search results and graph visualization
- Maintain tags and category memberships

The source code remains the single source of truth. The wiki provides the **architectural overlay** — categories, overviews, and cross-cutting narratives — while source modules provide the **ground-level documentation** that backs them up.

## What This Is NOT

This system is explicitly **not** a code indexing tool. We do not want to:

- Build detailed class hierarchies or inheritance trees
- Index every method signature and parameter
- Create call graphs or dependency trees
- Replicate what tools like Codebase Memory MCP, ctags, or language servers already do

Those tools answer "what does this function do?" and "who calls it?" — they help you navigate **within the trees**.

Our system answers "what is this module's role in the architecture?" and "how do these components snap together?" — it helps AIs and humans **see the forest**.

### The AI Problem Specifically

AI agents frequently fail to grasp overall code architecture without spending enormous token budgets:
- They read file after file, building up context piecemeal
- They lose the big picture while getting mired in implementation details
- They make changes that work locally but violate architectural boundaries they never understood
- Each new session starts this expensive discovery process from scratch

By having architectural knowledge annotated directly in source files and integrated into a navigable knowledge graph, an AI can:
1. Read the wiki's category overview to understand the system's high-level structure
2. Follow links to source-code articles for module-level detail
3. Use code indexing tools (Codebase Memory MCP) for fine-grained code navigation

This creates a **zoom-in workflow**: wiki overview → source module documentation → actual code.

## Design Principles

1. **Minimal source impact**: Use existing documentation conventions (docstrings, JSDoc). Developers who don't use WikiKnowledge just see well-documented code.

2. **No sidecar files**: All metadata is embedded in the source files themselves. No `.wk.json` or `.meta` files cluttering the repo.

3. **Optional and detachable**: Connected codebases can disappear without breaking the wiki. Links to disconnected sources degrade gracefully (shown as "disconnected" rather than "broken").

4. **Multi-language**: Each language has its own annotation parser, but they all produce the same WikiKnowledge article model (id, title, tags, categories, content, wiki-links).

5. **Multi-project**: Multiple independent codebases can be connected simultaneously, each with its own source name and configuration.

6. **Forward-looking**: The plugin architecture is designed for future source types beyond source code — remote WikiKnowledge instances, API documentation generators, database schemas, etc.
