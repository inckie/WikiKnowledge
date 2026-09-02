"""Source Code Plugin for parsing :wk-*: and @wk-* annotations from source files."""

import glob
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from wikiknowledge.core.parser import extract_wiki_links
from wikiknowledge.core.plugins.base import KnowledgeSourcePlugin
from wikiknowledge.storage.models import ArticleMeta, ArticleType, WikiLink


class SourceCodePlugin(KnowledgeSourcePlugin):
    """Parses source code files for WikiKnowledge annotations."""

    # Python module-level docstring RST-style tags
    PY_WK_ID_RE = re.compile(r":wk-id:\s*([^\n]+)")
    PY_WK_TAGS_RE = re.compile(r":wk-tags:\s*([^\n]+)")
    PY_WK_CAT_RE = re.compile(r":wk-categories:\s*([^\n]+)")
    PY_WK_TITLE_RE = re.compile(r":wk-title:\s*([^\n]+)")

    # JSDoc / JavaDoc / KDoc-style tags
    JS_WK_ID_RE = re.compile(r"@wk-id\s+([^\n]+)")
    JS_WK_TAGS_RE = re.compile(r"@wk-tags\s+([^\n]+)")
    JS_WK_CAT_RE = re.compile(r"@wk-categories\s+([^\n]+)")
    JS_WK_TITLE_RE = re.compile(r"@wk-title\s+([^\n]+)")

    def __init__(self, source_name: str, kb_name: str = "default"):
        self.source_name = source_name
        self.kb_name = kb_name
        self.config: dict = {}
        self.root_path: Path = Path(".")
        self._articles_meta: dict[str, ArticleMeta] = {}
        self._articles_content: dict[str, str] = {}
        self._links: dict[str, list[WikiLink]] = {}
        self._available = False

    async def initialize(self, config: dict) -> None:
        """Initialize with config containing path and languages."""
        self.config = config
        path_str = config.get("path")
        if not path_str:
            self._available = False
            return
            
        self.root_path = Path(path_str).resolve()
        self._available = self.root_path.exists() and self.root_path.is_dir()
        
    def is_available(self) -> bool:
        return self._available

    async def discover_articles(self) -> list[ArticleMeta]:
        if not self.is_available():
            return []
            
        self._articles_meta.clear()
        self._articles_content.clear()
        self._links.clear()

        languages = self.config.get("languages", {})
        
        for lang, settings in languages.items():
            includes = settings.get("include", [])
            excludes = settings.get("exclude", [])
            
            # Simple globbing, handles includes and excludes
            files_to_check = set()
            for inc in includes:
                matches = self.root_path.glob(inc)
                for m in matches:
                    if m.is_file():
                        files_to_check.add(m)
                        
            for exc in excludes:
                exc_matches = set(self.root_path.glob(exc))
                files_to_check -= exc_matches
                
            respect_gitignore = self.config.get("respect_gitignore", False)
            if respect_gitignore:
                from wikiknowledge.core.plugins.base import is_path_ignored
                gitignore_cache = {}
                filtered_files = set()
                for file_path in files_to_check:
                    if not is_path_ignored(file_path, self.root_path, gitignore_cache):
                        filtered_files.add(file_path)
                files_to_check = filtered_files
                
            for file_path in files_to_check:
                try:
                    self._parse_file(file_path, lang)
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")

        return list(self._articles_meta.values())

    async def get_article_content(self, article_id: str) -> str:
        if article_id not in self._articles_content:
            raise KeyError(f"Article '{article_id}' not found in source '{self.source_name}'")
        return self._articles_content[article_id]

    async def get_links(self) -> dict[str, list[WikiLink]]:
        return self._links

    def _parse_file(self, file_path: Path, lang: str) -> None:
        content = file_path.read_text(encoding="utf-8")
        if not content:
            return

        lang_lower = lang.lower()
        if lang_lower == "python":
            self._parse_python(content, file_path)
        elif lang_lower in ("javascript", "typescript", "js", "ts"):
            self._parse_javascript(content, file_path)
        elif lang_lower in ("java", "kotlin", "kt"):
            self._parse_java_kotlin(content, file_path)

    def _parse_python(self, content: str, file_path: Path) -> None:
        docstring_matches = re.finditer(r'^(\s*)"""(.*?)"""', content, re.DOTALL | re.MULTILINE)
        docstring = None
        for match in docstring_matches:
            candidate = match.group(2)
            if self.PY_WK_ID_RE.search(candidate):
                docstring = candidate
                break

        if not docstring:
            return
            
        id_match = self.PY_WK_ID_RE.search(docstring)
        if not id_match:
            return
            
        module_path = id_match.group(1).strip()
        article_id = f"src:{self.source_name}/{module_path}"
        
        # Title is overridden by :wk-title: or is the first non-empty line
        title_match = self.PY_WK_TITLE_RE.search(docstring)
        if title_match:
            title = title_match.group(1).strip()
        else:
            lines = [l.strip() for l in docstring.split("\n")]
            title = next((l for l in lines if l and not l.startswith(":")), module_path)
        
        # Extract tags and categories
        tags = []
        tags_match = self.PY_WK_TAGS_RE.search(docstring)
        if tags_match:
            tags = [t.strip() for t in tags_match.group(1).split(",") if t.strip()]
            
        categories = []
        cat_match = self.PY_WK_CAT_RE.search(docstring)
        if cat_match:
            categories = [c.strip() for c in cat_match.group(1).split(",") if c.strip()]
            
        # Get stat for modified time
        stat = file_path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        
        # Remove the wk- metadata fields from content
        clean_content = self.PY_WK_ID_RE.sub("", docstring)
        clean_content = self.PY_WK_TAGS_RE.sub("", clean_content)
        clean_content = self.PY_WK_CAT_RE.sub("", clean_content)
        clean_content = self.PY_WK_TITLE_RE.sub("", clean_content)
        
        meta = ArticleMeta(
            id=article_id,
            title=title,
            type=ArticleType.LEAF,
            tags=tags,
            categories=categories,
            created=modified,
            modified=modified
        )
        
        clean_content = clean_content.strip()
        lines = clean_content.split('\n')
        if lines and lines[0].strip() and not lines[0].startswith('#'):
            lines[0] = f"# {lines[0].strip()}"
            
        clean_content = '\n'.join(lines)
        # Rewrite [[src:target]] to [[src:{self.source_name}/target]]
        # This allows source code to link to other files in the same codebase using [[src:module-path]]
        # without needing to hardcode the KB configuration name (source_name).
        clean_content = re.sub(
            r"\[\[src:([^/\]|]+)(\|[^\]]+)?\]\]",
            lambda m: f"[[src:{self.source_name}/{m.group(1)}{m.group(2) or ''}]]",
            clean_content
        )
        rel_path = file_path.relative_to(self.root_path.parent).as_posix() if self.root_path.parent in file_path.parents else file_path.name
        clean_content += f"\n\n---\n🔌 **Source File**: <a href=\"file:///{file_path.resolve().as_posix()}\">{rel_path}</a>"

        self._articles_meta[article_id] = meta
        self._articles_content[article_id] = clean_content
        self._links[article_id] = extract_wiki_links(article_id, clean_content)

    def _parse_javascript(self, content: str, file_path: Path) -> None:
        self._parse_jsdoc_style(content, file_path)

    def _parse_java_kotlin(self, content: str, file_path: Path) -> None:
        self._parse_jsdoc_style(content, file_path)

    def _parse_jsdoc_style(self, content: str, file_path: Path) -> None:
        doc_matches = re.finditer(r'/\*\*(.*?)\*/', content, re.DOTALL)
        docblock = None
        for match in doc_matches:
            candidate = match.group(1)
            if self.JS_WK_ID_RE.search(candidate):
                docblock = candidate
                break

        if not docblock:
            return
            
        id_match = self.JS_WK_ID_RE.search(docblock)
        if not id_match:
            return
            
        module_path = id_match.group(1).strip()
        article_id = f"src:{self.source_name}/{module_path}"
        
        # Clean JSDoc / Javadoc lines (remove * prefix)
        lines = []
        for line in docblock.split("\n"):
            line = line.strip()
            if line.startswith("*"):
                line = line[1:].strip()
            lines.append(line)
            
        clean_doc = "\n".join(lines)
        
        # Title is overridden by @wk-title or is the first line
        title_match = self.JS_WK_TITLE_RE.search(clean_doc)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = next((l for l in lines if l and not l.startswith("@")), module_path)
        
        # Extract tags and categories
        tags = []
        tags_match = self.JS_WK_TAGS_RE.search(clean_doc)
        if tags_match:
            tags = [t.strip() for t in tags_match.group(1).split(",") if t.strip()]
            
        categories = []
        cat_match = self.JS_WK_CAT_RE.search(clean_doc)
        if cat_match:
            categories = [c.strip() for c in cat_match.group(1).split(",") if c.strip()]
            
        # Get stat for modified time
        stat = file_path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        
        # Remove metadata tags
        final_content = self.JS_WK_ID_RE.sub("", clean_doc)
        final_content = self.JS_WK_TAGS_RE.sub("", final_content)
        final_content = self.JS_WK_CAT_RE.sub("", final_content)
        final_content = self.JS_WK_TITLE_RE.sub("", final_content)
        
        meta = ArticleMeta(
            id=article_id,
            title=title,
            type=ArticleType.LEAF,
            tags=tags,
            categories=categories,
            created=modified,
            modified=modified
        )
        
        final_content = final_content.strip()
        lines = final_content.split('\n')
        if lines and lines[0].strip() and not lines[0].startswith('#'):
            lines[0] = f"# {lines[0].strip()}"
            
        final_content = '\n'.join(lines)
        # Rewrite [[src:target]] to [[src:{self.source_name}/target]]
        # This allows source code to link to other files in the same codebase using [[src:module-path]]
        # without needing to hardcode the KB configuration name (source_name).
        final_content = re.sub(
            r"\[\[src:([^/\]|]+)(\|[^\]]+)?\]\]",
            lambda m: f"[[src:{self.source_name}/{m.group(1)}{m.group(2) or ''}]]",
            final_content
        )
        rel_path = file_path.relative_to(self.root_path.parent).as_posix() if self.root_path.parent in file_path.parents else file_path.name
        final_content += f"\n\n---\n🔌 **Source File**: <a href=\"file:///{file_path.resolve().as_posix()}\">{rel_path}</a>"

        self._articles_meta[article_id] = meta
        self._articles_content[article_id] = final_content
        self._links[article_id] = extract_wiki_links(article_id, final_content)