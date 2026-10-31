import os
"""Database connection and audit logging repository using SQLModel / SQLite."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import Session, SQLModel, create_engine, select

from netcoop.config import settings
from netcoop.core.envelope import AgentEnvelope
from netcoop.storage.models import (
    EnvelopeLog,
    IncidentRecord,
    RemediationLog,
    OrchestratorCheckpoint,
    UserRecord,
    AuthAuditLog,
    RevokedToken,
)

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
            if "actor_user_id" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE remediation_logs ADD COLUMN actor_user_id TEXT")
            if "actor_username" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE remediation_logs ADD COLUMN actor_username TEXT")
            if "actor_role" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE remediation_logs ADD COLUMN actor_role TEXT")
            if "decision" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE remediation_logs ADD COLUMN decision TEXT")

            inc_cursor = conn.exec_driver_sql("PRAGMA table_info(incidents)")
            inc_cols = {row[1] for row in inc_cursor.fetchall()}
            if "assigned_to" not in inc_cols:
                conn.exec_driver_sql("ALTER TABLE incidents ADD COLUMN assigned_to TEXT")
            if "assigned_by" not in inc_cols:
                conn.exec_driver_sql("ALTER TABLE incidents ADD COLUMN assigned_by TEXT")
            if "assigned_at" not in inc_cols:
                conn.exec_driver_sql("ALTER TABLE incidents ADD COLUMN assigned_at TEXT")

            conn.commit()
        except Exception:
            pass
    init_default_users()


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
        statement = select(EnvelopeLog).where(EnvelopeLog.correlation_id == correlation_id).order_by(EnvelopeLog.id)
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
    """Retrieve incident record by ID."""
    with Session(engine) as session:
        return session.get(IncidentRecord, incident_id)


def list_incidents() -> List[IncidentRecord]:
    """List all incidents ordered by creation time descending."""
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
            existing.device = device
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
    """Look up a specific remediation action by action_id."""
    with Session(engine) as session:
        statement = select(RemediationLog).where(RemediationLog.action_id == action_id)
        return session.exec(statement).first()


def list_remediation_action_logs(
    incident_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[RemediationLog]:
    """List remediation actions filtered by incident_id or approval status."""
    with Session(engine) as session:
        statement = select(RemediationLog)
        if incident_id:
            statement = statement.where(RemediationLog.incident_id == incident_id)
        if status:
            statement = statement.where(RemediationLog.status == status)
        statement = statement.order_by(RemediationLog.id.desc())
        return list(session.exec(statement).all())


def record_hitl_decision(
    action_id: str,
    status: str,
    operator: str = "human_operator",
    rationale: Optional[str] = None,
    modified_commands: Optional[List[str]] = None,
    actor_user_id: Optional[str] = None,
    actor_username: Optional[str] = None,
    actor_role: Optional[str] = None,
) -> Optional[RemediationLog]:
    """Record an operator approval, rejection, or modification decision with dedicated actor fields."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        statement = select(RemediationLog).where(RemediationLog.action_id == action_id)
        rem_log = session.exec(statement).first()
        if not rem_log:
            return None

        actor_display = f"{actor_username} ({actor_role})" if actor_username else operator
        rem_log.status = status
        rem_log.decision = status
        rem_log.approved_by = actor_display
        rem_log.actor_user_id = actor_user_id
        rem_log.actor_username = actor_username
        rem_log.actor_role = actor_role
        rem_log.rationale = rationale
        rem_log.decision_timestamp = now_iso

        if modified_commands is not None:
            rem_log.modified_commands_json = json.dumps(modified_commands)
            rem_log.commands_json = json.dumps(modified_commands)

        session.add(rem_log)

        # Record envelope audit entry for human decision
        envelope_event = EnvelopeLog(
            correlation_id=rem_log.incident_id,
            message_id=f"hitl-{action_id}-{int(datetime.now(timezone.utc).timestamp())}",
            timestamp_utc=now_iso,
            sender=actor_display,
            recipient="remediation_engine",
            message_type="REMEDIATION_DECISION",
            priority="high",
            payload_json=json.dumps({
                "action_id": action_id,
                "status": status,
                "decision": status,
                "operator": actor_display,
                "actor_user_id": actor_user_id,
                "actor_username": actor_username,
                "actor_role": actor_role,
                "rationale": rationale or f"Operator decision: {status}",
                "modified_commands": modified_commands,
            }),
            context_json=json.dumps({
                "decision": status,
                "operator": actor_display,
                "actor_user_id": actor_user_id,
                "actor_username": actor_username,
                "actor_role": actor_role,
            }),
        )
        session.add(envelope_event)
        session.commit()
        session.refresh(rem_log)
        return rem_log


def get_remediation_logs(incident_id: Optional[str] = None) -> List[RemediationLog]:
    """Retrieve decision and simulated remediation history logs."""
    with Session(engine) as session:
        statement = select(RemediationLog)
        if incident_id:
            statement = statement.where(RemediationLog.incident_id == incident_id)
        statement = statement.order_by(RemediationLog.id.desc())
        return list(session.exec(statement).all())


