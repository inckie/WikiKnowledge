"""MCP (Model Context Protocol) server for AI tool access to the knowledge base."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from wikiknowledge.core.graph import KnowledgeGraph
from wikiknowledge.core.index import KnowledgeIndex
from wikiknowledge.storage.markdown_backend import MarkdownStorageBackend
from wikiknowledge.storage.models import Article, ArticleMeta, ArticleType

from datetime import datetime, timezone


def create_mcp_server(
    storage: MarkdownStorageBackend,
    index: KnowledgeIndex,
    graph: KnowledgeGraph,
) -> FastMCP:
    """Create an MCP server with tools for knowledge base access.

    This server is mounted on the FastAPI app and allows AI agents
    (via IDE integration) to read, write, and query articles.
    """

    mcp = FastMCP(
        "WikiKnowledge",
        instructions=(
            "WikiKnowledge is a hierarchical knowledge graph system built over "
            "markdown files. Articles use YAML frontmatter for metadata and "
            "[[wiki-links]] for internal connections. Category articles use "
            "<!-- human:start/end --> and <!-- ai:start/end --> markers to "
            "separate human-written from AI-generated content. "
            "Use these tools to read, create, update, and query articles."
        ),
    )

    @mcp.tool()
    async def get_article(article_id: str) -> str:
        """Read a full article (metadata + content) by its ID.

        Returns the article as YAML frontmatter + markdown body.
        """
        try:
            article = await storage.get_article(article_id)
        except KeyError:
            return f"Error: Article '{article_id}' not found"

        meta = article.meta
        return (
            f"---\n"
            f"id: {meta.id}\n"
            f"title: {meta.title}\n"
            f"type: {meta.type.value}\n"
            f"tags: {meta.tags}\n"
            f"categories: {meta.categories}\n"
            f"created: {meta.created.isoformat()}\n"
            f"modified: {meta.modified.isoformat()}\n"
            f"---\n\n"
            f"{article.content}"
        )

    @mcp.tool()
    async def list_articles(
        article_type: str | None = None,
        tag: str | None = None,
        category: str | None = None,
    ) -> str:
        """List articles, optionally filtered by type ('leaf'/'category'), tag, or category ID.

        Returns a formatted list of article IDs and titles.
        """
        if tag:
            metas = await storage.get_by_tag(tag)
        elif category:
            metas = await storage.get_by_category(category)
        else:
            atype = ArticleType(article_type) if article_type else None
            metas = await storage.list_articles(atype)

        if not metas:
            return "No articles found."

        lines = [f"Found {len(metas)} article(s):\n"]
        for m in metas:
            lines.append(
                f"- [{m.type.value}] {m.id}: \"{m.title}\" "
                f"tags={m.tags} categories={m.categories}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def save_article(
        article_id: str,
        title: str,
        article_type: str,
        tags: list[str],
        categories: list[str],
        content: str,
    ) -> str:
        """Create or update an article.

        Args:
            article_id: URL-safe unique identifier (slug).
            title: Human-readable title.
            article_type: 'leaf' or 'category'.
            tags: List of freeform tags.
            categories: List of category article IDs this article belongs to.
            content: Markdown body content (without frontmatter).

        Returns confirmation with the saved article ID.
        """
        is_new = article_id not in storage._meta_cache

        # Preserve original created timestamp if updating
        created = datetime.now(timezone.utc)
        if not is_new:
            try:
                existing = await storage.get_article(article_id)
                created = existing.meta.created
            except KeyError:
                pass

        article = Article(
            meta=ArticleMeta(
                id=article_id,
                title=title,
                type=ArticleType(article_type),
                tags=tags,
                categories=categories,
                created=created,
                modified=datetime.now(timezone.utc),
            ),
            content=content,
        )

        meta = await storage.save_article(article)
        index.rebuild_article(article_id, meta, content)

        action = "Created" if is_new else "Updated"
        return f"{action} article '{article_id}' ({title})"

    @mcp.tool()
    async def delete_article(article_id: str) -> str:
        """Delete an article by its ID."""
        try:
            await storage.delete_article(article_id)
            index.remove_article(article_id)
            return f"Deleted article '{article_id}'"
        except KeyError:
            return f"Error: Article '{article_id}' not found"

    @mcp.tool()
    async def get_backlinks(article_id: str) -> str:
        """Get all articles that link to a given article ('What links here').

        Returns a list of source articles with their titles.
        """
        backlinks = index.what_links_here(article_id)
        if not backlinks:
            return f"No articles link to '{article_id}'."

        lines = [f"Articles linking to '{article_id}':\n"]
        for bl in backlinks:
            source_meta = index.get_meta(bl.source_id)
            title = source_meta.title if source_meta else "Unknown"
            display = f" (as '{bl.display_text}')" if bl.display_text else ""
            lines.append(f"- {bl.source_id}: \"{title}\" at line {bl.line_number}{display}")
        return "\n".join(lines)

    @mcp.tool()
    async def get_category_members(category_id: str) -> str:
        """Get all articles belonging to a specific category.

        Returns article IDs and titles of all members.
        """
        member_ids = index.articles_in_category(category_id)
        if not member_ids:
            return f"No articles in category '{category_id}'."

        lines = [f"Articles in category '{category_id}':\n"]
        for mid in sorted(member_ids):
            meta = index.get_meta(mid)
            if meta:
                lines.append(f"- [{meta.type.value}] {mid}: \"{meta.title}\"")
        return "\n".join(lines)

    @mcp.tool()
    async def get_category_status(category_id: str) -> str:
        """Check if a category article's summary is outdated ('dirty').

        A category is dirty if any of its member articles have been modified
        more recently than the category article itself.

        Returns the dirty status, the category's modification time, and the
        most recent modification time among its members.
        """
        try:
            # Get category article metadata
            category_meta = await storage.get_meta(category_id)
            if category_meta.type != ArticleType.CATEGORY:
                return f"Error: Article '{category_id}' is not a category."
        except KeyError:
            return f"Error: Category '{category_id}' not found."

        # Get members and their modification times
        member_ids = index.articles_in_category(category_id)
        if not member_ids:
            return (
                f"Category '{category_id}' is not dirty (it has no members).\n"
                f"- Category modified: {category_meta.modified.isoformat()}"
            )

        member_metas = [await storage.get_meta(mid) for mid in member_ids]
        most_recent_member = max(member_metas, key=lambda m: m.modified)

        # Compare timestamps
        is_dirty = most_recent_member.modified > category_meta.modified

        return (
            f"Category '{category_id}' is {'dirty' if is_dirty else 'not dirty'}.\n"
            f"- Category modified: {category_meta.modified.isoformat()}\n"
            f"- Most recent member ('{most_recent_member.id}') modified: {most_recent_member.modified.isoformat()}"
        )

    @mcp.tool()
    async def search(query: str) -> str:
        """Full-text search across article titles, tags, and content.

        Returns matching article IDs and titles.
        """
        results = await storage.search(query)
        if not results:
            return f"No results for '{query}'."

        lines = [f"Search results for '{query}' ({len(results)} matches):\n"]
        for m in results:
            lines.append(f"- [{m.type.value}] {m.id}: \"{m.title}\"")
        return "\n".join(lines)

    @mcp.tool()
    async def get_all_tags() -> str:
        """List all tags used across the knowledge base with their usage counts."""
        tag_counts = await storage.get_all_tags()
        if not tag_counts:
            return "No tags found."

        lines = ["Tags:\n"]
        for tag, count in tag_counts.items():
            lines.append(f"- {tag}: {count} article(s)")
        return "\n".join(lines)

    @mcp.tool()
    async def rebuild_index() -> str:
        """Rebuild the knowledge index from the storage backend.

        This reads all articles from disk, re-parses their frontmatter and links,
        and reconstructs the in-memory indices (tags, categories, backlinks).
        """
        await storage.initialize()
        index.build(
            all_meta=dict(storage._meta_cache),
            all_links=storage.get_all_links(),
        )
        return "Knowledge index rebuilt successfully."

    return mcp
