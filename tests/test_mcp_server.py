import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from wikiknowledge.mcp_server import create_mcp_server
from wikiknowledge.storage.models import ArticleType, ArticleMeta, Article, ResourceMeta, Resource

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
    
    base_time = datetime.now(timezone.utc)
    
    cat_meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
        modified=base_time
    )
    
    member_meta = ArticleMeta(
        id="member1",
        title="Member 1",
        type=ArticleType.LEAF,
        modified=base_time - timedelta(days=1)
    )

    def mock_get_meta(mid):
        if mid == "cat": return cat_meta
        return member_meta

    index.get_meta.side_effect = mock_get_meta
    index.articles_in_category.return_value = ["member1"]
    
    content = """
    some text
    <!-- ai:start -->
    Summary:
    - [[member1]]
    <!-- ai:end -->
    """
    
    article = Article(meta=cat_meta, content=content)
    storage.get_article.return_value = article

    result = await call_get_category_status(mcp, "cat")
    assert "not dirty (all members present and timestamps valid)" in result

@pytest.mark.asyncio
async def test_get_category_status_dirty_by_content(mcp, mocks):
    storage, index, _, _ = mocks
    
    base_time = datetime.now(timezone.utc)
    
    cat_meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
        modified=base_time
    )
    
    member_meta = ArticleMeta(
        id="member1",
        title="Member 1",
        type=ArticleType.LEAF,
        modified=base_time - timedelta(days=1)
    )

    def mock_get_meta(mid):
        if mid == "cat": return cat_meta
        return member_meta

    index.get_meta.side_effect = mock_get_meta
    index.articles_in_category.return_value = ["member1"]
    
    content = """
    some text
    <!-- ai:start -->
    Summary:
    <!-- ai:end -->
    """
    
    article = Article(meta=cat_meta, content=content)
    storage.get_article.return_value = article

    result = await call_get_category_status(mcp, "cat")
    assert "is dirty" in result
    assert "Missing members in AI summary" in result
    assert "- member1" in result

@pytest.mark.asyncio
async def test_get_category_status_dirty_by_timestamp(mcp, mocks):
    storage, index, _, _ = mocks
    
    base_time = datetime.now(timezone.utc)
    
    cat_meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
        modified=base_time
    )
    
    member_meta = ArticleMeta(
        id="member1",
        title="Member 1",
        type=ArticleType.LEAF,
        modified=base_time + timedelta(days=1)
    )

    def mock_get_meta(mid):
        if mid == "cat": return cat_meta
        return member_meta

    index.get_meta.side_effect = mock_get_meta
    index.articles_in_category.return_value = ["member1"]
    
    content = """
    some text
    <!-- ai:start -->
    Summary:
    - [[member1]]
    <!-- ai:end -->
    """
    
    article = Article(meta=cat_meta, content=content)
    storage.get_article.return_value = article

    result = await call_get_category_status(mcp, "cat")
    assert "is dirty" in result
    assert "modified later" in result

@pytest.mark.asyncio
async def test_get_category_status_missing_ai_block(mcp, mocks):
    storage, index, _, _ = mocks
    
    cat_meta = ArticleMeta(
        id="cat",
        title="Cat",
        type=ArticleType.CATEGORY,
        modified=datetime.now(timezone.utc)
    )
    
    member_meta = ArticleMeta(
        id="member1",
        title="Member 1",
        type=ArticleType.LEAF,
        modified=datetime.now(timezone.utc) - timedelta(days=1)
    )

    def mock_get_meta(mid):
        if mid == "cat": return cat_meta
        return member_meta
        
    index.get_meta.side_effect = mock_get_meta
    index.articles_in_category.return_value = ["member1"]
    
    # Missing the block entirely
    content = """
    some text
    [[member1]]
    """
    
    article = Article(meta=cat_meta, content=content)
    storage.get_article.return_value = article

    result = await call_get_category_status(mcp, "cat")
    assert "is dirty" in result
    assert "- member1" in result


async def _invoke_tool(mcp, name, args):
    res = await mcp.call_tool(name, args)
    if isinstance(res, tuple):
        return res[0][0].text
    elif isinstance(res, list):
        return res[0].text
    else:
        return str(res)


