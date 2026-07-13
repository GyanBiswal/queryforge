from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, loaded from environment variables / .env"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "QueryForge"
    environment: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Storage
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 25
    allowed_extensions: set[str] = {".pdf", ".txt", ".docx"}

    # Database
    database_url: str = "sqlite:///./queryforge.db"

    # Embeddings
    google_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Vector store
    chroma_persist_dir: str = "./chroma_data"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — avoids re-parsing env on every request."""
    return Settings()