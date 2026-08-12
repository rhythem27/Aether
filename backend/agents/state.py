import operator
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """LangGraph central state dictionary for multi-agent financial research workflows."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    company_ticker: str
    company_name: Optional[str]
    fiscal_year: Optional[int]
    research_data: Dict[str, Any]
    analysis_results: Dict[str, Any]
    verified_claims: List[Dict[str, Any]]
    graph_operations: List[Dict[str, Any]]
    report_sections: Dict[str, Any]
    human_approval: bool
    errors: List[str]
    token_usage: Dict[str, int]
