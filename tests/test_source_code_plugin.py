"""
Unit tests for SourceCodePlugin with Python, JavaScript, TypeScript, Java, Kotlin
and Swift support.

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

    # Swift files. Swift documents with `///` runs, not `/** */` blocks.
    swift_dir = root / "src" / "swift"
    swift_dir.mkdir(parents=True)
    (swift_dir / "RestTimer.swift").write_text(
        'import Foundation\n\n'
        '// MARK: ─────────────────────────────────────\n'
        '//// a separator, not documentation\n\n'
        '/// The rest between sets, counted down.\n'
        '///\n'
        '/// @wk-id timers/rest\n'
        '/// @wk-tags swift, timer\n'
        '/// @wk-categories client-layer\n'
        '///\n'
        '/// The clock the Lock Screen shows. See [[activity-attributes]].\n'
        'public struct RestTimer {}\n',
        encoding="utf-8",
    )
    (swift_dir / "Palette.swift").write_text(
        'import SwiftUI\n\n'
        '/**\n'
        ' * The palette, carried over unchanged.\n'
        ' *\n'
        ' * @wk-id design/palette\n'
        ' * @wk-tags swift, design\n'
        ' * @wk-categories client-layer\n'
        ' * @wk-title Colour Palette\n'
        ' */\n'
        'public extension Color {}\n',
        encoding="utf-8",
    )
    (swift_dir / "Untagged.swift").write_text(
        '/// A well documented type that opts out of the knowledge graph.\n'
        '///\n'
        '/// Plenty of prose, no directives.\n'
        'public struct Untagged {}\n',
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


@pytest.mark.asyncio
async def test_swift_line_doc_comments_become_articles(src_root: Path):
    plugin = await _build_plugin(src_root, {"swift": {"include": ["src/swift/**/*.swift"]}})

    meta = plugin._articles_meta["src:myproject/timers/rest"]
    assert meta.title == "The rest between sets, counted down."
    assert meta.tags == ["swift", "timer"]
    assert meta.categories == ["client-layer"]


@pytest.mark.asyncio
async def test_swift_block_doc_comments_also_work(src_root: Path):
    plugin = await _build_plugin(src_root, {"swift": {"include": ["src/swift/**/*.swift"]}})

    meta = plugin._articles_meta["src:myproject/design/palette"]
    assert meta.title == "Colour Palette"


@pytest.mark.asyncio
async def test_swift_file_without_directives_is_not_an_article(src_root: Path):
    plugin = await _build_plugin(src_root, {"swift": {"include": ["src/swift/**/*.swift"]}})

    assert not [i for i in plugin._articles_meta if "untagged" in i.lower()]


@pytest.mark.asyncio
async def test_swift_separators_do_not_hide_the_real_doc_comment(src_root: Path):
    """`// MARK:` rules and //// separators sit above the doc comment in real files."""
    plugin = await _build_plugin(src_root, {"swift": {"include": ["src/swift/**/*.swift"]}})

    content = plugin._articles_content["src:myproject/timers/rest"]
    assert "separator, not documentation" not in content
    assert "The clock the Lock Screen shows" in content


@pytest.mark.asyncio
async def test_swift_wiki_links_are_extracted(src_root: Path):
    plugin = await _build_plugin(src_root, {"swift": {"include": ["src/swift/**/*.swift"]}})

    targets = [l.target_id for l in plugin._links["src:myproject/timers/rest"]]
    assert "activity-attributes" in targets


@pytest.mark.asyncio
async def test_swift_directives_are_stripped_from_the_body(src_root: Path):
    plugin = await _build_plugin(src_root, {"swift": {"include": ["src/swift/**/*.swift"]}})

    content = plugin._articles_content["src:myproject/timers/rest"]
    assert "@wk-id" not in content and "@wk-tags" not in content


@pytest.mark.asyncio
async def test_stripped_directives_leave_no_gap_in_the_body(src_root: Path):
    """Each removed @wk- line used to leave its blank line behind, stacking up
    into a hole between the title and the first paragraph."""
    plugin = await _build_plugin(
        src_root,
        {
            "python": {"include": ["src/py/**/*.py"]},
            "java": {"include": ["src/java/**/*.java"]},
            "swift": {"include": ["src/swift/**/*.swift"]},
        },
    )

    for article_id in (
        "src:myproject/backend/py-service",
        "src:myproject/auth/manager",
        "src:myproject/timers/rest",
    ):
        assert "\n\n\n" not in plugin._articles_content[article_id], article_id
