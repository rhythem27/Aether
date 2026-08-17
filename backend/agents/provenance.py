import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


class ProvenanceRecord(BaseModel):
    """Cryptographic provenance record for tamper-evident agent state tracking."""

    record_id: str
    agent_name: str
    timestamp_utc: str
    model_id: str
    prompt_hash: str
    source_doc_ids: List[str] = Field(default_factory=list)
    signature_hash: str
    previous_hash: str = "GENESIS_BLOCK"


def compute_sha256(content: str) -> str:
    """Compute SHA-256 hex digest for string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_provenance_record(
    agent_name: str,
    model_id: str = "gpt-4o-mini",
    prompt_text: str = "",
    source_doc_ids: Optional[List[str]] = None,
    previous_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Create and cryptographically sign a new provenance record."""
    rec_id = f"prov_{uuid.uuid4().hex[:12]}"
    now_utc = datetime.now(timezone.utc).isoformat()
    p_hash = compute_sha256(prompt_text) if prompt_text else compute_sha256(agent_name)
    prev_hash = previous_hash or "GENESIS_BLOCK"
    doc_ids = list(source_doc_ids) if source_doc_ids else []

    raw_sig_payload = f"{rec_id}:{agent_name}:{now_utc}:{p_hash}:{prev_hash}:{','.join(sorted(doc_ids))}"
    sig_hash = compute_sha256(raw_sig_payload)

    record = ProvenanceRecord(
        record_id=rec_id,
        agent_name=agent_name,
        timestamp_utc=now_utc,
        model_id=model_id,
        prompt_hash=p_hash,
        source_doc_ids=doc_ids,
        signature_hash=sig_hash,
        previous_hash=prev_hash,
    )

    logger.info(
        "provenance_record_created",
        record_id=rec_id,
        agent=agent_name,
        sig=sig_hash[:8],
    )
    return record.model_dump()
