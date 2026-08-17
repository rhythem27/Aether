import re
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)

# Financial domain lexicons for high-precision, low-latency tonality scoring
POSITIVE_FINANCIAL_WORDS = {
    "growth", "growth guidance", "expansion", "profit", "profitability",
    "revenue increase", "margin expansion", "outperform", "record quarter",
    "exceeded expectations", "bullish", "surplus", "dividend increase",
    "robust", "strong demand", "cash flow positive", "upside"
}

NEGATIVE_FINANCIAL_WORDS = {
    "loss", "decline", "liability", "liabilities", "headwind", "headwinds",
    "downturn", "impairment", "bankruptcy", "default", "overhead", "overhead burden",
    "restructuring charge", "bearish", "deficit", "margin compression", "weakness",
    "downgrade", "missed estimates", "litigation risk", "write-down", "slump",
    "suffered", "bottlenecks", "bottleneck", "constrained", "drop", "slowdown"
}



class FinBERTSentimentAnalyzer:
    """Sentence-Level Financial Tonality & Sentiment Analysis Engine wrapping FinBERT / Lexicon Rules."""

    def __init__(self, use_hf_model: bool = False):
        self.use_hf_model = use_hf_model
        self._pipeline = None
        if use_hf_model:
            try:
                from transformers import pipeline
                self._pipeline = pipeline(
                    "text-classification",
                    model="ProsusAI/finbert",
                    return_all_scores=True,
                )
                logger.info("finbert_transformer_model_loaded")
            except Exception as err:
                logger.warning("finbert_model_load_failed_using_fallback", error=str(err))
                self.use_hf_model = False

    def analyze_sentence(self, sentence: str) -> Dict[str, Any]:
        """Analyze financial sentiment of a single sentence."""
        if not sentence or not sentence.strip():
            return {"label": "neutral", "score": 0.0, "confidence": 0.5}

        if self.use_hf_model and self._pipeline is not None:
            try:
                results = self._pipeline(sentence[:512])[0]
                pos = next((r["score"] for r in results if r["label"].lower() == "positive"), 0.0)
                neg = next((r["score"] for r in results if r["label"].lower() == "negative"), 0.0)
                neu = next((r["score"] for r in results if r["label"].lower() == "neutral"), 0.0)
                raw_score = round(pos - neg, 4)
                label = "positive" if raw_score > 0.1 else ("negative" if raw_score < -0.1 else "neutral")
                return {"label": label, "score": raw_score, "confidence": round(max(pos, neg, neu), 4)}
            except Exception as e:
                logger.warning("finbert_pipeline_eval_failed_fallback", error=str(e))

        # Financial lexicon rule evaluation fallback
        text_lower = sentence.lower()
        pos_hits = sum(1 for w in POSITIVE_FINANCIAL_WORDS if w in text_lower)
        neg_hits = sum(1 for w in NEGATIVE_FINANCIAL_WORDS if w in text_lower)

        total_hits = pos_hits + neg_hits
        if total_hits == 0:
            return {"label": "neutral", "score": 0.0, "confidence": 0.5}

        net_score = round((pos_hits - neg_hits) / max(1, total_hits), 4)
        if net_score > 0.1:
            label = "positive"
        elif net_score < -0.1:
            label = "negative"
        else:
            label = "neutral"

        conf = round(min(1.0, 0.6 + 0.1 * total_hits), 4)
        return {"label": label, "score": net_score, "confidence": conf}

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze financial sentiment across multi-sentence text passages."""
        if not text:
            return {
                "overall_label": "neutral",
                "overall_score": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "sentence_details": [],
            }

        sentences = [s.strip() for s in re.split(r"[.!?]\s+", text) if len(s.strip()) > 5]
        if not sentences:
            sentences = [text]

        results = [self.analyze_sentence(s) for s in sentences]
        scores = [r["score"] for r in results]
        avg_score = round(sum(scores) / max(1, len(scores)), 4)

        pos_c = sum(1 for r in results if r["label"] == "positive")
        neg_c = sum(1 for r in results if r["label"] == "negative")
        neu_c = sum(1 for r in results if r["label"] == "neutral")

        if avg_score > 0.08:
            overall_label = "positive"
        elif avg_score < -0.08:
            overall_label = "negative"
        else:
            overall_label = "neutral"

        return {
            "overall_label": overall_label,
            "overall_score": avg_score,
            "positive_count": pos_c,
            "negative_count": neg_c,
            "neutral_count": neu_c,
            "sentence_details": results,
        }


_analyzer_instance: Optional[FinBERTSentimentAnalyzer] = None


def get_financial_sentiment(text: str) -> Dict[str, Any]:
    """Get financial sentiment analysis score (-1.0 to +1.0) for input text."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = FinBERTSentimentAnalyzer(use_hf_model=False)
    return _analyzer_instance.analyze_text(text)
