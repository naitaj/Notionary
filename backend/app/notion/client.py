import asyncio
import random
import time
from typing import Dict, Any, Optional, List
import httpx
from app.core.config import settings
from app.core.logging import logger

NOTION_BASE_URL = "https://api.notion.com/v1"

class NotionRateLimiter:
    """Token bucket rate limiter: ~3 requests per second to comply with Notion API limits."""
    def __init__(self, rate_per_second: float = 3.0, capacity: float = 3.0):
        self.rate = rate_per_second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1.0

class NotionClient:
    """Notion API Client with Token Bucket Rate Limiting, Backoff + Jitter, and Mock Fallback."""

    def __init__(self, api_key: Optional[str] = None, api_version: Optional[str] = None):
        self.api_key = api_key or settings.NOTION_API_KEY
        self.api_version = api_version or settings.NOTION_API_VERSION
        self.rate_limiter = NotionRateLimiter(rate_per_second=3.0)
        self.is_mock = not bool(self.api_key) or self.api_key.startswith("mock_")
        
        # In-memory mock store for offline testing
        self.mock_databases: Dict[str, Dict[str, Any]] = {}
        self.mock_pages: Dict[str, Dict[str, Any]] = {}

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.api_version,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 5,
    ) -> Dict[str, Any]:
        url = f"{NOTION_BASE_URL}{endpoint}"
        headers = self._get_headers()

        for attempt in range(1, max_retries + 1):
            await self.rate_limiter.acquire()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=payload if payload else None,
                    )
                    
                    if response.status_code in (200, 201):
                        return response.json()
                    
                    # Rate limiting (429) or transient server errors (5xx)
                    if response.status_code in (429, 500, 502, 503, 504):
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            backoff = float(retry_after)
                        else:
                            jitter = random.uniform(0.5, 1.5)
                            backoff = (2 ** attempt) * 0.5 + jitter
                        
                        logger.warning(
                            "Notion API transient failure, retrying",
                            status_code=response.status_code,
                            attempt=attempt,
                            backoff=backoff,
                            endpoint=endpoint,
                        )
                        await asyncio.sleep(backoff)
                        continue

                    # Unrecoverable error
                    logger.error(
                        "Notion API call failed",
                        status_code=response.status_code,
                        response=response.text,
                        endpoint=endpoint,
                    )
                    response.raise_for_status()

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                if attempt == max_retries:
                    raise
                jitter = random.uniform(0.5, 1.5)
                backoff = (2 ** attempt) * 0.5 + jitter
                logger.warning("Notion connection error, retrying", error=str(exc), attempt=attempt)
                await asyncio.sleep(backoff)

        raise RuntimeError(f"Exceeded max retries ({max_retries}) for Notion API request to {endpoint}")

    # ----------------- Database Operations -----------------

    async def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Creates a database under parent_page_id."""
        if self.is_mock:
            db_id = f"mock-db-{title.lower().replace(' ', '-')}-{int(time.time() * 1000)}"
            data = {
                "id": db_id,
                "title": [{"type": "text", "text": {"content": title}}],
                "properties": properties,
                "url": f"https://notion.so/workspace/{db_id}",
            }
            self.mock_databases[db_id] = data
            return data

        payload = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        return await self._request("POST", "/databases", payload)

    async def update_database(
        self,
        database_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Updates property schemas of an existing database (e.g., adding relation columns)."""
        if self.is_mock:
            if database_id in self.mock_databases:
                self.mock_databases[database_id]["properties"].update(properties)
                return self.mock_databases[database_id]
            return {"id": database_id, "properties": properties}

        payload = {"properties": properties}
        return await self._request("PATCH", f"/databases/{database_id}", payload)

    async def query_database(
        self,
        database_id: str,
        filter_expr: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        start_cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Queries database items with optional filter and sorting."""
        if self.is_mock:
            results = [
                p for p in self.mock_pages.values()
                if p.get("parent", {}).get("database_id") == database_id
            ]
            return {"results": results, "has_more": False, "next_cursor": None}

        payload: Dict[str, Any] = {"page_size": page_size}
        if filter_expr:
            payload["filter"] = filter_expr
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor

        return await self._request("POST", f"/databases/{database_id}/query", payload)

    # ----------------- Page Operations -----------------

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        if self.is_mock:
            if page_id in self.mock_pages:
                return self.mock_pages[page_id]
            return {
                "id": page_id,
                "properties": {},
                "last_edited_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "url": f"https://notion.so/workspace/{page_id}",
            }

        return await self._request("GET", f"/pages/{page_id}")

    async def create_page(
        self,
        database_id: str,
        properties: Dict[str, Any],
        children: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Creates a new record page in a database."""
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if self.is_mock:
            page_id = f"mock-page-{int(time.time() * 1000)}-{random.randint(100, 999)}"
            data = {
                "id": page_id,
                "parent": {"type": "database_id", "database_id": database_id},
                "properties": properties,
                "created_time": now_iso,
                "last_edited_time": now_iso,
                "url": f"https://notion.so/workspace/{page_id}",
                "children": children or [],
            }
            self.mock_pages[page_id] = data
            return data

        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        if children:
            payload["children"] = children

        return await self._request("POST", "/pages", payload)

    async def update_page(
        self,
        page_id: str,
        properties: Optional[Dict[str, Any]] = None,
        archived: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Updates page properties or soft-deletes (archived)."""
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if self.is_mock:
            if page_id in self.mock_pages:
                if properties:
                    self.mock_pages[page_id]["properties"].update(properties)
                if archived is not None:
                    self.mock_pages[page_id]["archived"] = archived
                self.mock_pages[page_id]["last_edited_time"] = now_iso
                return self.mock_pages[page_id]
            return {
                "id": page_id,
                "properties": properties or {},
                "last_edited_time": now_iso,
            }

        payload: Dict[str, Any] = {}
        if properties:
            payload["properties"] = properties
        if archived is not None:
            payload["archived"] = archived

        return await self._request("PATCH", f"/pages/{page_id}", payload)

    async def append_block_children(
        self,
        block_id: str,
        children: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Appends block children (e.g. Callouts, bullet points, paragraphs) to a page."""
        if self.is_mock:
            if block_id in self.mock_pages:
                self.mock_pages[block_id].setdefault("children", []).extend(children)
            return {"results": children}

        payload = {"children": children}
        return await self._request("PATCH", f"/blocks/{block_id}/children", payload)

    async def get_block_children(
        self,
        block_id: str,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieves children blocks of a block or page."""
        if self.is_mock:
            return self.mock_pages.get(block_id, {}).get("children", [])

        res = await self._request("GET", f"/blocks/{block_id}/children?page_size={page_size}")
        return res.get("results", [])

def get_notion_client() -> NotionClient:
    return NotionClient()
