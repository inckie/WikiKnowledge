---
id: "wiki-link-syntax"
title: "Wiki Link Syntax"
type: "leaf"
tags: ["markdown", "wiki-links", "syntax", "navigation"]
categories: ["markup-conventions"]
created: "2026-06-19T21:00:00Z"
modified: "2026-06-19T21:00:00Z"
---

# Wiki Link Syntax

WikiKnowledge uses double-bracket syntax (`[[...]]`) for internal links between articles. This is the primary mechanism for connecting knowledge and building the graph structure that powers the [[in-memory-index]] and the graph visualization.

## Basic Syntax

### Simple Link

```markdown
See the article on [[rigid-body-dynamics]].
```

Renders as a clickable link with the target article's title as display text. If the article titled "Rigid Body Dynamics" exists, it renders as:

> See the article on [Rigid Body Dynamics](#).

### Link with Display Text

```markdown
The system uses [[markdown-frontmatter|YAML metadata]] for each article.
```

The pipe character `|` separates the target article ID from the display text:

> The system uses [YAML metadata](#) for each article.

## Resolution Rules

1. The text inside `[[...]]` (before any `|`) is matched against the `id` field in article [[markdown-frontmatter|frontmatter]]
2. Resolution is **case-sensitive** — `[[My-Article]]` and `[[my-article]]` are different targets
3. If the target article does not exist, the link is rendered with a distinct "missing article" style (red, with a `?` indicator), inviting the user to create it
4. Links work across article types — a leaf article can link to a category article and vice versa

## Extraction and Indexing

The core [[in-memory-index|indexing engine]] extracts all wiki links from every article using a regex parser. For each link, it records:

- **Source article ID** — the article containing the link
- **Target article ID** — the article being linked to
- **Display text** — the optional custom label
- **Line number** — where the link appears in the source

This data feeds two indices:

- **Forward links** — "what does this article link to?"
- **Back links** — "what links here?" (the reverse query)

The "What Links Here" query is one of the most powerful navigation tools in the system, allowing readers to discover related content they might not have found otherwise.

## Edge Cases

- **Self-links**: An article linking to itself (`[[my-own-id]]`) is valid but flagged in the UI
- **Nested brackets**: `[[ [[not-valid]] ]]` — inner brackets are not supported; the parser matches the first `]]`
- **Links in code blocks**: Wiki links inside fenced code blocks (`` ``` ``) are **not** parsed or resolved
- **Links in frontmatter**: Wiki links in YAML frontmatter are **not** parsed; use the `categories` field instead

## Relationship to Graph

Every wiki link becomes an **edge** in the knowledge graph. The [[storage-abstraction]] provides the `get_backlinks()` method, which the [[fastapi-backend]] exposes at `GET /api/articles/{id}/backlinks`. The graph visualization uses these edges to draw connections between nodes.
