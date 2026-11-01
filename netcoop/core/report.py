"""Unified JSON diagnostic report generator conforming to schemas/diagnostic_report.json."""

import time
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

    # Additive fields for multi-agent reasoning, arbitration & auditability
    causal_chain: List[str] = Field(default_factory=list)
    conflicts_resolved: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    confidence_breakdown: Optional[Dict[str, float]] = None
    conformal_prediction_set: List[str] = Field(default_factory=list)
    confidence_category: Optional[str] = None
    hypothesis_key: Optional[str] = None

    def to_json(self) -> str:
        """Serialize report to formatted JSON string."""
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        """Render a clean monochrome markdown report."""
        lines = [
            f"# Diagnostic Incident Report: {self.incident_id}",
            "",
            "## Summary",
            f"- Network ID: {self.network_id}",
            f"- Timestamp (UTC): {self.timestamp_utc}",
            f"- Diagnostic Status: {self.status.upper()}",
            f"- Probable Cause: {self.probable_cause or 'None (insufficient evidence)'}",
            f"- Confidence: {self.confidence:.2%}",
            f"- Processing Time: {self.processing_time_ms:.1f} ms",
            "",
            f"> {self.summary}",
            "",
        ]

        if self.affected_devices or self.affected_interfaces:
            lines.extend([
                "## Scope Impact",
                f"- Affected Devices: {', '.join(self.affected_devices) if self.affected_devices else 'None'}",
                f"- Affected Interfaces: {', '.join(self.affected_interfaces) if self.affected_interfaces else 'None'}",
                "",
            ])

        if self.causal_chain:
            lines.extend([
                "## Causal Chain",
                *[f"{idx+1}. {step}" for idx, step in enumerate(self.causal_chain)],
                "",
            ])

        if self.evidence:
            lines.extend([
                "## Supporting Evidence",
                "| Domain | Entity | Metric | Value | Severity | Finding |",
                "| --- | --- | --- | --- | --- | --- |",
            ])
            for ev in self.evidence[:10]:
                src = ev.get("source_agent", "unknown")
                ent = ev.get("entity", "-")
                m = ev.get("metric_name", "-")
                v = f"{ev.get('value')} {ev.get('unit', '')}".strip()
                sev = ev.get("severity", "info")
                fnd = ev.get("finding", "-")
                lines.append(f"| {src} | {ent} | {m} | {v} | {sev} | {fnd} |")
            lines.append("")

        if self.uncertainty.alternative_hypotheses:
            lines.extend([
                "## Alternative Hypotheses",
                "| Candidate Cause | Confidence | Discriminating Test |",
                "| --- | --- | --- |",
            ])
            for alt in self.uncertainty.alternative_hypotheses:
                cause = alt.get("cause", "-")
                conf = alt.get("confidence", 0.0)
                test = alt.get("discriminating_test", "Path-level telemetry corroboration")
                lines.append(f"| {cause} | {conf:.2%} | {test} |")
            lines.append("")

        if self.conflicts_resolved:
            lines.extend([
                "## Multi-Agent Conflicts & Arbitration",
                *[f"- **Iteration {c.get('iteration', 1)}**: {c.get('rationale', 'Resolved via evidence precedence')}" for c in self.conflicts_resolved],
                "",
            ])

        if self.confidence_breakdown:
            lines.extend([
                "## Confidence Breakdown & Calibration",
                f"- Rules Score: {self.confidence_breakdown.get('rules_score', 0.0):.3f}",
                f"- Model Score: {self.confidence_breakdown.get('model_score', 0.0):.3f}",
                f"- Blended Score: {self.confidence_breakdown.get('blended_score', 0.0):.3f}",
                f"- Calibrated Confidence: {self.confidence_breakdown.get('calibrated_confidence', 0.0):.3f}",
                f"- Confidence Category: {self.confidence_category or 'N/A'}",
                f"- Conformal Prediction Set: {', '.join(self.conformal_prediction_set) if self.conformal_prediction_set else 'None (Abstain)'}",
                "",
            ])

        if self.limitations:
            lines.extend([
                "## Data Limitations & Caveats",
                *[f"- {lim}" for lim in self.limitations],
                "",
            ])

        if self.remediation_actions:
            lines.extend([
                "## Simulated Remediation Plan",
                "| Action ID | Target Device | Risk Level | Description |",
                "| --- | --- | --- | --- |",
            ])
            for act in self.remediation_actions:
                lines.append(f"| {act.action_id} | {act.device} | {act.risk_level.upper()} | {act.title} |")
            lines.append("")
            lines.append("*Notice: Remediation actions are simulated only. No production state modified.*")
            lines.append("")

        return "\n".join(lines)


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
        causal_chain: Optional[List[str]] = None,
        conflicts_resolved: Optional[List[Dict[str, Any]]] = None,
        limitations: Optional[List[str]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        confidence_breakdown: Optional[Dict[str, float]] = None,
        conformal_prediction_set: Optional[List[str]] = None,
        confidence_category: Optional[str] = None,
    ) -> UnifiedDiagnosticReport:
        """Construct a standardized UnifiedDiagnosticReport."""
        evidence_dicts: List[Dict[str, Any]] = []
        affected_devices: List[str] = []
        affected_interfaces: List[str] = []
        probable_cause = None
        confidence = 0.0
        hypothesis_key = hypothesis.cause_key if hypothesis else None

        if hypothesis and status in ("diagnosed", "benign"):
            probable_cause = hypothesis.title
            confidence = hypothesis.final_confidence
            affected_devices = hypothesis.affected_devices
            affected_interfaces = hypothesis.affected_interfaces
            for ev in hypothesis.supporting_evidence:
                ev_d = ev.model_dump()
                if not ev_d.get("timestamp"):
                    ev_d["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                evidence_dicts.append(ev_d)
        elif status == "insufficient_evidence":
            probable_cause = None
            confidence = 0.0
            if summary is None:
                summary = (
                    "Insufficient evidence to isolate root cause. "
                    "Observed anomalies lack required cross-domain corroboration."
                )

        if summary is None:
            if status in ("diagnosed", "benign") and hypothesis:
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
            causal_chain=causal_chain or [],
            conflicts_resolved=conflicts_resolved or [],
            limitations=limitations or [],
            provenance=provenance or {},
            confidence_breakdown=confidence_breakdown,
            conformal_prediction_set=conformal_prediction_set or [],
            confidence_category=confidence_category,
            hypothesis_key=hypothesis_key,
        )
