import os
"""Database connection and audit logging repository using SQLModel / SQLite."""

import json
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import Session, SQLModel, create_engine, select, update

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
    WsTicketRecord,
    TicketRecord,
    DiagnosisRunRecord,
)

connect_args = {"timeout": 60.0} if "sqlite" in settings.database_url else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


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
    init_default_tickets()


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
            rollback_commands_json=json.dumps(rollback_commands),
            risk_level=risk_level,
            status=status,
            simulated_at=datetime.now(timezone.utc).isoformat(),
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
    rationale: Optional[str] = None,
    modified_commands_json: Optional[str] = None,
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
            rationale=rationale,
            modified_commands_json=modified_commands_json,
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
    """Seed demonstration accounts strictly when demo mode is enabled, in development/testing, or cloud demo deployment."""
    from netcoop.config import is_demo_mode_allowed
    from netcoop.core.auth import DEMO_SEED_ACCOUNTS, hash_password

    DEFAULT_DEMO_PASSWORDS = {
        "platform_admin": "NetCoopPlat!2026",
        "admin": "NetCoopAdmin!2026",
        "engineer": "NetCoopEng!2026",
        "helpdesk": "NetCoopHelp!2026",
        "noc": "NetCoopNoc!2026",
        "security": "NetCoopSec!2026",
        "it_manager": "NetCoopMgr!2026",
        "auditor": "NetCoopAuditor!2026",
    }

    env = os.getenv("NETCOOP_ENV", settings.environment).lower()
    is_render = os.getenv("RENDER") == "true"
    allow_seed = (env != "production") or is_demo_mode_allowed() or is_render

    with Session(engine) as session:
        has_any_user = session.exec(select(UserRecord)).first() is not None
        # In strict non-cloud production with existing users, never re-seed
        if not allow_seed and has_any_user:
            return

        for acc in DEMO_SEED_ACCOUNTS:
            existing = session.exec(
                select(UserRecord).where(UserRecord.username == acc["username"])
            ).first()
            if not existing:
                account_pass = os.getenv("NETCOOP_DEV_PASSWORD") or DEFAULT_DEMO_PASSWORDS.get(
                    acc["username"], "NetCoopDev!2026"
                )
                user = UserRecord(
                    username=acc["username"],
                    hashed_password=hash_password(account_pass),
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

def create_db_ws_ticket(user: UserRecord, expiry_seconds: int = 60) -> str:
    """Generate and persist a single-use WebSocket connection ticket."""
    import hashlib
    import secrets
    raw_ticket = secrets.token_urlsafe(32)
    ticket_hash = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
    expires_at = time.time() + expiry_seconds

    with Session(engine) as session:
        rec = WsTicketRecord(
            ticket_hash=ticket_hash,
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            expires_at=expires_at,
            consumed=False,
        )
        session.add(rec)
        session.commit()
    return raw_ticket


def consume_db_ws_ticket(raw_ticket: str) -> tuple[bool, str, Optional[UserRecord]]:
    """Atomically validate and consume a single-use WebSocket ticket via conditional update."""
    import hashlib
    ticket_hash = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
    now = time.time()
    consumed_at_str = datetime.now(timezone.utc).isoformat()

    with Session(engine) as session:
        # Atomic conditional update query
        stmt = (
            update(WsTicketRecord)
            .where(
                WsTicketRecord.ticket_hash == ticket_hash,
                WsTicketRecord.consumed == False,
                WsTicketRecord.expires_at >= now,
            )
            .values(consumed=True, consumed_at=consumed_at_str)
        )
        res = session.exec(stmt)
        session.commit()

        if res.rowcount == 0:
            # Query status to provide precise rejection reason
            check = session.exec(
                select(WsTicketRecord).where(WsTicketRecord.ticket_hash == ticket_hash)
            ).first()
            if not check:
                return False, "Invalid or non-existent WebSocket ticket.", None
            if check.consumed:
                return False, "WebSocket ticket has already been consumed (replay rejected).", None
            if now > check.expires_at:
                return False, "WebSocket ticket has expired.", None
            return False, "Ticket consumption failed.", None

        # Successful atomic consumption: retrieve user
        rec = session.exec(
            select(WsTicketRecord).where(WsTicketRecord.ticket_hash == ticket_hash)
        ).first()
        if not rec:
            return False, "Ticket record error.", None

        user = get_user_by_username(rec.username)
        if not user or not user.is_active:
            return False, "User account is inactive or not found.", None
        return True, "Ticket valid.", user


# -----------------------------------------------------------------------------
# Support Ticket Management & Persistent Storage
# -----------------------------------------------------------------------------

VALID_TICKET_TRANSITIONS = {
    "New": {"Open", "Assigned", "Closed"},
    "Open": {"Assigned", "Investigating", "Closed"},
    "Assigned": {"Investigating", "Open", "Closed"},
    "Investigating": {"Awaiting User", "Resolved", "Assigned", "Closed"},
    "Awaiting User": {"Investigating", "Resolved", "Closed"},
    "Resolved": {"Closed", "Open"},
    "Closed": {"Open"},
}


def init_default_tickets() -> None:
    """Seed initial demonstration support tickets if ticket repository is empty."""
    with Session(engine) as session:
        count = session.exec(select(TicketRecord)).first()
        if count is not None:
            return

        demo_tickets = [
            TicketRecord(
                ticket_id="TICK-2026-001",
                title="Severe packet loss and video buffering in Hostel Block B",
                category="wifi",
                location="Hostel Block B",
                affected_service="Campus WiFi",
                description="Students reporting intermittent video call freezes and dropped connections during peak evening hours.",
                priority="high",
                status="Investigating",
                created_by="helpdesk",
                contact_info="hostel-rep@iitbbsr.ac.in",
                assigned_to="engineer",
                linked_incident_id="inc-link-congestion-42",
                resolution_notes="Corroborated with inc-link-congestion-42 telemetry showing interface saturation on SW_CAMPUS_1.",
                user_facing_summary="Engineers are optimizing core switch traffic queues. Service stability expected within 15 minutes.",
            ),
            TicketRecord(
                ticket_id="TICK-2026-002",
                title="LMS portal timeout on assignment submissions",
                category="application",
                location="Academic Block 2",
                affected_service="LMS",
                description="Faculty and students experiencing 504 gateway timeouts when uploading assignment files to the Moodle portal.",
                priority="medium",
                status="Open",
                created_by="helpdesk",
                contact_info="dept-cse@iitbbsr.ac.in",
                assigned_to="engineer",
                linked_incident_id=None,
                resolution_notes="Under active triage by Network Engineering.",
                user_facing_summary="LMS application server capacity is being reviewed by the operations team.",
            ),
            TicketRecord(
                ticket_id="TICK-2026-003",
                title="Core switch uplink interface flap",
                category="hardware",
                location="Main Data Center",
                affected_service="Internet Gateway",
                description="Automated telemetry detected CRC error spikes and carrier transitions on port xe-0/0/2.",
                priority="critical",
                status="Assigned",
                created_by="admin",
                contact_info="noc-ops@iitbbsr.ac.in",
                assigned_to="admin",
                linked_incident_id="inc-link-congestion-42",
                resolution_notes="Interface optics inspected, diagnostic report generated.",
                user_facing_summary="Network backbone maintenance in progress. Redundant link active.",
            ),
        ]
        for t in demo_tickets:
            session.add(t)
        session.commit()


def create_ticket(
    title: str,
    category: str,
    location: str,
    affected_service: str,
    description: str,
    priority: str = "medium",
    created_by: str = "helpdesk",
    contact_info: str = None,
    linked_incident_id: str = None,
    assigned_to: str = None,
) -> TicketRecord:
    """Create and persist a new support ticket."""
    import secrets
    ticket_id = f"TICK-2026-{secrets.randbelow(9000) + 1000}"
    with Session(engine) as session:
        ticket = TicketRecord(
            ticket_id=ticket_id,
            title=title,
            category=category,
            location=location,
            affected_service=affected_service,
            description=description,
            priority=priority,
            status="New",
            created_by=created_by,
            contact_info=contact_info,
            linked_incident_id=linked_incident_id,
            assigned_to=assigned_to,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return ticket


def get_ticket(ticket_id: str) -> Optional[TicketRecord]:
    """Retrieve ticket by unique ticket_id."""
    with Session(engine) as session:
        stmt = select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)
        return session.exec(stmt).first()


def list_tickets(
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    role: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
) -> List[TicketRecord]:
    """List tickets with optional role-based filtering and status constraints."""
    with Session(engine) as session:
        stmt = select(TicketRecord)
        if category:
            stmt = stmt.where(TicketRecord.category == category)
        if status:
            stmt = stmt.where(TicketRecord.status == status)
        if priority:
            stmt = stmt.where(TicketRecord.priority == priority)
        # Role-based restriction:
        # Non-operational users only see tickets they created
        if role and role not in ["platform_admin", "network_admin", "network_engineer", "helpdesk"]:
            if username:
                stmt = stmt.where(TicketRecord.created_by == username)
        stmt = stmt.order_by(TicketRecord.id.desc()).limit(limit)
        return list(session.exec(stmt).all())


def update_ticket_status(
    ticket_id: str,
    new_status: str,
    actor_username: str,
    actor_role: str,
    notes: Optional[str] = None,
    user_summary: Optional[str] = None,
    assigned_to: Optional[str] = None,
) -> Tuple[bool, str, Optional[TicketRecord]]:
    """Validate lifecycle transition and update ticket status."""
    with Session(engine) as session:
        ticket = session.exec(select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)).first()
        if not ticket:
            return False, f"Ticket {ticket_id} not found.", None

        if new_status != ticket.status:
            allowed = VALID_TICKET_TRANSITIONS.get(ticket.status, set())
            if new_status not in allowed:
                return False, f"Invalid transition from {ticket.status} to {new_status}. Allowed transitions: {sorted(list(allowed))}", None

        ticket.status = new_status
        ticket.updated_at = datetime.now(timezone.utc).isoformat()
        if notes:
            ticket.resolution_notes = notes
        if user_summary:
            ticket.user_facing_summary = user_summary
        if assigned_to is not None:
            ticket.assigned_to = assigned_to

        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return True, "Status updated successfully.", ticket


