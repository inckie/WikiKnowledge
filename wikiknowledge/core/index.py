"""In-memory knowledge index for fast lookups."""

from __future__ import annotations

from wikiknowledge.core.parser import extract_wiki_links
from wikiknowledge.storage.models import ArticleMeta, WikiLink


class KnowledgeIndex:
    """Inverted indices over articles for fast query operations.

    Maintains four indices built from article metadata and wiki links:
    - forward_links: article_id → outgoing WikiLinks
    - back_links: article_id → incoming WikiLinks ("what links here")
    - tag_index: tag → set of article IDs
    - category_index: category_id → set of member article IDs
    """

    def __init__(self) -> None:
        self.forward_links: dict[str, list[WikiLink]] = {}
        self.back_links: dict[str, list[WikiLink]] = {}
        self.tag_index: dict[str, set[str]] = {}
        self.category_index: dict[str, set[str]] = {}
        self._all_meta: dict[str, ArticleMeta] = {}

    def build(
        self,
        all_meta: dict[str, ArticleMeta],
        all_links: dict[str, list[WikiLink]],
    ) -> None:
        """Build all indices from scratch.

        Args:
            all_meta: Map of article_id → ArticleMeta.
            all_links: Map of article_id → outgoing WikiLinks.
        """
        self._all_meta = dict(all_meta)
        self.forward_links = {k: list(v) for k, v in all_links.items()}
        self.back_links = {}
        self.tag_index = {}
        self.category_index = {}

        # Build tag and category indices from metadata
        for article_id, meta in all_meta.items():
            for tag in meta.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = set()
                self.tag_index[tag].add(article_id)

            for cat_id in meta.categories:
                if cat_id not in self.category_index:
                    self.category_index[cat_id] = set()
                self.category_index[cat_id].add(article_id)

        # Invert forward links to build back links
        for source_id, links in self.forward_links.items():
            for link in links:
                if link.target_id not in self.back_links:
                    self.back_links[link.target_id] = []
                self.back_links[link.target_id].append(link)

        # Stats
        total_links = sum(len(v) for v in self.forward_links.values())
        orphans = self.get_orphans()
        broken = self.get_broken_links()
        print(
            f"Index built: {len(all_meta)} articles, {total_links} links, "
            f"{len(orphans)} orphans, {len(broken)} broken links"
        )

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

    def remove_article(self, article_id: str) -> None:
        """Remove an article from all indices."""
        self._remove_article(article_id)

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

        # Also remove any back links where this article was the target
        # (handled by the source articles' forward links — no action needed here)

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
        """Articles with no incoming or outgoing wiki links."""
        orphans = set()
        for article_id in self._all_meta:
            has_outgoing = bool(self.forward_links.get(article_id))
            has_incoming = bool(self.back_links.get(article_id))
            if not has_outgoing and not has_incoming:
                orphans.add(article_id)
        return orphans

    def get_broken_links(self) -> list[WikiLink]:
        """Links whose targets don't exist."""
        broken = []
        for links in self.forward_links.values():
            for link in links:
                if link.target_id not in self._all_meta:
                    broken.append(link)
        return broken

    def get_meta(self, article_id: str) -> ArticleMeta | None:
        """Get cached metadata for an article."""
        return self._all_meta.get(article_id)