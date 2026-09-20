from abc import ABC, abstractmethod

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class Embedder(ABC):
    """Port v"""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder(Embedder):
    """local model to embed"""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        logger.info("embedder_loaded", model=model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)
