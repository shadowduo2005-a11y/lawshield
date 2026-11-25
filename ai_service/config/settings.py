from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM API Keys
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Provider selection and model overrides
    DEFAULT_LLM_PROVIDER: str = "gemini"
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"

    # Runtime
    ENVIRONMENT: str = "development"
    SPACY_MODEL: str = "en_core_web_sm"
    ENABLE_VECTOR_MEMORY: bool = False
    ENABLE_LONG_TERM_MEMORY: bool = False
    AI_SERVICE_TOKEN: Optional[str] = None
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Optional Redis
    REDIS_URL: Optional[str] = None

    # RAG Databases
    QDRANT_URL: str = "http://localhost:6333"
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    PORT: int = 8000
    DATABASE_URL: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

settings = Settings()
