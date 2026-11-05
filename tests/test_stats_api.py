import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from wikiknowledge.api.search import router as search_router, get_stats
from wikiknowledge.storage.models import ArticleMeta, ArticleType, ResourceMeta
from wikiknowledge.core.index import WikiLink


def test_get_stats_endpoint():
    app = FastAPI()
    app.include_router(search_router, prefix="/api")

    # Mock storage and index
    mock_storage = AsyncMock()
    mock_cat = MagicMock()
    mock_cat.id = "overview"
    mock_cat.title = "Overview"
    mock_storage.get_all_categories.return_value = [mock_cat]

    mock_index = MagicMock()
    
    # Meta dicts
    mock_index._all_meta = {
        "overview": ArticleMeta(id="overview", title="Overview", type=ArticleType.CATEGORY),
        "page-a": ArticleMeta(id="page-a", title="Page A", type=ArticleType.LEAF),
        "src:code": ArticleMeta(id="src:code", title="Code", type=ArticleType.LEAF),
    }
    mock_index._all_resource_meta = {
        "image.png": ResourceMeta(id="image.png", title="Image", filename="image.png", mime_type="image/png")
    }

    # Links: page-a -> missing-page, page-a -> image.png
    link1 = WikiLink(source_id="page-a", target_id="missing-page", display_text="Missing", line_number=12)
    link2 = WikiLink(source_id="page-a", target_id="image.png", display_text="Img", line_number=15)
    mock_index.forward_links = {
        "page-a": [link1, link2],
    }
    mock_index.back_links = {
        "image.png": [link2],
    }
    mock_index.tag_index = {"tag1": ["page-a"], "tag2": ["page-a", "src:code"]}

    app.state.storage = mock_storage
    app.state.index = mock_index

    client = TestClient(app)
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()

    assert data["total_articles"] == 3
    assert data["native_articles"] == 2
    assert data["external_articles"] == 1
    assert data["total_resources"] == 1
    assert data["total_categories"] == 1
    assert data["total_tags"] == 2
    assert data["total_links"] == 2

    # Broken links
    assert data["broken_links_count"] == 1
    assert len(data["broken_links"]) == 1
    assert data["broken_links"][0]["source_id"] == "page-a"
    assert data["broken_links"][0]["target_id"] == "missing-page"
    assert data["broken_links"][0]["line_number"] == 12

    # Orphaned pages (overview excluded, image.png has backlink, page-a and src:code are orphans)
    assert data["orphaned_pages_count"] == 2
    orphan_ids = [o["id"] for o in data["orphaned_pages"]]
    assert "page-a" in orphan_ids
    assert "src:code" in orphan_ids
