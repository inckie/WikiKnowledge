import asyncio
import fnmatch
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Any, Optional

from wikiknowledge.storage.models import ArticleMeta, WikiLink

PRUNED_DIRECTORIES = frozenset({
    "node_modules", "build", "dist", "Pods", ".gradle",
    "target", "vendor", ".docusaurus", ".next", ".nuxt",
    ".cache", "out", "coverage"
})


def get_optimal_worker_count(max_cap: int = 32) -> int:
    """Calculate optimal worker threads for I/O and file parsing tasks."""
    return min(max_cap, max(4, (os.cpu_count() or 4) * 2))


class KnowledgeSourcePlugin(ABC):
    """Base interface for all knowledge source plugins."""
    
    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Connect to the source and prepare for article discovery."""
        pass
    
    async def discover_articles(self) -> list[ArticleMeta]:
        """Scan the source and return metadata for all discoverable articles.
        
        Default implementation offloads synchronous discovery to a worker thread.
        Plugins with native async I/O can override this directly.
        """
        if not self.is_available():
            return []
        return await asyncio.to_thread(self._discover_articles_sync)

    def _discover_articles_sync(self) -> list[ArticleMeta]:
        """Synchronous discovery logic executed on a background worker thread."""
        raise NotImplementedError
    
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


def collect_source_files(
    root_path: Path | str,
    includes: list[str],
    excludes: Optional[list[str]] = None,
    valid_extensions: Optional[tuple[str, ...] | set[str]] = None,
    respect_gitignore: bool = False,
    gitignore_cache: Optional[dict] = None,
) -> list[Path]:
    """Efficiently collect files matching includes and not in excludes under root_path.

    Uses a fast single-pass os.walk when all include patterns are recursive extensions
    (e.g., '**/*.ts' or './**/*.md'), pruning well-known build and dependency folders.
    Falls back to Path.glob for arbitrary or complex patterns.
    """
    root_path = Path(root_path).resolve()
    excludes = excludes or []

    can_fast_walk = bool(includes) and all(
        inc.startswith("**/") or inc.startswith("./**/")
        for inc in includes
    )

    if can_fast_walk:
        fast_patterns = [inc.split("**/")[-1] for inc in includes]
        matched: set[Path] = set()
        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in PRUNED_DIRECTORIES
            ]
            for pat in fast_patterns:
                for f in fnmatch.filter(filenames, pat):
                    fp = Path(dirpath) / f
                    if valid_extensions:
                        if fp.suffix.lower() in valid_extensions:
                            matched.add(fp.resolve())
                    else:
                        matched.add(fp.resolve())
    else:
        matched = set()
        for pattern in includes:
            for path in root_path.glob(pattern):
                if path.is_file():
                    if valid_extensions:
                        if path.suffix.lower() in valid_extensions:
                            matched.add(path.resolve())
                    else:
                        matched.add(path.resolve())

    if excludes:
        for exc in excludes:
            matched -= {p.resolve() for p in root_path.glob(exc)}

    if respect_gitignore:
        gi_cache = gitignore_cache if gitignore_cache is not None else {}
        matched = {f for f in matched if not is_path_ignored(f, root_path, gi_cache)}

    return sorted(matched)


def is_path_ignored(file_path: Any, root_path: Any, gitignore_cache: dict) -> bool:
    """Check if a file or directory is ignored by any .gitignore file in its lineage."""
    from pathlib import Path
    fp = Path(file_path)
    rp = Path(root_path)

    parent = fp if fp.is_dir() else fp.parent

    # Fast check: parent directory already known to be ignored
    if gitignore_cache.get(("ignored_dir", parent)) is True:
        return True

    # Build lineage from root down to parent
    lineage = []
    curr = parent
    while curr != rp and rp in curr.parents:
        lineage.append(curr)
        curr = curr.parent
    lineage.append(rp)
    lineage.reverse()  # root_path first

    # Check if any ancestor is already known to be ignored
    for p in lineage:
        if gitignore_cache.get(("ignored_dir", p)) is True:
            gitignore_cache[("ignored_dir", parent)] = True
            return True

    # Evaluate pathspecs down the lineage
    for p in lineage:
        spec_key = ("spec", p)
        if spec_key not in gitignore_cache:
            # Also support legacy direct path key if present
            if p in gitignore_cache:
                gitignore_cache[spec_key] = gitignore_cache[p]
            else:
                ignore_file = p / ".gitignore"
                if ignore_file.is_file():
                    try:
                        import pathspec
                        with open(ignore_file, "r", encoding="utf-8") as f:
                            gitignore_cache[spec_key] = pathspec.PathSpec.from_lines("gitwildmatch", f)
                    except Exception:
                        gitignore_cache[spec_key] = None
                else:
                    gitignore_cache[spec_key] = None

        spec = gitignore_cache.get(spec_key)
        if spec:
            try:
                rel_to_p = str(fp.relative_to(p)).replace("\\", "/")
                if spec.match_file(rel_to_p):
                    gitignore_cache[("ignored_dir", parent)] = True
                    return True
            except ValueError:
                pass

    return False