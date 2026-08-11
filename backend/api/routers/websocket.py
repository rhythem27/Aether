import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

from backend.workers.research_tasks import JobManager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/research", tags=["websocket"])

@router.websocket("/ws/{job_id}")
async def research_websocket(websocket: WebSocket, job_id: str):
    """Stream real-time agent execution progress, thoughts, and tool invocation events over WebSockets."""
    await websocket.accept()
    logger.info("websocket_client_connected", job_id=job_id)

    last_activity_count = 0
    try:
        while True:
            job = JobManager.get_job(job_id)
            if not job:
                await websocket.send_json({"event": "error", "detail": f"Job '{job_id}' not found."})
                await websocket.close()
                break

            # Send new activity events
            current_activities = job.activities
            if len(current_activities) > last_activity_count:
                new_items = current_activities[last_activity_count:]
                for item in new_items:
                    await websocket.send_json({
                        "event": "agent_activity",
                        "job_id": job_id,
                        "status": job.status,
                        "progress_pct": job.progress_pct,
                        "activity": item.model_dump(mode="json")
                    })
                last_activity_count = len(current_activities)

            # Close socket when job reaches terminal state
            if job.status in ["complete", "error"]:
                await websocket.send_json({
                    "event": "job_terminal",
                    "job_id": job_id,
                    "status": job.status,
                    "progress_pct": job.progress_pct,
                    "result": job.result if job.status == "complete" else None,
                    "error_message": job.error_message if job.status == "error" else None
                })
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info("websocket_client_disconnected", job_id=job_id)
    except Exception as e:
        logger.error("websocket_streaming_error", job_id=job_id, error=str(e))
        try:
            await websocket.close()
        except Exception:
            pass
