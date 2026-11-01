"""Pydantic models for the two-level Network Diagnostic Report.

Defines:
- Level 1: Executive Report (operational summary, health observations, advisory recommendations)
- Level 2: Technical Report (extensible technical sections, evidence records, calibration, audit)
- NetworkDiagnosticReport: Versioned root container model adhering to NetCoop AI contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class DiagnosticStatus(str, Enum):
    """Categorical diagnostic outcome."""

    DIAGNOSED = "diagnosed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCONCLUSIVE = "inconclusive"
    ABSTAINED = "abstained"
    BENIGN = "benign"


class ReportSeverity(str, Enum):
    """Incident severity classification."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AgentState(str, Enum):
    """Execution state of a diagnostic agent."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RootCauseStatus(str, Enum):
    """Verification classification of the root-cause finding."""

    VERIFIED = "verified"
    PROBABLE = "probable"
    UNVERIFIED_HYPOTHESIS = "unverified_hypothesis"
    INCONCLUSIVE = "inconclusive"
    ABSTAINED = "abstained"


class RemediationState(str, Enum):
    """State of a recommended remediation action."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    SIMULATED = "simulated"
    BLOCKED = "blocked"
    VERIFIED = "verified"
    REJECTED = "rejected"


class RecoveryStatus(str, Enum):
    """Post-incident network recovery verification status."""

    PENDING_VERIFICATION = "pending_verification"
    RECOVERED = "recovered"
    NOT_RECOVERED = "not_recovered"
    NOT_APPLICABLE = "not_applicable"


class MetricObservation(BaseModel):
    """Individual empirical metric observation with explicit provenance.

    Missing or uncollected metrics must be represented with value=None,
    never fabricated or defaulted to zero.
    """

    metric_name: str
    value: Optional[Union[float, int, str, bool]] = None
    unit: Optional[str] = None
    entity: Optional[str] = None
    source: str = "telemetry_agent"
    timestamp: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    severity: ReportSeverity = ReportSeverity.INFO
    is_available: bool = True

    @field_validator("is_available", mode="before")
    @classmethod
    def sync_availability(cls, v: Any, info: Any) -> bool:
        """If value is explicitly None, ensure is_available is False unless explicitly forced."""
        values = info.data
        if "value" in values and values["value"] is None:
            return False
        return bool(v)


class EvidenceRecord(BaseModel):
    """Traceable evidence datum supporting or refuting a hypothesis."""

    evidence_id: str = Field(default_factory=lambda: f"evi-{uuid4().hex[:8]}")
    source_agent: str
    category: str
    finding: str
    entity: str
    metric_name: Optional[str] = None
    value: Optional[Union[float, int, str, bool]] = None
    unit: Optional[str] = None
    severity: ReportSeverity = ReportSeverity.WARNING
    timestamp: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


class AgentInvestigationRecord(BaseModel):
    """Audit record of an agent's participation in the diagnostic workflow."""

    agent_role: str
    agent_name: str
    status: AgentState = AgentState.QUEUED
    execution_time_ms: Optional[float] = None
    observations_count: int = 0
    findings_summary: Optional[str] = None
    error_message: Optional[str] = None


class RecommendedAction(BaseModel):
    """Advisory remediation proposal.

    Remediation actions are strictly advisory and simulated. They must not
    be mistaken for executed changes to a production network.
    """

    action_id: str
    title: str
    description: str
    target_device: str
    commands: List[str] = Field(default_factory=list)
    rollback_commands: List[str] = Field(default_factory=list)
    risk_level: str = "medium"  # low, medium, high
    blast_radius_devices: List[str] = Field(default_factory=list)
    is_simulated: bool = True
    status: RemediationState = RemediationState.PROPOSED
    is_advisory: bool = True
    advisory_notice: str = (
        "Action is advisory and simulated only. No production network change has occurred."
    )


class CampusTopologyReference(BaseModel):
    """Demonstration topology linkage adhering to IITBBSR campus schema."""

    campus_id: Optional[str] = None
    affected_node_ids: List[str] = Field(default_factory=list)
    affected_site_ids: List[str] = Field(default_factory=list)
    affected_site_names: List[str] = Field(default_factory=list)
    affected_path_ids: List[str] = Field(default_factory=list)
    topology_provenance: Optional[Dict[str, Any]] = None
    simulated_inventory: bool = True
    disclaimer: str = (
        "All network equipment, nodes, links, and paths are synthetic demonstration inventory. "
        "Official campus maps establish physical building landmarks only and contain zero network routing equipment records."
    )


