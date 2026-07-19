"""
Graph structure for D3.js visualization.

D3.js graph data generation. Produces nodes+links for full graph, subgraph, and category tree.
"""

from __future__ import annotations

from typing import Any

from wikiknowledge.core.index import KnowledgeIndex
from wikiknowledge.storage.models import ArticleType


class KnowledgeGraph:
    """Builds graph data structures from the KnowledgeIndex for visualization.

    Produces node/link data consumable by D3.js force-directed graphs.
    """

    def __init__(self, index: KnowledgeIndex) -> None:
        self.index = index

    def get_full_graph(self) -> dict[str, list[dict[str, Any]]]:
        """Return the entire knowledge graph as nodes + links.

        Returns:
            {
                "nodes": [{"id", "title", "type", "linkCount", "tags"}, ...],
                "links": [{"source", "target"}, ...]
            }
        """
        nodes = []
        links_set: set[tuple[str, str]] = set()

        # All known node IDs (articles + resources)
        all_known_ids = set(self.index._all_meta.keys()) | set(self.index._all_resource_meta.keys())

        # Add article nodes
        for article_id, meta in self.index._all_meta.items():
            incoming = len(self.index.back_links.get(article_id, []))
            outgoing = len(self.index.forward_links.get(article_id, []))

            nodes.append({
                "id": article_id,
                "title": meta.title,
                "type": meta.type.value,
                "linkCount": incoming + outgoing,
                "tags": meta.tags,
                "categories": meta.categories,
            })

            # Add wiki-link edges
            for link in self.index.forward_links.get(article_id, []):
                if link.target_id in all_known_ids:
                    edge = (article_id, link.target_id)
                    links_set.add(edge)

            # Add category membership edges
            for cat_id in meta.categories:
                if cat_id in self.index._all_meta:
                    edge = (article_id, cat_id)
                    links_set.add(edge)

        # Add resource nodes
        for resource_id, meta in self.index._all_resource_meta.items():
            incoming = len(self.index.back_links.get(resource_id, []))
            outgoing = len(self.index.forward_links.get(resource_id, []))

            nodes.append({
                "id": resource_id,
                "title": meta.title,
                "type": "resource",
                "linkCount": incoming + outgoing,
                "tags": meta.tags,
                "categories": meta.categories,
                "mime_type": meta.mime_type,
            })

            # Add resource `related` edges
            for link in self.index.forward_links.get(resource_id, []):
                if link.target_id in all_known_ids:
                    edge = (resource_id, link.target_id)
                    links_set.add(edge)

        links = [
            {"source": src, "target": tgt}
            for src, tgt in links_set
        ]

        return {"nodes": nodes, "links": links}

    def get_subgraph(
        self, article_id: str, depth: int = 2
    ) -> dict[str, list[dict[str, Any]]]:
        """Return a neighborhood subgraph around a node (article or resource).

        Args:
            article_id: Center node.
            depth: How many hops to include (default 2).
        """
        all_known_ids = set(self.index._all_meta.keys()) | set(self.index._all_resource_meta.keys())
        if article_id not in all_known_ids:
            return {"nodes": [], "links": []}

        # BFS to collect nearby nodes
        visited: set[str] = set()
        frontier: set[str] = {article_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node_id in frontier:
                if node_id in visited:
                    continue
                visited.add(node_id)

                # Outgoing links
                for link in self.index.forward_links.get(node_id, []):
                    if link.target_id in all_known_ids:
                        next_frontier.add(link.target_id)

                # Incoming links
                for link in self.index.back_links.get(node_id, []):
                    if link.source_id in all_known_ids:
                        next_frontier.add(link.source_id)

                # Category membership
                meta = self.index.get_meta(node_id)
                if meta:
                    for cat_id in meta.categories:
                        if cat_id in self.index._all_meta:
                            next_frontier.add(cat_id)

                # Members of this category (if it is one)
                for member_id in self.index.articles_in_category(node_id):
                    next_frontier.add(member_id)

            frontier = next_frontier - visited

        visited.update(frontier)

        # Build node and link lists for the subgraph
        full_graph = self.get_full_graph()
        nodes = [n for n in full_graph["nodes"] if n["id"] in visited]
        links = [
            l
            for l in full_graph["links"]
            if l["source"] in visited and l["target"] in visited
        ]

        return {"nodes": nodes, "links": links}

    def get_category_tree(self) -> list[dict[str, Any]]:
        """Return a hierarchical tree of categories.

        Returns a list of root categories (those with no parent categories),
        each with nested 'children' containing their member categories.
        """
        all_categories = {
            aid: meta
            for aid, meta in self.index._all_meta.items()
            if meta.type == ArticleType.CATEGORY
        }

        # Find root categories (not listed as belonging to another category)
        child_cats = set()
        for meta in all_categories.values():
            for cat_id in meta.categories:
                if cat_id in all_categories:
                    child_cats.add(meta.id)

        def build_tree(cat_id: str) -> dict[str, Any]:
            meta = all_categories[cat_id]
            members = self.index.articles_in_category(cat_id)
            children = []
            articles = []

            for member_id in sorted(members):
                member_meta = self.index.get_meta(member_id)
                if not member_meta:
                    continue
                if member_meta.type == ArticleType.CATEGORY:
                    children.append(build_tree(member_id))
                else:
                    articles.append({
                        "id": member_id,
                        "title": member_meta.title,
                        "type": "leaf",
                    })

            return {
                "id": cat_id,
                "title": meta.title,
                "type": "category",
                "children": children,
                "articles": articles,
            }

        roots = [
            cat_id
            for cat_id in all_categories
            if cat_id not in child_cats
        ]

        return [build_tree(r) for r in sorted(roots)]
