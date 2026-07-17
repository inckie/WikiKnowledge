import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from wikiknowledge.mcp_server import create_mcp_server
from wikiknowledge.storage.models import ArticleType, ArticleMeta, Article

@pytest.fixture
def mocks():
    storage = AsyncMock()
    index = MagicMock()
    graph = MagicMock()
    source_manager = AsyncMock()
    return storage, index, graph, source_manager

@pytest.fixture
def mcp(mocks):
    storage, index, graph, sm = mocks
    return create_mcp_server(storage, index, graph, sm)

async def call_get_category_status(mcp, category_id):
    res = await mcp.call_tool("get_category_status", {"category_id": category_id})
    if isinstance(res, tuple):
        return res[0][0].text
    elif isinstance(res, list):
        return res[0].text
    else:
        return str(res)

@pytest.mark.asyncio
async def test_get_category_status_not_found(mcp, mocks):
    storage, index, _, _ = mocks
    index.get_meta.return_value = None

    result = await call_get_category_status(mcp, "missing")
    assert "Error: Category 'missing' not found" in result

@pytest.mark.asyncio
async def test_get_category_status_not_a_category(mcp, mocks):
    storage, index, _, _ = mocks
    
    meta = ArticleMeta(
        id="leaf",
        title="Leaf",
        type=ArticleType.LEAF,
    )
    index.get_meta.return_value = meta

    result = await call_get_category_status(mcp, "leaf")
    assert "Error: Article 'leaf' is not a category" in result

@pytest.mark.asyncio
async def test_get_category_status_no_members(mcp, mocks):
    storage, index, _, _ = mocks
    
    meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
    )
    index.get_meta.return_value = meta
    index.articles_in_category.return_value = []

    result = await call_get_category_status(mcp, "cat")
    assert "is not dirty (it has no members)" in result

@pytest.mark.asyncio
async def test_get_category_status_clean(mcp, mocks):
    storage, index, _, _ = mocks
    
    meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
    )
    index.get_meta.return_value = meta
    index.articles_in_category.return_value = ["member1", "member2"]
    
    content = """
    some text
    <!-- ai:start -->
    Summary:
    - [[member1]]
    - [[member2|some title]]
    <!-- ai:end -->
    """
    
    article = Article(meta=meta, content=content)
    storage.get_article.return_value = article

    result = await call_get_category_status(mcp, "cat")
    assert "not dirty (all members present in AI summary)" in result

@pytest.mark.asyncio
async def test_get_category_status_dirty(mcp, mocks):
    storage, index, _, _ = mocks
    
    meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
    )
    index.get_meta.return_value = meta
    index.articles_in_category.return_value = ["member1", "member2", "member3"]
    
    content = """
    some text
    <!-- ai:start -->
    Summary:
    - [[member1]]
    <!-- ai:end -->
    """
    
    article = Article(meta=meta, content=content)
    storage.get_article.return_value = article

    result = await call_get_category_status(mcp, "cat")
    assert "is dirty" in result
    assert "Missing members" in result
    assert "- member2" in result
    assert "- member3" in result
    assert "- member1" not in result

@pytest.mark.asyncio
async def test_get_category_status_missing_ai_block(mcp, mocks):
    storage, index, _, _ = mocks
    
    meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
    )
    index.get_meta.return_value = meta
    index.articles_in_category.return_value = ["member1"]
    
    # Missing the block entirely
    content = """
    some text
    [[member1]]
    """
    
    article = Article(meta=meta, content=content)
    storage.get_article.return_value = article

    result = await call_get_category_status(mcp, "cat")
    assert "is dirty" in result
    assert "- member1" in result
