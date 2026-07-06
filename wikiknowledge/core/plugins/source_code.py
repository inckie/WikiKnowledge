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

    # JavaScript JSDoc-style tags
    JS_WK_ID_RE = re.compile(r"@wk-id\s+([^\n]+)")
    JS_WK_TAGS_RE = re.compile(r"@wk-tags\s+([^\n]+)")
    JS_WK_CAT_RE = re.compile(r"@wk-categories\s+([^\n]+)")

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
            
            # Simple globbing, could be improved to handle complex excludes
            files_to_check = set()
            for inc in includes:
                # Use recursive glob
                matches = self.root_path.glob(inc)
                for m in matches:
                    if m.is_file():
                        files_to_check.add(m)
                        
            # Naive exclude processing
            for exc in excludes:
                exc_matches = set(self.root_path.glob(exc))
                files_to_check -= exc_matches
                
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

        if lang == "python":
            self._parse_python(content, file_path)
        elif lang == "javascript":
            self._parse_javascript(content, file_path)

    def _parse_python(self, content: str, file_path: Path) -> None:
        # Very simple docstring extraction (first """ block)
        docstring_match = re.search(r'^(\s*)"""(.*?)"""', content, re.DOTALL | re.MULTILINE)
        if not docstring_match:
            return
            
        docstring = docstring_match.group(2)
        
        # Check for wk-id
        id_match = self.PY_WK_ID_RE.search(docstring)
        if not id_match:
            return
            
        module_path = id_match.group(1).strip()
        article_id = f"src:{self.source_name}/{module_path}"
        
        # Title is the first line of the docstring (ignoring empty lines)
        lines = [l.strip() for l in docstring.split("\n")]
        title = next((l for l in lines if l), module_path)
        
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
        rel_path = file_path.relative_to(self.root_path.parent).as_posix() if self.root_path.parent in file_path.parents else file_path.name
        clean_content += f"\n\n---\n🔌 **Source File**: <a href=\"file:///{file_path.resolve().as_posix()}\">{rel_path}</a>"

        self._articles_meta[article_id] = meta
        self._articles_content[article_id] = clean_content
        self._links[article_id] = extract_wiki_links(article_id, clean_content)

    def _parse_javascript(self, content: str, file_path: Path) -> None:
        # Simple JSDoc block extraction
        jsdoc_match = re.search(r'/\*\*(.*?)\*/', content, re.DOTALL)
        if not jsdoc_match:
            return
            
        jsdoc = jsdoc_match.group(1)
        
        # Check for wk-id
        id_match = self.JS_WK_ID_RE.search(jsdoc)
        if not id_match:
            return
            
        module_path = id_match.group(1).strip()
        article_id = f"src:{self.source_name}/{module_path}"
        
        # Clean JSDoc lines (remove * prefix)
        lines = []
        for line in jsdoc.split("\n"):
            line = line.strip()
            if line.startswith("*"):
                line = line[1:].strip()
            lines.append(line)
            
        clean_jsdoc = "\n".join(lines)
        
        # Title is the first line
        title = next((l for l in lines if l), module_path)
        
        # Extract tags and categories
        tags = []
        tags_match = self.JS_WK_TAGS_RE.search(clean_jsdoc)
        if tags_match:
            tags = [t.strip() for t in tags_match.group(1).split(",") if t.strip()]
            
        categories = []
        cat_match = self.JS_WK_CAT_RE.search(clean_jsdoc)
        if cat_match:
            categories = [c.strip() for c in cat_match.group(1).split(",") if c.strip()]
            
        # Get stat for modified time
        stat = file_path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        
        # Remove metadata tags
        final_content = self.JS_WK_ID_RE.sub("", clean_jsdoc)
        final_content = self.JS_WK_TAGS_RE.sub("", final_content)
        final_content = self.JS_WK_CAT_RE.sub("", final_content)
        
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
        rel_path = file_path.relative_to(self.root_path.parent).as_posix() if self.root_path.parent in file_path.parents else file_path.name
        final_content += f"\n\n---\n🔌 **Source File**: <a href=\"file:///{file_path.resolve().as_posix()}\">{rel_path}</a>"

        self._articles_meta[article_id] = meta
        self._articles_content[article_id] = final_content
        self._links[article_id] = extract_wiki_links(article_id, final_content)