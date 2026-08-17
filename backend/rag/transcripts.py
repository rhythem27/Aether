import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import structlog

from backend.rag.sentiment import get_financial_sentiment
from backend.rag.graphrag import (
    EntityNode,
    EntityType,
    ExtractedGraphData,
    RelationshipTriple,
    RelationType,
    EntityResolver,
)

logger = structlog.get_logger(__name__)


class TranscriptSpeaker(BaseModel):
    """Speaker metadata in conversational expert network call transcript."""

    name: str
    role: str  # e.g., "Lead Analyst", "Former Executive", "Competitor", "Industry Expert"
    organization: Optional[str] = None


class TranscriptUtterance(BaseModel):
    """Structured speaker utterance statement with timestamp and tonality score."""

    speaker_name: str
    speaker_role: str
    text: str
    timestamp: Optional[str] = None
    sentiment_score: float = 0.0


class ParsedTranscript(BaseModel):
    """Structured expert call transcript with diarization annotations."""

    transcript_id: str
    title: str
    company_ticker: str
    date: str
    speakers: List[TranscriptSpeaker] = Field(default_factory=list)
    utterances: List[TranscriptUtterance] = Field(default_factory=list)


class TranscriptDiarizer:
    """Conversational Expert Call Transcript Parsing & Speaker Diarization Engine."""

    @staticmethod
    def parse_transcript(raw_text: str, company_ticker: str = "UNKNOWN") -> ParsedTranscript:
        """Parse raw transcript into speaker-role annotated JSON array and utterances."""
        t_id = f"tr_{uuid.uuid4().hex[:10]}"
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        speakers_map: Dict[str, TranscriptSpeaker] = {}
        utterances: List[TranscriptUtterance] = []

        # Standard header regex: [timestamp] Role (Name): utterance
        pattern_ts = re.compile(
            r"^\[(\d{2}:\d{2}:\d{2}|\d{2}:\d{2})\]\s*([^-\(\:]+)(?:\(([^)]+)\))?\s*:\s*(.*)$"
        )
        # Alternate header regex: Role - Name: utterance
        pattern_alt = re.compile(r"^([^-\:]+)\s*-\s*([^:]+):\s*(.*)$")

        for line in lines:
            ts_match = pattern_ts.match(line)
            if ts_match:
                ts, role_raw, name_raw, speech = ts_match.groups()
                s_role = role_raw.strip()
                s_name = name_raw.strip() if name_raw else s_role
                speech_text = speech.strip()

                if s_name not in speakers_map:
                    speakers_map[s_name] = TranscriptSpeaker(name=s_name, role=s_role)

                sent = get_financial_sentiment(speech_text)["overall_score"]
                utterances.append(
                    TranscriptUtterance(
                        speaker_name=s_name,
                        speaker_role=s_role,
                        text=speech_text,
                        timestamp=ts,
                        sentiment_score=sent,
                    )
                )
                continue

            alt_match = pattern_alt.match(line)
            if alt_match:
                role_raw, name_raw, speech = alt_match.groups()
                s_role = role_raw.strip()
                s_name = name_raw.strip()
                speech_text = speech.strip()

                if s_name not in speakers_map:
                    speakers_map[s_name] = TranscriptSpeaker(name=s_name, role=s_role)

                sent = get_financial_sentiment(speech_text)["overall_score"]
                utterances.append(
                    TranscriptUtterance(
                        speaker_name=s_name,
                        speaker_role=s_role,
                        text=speech_text,
                        sentiment_score=sent,
                    )
                )
                continue

            # Fallback generic speaker turn
            if ":" in line:
                parts = line.split(":", 1)
                s_name = parts[0].strip()
                speech_text = parts[1].strip()
                s_role = "Industry Expert" if "Analyst" not in s_name else "Lead Analyst"

                if s_name not in speakers_map:
                    speakers_map[s_name] = TranscriptSpeaker(name=s_name, role=s_role)

                sent = get_financial_sentiment(speech_text)["overall_score"]
                utterances.append(
                    TranscriptUtterance(
                        speaker_name=s_name,
                        speaker_role=s_role,
                        text=speech_text,
                        sentiment_score=sent,
                    )
                )

        logger.info(
            "transcript_parsed",
            transcript_id=t_id,
            speakers=len(speakers_map),
            utterances=len(utterances),
        )

        return ParsedTranscript(
            transcript_id=t_id,
            title=f"Expert Network Call Transcript - {company_ticker}",
            company_ticker=company_ticker,
            date="2024-05-15",
            speakers=list(speakers_map.values()),
            utterances=utterances,
        )


