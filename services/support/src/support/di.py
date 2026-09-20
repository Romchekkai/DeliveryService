import structlog

from support.config import llm_settings, rag_settings
from support.rag.embedder import SentenceTransformerEmbedder
from support.rag.knowledge_loader import load_chunks
from support.rag.llm_client import OpenAICompatibleLLMClient
from support.rag.vector_store import InMemoryVectorStore

logger = structlog.get_logger(__name__)

llm_client = OpenAICompatibleLLMClient(
    base_url=llm_settings.base_url,
    api_key=llm_settings.api_key,
    model=llm_settings.model,
    timeout_seconds=llm_settings.timeout_seconds,
    temperature=llm_settings.temperature,
)

# Модель и индекс строятся один раз при старте (в lifespan), а не на каждый запрос.
vector_store: InMemoryVectorStore | None = None


def build_index() -> InMemoryVectorStore:
    global vector_store

    embedder = SentenceTransformerEmbedder(rag_settings.embedding_model)
    store = InMemoryVectorStore(embedder)
    store.index(load_chunks(rag_settings.knowledge_base_path, rag_settings.chunk_min_chars))

    vector_store = store
    return store


def get_vector_store() -> InMemoryVectorStore:
    if vector_store is None:
        raise RuntimeError("Index not built yet")
    return vector_store
