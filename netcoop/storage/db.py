"""Database connection and audit logging repository using SQLModel / SQLite."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import Session, SQLModel, create_engine, select

from netcoop.config import settings
from netcoop.core.envelope import AgentEnvelope
from netcoop.storage.models import EnvelopeLog, IncidentRecord, RemediationLog, OrchestratorCheckpoint

engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    """Initialize database tables and run lightweight schema migrations."""
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        try:
            cursor = conn.exec_driver_sql("PRAGMA table_info(remediation_logs)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "rationale" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE remediation_logs ADD COLUMN rationale TEXT")
            if "modified_commands_json" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE remediation_logs ADD COLUMN modified_commands_json TEXT")
            if "decision_timestamp" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE remediation_logs ADD COLUMN decision_timestamp TEXT")
            conn.commit()
        except Exception:
            pass


def log_envelope(envelope: AgentEnvelope) -> None:
    """Record an agent envelope to the persistent auditable log."""
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
    """Upsert incident record in persistent store."""
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


def get_incident(incident_id: str) -> Optional[IncidentRecord]:
    """Fetch incident by identifier."""
    with Session(engine) as session:
        return session.get(IncidentRecord, incident_id)


def list_incidents() -> List[IncidentRecord]:
    """List recent incidents ordered by creation time."""
    with Session(engine) as session:
        statement = select(IncidentRecord).order_by(IncidentRecord.created_at.desc())
        return list(session.exec(statement).all())


# -----------------------------------------------------------------------------
# Orchestrator Checkpointing (FEATURE_RESUME)
# -----------------------------------------------------------------------------

def _sanitize_for_json(obj: Any) -> Any:
    """Helper to ensure graph state is safely JSON-serializable."""
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [_sanitize_for_json(v) for v in obj]
    elif hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "to_dict"):
        return obj.to_dict()
    return obj


def save_checkpoint(
    session_id: str,
    node_name: str,
    state_dict: Dict[str, Any],
    iteration: int = 0,
    is_paused: bool = False,
) -> OrchestratorCheckpoint:
    """Persist an intermediate LangGraph orchestrator state checkpoint to SQLite."""
    clean_state = _sanitize_for_json(state_dict)
    state_json = json.dumps(clean_state)

    with Session(engine) as session:
        cp = OrchestratorCheckpoint(
            session_id=session_id,
            node_name=node_name,
            iteration=iteration,
            state_json=state_json,
            is_paused=is_paused,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(cp)

        # Also update IncidentRecord's state_blob and status if incident exists
        inc = session.get(IncidentRecord, session_id)
        if inc:
            inc.state_blob = state_json
            if is_paused:
                inc.status = "paused"
            session.add(inc)

        session.commit()
        session.refresh(cp)
        return cp


def get_latest_checkpoint(session_id: str) -> Optional[OrchestratorCheckpoint]:
    """Retrieve the most recent checkpoint for an orchestrator session."""
    with Session(engine) as session:
        statement = (
            select(OrchestratorCheckpoint)
            .where(OrchestratorCheckpoint.session_id == session_id)
            .order_by(OrchestratorCheckpoint.id.desc())
        )
        return session.exec(statement).first()


def list_checkpoints(session_id: str) -> List[OrchestratorCheckpoint]:
    """Retrieve all chronological checkpoints recorded for a session."""
    with Session(engine) as session:
        statement = (
            select(OrchestratorCheckpoint)
            .where(OrchestratorCheckpoint.session_id == session_id)
            .order_by(OrchestratorCheckpoint.id.asc())
        )
        return list(session.exec(statement).all())


def mark_session_paused(session_id: str) -> bool:
    """Flag the active session as paused in both latest checkpoint and incident record."""
    with Session(engine) as session:
        statement = (
            select(OrchestratorCheckpoint)
            .where(OrchestratorCheckpoint.session_id == session_id)
            .order_by(OrchestratorCheckpoint.id.desc())
        )
        cp = session.exec(statement).first()
        if cp:
            cp.is_paused = True
            session.add(cp)

        inc = session.get(IncidentRecord, session_id)
        if inc:
            inc.status = "paused"
            session.add(inc)

        session.commit()
        return True


def mark_session_resumed(session_id: str) -> bool:
    """Clear paused flag on the session so execution proceeds."""
    with Session(engine) as session:
        statement = (
            select(OrchestratorCheckpoint)
            .where(OrchestratorCheckpoint.session_id == session_id)
            .order_by(OrchestratorCheckpoint.id.desc())
        )
        cp = session.exec(statement).first()
        if cp:
            cp.is_paused = False
            session.add(cp)

        inc = session.get(IncidentRecord, session_id)
        if inc and inc.status == "paused":
            inc.status = "running"
            session.add(inc)

        session.commit()
        return True


# -----------------------------------------------------------------------------
# Human-in-the-Loop Remediation Persistence (FEATURE_HITL)
# -----------------------------------------------------------------------------

def save_remediation_action_log(
    incident_id: str,
    action_dict: Dict[str, Any],
    status: str = "pending",
) -> RemediationLog:
    """Record a recommended remediation action in pending-approval state."""
    action_id = action_dict.get("action_id", "act-unknown")
    device = action_dict.get("device", "unknown")
    commands = action_dict.get("commands", [])
    rollback = action_dict.get("rollback_commands", [])
    risk = action_dict.get("risk_level", "medium")

    with Session(engine) as session:
        statement = select(RemediationLog).where(
            RemediationLog.action_id == action_id
        )
        existing = session.exec(statement).first()
        if existing:
            existing.incident_id = incident_id
            existing.status = status
            existing.commands_json = json.dumps(commands)
            existing.rollback_commands_json = json.dumps(rollback)
            existing.risk_level = risk
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        log_entry = RemediationLog(
            incident_id=incident_id,
            action_id=action_id,
            device=device,
            commands_json=json.dumps(commands),
            rollback_commands_json=json.dumps(rollback),
            risk_level=risk,
            status=status,
            decision_timestamp=datetime.now(timezone.utc).isoformat(),
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        return log_entry


def get_remediation_action_log(action_id: str) -> Optional[RemediationLog]:
    """Lookup a specific remediation action by action_id."""
    with Session(engine) as session:
        statement = select(RemediationLog).where(RemediationLog.action_id == action_id)
        return session.exec(statement).first()


def list_remediation_action_logs(
    incident_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[RemediationLog]:
    """List remediation actions filtered by incident_id or approval status."""
    with Session(engine) as session:
        query = select(RemediationLog)
        if incident_id:
            query = query.where(RemediationLog.incident_id == incident_id)
        if status:
            query = query.where(RemediationLog.status == status)
        query = query.order_by(RemediationLog.id.desc())
        return list(session.exec(query).all())


def record_hitl_decision(
    action_id: str,
    status: str,
    operator: str = "human_operator",
    rationale: Optional[str] = None,
    modified_commands: Optional[List[str]] = None,
) -> Optional[RemediationLog]:
    """Record an operator approval, rejection, or modification decision with event log trace."""
    decision_ts = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        statement = select(RemediationLog).where(RemediationLog.action_id == action_id)
        rem_log = session.exec(statement).first()
        if not rem_log:
            return None

        rem_log.status = status
        rem_log.approved_by = operator
        rem_log.rationale = rationale
        rem_log.decision_timestamp = decision_ts
        if modified_commands is not None:
            rem_log.modified_commands_json = json.dumps(modified_commands)
            rem_log.commands_json = json.dumps(modified_commands)

        session.add(rem_log)

        # Log decision into event audit trail (EnvelopeLog)
        envelope_event = EnvelopeLog(
            correlation_id=rem_log.incident_id,
            message_id=f"hitl-{action_id}-{int(datetime.now(timezone.utc).timestamp())}",
            timestamp_utc=decision_ts,
            sender=operator,
            recipient="remediation_engine",
            message_type="REMEDIATION_DECISION",
            priority="high",
            payload_json=json.dumps({
                "action_id": action_id,
                "status": status,
                "operator": operator,
                "rationale": rationale or f"Operator decision: {status}",
                "modified_commands": modified_commands,
            }),
            context_json=json.dumps({
                "decision": status,
                "operator": operator,
            }),
        )
        session.add(envelope_event)
        session.commit()
        session.refresh(rem_log)
        return rem_log