def build_transcript_graph(parsed: ParsedTranscript) -> ExtractedGraphData:
    """Build Neo4j qualitative opinion graph triples (EXPRESSED_OPINION_ON, CONTRADICTS, CONFIRMS)."""
    nodes: List[EntityNode] = []
    relationships: List[RelationshipTriple] = []

    comp_id = EntityResolver.generate_entity_id(parsed.company_ticker, EntityType.COMPANY)
    nodes.append(
        EntityNode(
            id=comp_id, name=parsed.company_ticker, label=EntityType.COMPANY
        )
    )

    speaker_nodes: Dict[str, str] = {}
    for s in parsed.speakers:
        e_id = EntityResolver.generate_entity_id(s.name, EntityType.EXPERT)
        speaker_nodes[s.name] = e_id
        nodes.append(
            EntityNode(
                id=e_id,
                name=s.name,
                label=EntityType.EXPERT,
                properties={"role": s.role, "organization": s.organization or "Independent"},
            )
        )

    prev_utterance: Optional[TranscriptUtterance] = None

    for idx, u in enumerate(parsed.utterances):
        s_id = speaker_nodes.get(u.speaker_name)
        if not s_id:
            s_id = EntityResolver.generate_entity_id(u.speaker_name, EntityType.EXPERT)

        op_id = f"op_{parsed.transcript_id}_{idx+1}"
        nodes.append(
            EntityNode(
                id=op_id,
                name=f"Opinion by {u.speaker_role}",
                label=EntityType.OPINION,
                properties={
                    "text": u.text,
                    "sentiment_score": u.sentiment_score,
                    "timestamp": u.timestamp,
                    "role": u.speaker_role,
                },
            )
        )

        # Expert EXPRESSED_OPINION_ON Company
        relationships.append(
            RelationshipTriple(
                source_id=s_id,
                target_id=comp_id,
                rel_type=RelationType.EXPRESSED_OPINION_ON,
                properties={
                    "sentiment_score": u.sentiment_score,
                    "role": u.speaker_role,
                    "timestamp": u.timestamp or "2024-05-15",
                    "text": u.text[:120],
                },
            )
        )

        # Check CONTRADICTS / CONFIRMS against previous speaker turn
        if prev_utterance and prev_utterance.speaker_name != u.speaker_name:
            prev_s_id = speaker_nodes.get(prev_utterance.speaker_name)
            if prev_s_id:
                # Disagreement in sentiment sign indicates CONTRADICTS
                if (prev_utterance.sentiment_score > 0.1 and u.sentiment_score < -0.1) or (
                    prev_utterance.sentiment_score < -0.1 and u.sentiment_score > 0.1
                ):
                    relationships.append(
                        RelationshipTriple(
                            source_id=s_id,
                            target_id=prev_s_id,
                            rel_type=RelationType.CONTRADICTS,
                            properties={"timestamp": u.timestamp or "2024-05-15"},
                        )
                    )
                # Agreement in sentiment sign indicates CONFIRMS
                elif abs(prev_utterance.sentiment_score - u.sentiment_score) < 0.3:
                    relationships.append(
                        RelationshipTriple(
                            source_id=s_id,
                            target_id=prev_s_id,
                            rel_type=RelationType.CONFIRMS,
                            properties={"timestamp": u.timestamp or "2024-05-15"},
                        )
                    )

        prev_utterance = u

    raw_graph = ExtractedGraphData(nodes=nodes, relationships=relationships)
    return EntityResolver.resolve_and_deduplicate(raw_graph)


async def query_qualitative_transcript_passages(
    parsed: ParsedTranscript,
    speaker_role_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve qualitative transcript passages filtered by speaker role and sentiment."""
    results = []
    role_filt = speaker_role_filter.lower().strip() if speaker_role_filter else None

    for u in parsed.utterances:
        if role_filt and role_filt not in u.speaker_role.lower():
            continue

        results.append(
            {
                "speaker_name": u.speaker_name,
                "speaker_role": u.speaker_role,
                "text": u.text,
                "timestamp": u.timestamp,
                "sentiment_score": u.sentiment_score,
                "qualitative_assessment": (
                    "CRITICAL_NEGATIVE"
                    if u.sentiment_score < -0.15
                    else ("FAVORABLE_POSITIVE" if u.sentiment_score > 0.15 else "NEUTRAL")
                ),
            }
        )

    logger.info(
        "qualitative_transcripts_queried",
        role_filter=speaker_role_filter,
        matched=len(results),
    )
    return results
