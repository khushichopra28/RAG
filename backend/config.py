"""Central configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""

    # Groq serves chat/completions only (no embeddings endpoint), so
    # embeddings run locally and for free via sentence-transformers.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "llama-3.3-70b-versatile"

    chunk_size: int = 1000
    chunk_overlap: int = 150
    retriever_k: int = 4

    data_dir: str = "./data"
    chroma_dir: str = "./chroma_db"

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
