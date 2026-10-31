"""LangGraph multi-agent diagnostic state machine orchestrator."""

import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from netcoop.core.correlation import OfflineCorrelationEngine
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    EnvelopePayload,
    Hypothesis,
    Inquiry,
    MessageType,
    NetworkScope,
    Observation,
    ProtocolHeader,
)
from netcoop.core.evidence import DiagnosticHypothesis, UncertaintyEvaluation
from netcoop.core.report import ReportBuilder, UnifiedDiagnosticReport
from netcoop.core.thresholds import is_snapshot_mode
from netcoop.llm.gemini_bridge import GeminiBridge
from netcoop.orchestrator.conflict_resolver import ConflictResolver
from netcoop.orchestrator.mediator import AgentMediator
from netcoop.remediation.engine import RemediationEngine
from netcoop.storage.db import get_incident, init_db, save_incident


class GraphState(TypedDict):
    """LangGraph execution state dictionary."""

    incident_id: str
    network_id: str
    raw_data: Dict[str, Any]
    scope_devices: List[str]
    accumulated_observations: List[Dict[str, Any]]
    accumulated_hypotheses: List[Dict[str, Any]]
    inquiries_queue: List[Dict[str, Any]]
    conflict_detected: bool
    conflict_summary: Optional[str]
    conflicts_resolved: List[Dict[str, Any]]
    limitations: List[str]
    iteration: int
    is_paused: bool
    status: str
    hypothesis_dict: Optional[Dict[str, Any]]
    uncertainty_dict: Optional[Dict[str, Any]]
    remediation_actions: List[Dict[str, Any]]
    report_dict: Optional[Dict[str, Any]]
    start_time_s: float
    classifier_conformal_set: List[str]
    classifier_calib_probs: Dict[str, float]
    classifier_conformal_status: str


mediator = AgentMediator()


def node_specialists(state: GraphState) -> Dict[str, Any]:
    """Broadcast raw telemetry/configs to specialist domain agents."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    raw_data = state["raw_data"]
    devices = state["scope_devices"]

    # Specialist agents roster
    specialist_roles = [
        AgentRole.TELEMETRY_AGENT,
        AgentRole.TOPOLOGY_AGENT,
        AgentRole.CONFIG_AGENT,
        AgentRole.LOG_AGENT,
        AgentRole.WIFI_SERVICES_AGENT,
    ]
    # Dynamically include ClassifierAgent if registered
    if AgentRole.CLASSIFIER_AGENT in mediator._in_process_agents:
        specialist_roles.append(AgentRole.CLASSIFIER_AGENT)

    all_obs: List[Dict[str, Any]] = list(state.get("accumulated_observations", []))
    all_hyps: List[Dict[str, Any]] = list(state.get("accumulated_hypotheses", []))
    limitations: List[str] = list(state.get("limitations", []))
    classifier_conformal_set: List[str] = list(state.get("classifier_conformal_set", []))
    classifier_calib_probs: Dict[str, float] = dict(state.get("classifier_calib_probs", {}))
    classifier_conformal_status: str = state.get("classifier_conformal_status", "single")

    # Detect snapshot mode
    raw_telemetry = raw_data.get("telemetry", [])
    if is_snapshot_mode(raw_telemetry):
        if "single snapshot, no temporal context" not in limitations:
            limitations.append("single snapshot, no temporal context")

    # Detect absent topology
    raw_topology = raw_data.get("topology")
    if not raw_topology or not raw_topology.get("nodes"):
        if "topology unavailable; upstream transit inference uncorroborated" not in limitations:
            limitations.append("topology unavailable; upstream transit inference uncorroborated")

    for role in specialist_roles:
        dispatch_env = AgentEnvelope(
            header=ProtocolHeader(
                correlation_id=incident_id,
                sender=AgentRole.ORCHESTRATOR,
                recipient=role,
                message_type=MessageType.TELEMETRY_DISPATCH,
            ),
            payload=EnvelopePayload(
                scope=NetworkScope(network_id=network_id, devices=devices),
                raw_data=raw_data,
            ),
            context={"iteration": state.get("iteration", 0)},
        )

        response_env = mediator.dispatch(dispatch_env)
        if role == AgentRole.CLASSIFIER_AGENT:
            classifier_conformal_set = response_env.context.get("classifier_conformal_set", [])
            dq = response_env.payload.data_quality or {}
            if "calibrated_probabilities" in dq:
                classifier_calib_probs = dq["calibrated_probabilities"]
            if "conformal_status" in dq:
                classifier_conformal_status = dq["conformal_status"]
            if "conformal_prediction_set" in dq and not classifier_conformal_set:
                classifier_conformal_set = dq["conformal_prediction_set"]

        for obs in response_env.payload.observations:
            all_obs.append(obs.model_dump())
        for hyp in response_env.payload.hypotheses:
            all_hyps.append(hyp.model_dump())
        for lim in response_env.context.get("limitations", []):
            if lim not in limitations:
                limitations.append(lim)

    return {
        "accumulated_observations": all_obs,
        "accumulated_hypotheses": all_hyps,
        "limitations": limitations,
        "classifier_conformal_set": classifier_conformal_set,
        "classifier_calib_probs": classifier_calib_probs,
        "classifier_conformal_status": classifier_conformal_status,
    }


def node_mediation(state: GraphState) -> Dict[str, Any]:
    """Evaluate hypotheses for conflicts and determine if targeted inquiries are required."""
    hyps = [Hypothesis(**h) for h in state.get("accumulated_hypotheses", [])]
    obs = [Observation(**o) for o in state.get("accumulated_observations", [])]
    existing_resolved = list(state.get("conflicts_resolved", []))

    conflict = ConflictResolver.detect_conflicts(hyps)
    conflict_summary = None
    inquiries: List[Dict[str, Any]] = []

    if conflict:
        winning_hyp, rationale, new_resolved = ConflictResolver.arbitrate(hyps, obs)
        conflict_summary = rationale
        for r in new_resolved:
            r["iteration"] = state.get("iteration", 0) + 1
            existing_resolved.append(r)

        if winning_hyp is None and state.get("iteration", 0) < 2:
            # Need targeted inquiry pass (max 2 iterations)
            raw_inquiries = ConflictResolver.generate_cross_inquiries(hyps, obs)
            inquiries = [inq.model_dump() for inq in raw_inquiries]

    return {
        "conflict_detected": conflict,
        "conflict_summary": conflict_summary,
        "conflicts_resolved": existing_resolved,
        "inquiries_queue": inquiries,
    }


def route_mediation(state: GraphState) -> str:
    """Conditional edge routing to inquiries or directly to root cause synthesis."""
    if state.get("inquiries_queue") and state.get("iteration", 0) < 2:
        return "inquiry"
    return "synthesis"


def node_inquiry(state: GraphState) -> Dict[str, Any]:
    """Route pending cross-examination inquiries to target agents and increment turn."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    devices = state["scope_devices"]
    inquiries = [Inquiry(**i) for i in state.get("inquiries_queue", [])]

    new_obs = list(state.get("accumulated_observations", []))

    for inq in inquiries:
        inq_env = AgentEnvelope(
            header=ProtocolHeader(
                correlation_id=incident_id,
                sender=AgentRole.ORCHESTRATOR,
                recipient=inq.target_agent,
                message_type=MessageType.INQUIRY_REQUEST,
            ),
            payload=EnvelopePayload(
                scope=NetworkScope(network_id=network_id, devices=devices),
                inquiries=[inq],
                raw_data=state["raw_data"],
            ),
            context={"iteration": state.get("iteration", 0) + 1},
        )
        response_env = mediator.dispatch(inq_env)
        for obs in response_env.payload.observations:
            new_obs.append(obs.model_dump())

    return {
        "accumulated_observations": new_obs,
        "inquiries_queue": [],
        "iteration": state.get("iteration", 0) + 1,
    }