@pytest.mark.asyncio
async def test_replace_resource_success(mcp, mocks):
    storage, index, _, _ = mocks
    created_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    old_meta = ResourceMeta(
        id="logo.svg",
        title="Old Logo",
        filename="logo.svg",
        mime_type="image/svg+xml",
        created=created_time,
        modified=created_time,
    )
    old_resource = Resource(meta=old_meta, data=b"<svg>old</svg>")
    storage.get_resource.return_value = old_resource
    storage.save_resource.side_effect = lambda r_id, data, meta: meta

    result = await _invoke_tool(
        mcp,
        "replace_resource",
        {
            "resource_id": "logo.svg",
            "data": "<svg>new</svg>",
            "title": "New Logo",
        },
    )

    assert "Success: Resource 'logo.svg' replaced successfully." in result
    storage.save_resource.assert_called_once()
    saved_id, saved_data, saved_meta = storage.save_resource.call_args[0]
    assert saved_id == "logo.svg"
    assert saved_data == b"<svg>new</svg>"
    assert saved_meta.title == "New Logo"
    assert saved_meta.created == created_time
    index.rebuild_resource.assert_called_once_with("logo.svg", saved_meta)


@pytest.mark.asyncio
async def test_replace_resource_not_found(mcp, mocks):
    storage, index, _, _ = mocks
    storage.get_resource.side_effect = KeyError("logo.svg")

    result = await _invoke_tool(
        mcp,
        "replace_resource",
        {
            "resource_id": "logo.svg",
            "data": "<svg>new</svg>",
        },
    )

    assert "Error: Resource 'logo.svg' not found." in result


@pytest.mark.asyncio
async def test_update_resource_with_data(mcp, mocks):
    storage, index, _, _ = mocks
    old_meta = ResourceMeta(
        id="notes.txt",
        title="Notes",
        filename="notes.txt",
        mime_type="text/plain",
    )
    old_resource = Resource(meta=old_meta, data=b"original")
    storage.get_resource.return_value = old_resource
    storage.save_resource.side_effect = lambda r_id, data, meta: meta

    result = await _invoke_tool(
        mcp,
        "update_resource",
        {
            "resource_id": "notes.txt",
            "data": "updated content",
        },
    )

    assert "Success: Resource 'notes.txt' updated successfully." in result
    saved_id, saved_data, saved_meta = storage.save_resource.call_args[0]
    assert saved_data == b"updated content"
    assert saved_meta.title == "Notes"


@pytest.mark.asyncio
async def test_update_resource_metadata_only(mcp, mocks):
    storage, index, _, _ = mocks
    old_meta = ResourceMeta(
        id="notes.txt",
        title="Notes",
        filename="notes.txt",
        mime_type="text/plain",
    )
    old_resource = Resource(meta=old_meta, data=b"original")
    storage.get_resource.return_value = old_resource
    storage.save_resource.side_effect = lambda r_id, data, meta: meta

    result = await _invoke_tool(
        mcp,
        "update_resource",
        {
            "resource_id": "notes.txt",
            "title": "Renamed Notes",
        },
    )

    assert "Success: Resource 'notes.txt' updated successfully." in result
    saved_id, saved_data, saved_meta = storage.save_resource.call_args[0]
    assert saved_data == b"original"
    assert saved_meta.title == "Renamed Notes"


@pytest.mark.asyncio
async def test_upload_resource_preserves_created(mcp, mocks):
    storage, index, _, _ = mocks
    past_time = datetime(2024, 6, 1, tzinfo=timezone.utc)
    existing_meta = ResourceMeta(
        id="file.bin",
        title="Existing File",
        filename="file.bin",
        created=past_time,
    )
    storage.get_resource_meta.return_value = existing_meta
    storage.save_resource.side_effect = lambda r_id, data, meta: meta

    result = await _invoke_tool(
        mcp,
        "upload_resource",
        {
            "resource_id": "file.bin",
            "title": "New Title",
            "data": "new bytes",
        },
    )

    assert "Success: Resource 'file.bin' uploaded successfully." in result
    saved_id, saved_data, saved_meta = storage.save_resource.call_args[0]
    assert saved_meta.created == past_time


