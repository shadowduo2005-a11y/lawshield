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
                res = self._model.invoke(input, config=config, **kwargs)
                if hasattr(res, "content") and isinstance(res.content, list):
                    res.content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in res.content])
                elif hasattr(res, "content") and not isinstance(res.content, str):
                    res.content = str(res.content)
                return res
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
            model=settings.OPENAI_MODEL,
            streaming=streaming,
            temperature=0.7,
            max_retries=3
        )
        return RateLimitRetryWrapper(raw)

class GeminiProvider(BaseLLMProvider):
    def get_model(self, streaming: bool = False):
        candidates = [
            settings.GEMINI_MODEL,
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
        ]
        # Keep order while removing duplicates.
        candidates = list(dict.fromkeys(c for c in candidates if c))

        class MultiModelFallbackWrapper:
            def __init__(self, models_list, api_key, streaming_mode):
                self.models_list = models_list
                self.api_key = api_key
                self.streaming_mode = streaming_mode
                self._active_model = None

            def _get_active(self):
                if not self._active_model:
                    self._active_model = ChatGoogleGenerativeAI(
                        api_key=self.api_key,
                        model=self.models_list[0],
                        streaming=self.streaming_mode,
                        temperature=0.7,
                        max_retries=1
                    )
                return self._active_model

            @staticmethod
            def _should_fallback(exc: Exception) -> bool:
                """Return True for transient/quota errors that warrant trying the next model."""
                s = str(exc)
                su = s.upper()
                return (
                    "404" in s
                    or "503" in s
                    or "429" in s
                    or "not found" in s.lower()
                    or "not supported" in s.lower()
                    or "UNAVAILABLE" in su
                    or "HIGH DEMAND" in su
                    or "RESOURCE_EXHAUSTED" in su
                    or "RATE_LIMIT" in su
                    or "overloaded" in s.lower()
                    or "try again" in s.lower()
                )

            def invoke(self, *args, **kwargs):
                last_exc = None
                for idx, m_name in enumerate(self.models_list):
                    try:
                        m = ChatGoogleGenerativeAI(
                            api_key=self.api_key,
                            model=m_name,
                            streaming=self.streaming_mode,
                            temperature=0.7,
                            max_retries=1
                        )
                        res = m.invoke(*args, **kwargs)
                        if hasattr(res, "content") and isinstance(res.content, list):
                            res.content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in res.content])
                        elif hasattr(res, "content") and not isinstance(res.content, str):
                            res.content = str(res.content)
                        self._active_model = m
                        if idx > 0:
                            logger.info("Fell back to Gemini model: %s", m_name)
                        return res
                    except Exception as e:
                        last_exc = e
                        if self._should_fallback(e) and idx < len(self.models_list) - 1:
                            logger.warning(
                                "Gemini model '%s' failed (%s). Trying next candidate...",
                                m_name, str(e)[:120]
                            )
                            time.sleep(1)
                            continue
                        raise e
                raise last_exc

            def stream(self, *args, **kwargs):
                last_exc = None
                for idx, m_name in enumerate(self.models_list):
                    try:
                        m = ChatGoogleGenerativeAI(
                            api_key=self.api_key,
                            model=m_name,
                            streaming=self.streaming_mode,
                            temperature=0.7,
                            max_retries=1
                        )
                        gen = m.stream(*args, **kwargs)
                        self._active_model = m
                        if idx > 0:
                            logger.info("Stream fell back to Gemini model: %s", m_name)
                        return gen
                    except Exception as e:
                        last_exc = e
                        if self._should_fallback(e) and idx < len(self.models_list) - 1:
                            logger.warning(
                                "Gemini stream model '%s' failed (%s). Trying next candidate...",
                                m_name, str(e)[:120]
                            )
                            time.sleep(1)
                            continue
                        raise e
                raise last_exc

            def __getattr__(self, name):
                return getattr(self._get_active(), name)

        wrapper = MultiModelFallbackWrapper(candidates, settings.GEMINI_API_KEY, streaming)
        return RateLimitRetryWrapper(wrapper)

class AnthropicProvider(BaseLLMProvider):
    def get_model(self, streaming: bool = False):
        raw = ChatAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.ANTHROPIC_MODEL,
            streaming=streaming,
            temperature=0.7,
            max_retries=3
        )
        return RateLimitRetryWrapper(raw)

class GroqProvider(BaseLLMProvider):
    def get_model(self, streaming: bool = False):
        raw = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            streaming=streaming,
            temperature=0.4,
            max_tokens=1024,
            max_retries=5
        )
        return RateLimitRetryWrapper(raw)

_PROVIDER_KEYS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
}


def resolve_llm_provider_name(provider_name: str | None = None) -> str:
    """Return a provider which actually has an API key configured.

    Production previously defaulted to Groq even when only a Gemini/OpenAI key
    existed, causing every chat request to fail at runtime. The requested/default
    provider is still preferred, but the service can safely use another configured
    provider when necessary.
    """
    requested = (provider_name or settings.DEFAULT_LLM_PROVIDER or "").strip().lower()
    if requested not in _PROVIDER_KEYS:
        raise ValueError(
            f"Unknown LLM provider: {requested!r}. "
            f"Choose one of: {', '.join(_PROVIDER_KEYS)}"
        )

    if getattr(settings, _PROVIDER_KEYS[requested], None):
        return requested

    for fallback in ("groq", "gemini", "openai", "anthropic"):
        if getattr(settings, _PROVIDER_KEYS[fallback], None):
            logger.warning(
                "LLM provider '%s' has no API key; using configured provider '%s'.",
                requested,
                fallback,
            )
            return fallback

    raise RuntimeError(
        "No LLM API key is configured. Set GROQ_API_KEY, GEMINI_API_KEY, "
        "OPENAI_API_KEY, or ANTHROPIC_API_KEY on the AI service."
    )


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    provider = resolve_llm_provider_name(provider_name)
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
