"""SQLModel database models for incident persistence, audit logs, and user authentication."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class IncidentRecord(SQLModel, table=True):
    """Persisted network incident diagnostic session."""

    __tablename__ = "incidents"

    incident_id: str = Field(primary_key=True)
    network_id: str = Field(index=True)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = Field(default="pending", index=True)  # pending, diagnosed, insufficient_evidence, remediated, paused
    probable_cause: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0)
    report_json: Optional[str] = Field(default=None)
    state_blob: Optional[str] = Field(default=None)
    assigned_to: Optional[str] = Field(default=None, index=True)
    assigned_by: Optional[str] = Field(default=None)
    assigned_at: Optional[str] = Field(default=None)


class EnvelopeLog(SQLModel, table=True):
    """Auditable log entry for every inter-agent envelope message."""

    __tablename__ = "envelope_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    correlation_id: str = Field(index=True)
    message_id: str = Field(index=True)
    timestamp_utc: str = Field(index=True)
    sender: str = Field(index=True)
    recipient: str = Field(index=True)
    message_type: str = Field(index=True)
    priority: str = Field(default="normal")
    payload_json: str
    context_json: Optional[str] = Field(default=None)


class RemediationLog(SQLModel, table=True):
    """Auditable log of simulated remediation actions and operator approvals."""

    __tablename__ = "remediation_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(index=True)
    action_id: str = Field(index=True)
    device: str
    commands_json: str
    rollback_commands_json: str
    risk_level: str
    status: str = Field(default="pending")  # pending, approved, rejected, modified, simulated_executed
    approved_by: Optional[str] = Field(default=None)
    actor_user_id: Optional[str] = Field(default=None, index=True)
    actor_username: Optional[str] = Field(default=None, index=True)
    actor_role: Optional[str] = Field(default=None, index=True)
    decision: Optional[str] = Field(default=None, index=True)
    rationale: Optional[str] = Field(default=None)
    modified_commands_json: Optional[str] = Field(default=None)
    simulated_at: Optional[str] = Field(default=None)
    decision_timestamp: Optional[str] = Field(default=None)


class OrchestratorCheckpoint(SQLModel, table=True):
    """Persisted checkpoint of LangGraph orchestrator state for pause and resume."""

    __tablename__ = "orchestrator_checkpoints"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    node_name: str = Field(index=True)
    iteration: int = Field(default=0)
    state_json: str
    is_paused: bool = Field(default=False)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserRecord(SQLModel, table=True):
    """Persisted user account record for authentication and server-side RBAC."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    role: str = Field(index=True)
    full_name: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuthAuditLog(SQLModel, table=True):
    """Auditable log of authentication, authorization, and security events."""

    __tablename__ = "auth_audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), index=True)
    event_type: str = Field(index=True)  # LOGIN_SUCCESS, LOGIN_FAILURE, ACCESS_DENIED, TOKEN_EXPIRED, TOKEN_REVOKED
    username: Optional[str] = Field(default=None, index=True)
    user_id: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default=None)
    endpoint: Optional[str] = Field(default=None)
    client_ip: Optional[str] = Field(default=None)
    details: Optional[str] = Field(default=None)


class RevokedToken(SQLModel, table=True):
    """Persisted revoked JWT access tokens for server-side logout and session invalidation."""

    __tablename__ = "revoked_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    jti: str = Field(unique=True, index=True)
    revoked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = Field(default=None)
