import numpy as np
import structlog

from support.rag.embedder import Embedder
from support.rag.knowledge_loader import Chunk

logger = structlog.get_logger(__name__)


class InMemoryVectorStore:
    """Векторный поиск косинусной близостью.БД - файл"""

    def __init__(self, embedder: Embedder):
        self._embedder = embedder
        self._chunks: list[Chunk] = []
        self._vectors: np.ndarray | None = None

    def index(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("Нечего индексировать: база знаний пуста")

        self._chunks = chunks
        self._vectors = self._embedder.embed([c.text for c in chunks])
        logger.info("vector_store_indexed", chunks=len(chunks), dim=self._vectors.shape[1])

    def search(self, query: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        if self._vectors is None:
            raise RuntimeError("Индекс не построен — вызовите index()")

        query_vector = self._embedder.embed([query])[0]
        # эмбеддинги нормализованы, поэтому скалярное произведение = косинусная близость
        scores = self._vectors @ query_vector

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self._chunks[i], float(scores[i])) for i in top_indices]
