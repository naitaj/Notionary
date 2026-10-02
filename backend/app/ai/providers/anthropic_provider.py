import json
from typing import Optional, Type, TypeVar
from pydantic import BaseModel
from app.ai.providers.base import LLMProvider
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.client = None
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except Exception:
                self.client = None

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        if not self.client:
            raise RuntimeError("Anthropic client is not configured or ANTHROPIC_API_KEY is missing.")
        
        system = system_prompt or "You are an AI assistant for project intelligence and lineage reasoning."
        message = await self.client.messages.create(
            model=settings.CLAUDE_SONNET_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    async def complete_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system = (system_prompt or "") + f"\nYou MUST respond with valid JSON strictly conforming to this JSON schema:\n{schema_json}\nRespond ONLY with valid JSON."
        
        raw_text = await self.complete(prompt=prompt, system_prompt=system, temperature=0.0)
        # Clean markdown code blocks if present
        clean_json = raw_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()
        
        data = json.loads(clean_json)
        return response_model.model_validate(data)
