from fastapi import APIRouter
from app.api.v1.projects import router as projects_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.experiments import router as experiments_router
from app.api.v1.claims import router as claims_router
from app.api.v1.impact import router as impact_router
from app.api.v1.contradictions import router as contradictions_router
from app.api.v1.notion import router as notion_router
from app.api.v1.ai import router as ai_router
from app.api.v1.seed import router as seed_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.audit import router as audit_router
from app.api.v1.documents import router as documents_router
from app.api.v1.search import router as search_router
from app.api.v1.proposals import router as proposals_router
from app.api.v1.edges import router as edges_router
from app.api.v1.graph import router as graph_router

router = APIRouter()

router.include_router(projects_router)
router.include_router(decisions_router)
router.include_router(tasks_router)
router.include_router(experiments_router)
router.include_router(claims_router)
router.include_router(impact_router)
router.include_router(contradictions_router)
router.include_router(notion_router)
router.include_router(ai_router)
router.include_router(seed_router)
router.include_router(jobs_router)
router.include_router(audit_router)
router.include_router(documents_router)
router.include_router(search_router)
router.include_router(proposals_router, prefix="/proposals", tags=["proposals"])
router.include_router(edges_router)
router.include_router(graph_router)
