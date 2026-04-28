from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Protocol

from cosk.extraction.models import SkeletonNode

_GEMINI_BATCH_LIMIT = 100


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


def _retry_with_backoff(
    func: Callable[[], object],
    *,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
) -> object:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    attempt = 0
    while True:
        attempt += 1
        try:
            return func()
        except Exception:  # noqa: BLE001
            if attempt >= max_attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            time.sleep(delay)


class GeminiEmbeddingProvider:
    def __init__(
        self,
        *,
        model_name: str = "gemini-embedding-001",
        key_file: str = ".geminikey",
        retry_max_attempts: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 8.0,
    ) -> None:
        if not model_name or not model_name.strip():
            raise ValueError("embedding model name must not be empty")
        self._model_name = model_name.strip()
        self._api_key = self._resolve_key(key_file)
        self._retry_max_attempts = retry_max_attempts
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay
        self._client = self._build_client()

    def _build_client(self) -> object:
        from google import genai  # noqa: PLC0415

        return genai.Client(api_key=self._api_key)

    @staticmethod
    def _resolve_key(key_file: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            return api_key

        resolved = os.getenv("GEMINI_KEY_PATH", key_file)
        if os.path.exists(resolved):
            with open(resolved, encoding="utf-8") as handle:
                return handle.read().strip()
        raise RuntimeError("GEMINI_API_KEY not set and key file not found")

    def embed(self, text: str) -> list[float]:
        if text is None:
            raise ValueError("text must not be None")

        def _request() -> object:
            return self._client.models.embed_content(model=self._model_name, contents=text)

        result = _retry_with_backoff(
            _request,
            max_attempts=self._retry_max_attempts,
            base_delay=self._retry_base_delay,
            max_delay=self._retry_max_delay,
        )
        embeddings = getattr(result, "embeddings", None)
        if not embeddings:
            raise ValueError("Gemini embedding response returned empty vector")
        values = getattr(embeddings[0], "values", None)
        if not values:
            raise ValueError("Gemini embedding response returned empty vector")
        return [float(value) for value in values]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed up to _GEMINI_BATCH_LIMIT texts in a single API call."""
        if not texts:
            return []
        if len(texts) > _GEMINI_BATCH_LIMIT:
            raise ValueError(
                f"embed_batch: max {_GEMINI_BATCH_LIMIT} texts per call, got {len(texts)}"
            )

        def _request() -> object:
            return self._client.models.embed_content(model=self._model_name, contents=texts)

        result = _retry_with_backoff(
            _request,
            max_attempts=self._retry_max_attempts,
            base_delay=self._retry_base_delay,
            max_delay=self._retry_max_delay,
        )
        embeddings = getattr(result, "embeddings", None)
        got = len(embeddings) if embeddings else 0
        if not embeddings or got != len(texts):
            raise ValueError(
                f"Gemini batch embedding returned {got} vectors for {len(texts)} inputs"
            )
        results: list[list[float]] = []
        for emb in embeddings:
            values = getattr(emb, "values", None)
            if not values:
                raise ValueError("Gemini embedding response returned empty vector")
            results.append([float(v) for v in values])
        return results


def build_node_embedding_text(node: SkeletonNode) -> str:
    return node.raw_signature + "\n" + node.docstring
