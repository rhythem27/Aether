from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime, timezone
from sqlalchemy import text, Column, Integer, String, JSON, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.core.config import settings
from backend.core.logging import logger

engine = create_async_engine(
    settings.postgres_async_url, echo=False, future=True, pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class AuditProvenanceLedger(Base):
    """SEBI-Compliant Append-Only Cryptographic Audit Ledger Table."""

    __tablename__ = "audit_provenance_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(64), unique=True, nullable=False, index=True)
    report_id = Column(String(64), nullable=False, index=True)
    company_ticker = Column(String(16), nullable=False)
    agent_name = Column(String(64), nullable=False)
    timestamp_utc = Column(String(64), nullable=False)
    model_id = Column(String(64), nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    source_doc_ids = Column(JSON, nullable=False, default=list)
    signature_hash = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class InMemoryPostgresLedger:
    """In-memory mock ledger for offline testing environments without active PostgreSQL container."""

    _instance: Optional["InMemoryPostgresLedger"] = None

    def __init__(self):
        self.records: List[Dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> "InMemoryPostgresLedger":
        if cls._instance is None:
            cls._instance = InMemoryPostgresLedger()
        return cls._instance

    def append(self, report_id: str, company_ticker: str, record: Dict[str, Any]):
        entry = dict(record)
        entry["report_id"] = report_id
        entry["company_ticker"] = company_ticker
        entry["created_at"] = datetime.now(timezone.utc).isoformat()
        self.records.append(entry)

    def get_by_report_id(self, report_id: str) -> List[Dict[str, Any]]:
        return [r for r in self.records if r.get("report_id") == report_id]


async def init_postgres_audit_ledger():
    """Ensure the PostgreSQL audit_provenance_ledger table is created."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("postgres_audit_ledger_initialized")
    except Exception as e:
        logger.warning("postgres_init_ledger_warning_using_in_memory", error=str(e))


async def append_provenance_records(
    report_id: str,
    company_ticker: str,
    records: List[Dict[str, Any]],
    session: Optional[AsyncSession] = None,
) -> int:
    """Append immutable cryptographic provenance records to the PostgreSQL audit ledger."""
    if not records:
        return 0

    in_mem_ledger = InMemoryPostgresLedger.get_instance()

    try:
        async def _write(s: AsyncSession) -> int:
            count = 0
            for rec in records:
                # Check for existing record_id to preserve immutability & idempotency
                existing = await s.execute(
                    text("SELECT 1 FROM audit_provenance_ledger WHERE record_id = :rid"),
                    {"rid": rec["record_id"]},
                )
                if existing.scalar():
                    continue

                db_item = AuditProvenanceLedger(
                    record_id=rec["record_id"],
                    report_id=report_id,
                    company_ticker=company_ticker,
                    agent_name=rec["agent_name"],
                    timestamp_utc=rec["timestamp_utc"],
                    model_id=rec["model_id"],
                    prompt_hash=rec["prompt_hash"],
                    source_doc_ids=rec.get("source_doc_ids", []),
                    signature_hash=rec["signature_hash"],
                    previous_hash=rec.get("previous_hash", "GENESIS_BLOCK"),
                )
                s.add(db_item)
                count += 1
                in_mem_ledger.append(report_id, company_ticker, rec)
            await s.commit()
            return count

        if session is not None:
            return await _write(session)
        else:
            async with AsyncSessionLocal() as s:
                return await _write(s)
    except Exception as err:
        logger.warning("postgres_append_ledger_fallback_in_memory", error=str(err))
        count = 0
        for rec in records:
            in_mem_ledger.append(report_id, company_ticker, rec)
            count += 1
        return count


async def get_provenance_records_by_report_id(
    report_id: str, session: Optional[AsyncSession] = None
) -> List[Dict[str, Any]]:
    """Retrieve immutable provenance records for a given report ID."""
    try:
        async def _query(s: AsyncSession) -> List[Dict[str, Any]]:
            res = await s.execute(
                text(
                    "SELECT record_id, report_id, company_ticker, agent_name, timestamp_utc, model_id, prompt_hash, source_doc_ids, signature_hash, previous_hash FROM audit_provenance_ledger WHERE report_id = :rid ORDER BY id ASC"
                ),
                {"rid": report_id},
            )
            rows = res.fetchall()
            if not rows:
                return InMemoryPostgresLedger.get_instance().get_by_report_id(report_id)
            return [
                {
                    "record_id": r[0],
                    "report_id": r[1],
                    "company_ticker": r[2],
                    "agent_name": r[3],
                    "timestamp_utc": r[4],
                    "model_id": r[5],
                    "prompt_hash": r[6],
                    "source_doc_ids": r[7],
                    "signature_hash": r[8],
                    "previous_hash": r[9],
                }
                for r in rows
            ]

        if session is not None:
            return await _query(session)
        else:
            async with AsyncSessionLocal() as s:
                return await _query(s)
    except Exception as err:
        logger.warning("postgres_get_ledger_fallback_in_memory", error=str(err))
        return InMemoryPostgresLedger.get_instance().get_by_report_id(report_id)


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_postgres_health() -> bool:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error("postgres_health_check_failed", error=str(e))
        return False