class ConfidenceCalibrationData(BaseModel):
    """Calibration and uncertainty metrics for scientific defensibility."""

    rules_score: Optional[float] = None
    raw_rules_score: Optional[float] = None
    model_score: Optional[float] = None
    blended_score: Optional[float] = None
    calibrated_confidence: Optional[float] = None
    calibration_method: Optional[str] = None
    conformal_prediction_set: List[str] = Field(default_factory=list)
    confidence_category: Optional[str] = None
    is_calibrated: bool = False
    notes: Optional[str] = None


class AuditReference(BaseModel):
    """Traceability references linking report to persistent SQLite storage."""

    audit_logged: bool = False
    storage_engine: Optional[str] = None
    incident_record_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    envelope_count: int = 0
    replay_trace_id: Optional[str] = None
    notes: Optional[str] = None


class ExecutiveReport(BaseModel):
    """Level 1: Concise operational summary for operations leadership and incident commanders."""

    report_id: str
    incident_id: str
    generated_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    diagnostic_status: DiagnosticStatus
    severity: ReportSeverity = ReportSeverity.INFO
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Diagnostic confidence when genuinely available; None when abstained or insufficient evidence.",
    )
    confidence_category: Optional[str] = None
    is_confidence_calibrated: bool = False
    confidence_type: Optional[str] = None
    affected_devices: List[str] = Field(default_factory=list)
    affected_site_ids: List[str] = Field(default_factory=list)
    affected_site_names: List[str] = Field(default_factory=list)
    affected_sites: List[str] = Field(default_factory=list)
    probable_root_cause: Optional[str] = Field(
        default=None,
        description="Probable root cause title or null if diagnosis abstained or inconclusive.",
    )
    root_cause_status: RootCauseStatus = RootCauseStatus.PROBABLE
    executive_summary: str
    key_observations: List[MetricObservation] = Field(default_factory=list)
    supporting_evidence_summary: str = ""
    agent_investigation_status: List[AgentInvestigationRecord] = Field(
        default_factory=list
    )
    recommended_actions: List[RecommendedAction] = Field(default_factory=list)
    recovery_verification_status: RecoveryStatus = RecoveryStatus.PENDING_VERIFICATION
    data_provenance: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class TechnicalSection(BaseModel):
    """Extensible section container for Level 2 technical diagnostic findings."""

    section_id: str
    title: str
    order: int
    is_available: bool = True
    summary: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class TechnicalReport(BaseModel):
    """Level 2: Comprehensive, traceable technical report for network engineering analysis."""

    sections: List[TechnicalSection] = Field(default_factory=list)

    def get_section(self, section_id: str) -> Optional[TechnicalSection]:
        """Retrieve a specific technical section by identifier."""
        for sec in self.sections:
            if sec.section_id == section_id:
                return sec
        return None

    def add_section(self, section: TechnicalSection) -> None:
        """Add or replace a technical section."""
        for idx, sec in enumerate(self.sections):
            if sec.section_id == section.section_id:
                self.sections[idx] = section
                return
        self.sections.append(section)
        self.sections.sort(key=lambda s: s.order)


