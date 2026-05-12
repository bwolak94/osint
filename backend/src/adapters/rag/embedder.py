"""BGE-M3 embedder via Ollama with graceful fallback to zero vectors."""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

_MODEL = "bge-m3"
_DIMENSIONS = 1024
_ZERO_VECTOR = [0.0] * _DIMENSIONS


class BGEEmbedder:
    """Wraps the Ollama ``bge-m3`` embedding model (1024-dimensional).

    If Ollama is unavailable (network error, model not pulled, etc.) every
    call silently returns a zero vector so that the rest of the pipeline can
    continue in keyword-only mode.
    """

    MODEL = _MODEL
    DIMENSIONS = _DIMENSIONS

    def __init__(self, ollama_host: str) -> None:
        self._ollama_host = ollama_host
        self._client: object | None = None
        self._available: bool | None = None  # lazy-checked on first call

    def _get_client(self) -> object:
        if self._client is None:
            try:
                from ollama import AsyncClient  # type: ignore[import-untyped]

                self._client = AsyncClient(host=self._ollama_host)
            except ImportError:
                log.warning("bge_embedder.ollama_not_installed")
                self._client = None
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Return a 1024-dim embedding for *text*, or a zero vector on failure."""
        client = self._get_client()
        if client is None:
            return list(_ZERO_VECTOR)

        try:
            resp = await client.embeddings(model=self.MODEL, prompt=text)  # type: ignore[union-attr]
            embedding: list[float] = resp.get("embedding") or resp["embedding"]
            if len(embedding) != self.DIMENSIONS:
                log.warning(
                    "bge_embedder.unexpected_dim",
                    expected=self.DIMENSIONS,
                    got=len(embedding),
                )
            return embedding
        except Exception as exc:
            log.warning("bge_embedder.embed_failed", error=str(exc))
            return list(_ZERO_VECTOR)

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Embed a list of texts in batches to avoid overwhelming Ollama."""
        results: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = [await self.embed(t) for t in batch]
            results.extend(batch_embeddings)
        return results

    def is_zero_vector(self, embedding: list[float]) -> bool:
        """Return True when the embedding is an all-zero fallback vector."""
        return all(v == 0.0 for v in embedding)
