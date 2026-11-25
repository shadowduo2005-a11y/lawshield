from abc import ABC, abstractmethod
from typing import AsyncGenerator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

class BaseLLMProvider(ABC):
    @abstractmethod
    def get_model(self, streaming: bool = False) -> BaseChatModel:
        """Return the LangChain chat model instance."""
        pass
