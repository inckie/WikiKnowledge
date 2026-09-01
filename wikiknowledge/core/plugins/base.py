"""Base interface for Knowledge Source plugins."""

from abc import ABC, abstractmethod
from typing import Callable, Any, Optional

from wikiknowledge.storage.models import ArticleMeta, WikiLink


class KnowledgeSourcePlugin(ABC):
    """Base interface for all knowledge source plugins."""
    
    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Connect to the source and prepare for article discovery."""
        pass
    
    @abstractmethod
    async def discover_articles(self) -> list[ArticleMeta]:
        """Scan the source and return metadata for all discoverable articles."""
        pass
    
    @abstractmethod
    async def get_article_content(self, article_id: str) -> str:
        """Read the full content of a virtual article."""
        pass
    
    @abstractmethod
    async def get_links(self) -> dict[str, list[WikiLink]]:
        """Extract all wiki links from all virtual articles."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the source is currently reachable."""
        pass
    
    async def on_change(self, callback: Callable) -> None:
        """Optional: register a file-watcher callback for live updates."""
        pass


def is_path_ignored(file_path: __import__('pathlib').Path, root_path: __import__('pathlib').Path, gitignore_cache: dict) -> bool:
    """Check if a file is ignored by any .gitignore file in its lineage."""
    ignored = False
    
    # We walk from root down to the file's parent
    parents = list(file_path.parents)
    # filter to only those under root_path, plus root_path
    rel_parents = [p for p in parents if root_path in p.parents]
    if root_path not in rel_parents:
        rel_parents.append(root_path)
    rel_parents.reverse() # root first
    
    for p in rel_parents:
        if p not in gitignore_cache:
            ignore_file = p / ".gitignore"
            if ignore_file.is_file():
                try:
                    import pathspec
                    with open(ignore_file, "r", encoding="utf-8") as f:
                        gitignore_cache[p] = pathspec.PathSpec.from_lines("gitwildmatch", f)
                except Exception:
                    gitignore_cache[p] = None
            else:
                gitignore_cache[p] = None
                
        spec = gitignore_cache[p]
        if spec:
            rel_to_p = str(file_path.relative_to(p))
            if spec.match_file(rel_to_p):
                ignored = True
                
    return ignored