"""Unified JSON diagnostic report generator conforming to schemas/diagnostic_report.json."""

from enum import Enum
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator

from netcoop.core.evidence import DiagnosticHypothesis, EvidenceItem, UncertaintyEvaluation


class DiagnosticReportStatus(str, Enum):
    """Formal status semantics for diagnostic reports."""

    DIAGNOSED = "diagnosed"
    BENIGN = "benign"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"
    FAILED = "failed"


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
    action: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_action_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "action" not in data or data["action"] is None:
                data["action"] = data.get("title") or data.get("description")
        return data


class UnifiedDiagnosticReport(BaseModel):
    """Unified JSON diagnostic report specification."""

    incident_id: str
    network_id: str
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str  # diagnosed, insufficient_evidence, inconclusive, benign, invalid, failed
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

    # Phase 4 additive fields for PS compliance and operator explainability
    evidence_sources: List[str] = Field(default_factory=list)
    suspected_root_cause: Optional[str] = None
    is_confidence_calibrated: bool = False
    confidence_type: str = "uncalibrated_heuristic"

    @model_validator(mode="before")
    @classmethod
    def populate_report_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Synchronize suspected_root_cause <-> probable_cause
            if data.get("suspected_root_cause") is None and data.get("probable_cause") is not None:
                data["suspected_root_cause"] = data["probable_cause"]
            elif data.get("probable_cause") is None and data.get("suspected_root_cause") is not None:
                data["probable_cause"] = data["suspected_root_cause"]

            # Derive evidence_sources if missing
            if not data.get("evidence_sources") and data.get("evidence"):
                sources = set()
                for ev in data["evidence"]:
                    if isinstance(ev, dict) and ev.get("source_agent"):
                        sources.add(ev["source_agent"])
                data["evidence_sources"] = sorted(list(sources))

            # Derive is_confidence_calibrated if not explicitly provided
            if "is_confidence_calibrated" not in data:
                cb = data.get("confidence_breakdown")
                data["is_confidence_calibrated"] = bool(cb and cb.get("calibrated_confidence") is not None)

            # Derive confidence_type if not explicitly provided
            if "confidence_type" not in data:
                status = data.get("status")
                if status in ("insufficient_evidence", "inconclusive", "invalid", "failed"):
                    data["confidence_type"] = "abstain"
                elif data.get("is_confidence_calibrated"):
                    data["confidence_type"] = "calibrated_probability"
                else:
                    data["confidence_type"] = "uncalibrated_heuristic"

        return data

    def to_json(self) -> str:
        """Serialize report to formatted JSON string."""
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        """Render a clean monochrome markdown report strictly consistent with JSON."""
        status_upper = self.status.upper()
        if self.status == "benign":
            cause_display = self.probable_cause or "Normal Operation (No Fault Detected)"
        elif self.status == "diagnosed":
            cause_display = self.probable_cause or "Unknown Diagnosed Cause"
        elif self.status == "insufficient_evidence":
            cause_display = "None (Insufficient evidence to isolate root cause)"
        elif self.status == "inconclusive":
            cause_display = "None (Inconclusive - competing hypotheses unresolvable)"
        elif self.status == "invalid":
            cause_display = "None (Input validation failure)"
        elif self.status == "failed":
            cause_display = "None (Diagnostic pipeline execution failure)"
        else:
            cause_display = self.probable_cause or "None"

        conf_semantics = (
            "Calibrated Probability (Isotonic / Conformal)"
            if self.is_confidence_calibrated
            else "Uncalibrated Heuristic Corroboration Score"
        )
        if self.status in ("insufficient_evidence", "inconclusive", "invalid", "failed"):
            conf_semantics = "N/A (Abstained / Zero Confidence)"

        lines = [
            f"# Diagnostic Incident Report: {self.incident_id}",
            "",
            "## 1. Incident Overview & Summary",
            f"- **Network ID**: `{self.network_id}`",
            f"- **Timestamp (UTC)**: `{self.timestamp_utc}`",
            f"- **Diagnostic Status**: **{status_upper}**",
            f"- **Probable Cause / Suspected Root Cause**: {cause_display}",
            f"- **Confidence Score**: {self.confidence:.2%} ({conf_semantics})",
            f"- **Confidence Category**: {self.confidence_category or 'N/A'}",
            f"- **Processing Time**: {self.processing_time_ms:.1f} ms",
            f"- **Evidence Sources**: {', '.join(self.evidence_sources) if self.evidence_sources else 'None'}",
            "",
            f"> {self.summary}",
            "",
            "## 2. Scope & Topology Footprint",
            f"- **Affected Devices**: {', '.join(self.affected_devices) if self.affected_devices else 'None identified (or unknown)'}",
            f"- **Affected Interfaces**: {', '.join(self.affected_interfaces) if self.affected_interfaces else 'None identified (or unknown)'}",
            "",
        ]

        if self.causal_chain:
            lines.extend([
                "## 3. Causal Chain & Diagnostic Reasoning",
                *[f"{idx+1}. {step}" for idx, step in enumerate(self.causal_chain)],
                "",
            ])

        lines.extend([
            f"## 4. Empirical Facts & Supporting Evidence ({len(self.evidence)} items)",
        ])
        if self.evidence:
            lines.extend([
                "| Evidence ID | Domain Agent | Target Entity | Metric | Observed Value | Severity | Finding / Interpretation | Reference |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ])
            for ev in self.evidence:
                ev_id = ev.get("evidence_id") or ev.get("observation_id") or "-"
                src = ev.get("source_agent", "unknown")
                ent = ev.get("entity", "unknown")
                m = ev.get("metric_name") or ev.get("metric") or "unknown"
                val = ev.get("value")
                unit = ev.get("unit") or ""
                if val is None:
                    val_str = "unknown"
                else:
                    val_str = f"{val} {unit}".strip()
                sev = ev.get("severity", "info")
                interp = ev.get("interpretation") or ev.get("finding") or "-"
                ref = ev.get("observation_id") or ev.get("message_id") or "-"
                lines.append(f"| `{ev_id}` | {src} | `{ent}` | `{m}` | {val_str} | {sev} | {interp} | `{ref}` |")
            lines.append("")
        else:
            lines.extend([
                "No empirical evidence items recorded.",
                "",
            ])

        if self.uncertainty.alternative_hypotheses or self.uncertainty.missing_evidence or self.uncertainty.reasons:
            lines.extend([
                "## 5. Alternative Hypotheses & Uncertainty Evaluation",
                f"- **Uncertainty Score**: {self.uncertainty.score:.2%}",
            ])
            if self.uncertainty.reasons:
                lines.append("- **Uncertainty Factors**:")
                for r in self.uncertainty.reasons:
                    lines.append(f"  * {r}")
            if self.uncertainty.missing_evidence:
                lines.append("- **Prerequisite Evidence Missing**:")
                for m in self.uncertainty.missing_evidence:
                    lines.append(f"  * {m}")
            if self.uncertainty.alternative_hypotheses:
                lines.extend([
                    "",
                    "| Candidate Alternative Cause | Confidence | Discriminating Test | Supporting Evidence | Refuting Evidence |",
                    "| --- | --- | --- | --- | --- |",
                ])
                for alt in self.uncertainty.alternative_hypotheses:
                    cause = alt.get("cause") or alt.get("title") or "-"
                    conf = alt.get("confidence", 0.0)
                    test = alt.get("discriminating_test", "Cross-domain telemetry corroboration")
                    sup = ", ".join(alt.get("supporting_evidence_ids", [])) or "None"
                    ref = ", ".join(alt.get("refuting_evidence_ids", [])) or "None"
                    lines.append(f"| {cause} | {conf:.2%} | {test} | {sup} | {ref} |")
            lines.append("")

        if self.conflicts_resolved:
            lines.extend([
                "## 6. Multi-Agent Contradictions & Conflict Resolution",
                *[f"- **Iteration {c.get('iteration', 1)}**: {c.get('rationale', 'Resolved via evidence precedence')}" for c in self.conflicts_resolved],
                "",
            ])

        lines.extend([
            "## 7. Confidence Calibration Breakdown",
            f"- **Confidence Score**: {self.confidence:.3f}",
            f"- **Semantics**: {conf_semantics}",
        ])
        if self.confidence_breakdown:
            lines.extend([
                f"- Rules Engine Score: {self.confidence_breakdown.get('rules_score', 0.0):.3f}",
                f"- Classifier Softmax Score: {self.confidence_breakdown.get('model_score', 0.0):.3f}",
                f"- Hybrid Blended Score: {self.confidence_breakdown.get('blended_score', 0.0):.3f}",
                f"- Isotonically Calibrated Probability: {self.confidence_breakdown.get('calibrated_confidence', 0.0):.3f}",
            ])
        if self.conformal_prediction_set:
            lines.append(f"- Conformal Prediction Set (alpha=0.10): [{', '.join(self.conformal_prediction_set)}]")
        else:
            lines.append("- Conformal Prediction Set: None (Disciplined Abstention)")
        lines.append("")

        lines.append("## 8. Data Limitations & Caveats")
        if self.limitations:
            for lim in self.limitations:
                lines.append(f"- {lim}")
        else:
            lines.append("- No operational data limitations recorded for this incident.")
        lines.append("")

        lines.append("## 9. Simulated Remediation Plan")
        if self.remediation_actions:
            lines.extend([
                "| Action ID | Target Device | Risk Level | Title | Status |",
                "| --- | --- | --- | --- | --- |",
            ])
            for act in self.remediation_actions:
                lines.append(f"| `{act.action_id}` | `{act.device}` | {act.risk_level.upper()} | {act.title} | {act.status.upper()} |")
            lines.append("")
            lines.append("### Remediation Action Steps")
            for act in self.remediation_actions:
                lines.append(f"#### Action `{act.action_id}`: {act.title}")
                lines.append(f"- **Target Device**: `{act.device}`")
                lines.append(f"- **Description**: {act.description}")
                lines.append(f"- **Risk Level**: {act.risk_level.upper()} (Blast Radius: {', '.join(act.blast_radius_devices) if act.blast_radius_devices else 'Isolated'})")
                if act.commands:
                    lines.append(f"- **Simulated Commands**:\n```bash\n" + "\n".join(act.commands) + "\n```")
                if act.rollback_commands:
                    lines.append(f"- **Rollback Commands**:\n```bash\n" + "\n".join(act.rollback_commands) + "\n```")
                lines.append("")
            lines.append("*Safety Guarantee: Remediation actions are advisory and simulated only. No production network state has been modified.*")
            lines.append("")
        else:
            lines.extend([
                "No justified remediation actions.",
                "",
                "> Remediation is withheld because the incident is either benign (normal operation), lacking conclusive root-cause corroboration, or flagged with validation/pipeline errors.",
                "",
            ])

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
        evidence_sources: Optional[List[str]] = None,
        suspected_root_cause: Optional[str] = None,
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
                if not ev_d.get("evidence_id"):
                    obs_id = ev_d.get("observation_id")
                    ev_d["evidence_id"] = str(obs_id) if obs_id and str(obs_id).startswith("evi-") else (f"evi-{obs_id}" if obs_id else f"evi-{uuid4().hex[:8]}")
                if not ev_d.get("interpretation"):
                    ev_d["interpretation"] = ev_d.get("finding", "")
                if not ev_d.get("metric"):
                    ev_d["metric"] = ev_d.get("metric_name")
                if not ev_d.get("timestamp"):
                    ev_d["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                evidence_dicts.append(ev_d)
        elif status == "benign":
            probable_cause = hypothesis.title if hypothesis else "Normal Operation"
            confidence = hypothesis.final_confidence if hypothesis else 1.0
            if summary is None:
                summary = "Normal operation verified: all telemetry metrics within nominal baseline boundaries."
        elif status == "insufficient_evidence":
            probable_cause = None
            confidence = 0.0
            if summary is None:
                summary = (
                    "Insufficient evidence to isolate root cause. "
                    "Observed anomalies lack required cross-domain corroboration."
                )
        elif status == "invalid":
            probable_cause = None
            confidence = 0.0
            if summary is None:
                summary = (
                    "Input validation failure: telemetry payload is malformed, "
                    "corrupted, or missing required schema container attributes."
                )
        elif status == "failed":
            probable_cause = None
            confidence = 0.0
            if summary is None:
                summary = (
                    "Diagnostic processing error: pipeline encountered an unrecoverable "
                    "exception or agent timeout during multi-agent synthesis."
                )

        if summary is None:
            if status == "diagnosed" and hypothesis:
                dev_str = f" Affecting devices: {', '.join(affected_devices)}." if affected_devices else ""
                summary = (
                    f"Diagnosed {hypothesis.title} with {int(confidence * 100)}% confidence.{dev_str}"
                )
            else:
                summary = f"Incident status: {status}."

        # Derive unique evidence sources
        if evidence_sources:
            derived_sources = sorted(list(set(evidence_sources)))
        else:
            derived_sources = sorted(list(set(
                ev.get("source_agent") for ev in evidence_dicts if ev.get("source_agent")
            )))

        # Calibration flags
        is_calibrated = bool(confidence_breakdown and confidence_breakdown.get("calibrated_confidence") is not None)
        if status in ("insufficient_evidence", "inconclusive", "invalid", "failed"):
            conf_type = "abstain"
        elif is_calibrated:
            conf_type = "calibrated_probability"
        else:
            conf_type = "uncalibrated_heuristic"

        # Disallow remediation actions for non-diagnosed incidents
        actions = remediation_actions if status == "diagnosed" else []

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
            remediation_actions=actions or [],
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
            evidence_sources=derived_sources,
            suspected_root_cause=suspected_root_cause or probable_cause,
            is_confidence_calibrated=is_calibrated,
            confidence_type=conf_type,
        )

    @classmethod
    def build_invalid_report(
        cls,
        incident_id: str = "invalid-incident",
        network_id: str = "unknown-network",
        errors: Optional[List[str]] = None,
        limitations: Optional[List[str]] = None,
    ) -> UnifiedDiagnosticReport:
        """Construct a standardized report representing input validation failures."""
        err_list = errors or ["Input validation failed: malformed payload or missing required container fields."]
        lim_list = list(limitations or [])
        for err in err_list:
            if err not in lim_list:
                lim_list.append(err)
        return cls.build_report(
            incident_id=incident_id,
            network_id=network_id,
            status="invalid",
            hypothesis=None,
            uncertainty=UncertaintyEvaluation(
                score=1.0,
                reasons=err_list,
                missing_evidence=["valid_canonical_telemetry_payload"],
            ),
            remediation_actions=[],
            summary=f"Input validation failure: {'; '.join(err_list)}",
            limitations=lim_list,
        )

    @classmethod
    def build_failed_report(
        cls,
        incident_id: str,
        network_id: str,
        error_message: str,
        limitations: Optional[List[str]] = None,
    ) -> UnifiedDiagnosticReport:
        """Construct a standardized report representing diagnostic execution crashes."""
        lim_list = list(limitations or [])
        lim_entry = f"Pipeline execution failure: {error_message}"
        if lim_entry not in lim_list:
            lim_list.append(lim_entry)
        return cls.build_report(
            incident_id=incident_id,
            network_id=network_id,
            status="failed",
            hypothesis=None,
            uncertainty=UncertaintyEvaluation(
                score=1.0,
                reasons=[f"Diagnostic pipeline execution crashed: {error_message}"],
                missing_evidence=["successful_multi_agent_execution"],
            ),
            remediation_actions=[],
            summary=f"Diagnostic pipeline error: {error_message}",
            limitations=lim_list,
        )
