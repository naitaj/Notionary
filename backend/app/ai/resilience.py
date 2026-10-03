import asyncio
import hashlib
import json
import logging
from typing import Optional, Type, TypeVar, Dict, Any
from pydantic import BaseModel

from app.ai.providers.base import LLMProvider
from app.ai.providers.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

class ResilientLLMProvider(LLMProvider):
    """
    Plan §9.3: Demo Hardening Resilience Wrapper.
    - Enforces a 15-second timeout on live provider operations.
    - Caches responses in-memory to prevent repeated latency overhead.
    - Seamlessly falls back to deterministic golden responses on network errors, timeouts, or rate limits.
    """
    def __init__(self, primary: LLMProvider, fallback: Optional[LLMProvider] = None, timeout_seconds: float = 15.0):
        self.primary = primary
        self.fallback = fallback or MockLLMProvider()
        self.timeout = timeout_seconds
        self._text_cache: Dict[str, str] = {}
        self._structured_cache: Dict[str, Any] = {}

    def _hash_key(self, prompt: str, system_prompt: Optional[str], extra: str = "") -> str:
        payload = f"{system_prompt or ''}::{prompt}::{extra}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        **kwargs,
    ) -> str:
        key = self._hash_key(prompt, system_prompt, f"complete_{max_tokens}_{temperature}")
        if key in self._text_cache:
            return self._text_cache[key]

        try:
            res = await asyncio.wait_for(
                self.primary.complete(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                ),
                timeout=self.timeout,
            )
            self._text_cache[key] = res
            return res
        except Exception as e:
            logger.warning(
                f"[ResilientLLMProvider] Primary LLM failed or timed out ({type(e).__name__}: {e}). "
                f"Falling back to golden response."
            )
            res = await self.fallback.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            self._text_cache[key] = res
            return res

    async def complete_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> T:
        key = self._hash_key(prompt, system_prompt, f"struct_{response_model.__name__}")
        if key in self._structured_cache:
            data = self._structured_cache[key]
            return response_model.model_validate(data)

        try:
            res = await asyncio.wait_for(
                self.primary.complete_structured(
                    prompt=prompt,
                    response_model=response_model,
                    system_prompt=system_prompt,
                    **kwargs,
                ),
                timeout=self.timeout,
            )
            if hasattr(res, "model_dump"):
                self._structured_cache[key] = res.model_dump()
            return res
        except Exception as e:
            logger.warning(
                f"[ResilientLLMProvider] Primary LLM structured extraction failed or timed out ({type(e).__name__}: {e}). "
                f"Falling back to golden response."
            )
            res = await self.fallback.complete_structured(
                prompt=prompt,
                response_model=response_model,
                system_prompt=system_prompt,
                **kwargs,
            )
            if hasattr(res, "model_dump"):
                self._structured_cache[key] = res.model_dump()
            return res
