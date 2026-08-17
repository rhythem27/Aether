import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.rag.sentiment import FinBERTSentimentAnalyzer, get_financial_sentiment
from backend.rag.graphrag import EntityExtractor
from backend.agents.analysis import compute_sentiment_momentum

test_client = TestClient(app)


def test_finbert_sentiment_analyzer():
    analyzer = FinBERTSentimentAnalyzer(use_hf_model=False)

    pos_res = analyzer.analyze_sentence("Company reported record quarter with strong revenue growth guidance.")
    assert pos_res["label"] == "positive"
    assert pos_res["score"] > 0.0

    neg_res = analyzer.analyze_sentence("Company posted severe loss and restructuring charge liabilities.")
    assert neg_res["label"] == "negative"
    assert neg_res["score"] < 0.0

    neu_res = analyzer.analyze_sentence("Company filed Form 10-K for fiscal year.")
    assert neu_res["label"] == "neutral"


def test_edge_level_sentiment_graph_properties():
    extractor = EntityExtractor()
    text = "Apple Inc. reported revenue of $90 billion with strong growth guidance."

    graph_data = extractor.extract_from_text(text)
    assert len(graph_data.relationships) > 0

    for rel in graph_data.relationships:
        assert "sentiment_score" in rel.properties
        assert rel.properties["sentiment_score"] > 0.0


def test_compute_sentiment_momentum():
    bullish_q = [
        {"quarter": "Q1", "avg_sentiment": 0.10},
        {"quarter": "Q2", "avg_sentiment": 0.25},
        {"quarter": "Q3", "avg_sentiment": 0.40},
        {"quarter": "Q4", "avg_sentiment": 0.55},
    ]
    res_b = compute_sentiment_momentum(bullish_q)
    assert res_b["momentum_direction"] == "BULLISH_EXPANSION"
    assert res_b["sentiment_momentum_score"] > 0.50

    bearish_q = [
        {"quarter": "Q1", "avg_sentiment": 0.50},
        {"quarter": "Q2", "avg_sentiment": 0.30},
        {"quarter": "Q3", "avg_sentiment": 0.10},
        {"quarter": "Q4", "avg_sentiment": -0.20},
    ]
    res_bear = compute_sentiment_momentum(bearish_q)
    assert res_bear["momentum_direction"] == "BEARISH_DETERIORATION"
    assert res_bear["sentiment_momentum_score"] < 0.0


def test_fastapi_sentiment_momentum_endpoint():
    resp = test_client.get("/api/v1/analysis/sentiment-momentum?company_ticker=AAPL&num_quarters=4")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_ticker"] == "AAPL"
    assert "momentum_direction" in data
    assert "sentiment_momentum_score" in data
    assert len(data["quarterly_trajectory"]) == 4
