"""Unified JSON diagnostic report generator conforming to schemas/diagnostic_report.json."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from netcoop.core.evidence import DiagnosticHypothesis, EvidenceItem, UncertaintyEvaluation


class RemediationActionItem(BaseModel):
    """Simulated remediation step."""

    action_id: str
    title: str
    description: str
    device: str
    commands: List[str]
    rollback_commands: List[str]
    risk_level: str = "medium"  # low, medium, high
    blast_radius_devices: List[str] = Field(default_factory=list)
    is_simulated: bool = True
    status: str = "recommended"  # recommended, pending_approval, simulated_success, rejected


class UnifiedDiagnosticReport(BaseModel):
    """Unified JSON diagnostic report specification."""

    incident_id: str
    network_id: str
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str  # diagnosed, insufficient_evidence, inconclusive, benign
    probable_cause: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    affected_devices: List[str] = Field(default_factory=list)
    affected_interfaces: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    uncertainty: UncertaintyEvaluation
    remediation_actions: List[RemediationActionItem] = Field(default_factory=list)
    summary: str = ""
    processing_time_ms: float = 0.0

    def to_json(self) -> str:
        """Serialize report to formatted JSON string."""
        return self.model_dump_json(indent=2)


class ReportBuilder:
    """Builds and serializes unified diagnostic reports."""

    @classmethod
    def build_report(
        cls,
        incident_id: str,
        network_id: str,
        status: str,
        hypothesis: Optional[DiagnosticHypothesis],
        uncertainty: UncertaintyEvaluation,
        remediation_actions: Optional[List[RemediationActionItem]] = None,
        summary: Optional[str] = None,
        processing_time_ms: float = 0.0,
    ) -> UnifiedDiagnosticReport:
        """Construct a standardized UnifiedDiagnosticReport."""
        evidence_dicts: List[Dict[str, Any]] = []
        affected_devices: List[str] = []
        affected_interfaces: List[str] = []
        probable_cause = None
        confidence = 0.0

        if hypothesis and status == "diagnosed":
            probable_cause = hypothesis.title
            confidence = hypothesis.final_confidence
            affected_devices = hypothesis.affected_devices
            affected_interfaces = hypothesis.affected_interfaces
            for ev in hypothesis.supporting_evidence:
                evidence_dicts.append(ev.model_dump())
        elif status == "insufficient_evidence":
            probable_cause = None
            confidence = 0.0
            if summary is None:
                summary = (
                    "Insufficient evidence to isolate root cause. "
                    "Observed anomalies lack required cross-domain corroboration."
                )

        if summary is None:
            if status == "diagnosed" and hypothesis:
                summary = (
                    f"Diagnosed {hypothesis.title} with {int(confidence * 100)}% confidence. "
                    f"Affecting devices: {', '.join(affected_devices)}."
                )
            else:
                summary = f"Incident status: {status}."

        return UnifiedDiagnosticReport(
            incident_id=incident_id,
            network_id=network_id,
            status=status,
            probable_cause=probable_cause,
            confidence=confidence,
            affected_devices=affected_devices,
            affected_interfaces=affected_interfaces,
            evidence=evidence_dicts,
            uncertainty=uncertainty,
            remediation_actions=remediation_actions or [],
            summary=summary,
            processing_time_ms=processing_time_ms,
        )

