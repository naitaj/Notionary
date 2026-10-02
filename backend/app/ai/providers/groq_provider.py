import json
import re
from typing import Type, TypeVar, Optional, Any
import httpx
from pydantic import BaseModel

from app.ai.providers.base import LLMProvider
from app.config import settings
from app.models.entities import LLMCall
from app.database import AsyncSessionLocal
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)

class GroqProvider(LLMProvider):
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        model: str = "openai/gpt-oss-20b",
        **kwargs,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            
            try:
                async with AsyncSessionLocal() as session:
                    call_log = LLMCall(
                        purpose="complete",
                        model=model,
                        input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                        output_tokens=data.get("usage", {}).get("completion_tokens", 0),
                        status="succeeded"
                    )
                    session.add(call_log)
                    await session.commit()
            except Exception:
                pass
                
            return content

    async def complete_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        **kwargs,
    ) -> T:
        messages = []
        sys_content = system_prompt or "You are a helpful assistant."
        if "json" not in sys_content.lower():
            sys_content = f"{sys_content}\nOutput your response strictly as a valid JSON object."
        messages.append({"role": "system", "content": sys_content})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            if response.status_code >= 400:
                logger.error("groq_request_failed", status_code=response.status_code, body=response.text)
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"].strip()
            
            # Clean possible markdown formatting
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\n?", "", content)
                content = re.sub(r"\n?```$", "", content).strip()
                
            parsed = json.loads(content)
            
            try:
                async with AsyncSessionLocal() as session:
                    call_log = LLMCall(
                        purpose="complete_structured",
                        model=model,
                        input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                        output_tokens=data.get("usage", {}).get("completion_tokens", 0),
                        status="succeeded"
                    )
                    session.add(call_log)
                    await session.commit()
            except Exception:
                pass
                
            return response_model.model_validate(parsed)
