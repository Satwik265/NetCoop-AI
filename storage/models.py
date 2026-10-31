"""SQLModel database models for incident persistence and auditable envelope traces."""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class IncidentRecord(SQLModel, table=True):
    """Persisted network incident diagnostic session."""

    __tablename__ = "incidents"

    incident_id: str = Field(primary_key=True)
    network_id: str = Field(index=True)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = Field(default="pending", index=True)  # pending, diagnosed, insufficient_evidence, remediated
    probable_cause: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0)
    report_json: Optional[str] = Field(default=None)
    state_blob: Optional[str] = Field(default=None)


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
    status: str = Field(default="pending_approval")  # pending_approval, approved, simulated_executed, rejected
    approved_by: Optional[str] = Field(default=None)
    simulated_at: Optional[str] = Field(default=None)

