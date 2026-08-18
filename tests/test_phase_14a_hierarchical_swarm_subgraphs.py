import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.agents.state import AgentState
from backend.agents.subgraphs import (
    create_ingestion_subgraph,
    ingestion_node,
    create_quantitative_subgraph,
    quantitative_node,
    create_qualitative_subgraph,
    qualitative_node,
)
from backend.agents.supervisor import (
    create_supervisor_workflow,
    create_master_orchestrator_workflow,
)
from backend.workers.research_tasks import dispatch_parallel_subgraphs_async


@pytest.mark.asyncio
async def test_ingestion_subgraph_execution():
    """Verify Data Ingestion Sub-Graph standalone execution."""
    initial_state: AgentState = {
        "messages": [HumanMessage(content="Ingest NVDA filings")],
        "company_ticker": "NVDA",
        "company_name": "NVIDIA Corp",
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

    res = await ingestion_node(initial_state)
    assert "research_data" in res
    rdata = res["research_data"]
    assert rdata["ticker"] == "NVDA"
    assert "company_profile" in rdata
    assert "sec_filings" in rdata
    assert len(res["messages"]) > 0


@pytest.mark.asyncio
async def test_quantitative_subgraph_execution():
    """Verify Quantitative Sub-Graph standalone execution."""
    initial_state: AgentState = {
        "messages": [],
        "company_ticker": "TSLA",
        "company_name": "Tesla Inc",
        "fiscal_year": 2025,
        "research_data": {
            "financial_extracts": {
                "revenue": 96_000_000_000,
                "net_income": 15_000_000_000,
            }
        },
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await quantitative_node(initial_state)
    assert "analysis_results" in res
    anal = res["analysis_results"]
    assert anal["profit_margin_pct"] > 0
    assert "pe_ratio" in anal
    assert "ev_ebitda" in anal
    assert anal["financial_risk_score"] < 50


@pytest.mark.asyncio
async def test_qualitative_subgraph_execution():
    """Verify Qualitative Sub-Graph standalone execution."""
    initial_state: AgentState = {
        "messages": [],
        "company_ticker": "AAPL",
        "company_name": "Apple Inc",
        "fiscal_year": 2025,
        "research_data": {
            "news_sentiment": {"score": 0.42, "sentiment": "bullish"},
            "expert_transcripts": ["CEO highlighted high margin hardware growth."],
        },
        "analysis_results": {},
        "verified_claims": [],
        "graph_operations": [],
        "report_sections": {},
        "human_approval": True,
        "errors": [],
        "token_usage": {},
    }

    res = await qualitative_node(initial_state)
    assert "analysis_results" in res
    anal = res["analysis_results"]
    assert "sentiment_momentum" in anal
    assert anal["sentiment_momentum"]["sentiment_momentum_score"] > 0
    assert "qualitative_risk" in anal
    assert anal["qualitative_risk"]["regulatory_compliance_status"] == "COMPLIANT"


@pytest.mark.asyncio
async def test_master_orchestrator_integration_with_checkpointer():
    """Verify Master Orchestrator workflow with checkpointer persistence across sub-graphs."""
    memory = MemorySaver()
    app = create_master_orchestrator_workflow(checkpointer=memory)

    config = {"configurable": {"thread_id": "phase14a_thread_1"}}
    initial_state: AgentState = {
        "messages": [HumanMessage(content="Full due diligence on MSFT")],
        "company_ticker": "MSFT",
        "company_name": "Microsoft Corp",
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

    final_state = await app.ainvoke(initial_state, config=config)

    assert len(final_state["research_data"]) > 0
    assert len(final_state["analysis_results"]) > 0
    assert len(final_state["verified_claims"]) > 0
    assert len(final_state["graph_operations"]) > 0
    assert final_state["report_sections"]["status"] == "FINALIZED"

    # Checkpoint state verification across sub-graph boundaries
    checkpointed = await app.aget_state(config)
    assert checkpointed.values["company_ticker"] == "MSFT"
    assert "profit_margin_pct" in checkpointed.values["analysis_results"]


@pytest.mark.asyncio
async def test_parallel_subgraph_dispatch():
    """Verify parallel sub-graph execution coroutines for multi-document batch handling."""
    res = await dispatch_parallel_subgraphs_async(target_company="AMZN")
    assert "research_data" in res
    assert "analysis_results" in res
    assert res["research_data"]["ticker"] == "AMZN"
    assert "profit_margin_pct" in res["analysis_results"]
