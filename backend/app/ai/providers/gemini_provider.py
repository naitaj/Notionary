import json
from typing import Optional, Type, TypeVar
from pydantic import BaseModel
from app.ai.providers.base import LLMProvider
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
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
            raise RuntimeError("Gemini client is not configured or GEMINI_API_KEY is missing.")
        
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        # google-genai client synchronous call wrapped or async
        response = self.client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=full_prompt,
        )
        return response.text

    async def complete_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system = (system_prompt or "") + f"\nYou MUST respond with valid JSON strictly conforming to this JSON schema:\n{schema_json}\nRespond ONLY with valid JSON."
        raw_text = await self.complete(prompt=prompt, system_prompt=system, temperature=0.0)
        
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
