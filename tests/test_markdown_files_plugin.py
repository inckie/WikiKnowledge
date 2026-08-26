"""
Unit tests for MarkdownFilesPlugin.

Run with: uv run pytest tests/ -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wikiknowledge.core.plugins.markdown_files import MarkdownFilesPlugin


@pytest.fixture
def docs_root(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    (root / "guides" / "auth").mkdir(parents=True)
    (root / "private").mkdir()

    (root / "intro.md").write_text(
        "---\ntitle: About\ntags: [overview, intro]\n---\n\n"
        "See the [login guide](./guides/auth/login.md) and the [guides](./guides).\n",
        encoding="utf-8",
    )
    (root / "guides" / "index.md").write_text(
        "---\ntitle: Guides\n---\n\nAll guides.\n", encoding="utf-8"
    )
    (root / "guides" / "auth" / "login.md").write_text(
        "# Login\n\nBack to [about](../../intro.md#top).\n"
        "![diagram](./flow.png)\n"
        "External [site](https://example.com/page.md).\n"
        "```md\n[not a link](../../intro.md)\n```\n",
        encoding="utf-8",
    )
    (root / "guides" / "auth" / "flow.png").write_bytes(b"png")
    (root / "private" / "secret.md").write_text("# Secret\n", encoding="utf-8")
    return root


async def _build(root: Path, **config) -> MarkdownFilesPlugin:
    plugin = MarkdownFilesPlugin("docs")
    await plugin.initialize({"path": str(root), **config})
    await plugin.discover_articles()
    return plugin


@pytest.mark.asyncio
async def test_ids_are_dash_concatenated_paths(docs_root: Path):
    plugin = await _build(docs_root)
    ids = set(plugin._articles_meta)

    assert "src:docs/intro" in ids
    assert "src:docs/guides-auth-login" in ids
    # index.md represents its folder
    assert "src:docs/guides-index" not in ids
    assert "src:docs/guides" in ids


@pytest.mark.asyncio
async def test_folders_become_categories(docs_root: Path):
    plugin = await _build(docs_root, categories=["external-docs"])

    guides = plugin._articles_meta["src:docs/guides"]
    assert guides.type.value == "category"
    assert guides.title == "Guides"
    assert guides.categories == ["external-docs"]

    login = plugin._articles_meta["src:docs/guides-auth-login"]
    assert login.categories == ["src:docs/guides-auth"]
    assert plugin._articles_meta["src:docs/guides-auth"].categories == ["src:docs/guides"]


@pytest.mark.asyncio
async def test_frontmatter_metadata_is_used(docs_root: Path):
    plugin = await _build(docs_root, tags=["imported"])

    intro = plugin._articles_meta["src:docs/intro"]
    assert intro.title == "About"
    assert intro.tags == ["overview", "intro", "imported"]

    # Title falls back to the H1 when there is no frontmatter
    assert plugin._articles_meta["src:docs/guides-auth-login"].title == "Login"


@pytest.mark.asyncio
async def test_markdown_links_are_converted_to_wiki_links(docs_root: Path):
    plugin = await _build(docs_root)

    intro = await plugin.get_article_content("src:docs/intro")
    assert "[[src:docs/guides-auth-login|login guide]]" in intro
    assert "[[src:docs/guides|guides]]" in intro

    login = await plugin.get_article_content("src:docs/guides-auth-login")
    assert "[[src:docs/intro|about]]" in login
    # external links and fenced code are untouched
    assert "[site](https://example.com/page.md)" in login
    assert "[not a link](../../intro.md)" in login


@pytest.mark.asyncio
async def test_images_are_rewritten_to_asset_urls(docs_root: Path):
    plugin = await _build(docs_root)

    login = await plugin.get_article_content("src:docs/guides-auth-login")
    assert "![diagram](/api/sources/docs/assets/guides/auth/flow.png)" in login


@pytest.mark.asyncio
async def test_include_and_exclude_patterns(docs_root: Path):
    plugin = await _build(docs_root, exclude=["private/**"])

    assert "src:docs/private-secret" not in plugin._articles_meta
    assert "src:docs/private" not in plugin._articles_meta

    plugin = await _build(docs_root, include=["guides/**/*.md"])
    assert "src:docs/intro" not in plugin._articles_meta
    assert "src:docs/guides-auth-login" in plugin._articles_meta


@pytest.mark.asyncio
async def test_links_are_extracted_for_the_index(docs_root: Path):
    plugin = await _build(docs_root)
    links = await plugin.get_links()

    targets = {link.target_id for link in links["src:docs/intro"]}
    assert "src:docs/guides-auth-login" in targets

    known = set(plugin._articles_meta)
    broken = [l.target_id for ls in links.values() for l in ls if l.target_id not in known]
    assert broken == []


@pytest.mark.asyncio
async def test_resolve_asset_rejects_traversal(docs_root: Path):
    plugin = await _build(docs_root)

    assert plugin.resolve_asset("guides/auth/flow.png") is not None
    assert plugin.resolve_asset("../outside.png") is None
    assert plugin.resolve_asset("guides/auth/missing.png") is None


@pytest.mark.asyncio
async def test_unavailable_when_path_missing(tmp_path: Path):
    plugin = MarkdownFilesPlugin("docs")
    await plugin.initialize({"path": str(tmp_path / "nope")})

    assert plugin.is_available() is False
    assert await plugin.discover_articles() == []
