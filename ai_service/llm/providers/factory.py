from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from .base import BaseLLMProvider
from config.settings import settings

import time
import logging

logger = logging.getLogger(__name__)

class RateLimitRetryWrapper:
    """Wraps any LangChain ChatModel to retry automatically on HTTP 429 RateLimit errors with backoff."""
    def __init__(self, model):
        self._model = model

    def invoke(self, input, config=None, **kwargs):
        for attempt in range(4):
            try:
                return self._model.invoke(input, config=config, **kwargs)
            except Exception as exc:
                exc_str = str(exc).lower()
                if ("429" in exc_str or "rate limit" in exc_str or "rate_limit_exceeded" in exc_str) and attempt < 3:
                    wait_time = 3.0 * (attempt + 1)
                    logger.warning("LLM rate limit 429 hit (attempt %d/3). Waiting %.1fs before retrying...", attempt + 1, wait_time)
                    time.sleep(wait_time)
                else:
                    raise exc

    def stream(self, input, config=None, **kwargs):
        for attempt in range(4):
            try:
                return self._model.stream(input, config=config, **kwargs)
            except Exception as exc:
                exc_str = str(exc).lower()
                if ("429" in exc_str or "rate limit" in exc_str or "rate_limit_exceeded" in exc_str) and attempt < 3:
                    wait_time = 3.0 * (attempt + 1)
                    logger.warning("LLM rate limit 429 hit during stream (attempt %d/3). Waiting %.1fs before retrying...", attempt + 1, wait_time)
                    time.sleep(wait_time)
                else:
                    raise exc

    def __getattr__(self, name):
        return getattr(self._model, name)


class OpenAIProvider(BaseLLMProvider):
    def get_model(self, streaming: bool = False):
        raw = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model="gpt-4o-mini",
            streaming=streaming,
            temperature=0.7,
            max_retries=3
        )
        return RateLimitRetryWrapper(raw)

class GeminiProvider(BaseLLMProvider):
    def get_model(self, streaming: bool = False):
        import os
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        raw = ChatGoogleGenerativeAI(
            api_key=settings.GEMINI_API_KEY,
            model=model_name,
            streaming=streaming,
            temperature=0.7,
            max_retries=3
        )
        return RateLimitRetryWrapper(raw)

class AnthropicProvider(BaseLLMProvider):
    def get_model(self, streaming: bool = False):
        raw = ChatAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            model="claude-3-haiku-20240307",
            streaming=streaming,
            temperature=0.7,
            max_retries=3
        )
        return RateLimitRetryWrapper(raw)

class GroqProvider(BaseLLMProvider):
    def get_model(self, streaming: bool = False):
        raw = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model="llama-3.1-8b-instant",
            streaming=streaming,
            temperature=0.4,
            max_tokens=1024,
            max_retries=5
        )
        return RateLimitRetryWrapper(raw)

def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    provider = provider_name or settings.DEFAULT_LLM_PROVIDER
    if provider == "openai":
        return OpenAIProvider()
    elif provider == "gemini":
        return GeminiProvider()
    elif provider == "anthropic":
        return AnthropicProvider()
    elif provider == "groq":
        return GroqProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

