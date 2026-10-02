from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        """Generates plain text completion."""
        pass

    @abstractmethod
    async def complete_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        """Generates a structured, schema-validated Pydantic model."""
        pass

class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass
