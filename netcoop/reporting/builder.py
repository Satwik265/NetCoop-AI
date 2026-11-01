"""Report builder and normalizer for two-level Network Diagnostic Reports.

Constructs Executive (Level 1) and Technical (Level 2) reports from orchestrator outputs,
unified diagnostic reports, telemetry envelopes, and optional IITBBSR campus topology references.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from netcoop.core.report import UnifiedDiagnosticReport
from netcoop.reporting.models import (
    AgentInvestigationRecord,
    AgentState,
    AuditReference,
    CampusTopologyReference,
    ConfidenceCalibrationData,
    DiagnosticStatus,
    EvidenceRecord,
    ExecutiveReport,
    MetricObservation,
    NetworkDiagnosticReport,
    RecommendedAction,
    RecoveryStatus,
    RemediationState,
    ReportSeverity,
    RootCauseStatus,
    TechnicalReport,
    TechnicalSection,
)

STANDARD_AGENTS = [
    ("telemetry_agent", "Telemetry Specialist"),
    ("topology_agent", "Topology Specialist"),
    ("config_agent", "Configuration Specialist"),
    ("log_agent", "Syslog Specialist"),
    ("wifi_services_agent", "WiFi & Core Services Specialist"),
    ("classifier_agent", "Statistical ML Classifier"),
    ("synthesizer_agent", "Root Cause Synthesizer"),
]


class DiagnosticReportBuilder:
    """Constructs and normalizes versioned Network Diagnostic Reports."""

    @classmethod
    def from_unified_report(
        cls,
        unified_report: UnifiedDiagnosticReport,
        incident_data: Optional[Dict[str, Any]] = None,
        campus_topology: Optional[Dict[str, Any]] = None,
        agent_records: Optional[List[AgentInvestigationRecord]] = None,
        envelopes: Optional[List[Any]] = None,
        recovery_status: Optional[RecoveryStatus] = None,
        report_id: Optional[str] = None,
        audit_metadata: Optional[Dict[str, Any]] = None,
        missing_metric_names: Optional[List[str]] = None,
    ) -> NetworkDiagnosticReport:
        """Transform a UnifiedDiagnosticReport into a two-level NetworkDiagnosticReport."""
        rep_id = report_id or f"rep-{uuid4().hex[:10]}"
        inc_id = unified_report.incident_id
        net_id = unified_report.network_id

        # 1. Diagnostic Status & Root Cause mapping
        raw_status = unified_report.status.lower()
        if raw_status in ("insufficient_evidence", "inconclusive"):
            diag_status = DiagnosticStatus.INSUFFICIENT_EVIDENCE
            probable_cause = None
            conf_val: Optional[float] = None
            root_cause_status = RootCauseStatus.INCONCLUSIVE
        elif raw_status == "abstained":
            diag_status = DiagnosticStatus.ABSTAINED
            probable_cause = None
            conf_val = None
            root_cause_status = RootCauseStatus.ABSTAINED
        elif raw_status == "benign":
            diag_status = DiagnosticStatus.BENIGN
            probable_cause = unified_report.probable_cause or "Normal Operation"
            conf_val = unified_report.confidence
            root_cause_status = RootCauseStatus.PROBABLE
        else:
            diag_status = DiagnosticStatus.DIAGNOSED
            probable_cause = unified_report.probable_cause
            conf_val = unified_report.confidence
            root_cause_status = RootCauseStatus.PROBABLE

        # 2. Extract and normalize EvidenceRecords with stable IDs
        evidence_records: List[EvidenceRecord] = []
        max_severity = ReportSeverity.INFO
        severity_order = {
            ReportSeverity.UNKNOWN: 0,
            ReportSeverity.INFO: 1,
            ReportSeverity.WARNING: 2,
            ReportSeverity.CRITICAL: 3,
        }

        for idx, ev in enumerate(unified_report.evidence):
            sev_raw = str(ev.get("severity", "warning")).lower()
            if sev_raw == "critical":
                item_sev = ReportSeverity.CRITICAL
            elif sev_raw == "warning":
                item_sev = ReportSeverity.WARNING
            elif sev_raw == "info":
                item_sev = ReportSeverity.INFO
            else:
                item_sev = ReportSeverity.UNKNOWN

            if severity_order[item_sev] > severity_order[max_severity]:
                max_severity = item_sev

            ev_id = ev.get("evidence_id") or f"evi-{inc_id[-6:]}-{idx + 1:03d}"
            evidence_records.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source_agent=ev.get("source_agent", "unknown"),
                    category=ev.get("category", "metric_anomaly"),
                    finding=ev.get("finding", ""),
                    entity=ev.get("entity", "-"),
                    metric_name=ev.get("metric_name"),
                    value=ev.get("value"),
                    unit=ev.get("unit"),
                    severity=item_sev,
                    timestamp=ev.get("timestamp"),
                    provenance=ev.get("provenance", {}),
                    weight=float(ev.get("weight", 1.0)),
                )
            )

        # 3. Key Observations (from evidence plus explicit missing telemetry fields)
        key_observations: List[MetricObservation] = []
        observed_metric_entities: Set[str] = set()

        for ev in evidence_records:
            if ev.metric_name:
                key = f"{ev.entity}:{ev.metric_name}"
                if key not in observed_metric_entities:
                    observed_metric_entities.add(key)
                    key_observations.append(
                        MetricObservation(
                            metric_name=ev.metric_name,
                            value=ev.value,
                            unit=ev.unit,
                            entity=ev.entity,
                            source=ev.source_agent,
                            timestamp=ev.timestamp,
                            provenance=ev.provenance,
                            severity=ev.severity,
                            is_available=ev.value is not None,
                        )
                    )

        # Add explicit uncollected/missing telemetry metrics (never fabricated!)
        if missing_metric_names:
            for m_name in missing_metric_names:
                key_observations.append(
                    MetricObservation(
                        metric_name=m_name,
                        value=None,
                        unit=None,
                        entity=None,
                        source="telemetry_collector",
                        timestamp=None,
                        provenance={"status": "not_reported_by_telemetry_source"},
                        severity=ReportSeverity.UNKNOWN,
                        is_available=False,
                    )
                )

        # 4. Agent Execution Status (Genuine provenance, no fake static lists)
        agents_status_list: List[AgentInvestigationRecord] = []
        contributing_agents = {ev.source_agent for ev in evidence_records}

        if agent_records:
            agents_status_list = agent_records
        elif envelopes:
            # Derive agent status directly from real envelopes
            agents_seen: Dict[str, Dict[str, Any]] = {}
            for env in envelopes:
                sender = getattr(env.header, "sender", None)
                s_val = sender.value if hasattr(sender, "value") else str(sender)
                recipient = getattr(env.header, "recipient", None)
                r_val = recipient.value if hasattr(recipient, "value") else str(recipient)

                if s_val not in agents_seen:
                    agents_seen[s_val] = {"status": AgentState.COMPLETED, "obs_count": 0}
                if hasattr(env.payload, "observations"):
                    agents_seen[s_val]["obs_count"] += len(env.payload.observations)

                msg_type = getattr(env.header, "message_type", None)
                m_val = msg_type.value if hasattr(msg_type, "value") else str(msg_type)
                if m_val == "protocol_error":
                    agents_seen[s_val]["status"] = AgentState.FAILED

                if r_val and r_val not in agents_seen:
                    agents_seen[r_val] = {"status": AgentState.QUEUED, "obs_count": 0}

            for role_str, name_str in STANDARD_AGENTS:
                if role_str in agents_seen:
                    st = agents_seen[role_str]["status"]
                    cnt = agents_seen[role_str]["obs_count"]
                    s_text = f"Dispatched and evaluated ({cnt} observations)."
                else:
                    st = AgentState.SKIPPED
                    cnt = 0
                    s_text = "No envelope or dispatch record recorded in session."
                agents_status_list.append(
                    AgentInvestigationRecord(
                        agent_role=role_str,
                        agent_name=name_str,
                        status=st,
                        execution_time_ms=None,
                        observations_count=cnt,
                        findings_summary=s_text,
                    )
                )
        else:
            # Derived strictly from evidence records
            for role_str, name_str in STANDARD_AGENTS:
                cnt = sum(1 for ev in evidence_records if ev.source_agent == role_str)
                if role_str in contributing_agents:
                    st = AgentState.COMPLETED
                    summary_text = f"Participated and contributed {cnt} evidence records."
                elif role_str == "synthesizer_agent" and raw_status in ("diagnosed", "insufficient_evidence", "benign"):
                    st = AgentState.COMPLETED
                    summary_text = f"Concluded root cause synthesis with status '{diag_status.value}'."
                else:
                    st = AgentState.SKIPPED
                    summary_text = "No anomalous findings or observations recorded in domain."

                agents_status_list.append(
                    AgentInvestigationRecord(
                        agent_role=role_str,
                        agent_name=name_str,
                        status=st,
                        execution_time_ms=None,
                        observations_count=cnt,
                        findings_summary=summary_text,
                    )
                )

        # 5. Advisory Remediation Actions (preserving simulation boundary)
        recommended_actions: List[RecommendedAction] = []
        for act in unified_report.remediation_actions:
            raw_act_status = getattr(act, "status", "recommended").lower()
            if raw_act_status in ("approved", "pending_approval"):
                rem_state = RemediationState.APPROVED
            elif raw_act_status == "simulated_success":
                rem_state = RemediationState.SIMULATED
            elif raw_act_status == "rejected":
                rem_state = RemediationState.REJECTED
            else:
                rem_state = RemediationState.PROPOSED

            recommended_actions.append(
                RecommendedAction(
                    action_id=act.action_id,
                    title=act.title,
                    description=act.description,
                    target_device=act.device,
                    commands=act.commands,
                    rollback_commands=act.rollback_commands,
                    risk_level=act.risk_level,
                    blast_radius_devices=act.blast_radius_devices,
                    is_simulated=True,
                    status=rem_state,
                    is_advisory=True,
                    advisory_notice=(
                        "Action is advisory and simulated only. No production network change has occurred."
                    ),
                )
            )

        # 6. IITBBSR Demonstration Topology Interoperability (Strict site_id vs site_name)
        topology_ref = cls._build_topology_reference(
            affected_devices=unified_report.affected_devices,
            campus_topology=campus_topology,
            incident_data=incident_data,
        )

        affected_site_ids: List[str] = []
        affected_site_names: List[str] = []
        if topology_ref:
            affected_site_ids = topology_ref.affected_site_ids
            affected_site_names = topology_ref.affected_site_names

        # 7. Recovery Verification Status (independent of diagnostic completion)
        if recovery_status is not None:
            rec_status = recovery_status
        elif diag_status == DiagnosticStatus.BENIGN:
            rec_status = RecoveryStatus.NOT_APPLICABLE
        else:
            rec_status = RecoveryStatus.PENDING_VERIFICATION

        # 8. Calibration & Uncertainty evaluation
        has_breakdown = bool(unified_report.confidence_breakdown)
        calibrated_val = (
            unified_report.confidence_breakdown.get("calibrated_confidence")
            if has_breakdown
            else None
        )
        is_calibrated = has_breakdown and calibrated_val is not None

        if is_calibrated:
            confidence_type = "calibrated_probability"
            report_conf = calibrated_val
        elif diag_status in (DiagnosticStatus.DIAGNOSED, DiagnosticStatus.BENIGN) and conf_val is not None:
            confidence_type = "uncalibrated_heuristic"
            report_conf = conf_val
        else:
            confidence_type = None
            report_conf = None

        calib_data = ConfidenceCalibrationData(
            rules_score=(
                unified_report.confidence_breakdown.get("rules_score")
                if has_breakdown
                else conf_val
            ),
            raw_rules_score=(
                unified_report.confidence_breakdown.get("rules_score")
                if has_breakdown
                else conf_val
            ),
            model_score=(
                unified_report.confidence_breakdown.get("model_score")
                if has_breakdown
                else None
            ),
            blended_score=(
                unified_report.confidence_breakdown.get("blended_score")
                if has_breakdown
                else None
            ),
            calibrated_confidence=calibrated_val,
            calibration_method="isotonic_plus_conformal" if is_calibrated else None,
            conformal_prediction_set=unified_report.conformal_prediction_set,
            confidence_category=unified_report.confidence_category,
            is_calibrated=is_calibrated,
            notes=(
                "Calibrated via held-out split conformal nonconformity bounds."
                if is_calibrated
                else "Uncalibrated heuristic rule confidence; no empirical calibration applied."
            ),
        )

        # 9. Audit Reference Verification (genuine database audit check)
        audit_ref = cls._build_audit_reference(inc_id=inc_id, audit_metadata=audit_metadata)

        # 10. Level 1: Executive Report Assembly
        exec_summary = unified_report.summary or (
            f"Diagnosed {probable_cause} affecting devices {', '.join(unified_report.affected_devices)}."
            if probable_cause
            else f"Diagnostic concluded with status '{diag_status.value}'. Insufficient evidence to isolate root cause."
        )

        ev_summary = (
            f"Corroborated across {len(evidence_records)} evidence records from "
            f"{len(contributing_agents)} specialist agents."
            if evidence_records
            else "No anomalous evidence corroborated."
        )

        executive = ExecutiveReport(
            report_id=rep_id,
            incident_id=inc_id,
            generated_timestamp=datetime.now(timezone.utc).isoformat(),
            diagnostic_status=diag_status,
            severity=max_severity,
            confidence=report_conf,
            confidence_category=unified_report.confidence_category,
            is_confidence_calibrated=is_calibrated,
            confidence_type=confidence_type,
            affected_devices=unified_report.affected_devices,
            affected_site_ids=affected_site_ids,
            affected_site_names=affected_site_names,
            affected_sites=affected_site_names,
            probable_root_cause=probable_cause,
            root_cause_status=root_cause_status,
            executive_summary=exec_summary,
            key_observations=key_observations,
            supporting_evidence_summary=ev_summary,
            agent_investigation_status=agents_status_list,
            recommended_actions=recommended_actions,
            recovery_verification_status=rec_status,
            data_provenance=unified_report.provenance or {
                "source": "netcoop_orchestrator",
                "pipeline_version": "2.0.0",
                "timestamp_utc": unified_report.timestamp_utc,
            },
            limitations=unified_report.limitations or [
                "Remediation actions are simulated proposals only.",
                "Topology references denote demonstration campus inventory.",
            ],
        )

        # 11. Level 2: Technical Report Assembly (12 Extensible Sections)
        sections = cls._build_technical_sections(
            unified_report=unified_report,
            evidence_records=evidence_records,
            calib_data=calib_data,
            topology_ref=topology_ref,
            recommended_actions=recommended_actions,
            audit_ref=audit_ref,
            recovery_status=rec_status,
        )

        technical = TechnicalReport(sections=sections)

        return NetworkDiagnosticReport(
            schema_version="2.0.0",
            report_id=rep_id,
            incident_id=inc_id,
            network_id=net_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            executive=executive,
            technical=technical,
            topology_reference=topology_ref,
            audit=audit_ref,
        )

    @classmethod
    def _build_topology_reference(
        cls,
        affected_devices: List[str],
        campus_topology: Optional[Dict[str, Any]] = None,
        incident_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[CampusTopologyReference]:
        """Resolve demonstration topology linkage from IITBBSR fixture with strict site_id and site_name separation."""
        topology_dict = campus_topology
        if not topology_dict:
            topo_file = Path("data/campus/iitbbsr_demo_topology.json")
            if topo_file.is_file():
                try:
                    with open(topo_file, "r", encoding="utf-8") as f:
                        topology_dict = json.load(f)
                except Exception:
                    topology_dict = None

        if not topology_dict and incident_data:
            topology_dict = incident_data.get("topology")

        if not topology_dict:
            return None

        campus_id = topology_dict.get("campus_id", "iitbbsr_argul_campus")
        nodes = topology_dict.get("nodes", [])
        paths = topology_dict.get("logical_routing_paths", [])

        # Match nodes and strictly separate site_id from site_name
        matched_node_ids: List[str] = []
        matched_site_ids: List[str] = []
        matched_site_names: List[str] = []

        for dev in affected_devices:
            for n in nodes:
                nid = n.get("id")
                if nid and (nid == dev or dev in nid or nid in dev):
                    if nid not in matched_node_ids:
                        matched_node_ids.append(nid)
                    sid = n.get("site_id")
                    if sid and sid not in matched_site_ids:
                        matched_site_ids.append(sid)
                    sname = n.get("site_name")
                    if sname and sname not in matched_site_names:
                        matched_site_names.append(sname)

        # Check affected logical paths
        matched_path_ids: List[str] = []
        for p in paths:
            hops = p.get("hops", [])
            if any(h in matched_node_ids for h in hops):
                matched_path_ids.append(p.get("path_id", "PATH-DEMO"))

        return CampusTopologyReference(
            campus_id=campus_id,
            affected_node_ids=matched_node_ids or affected_devices,
            affected_site_ids=matched_site_ids,
            affected_site_names=matched_site_names,
            affected_path_ids=matched_path_ids,
            topology_provenance=topology_dict.get("topology_provenance"),
            simulated_inventory=True,
            disclaimer=(
                "All network equipment, nodes, links, and paths are synthetic demonstration inventory. "
                "Official campus maps establish physical building landmarks only and contain zero network routing equipment records."
            ),
        )

    @classmethod
    def _build_audit_reference(
        cls,
        inc_id: str,
        audit_metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditReference:
        """Verify audit persistence against real storage records."""
        if audit_metadata:
            return AuditReference(
                audit_logged=bool(audit_metadata.get("audit_logged", True)),
                storage_engine=audit_metadata.get("storage_engine", "sqlite"),
                incident_record_id=audit_metadata.get("incident_record_id", inc_id),
                checkpoint_id=audit_metadata.get("checkpoint_id"),
                envelope_count=int(audit_metadata.get("envelope_count", 0)),
                replay_trace_id=audit_metadata.get("replay_trace_id"),
                notes=audit_metadata.get("notes"),
            )

        # Query database to check if genuine records exist
        try:
            from netcoop.storage.db import get_incident, get_envelope_logs
            inc_rec = get_incident(inc_id)
            env_logs = get_envelope_logs(inc_id)
            if inc_rec or env_logs:
                return AuditReference(
                    audit_logged=True,
                    storage_engine="sqlite",
                    incident_record_id=inc_id,
                    envelope_count=len(env_logs),
                    replay_trace_id=inc_id,
                    notes=f"Persisted in SQLite database with {len(env_logs)} envelope logs.",
                )
        except Exception:
            pass

        return AuditReference(
            audit_logged=False,
            storage_engine="sqlite",
            incident_record_id=None,
            checkpoint_id=None,
            envelope_count=0,
            replay_trace_id=None,
            notes="No persistent storage records verified for incident.",
        )

    @classmethod
    def _build_technical_sections(
        cls,
        unified_report: UnifiedDiagnosticReport,
        evidence_records: List[EvidenceRecord],
        calib_data: ConfidenceCalibrationData,
        topology_ref: Optional[CampusTopologyReference],
        recommended_actions: List[RecommendedAction],
        audit_ref: AuditReference,
        recovery_status: RecoveryStatus,
    ) -> List[TechnicalSection]:
        """Construct the 12 technical diagnostic sections with explicit availability tracking."""
        sections: List[TechnicalSection] = []

        # 1. Incident and Diagnostic Context
        sections.append(
            TechnicalSection(
                section_id="incident_context",
                title="Incident and Diagnostic Context",
                order=1,
                is_available=True,
                summary="Primary incident telemetry context, processing duration, and runtime invocation metadata.",
                data={
                    "incident_id": unified_report.incident_id,
                    "network_id": unified_report.network_id,
                    "timestamp_utc": unified_report.timestamp_utc,
                    "processing_time_ms": unified_report.processing_time_ms,
                    "status": unified_report.status,
                    "affected_devices": unified_report.affected_devices,
                    "affected_interfaces": unified_report.affected_interfaces,
                },
            )
        )

        # 2. Input Telemetry and Normalization
        has_telemetry = len(evidence_records) > 0
        sections.append(
            TechnicalSection(
                section_id="input_telemetry",
                title="Input Telemetry and Normalization",
                order=2,
                is_available=has_telemetry,
                summary=(
                    "Telemetry ingestion audit, domain distributions, and normalized units."
                    if has_telemetry
                    else "No input telemetry records supplied or preserved."
                ),
                data={
                    "total_evidence_items": len(evidence_records),
                    "normalized_units": list({ev.unit for ev in evidence_records if ev.unit}),
                    "entities_covered": list({ev.entity for ev in evidence_records if ev.entity}),
                    "domains_represented": list({ev.category for ev in evidence_records if ev.category}),
                }
                if has_telemetry
                else {"status": "unavailable", "reason": "No input telemetry records supplied."},
            )
        )

        # 3. Topology Context and Affected Paths
        has_topology = topology_ref is not None and bool(topology_ref.affected_node_ids)
        sections.append(
            TechnicalSection(
                section_id="topology_and_paths",
                title="Topology Context and Affected Paths",
                order=3,
                is_available=has_topology,
                summary=(
                    "Demonstration campus topology linkage and logical hop paths."
                    if has_topology
                    else "Topology unmapped or uncorroborated."
                ),
                data=topology_ref.model_dump()
                if topology_ref
                else {"status": "unavailable", "reason": "Topology context not supplied or unmapped."},
            )
        )

        # 4. Anomaly and Fault-Detection Findings
        has_anomalies = len(evidence_records) > 0
        sections.append(
            TechnicalSection(
                section_id="anomaly_detection",
                title="Anomaly and Fault-Detection Findings",
                order=4,
                is_available=has_anomalies,
                summary=(
                    "Metric anomaly detections filtered against baseline thresholds."
                    if has_anomalies
                    else "No metric anomalies detected."
                ),
                data={
                    "anomalies": [
                        {
                            "metric": ev.metric_name,
                            "entity": ev.entity,
                            "observed_value": ev.value,
                            "unit": ev.unit,
                            "severity": ev.severity.value,
                            "finding": ev.finding,
                        }
                        for ev in evidence_records
                    ]
                }
                if has_anomalies
                else {"status": "unavailable", "anomalies": [], "reason": "Zero metric anomalies flagged."},
            )
        )

        # 5. Root-Cause Hypotheses
        has_hyp = bool(unified_report.probable_cause) or bool(
            getattr(unified_report.uncertainty, "alternative_hypotheses", [])
        )
        sections.append(
            TechnicalSection(
                section_id="hypotheses_evaluation",
                title="Root-Cause Hypotheses and Causal Inference",
                order=5,
                is_available=has_hyp,
                summary=(
                    "Hypothesis ranking, deterministic signature matching, and causal chain inference."
                    if has_hyp
                    else "Hypothesis generation inconclusive; insufficient corroborating evidence."
                ),
                data={
                    "evaluated_cause": unified_report.probable_cause,
                    "confidence": unified_report.confidence,
                    "causal_chain": unified_report.causal_chain,
                    "alternative_hypotheses": getattr(
                        unified_report.uncertainty, "alternative_hypotheses", []
                    ),
                    "uncertainty_score": getattr(unified_report.uncertainty, "score", 0.0),
                    "missing_evidence_domains": getattr(
                        unified_report.uncertainty, "missing_evidence", []
                    ),
                },
            )
        )

        # 6. Evidence Records and Source References
        sections.append(
            TechnicalSection(
                section_id="evidence_records",
                title="Evidence Records and Source References",
                order=6,
                is_available=len(evidence_records) > 0,
                summary=(
                    "Normalized, traceable evidence inventory with stable IDs and agent source attribution."
                    if evidence_records
                    else "No evidence records collected."
                ),
                data={"records": [ev.model_dump() for ev in evidence_records]}
                if evidence_records
                else {"status": "unavailable", "records": [], "reason": "No evidence items provided."},
            )
        )

        # 7. Specialist-Agent Findings
        has_agents = len(evidence_records) > 0
        sections.append(
            TechnicalSection(
                section_id="specialist_findings",
                title="Specialist-Agent Findings Breakdown",
                order=7,
                is_available=has_agents,
                summary=(
                    "Domain-specific evaluations produced across specialist agent envelopes."
                    if has_agents
                    else "No specialist findings recorded."
                ),
                data={
                    "contributing_specialists": list({ev.source_agent for ev in evidence_records}),
                    "findings_by_agent": {
                        agent: [
                            {"entity": ev.entity, "finding": ev.finding, "severity": ev.severity.value}
                            for ev in evidence_records
                            if ev.source_agent == agent
                        ]
                        for agent in {ev.source_agent for ev in evidence_records}
                    },
                }
                if has_agents
                else {"status": "unavailable", "reason": "No specialist agent findings recorded."},
            )
        )

        # 8. Mediator and Conflict-Resolution Decisions
        has_conflicts = bool(unified_report.conflicts_resolved)
        sections.append(
            TechnicalSection(
                section_id="arbitration",
                title="Mediator Arbitration and Conflict Resolution",
                order=8,
                is_available=True,
                summary=(
                    f"Arbitrated {len(unified_report.conflicts_resolved)} cross-agent contradictions."
                    if has_conflicts
                    else "No contradictory hypotheses detected between specialist agents."
                ),
                data={
                    "conflicts_resolved": unified_report.conflicts_resolved,
                    "arbitration_rule": "Direct Telemetry > Correlated Telemetry > Topology Inference",
                    "conflict_status": "contradictions_resolved" if has_conflicts else "concordant",
                },
            )
        )

        # 9. Confidence, Calibration, and Abstention Information
        sections.append(
            TechnicalSection(
                section_id="confidence_calibration",
                title="Confidence Calibration and Statistical Abstention",
                order=9,
                is_available=calib_data.is_calibrated,
                summary=(
                    "Scientific calibration breakdown, isotonic probabilities, and conformal coverage bounds."
                    if calib_data.is_calibrated
                    else "Uncalibrated heuristic confidence; statistical ML calibration was not executed."
                ),
                data=calib_data.model_dump(),
            )
        )

        # 10. Recommended Remediation and Approval State
        has_actions = len(recommended_actions) > 0
        sections.append(
            TechnicalSection(
                section_id="remediation_plan",
                title="Recommended Remediation and Approval State",
                order=10,
                is_available=has_actions,
                summary=(
                    "Simulated remediation actions, CLI syntax, rollback safety, and operator gate status."
                    if has_actions
                    else "No remediation actions proposed for this incident status."
                ),
                data={
                    "is_simulated_only": True,
                    "actions": [act.model_dump() for act in recommended_actions],
                }
                if has_actions
                else {"status": "unavailable", "actions": [], "reason": "No actions proposed."},
            )
        )

        # 11. Audit and Replay References
        sections.append(
            TechnicalSection(
                section_id="audit_replay",
                title="Audit and Replay Trace References",
                order=11,
                is_available=audit_ref.audit_logged,
                summary=(
                    "Traceability references linking report to persistent SQLite envelope logs and checkpoints."
                    if audit_ref.audit_logged
                    else "Audit record not verified in persistent storage."
                ),
                data=audit_ref.model_dump(),
            )
        )

        # 12. Recovery Verification and Unresolved Limitations
        sections.append(
            TechnicalSection(
                section_id="recovery_limitations",
                title="Recovery Verification and Data Limitations",
                order=12,
                is_available=True,
                summary="Independent recovery verification status, data caveats, and boundary conditions.",
                data={
                    "recovery_status": recovery_status.value,
                    "data_limitations": unified_report.limitations,
                    "unresolved_ambiguity_reasons": getattr(
                        unified_report.uncertainty, "reasons", []
                    ),
                },
            )
        )

        return sections


def export_hackathon_report_json(unified_report: Any) -> Dict[str, Any]:
    """Export a UnifiedDiagnosticReport or dictionary into the hackathon required JSON shape.

    Keys:
    - incident_id
    - status
    - suspected_root_cause
    - confidence
    - affected_devices
    - supporting_evidence: [{metric, value, interpretation}]
    - alternative_causes
    - recommended_actions: list of strings
    - evidence_sources
    - limitations
    """
    if hasattr(unified_report, "model_dump"):
        data = unified_report.model_dump()
    elif isinstance(unified_report, dict):
        data = unified_report
    else:
        raise ValueError("unified_report must be a model or dict")

    incident_id = data.get("incident_id")
    status = data.get("status")
    suspected_root_cause = data.get("probable_cause")
    confidence = data.get("confidence", 0.0)
    affected_devices = list(data.get("affected_devices") or [])

    raw_evidence = data.get("evidence") or []
    supporting_evidence = []
    evidence_sources_set = set()
    for ev in raw_evidence:
        if isinstance(ev, dict):
            metric = ev.get("metric_name")
            val = ev.get("value")
            interp = ev.get("finding") or ev.get("interpretation")
            src = ev.get("source_agent")
        else:
            metric = getattr(ev, "metric_name", None)
            val = getattr(ev, "value", None)
            interp = getattr(ev, "finding", None) or getattr(ev, "interpretation", None)
            src = getattr(ev, "source_agent", None)
        if src:
            evidence_sources_set.add(src)
        supporting_evidence.append({
            "metric": metric,
            "value": val,
            "interpretation": interp,
        })

    uncertainty = data.get("uncertainty") or {}
    alt_hyps = uncertainty.get("alternative_hypotheses") if isinstance(uncertainty, dict) else getattr(uncertainty, "alternative_hypotheses", [])
    alternative_causes = []
    for h in alt_hyps or []:
        if isinstance(h, dict):
            cause = h.get("cause") or h.get("title")
        else:
            cause = getattr(h, "cause", None) or getattr(h, "title", None)
        if cause:
            alternative_causes.append(cause)

    raw_actions = data.get("remediation_actions") or []
    recommended_actions = []
    for act in raw_actions:
        if isinstance(act, str):
            recommended_actions.append(act)
        elif isinstance(act, dict):
            action_str = act.get("action") or act.get("description") or act.get("title")
            if action_str:
                recommended_actions.append(action_str)
        else:
            action_str = getattr(act, "action", None) or getattr(act, "description", None) or getattr(act, "title", None)
            if action_str:
                recommended_actions.append(action_str)

    evidence_sources = sorted(list(evidence_sources_set))
    limitations = list(data.get("limitations") or [])

    return {
        "incident_id": incident_id,
        "status": status,
        "suspected_root_cause": suspected_root_cause,
        "confidence": confidence,
        "affected_devices": affected_devices,
        "supporting_evidence": supporting_evidence,
        "alternative_causes": alternative_causes,
        "recommended_actions": recommended_actions,
        "evidence_sources": evidence_sources,
        "limitations": limitations,
    }

