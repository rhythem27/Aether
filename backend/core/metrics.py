from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

# 1. Total Research Jobs Enqueued
RESEARCH_JOBS_TOTAL = Counter(
    "aether_research_jobs_total",
    "Total autonomous due diligence research jobs processed",
    ["status"]
)

# 2. Currently Active Research Jobs
ACTIVE_RESEARCH_JOBS = Gauge(
    "aether_active_research_jobs",
    "Number of active multi-agent research workflows"
)

# 3. Agent Execution Latency Histogram
AGENT_EXECUTION_DURATION_SECONDS = Histogram(
    "aether_agent_execution_seconds",
    "Execution duration of individual swarm agent nodes",
    ["agent_name"]
)

# 4. Verified Claims Counter
VERIFIED_CLAIMS_COUNT = Counter(
    "aether_verified_claims_total",
    "Total audited financial claims",
    ["status"]
)

def get_prometheus_metrics() -> tuple[bytes, str]:
    """Generate Prometheus metric payload and content-type header."""
    return generate_latest(), CONTENT_TYPE_LATEST
