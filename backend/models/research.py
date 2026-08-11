from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class ResearchRequest(BaseModel):
    """Payload for submitting an autonomous multi-agent deep dive research job."""
    target_company: str = Field(..., description="Company ticker or full name (e.g. AAPL, NVDA)")
    research_depth: Literal["quick", "standard", "deep"] = Field(default="standard", description="Investigation depth level")
    focus_areas: List[str] = Field(
        default=["financials", "competition", "leadership", "risk"],
        description="Key domain areas to analyze"
    )
    data_sources: List[str] = Field(
        default=["sec_edgar", "crunchbase", "news"],
        description="Primary external data sources"
    )
    output_format: Literal["json", "markdown", "pdf"] = Field(default="markdown", description="Report output format")
    human_review_gates: List[str] = Field(
        default=["high_risk_claims"],
        description="Human-in-the-loop validation triggers"
    )

class ResearchResponse(BaseModel):
    """Immediate HTTP 202 response containing queued job reference."""
    job_id: str
    status: Literal["queued", "researching", "analyzing", "verifying", "reporting", "complete", "error"]
    estimated_duration_seconds: int = 180
    poll_endpoint: str
    websocket_endpoint: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AgentActivity(BaseModel):
    """Real-time agent step event streamed over WebSockets."""
    agent_name: str
    activity_type: Literal["thinking", "tool_call", "tool_result", "error", "complete"]
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    token_usage: Optional[int] = None
    cost_usd: Optional[float] = None

class JobStatus(BaseModel):
    """Detailed status payload polled by client."""
    job_id: str
    target_company: str
    status: Literal["queued", "researching", "analyzing", "verifying", "reporting", "complete", "error"]
    progress_pct: float = 0.0
    current_agent: Optional[str] = None
    activities: List[AgentActivity] = Field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
