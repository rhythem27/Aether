from typing import Any, Dict, List
from langchain_core.messages import AIMessage
import structlog

from backend.agents.state import AgentState
from backend.rag.vlm_extractor import VLMExtractionService

logger = structlog.get_logger(__name__)


async def document_extraction_node(state: AgentState) -> Dict[str, Any]:
    """Document Extraction Agent: Extracts structured invoice JSON schemas with field-level log-probability confidence scores."""
    ticker = state.get("company_ticker", "UNKNOWN")
    research_data = dict(state.get("research_data", {}))
    errors = list(state.get("errors", []))
    logger.info("document_extraction_agent_executing", ticker=ticker)

    extracted_invoices: List[Dict[str, Any]] = list(research_data.get("extracted_invoices", []))
    document_paths: List[str] = research_data.get("document_paths", [])
    force_low_conf: bool = research_data.get("force_low_confidence_invoices", False)

    vlm_service = VLMExtractionService()

    try:
        # If specific document paths are provided, process them
        paths_to_process = document_paths if document_paths else [f"invoice_{ticker.lower()}_sample.pdf"]

        for path in paths_to_process:
            extracted = await vlm_service.extract_invoice_async(
                file_path=path, force_low_confidence=force_low_conf
            )
            extracted_invoices.append(extracted.model_dump())

        research_data["extracted_invoices"] = extracted_invoices

        # Count low confidence fields (< 90%)
        low_conf_fields_count = 0
        for inv in extracted_invoices:
            scores = inv.get("confidence_scores", {})
            for field, score in scores.items():
                if score < 0.90:
                    low_conf_fields_count += 1

        ai_msg = AIMessage(
            content=f"[Document Extraction Agent] Parsed {len(extracted_invoices)} financial invoice(s) for {ticker}. Low-confidence fields (< 90%): {low_conf_fields_count}."
        )

        return {
            "research_data": research_data,
            "messages": [ai_msg],
        }

    except Exception as e:
        err_msg = f"Document Extraction Agent failed for {ticker}: {str(e)}"
        logger.error("document_extraction_agent_failed", ticker=ticker, error=str(e))
        errors.append(err_msg)
        return {
            "errors": errors,
            "messages": [AIMessage(content=f"[Document Extraction Agent Error] {err_msg}")],
        }