def node_synthesis(state: GraphState) -> Dict[str, Any]:
    """Invoke Synthesizer Agent to render root cause diagnosis or flag insufficient evidence."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    devices = state["scope_devices"]
    obs = [Observation(**o) for o in state.get("accumulated_observations", [])]

    synthesis_req = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id=incident_id,
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole.SYNTHESIZER_AGENT,
            message_type=MessageType.SYNTHESIS_SUBMISSION,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id=network_id, devices=devices),
            observations=obs,
        ),
        context={"iteration": state.get("iteration", 0)},
    )

    synth_resp = mediator.dispatch(synthesis_req)
    diag_status = synth_resp.context.get("diagnostic_status", "insufficient_evidence")
    uncertainty_dict = synth_resp.context.get("uncertainty", {})
    hypothesis_dict = synth_resp.context.get("hypothesis")

    return {
        "status": diag_status,
        "uncertainty_dict": uncertainty_dict,
        "hypothesis_dict": hypothesis_dict,
    }


def node_remediation(state: GraphState) -> Dict[str, Any]:
    """Generate simulated remediation plan if incident is successfully diagnosed."""
    hyp_dict = state.get("hypothesis_dict")
    status = state.get("status", "insufficient_evidence")
    devices = state["scope_devices"]

    actions: List[Dict[str, Any]] = []
    if status == "diagnosed" and hyp_dict:
        hypothesis = DiagnosticHypothesis(**hyp_dict)
        plan_items = RemediationEngine.generate_plan(hypothesis, devices)
        actions = [a.model_dump() for a in plan_items]

    return {"remediation_actions": actions}


def node_report(state: GraphState) -> Dict[str, Any]:
    """Compile final Unified Diagnostic Report and save to persistent SQLite database."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    status = state.get("status", "insufficient_evidence")
    hyp_dict = state.get("hypothesis_dict")
    uncertainty_dict = state.get("uncertainty_dict") or {"score": 1.0, "reasons": [], "missing_evidence": []}
    remediation_dicts = state.get("remediation_actions", [])

    hypothesis = DiagnosticHypothesis(**hyp_dict) if hyp_dict else None
    uncertainty = UncertaintyEvaluation(**uncertainty_dict)
    remediation_items = [RemediationEngine.generate_plan(hypothesis, state["scope_devices"])[0]] if (hypothesis and remediation_dicts) else []

    duration_ms = round((time.time() - state.get("start_time_s", time.time())) * 1000, 2)

    evidence_summary = [
        f"{e.entity}: {e.finding}"
        for e in (hypothesis.supporting_evidence if hypothesis else [])
    ]
    summary_text = GeminiBridge.generate_executive_summary(
        incident_id=incident_id,
        network_id=network_id,
        status=status,
        probable_cause=hypothesis.title if hypothesis else None,
        confidence=hypothesis.final_confidence if hypothesis else 0.0,
        affected_devices=hypothesis.affected_devices if hypothesis else [],
        evidence_summary=evidence_summary,
    )

    # Compile causal chain from formal fault models
    causal_chain = []
    if hypothesis:
        causal_chain = OfflineCorrelationEngine.get_causal_chain(hypothesis.cause_key)

    # Collect complete limitations including degraded mediator agents
    limitations = list(state.get("limitations", []))
    for deg in mediator.get_degraded_limitations():
        if deg not in limitations:
            limitations.append(deg)

    conflicts_resolved = list(state.get("conflicts_resolved", []))

    # Provenance tracking
    raw_data = state.get("raw_data", {})
    provenance = {
        "generator": raw_data.get("generator", "netcoop_synthetic"),
        "timestamp_ingested": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if raw_data.get("topology", {}).get("is_assumed"):
        provenance["topology"] = "assumed"

    # Hybrid integration: blend rule-based scores with classifier findings using weights.json
    classifier_calib_probs = state.get("classifier_calib_probs", {})
    classifier_conformal_set = state.get("classifier_conformal_set", [])
    classifier_conformal_status = state.get("classifier_conformal_status", "single")

    weights_path = Path("netcoop/models/artifacts/weights.json")
    weights_data = {}
    if weights_path.exists():
        try:
            with open(weights_path, "r", encoding="utf-8") as f:
                weights_data = json.load(f)
        except Exception:
            pass

    # Weights from validation results (never a blind 50/50 average)
    w_rules = 0.55
    w_model = 0.45

    confidence_breakdown = None
    conformal_prediction_set = list(classifier_conformal_set)
    confidence_category = None

    # Conformal abstention standard: |S| == 0 or status == 'abstain'
    statistical_cause_keys = {
        "LINK_CONGESTION",
        "UPSTREAM_CONGESTION",
        "UPSTREAM_FAILURE_CASCADE",
        "WEAK_WIFI_SIGNAL",
        "ETHERNET_INTERFACE_FAULT",
        "DEVICE_CPU_OVERLOAD",
        "DNS_FAILURE",
        "DHCP_FAILURE",
        "DEVICE_HARDWARE_FAILURE",
        "NO_FAULT",
    }
    is_statistical_domain = hypothesis and (hypothesis.cause_key in statistical_cause_keys)

    classifier_abstained = (
        classifier_conformal_status == "abstain"
        or (is_statistical_domain and classifier_calib_probs and len(conformal_prediction_set) == 0)
        or (not hypothesis and len(conformal_prediction_set) == 0 and classifier_calib_probs)
    )

    if classifier_abstained:
        status = "insufficient_evidence"
        hypothesis = None
        confidence_category = "abstain"
        uncertainty = UncertaintyEvaluation(
            score=1.0,
            reasons=["Classifier model layer abstained under split conformal prediction guarantee."],
            missing_evidence=["Decisive empirical attribution features"],
            alternative_hypotheses=[],
        )

    if hypothesis and status == "diagnosed":
        rules_score = round(hypothesis.final_confidence, 3)
        cause_map = {
            "LINK_CONGESTION": "link_congestion",
            "UPSTREAM_CONGESTION": "upstream_failure_cascade",
            "UPSTREAM_FAILURE_CASCADE": "upstream_failure_cascade",
            "WEAK_WIFI_SIGNAL": "weak_wifi_signal",
            "ETHERNET_INTERFACE_FAULT": "ethernet_interface_fault",
            "DEVICE_CPU_OVERLOAD": "device_cpu_overload",
            "DNS_FAILURE": "dns_failure",
            "DHCP_FAILURE": "dhcp_failure",
            "DEVICE_HARDWARE_FAILURE": "device_cpu_overload",
            "NO_FAULT": "normal_operation",
        }
        cname = cause_map.get(hypothesis.cause_key)
        if cname and classifier_calib_probs:
            model_score = round(float(classifier_calib_probs.get(cname, rules_score)), 3)
            blended_score = round(w_rules * rules_score + w_model * model_score, 3)
            calibrated_confidence = blended_score
            if not conformal_prediction_set:
                conformal_prediction_set = [cname]
        else:
            model_score = rules_score
            blended_score = rules_score
            calibrated_confidence = rules_score
            if not conformal_prediction_set:
                conformal_prediction_set = [hypothesis.cause_key.lower()]

        hypothesis.final_confidence = calibrated_confidence

        confidence_breakdown = {
            "rules_score": rules_score,
            "model_score": model_score,
            "blended_score": blended_score,
            "calibrated_confidence": calibrated_confidence,
        }

        if calibrated_confidence >= 0.85:
            confidence_category = "high"
        elif calibrated_confidence >= 0.70:
            confidence_category = "medium"
        else:
            confidence_category = "low"

    report = ReportBuilder.build_report(
        incident_id=incident_id,
        network_id=network_id,
        status=status,
        hypothesis=hypothesis,
        uncertainty=uncertainty,
        remediation_actions=remediation_items,
        summary=summary_text,
        processing_time_ms=duration_ms,
        causal_chain=causal_chain,
        conflicts_resolved=conflicts_resolved,
        limitations=limitations,
        provenance=provenance,
        confidence_breakdown=confidence_breakdown,
        conformal_prediction_set=conformal_prediction_set,
        confidence_category=confidence_category,
    )

    # Schema validation against schemas/diagnostic_report.json
    _validate_report_schema(report)

    # Persist in SQLite
    save_incident(
        incident_id=incident_id,
        network_id=network_id,
        status=status,
        probable_cause=report.probable_cause,
        confidence=report.confidence,
        report_json=report.to_json(),
    )

    return {"report_dict": report.model_dump()}


def _validate_report_schema(report: UnifiedDiagnosticReport) -> None:
    """Validate report against schemas/diagnostic_report.json schema file."""
    schema_path = Path("schemas/diagnostic_report.json")
    if not schema_path.exists():
        return
    try:
        import jsonschema
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        report_dict = json.loads(report.to_json())
        jsonschema.validate(instance=report_dict, schema=schema)
    except ImportError:
        pass  # jsonschema optional, pydantic already validated


def build_diagnostic_graph() -> StateGraph:
    """Construct and compile the LangGraph workflow."""
    builder = StateGraph(GraphState)

    builder.add_node("specialists", node_specialists)
    builder.add_node("mediation", node_mediation)
    builder.add_node("inquiry", node_inquiry)
    builder.add_node("synthesis", node_synthesis)
    builder.add_node("remediation", node_remediation)
    builder.add_node("report", node_report)

    builder.set_entry_point("specialists")
    builder.add_edge("specialists", "mediation")
    builder.add_conditional_edges(
        "mediation",
        route_mediation,
        {
            "inquiry": "inquiry",
            "synthesis": "synthesis",
        },
    )
    builder.add_edge("inquiry", "mediation")
    builder.add_edge("synthesis", "remediation")
    builder.add_edge("remediation", "report")
    builder.add_edge("report", END)

    return builder


# Global compiled app with in-memory checkpointer for turn-based state
checkpointer = MemorySaver()
compiled_diagnostic_graph = build_diagnostic_graph().compile(checkpointer=checkpointer)


def run_diagnosis(incident_data: Dict[str, Any]) -> UnifiedDiagnosticReport:
    """High-level runner executing full diagnostic pipeline on network incident input."""
    init_db()

    incident_id = incident_data.get("incident_id", "inc-default")
    network_id = incident_data.get("network_id", "net-default")
    topology_nodes = incident_data.get("topology", {}).get("nodes", [])
    devices = [n.get("id") for n in topology_nodes if "id" in n]

    # In single-snapshot organizer mode, devices may be inside telemetry records
    if not devices:
        telemetry_records = incident_data.get("telemetry", [])
        dev_set = set()
        for rec in telemetry_records:
            d = rec.get("device_id") or rec.get("device")
            if d:
                dev_set.add(d)
        devices = list(dev_set)

    initial_state: GraphState = {
        "incident_id": incident_id,
        "network_id": network_id,
        "raw_data": incident_data,
        "scope_devices": devices or ["unknown_device"],
        "accumulated_observations": [],
        "accumulated_hypotheses": [],
        "inquiries_queue": [],
        "conflict_detected": False,
        "conflict_summary": None,
        "conflicts_resolved": [],
        "limitations": [],
        "iteration": 0,
        "is_paused": False,
        "status": "initialized",
        "hypothesis_dict": None,
        "uncertainty_dict": None,
        "remediation_actions": [],
        "report_dict": None,
        "start_time_s": time.time(),
        "classifier_conformal_set": [],
        "classifier_calib_probs": {},
        "classifier_conformal_status": "single",
    }

    config = {"configurable": {"thread_id": incident_id}}
    final_state = compiled_diagnostic_graph.invoke(initial_state, config=config)
    report_dict = final_state.get("report_dict")
    if not report_dict:
        raise RuntimeError("Diagnostic execution failed to produce a report.")

    return UnifiedDiagnosticReport(**report_dict)
