import hashlib
import json
import time
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import LLMCall

def compute_cache_key(purpose: str, model: str, prompt: str, system_prompt: Optional[str] = None) -> str:
    payload = f"{purpose}:{model}:{system_prompt or ''}:{prompt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

async def get_cached_llm_call(db: AsyncSession, cache_key: str) -> Optional[Dict[str, Any]]:
    query = select(LLMCall).where(LLMCall.cache_key == cache_key, LLMCall.status == "succeeded")
    res = await db.execute(query)
    record = res.scalars().first()
    if record and record.response:
        return record.response
    return None

async def record_llm_call(
    db: AsyncSession,
    purpose: str,
    model: str,
    cache_key: str,
    response_data: Any,
    project_id: Optional[str] = None,
    job_id: Optional[str] = None,
    prompt_version: str = "v1.0",
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
) -> LLMCall:
    record = LLMCall(
        project_id=project_id,
        job_id=job_id,
        purpose=purpose,
        model=model,
        prompt_version=prompt_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cache_key=cache_key,
        response=response_data if isinstance(response_data, dict) else {"text": str(response_data)},
        status="succeeded",
    )
    db.add(record)
    await db.commit()
    return record
