"""Ranked keyword search over article metadata and bodies.

Every query word must appear somewhere in the article (title, id, tags or body).
If no article contains all of them, articles matching the most words are returned
instead, marked as partial. Words are matched as substrings, so "river" also
finds "rivers" and "chromecast" finds "chromecast-ios".
"""

import re
from dataclasses import dataclass
from typing import Iterable

from wikiknowledge.storage.models import ArticleMeta

_TOKEN_RE = re.compile(r"[\w.\-/:]+")


@dataclass
class SearchHit:
    meta: ArticleMeta
    score: float
    matched: int
    snippet: str


def tokenize(query: str) -> list[str]:
    seen: list[str] = []
    for t in _TOKEN_RE.findall(query.lower()):
        t = t.strip(".-/:")
        if len(t) >= 2 and t not in seen:
            seen.append(t)
    return seen


def _snippet(body: str, tokens: list[str], width: int = 160) -> str:
    best_line, best_hits = "", 0
    for line in body.splitlines():
        low = line.lower()
        hits = sum(1 for t in tokens if t in low)
        if hits > best_hits:
            best_line, best_hits = line.strip(), hits
            if hits == len(tokens):
                break
    return best_line[:width]


def rank(query: str, docs: Iterable[tuple[ArticleMeta, str]], limit: int = 25) -> tuple[list[SearchHit], bool]:
    """Return (hits, partial). `partial` is True when no doc matched every word."""
    tokens = tokenize(query)
    if not tokens:
        return [], False
    phrase = query.lower().strip()
    hits: list[SearchHit] = []
    for meta, body in docs:
        title, ident = meta.title.lower(), meta.id.lower()
        tags = " ".join(meta.tags).lower()
        low = body.lower()
        score, matched = 0.0, 0
        for t in tokens:
            s = 0.0
            if t in title:
                s += 6
            if t in ident:
                s += 4
            if t in tags:
                s += 3
            n = low.count(t)
            if n:
                s += 1 + min(n, 10) * 0.2
            if s:
                matched += 1
                score += s
        if not matched:
            continue
        if len(tokens) > 1:
            if phrase in title:
                score += 10
            elif phrase in low:
                score += 5
        hits.append(SearchHit(meta, score, matched, _snippet(body, tokens)))

    full = [h for h in hits if h.matched == len(tokens)]
    partial = not full
    pool = full or hits
    pool.sort(key=lambda h: (-h.matched, -h.score, h.meta.title))
    return pool[:limit], partial


if __name__ == "__main__":
    from wikiknowledge.storage.models import ArticleType

    def m(i, title, tags=()):
        return ArticleMeta(id=i, title=title, type=ArticleType.LEAF, tags=list(tags))

    docs = [
        (m("cast-ios", "Chromecast on iOS: no devices", ["chromecast"]), "NSBonjourServices placeholder left unresolved"),
        (m("cast-arch", "Chromecast architecture", ["chromecast"]), "sender and receiver"),
        (m("iap", "Storefront", ["iap"]), "451 restricted content gating"),
    ]
    hits, partial = rank("chromecast ios no devices", docs)
    assert not partial and [h.meta.id for h in hits] == ["cast-ios"], hits
    hits, _ = rank("chromecast", docs)
    assert {h.meta.id for h in hits} == {"cast-ios", "cast-arch"}
    hits, _ = rank("NSBonjourServices", docs)
    assert hits[0].meta.id == "cast-ios" and "placeholder" in hits[0].snippet
    hits, partial = rank("451 restricted entitlement", docs)
    assert partial and hits[0].meta.id == "iap"
    assert rank("  ", docs) == ([], False)
    print("ok")
