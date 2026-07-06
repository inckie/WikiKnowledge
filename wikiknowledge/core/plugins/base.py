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