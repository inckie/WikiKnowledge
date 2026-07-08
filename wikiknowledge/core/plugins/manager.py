"""SourceManager for handling Knowledge Source plugins and config."""

import json
from pathlib import Path
from typing import Optional

from wikiknowledge.core.plugins.base import KnowledgeSourcePlugin
from wikiknowledge.core.plugins.source_code import SourceCodePlugin
from wikiknowledge.storage.models import ArticleMeta, WikiLink


class SourceManager:
    def __init__(self, kb_dir: Path | str, current_kb_name: str = "default"):
        self.kb_dir = Path(kb_dir)
        self.current_kb_name = current_kb_name
        self.sources_file = self.kb_dir / "sources.json"
        self.settings_file = self.kb_dir / ".settings" / "sources.json"
        
        self.plugins: dict[str, KnowledgeSourcePlugin] = {}

    async def initialize(self) -> None:
        """Load configurations and initialize all plugins."""
        self.plugins.clear()
        
        if not self.sources_file.exists():
            return
            
        try:
            with open(self.sources_file, "r", encoding="utf-8") as f:
                declarations = json.load(f).get("sources", {})
        except Exception as e:
            print(f"Error reading {self.sources_file}: {e}")
            return
            
        settings = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception as e:
                print(f"Error reading {self.settings_file}: {e}")

        for source_name, decl in declarations.items():
            # Check if this source connects to the current KB
            kbs = decl.get("knowledge_bases", {"default": "self"})
            kb_alias = None
            for alias, target in kbs.items():
                if target == "self" or alias == self.current_kb_name:
                    kb_alias = alias
                    break
                    
            if not kb_alias:
                continue # Source doesn't connect to this KB
                
            plugin_type = decl.get("type")
            source_settings = settings.get(source_name, {})

            if plugin_type == "source-code":
                plugin = SourceCodePlugin(source_name, kb_alias)
                
                # Resolve path
                actual_path = source_settings.get("path")
                if not actual_path and decl.get("default_path"):
                    actual_path = (self.kb_dir / decl["default_path"]).resolve()
                    
                decl["path"] = str(actual_path) if actual_path else None
                
                await plugin.initialize(decl)
                self.plugins[source_name] = plugin

            elif plugin_type == "google-drive":
                # Import lazily to avoid hard dependency if not configured
                from wikiknowledge.core.plugins.google_drive import GoogleDrivePlugin

                plugin = GoogleDrivePlugin(source_name, kb_alias, kb_dir=self.kb_dir)

                # Inject credentials path from machine-local settings
                credentials_file = source_settings.get("credentials_file")
                decl["credentials_file"] = credentials_file

                await plugin.initialize(decl)
                self.plugins[source_name] = plugin

            else:
                print(f"Unknown plugin type '{plugin_type}' for source '{source_name}'")

    async def discover_all_articles(self) -> list[ArticleMeta]:
        """Aggregate discover_articles from all available plugins."""
        all_meta = []
        for plugin in self.plugins.values():
            if plugin.is_available():
                meta_list = await plugin.discover_articles()
                all_meta.extend(meta_list)
        return all_meta

    async def get_all_links(self) -> dict[str, list[WikiLink]]:
        """Aggregate get_links from all available plugins."""
        all_links = {}
        for plugin in self.plugins.values():
            if plugin.is_available():
                links = await plugin.get_links()
                all_links.update(links)
        return all_links

    async def get_article_content(self, article_id: str) -> str:
        """Route to the appropriate plugin to get content."""
        if article_id.startswith("gdrive:"):
            # Route to the Google Drive plugin that owns this doc
            from wikiknowledge.core.plugins.google_drive import GoogleDrivePlugin

            for plugin in self.plugins.values():
                if isinstance(plugin, GoogleDrivePlugin) and plugin.is_available():
                    if plugin.has_article(article_id):
                        return await plugin.get_article_content(article_id)
            raise KeyError(f"Google Drive article '{article_id}' not found in any source")

        elif article_id.startswith("src:"):
            # ID format: src:source_name/module_path
            parts = article_id[4:].split("/", 1)
            if len(parts) < 2:
                raise ValueError(f"Invalid virtual article ID: {article_id}")
                
            source_name = parts[0]
            if source_name not in self.plugins:
                raise KeyError(f"Source '{source_name}' not configured")
                
            plugin = self.plugins[source_name]
            if not plugin.is_available():
                raise KeyError(f"Source '{source_name}' is currently disconnected")
                
            return await plugin.get_article_content(article_id)

        else:
            raise ValueError(f"Not a virtual article ID: {article_id}")

    async def sync_all(self) -> dict[str, dict]:
        """
        Run sync() on all plugins that support it (e.g. Google Drive).
        Returns a dict of source_name -> sync stats.
        """
        from wikiknowledge.core.plugins.google_drive import GoogleDrivePlugin

        results = {}
        for source_name, plugin in self.plugins.items():
            if isinstance(plugin, GoogleDrivePlugin) and plugin.is_available():
                try:
                    stats = await plugin.sync()
                    results[source_name] = stats
                except Exception as exc:
                    results[source_name] = {"error": str(exc)}
        return results

    def get_status(self) -> list[dict]:
        """Return the current status of all discovered sources."""
        from wikiknowledge.core.plugins.google_drive import GoogleDrivePlugin

        status_list = []
        for name, plugin in self.plugins.items():
            entry: dict = {
                "id": name,
                "type": plugin.__class__.__name__,
                "available": plugin.is_available(),
            }
            if hasattr(plugin, "root_path"):
                entry["path"] = str(plugin.root_path)
            if isinstance(plugin, GoogleDrivePlugin):
                entry["folder_id"] = plugin.config.get("folder_id")
                entry["bidirectional"] = plugin.config.get("bidirectional", False)
                # Include last_sync from manifest if available
                try:
                    manifest = plugin._read_manifest()
                    entry["last_sync"] = manifest.get("last_sync")
                    entry["article_count"] = len(manifest.get("articles", {}))
                    entry["sync_status"] = manifest.get("sync_status")
                except Exception:
                    pass
            status_list.append(entry)
        return status_list

    def update_source_path(self, source_id: str, new_path: str) -> None:
        """Update the local path for a source in .settings/sources.json."""
        if source_id not in self.plugins:
            raise KeyError(f"Source '{source_id}' is not a declared source.")

        settings = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}

        if source_id not in settings:
            settings[source_id] = {}
            
        settings[source_id]["path"] = new_path
        
        # Ensure parent exists
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)