"""Reading article bodies regardless of where the article lives.

Native articles come from storage; virtual ones (source plugins, Google Drive)
come from the source manager. This is the one place that knows the split.
"""

import logging

from wikiknowledge.storage.models import Article, ArticleMeta

logger = logging.getLogger(__name__)

VIRTUAL_PREFIXES = ("src:", "gdrive:")


def is_virtual(article_id: str) -> bool:
    return article_id.startswith(VIRTUAL_PREFIXES)


async def read_article(article_id: str, storage, index, source_manager) -> Article:
    """Return the article with its body. Raises KeyError if it does not exist."""
    if not is_virtual(article_id):
        return await storage.get_article(article_id)
    meta = index.get_meta(article_id)
    if not meta:
        raise KeyError(article_id)
    return Article(meta=meta, content=await source_manager.get_article_content(article_id))


async def collect_article_texts(storage, index, source_manager) -> list[tuple[ArticleMeta, str]]:
    """(meta, body) for every indexed article; unreadable bodies become ""."""
    out: list[tuple[ArticleMeta, str]] = []
    for article_id, meta in dict(index._all_meta).items():
        try:
            body = (await read_article(article_id, storage, index, source_manager)).content
        except Exception as e:
            logger.debug("Could not read content for %s: %s", article_id, e)
            body = ""
        out.append((meta, body or ""))
    return out
