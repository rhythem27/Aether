from typing import List
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
import structlog

from backend.models.research import JobStatus, ResearchRequest, ResearchResponse
from backend.workers.research_tasks import JobManager, execute_research_job_async

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


@router.post(
    "/deep-dive", response_model=ResearchResponse, status_code=status.HTTP_202_ACCEPTED
)
async def initiate_deep_dive(
    request: ResearchRequest, background_tasks: BackgroundTasks
):
    """Initiate autonomous multi-agent financial due diligence research workflow."""
    logger.info(
        "initiating_deep_dive_research",
        company=request.target_company,
        depth=request.research_depth,
    )

    job = JobManager.create_job(request)
    background_tasks.add_task(
        execute_research_job_async, job.job_id, request.target_company
    )

    return ResearchResponse(
        job_id=job.job_id,
        status="queued",
        estimated_duration_seconds=180,
        poll_endpoint=f"/api/v1/research/jobs/{job.job_id}",
        websocket_endpoint=f"/api/v1/research/ws/{job.job_id}",
    )


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_research_status(job_id: str):
    """Retrieve research job status, execution progress, agent activity log, and report results."""
    job = JobManager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job '{job_id}' not found.",
        )
    return job


@router.get("/jobs", response_model=List[JobStatus])
async def list_research_jobs():
    """List all recent research jobs."""
    return JobManager.list_jobs()
