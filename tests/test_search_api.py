from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from wikiknowledge.api.search import router as search_router
from wikiknowledge.storage.models import Article, ArticleMeta, ArticleType, SourceType


def test_search_ranks_native_and_virtual_articles():
    metas = {
        "cast-ios": ArticleMeta(id="cast-ios", title="Chromecast on iOS", type=ArticleType.LEAF, tags=["chromecast"]),
        "cast-arch": ArticleMeta(id="cast-arch", title="Chromecast architecture", type=ArticleType.LEAF),
        "src:qb-docs/screens": ArticleMeta(
            id="src:qb-docs/screens",
            title="Screens",
            type=ArticleType.LEAF,
            source_type=SourceType.MARKDOWN,
        ),
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
    assert data[0]["source_type"] == "native"
    assert "NSBonjourServices" in data[0]["snippet"]

    # virtual article bodies are searched through the source manager
    data = client.get("/api/search", params={"q": "ComponentsMap"}).json()
    assert [d["id"] for d in data] == ["src:qb-docs/screens"]
    assert data[0]["source_type"] == "markdown"
    sources.get_article_content.assert_called_with("src:qb-docs/screens")


def test_search_hybrid_and_semantic_include_source_type():
    metas = {
        "cast-ios": ArticleMeta(id="cast-ios", title="Chromecast on iOS", type=ArticleType.LEAF),
        "src:repo/engine": ArticleMeta(
            id="src:repo/engine",
            title="Engine",
            type=ArticleType.LEAF,
            source_type=SourceType.CODE,
        ),
    }
    bodies = {
        "cast-ios": "Chromecast playback receiver",
        "src:repo/engine": "Playback controller",
    }

    storage = AsyncMock()
    storage.get_article.side_effect = lambda i: Article(meta=metas[i], content=bodies[i])
    index = MagicMock()
    index._all_meta = metas
    index.get_meta.side_effect = metas.get
    sources = AsyncMock()
    sources.get_article_content.side_effect = lambda i: bodies[i]

    embedding_service = MagicMock()
    embedding_service.enabled = True
    embedding_service.status = "ready"
    embedding_service.search.return_value = [
        {
            "id": "src:repo/engine",
            "title": "Engine",
            "type": "leaf",
            "tags": [],
            "score": 0.9,
            "snippet": "Playback controller",
        },
        {
            "id": "cast-ios",
            "title": "Chromecast on iOS",
            "type": "leaf",
            "tags": [],
            "score": 0.7,
            "snippet": "Chromecast playback receiver",
        },
    ]

    app = FastAPI()
    app.include_router(search_router, prefix="/api")
    app.state.storage = storage
    app.state.index = index
    app.state.source_manager = sources
    app.state.embedding_service = embedding_service
    client = TestClient(app)

    data = client.get("/api/search", params={"q": "receiver"}).json()
    by_id = {d["id"]: d for d in data}
    assert by_id["cast-ios"]["match_type"] == "hybrid"
    assert by_id["cast-ios"]["source_type"] == "native"
    assert by_id["src:repo/engine"]["match_type"] == "semantic"
    assert by_id["src:repo/engine"]["source_type"] == "code"
