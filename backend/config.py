"""Central configuration, loaded from environment / .env."""
import logging
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("uvicorn.error")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    groq_api_key: str = ""

    # Groq serves chat/completions only (no embeddings endpoint), so
    # embeddings run locally and for free via sentence-transformers.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "openai/gpt-oss-120b"

    chunk_size: int = 1000
    chunk_overlap: int = 150
    retriever_k: int = 4

    data_dir: str = "./data"
    chroma_dir: str = "./chroma_db"

    cors_origins: str = "*"

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def clean_groq_api_key(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().strip("'\"")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_startup(self) -> bool:
        """Validate critical configuration on startup and log clear diagnostics."""
        if not self.groq_api_key:
            logger.error(
                "CRITICAL STARTUP ERROR: GROQ_API_KEY is not set! "
                "Please configure GROQ_API_KEY in backend/.env with a valid key starting with 'gsk_'."
            )
            return False

        if not self.groq_api_key.startswith("gsk_"):
            prefix = self.groq_api_key[:6] if len(self.groq_api_key) >= 6 else self.groq_api_key
            logger.error(
                f"CRITICAL STARTUP ERROR: GROQ_API_KEY is malformed! Found prefix '{prefix}...', "
                "expected key to start with 'gsk_'. Please check backend/.env for corruption, "
                "stray quotes, or PowerShell formatting artifacts."
            )
            return False

        logger.info(
            f"Config validation: GROQ_API_KEY verified successfully (starts with 'gsk_'). "
            f"Using model: {self.llm_model}"
        )
        return True


settings = Settings()

