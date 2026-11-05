import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from wikiknowledge.core.transclusion import extract_section, slugify, resolve_transclusions
from wikiknowledge.storage.models import Article, ArticleMeta, ArticleType


def test_slugify():
    assert slugify("Basic Syntax") == "basic-syntax"
    assert slugify("Query Methods (Advanced)") == "query-methods-advanced"
    assert slugify("hello---world") == "hello-world"


def test_extract_section_by_heading_title():
    markdown = """# Document Title

Some intro text.

## Section One
Content of section one.
More lines.

### Subsection 1.1
Sub-content inside section one.

## Section Two
Content of section two.
"""
    result = extract_section(markdown, "Section One")
    assert result is not None
    body, title, level = result
    assert title == "Section One"
    assert level == 2
    assert "Content of section one." in body
    assert "### Subsection 1.1" in body
    assert "Sub-content inside section one." in body
    assert "Content of section two" not in body


def test_extract_section_by_slug():
    markdown = """# Doc
## Data Structures & Algorithms
Algorithm content here.

## Next Section
Other content.
"""
    result = extract_section(markdown, "data-structures-algorithms")
    assert result is not None
    body, title, level = result
    assert "Algorithm content here" in body
    assert "Other content" not in body


def test_extract_section_code_blocks_protected():
    markdown = """# Doc
## Real Section
```python
## Not A Real Header
print("hello")
```
Body after code.

## Another Section
Stop here.
"""
    result = extract_section(markdown, "Not A Real Header")
    assert result is None

    result = extract_section(markdown, "Real Section")
    assert result is not None
    body, _, _ = result
    assert 'print("hello")' in body
    assert "Body after code." in body
    assert "Stop here" not in body


def test_extract_section_future_block_id():
    markdown = """# Doc
Here is an important paragraph that has an anchor. ^my-block-anchor

Here is another paragraph.
"""
    result = extract_section(markdown, "^my-block-anchor")
    assert result is not None
    body, title, level = result
    assert title == "^my-block-anchor"
    assert level == 0
    assert "Here is an important paragraph that has an anchor." in body
    assert "^my-block-anchor" not in body
    assert "Here is another paragraph" not in body


@pytest.mark.asyncio
async def test_resolve_transclusions_html():
    target_meta = ArticleMeta(
        id="target-art",
        title="Target Article",
        type=ArticleType.LEAF,
        tags=[],
        categories=[],
        created=datetime.now(timezone.utc),
        modified=datetime.now(timezone.utc),
    )
    target_content = """# Target Article
## Key Concepts
Transcluded concept text.

## Other Stuff
Not included.
"""
    target_article = Article(meta=target_meta, content=target_content)

    storage = MagicMock()
    storage.get_article = AsyncMock(return_value=target_article)
    source_manager = MagicMock()
    index = MagicMock()
    index.get_meta.return_value = target_meta

    content = "Before transclusion.\n\n![[target-art#Key Concepts]]\n\nAfter transclusion."
    resolved = await resolve_transclusions(
        content=content,
        current_article_id="source-art",
        storage=storage,
        source_manager=source_manager,
        index=index,
        format="html",
    )

    assert "<!-- transclusion:start id=\"target-art\" section=\"key-concepts\" label=\"Target Article > Key Concepts\"" in resolved
    assert "Transcluded concept text." in resolved
    assert "Not included." not in resolved
    assert "<!-- transclusion:end -->" in resolved


@pytest.mark.asyncio
async def test_resolve_transclusions_markdown_ai():
    target_meta = ArticleMeta(
        id="src:wk/parser",
        title="Parser Module",
        type=ArticleType.LEAF,
        tags=[],
        categories=[],
        created=datetime.now(timezone.utc),
        modified=datetime.now(timezone.utc),
    )
    target_content = """# Parser
## Regex Definitions
WIKI_LINK_RE matches wiki links.
"""
    source_manager = MagicMock()
    source_manager.get_article_content = AsyncMock(return_value=target_content)
    storage = MagicMock()
    index = MagicMock()
    index.get_meta.return_value = target_meta

    content = "See the implementation:\n\n![[src:wk/parser#Regex Definitions]]"
    resolved = await resolve_transclusions(
        content=content,
        current_article_id="source-art",
        storage=storage,
        source_manager=source_manager,
        index=index,
        format="markdown",
    )

    assert "> 📦 **Transcluded from [[src:wk/parser#Regex Definitions|Parser Module > Regex Definitions]]**" in resolved
    assert "> WIKI_LINK_RE matches wiki links." in resolved


@pytest.mark.asyncio
async def test_resolve_transclusions_circular_detection():
    storage = MagicMock()
    source_manager = MagicMock()
    index = MagicMock()

    content = "Self reference: ![[self-art]]"
    resolved = await resolve_transclusions(
        content=content,
        current_article_id="self-art",
        storage=storage,
        source_manager=source_manager,
        index=index,
        format="markdown",
    )

    assert "Circular transclusion detected" in resolved


@pytest.mark.asyncio
async def test_resolve_transclusions_disconnected_source():
    source_manager = MagicMock()
    mock_plugin = MagicMock()
    mock_plugin.is_available.return_value = False
    source_manager.plugins = {"remote-repo": mock_plugin}
    source_manager.get_article_content = AsyncMock(side_effect=KeyError("Source 'remote-repo' is currently disconnected"))

    index = MagicMock()
    cached_meta = ArticleMeta(
        id="src:remote-repo/auth",
        title="Auth Service",
        type=ArticleType.LEAF,
        tags=[],
        categories=[],
        created=datetime.now(timezone.utc),
        modified=datetime.now(timezone.utc),
    )
    index.get_meta.return_value = cached_meta
    storage = MagicMock()

    content = "Check authentication logic:\n\n![[src:remote-repo/auth#Login Flow]]"
    
    # Test HTML format
    resolved_html = await resolve_transclusions(
        content=content,
        current_article_id="source-art",
        storage=storage,
        source_manager=source_manager,
        index=index,
        format="html",
    )
    assert 'disconnected="true"' in resolved_html
    assert 'badge="Source Disconnected"' in resolved_html
    assert 'Auth Service > Login Flow' in resolved_html

    # Test Markdown format (for AI / MCP)
    resolved_md = await resolve_transclusions(
        content=content,
        current_article_id="source-art",
        storage=storage,
        source_manager=source_manager,
        index=index,
        format="markdown",
    )
    assert "⊘ **Transcluded content unavailable (Source disconnected)" in resolved_md
    assert "Auth Service > Login Flow" in resolved_md
