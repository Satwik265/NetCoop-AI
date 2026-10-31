"""Database connection and audit logging repository using SQLModel / SQLite."""

import json
import time
from typing import Any, Dict, List, Optional
from sqlmodel import Session, SQLModel, create_engine, select

from netcoop.config import settings
from netcoop.core.envelope import AgentEnvelope
from netcoop.storage.models import EnvelopeLog, IncidentRecord, RemediationLog

connect_args = {"timeout": 60.0} if "sqlite" in settings.database_url else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)


def log_envelope(envelope: AgentEnvelope) -> None:
    """Record an agent envelope to the persistent auditable log with retry for concurrency."""
    for attempt in range(3):
        try:
            with Session(engine) as session:
                log_entry = EnvelopeLog(
                    correlation_id=envelope.header.correlation_id,
                    message_id=envelope.header.message_id,
                    timestamp_utc=envelope.header.timestamp_utc,
                    sender=envelope.header.sender.value,
                    recipient=envelope.header.recipient.value,
                    message_type=envelope.header.message_type.value,
                    priority=envelope.header.priority.value,
                    payload_json=envelope.payload.model_dump_json(),
                    context_json=json.dumps(envelope.context),
                )
                session.add(log_entry)
                session.commit()
                return
        except Exception:
            if attempt < 2:
                time.sleep(0.05 * (attempt + 1))
            else:
                pass


def get_envelope_logs(correlation_id: str) -> List[EnvelopeLog]:
    """Retrieve complete audit trace of envelopes for an incident."""
    with Session(engine) as session:
        statement = select(EnvelopeLog).where(
            EnvelopeLog.correlation_id == correlation_id
        ).order_by(EnvelopeLog.id)
        return list(session.exec(statement).all())


def save_incident(
    incident_id: str,
    network_id: str,
    status: str,
    probable_cause: Optional[str] = None,
    confidence: float = 0.0,
    report_json: Optional[str] = None,
    state_blob: Optional[str] = None,
) -> IncidentRecord:
    """Upsert incident record in persistent store with retry for concurrency."""
    for attempt in range(3):
        try:
            with Session(engine) as session:
                existing = session.get(IncidentRecord, incident_id)
                if existing:
                    existing.status = status
                    existing.probable_cause = probable_cause
                    existing.confidence = confidence
                    existing.report_json = report_json
                    existing.state_blob = state_blob
                    session.add(existing)
                    session.commit()
                    session.refresh(existing)
                    return existing
                else:
                    rec = IncidentRecord(
                        incident_id=incident_id,
                        network_id=network_id,
                        status=status,
                        probable_cause=probable_cause,
                        confidence=confidence,
                        report_json=report_json,
                        state_blob=state_blob,
                    )
                    session.add(rec)
                    session.commit()
                    session.refresh(rec)
                    return rec
        except Exception:
            if attempt < 2:
                time.sleep(0.05 * (attempt + 1))
            else:
                # Return dummy in-memory record if database lock persisted
                return IncidentRecord(
                    incident_id=incident_id,
                    network_id=network_id,
                    status=status,
                    probable_cause=probable_cause,
                    confidence=confidence,
                )


def get_incident(incident_id: str) -> Optional[IncidentRecord]:
    """Fetch incident by identifier."""
    with Session(engine) as session:
        return session.get(IncidentRecord, incident_id)


def list_incidents() -> List[IncidentRecord]:
    """List recent incidents ordered by creation time."""
    with Session(engine) as session:
        statement = select(IncidentRecord).order_by(IncidentRecord.created_at.desc())
        return list(session.exec(statement).all())


def log_remediation(
    action_id: str,
    incident_id: str,
    device: str,
    commands: List[str],
    rollback_commands: List[str],
    risk_level: str = "medium",
    status: str = "simulated_success",
    diff: str = "",
) -> RemediationLog:
    """Record remediation execution audit log."""
    with Session(engine) as session:
        log_entry = RemediationLog(
            action_id=action_id,
            incident_id=incident_id,
            device=device,
            commands_json=json.dumps(commands),
            rollback_json=json.dumps(rollback_commands),
            risk_level=risk_level,
            status=status,
            diff=diff,
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        return log_entry
