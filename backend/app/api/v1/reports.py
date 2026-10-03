"""
Phase 8 — Weekly Intelligence Reports API (PRD §14.7 / Plan §8.3)

Endpoints:
  POST /reports/projects/{project_id}/generate — generate weekly intelligence report
  GET  /reports/{report_id}                    — retrieve generated report
  GET  /reports/projects/{project_id}          — list historical reports for project
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.entities import Report
from app.schemas.contracts import ReportSections
from app.intelligence.reports import generate_weekly_report

router = APIRouter(prefix="/reports", tags=["Weekly Reports"])


class ReportGenerateRequest(BaseModel):
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    time_window_days: Optional[int] = 7
    use_llm: bool = True


class ReportResponse(BaseModel):
    id: str
    project_id: str
    period_start: str
    period_end: str
    sections: Dict[str, Any]
    notion_page_id: Optional[str] = None
    created_at: str


@router.post("/projects/{project_id}/generate", response_model=ReportResponse)
async def generate_project_weekly_report(
    project_id: str,
    data: Optional[ReportGenerateRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate weekly intelligence report for a project."""
    from datetime import timezone, timedelta
    req = data or ReportGenerateRequest()
    days = req.time_window_days or 7
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    end_dt = req.period_end or now
    start_dt = req.period_start or (end_dt - timedelta(days=days))
    if hasattr(end_dt, "replace"):
        end_dt = end_dt.replace(tzinfo=None)
    if hasattr(start_dt, "replace"):
        start_dt = start_dt.replace(tzinfo=None)

    report, _ = await generate_weekly_report(
        db=db,
        project_id=project_id,
        period_start=start_dt,
        period_end=end_dt,
        use_llm=req.use_llm,
    )

    return ReportResponse(
        id=report.id,
        project_id=report.project_id,
        period_start=report.period_start.isoformat(),
        period_end=report.period_end.isoformat(),
        sections=report.sections or {},
        notion_page_id=report.notion_page_id,
        created_at=report.created_at.isoformat() if report.created_at else "",
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_by_id(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a previously generated intelligence report."""
    res = await db.execute(select(Report).where(Report.id == report_id))
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        id=report.id,
        project_id=report.project_id,
        period_start=report.period_start.isoformat(),
        period_end=report.period_end.isoformat(),
        sections=report.sections or {},
        notion_page_id=report.notion_page_id,
        created_at=report.created_at.isoformat() if report.created_at else "",
    )


@router.get("/projects/{project_id}", response_model=List[ReportResponse])
async def list_project_reports(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all reports generated for a project."""
    res = await db.execute(
        select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc())
    )
    reports = res.scalars().all()
    return [
        ReportResponse(
            id=r.id,
            project_id=r.project_id,
            period_start=r.period_start.isoformat(),
            period_end=r.period_end.isoformat(),
            sections=r.sections or {},
            notion_page_id=r.notion_page_id,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in reports
    ]
