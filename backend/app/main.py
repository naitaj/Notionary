import sys
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings
from app.core.logging import setup_logging, logger, request_id_ctx
from app.core.errors import setup_exception_handlers
from app.database import engine, Base
import app.models.entities  # Ensure all model tables are registered
from app.api.v1 import router as api_v1_router

# Initialize structured logging
setup_logging(debug=settings.DEBUG)

async def _background_worker_task():
    logger.info("Notionary Background Worker Task Started")
    from workers.runner import process_next_job
    while True:
        try:
            processed = await process_next_job(worker_id="backend-worker")
            if not processed:
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in background worker", error=str(e))
            await asyncio.sleep(2.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Notionary Backend Service", env=settings.ENV)
    # Ensure database schema is created
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schemas verified and initialized")
    worker = asyncio.create_task(_background_worker_task())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        logger.info("Shutting down Notionary Backend Service")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Project Intelligence, Lineage Reasoning & Memory Layer on top of Notion",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup RFC 7807 exception handling
setup_exception_handlers(app)

# Request ID correlation middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or os.urandom(8).hex()
    request_id_ctx.set(req_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root status
@app.get("/")
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "online",
        "version": "1.0.0",
        "docs_url": "/docs",
        "llm_provider": settings.DEFAULT_LLM_PROVIDER,
        "embedding_provider": settings.DEFAULT_EMBEDDING_PROVIDER,
    }

# API v1 routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
