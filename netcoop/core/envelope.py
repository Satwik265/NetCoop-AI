"""Inter-agent protocol envelope and message payload models conforming to schema v1.0."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


class AgentRole(str, Enum):
    """Recognized sender and recipient roles in the multi-agent network."""

    ORCHESTRATOR = "orchestrator"
    TELEMETRY_AGENT = "telemetry_agent"
    TOPOLOGY_AGENT = "topology_agent"
    CONFIG_AGENT = "config_agent"
    LOG_AGENT = "log_agent"
    SYNTHESIZER_AGENT = "synthesizer_agent"
    CLASSIFIER_AGENT = "classifier_agent"
    HUMAN_OPERATOR = "human_operator"
    BROADCAST = "broadcast"


class MessageType(str, Enum):
    """Functional categorization of envelope payloads."""

    TELEMETRY_DISPATCH = "telemetry_dispatch"
    FINDING_SUBMISSION = "finding_submission"
    INQUIRY_REQUEST = "inquiry_request"
    INQUIRY_RESPONSE = "inquiry_response"
    CONFLICT_NOTIFICATION = "conflict_notification"
    SYNTHESIS_SUBMISSION = "synthesis_submission"
    PROTOCOL_ERROR = "protocol_error"


class Priority(str, Enum):
    """Processing urgency for envelope queues."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ObservationCategory(str, Enum):
    """Classification of raw empirical observations."""

    METRIC_ANOMALY = "metric_anomaly"
    TOPOLOGY_CHANGE = "topology_change"
    CONFIG_DIFF = "config_diff"
    LOG_PATTERN = "log_pattern"
    STATE_TRANSITION = "state_transition"


class Severity(str, Enum):
    """Severity rating for findings and observations."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ProtocolHeader(BaseModel):
    """Metadata header routing the agent envelope."""

    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sender: AgentRole
    recipient: AgentRole
    schema_version: str = "1.0.0"
    message_type: MessageType
    priority: Priority = Priority.NORMAL

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        """Enforce semantic versioning matching 1.x.x."""
        if not v.startswith("1."):
            raise ValueError(f"Incompatible schema version: {v}. Expected 1.x.x")
        return v


class NetworkScope(BaseModel):
    """Network target boundary for the incident."""

    network_id: str
    devices: List[str]
    interfaces: List[str] = Field(default_factory=list)


class Observation(BaseModel):
    """An empirical observation discovered by a specialist agent."""

    observation_id: str = Field(default_factory=lambda: f"obs-{uuid4().hex[:8]}")
    category: ObservationCategory
    entity: str  # e.g., 'spine-01:et-0/0/1' or 'leaf-02'
    metric_name: str
    observed_value: Union[float, int, str, bool, None]
    baseline_value: Union[float, int, str, bool, None] = None
    unit: str
    severity: Severity
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    data_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        """Ensure standard SI or telemetry unit representation with alias mapping."""
        unit_map = {
            "%": "percent",
            "pct": "percent",
            "percentage": "percent",
            "sec": "s",
            "seconds": "s",
            "second": "s",
            "millisecond": "ms",
            "milliseconds": "ms",
        }
        val = unit_map.get(v.lower().strip(), v.lower().strip())
        valid_units = {
            "bps",
            "kbps",
            "mbps",
            "gbps",
            "bytes",
            "octets",
            "packets",
            "pkts",
            "frames",
            "ms",
            "s",
            "us",
            "dbm",
            "percent",
            "count",
            "flaps_per_minute",
            "ratio",
            "boolean",
            "text",
        }
        if val not in valid_units:
            raise ValueError(
                f"Unknown unit '{v}'. Allowed units include: {sorted(list(valid_units))}"
            )
        return val


class Hypothesis(BaseModel):
    """Diagnostic fault hypothesis proposed by an agent."""

    hypothesis_id: str = Field(default_factory=lambda: f"hyp-{uuid4().hex[:8]}")
    probable_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_observation_ids: List[str]
    refuting_observation_ids: List[str] = Field(default_factory=list)
    required_corroboration: List[str] = Field(default_factory=list)
    provenance: Optional[Dict[str, Any]] = None
    data_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class Inquiry(BaseModel):
    """Cross-agent question for targeted corroboration."""

    inquiry_id: str = Field(default_factory=lambda: f"inq-{uuid4().hex[:8]}")
    target_agent: AgentRole
    question: str
    target_entity: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    answer: Optional[Union[str, Dict[str, Any]]] = None
    provenance: Optional[Dict[str, Any]] = None


class ProtocolErrorDetail(BaseModel):
    """Structured protocol error information."""

    error_code: str
    message: str
    field_path: Optional[str] = None


class EnvelopePayload(BaseModel):
    """Functional payload enclosed within an agent envelope."""

    scope: NetworkScope
    observations: List[Observation] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    inquiries: List[Inquiry] = Field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None
    error: Optional[ProtocolErrorDetail] = None
    data_quality: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None


class AgentEnvelope(BaseModel):
    """Standardized inter-agent envelope for all NetCoop communications."""

    header: ProtocolHeader
    payload: EnvelopePayload
    context: Dict[str, Any] = Field(
        default_factory=lambda: {"iteration": 0, "environment": "simulation"}
    )

    def to_json(self) -> str:
        """Serialize envelope to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def create_error_response(
        cls,
        original: "AgentEnvelope",
        error_code: str,
        message: str,
        field_path: Optional[str] = None,
    ) -> "AgentEnvelope":
        """Generate a corresponding protocol_error envelope."""
        return cls(
            header=ProtocolHeader(
                correlation_id=original.header.correlation_id,
                sender=AgentRole.ORCHESTRATOR,
                recipient=original.header.sender,
                message_type=MessageType.PROTOCOL_ERROR,
                priority=Priority.HIGH,
            ),
            payload=EnvelopePayload(
                scope=original.payload.scope,
                error=ProtocolErrorDetail(
                    error_code=error_code,
                    message=message,
                    field_path=field_path,
                ),
            ),
            context={"iteration": original.context.get("iteration", 0)},
        )
