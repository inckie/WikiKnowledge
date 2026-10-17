"""Embedding Search Service

:wk-id: embedding-search-service
:wk-tags: architecture, embeddings, search, model2vec, vector, python
:wk-categories: system-architecture

The Embedding Search Service provides fast semantic search across WikiKnowledge articles using lightweight static embeddings (Model2Vec). It indexes all reachable wiki content (native markdown and virtual plugin articles) without blocking the FastAPI event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "minishlab/potion-base-8M"
DEFAULT_CONFIG = {
    "enabled": False,
    "model_name": DEFAULT_MODEL_NAME,
    "min_score": 0.20,
    "top_k": 30,
}


class EmbeddingChunk:
    """Represents a chunk of an article for vector indexing."""

    def __init__(
        self,
        article_id: str,
        title: str,
        article_type: str,
        tags: list[str],
        heading: str,
        text: str,
    ):
        self.article_id = article_id
        self.title = title
        self.article_type = article_type
        self.tags = tags
        self.heading = heading
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "article_type": self.article_type,
            "tags": self.tags,
            "heading": self.heading,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmbeddingChunk:
        return cls(
            article_id=data.get("article_id", ""),
            title=data.get("title", ""),
            article_type=data.get("article_type", "leaf"),
            tags=data.get("tags", []),
            heading=data.get("heading", ""),
            text=data.get("text", ""),
        )


class EmbeddingSearchService:
    """Service for managing, indexing, and querying Model2Vec embeddings."""

    def __init__(self, knowledge_dir: Path | str):
        self.knowledge_dir = Path(knowledge_dir)
        self.settings_file = self.knowledge_dir / ".settings" / "search_config.json"
        self.cache_dir = self.knowledge_dir / ".index" / "embeddings"

        self.config: dict[str, Any] = dict(DEFAULT_CONFIG)
        self.status: str = "idle"  # idle, indexing, ready, error
        self.last_indexed_at: Optional[str] = None
        self.last_error: Optional[str] = None

        self._model = None
        self._chunks: list[EmbeddingChunk] = []
        self._matrix: Optional[np.ndarray] = None
        self._indexing_lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    @property
    def model_name(self) -> str:
        return self.config.get("model_name", DEFAULT_MODEL_NAME)

    @property
    def min_score(self) -> float:
        return float(self.config.get("min_score", 0.20))

    @property
    def top_k(self) -> int:
        return int(self.config.get("top_k", 30))

    def load_settings(self) -> dict[str, Any]:
        """Load configuration from .settings/search_config.json."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = {**DEFAULT_CONFIG, **data.get("embedding_search", {})}
            except Exception as e:
                logger.error("Failed to load search_config.json: %s", e)
                self.config = dict(DEFAULT_CONFIG)
        else:
            self.config = dict(DEFAULT_CONFIG)
        return self.config

    def save_settings(self, enabled: bool) -> dict[str, Any]:
        """Save configuration to .settings/search_config.json."""
        self.config["enabled"] = enabled
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = {"embedding_search": self.config}
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.error("Failed to save search_config.json: %s", e)
            raise
        return self.config

    def get_status(self) -> dict[str, Any]:
        """Return status information for UI/API consumption."""
        article_ids = {c.article_id for c in self._chunks} if self._chunks else set()
        return {
            "enabled": self.enabled,
            "status": self.status,
            "article_count": len(article_ids),
            "chunk_count": len(self._chunks),
            "last_indexed": self.last_indexed_at,
            "last_error": self.last_error,
            "model_name": self.model_name,
        }

    def _get_model(self):
        """Lazily load the Model2Vec static model."""
        if self._model is None:
            logger.info("Loading Model2Vec model '%s'...", self.model_name)
            from model2vec import StaticModel
            self._model = StaticModel.from_pretrained(self.model_name)
            logger.info("Model2Vec model loaded.")
        return self._model

    def load_cache(self) -> bool:
        """Attempt to load pre-computed embeddings and chunks from disk cache."""
        matrix_path = self.cache_dir / "embeddings.npy"
        chunks_path = self.cache_dir / "chunks.json"
        meta_path = self.cache_dir / "meta.json"

        if matrix_path.exists() and chunks_path.exists():
            try:
                t0 = time.perf_counter()
                self._matrix = np.load(matrix_path)
                with open(chunks_path, "r", encoding="utf-8") as f:
                    chunks_raw = json.load(f)
                    self._chunks = [EmbeddingChunk.from_dict(c) for c in chunks_raw]

                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        self.last_indexed_at = meta.get("indexed_at")

                self.status = "ready"
                logger.info(
                    "Loaded cached embeddings in %.3fs (%d chunks, matrix %s)",
                    time.perf_counter() - t0,
                    len(self._chunks),
                    self._matrix.shape,
                )
                return True
            except Exception as e:
                logger.warning("Failed to load embedding cache: %s. Will re-index.", e)
                self._matrix = None
                self._chunks = []
                self.status = "idle"
                return False
        return False

    async def initialize(self, storage, index, source_manager) -> None:
        """Initialize the service on application startup."""
        self.load_settings()
        cached = self.load_cache()

        if self.enabled:
            if not cached:
                logger.info("Embedding search enabled but cache missing. Scheduling background index build...")
                asyncio.create_task(self.start_background_indexing(storage, index, source_manager))
            else:
                self.status = "ready"
        else:
            self.status = "idle" if not cached else "ready"

    async def _collect_articles(self, storage, index, source_manager) -> list[dict[str, Any]]:
        """Collect reachable wiki content: native articles and virtual plugin articles."""
        collected: list[dict[str, Any]] = []

        # Iterate over all registered metadata in the knowledge graph
        all_meta_copy = dict(index._all_meta)

        for article_id, meta in all_meta_copy.items():
            content = ""
            try:
                if article_id.startswith("src:") or article_id.startswith("gdrive:"):
                    content = await source_manager.get_article_content(article_id)
                else:
                    article = await storage.get_article(article_id)
                    content = article.content
            except Exception as e:
                logger.debug("Could not read content for %s: %s", article_id, e)
                content = ""

            collected.append({
                "id": article_id,
                "title": meta.title or article_id,
                "type": meta.type.value if hasattr(meta.type, "value") else str(meta.type),
                "tags": list(meta.tags or []),
                "categories": list(meta.categories or []),
                "content": content,
            })

        return collected

    def _chunk_article(self, article: dict[str, Any]) -> list[EmbeddingChunk]:
        """Chunk a single article into semantic segments for embedding."""
        chunks: list[EmbeddingChunk] = []
        article_id = article["id"]
        title = article["title"]
        atype = article["type"]
        tags = article["tags"]
        content = article.get("content", "")

        # 1. Summary chunk (Title, tags, categories, ID)
        header_text = f"Title: {title}. Tags: {', '.join(tags)}. ID: {article_id}."
        chunks.append(EmbeddingChunk(
            article_id=article_id,
            title=title,
            article_type=atype,
            tags=tags,
            heading="Overview",
            text=header_text,
        ))

        if not content:
            return chunks

        # Remove HTML comments like <!-- human:start -->
        clean_content = re.sub(r"<!--[\s\S]*?-->", "", content).strip()
        if not clean_content:
            return chunks

        # Split into sections by markdown headings
        # Regex captures heading lines like # Heading or ## Section
        sections = re.split(r"(?m)^(?=#{1,4}\s+)", clean_content)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n", 1)
            heading = ""
            body = section
            if lines[0].startswith("#"):
                heading = lines[0].lstrip("#").strip()
                body = lines[1].strip() if len(lines) > 1 else ""

            # If section body is short, keep as single chunk
            if len(body) <= 600:
                chunk_text = f"{title} - {heading}: {body}" if heading else f"{title}: {body}"
                chunks.append(EmbeddingChunk(
                    article_id=article_id,
                    title=title,
                    article_type=atype,
                    tags=tags,
                    heading=heading or "Content",
                    text=chunk_text.strip(),
                ))
            else:
                # Split large section into paragraphs
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                current_p = ""
                for p in paragraphs:
                    if len(current_p) + len(p) < 600:
                        current_p = f"{current_p}\n\n{p}".strip()
                    else:
                        if current_p:
                            chunk_text = f"{title} - {heading}: {current_p}" if heading else f"{title}: {current_p}"
                            chunks.append(EmbeddingChunk(
                                article_id=article_id,
                                title=title,
                                article_type=atype,
                                tags=tags,
                                heading=heading or "Content",
                                text=chunk_text.strip(),
                            ))
                        current_p = p
                if current_p:
                    chunk_text = f"{title} - {heading}: {current_p}" if heading else f"{title}: {current_p}"
                    chunks.append(EmbeddingChunk(
                        article_id=article_id,
                        title=title,
                        article_type=atype,
                        tags=tags,
                        heading=heading or "Content",
                        text=chunk_text.strip(),
                    ))

        return chunks

    def _process_and_save_index(self, articles_data: list[dict[str, Any]]) -> None:
        """CPU-heavy processing: chunking, embedding generation, disk saving (runs in worker thread)."""
        t0 = time.perf_counter()
        all_chunks: list[EmbeddingChunk] = []

        for article in articles_data:
            chunks = self._chunk_article(article)
            all_chunks.extend(chunks)

        if not all_chunks:
            self._chunks = []
            self._matrix = None
            return

        texts = [c.text for c in all_chunks]
        logger.info("Computing Model2Vec embeddings for %d chunks across %d articles...", len(texts), len(articles_data))

        model = self._get_model()
        raw_embeddings = model.encode(texts)

        # Normalize rows to unit length for fast dot-product cosine similarity
        norms = np.linalg.norm(raw_embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized_matrix = (raw_embeddings / norms).astype(np.float32)

        # Save to disk cache
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        matrix_path = self.cache_dir / "embeddings.npy"
        chunks_path = self.cache_dir / "chunks.json"
        meta_path = self.cache_dir / "meta.json"

        np.save(matrix_path, normalized_matrix)

        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in all_chunks], f)

        meta = {
            "model_name": self.model_name,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "article_count": len(articles_data),
            "chunk_count": len(all_chunks),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self._matrix = normalized_matrix
        self._chunks = all_chunks
        self.last_indexed_at = meta["indexed_at"]
        elapsed = time.perf_counter() - t0
        logger.info(
            "Embedding indexing complete in %.3fs (%d chunks, matrix shape: %s)",
            elapsed, len(all_chunks), self._matrix.shape,
        )

    async def start_background_indexing(self, storage, index, source_manager) -> None:
        """Run non-blocking background indexing task."""
        if self._indexing_lock.locked():
            logger.info("Embedding indexing already running. Skipping duplicate call.")
            return

        async with self._indexing_lock:
            self.status = "indexing"
            self.last_error = None
            try:
                # Step 1: Collect reachable wiki content
                articles_data = await self._collect_articles(storage, index, source_manager)

                # Step 2: Offload CPU chunking and embedding inference to worker thread
                await asyncio.to_thread(self._process_and_save_index, articles_data)

                self.status = "ready"
            except Exception as e:
                self.status = "error"
                self.last_error = str(e)
                logger.error("Embedding indexing failed: %s", e, exc_info=True)

    def search(self, query: str, top_k: Optional[int] = None) -> list[dict[str, Any]]:
        """Perform semantic search using cosine similarity over pre-computed vectors."""
        if not self.enabled or self._matrix is None or not self._chunks:
            return []

        q = query.strip()
        if not q:
            return []

        limit = top_k or self.top_k

        try:
            model = self._get_model()
            q_emb = model.encode([q])
            q_norm = np.linalg.norm(q_emb)
            if q_norm > 0:
                q_emb = (q_emb / q_norm).astype(np.float32)

            # Cosine similarity dot product
            scores = np.dot(self._matrix, q_emb.T).flatten()

            # Aggregate best score per article_id
            article_matches: dict[str, dict[str, Any]] = {}
            for idx, score in enumerate(scores):
                if score < self.min_score:
                    continue
                chunk = self._chunks[idx]
                aid = chunk.article_id
                if aid not in article_matches or score > article_matches[aid]["score"]:
                    article_matches[aid] = {
                        "id": aid,
                        "title": chunk.title,
                        "type": chunk.article_type,
                        "tags": chunk.tags,
                        "score": round(float(score), 4),
                        "heading": chunk.heading,
                        "snippet": chunk.text[:220].replace("\n", " ").strip(),
                    }

            ranked = sorted(article_matches.values(), key=lambda x: x["score"], reverse=True)
            return ranked[:limit]
        except Exception as e:
            logger.error("Error during embedding search: %s", e)
            return []
