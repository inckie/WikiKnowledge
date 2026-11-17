"""Search miss log

:wk-id: search-miss-log
:wk-tags: search, mcp, health, maintenance
:wk-categories: system-architecture

Records the agent searches that found nothing, or only partial matches, so the
gaps in a knowledge base become visible: a query that keeps missing is an article
nobody has written yet. Entries are JSON lines in `<kb_dir>/.index/search-misses.jsonl`
(the machine-local cache folder, not versioned). `kb_health` reports the most
frequent ones.

Logging is best-effort: a failure to write never fails the search.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_NAME = "search-misses.jsonl"


def log_path(kb_dir: Path) -> Path:
    return Path(kb_dir) / ".index" / LOG_NAME


def record_miss(kb_dir: Path | None, query: str, hits: int, partial: bool) -> None:
    """Append one miss (no hits, or partial hits only). Full matches are not logged."""
    if kb_dir is None or (hits and not partial):
        return
    path = log_path(kb_dir)
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "query": query, "hits": hits, "partial": partial}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as error:
        logger.warning("search miss log not written: %s", error)


def top_misses(kb_dir: Path | None, limit: int = 20) -> list[tuple[str, int, int]]:
    """Most frequent missed queries: (query, times missed, times with zero hits).

    Queries are compared case-insensitively with whitespace collapsed.
    """
    if kb_dir is None or not log_path(kb_dir).exists():
        return []
    total, empty, shown = Counter(), Counter(), {}
    for line in log_path(kb_dir).read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        key = " ".join(str(entry.get("query", "")).lower().split())
        if not key:
            continue
        shown.setdefault(key, entry["query"])
        total[key] += 1
        if not entry.get("hits"):
            empty[key] += 1
    return [(shown[k], n, empty[k]) for k, n in total.most_common(limit)]
