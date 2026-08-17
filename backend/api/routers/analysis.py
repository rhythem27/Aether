from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException
import structlog

from backend.agents.analysis import compute_sentiment_momentum

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/sentiment-momentum", response_model=Dict[str, Any])
async def get_sentiment_momentum(
    company_ticker: str = Query(..., description="Stock ticker symbol (e.g. AAPL, TSLA)"),
    num_quarters: int = Query(4, ge=1, le=12, description="Number of historical quarters to evaluate"),
):
    """Retrieve multi-quarter executive tone trajectory and Sentiment Momentum Score for charting."""
    logger.info("fetching_sentiment_momentum", ticker=company_ticker, quarters=num_quarters)

    # Generate multi-quarter sentiment trajectory
    mock_quarterly_data: List[Dict[str, Any]] = [
        {
            "quarter": f"Q{((i) % 4) + 1}",
            "fiscal_year": 2024 if i >= 2 else 2023,
            "avg_sentiment": round(0.10 + 0.12 * i, 2),
            "positive_ratio": round(0.50 + 0.08 * i, 2),
        }
        for i in range(num_quarters)
    ]

    result = compute_sentiment_momentum(mock_quarterly_data)
    return {
        "company_ticker": company_ticker.upper(),
        "momentum_direction": result["momentum_direction"],
        "sentiment_momentum_score": result["sentiment_momentum_score"],
        "quarterly_trajectory": result["quarterly_trajectory"],
    }
