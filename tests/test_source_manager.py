import json
from pathlib import Path
import pytest

from wikiknowledge.core.plugins.manager import SourceManager


@pytest.fixture
def kb_with_sources(tmp_path: Path) -> Path:
    kb_dir = tmp_path / "knowledge"
    kb_dir.mkdir(parents=True)
    
    # Create external source dirs
    ext_dir = tmp_path / "external_src"
    ext_dir.mkdir(parents=True)
    (ext_dir / "test.py").write_text("# :wk-id: test\n", encoding="utf-8")

    alt_dir = tmp_path / "alt_src"
    alt_dir.mkdir(parents=True)

    sources_config = {
        "sources": {
            "test-code": {
                "type": "source-code",
                "default_path": "../external_src",
                "knowledge_bases": {
                    "default": "self"
                },
                "languages": {
                    "python": {"include": ["**/*.py"]}
                }
            }
        }
    }
    (kb_dir / "sources.json").write_text(json.dumps(sources_config), encoding="utf-8")
    return kb_dir


@pytest.mark.asyncio
async def test_update_source_path_reflects_in_status_and_persists(kb_with_sources: Path):
    mgr = SourceManager(kb_with_sources)
    await mgr.initialize()

    # Initial status
    status = mgr.get_status()
    assert len(status) == 1
    src = status[0]
    assert src["id"] == "test-code"
    assert src["available"] is True
    initial_path = src["path"]

    # Update path to a new directory
    alt_dir = (kb_with_sources.parent / "alt_src").resolve()
    mgr.update_source_path("test-code", str(alt_dir))

    # Verify status reflects new path immediately
    status_updated = mgr.get_status()
    src_updated = status_updated[0]
    assert src_updated["path"] == str(alt_dir)
    assert src_updated["available"] is True

    # Verify persisted to .settings/sources.json
    settings_file = kb_with_sources / ".settings" / "sources.json"
    assert settings_file.exists()
    settings_data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert settings_data["test-code"]["path"] == str(alt_dir)

    # Re-initialize to simulate restart
    mgr2 = SourceManager(kb_with_sources)
    await mgr2.initialize()
    status_restarted = mgr2.get_status()
    assert status_restarted[0]["path"] == str(alt_dir)


@pytest.mark.asyncio
async def test_update_source_path_revert_to_default(kb_with_sources: Path):
    mgr = SourceManager(kb_with_sources)
    await mgr.initialize()

    initial_path = mgr.get_status()[0]["path"]

    # Set custom override
    alt_dir = (kb_with_sources.parent / "alt_src").resolve()
    mgr.update_source_path("test-code", str(alt_dir))
    assert mgr.get_status()[0]["path"] == str(alt_dir)

    # Clear override (empty string)
    mgr.update_source_path("test-code", "")
    assert mgr.get_status()[0]["path"] == initial_path

    # Verify .settings/sources.json has removed the path
    settings_file = kb_with_sources / ".settings" / "sources.json"
    settings_data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "test-code" not in settings_data or "path" not in settings_data.get("test-code", {})


@pytest.mark.asyncio
async def test_update_source_path_clears_cached_articles(kb_with_sources: Path):
    mgr = SourceManager(kb_with_sources)
    await mgr.initialize()

    plugin = mgr.plugins["test-code"]
    plugin._articles_meta["dummy"] = "dummy_val"
    plugin._articles_content["dummy"] = "dummy_content"

    # Update path
    alt_dir = (kb_with_sources.parent / "alt_src").resolve()
    mgr.update_source_path("test-code", str(alt_dir))

    assert len(plugin._articles_meta) == 0
    assert len(plugin._articles_content) == 0


@pytest.mark.asyncio
async def test_update_source_path_invalid_source_raises(kb_with_sources: Path):
    mgr = SourceManager(kb_with_sources)
    await mgr.initialize()

    with pytest.raises(KeyError):
        mgr.update_source_path("nonexistent", "/some/path")


@pytest.mark.asyncio
async def test_update_source_path_strips_quotes_and_resolves_relative_to_kb(kb_with_sources: Path):
    alt_dir = (kb_with_sources.parent / "alt_src").resolve()
    (alt_dir / "alt.py").write_text('"""Alt\n:wk-id: alt\n"""\n', encoding="utf-8")

    mgr = SourceManager(kb_with_sources)
    await mgr.initialize()

    # Surrounding quotes (e.g. Windows Copy as path) and relative path should resolve cleanly
    mgr.update_source_path("test-code", '"../alt_src"')
    status = mgr.get_status()[0]
    assert status["path"] == str(alt_dir)
    assert status["available"] is True

    # Re-initializing from .settings/sources.json keeps resolving relative to kb_dir
    mgr2 = SourceManager(kb_with_sources)
    await mgr2.initialize()
    assert mgr2.get_status()[0]["path"] == str(alt_dir)
    assert mgr2.get_status()[0]["available"] is True


@pytest.mark.asyncio
async def test_put_source_path_endpoint_saves_and_rebuilds_index(kb_with_sources: Path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from wikiknowledge.api.sources import router as sources_router
    from wikiknowledge.core.index import KnowledgeIndex, rebuild_full_index
    from wikiknowledge.storage.markdown_backend import MarkdownStorageBackend

    ext_dir = (kb_with_sources.parent / "external_src").resolve()
    (ext_dir / "orig_mod.py").write_text('"""Orig Mod\n:wk-id: orig-mod\n"""\n', encoding="utf-8")

    alt_dir = (kb_with_sources.parent / "alt_src").resolve()
    (alt_dir / "new_mod.py").write_text('"""New Mod\n:wk-id: new-mod\n"""\n', encoding="utf-8")

    storage = MarkdownStorageBackend(kb_with_sources)
    await storage.initialize()
    index = KnowledgeIndex()
    mgr = SourceManager(kb_with_sources)
    await mgr.initialize()
    await rebuild_full_index(index, storage, mgr)

    assert "src:test-code/orig-mod" in index._all_meta
    assert "src:test-code/new-mod" not in index._all_meta

    app = FastAPI()
    app.include_router(sources_router, prefix="/api")
    app.state.storage = storage
    app.state.index = index
    app.state.source_manager = mgr

    client = TestClient(app)
    resp = client.put("/api/sources/test-code/path", json={"path": str(alt_dir)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["path"] == str(alt_dir)
    assert data["available"] is True
    assert data["virtual_articles_discovered"] == 1
    assert data["source"]["path"] == str(alt_dir)
    assert data["source"]["available"] is True

    # Index is rebuilt right away with articles from the new path
    assert "src:test-code/orig-mod" not in index._all_meta
    assert "src:test-code/new-mod" in index._all_meta

    # Missing directory reports available=False while persisting
    missing = kb_with_sources.parent / "does_not_exist"
    resp_missing = client.put("/api/sources/test-code/path", json={"path": str(missing)})
    assert resp_missing.status_code == 200
    data_missing = resp_missing.json()
    assert data_missing["available"] is False
    assert data_missing["virtual_articles_discovered"] == 0
    assert data_missing["source"]["available"] is False
