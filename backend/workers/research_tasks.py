import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from celery import Celery
import structlog

from backend.core.config import settings
from backend.models.research import AgentActivity, JobStatus, ResearchRequest
from backend.agents.supervisor import create_supervisor_workflow, AgentState
from langchain_core.messages import HumanMessage

logger = structlog.get_logger(__name__)

# Initialize Celery app
celery_app = Celery(
    "aether_workers",
    broker=getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
    backend=getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# In-memory job repository for fast local lookup and fallback
_JOBS_DB: Dict[str, JobStatus] = {}


class JobManager:
    """Central Job State Store & Redis Pub/Sub Activity Broadcaster."""

    @classmethod
    def create_job(cls, request: ResearchRequest) -> JobStatus:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = JobStatus(
            job_id=job_id,
            target_company=request.target_company,
            status="queued",
            progress_pct=0.0,
            current_agent="supervisor",
            activities=[
                AgentActivity(
                    agent_name="system",
                    activity_type="thinking",
                    description=f"Enqueued research job for {request.target_company} ({request.research_depth} depth).",
                )
            ],
        )
        _JOBS_DB[job_id] = job
        return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[JobStatus]:
        return _JOBS_DB.get(job_id)

    @classmethod
    def list_jobs(cls) -> List[JobStatus]:
        return list(_JOBS_DB.values())

    @classmethod
    def update_job_status(
        cls,
        job_id: str,
        status: str,
        progress_pct: float,
        current_agent: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[JobStatus]:
        job = _JOBS_DB.get(job_id)
        if not job:
            return None

        job.status = status  # type: ignore[assignment]
        job.progress_pct = progress_pct
        if current_agent:
            job.current_agent = current_agent
        if result:
            job.result = result
        if error_message:
            job.error_message = error_message
        job.updated_at = datetime.utcnow()
        return job

    @classmethod
    def add_activity(cls, job_id: str, activity: AgentActivity):
        job = _JOBS_DB.get(job_id)
        if job:
            job.activities.append(activity)
            job.updated_at = datetime.utcnow()


async def execute_research_job_async(job_id: str, target_company: str):
    """Execute multi-agent swarm workflow asynchronously and broadcast progress updates."""
    logger.info("executing_research_job", job_id=job_id, target_company=target_company)

    JobManager.update_job_status(
        job_id, status="researching", progress_pct=15.0, current_agent="research_agent"
    )
    JobManager.add_activity(
        job_id,
        AgentActivity(
            agent_name="research_agent",
            activity_type="tool_call",
            description=f"Gathering SEC filings and market disclosures for {target_company}",
        ),
    )

    try:
        app = create_supervisor_workflow()
        initial_state: AgentState = {
            "messages": [
                HumanMessage(
                    content=f"Perform deep dive financial research on {target_company}"
                )
            ],
            "company_ticker": target_company.upper(),
            "company_name": target_company,
            "fiscal_year": 2025,
            "research_data": {},
            "analysis_results": {},
            "verified_claims": [],
            "graph_operations": [],
            "report_sections": {},
            "human_approval": True,
            "errors": [],
            "token_usage": {},
        }

        # Step-by-step stream execution
        async for output in app.astream(initial_state):
            for node_name, node_state in output.items():
                logger.info("swarm_node_completed", job_id=job_id, node=node_name)

                if node_name == "research_agent":
                    JobManager.update_job_status(
                        job_id,
                        status="analyzing",
                        progress_pct=35.0,
                        current_agent="analysis_agent",
                    )
                    JobManager.add_activity(
                        job_id,
                        AgentActivity(
                            agent_name="research_agent",
                            activity_type="complete",
                            description=f"Retrieved {len(node_state.get('research_data', {}).get('sec_filings', []))} SEC filings and market news.",
                        ),
                    )
                elif node_name == "analysis_agent":
                    JobManager.update_job_status(
                        job_id,
                        status="verifying",
                        progress_pct=60.0,
                        current_agent="verify_agent",
                    )
                    JobManager.add_activity(
                        job_id,
                        AgentActivity(
                            agent_name="analysis_agent",
                            activity_type="complete",
                            description=f"Computed valuation metrics (Margin: {node_state.get('analysis_results', {}).get('profit_margin_pct')}%, Risk: {node_state.get('analysis_results', {}).get('financial_risk_score')}/100).",
                        ),
                    )
                elif node_name == "verify_agent":
                    JobManager.update_job_status(
                        job_id,
                        status="reporting",
                        progress_pct=80.0,
                        current_agent="report_agent",
                    )
                    JobManager.add_activity(
                        job_id,
                        AgentActivity(
                            agent_name="verify_agent",
                            activity_type="complete",
                            description=f"Audited {len(node_state.get('verified_claims', []))} financial claims against primary SEC sources.",
                        ),
                    )
                elif node_name == "report_agent":
                    report_res = node_state.get("report_sections", {})
                    JobManager.update_job_status(
                        job_id,
                        status="complete",
                        progress_pct=100.0,
                        current_agent="report_agent",
                        result=report_res,
                    )
                    JobManager.add_activity(
                        job_id,
                        AgentActivity(
                            agent_name="report_agent",
                            activity_type="complete",
                            description=f"Finalized comprehensive due diligence report for {target_company}.",
                        ),
                    )

    except Exception as e:
        logger.error("research_job_failed", job_id=job_id, error=str(e))
        JobManager.update_job_status(
            job_id, status="error", progress_pct=100.0, error_message=str(e)
        )
        JobManager.add_activity(
            job_id,
            AgentActivity(
                agent_name="supervisor",
                activity_type="error",
                description=f"Job execution failed: {str(e)}",
            ),
        )


@celery_app.task(name="backend.workers.research_tasks.run_research_workflow")
def run_research_workflow(job_id: str, target_company: str):
    """Celery background worker entry point."""
    asyncio.run(execute_research_job_async(job_id, target_company))
