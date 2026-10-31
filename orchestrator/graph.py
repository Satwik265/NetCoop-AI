"""LangGraph multi-agent diagnostic state machine orchestrator."""

import time
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

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
    iteration: int
    is_paused: bool
    status: str
    hypothesis_dict: Optional[Dict[str, Any]]
    uncertainty_dict: Optional[Dict[str, Any]]
    remediation_actions: List[Dict[str, Any]]
    report_dict: Optional[Dict[str, Any]]
    start_time_s: float


mediator = AgentMediator()


def node_specialists(state: GraphState) -> Dict[str, Any]:
    """Broadcast raw telemetry/configs to the 4 specialist domain agents."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    raw_data = state["raw_data"]
    devices = state["scope_devices"]

    specialist_roles = [
        AgentRole.TELEMETRY_AGENT,
        AgentRole.TOPOLOGY_AGENT,
        AgentRole.CONFIG_AGENT,
        AgentRole.LOG_AGENT,
    ]

    all_obs: List[Dict[str, Any]] = list(state.get("accumulated_observations", []))
    all_hyps: List[Dict[str, Any]] = list(state.get("accumulated_hypotheses", []))

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
        for obs in response_env.payload.observations:
            all_obs.append(obs.model_dump())
        for hyp in response_env.payload.hypotheses:
            all_hyps.append(hyp.model_dump())

    return {
        "accumulated_observations": all_obs,
        "accumulated_hypotheses": all_hyps,
    }


def node_mediation(state: GraphState) -> Dict[str, Any]:
    """Evaluate hypotheses for conflicts and determine if targeted inquiries are required."""
    hyps = [Hypothesis(**h) for h in state.get("accumulated_hypotheses", [])]
    obs = [Observation(**o) for o in state.get("accumulated_observations", [])]

    conflict = ConflictResolver.detect_conflicts(hyps)
    conflict_summary = None
    inquiries: List[Dict[str, Any]] = []

    if conflict:
        winning_hyp, rationale = ConflictResolver.arbitrate(hyps, obs)
        conflict_summary = rationale
        if winning_hyp is None and state.get("iteration", 0) < 2:
            # Need targeted inquiry pass
            raw_inquiries = ConflictResolver.generate_cross_inquiries(hyps, obs)
            inquiries = [inq.model_dump() for inq in raw_inquiries]

    return {
        "conflict_detected": conflict,
        "conflict_summary": conflict_summary,
        "inquiries_queue": inquiries,
    }


def route_mediation(state: GraphState) -> str:
    """Conditional edge routing to inquiries or directly to root cause synthesis."""
    if state.get("inquiries_queue") and state.get("iteration", 0) < 2:
        return "inquiry"
    return "synthesis"


def node_inquiry(state: GraphState) -> Dict[str, Any]:
    """Route pending inquiries to target agents and increment iteration turn."""
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

    report = ReportBuilder.build_report(
        incident_id=incident_id,
        network_id=network_id,
        status=status,
        hypothesis=hypothesis,
        uncertainty=uncertainty,
        remediation_actions=remediation_items,
        summary=summary_text,
        processing_time_ms=duration_ms,
    )

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
        "iteration": 0,
        "is_paused": False,
        "status": "initialized",
        "hypothesis_dict": None,
        "uncertainty_dict": None,
        "remediation_actions": [],
        "report_dict": None,
        "start_time_s": time.time(),
    }

    config = {"configurable": {"thread_id": incident_id}}
    final_state = compiled_diagnostic_graph.invoke(initial_state, config=config)
    report_dict = final_state.get("report_dict")
    if not report_dict:
        raise RuntimeError("Diagnostic execution failed to produce a report.")

    return UnifiedDiagnosticReport(**report_dict)
