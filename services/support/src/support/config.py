from pydantic_settings import BaseSettings, SettingsConfigDict


class RagSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    knowledge_base_path: str = "data/knowledge_base.txt"
    chunk_min_chars: int = 80
    top_k: int = 4
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    base_url: str = "http://localhost:11434/v1"
    api_key: str = "not-needed"
    model: str = "llama3.1"
    timeout_seconds: int = 60
    temperature: float = 0.2


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    json_logs: bool = True


rag_settings = RagSettings()
llm_settings = LLMSettings()
app_settings = AppSettings()