@pytest.mark.asyncio
async def test_get_article_with_transclusion(mcp, mocks):
    storage, index, _, _ = mocks

    now = datetime.now(timezone.utc)
    source_meta = ArticleMeta(
        id="guide",
        title="Guide Article",
        type=ArticleType.LEAF,
        created=now,
        modified=now,
    )
    target_meta = ArticleMeta(
        id="syntax",
        title="Syntax Doc",
        type=ArticleType.LEAF,
        created=now,
        modified=now,
    )

    def mock_get_article(art_id):
        if art_id == "guide":
            return Article(meta=source_meta, content="Guide intro.\n\n![[syntax#Section A]]\n\nGuide footer.")
        elif art_id == "syntax":
            return Article(meta=target_meta, content="# Syntax\n## Section A\nDetailed section A text.\n## Section B\nOther text.")
        raise KeyError(art_id)

    storage.get_article.side_effect = mock_get_article
    index.get_meta.side_effect = lambda aid: target_meta if aid == "syntax" else source_meta

    result = await _invoke_tool(mcp, "get_article", {"article_id": "guide"})
    assert "> 📦 **Transcluded from [[syntax#Section A|Syntax Doc > Section A]]**" in result
    assert "Detailed section A text." in result
    assert "Other text." not in result


@pytest.mark.asyncio
async def test_get_article_with_disconnected_transclusion(mcp, mocks):
    storage, index, _, source_manager = mocks

    now = datetime.now(timezone.utc)
    source_meta = ArticleMeta(
        id="guide",
        title="Guide Article",
        type=ArticleType.LEAF,
        created=now,
        modified=now,
    )
    disc_meta = ArticleMeta(
        id="src:repo/module",
        title="Repo Module",
        type=ArticleType.LEAF,
        created=now,
        modified=now,
    )

    storage.get_article.return_value = Article(meta=source_meta, content="Intro.\n\n![[src:repo/module#Code Details]]\n\nOutro.")
    index.get_meta.side_effect = lambda aid: disc_meta if aid == "src:repo/module" else source_meta

    mock_plug = MagicMock()
    mock_plug.is_available.return_value = False
    source_manager.plugins = {"repo": mock_plug}
    source_manager.get_article_content = AsyncMock(side_effect=KeyError("Source 'repo' is currently disconnected"))

    result = await _invoke_tool(mcp, "get_article", {"article_id": "guide"})
    assert "⊘ **Transcluded content unavailable (Source disconnected)" in result
    assert "Repo Module > Code Details" in result


@pytest.mark.asyncio
async def test_search_miss_logged_and_reported_by_kb_health(tmp_path, monkeypatch):
    from wikiknowledge.core.index import KnowledgeIndex, WikiLink

    (tmp_path / "articles").mkdir()
    (tmp_path / "articles" / "huge.md").write_text("x" * 3000)
    storage = AsyncMock()
    storage.knowledge_dir = tmp_path
    storage.articles_dir = tmp_path / "articles"

    index = MagicMock()
    index._all_meta = {
        "overview": ArticleMeta(id="overview", title="Overview", type=ArticleType.CATEGORY),
        "page-a": ArticleMeta(id="page-a", title="Page A", type=ArticleType.LEAF),
        "huge": ArticleMeta(id="huge", title="Huge", type=ArticleType.LEAF),
        "src:code": ArticleMeta(id="src:code", title="Code", type=ArticleType.LEAF),
    }
    index._all_resource_meta = {}
    index.forward_links = {"page-a": [
        WikiLink(source_id="page-a", target_id="nowhere", display_text=None, line_number=3),
        WikiLink(source_id="page-a", target_id="huge#part", display_text=None, line_number=4),
    ]}
    index.back_links = {"huge": [index.forward_links["page-a"][1]]}
    index.get_broken_links = lambda: KnowledgeIndex.get_broken_links(index)

    monkeypatch.setattr("wikiknowledge.mcp_server.lexical_search", AsyncMock(return_value=([], False)))
    mcp = create_mcp_server(storage, index, MagicMock(), AsyncMock())
    for q in ("AppLoaderBridge android", "apploaderbridge  Android", "other"):
        assert "No results" in await _invoke_tool(mcp, "search", {"query": q})

    report = await _invoke_tool(mcp, "kb_health", {"max_kb": 2})
    assert "page-a → [[nowhere]] (line 3)" in report
    assert "huge#part" not in report                      # anchor into an existing article
    assert "- page-a: \"Page A\"" in report and "src:code" not in report and "overview:" not in report
    assert "- huge: 2.9 KB" in report
    assert "\"AppLoaderBridge android\": missed 2×, 2× with no result at all" in report
