"""Refactoring Operations

:wk-id: refactoring
:wk-tags: python, refactor, operations
:wk-categories: system-architecture

Core operations for refactoring/renaming articles and resources across the knowledge base.

Global rename operations with cross-article link updates.
"""

import re

async def rename_article(storage, index, old_id: str, new_id: str, updates: dict = None, update_links: bool = True):
    """Rename an article and optionally update all references to it."""
    existing = await storage.get_article(old_id)
    
    try:
        await storage.get_article(new_id)
        raise ValueError(f"Article '{new_id}' already exists")
    except KeyError:
        pass
        
    existing.meta.id = new_id
    if updates:
        if "title" in updates and updates["title"] is not None:
            existing.meta.title = updates["title"]
        if "type" in updates and updates["type"] is not None:
            from wikiknowledge.storage.models import ArticleType
            existing.meta.type = ArticleType(updates["type"])
        if "tags" in updates and updates["tags"] is not None:
            existing.meta.tags = updates["tags"]
        if "categories" in updates and updates["categories"] is not None:
            existing.meta.categories = updates["categories"]
        if "content" in updates and updates["content"] is not None:
            existing.content = updates["content"]
        elif "content_patches" in updates and updates["content_patches"] is not None:
            import diff_match_patch as dmp_module
            dmp = dmp_module.diff_match_patch()
            patches = dmp.patch_fromText(updates["content_patches"])
            new_text, results = dmp.patch_apply(patches, existing.content)
            if not all(results):
                raise ValueError("Error: Some patches could not be applied cleanly.")
            existing.content = new_text
        
    new_meta = await storage.save_article(existing)
    await storage.delete_article(old_id)
    
    index._remove_article(old_id)
    index.rebuild_article(new_id, new_meta, existing.content)
    
    if not update_links:
        return new_meta
        
    backlinks = index.what_links_here(old_id)
    affected_article_ids = set(bl.source_id for bl in backlinks if not bl.is_file_link)
    
    if existing.meta.type.value == "category":
        members = index.articles_in_category(old_id)
        affected_article_ids.update(members)
        
    for a_id in affected_article_ids:
        try:
            a = await storage.get_article(a_id)
        except KeyError:
            continue
            
        changed = False
        
        if old_id in a.meta.categories:
            a.meta.categories = [new_id if c == old_id else c for c in a.meta.categories]
            changed = True
            
        pattern = re.compile(r'\[\[' + re.escape(old_id) + r'(\|.*?)?\]\]')
        new_content = pattern.sub(r'[[' + new_id + r'\1]]', a.content)
        if new_content != a.content:
            a.content = new_content
            changed = True
            
        if changed:
            m = await storage.save_article(a)
            index.rebuild_article(a_id, m, a.content)
            
    for bl in backlinks:
        if bl.source_id in index._all_resource_meta:
            try:
                r_meta = await storage.get_resource_meta(bl.source_id)
            except KeyError:
                continue
            if old_id in r_meta.related:
                r_meta.related = [new_id if x == old_id else x for x in r_meta.related]
                await storage.save_resource_meta(r_meta)
                index.rebuild_resource(bl.source_id, r_meta)
                
    return new_meta


async def rename_resource(storage, index, old_id: str, new_id: str, update_references: bool = True):
    """Rename a resource and optionally update all references to it."""
    try:
        await storage.get_resource_meta(new_id)
        raise ValueError(f"Resource '{new_id}' already exists")
    except KeyError:
        pass
        
    new_meta = await storage.rename_resource_files(old_id, new_id)
    
    index._remove_resource(old_id)
    index.rebuild_resource(new_id, new_meta)
    
    if not update_references:
        return new_meta
        
    backlinks = index.what_links_here(old_id)
    affected_article_ids = set(bl.source_id for bl in backlinks)
    
    for a_id in affected_article_ids:
        if a_id in index._all_meta:
            try:
                a = await storage.get_article(a_id)
            except KeyError:
                continue
                
            pattern = re.compile(r'\[\[file:' + re.escape(old_id) + r'(\|.*?)?\]\]', flags=re.IGNORECASE)
            new_content = pattern.sub(r'[[file:' + new_id + r'\1]]', a.content)
            
            if new_content != a.content:
                a.content = new_content
                m = await storage.save_article(a)
                index.rebuild_article(a_id, m, a.content)
                
    for bl in backlinks:
        if bl.source_id in index._all_resource_meta:
            try:
                r_meta = await storage.get_resource_meta(bl.source_id)
            except KeyError:
                continue
            if old_id in r_meta.related:
                r_meta.related = [new_id if x == old_id else x for x in r_meta.related]
                await storage.save_resource_meta(r_meta)
                index.rebuild_resource(bl.source_id, r_meta)
                
    return new_meta
