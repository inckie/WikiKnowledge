"""
Unit tests for SourceCodePlugin with Python, JavaScript, TypeScript, Java, and Kotlin support.

Run with: uv run pytest tests/test_source_code_plugin.py -v
"""

from __future__ import annotations

from pathlib import Path
import pytest

from wikiknowledge.core.plugins.source_code import SourceCodePlugin


@pytest.fixture
def src_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    
    # Python file
    py_dir = root / "src" / "py"
    py_dir.mkdir(parents=True)
    (py_dir / "service.py").write_text(
        '"""Python Backend Service.\n\n'
        ':wk-id: backend/py-service\n'
        ':wk-tags: python, backend, core\n'
        ':wk-categories: backend-layer\n\n'
        'Implements core backend services. See [[database-schema]].\n'
        '"""\n\n'
        'def run():\n    pass\n',
        encoding="utf-8",
    )

    # JavaScript file
    js_dir = root / "src" / "js"
    js_dir.mkdir(parents=True)
    (js_dir / "controller.js").write_text(
        '/**\n'
        ' * Main UI Controller.\n'
        ' *\n'
        ' * @wk-id frontend/controller\n'
        ' * @wk-tags js, ui\n'
        ' * @wk-categories frontend-layer\n'
        ' *\n'
        ' * Manages UI event dispatching.\n'
        ' */\n\n'
        'export function init() {}\n',
        encoding="utf-8",
    )

    # Java file (with license header and Javadoc)
    java_dir = root / "src" / "java" / "com" / "example"
    java_dir.mkdir(parents=True)
    (java_dir / "AuthManager.java").write_text(
        '/*\n'
        ' * Copyright 2026 Example Corp.\n'
        ' */\n\n'
        'package com.example;\n\n'
        '/**\n'
        ' * Authentication Manager.\n'
        ' *\n'
        ' * @wk-id auth/manager\n'
        ' * @wk-tags java, auth, security\n'
        ' * @wk-categories security-layer\n'
        ' * @wk-title Auth Manager Service\n'
        ' *\n'
        ' * Handles user authentication tokens and SSO integration.\n'
        ' * See [[security-guidelines]] for policy details.\n'
        ' */\n'
        'public class AuthManager {\n'
        '    public void authenticate() {}\n'
        '}\n',
        encoding="utf-8",
    )

    # Kotlin file
    kt_dir = root / "src" / "kotlin" / "com" / "example"
    kt_dir.mkdir(parents=True)
    (kt_dir / "UserRepository.kt").write_text(
        'package com.example\n\n'
        '/**\n'
        ' * User Account Repository.\n'
        ' *\n'
        ' * @wk-id data/user-repo\n'
        ' * @wk-tags kotlin, database, users\n'
        ' * @wk-categories data-layer\n'
        ' *\n'
        ' * CRUD repository implementation for user records.\n'
        ' */\n'
        'class UserRepository {\n'
        '    fun findById(id: String) = null\n'
        '}\n',
        encoding="utf-8",
    )

    # Non-annotated file (should be ignored)
    (java_dir / "Utils.java").write_text(
        'package com.example;\n\n'
        'public class Utils {}\n',
        encoding="utf-8",
    )

    return root


async def _build_plugin(root: Path, languages: dict) -> SourceCodePlugin:
    plugin = SourceCodePlugin("myproject")
    await plugin.initialize({"path": str(root), "languages": languages})
    await plugin.discover_articles()
    return plugin


@pytest.mark.asyncio
async def test_discover_python_and_javascript(src_root: Path):
    plugin = await _build_plugin(
        src_root,
        {
            "python": {"include": ["src/py/**/*.py"]},
            "javascript": {"include": ["src/js/**/*.js"]},
        },
    )

    ids = set(plugin._articles_meta)
    assert "src:myproject/backend/py-service" in ids
    assert "src:myproject/frontend/controller" in ids

    py_meta = plugin._articles_meta["src:myproject/backend/py-service"]
    assert py_meta.title == "Python Backend Service."
    assert "python" in py_meta.tags
    assert py_meta.categories == ["backend-layer"]


@pytest.mark.asyncio
async def test_discover_java(src_root: Path):
    plugin = await _build_plugin(
        src_root,
        {
            "java": {"include": ["src/java/**/*.java"]},
        },
    )

    ids = set(plugin._articles_meta)
    assert "src:myproject/auth/manager" in ids
    # Utils.java is not annotated
    assert len(ids) == 1

    java_meta = plugin._articles_meta["src:myproject/auth/manager"]
    assert java_meta.title == "Auth Manager Service"
    assert java_meta.tags == ["java", "auth", "security"]
    assert java_meta.categories == ["security-layer"]

    content = await plugin.get_article_content("src:myproject/auth/manager")
    assert "Handles user authentication tokens" in content
    assert "[[security-guidelines]]" in content
    assert "AuthManager.java" in content


@pytest.mark.asyncio
async def test_discover_kotlin(src_root: Path):
    plugin = await _build_plugin(
        src_root,
        {
            "kotlin": {"include": ["src/kotlin/**/*.kt"]},
        },
    )

    ids = set(plugin._articles_meta)
    assert "src:myproject/data/user-repo" in ids

    kt_meta = plugin._articles_meta["src:myproject/data/user-repo"]
    assert kt_meta.title == "User Account Repository."
    assert "kotlin" in kt_meta.tags
    assert kt_meta.categories == ["data-layer"]

    content = await plugin.get_article_content("src:myproject/data/user-repo")
    assert "CRUD repository implementation" in content
    assert "UserRepository.kt" in content


@pytest.mark.asyncio
async def test_links_extracted_across_languages(src_root: Path):
    plugin = await _build_plugin(
        src_root,
        {
            "python": {"include": ["src/py/**/*.py"]},
            "java": {"include": ["src/java/**/*.java"]},
        },
    )

    links = await plugin.get_links()
    py_links = [l.target_id for l in links.get("src:myproject/backend/py-service", [])]
    assert "database-schema" in py_links

    java_links = [l.target_id for l in links.get("src:myproject/auth/manager", [])]
    assert "security-guidelines" in java_links


@pytest.mark.asyncio
async def test_missing_path_unavailable(tmp_path: Path):
    plugin = SourceCodePlugin("myproject")
    await plugin.initialize({"path": str(tmp_path / "non_existent")})
    assert plugin.is_available() is False
    assert await plugin.discover_articles() == []
