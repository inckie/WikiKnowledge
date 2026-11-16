from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from wikiknowledge.api.search import router as search_router
from wikiknowledge.storage.models import Article, ArticleMeta, ArticleType


def test_search_ranks_native_and_virtual_articles():
    metas = {
        "cast-ios": ArticleMeta(id="cast-ios", title="Chromecast on iOS", type=ArticleType.LEAF, tags=["chromecast"]),
        "cast-arch": ArticleMeta(id="cast-arch", title="Chromecast architecture", type=ArticleType.LEAF),
        "src:qb-docs/screens": ArticleMeta(id="src:qb-docs/screens", title="Screens", type=ArticleType.LEAF),
    }
    bodies = {
        "cast-ios": "No devices found: NSBonjourServices placeholder",
        "cast-arch": "sender and receiver",
    }

    storage = AsyncMock()
    storage.get_article.side_effect = lambda i: Article(meta=metas[i], content=bodies[i])
    index = MagicMock()
    index._all_meta = metas
    index.get_meta.side_effect = metas.get
    sources = AsyncMock()
    sources.get_article_content.return_value = "ComponentsMap renders ui_components in a FlatList"

    app = FastAPI()
    app.include_router(search_router, prefix="/api")
    app.state.storage, app.state.index, app.state.source_manager = storage, index, sources
    client = TestClient(app)

    # every word, any order, ranked
    data = client.get("/api/search", params={"q": "ios devices chromecast"}).json()
    assert [d["id"] for d in data] == ["cast-ios"]
    assert "NSBonjourServices" in data[0]["snippet"]

    # virtual article bodies are searched through the source manager
    data = client.get("/api/search", params={"q": "ComponentsMap"}).json()
    assert [d["id"] for d in data] == ["src:qb-docs/screens"]
    sources.get_article_content.assert_called_with("src:qb-docs/screens")