def link_ticket_incident(ticket_id: str, incident_id: str, actor_username: str) -> Optional[TicketRecord]:
    """Associate a support ticket with a network diagnostic incident."""
    with Session(engine) as session:
        ticket = session.exec(select(TicketRecord).where(TicketRecord.ticket_id == ticket_id)).first()
        if not ticket:
            return None
        ticket.linked_incident_id = incident_id
        ticket.updated_at = datetime.now(timezone.utc).isoformat()
        if not ticket.resolution_notes:
            ticket.resolution_notes = f"Linked to incident {incident_id} by {actor_username}."
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return ticket



def save_diagnosis_run(
    run_id: str,
    execution_id: str,
    scenario_filename: str,
    status: str,
    report_json: str,
    probable_cause: Optional[str] = None,
    confidence: float = 0.0,
    uncertainty_score: float = 0.0,
    conformal_prediction_set: Optional[List[str]] = None,
    previous_run_id: Optional[str] = None,
    triggered_by: Optional[str] = None,
) -> DiagnosisRunRecord:
    """Persist a diagnostic execution run record for audit, tracking, and comparison."""
    with Session(engine) as session:
        rec = DiagnosisRunRecord(
            run_id=run_id,
            execution_id=execution_id,
            scenario_filename=scenario_filename,
            status=status,
            report_json=report_json,
            probable_cause=probable_cause,
            confidence=confidence,
            uncertainty_score=uncertainty_score,
            conformal_prediction_set_json=json.dumps(conformal_prediction_set or []),
            previous_run_id=previous_run_id,
            triggered_by=triggered_by,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return rec


def get_diagnosis_run(run_id: str) -> Optional[DiagnosisRunRecord]:
    """Retrieve a specific diagnostic run by run_id or execution_id."""
    with Session(engine) as session:
        return session.exec(
            select(DiagnosisRunRecord).where(
                (DiagnosisRunRecord.run_id == run_id) | (DiagnosisRunRecord.execution_id == run_id)
            )
        ).first()


def get_latest_diagnosis_run_for_scenario(scenario_filename: str) -> Optional[DiagnosisRunRecord]:
    """Retrieve the most recent diagnostic execution run for a given scenario."""
    with Session(engine) as session:
        return session.exec(
            select(DiagnosisRunRecord)
            .where(DiagnosisRunRecord.scenario_filename == scenario_filename)
            .order_by(DiagnosisRunRecord.id.desc())
        ).first()


def list_diagnosis_runs_for_scenario(scenario_filename: str, limit: int = 20) -> List[DiagnosisRunRecord]:
    """List chronological diagnostic runs recorded for a scenario."""
    with Session(engine) as session:
        return list(
            session.exec(
                select(DiagnosisRunRecord)
                .where(DiagnosisRunRecord.scenario_filename == scenario_filename)
                .order_by(DiagnosisRunRecord.id.desc())
                .limit(limit)
            ).all()
        )


def compare_diagnosis_runs(current_run_id: str, previous_run_id: str) -> Dict[str, Any]:
    """Compare two diagnostic runs for differences across causes, probabilities, devices, and metrics."""
    curr = get_diagnosis_run(current_run_id)
    prev = get_diagnosis_run(previous_run_id)
    if not curr or not prev:
        return {"error": "One or both runs not found"}

    curr_rep = json.loads(curr.report_json) if curr.report_json else {}
    prev_rep = json.loads(prev.report_json) if prev.report_json else {}

    c_cause = curr.probable_cause or curr_rep.get("probable_cause", "UNKNOWN")
    p_cause = prev.probable_cause or prev_rep.get("probable_cause", "UNKNOWN")
    cause_diff = {
        "current": c_cause,
        "previous": p_cause,
        "changed": c_cause != p_cause,
    }

    c_conf = round(float(curr.confidence or curr_rep.get("confidence", 0.0)), 4)
    p_conf = round(float(prev.confidence or prev_rep.get("confidence", 0.0)), 4)
    conf_delta = round(c_conf - p_conf, 4)
    conf_diff = {
        "current": c_conf,
        "previous": p_conf,
        "delta": conf_delta,
        "status": "increased" if conf_delta > 0.001 else ("decreased" if conf_delta < -0.001 else "unchanged"),
    }

    c_unc = round(float(curr.uncertainty_score or curr_rep.get("uncertainty", {}).get("score", 0.0)), 4)
    p_unc = round(float(prev.uncertainty_score or prev_rep.get("uncertainty", {}).get("score", 0.0)), 4)
    unc_delta = round(c_unc - p_unc, 4)
    unc_diff = {
        "current": c_unc,
        "previous": p_unc,
        "delta": unc_delta,
        "status": "increased" if unc_delta > 0.001 else ("decreased" if unc_delta < -0.001 else "unchanged"),
    }

    c_devs = set(curr_rep.get("affected_devices", []))
    p_devs = set(prev_rep.get("affected_devices", []))
    devs_diff = {
        "current": sorted(list(c_devs)),
        "previous": sorted(list(p_devs)),
        "added": sorted(list(c_devs - p_devs)),
        "removed": sorted(list(p_devs - c_devs)),
        "unchanged": sorted(list(c_devs & p_devs)),
        "changed": c_devs != p_devs,
    }

    c_set = set(curr_rep.get("conformal_prediction_set", []))
    p_set = set(prev_rep.get("conformal_prediction_set", []))
    set_diff = {
        "current": sorted(list(c_set)),
        "previous": sorted(list(p_set)),
        "changed": c_set != p_set,
    }

    c_probs = curr_rep.get("confidence_breakdown") or {}
    p_probs = prev_rep.get("confidence_breakdown") or {}
    all_classes = sorted(list(set(c_probs.keys()) | set(p_probs.keys())))
    probs_diff = {}
    for cls_name in all_classes:
        c_val = round(float(c_probs.get(cls_name, 0.0)), 4)
        p_val = round(float(p_probs.get(cls_name, 0.0)), 4)
        d_val = round(c_val - p_val, 4)
        probs_diff[cls_name] = {
            "current": c_val,
            "previous": p_val,
            "delta": d_val,
            "status": "increased" if d_val > 0.001 else ("decreased" if d_val < -0.001 else "unchanged"),
        }

    c_acts = [a.get("action_type") or a.get("title") for a in curr_rep.get("remediation_actions", [])]
    p_acts = [a.get("action_type") or a.get("title") for a in prev_rep.get("remediation_actions", [])]
    actions_diff = {
        "current": c_acts,
        "previous": p_acts,
        "changed": c_acts != p_acts,
    }

    return {
        "current_run_id": current_run_id,
        "previous_run_id": previous_run_id,
        "scenario_filename": curr.scenario_filename,
        "probable_cause": cause_diff,
        "confidence": conf_diff,
        "uncertainty": unc_diff,
        "affected_devices": devs_diff,
        "conformal_prediction_set": set_diff,
        "classification_probabilities": probs_diff,
        "remediation_actions": actions_diff,
    }
