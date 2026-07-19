"""In-Memory Index

:wk-id: in-memory-index
:wk-tags: architecture, index, search, graph, python
:wk-categories: system-architecture

The in-memory index is the heart of WikiKnowledge's query system. Built on application startup from data provided by the [[src:wikiknowledge/storage-abstraction|storage-abstraction]], it maintains several inverted indices that enable fast lookups without hitting the filesystem.

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

1. The [[src:wikiknowledge/storage-abstraction|storage-abstraction]] provides all article metadata and extracted wiki links
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

This is served by the [[src:wikiknowledge/fastapi-backend|fastapi-backend]] at `GET /api/graph` and consumed by the frontend's D3.js force-directed graph visualization.
"""

from __future__ import annotations

import time

from wikiknowledge.core.parser import extract_wiki_links
from wikiknowledge.storage.models import ArticleMeta, ResourceMeta, WikiLink


class KnowledgeIndex:
    """Inverted indices over articles and resources for fast query operations.

    Maintains indices built from article metadata, resource metadata, and wiki links:
    - forward_links: node_id → outgoing WikiLinks (articles + resources)
    - back_links: node_id → incoming WikiLinks ("what links here")
    - tag_index: tag → set of article IDs
    - category_index: category_id → set of member article IDs
    """

    def __init__(self) -> None:
        self.forward_links: dict[str, list[WikiLink]] = {}
        self.back_links: dict[str, list[WikiLink]] = {}
        self.tag_index: dict[str, set[str]] = {}
        self.category_index: dict[str, set[str]] = {}
        self._all_meta: dict[str, ArticleMeta] = {}
        self._all_resource_meta: dict[str, ResourceMeta] = {}

    def build(
        self,
        all_meta: dict[str, ArticleMeta],
        all_links: dict[str, list[WikiLink]],
        all_resource_meta: dict[str, ResourceMeta] | None = None,
        all_resource_links: dict[str, list[WikiLink]] | None = None,
    ) -> None:
        """Build all indices from scratch.

        Args:
            all_meta: Map of article_id → ArticleMeta.
            all_links: Map of article_id → outgoing WikiLinks.
            all_resource_meta: Map of resource_id → ResourceMeta (optional).
            all_resource_links: Map of resource_id → outgoing WikiLinks from `related` (optional).
        """
        start_time = time.perf_counter()
        self._all_meta = dict(all_meta)
        self._all_resource_meta = dict(all_resource_meta or {})

        self.forward_links = {k: list(v) for k, v in all_links.items()}

        self.back_links = {}
        self.tag_index = {}
        self.category_index = {}

        # Add resource forward links
        if all_resource_links:
            for res_id, links in all_resource_links.items():
                self.forward_links[res_id] = list(links)

        # Build tag and category indices from article metadata
        for article_id, meta in self._all_meta.items():
            for tag in meta.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = set()
                self.tag_index[tag].add(article_id)

            for cat_id in meta.categories:
                if cat_id not in self.category_index:
                    self.category_index[cat_id] = set()
                self.category_index[cat_id].add(article_id)

        # Build tag index from resource metadata
        for res_id, meta in self._all_resource_meta.items():
            for tag in meta.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = set()
                self.tag_index[tag].add(res_id)

        # Invert forward links to build back links (articles + resources)
        for source_id, links in self.forward_links.items():
            for link in links:
                if link.target_id not in self.back_links:
                    self.back_links[link.target_id] = []
                self.back_links[link.target_id].append(link)

        # Stats
        total_links = sum(len(v) for v in self.forward_links.values())
        orphans = self.get_orphans()
        broken = self.get_broken_links()
        elapsed_time = time.perf_counter() - start_time
        print(
            f"Index built: {len(all_meta)} articles, "
            f"{len(self._all_resource_meta)} resources, "
            f"{total_links} links, "
            f"{len(orphans)} orphans, {len(broken)} broken links "
            f"(took {elapsed_time:.3f}s)"
        )

    def search(self, query: str) -> list[ArticleMeta]:
        """Simple case-insensitive search across ALL titles and tags."""
        query_lower = query.lower()
        results: list[ArticleMeta] = []
        for meta in self._all_meta.values():
            if query_lower in meta.title.lower():
                results.append(meta)
                continue
            if any(query_lower in tag.lower() for tag in meta.tags):
                results.append(meta)
                continue
        return sorted(results, key=lambda m: m.title)

    def rebuild_article(
        self, article_id: str, meta: ArticleMeta, content: str
    ) -> None:
        """Incrementally update the index for a single article.

        Removes old entries and inserts new ones without a full rebuild.
        """
        # Remove old entries
        self._remove_article(article_id)

        # Insert new metadata
        self._all_meta[article_id] = meta

        # Update tag index
        for tag in meta.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = set()
            self.tag_index[tag].add(article_id)

        # Update category index
        for cat_id in meta.categories:
            if cat_id not in self.category_index:
                self.category_index[cat_id] = set()
            self.category_index[cat_id].add(article_id)

        # Update forward links
        new_links = extract_wiki_links(article_id, content)
        self.forward_links[article_id] = new_links

        # Update back links
        for link in new_links:
            if link.target_id not in self.back_links:
                self.back_links[link.target_id] = []
            self.back_links[link.target_id].append(link)

    def rebuild_resource(self, resource_id: str, meta: ResourceMeta) -> None:
        """Incrementally update the index for a single resource.

        Removes old entries and inserts new ones without a full rebuild.
        """
        self._remove_resource(resource_id)

        self._all_resource_meta[resource_id] = meta

        # Build forward links from `related` field
        new_links = [
            WikiLink(source_id=resource_id, target_id=target_id)
            for target_id in meta.related
        ]
        if new_links:
            self.forward_links[resource_id] = new_links
            for link in new_links:
                if link.target_id not in self.back_links:
                    self.back_links[link.target_id] = []
                self.back_links[link.target_id].append(link)

    def remove_article(self, article_id: str) -> None:
        """Remove an article from all indices."""
        self._remove_article(article_id)

    def remove_resource(self, resource_id: str) -> None:
        """Remove a resource from all indices."""
        self._remove_resource(resource_id)

    def _remove_article(self, article_id: str) -> None:
        """Internal: remove an article from all indices."""
        old_meta = self._all_meta.pop(article_id, None)
        if old_meta:
            # Remove from tag index
            for tag in old_meta.tags:
                if tag in self.tag_index:
                    self.tag_index[tag].discard(article_id)
                    if not self.tag_index[tag]:
                        del self.tag_index[tag]
            # Remove from category index
            for cat_id in old_meta.categories:
                if cat_id in self.category_index:
                    self.category_index[cat_id].discard(article_id)
                    if not self.category_index[cat_id]:
                        del self.category_index[cat_id]

        # Remove forward links
        old_links = self.forward_links.pop(article_id, [])

        # Remove corresponding back links
        for link in old_links:
            if link.target_id in self.back_links:
                self.back_links[link.target_id] = [
                    bl
                    for bl in self.back_links[link.target_id]
                    if bl.source_id != article_id
                ]
                if not self.back_links[link.target_id]:
                    del self.back_links[link.target_id]

    def _remove_resource(self, resource_id: str) -> None:
        """Internal: remove a resource from all indices."""
        self._all_resource_meta.pop(resource_id, None)

        # Remove forward links
        old_links = self.forward_links.pop(resource_id, [])

        # Remove corresponding back links
        for link in old_links:
            if link.target_id in self.back_links:
                self.back_links[link.target_id] = [
                    bl
                    for bl in self.back_links[link.target_id]
                    if bl.source_id != resource_id
                ]
                if not self.back_links[link.target_id]:
                    del self.back_links[link.target_id]

    # --- Query methods ---

    def what_links_here(self, article_id: str) -> list[WikiLink]:
        """Articles linking to the given ID."""
        return self.back_links.get(article_id, [])

    def search_by_tag(self, tag: str) -> set[str]:
        """Article IDs with the given tag."""
        return self.tag_index.get(tag, set())

    def articles_in_category(self, category_id: str) -> set[str]:
        """Article IDs classified under the category."""
        return self.category_index.get(category_id, set())

    def get_sub_articles(self, category_id: str) -> list[ArticleMeta]:
        """Get all articles that are members of a category."""
        sub_article_ids = self.articles_in_category(category_id)
        return [self.get_meta(id) for id in sub_article_ids if self.get_meta(id)]

    def is_dirty(self, category_id: str) -> bool:
        """Check if a category is dirty."""
        category_meta = self.get_meta(category_id)
        if not category_meta:
            return False
        
        sub_articles = self.get_sub_articles(category_id)
        for sub_article in sub_articles:
            if sub_article.modified > category_meta.modified:
                return True
        return False

    def get_all_tags(self) -> dict[str, int]:
        """All tags with their usage counts."""
        return {tag: len(ids) for tag, ids in sorted(self.tag_index.items())}

    def get_orphans(self) -> set[str]:
        """Articles and resources with no incoming or outgoing wiki links."""
        orphans = set()
        # Check articles
        for article_id in self._all_meta:
            has_outgoing = bool(self.forward_links.get(article_id))
            has_incoming = bool(self.back_links.get(article_id))
            if not has_outgoing and not has_incoming:
                orphans.add(article_id)
        # Check resources
        for resource_id in self._all_resource_meta:
            has_outgoing = bool(self.forward_links.get(resource_id))
            has_incoming = bool(self.back_links.get(resource_id))
            if not has_outgoing and not has_incoming:
                orphans.add(resource_id)
        return orphans

    def get_broken_links(self) -> list[WikiLink]:
        """Links whose targets don't exist (in either articles or resources)."""
        all_known_ids = set(self._all_meta.keys()) | set(self._all_resource_meta.keys())
        broken = []
        for links in self.forward_links.values():
            for link in links:
                if link.target_id not in all_known_ids:
                    broken.append(link)
        return broken

    def get_meta(self, article_id: str) -> ArticleMeta | None:
        """Get cached metadata for an article."""
        return self._all_meta.get(article_id)

    def get_resource_meta(self, resource_id: str) -> ResourceMeta | None:
        """Get cached metadata for a resource."""
        return self._all_resource_meta.get(resource_id)

    def get_any_meta(self, node_id: str) -> ArticleMeta | ResourceMeta | None:
        """Get cached metadata for an article or resource by ID."""
        return self._all_meta.get(node_id) or self._all_resource_meta.get(node_id)

async def rebuild_full_index(index: KnowledgeIndex, storage: 'Any', source_manager: 'Any') -> int:
    """Helper to rebuild the index from physical storage and virtual plugins.
    
    This function merges articles from the storage backend with virtual articles
    provided by plugins, and builds the full in-memory index graph.
    
    Returns the number of virtual articles discovered.
    """
    virtual_articles = await source_manager.discover_all_articles()
    virtual_meta = {a.id: a for a in virtual_articles}
    virtual_links = await source_manager.get_all_links()

    # Merge physical and virtual articles
    all_meta = dict(storage._meta_cache)
    all_meta.update(virtual_meta)
    
    all_links = storage.get_all_links()
    all_links.update(virtual_links)

    index.build(
        all_meta=all_meta,
        all_links=all_links,
        all_resource_meta=dict(storage._resource_meta_cache),
        all_resource_links=storage.get_all_resource_links(),
    )
    
    return len(virtual_articles)