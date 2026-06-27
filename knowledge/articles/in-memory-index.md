---
id: "in-memory-index"
title: "In-Memory Index"
type: "leaf"
tags: ["architecture", "index", "search", "graph", "python"]
categories: ["system-architecture"]
created: "2026-06-19T21:00:00Z"
modified: "2026-06-19T21:00:00Z"
---

# In-Memory Index

The in-memory index is the heart of WikiKnowledge's query system. Built on application startup from data provided by the [[storage-abstraction]], it maintains several inverted indices that enable fast lookups without hitting the filesystem.

## Data Structures

### Forward Links Index

```
forward_links: dict[str, list[WikiLink]]
```

Maps each article or resource ID to the list of [[wiki-link-syntax|wiki links]] found in its content (or `related` metadata field). Used to render outgoing links and to detect broken links (targets that don't exist).

### Back Links Index

```
back_links: dict[str, list[WikiLink]]
```

The reverse of `forward_links`. Maps each article ID to the list of articles that link *to* it. This powers the "What Links Here" feature — one of the most important navigation tools in any wiki system.

**Example**: If article `rigid-body-dynamics` contains `[[physics-simulation]]`, then:
- `forward_links["rigid-body-dynamics"]` includes a link to `physics-simulation`
- `back_links["physics-simulation"]` includes a link from `rigid-body-dynamics`

### Tag Index

```
tag_index: dict[str, set[str]]
```

Maps each tag string to the set of article IDs that carry that tag in their [[markdown-frontmatter|frontmatter]]. Enables the tag cloud and tag-based filtering in the UI.

### Category Index

```
category_index: dict[str, set[str]]
```

Maps each category article ID to the set of article IDs that list it in their `categories` frontmatter field. This is distinct from wiki links — it represents the *explicit* hierarchical classification, not the organic link graph.

## Build Process

The index is built in a single pass on startup:

1. The [[storage-abstraction]] provides all article metadata and extracted wiki links
2. For each article:
   - Add its tags to `tag_index`
   - Add its categories to `category_index`
   - Parse its content for `[[wiki links]]` and populate `forward_links`
3. Invert `forward_links` to produce `back_links`
4. Log statistics: total articles, total links, orphan articles (no incoming or outgoing links)

For a knowledge base of a few thousand articles, this completes in under a second.

## Incremental Updates

When a single article or resource is modified, a full rebuild is wasteful. Instead, the index supports `rebuild_article(id, meta, content)` and `rebuild_resource(id, meta)`:

1. Remove the old article/resource's entries from all indices
2. Re-parse the updated metadata, content, or `related` links
3. Insert the new entries
4. Recompute only the affected back-links

This keeps the index consistent without the cost of a full rebuild.

## Query Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `what_links_here(id)` | `list[WikiLink]` | All articles linking to the given ID |
| `search_by_tag(tag)` | `set[str]` | Article IDs with the given tag |
| `articles_in_category(cat_id)` | `set[str]` | Article IDs classified under the category |
| `get_all_tags()` | `dict[str, int]` | All tags with their usage counts |
| `get_orphans()` | `set[str]` | Articles with no incoming or outgoing links |
| `get_broken_links()` | `list[WikiLink]` | Links whose targets don't exist |

## Graph Export

The index also provides a `get_graph_data()` method that serializes the entire link structure into a format consumable by D3.js:

```json
{
  "nodes": [
    {"id": "article-one", "title": "Article One", "type": "leaf", "linkCount": 5},
    {"id": "cat-one", "title": "Category One", "type": "category", "linkCount": 12},
    {"id": "wikiknowledge-logo.svg", "title": "WikiKnowledge Logo", "type": "resource", "linkCount": 1, "mime_type": "image/svg+xml"}
  ],
  "links": [
    {"source": "article-one", "target": "cat-one"},
    {"source": "article-one", "target": "wikiknowledge-logo.svg"}
  ]
}
```

This is served by the [[fastapi-backend]] at `GET /api/graph` and consumed by the frontend's D3.js force-directed graph visualization.
