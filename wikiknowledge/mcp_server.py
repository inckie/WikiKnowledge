"""
MCP (Model Context Protocol) server for AI tool access to the knowledge base.
:wk-id: wk/mcp-interface
:wk-tags: python, mcp, agents, tools
:wk-categories: ai-integration

17-tool MCP server factory. Gives AI agents full CRUD + query access to the knowledge base.
Links to: [[ai-interaction-guide]], [[src:wikiknowledge/wk/index-engine]], [[src:wikiknowledge/wk/markdown-storage]]
"""

from __future__ import annotations

import base64
import mimetypes
from datetime import datetime, timezone
from typing import Optional
import diff_match_patch as dmp_module

from mcp.server.fastmcp import FastMCP

from wikiknowledge.core.graph import KnowledgeGraph
from wikiknowledge.core.index import KnowledgeIndex
from wikiknowledge.storage.markdown_backend import MarkdownStorageBackend
from wikiknowledge.storage.models import (
    Article,
    ArticleMeta,
    ArticleType,
    ResourceMeta,
)


def create_mcp_server(
    storage: MarkdownStorageBackend,
    index: KnowledgeIndex,
    graph: KnowledgeGraph,
    source_manager,
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
            if article_id.startswith("src:") or article_id.startswith("gdrive:"):
                content = await source_manager.get_article_content(article_id)
                meta = index._all_meta[article_id]
                article = Article(meta=meta, content=content)
            else:
                article = await storage.get_article(article_id)
        except KeyError as e:
            return f"Error: Article '{article_id}' not found. {e}"

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
        if article_id.startswith("src:"):
            return f"Error: Cannot manually save virtual source articles ({article_id})"
            
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
    async def update_article(
        article_id: str,
        title: str | None = None,
        article_type: str | None = None,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
        content: str | None = None,
        content_patches: str | None = None,
    ) -> str:
        """Update an existing article using partial metadata, full content replacement, or diff-match-patch patches.

        Args:
            article_id: URL-safe unique identifier of existing article.
            title: Human-readable title (optional).
            article_type: 'leaf' or 'category' (optional).
            tags: List of freeform tags (optional).
            categories: List of category article IDs (optional).
            content: Entire new Markdown body content (optional).
            content_patches: Patches in standard diff-match-patch text format (optional).

        Returns confirmation of the update.
        """
        if article_id.startswith("src:") or article_id.startswith("gdrive:"):
            if content is not None or content_patches is not None or title is not None or article_type is not None:
                return f"Error: Cannot update content, title, or type of virtual article '{article_id}'"
            
            if not article_id.startswith("gdrive:"):
                return f"Error: Metadata updates are only supported for Google Drive articles."

            # Check if there is a plugin with the article, preferring bidirectional
            found_plugin = source_manager.get_google_drive_plugin(article_id, require_bidirectional=True)
            
            if not found_plugin:
                # Provide a more helpful error if the article exists but isn't bidirectional
                if source_manager.get_google_drive_plugin(article_id, require_bidirectional=False):
                    return f"Error: Source for '{article_id}' is not configured as bidirectional."
                return f"Error: Google Drive article '{article_id}' not found in any available source."

            try:
                # Need to get current tags/cats if they are not provided
                current_meta = index.get_meta(article_id)
                if not current_meta:
                    return f"Error: Article '{article_id}' not found in index."
                    
                new_tags = tags if tags is not None else current_meta.tags
                new_cats = categories if categories is not None else current_meta.categories
                
                found_plugin.update_article_metadata(article_id, new_tags, new_cats)
                
                # Update in-memory index immediately
                updated_meta = ArticleMeta(
                    id=current_meta.id,
                    title=current_meta.title,
                    type=current_meta.type,
                    tags=new_tags,
                    categories=new_cats,
                    created=current_meta.created,
                    modified=current_meta.modified,
                )
                index._all_meta[article_id] = updated_meta
                return f"Updated metadata for Google Drive article '{article_id}'"
            except Exception as e:
                return f"Error updating metadata: {e}"

        try:
            existing = await storage.get_article(article_id)
        except KeyError:
            return f"Error: Article '{article_id}' not found"

        if title is not None:
            existing.meta.title = title
        if article_type is not None:
            existing.meta.type = ArticleType(article_type)
        if tags is not None:
            existing.meta.tags = tags
        if categories is not None:
            existing.meta.categories = categories

        if content is not None:
            existing.content = content
        elif content_patches is not None:
            dmp = dmp_module.diff_match_patch()
            try:
                patches = dmp.patch_fromText(content_patches)
                new_text, results = dmp.patch_apply(patches, existing.content)
                if not all(results):
                    return "Error: Some patches could not be applied cleanly."
                existing.content = new_text
            except Exception as e:
                return f"Error: Failed to apply patches: {e}"

        meta = await storage.save_article(existing)
        index.rebuild_article(article_id, meta, existing.content)

        return f"Updated article '{article_id}'"

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
    async def move_article(
        article_id: str,
        new_id: str,
        title: str | None = None,
        article_type: str | None = None,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
        content: str | None = None,
        content_patches: str | None = None,
        update_links: bool = True
    ) -> str:
        """Rename an article and optionally update all references to it globally.
        
        Args:
            article_id: The current ID of the article.
            new_id: The new ID to assign to the article.
            title: Optional new title.
            article_type: Optional new type (leaf, category).
            tags: Optional new list of tags.
            categories: Optional new list of categories.
            content: Optional new content (full replacement).
            content_patches: Optional patches string in diff-match-patch format.
            update_links: Whether to update all wiki links and category references globally.
        """
        from wikiknowledge.core.refactor import rename_article
        try:
            updates = {
                "title": title,
                "type": article_type,
                "tags": tags,
                "categories": categories,
                "content": content,
                "content_patches": content_patches,
            }
            updates = {k: v for k, v in updates.items() if v is not None}
            await rename_article(storage, index, article_id, new_id, updates, update_links)
            return f"Moved article '{article_id}' to '{new_id}'"
        except KeyError:
            return f"Error: Article '{article_id}' not found"
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def move_resource(
        resource_id: str,
        new_id: str,
        update_references: bool = True
    ) -> str:
        """Rename a resource and optionally update all references to it globally.
        
        Args:
            resource_id: The current ID of the resource.
            new_id: The new ID to assign to the resource.
            update_references: Whether to update all file links globally.
        """
        from wikiknowledge.core.refactor import rename_resource
        try:
            await rename_resource(storage, index, resource_id, new_id, update_references)
            return f"Moved resource '{resource_id}' to '{new_id}'"
        except KeyError:
            return f"Error: Resource '{resource_id}' not found"
        except (ValueError, FileExistsError) as e:
            return f"Error: {e}"

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
        more recently than the category article itself, OR if its AI summary
        block is missing any of its member articles.

        Returns the dirty status, reasons if dirty, and the category's modification time.
        """
        # Get category article metadata
        category_meta = index.get_meta(category_id)
        if not category_meta:
            return f"Error: Category '{category_id}' not found."
        if category_meta.type != ArticleType.CATEGORY:
            return f"Error: Article '{category_id}' is not a category."

        # Get members
        member_ids = index.articles_in_category(category_id)
        if not member_ids:
            return (
                f"Category '{category_id}' is not dirty (it has no members).\n"
                f"- Category modified: {category_meta.modified.isoformat()}"
            )

        # Get category article content
        try:
            category_article = await storage.get_article(category_id)
            content = category_article.content
        except Exception as e:
            return f"Error reading category '{category_id}': {e}"

        # 1. Timestamp comparison
        member_metas = [index.get_meta(mid) for mid in member_ids]
        member_metas = [m for m in member_metas if m is not None]
        if not member_metas:
            return (
                f"Category '{category_id}' is not dirty (it has no valid members).\n"
                f"- Category modified: {category_meta.modified.isoformat()}"
            )
        most_recent_member = max(member_metas, key=lambda m: m.modified)
        is_dirty_by_timestamp = most_recent_member.modified > category_meta.modified

        # 2. Content inclusion comparison
        ai_start = content.find("<!-- ai:start -->")
        ai_end = content.find("<!-- ai:end -->")
        
        ai_block = ""
        if ai_start != -1 and ai_end != -1 and ai_end > ai_start:
            ai_block = content[ai_start:ai_end]
            
        missing_members = []
        for mid in sorted(member_ids):
            if f"[[{mid}]]" not in ai_block and f"[[{mid}|" not in ai_block:
                missing_members.append(mid)
                
        is_dirty_by_content = len(missing_members) > 0

        is_dirty = is_dirty_by_timestamp or is_dirty_by_content

        if is_dirty:
            reasons = []
            if is_dirty_by_timestamp:
                reasons.append(
                    f"- Most recent member ('{most_recent_member.id}') modified later: {most_recent_member.modified.isoformat()}"
                )
            if is_dirty_by_content:
                missing_str = "\n  ".join([f"- {mid}" for mid in missing_members])
                reasons.append(f"- Missing members in AI summary:\n  {missing_str}")
                
            reasons_str = "\n".join(reasons)
            return (
                f"Category '{category_id}' is dirty.\n"
                f"Reasons:\n{reasons_str}\n"
                f"- Category modified: {category_meta.modified.isoformat()}"
            )
        else:
            return (
                f"Category '{category_id}' is not dirty (all members present and timestamps valid).\n"
                f"- Category modified: {category_meta.modified.isoformat()}"
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
        """Rebuild the knowledge index from the storage backend and plugins.

        This reads all articles and resources from disk and plugins, re-parses their
        frontmatter and links, and reconstructs the in-memory indices
        (tags, categories, backlinks, resource graph edges).
        """
        await storage.initialize()
        
        from wikiknowledge.core.index import rebuild_full_index
        await rebuild_full_index(index, storage, source_manager)
        
        return "Knowledge index rebuilt successfully."

    # --- Resource tools ---

    @mcp.tool()
    async def get_resource(resource_id: str) -> str:
        """Read resource metadata by its ID.

        Returns resource metadata as YAML. For text-based resources
        (like SVG), also includes the file content. For binary files,
        includes the base64-encoded content.
        """
        try:
            resource = await storage.get_resource(resource_id)
        except KeyError:
            return f"Error: Resource '{resource_id}' not found"

        meta = resource.meta
        result = (
            f"id: {meta.id}\n"
            f"title: {meta.title}\n"
            f"filename: {meta.filename}\n"
            f"mime_type: {meta.mime_type}\n"
            f"tags: {meta.tags}\n"
            f"categories: {meta.categories}\n"
            f"related: {meta.related}\n"
            f"description: {meta.description}\n"
            f"created: {meta.created.isoformat()}\n"
            f"modified: {meta.modified.isoformat()}\n"
        )

        # Include content for resources
        if resource.data:
            if meta.mime_type.startswith(("text/", "image/svg")):
                try:
                    text_content = resource.data.decode("utf-8")
                    result += f"\n--- content ---\n{text_content}"
                except UnicodeDecodeError:
                    b64_content = base64.b64encode(resource.data).decode("utf-8")
                    result += f"\n--- base64 content ---\n{b64_content}"
            else:
                b64_content = base64.b64encode(resource.data).decode("utf-8")
                result += f"\n--- base64 content ---\n{b64_content}"
        else:
            result += "\n(Empty file)"

        return result

    @mcp.tool()
    async def list_resources() -> str:
        """List all media resources in the knowledge base.

        Returns a formatted list of resource IDs, titles, and MIME types.
        """
        metas = await storage.list_resources()
        if not metas:
            return "No resources found."

        lines = [f"Found {len(metas)} resource(s):\n"]
        for m in metas:
            lines.append(
                f"- {m.id}: \"{m.title}\" ({m.mime_type}) "
                f"tags={m.tags} related={m.related}"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def upload_resource(
        resource_id: str,
        title: str,
        data: str,
        is_base64: bool = False,
        mime_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
        related: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Upload or update a media resource in the knowledge base.

        Args:
            resource_id: Unique ID including file extension (e.g., 'logo.svg').
            title: Human-readable title of the resource.
            data: Raw string content (for text/SVG) or base64-encoded binary string.
            is_base64: Set to True if `data` is a base64-encoded string.
            mime_type: Optional MIME type (e.g., 'image/svg+xml'). Guessed from extension if omitted.
            tags: List of tags.
            categories: List of categories.
            related: List of related article IDs (outgoing links).
            description: Summary/description of the resource content for non-multimodal LLMs.
        """
        if is_base64:
            try:
                raw_data = base64.b64decode(data)
            except Exception as e:
                return f"Error: Invalid base64 data: {e}"
        else:
            raw_data = data.encode("utf-8")

        if not mime_type:
            mime_type = mimetypes.guess_type(resource_id)[0] or "application/octet-stream"

        now = datetime.now(timezone.utc)
        meta = ResourceMeta(
            id=resource_id,
            title=title,
            filename=resource_id,
            mime_type=mime_type,
            tags=tags or [],
            categories=categories or [],
            related=related or [],
            description=description or "",
            created=now,
            modified=now,
        )

        try:
            saved_meta = await storage.save_resource(resource_id, raw_data, meta)
            index.rebuild_resource(resource_id, saved_meta)
            return (
                f"Success: Resource '{resource_id}' uploaded successfully.\n"
                f"Embed syntax: [[file:{resource_id}|{title}]]"
            )
        except Exception as e:
            return f"Error: Failed to save resource '{resource_id}': {e}"

    @mcp.tool()
    async def update_resource(
        resource_id: str,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
        related: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Update metadata for an existing media resource.
        
        Args:
            resource_id: Unique ID of the resource to update.
            title: Human-readable title (optional).
            tags: List of tags (optional).
            categories: List of categories (optional).
            related: List of related article IDs (optional).
            description: Summary/description of the resource (optional).
        """
        try:
            resource = await storage.get_resource(resource_id)
        except KeyError:
            return f"Error: Resource '{resource_id}' not found."
            
        meta = resource.meta
        
        if title is not None:
            meta.title = title
        if tags is not None:
            meta.tags = tags
        if categories is not None:
            meta.categories = categories
        if related is not None:
            meta.related = related
        if description is not None:
            meta.description = description
            
        meta.modified = datetime.now(timezone.utc)
        
        try:
            saved_meta = await storage.save_resource(resource_id, resource.data, meta)
            index.rebuild_resource(resource_id, saved_meta)
            return f"Success: Resource '{resource_id}' metadata updated successfully."
        except Exception as e:
            return f"Error: Failed to update resource metadata '{resource_id}': {e}"

    @mcp.tool()
    async def delete_resource(resource_id: str) -> str:
        """Delete a media resource and its metadata sidecar from the knowledge base.

        Args:
            resource_id: Unique ID of the resource to delete.
        """
        try:
            await storage.delete_resource(resource_id)
            index.remove_resource(resource_id)
            return f"Success: Resource '{resource_id}' deleted successfully."
        except KeyError:
            return f"Error: Resource '{resource_id}' not found."
        except Exception as e:
            return f"Error: Failed to delete resource '{resource_id}': {e}"

    @mcp.tool()
    async def list_sources() -> list[dict]:
        """List all configured knowledge sources and their connection status."""
        return source_manager.get_status()

    @mcp.tool()
    async def rescan_sources() -> str:
        """Re-initialize all sources and rebuild the knowledge graph index."""
        try:
            await source_manager.initialize()

            # Sync Google Drive sources (fetches new/changed docs)
            sync_results = await source_manager.sync_all()

            virtual_articles = await source_manager.discover_all_articles()
            virtual_meta = {a.id: a for a in virtual_articles}
            virtual_links = await source_manager.get_all_links()

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
            synced = ", ".join(f"{s}: {r}" for s, r in sync_results.items()) if sync_results else "none"
            return (
                f"Successfully rebuilt index and rescanned sources. "
                f"Discovered {len(virtual_articles)} virtual articles. "
                f"Drive sync results: {synced}"
            )
        except Exception as e:
            return f"Error triggering rescan: {e}"

    return mcp