def save_remediation_log(
    incident_id: str,
    action_id: str,
    device: str,
    commands: List[str],
    rollback_commands: List[str],
    risk_level: str,
    status: str,
    approved_by: Optional[str] = None,
    simulated_at: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_username: Optional[str] = None,
    actor_role: Optional[str] = None,
    decision: Optional[str] = None,
) -> RemediationLog:
    """Save or update a remediation decision in SQLite audit log with structured actor fields."""
    ts = simulated_at or datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        log_entry = RemediationLog(
            incident_id=incident_id,
            action_id=action_id,
            device=device,
            commands_json=json.dumps(commands),
            rollback_commands_json=json.dumps(rollback_commands),
            risk_level=risk_level,
            status=status,
            approved_by=approved_by,
            simulated_at=ts,
            decision_timestamp=ts,
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
            decision=decision or status,
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        return log_entry


# -----------------------------------------------------------------------------
# User Account & Authentication Persistence
# -----------------------------------------------------------------------------

def get_user_by_username(username: str) -> Optional[UserRecord]:
    """Look up user record by username."""
    with Session(engine) as session:
        statement = select(UserRecord).where(UserRecord.username == username)
        return session.exec(statement).first()


def get_user_by_id(user_id: str) -> Optional[UserRecord]:
    """Look up user record by user_id UUID."""
    with Session(engine) as session:
        statement = select(UserRecord).where(UserRecord.user_id == user_id)
        return session.exec(statement).first()


def create_user(
    username: str,
    hashed_password: str,
    role: str,
    full_name: Optional[str] = None,
    is_active: bool = True,
) -> UserRecord:
    """Create a new user account in SQLite."""
    with Session(engine) as session:
        user = UserRecord(
            username=username,
            hashed_password=hashed_password,
            role=role,
            full_name=full_name,
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def list_users() -> List[UserRecord]:
    """List all registered user accounts."""
    with Session(engine) as session:
        statement = select(UserRecord).order_by(UserRecord.id)
        return list(session.exec(statement).all())


def log_auth_event(
    event_type: str,
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    role: Optional[str] = None,
    endpoint: Optional[str] = None,
    client_ip: Optional[str] = None,
    details: Optional[str] = None,
) -> AuthAuditLog:
    """Record an authentication, authorization, or security violation event."""
    with Session(engine) as session:
        entry = AuthAuditLog(
            event_type=event_type,
            username=username,
            user_id=user_id,
            role=role,
            endpoint=endpoint,
            client_ip=client_ip,
            details=details,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def get_auth_audit_logs(limit: int = 100) -> List[AuthAuditLog]:
    """Retrieve recent authentication audit trail."""
    with Session(engine) as session:
        statement = select(AuthAuditLog).order_by(AuthAuditLog.id.desc()).limit(limit)
        return list(session.exec(statement).all())


def init_default_users() -> None:
    """Seed demonstration accounts strictly when demo mode is enabled or in development/testing."""
    from netcoop.config import is_demo_mode_allowed
    from netcoop.core.auth import DEMO_SEED_ACCOUNTS, hash_password

    # In production, never seed default demonstration accounts automatically
    env = os.getenv("NETCOOP_ENV", settings.environment).lower()
    if env == "production" and not is_demo_mode_allowed():
        return

    # Use development password for seeded testing accounts
    dev_pass = os.getenv("NETCOOP_DEV_PASSWORD", "NetCoopDev!2026")
    with Session(engine) as session:
        for acc in DEMO_SEED_ACCOUNTS:
            existing = session.exec(
                select(UserRecord).where(UserRecord.username == acc["username"])
            ).first()
            if not existing:
                user = UserRecord(
                    username=acc["username"],
                    hashed_password=hash_password(dev_pass),
                    role=acc["role"],
                    full_name=acc.get("full_name"),
                    is_active=True,
                )
                session.add(user)
        session.commit()


def provision_admin_user(
    username: str,
    password: str,
    full_name: Optional[str] = "Platform Administrator",
) -> UserRecord:
    """Provision administrative user account through controlled setup."""
    from netcoop.core.auth import hash_password, ROLE_PLATFORM_ADMIN

    with Session(engine) as session:
        existing = session.exec(select(UserRecord).where(UserRecord.username == username)).first()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.is_active = True
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        user = UserRecord(
            username=username,
            hashed_password=hash_password(password),
            role=ROLE_PLATFORM_ADMIN,
            full_name=full_name,
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def revoke_token(jti: str, expires_at: Optional[str] = None) -> RevokedToken:
    """Record a revoked JWT access token in the database."""
    with Session(engine) as session:
        rev = RevokedToken(jti=jti, expires_at=expires_at)
        session.add(rev)
        session.commit()
        session.refresh(rev)
        return rev


def is_token_revoked(jti: str) -> bool:
    """Check if a JWT access token has been revoked."""
    with Session(engine) as session:
        statement = select(RevokedToken).where(RevokedToken.jti == jti)
        return session.exec(statement).first() is not None


def assign_incident(
    incident_id: str,
    assignee: Optional[str] = None,
    assigner: Optional[str] = None,
    assigned_to: Optional[str] = None,
    assigned_by: Optional[str] = None,
) -> Optional[IncidentRecord]:
    """Record incident assignment in persistent store."""
    target_assignee = assigned_to or assignee or ""
    target_assigner = assigned_by or assigner or ""
    with Session(engine) as session:
        inc = session.get(IncidentRecord, incident_id)
        if not inc:
            return None
        inc.assigned_to = target_assignee
        inc.assigned_by = target_assigner
        inc.assigned_at = datetime.now(timezone.utc).isoformat()
        session.add(inc)
        session.commit()
        session.refresh(inc)
        return inc