class NetworkDiagnosticReport(BaseModel):
    """Versioned root container combining Executive (Level 1) and Technical (Level 2) views."""

    schema_version: str = "2.0.0"
    report_id: str
    incident_id: str
    network_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    executive: ExecutiveReport
    technical: TechnicalReport
    topology_reference: Optional[CampusTopologyReference] = None
    audit: Optional[AuditReference] = None

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON string."""
        return self.model_dump_json(indent=indent)

    def to_markdown(self) -> str:
        """Render a clean monochrome markdown report containing both levels."""
        lines = [
            f"# Network Diagnostic Report: {self.incident_id}",
            "",
            f"**Report ID**: `{self.report_id}`  ",
            f"**Network ID**: `{self.network_id}`  ",
            f"**Generated At (UTC)**: `{self.created_at}`  ",
            f"**Schema Version**: `{self.schema_version}`  ",
            "",
            "---",
            "",
            "## Level 1: Executive Summary",
            "",
            f"- **Diagnostic Status**: {self.executive.diagnostic_status.value.upper()}",
            f"- **Incident Severity**: {self.executive.severity.value.upper()}",
            f"- **Probable Root Cause**: {self.executive.probable_root_cause or 'None (Abstained / Inconclusive)'}",
            f"- **Root Cause Status**: {self.executive.root_cause_status.value}",
        ]

        if self.executive.confidence is not None:
            cat_str = f" ({self.executive.confidence_category})" if self.executive.confidence_category else ""
            calib_str = " [Calibrated Probability]" if self.executive.is_confidence_calibrated else " [Uncalibrated Heuristic]"
            lines.append(f"- **Confidence**: {self.executive.confidence:.2%}{cat_str}{calib_str}")
        else:
            lines.append("- **Confidence**: N/A (Abstained / Insufficient Evidence)")

        lines.extend([
            f"- **Recovery Status**: {self.executive.recovery_verification_status.value}",
            f"- **Affected Devices**: {', '.join(self.executive.affected_devices) if self.executive.affected_devices else 'None'}",
            f"- **Affected Site IDs**: {', '.join(self.executive.affected_site_ids) if self.executive.affected_site_ids else 'None'}",
            f"- **Affected Campus Sites**: {', '.join(self.executive.affected_site_names) if self.executive.affected_site_names else 'None'}",
            "",
            f"> {self.executive.executive_summary}",
            "",
        ])

        if self.executive.key_observations:
            lines.extend([
                "### Key Network-Health Observations",
                "",
                "| Metric | Entity | Observed Value | Severity | Available | Source |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ])
            for obs in self.executive.key_observations:
                val_str = f"{obs.value} {obs.unit or ''}".strip() if obs.is_available and obs.value is not None else "Unavailable"
                lines.append(
                    f"| {obs.metric_name} | {obs.entity or '-'} | {val_str} | {obs.severity.value} | {obs.is_available} | {obs.source} |"
                )
            lines.append("")

        if self.executive.agent_investigation_status:
            lines.extend([
                "### Agent Investigation Status",
                "",
                "| Agent | Role | Status | Exec Time | Findings |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ])
            for ag in self.executive.agent_investigation_status:
                t_str = f"{ag.execution_time_ms:.1f} ms" if ag.execution_time_ms is not None else "-"
                lines.append(
                    f"| {ag.agent_name} | {ag.agent_role} | {ag.status.value} | {t_str} | {ag.findings_summary or '-'} |"
                )
            lines.append("")

        if self.executive.recommended_actions:
            lines.extend([
                "### Advisory Recommended Actions (Simulation Only)",
                "",
                "| Action ID | Target Device | Risk Level | Description | Status |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ])
            for act in self.executive.recommended_actions:
                lines.append(
                    f"| `{act.action_id}` | `{act.target_device}` | {act.risk_level.upper()} | {act.title} | {act.status.value} |"
                )
            lines.append("")
            lines.append(f"*{self.executive.recommended_actions[0].advisory_notice}*")
            lines.append("")

        if self.topology_reference:
            lines.extend([
                "### Demonstration Topology Reference",
                "",
                f"- **Campus ID**: {self.topology_reference.campus_id or 'iitbbsr_argul_campus'}",
                f"- **Affected Nodes**: {', '.join(self.topology_reference.affected_node_ids) if self.topology_reference.affected_node_ids else 'None'}",
                f"- **Affected Site IDs**: {', '.join(self.topology_reference.affected_site_ids) if self.topology_reference.affected_site_ids else 'None'}",
                f"- **Affected Site Names**: {', '.join(self.topology_reference.affected_site_names) if self.topology_reference.affected_site_names else 'None'}",
                f"- **Affected Paths**: {', '.join(self.topology_reference.affected_path_ids) if self.topology_reference.affected_path_ids else 'None'}",
                f"- **Simulated Inventory**: {self.topology_reference.simulated_inventory}",
                "",
                f"*{self.topology_reference.disclaimer}*",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Level 2: Technical Diagnostic Details",
            "",
        ])

        for sec in self.technical.sections:
            avail_tag = "" if sec.is_available else " [Unavailable / Not Collected]"
            lines.append(f"### {sec.order}. {sec.title}{avail_tag}")
            if sec.summary:
                lines.append(f"\n{sec.summary}\n")
            lines.append("```json")
            import json
            lines.append(json.dumps(sec.data, indent=2))
            lines.append("```\n")

        return "\n".join(lines)
