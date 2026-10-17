from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # LLM API Keys
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Defaults
    DEFAULT_LLM_PROVIDER: str = "groq"

    # Optional Redis
    REDIS_URL: Optional[str] = None

    # RAG Databases
    QDRANT_URL: str = "http://localhost:6333"
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    PORT: Optional[int] = 8000
    DATABASE_URL: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
