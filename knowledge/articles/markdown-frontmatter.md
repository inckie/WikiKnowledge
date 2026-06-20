---
categories:
- markup-conventions
created: '2026-06-19T21:00:00+00:00'
id: markdown-frontmatter
modified: '2026-06-20T07:38:14.569244+00:00'
tags:
- markdown
- yaml
- frontmatter
- metadata
- file-format
title: Markdown Frontmatter Convention
type: leaf
---

# Markdown Frontmatter Convention

Every article in WikiKnowledge begins with a YAML frontmatter block delimited by triple dashes (`---`). This block carries all structured metadata about the article and is parsed separately from the Markdown body content.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | URL-safe unique identifier (slug). Must match the filename without `.md` extension. |
| `title` | string | Human-readable title displayed in the UI. |
| `type` | enum | Either `"leaf"` for content articles or `"category"` for overview articles. |
| `tags` | list[string] | Freeform tags for classification and search. |
| `categories` | list[string] | List of category article IDs this article belongs to. |
| `created` | ISO 8601 | Timestamp of initial creation. |
| `modified` | ISO 8601 | Timestamp of last modification. |

## Example

```yaml
---
id: "rigid-body-dynamics"
title: "Rigid Body Dynamics"
type: "leaf"
tags: ["physics", "simulation", "dynamics"]
categories: ["physics-simulation", "computer-graphics"]
created: "2026-06-19T21:00:00Z"
modified: "2026-06-19T21:00:00Z"
---
```

## Parsing

The system uses the `python-frontmatter` library to parse these blocks. On disk, the frontmatter is the single source of truth for article metadata. When an article is saved through the editor, the frontmatter is serialized back into the file automatically.

The `id` field must be unique across the entire knowledge base — both `articles/` and `categories/` directories. It is used as the primary key in the [[in-memory-index]] and as the target for [[wiki-link-syntax|wiki links]].

## Relationship to Storage Layer

The [[storage-abstraction]] reads frontmatter on startup to populate the in-memory cache. When articles are saved via the API, the [[fastapi-backend]] ensures the `modified` timestamp is updated and the frontmatter is re-serialized before writing to disk.

## Design Rationale

YAML frontmatter was chosen over alternatives (inline metadata, separate sidecar files, database records) because:

1. **Self-contained** — each `.md` file carries its own metadata, making articles portable
2. **Human-readable** — authors can edit metadata in any text editor
3. **Standard** — widely used in static site generators (Jekyll, Hugo, Eleventy), so tooling already exists
4. **Parseable** — the `python-frontmatter` library handles edge cases reliably