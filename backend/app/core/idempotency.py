from typing import Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import json

# In-memory fast cache with DB fallback
_idempotency_store: Dict[str, Dict[str, Any]] = {}

def get_idempotency_key(request: Request) -> Optional[str]:
    return request.headers.get("Idempotency-Key")

async def check_idempotency(key: str, route: str) -> Optional[Dict[str, Any]]:
    full_key = f"{route}:{key}"
    return _idempotency_store.get(full_key)

async def record_idempotency(key: str, route: str, status_code: int, response_data: Any):
    full_key = f"{route}:{key}"
    _idempotency_store[full_key] = {
        "status_code": status_code,
        "data": response_data,
    }
