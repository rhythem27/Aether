import pytest

from backend.rag.transcripts import (
    TranscriptDiarizer,
    build_transcript_graph,
    query_qualitative_transcript_passages,
)
from backend.rag.graphrag import RelationType, EntityType

SAMPLE_TRANSCRIPT_RAW = """
[00:01:15] Former Executive (John Doe): Our manufacturing capabilities suffered severe bottlenecks and rising overhead liabilities in Q3.
[00:02:40] Lead Analyst (Jane Smith): However, the company reported record quarter revenue and robust demand growth guidance.
"""


def test_transcript_diarizer_parsing():
    parsed = TranscriptDiarizer.parse_transcript(SAMPLE_TRANSCRIPT_RAW, company_ticker="AAPL")

    assert parsed.company_ticker == "AAPL"
    assert len(parsed.speakers) == 2
    assert len(parsed.utterances) == 2

    s_roles = [s.role for s in parsed.speakers]
    assert "Former Executive" in s_roles
    assert "Lead Analyst" in s_roles

    neg_u = parsed.utterances[0]
    assert neg_u.speaker_name == "John Doe"
    assert neg_u.speaker_role == "Former Executive"
    assert neg_u.sentiment_score < 0.0

    pos_u = parsed.utterances[1]
    assert pos_u.speaker_name == "Jane Smith"
    assert pos_u.speaker_role == "Lead Analyst"
    assert pos_u.sentiment_score > 0.0


def test_build_transcript_graph():
    parsed = TranscriptDiarizer.parse_transcript(SAMPLE_TRANSCRIPT_RAW, company_ticker="AAPL")
    graph_data = build_transcript_graph(parsed)

    assert len(graph_data.nodes) > 0
    assert len(graph_data.relationships) > 0

    rel_types = [r.rel_type for r in graph_data.relationships]
    assert RelationType.EXPRESSED_OPINION_ON in rel_types
    assert RelationType.CONTRADICTS in rel_types or RelationType.CONFIRMS in rel_types


@pytest.mark.asyncio
async def test_query_qualitative_transcript_passages():
    parsed = TranscriptDiarizer.parse_transcript(SAMPLE_TRANSCRIPT_RAW, company_ticker="AAPL")

    former_exec_passages = await query_qualitative_transcript_passages(
        parsed, speaker_role_filter="former executive"
    )
    assert len(former_exec_passages) == 1
    assert former_exec_passages[0]["speaker_name"] == "John Doe"
    assert former_exec_passages[0]["qualitative_assessment"] == "CRITICAL_NEGATIVE"

    analyst_passages = await query_qualitative_transcript_passages(
        parsed, speaker_role_filter="analyst"
    )
    assert len(analyst_passages) == 1
    assert analyst_passages[0]["speaker_name"] == "Jane Smith"
    assert analyst_passages[0]["qualitative_assessment"] == "FAVORABLE_POSITIVE"
