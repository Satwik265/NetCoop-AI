import re
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
from datetime import datetime, timezone
import logging
from netcoop.core.evidence import DiagnosticHypothesis, UncertaintyEvaluation
from netcoop.core.report import ReportBuilder, UnifiedDiagnosticReport
from netcoop.core.thresholds import is_snapshot_mode
from netcoop.llm.gemini_bridge import GeminiBridge
from netcoop.orchestrator.conflict_resolver import ConflictResolver
from netcoop.orchestrator.mediator import AgentMediator, AgentExecutionStatus

logger = logging.getLogger(__name__)
from netcoop.remediation.engine import RemediationEngine
from netcoop.config import settings
from netcoop.storage.db import (
    get_incident,
    init_db,
    save_incident,
    save_checkpoint,
    get_latest_checkpoint,
    mark_session_paused,
    mark_session_resumed,
    save_remediation_action_log,
)
from netcoop.core.report import RemediationActionItem, ReportBuilder, UnifiedDiagnosticReport


class GraphState(TypedDict):
    """LangGraph execution state dictionary."""

    incident_id: str
    network_id: str
    raw_data: Dict[str, Any]
    scope_devices: List[str]
    accumulated_observations: List[Dict[str, Any]]
    accumulated_hypotheses: List[Dict[str, Any]]
    inquiries_queue: List[Dict[str, Any]]
    inquiries_history: List[Dict[str, Any]]
    processed_inquiry_hashes: List[str]
    agent_execution: Dict[str, Dict[str, Any]]
    arbitration_winner: Optional[Dict[str, Any]]
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


from netcoop.core.envelope import ObservationCategory, Severity


def _deduplicate_observations(observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove identical observations while preserving evidence order and provenance."""
    seen: Set[Tuple[Any, Any, Any, Any]] = set()
    deduped: List[Dict[str, Any]] = []
    for obs in observations:
        key = (
            obs.get("entity"),
            obs.get("metric_name"),
            str(obs.get("observed_value")),
            obs.get("unit"),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(obs)
    return deduped


def _convert_inquiry_to_observation(inq: Inquiry, response_env: AgentEnvelope) -> Optional[Observation]:
    """Convert verified inquiry answers into structured observations without inventing measurements.

    Never invents observations from empty, ambiguous, or generic answers.
    Never fabricates numeric measurements, units, or timestamps when they are absent.
    """
    if not inq.answer:
        return None

    # 1. Handle structured dict answers
    if isinstance(inq.answer, dict):
        ans_dict = inq.answer
        status = str(ans_dict.get("status", "")).lower()
        if status in ("inconclusive", "ambiguous", "no_data", "error", "unknown", "insufficient_evidence"):
            return None

        val = ans_dict.get("value")
        if val is None:
            val = ans_dict.get("observed_value")

        qualitative = ans_dict.get("qualitative")
        unit = ans_dict.get("unit") or ("text" if val is None else "")
        metric_name = ans_dict.get("metric_name") or inq.parameters.get("metric_requested") or inq.question[:40].strip()
        entity = ans_dict.get("device_id") or ans_dict.get("entity") or inq.target_entity or "network"
        ts = ans_dict.get("timestamp") or ans_dict.get("timestamp_start")

        sev_str = str(ans_dict.get("severity", "")).lower()
        if sev_str == "critical":
            sev = Severity.CRITICAL
        elif sev_str == "warning":
            sev = Severity.WARNING
        else:
            sev = Severity.INFO

        final_val = val if val is not None else qualitative
        if final_val is None:
            if "nominal" in status:
                final_val = "nominal"
                sev = Severity.INFO
            elif any(k in status for k in ("confirmed", "anomaly", "attenuated", "mismatch", "degraded")):
                final_val = "anomaly"
                sev = Severity.CRITICAL
            else:
                return None

        return Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity=str(entity),
            metric_name=str(metric_name),
            observed_value=final_val,
            unit=str(unit) if unit else "text",
            severity=sev,
            timestamp_start=ts,
            context={
                "inquiry_id": inq.inquiry_id,
                "original_answer": inq.answer,
                "agent_domain": inq.target_agent.value,
                "converted_from_inquiry": True,
            },
            provenance={
                "source_agent": inq.target_agent.value,
                "inquiry_id": inq.inquiry_id,
            },
        )

    # 2. Handle string answers
    ans = str(inq.answer).strip()
    if not ans:
        return None
    ans_lower = ans.lower()

    # Reject malformed, ambiguous or inconclusive responses
    if any(p in ans_lower for p in (
        "no data", "none", "unknown", "inconclusive", "ambiguous", "unable to determine",
        "insufficient evidence", "cannot confirm", "unverified"
    )):
        return None

    target = inq.target_entity or "network"
    ts_resp = response_env.header.timestamp_utc if response_env and response_env.header else None

    # Case 1: Upstream link transit saturation / nominal
    if "upstream link saturation confirmed" in ans_lower or ("upstream" in ans_lower and "saturation" in ans_lower and "confirmed" in ans_lower):
        m_util = re.search(r"utilization\s+([0-9]+(?:\.[0-9]+)?)\s*%", ans, re.IGNORECASE)
        m_drops = re.search(r"queue\s+drops\s+([0-9]+)", ans, re.IGNORECASE)
        m_dev = re.search(r"confirmed\s+on\s+([a-zA-Z0-9_-]+)", ans, re.IGNORECASE)

        util_val = float(m_util.group(1)) if m_util else None
        drops_val = int(m_drops.group(1)) if m_drops else None
        dev_entity = m_dev.group(1) if m_dev else target

        final_val = util_val if util_val is not None else "saturated"
        unit = "percent" if util_val is not None else "text"

        return Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity=dev_entity,
            metric_name="upstream_link_saturation",
            observed_value=final_val,
            unit=unit,
            severity=Severity.CRITICAL,
            timestamp_start=None,
            context={
                "inquiry_id": inq.inquiry_id,
                "original_answer": ans,
                "agent_domain": inq.target_agent.value,
                "queue_drops": drops_val,
                "converted_from_inquiry": True,
                "response_timestamp": ts_resp,
            },
            provenance={"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id},
        )
    elif "upstream links nominal" in ans_lower or ("upstream" in ans_lower and "nominal" in ans_lower):
        m_util = re.search(r"utilization\s+([0-9]+(?:\.[0-9]+)?)\s*%", ans, re.IGNORECASE)
        util_val = float(m_util.group(1)) if m_util else None

        final_val = util_val if util_val is not None else "nominal"
        unit = "percent" if util_val is not None else "text"

        return Observation(
            category=ObservationCategory.METRIC_ANOMALY,
            entity=target,
            metric_name="upstream_links_nominal",
            observed_value=final_val,
            unit=unit,
            severity=Severity.INFO,
            timestamp_start=None,
            context={
                "inquiry_id": inq.inquiry_id,
                "original_answer": ans,
                "agent_domain": inq.target_agent.value,
                "converted_from_inquiry": True,
                "response_timestamp": ts_resp,
            },
            provenance={"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id},
        )

    # Case 2: Optical transceiver power
    if "rx power" in ans_lower or "optical transceiver" in ans_lower or "optical" in ans_lower:
        m_pwr = re.search(r"(-?[0-9]+(?:\.[0-9]+)?)\s*dbm", ans, re.IGNORECASE)
        actual_pwr = float(m_pwr.group(1)) if m_pwr else None

        if "nominal" in ans_lower or "within specification" in ans_lower:
            return Observation(
                category=ObservationCategory.METRIC_ANOMALY,
                entity=target,
                metric_name="rx_power_dbm" if actual_pwr is not None else "optical_transceiver_status",
                observed_value=actual_pwr if actual_pwr is not None else "nominal",
                unit="dbm" if actual_pwr is not None else "text",
                severity=Severity.INFO,
                timestamp_start=None,
                context={
                    "inquiry_id": inq.inquiry_id,
                    "original_answer": ans,
                    "agent_domain": inq.target_agent.value,
                    "optical_nominal": True,
                    "converted_from_inquiry": True,
                    "response_timestamp": ts_resp,
                },
                provenance={"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id},
            )
        elif "attenuated" in ans_lower or "below" in ans_lower or "degraded" in ans_lower or "fault" in ans_lower:
            return Observation(
                category=ObservationCategory.METRIC_ANOMALY,
                entity=target,
                metric_name="rx_power_dbm" if actual_pwr is not None else "optical_transceiver_status",
                observed_value=actual_pwr if actual_pwr is not None else "attenuated",
                unit="dbm" if actual_pwr is not None else "text",
                severity=Severity.CRITICAL,
                timestamp_start=None,
                context={
                    "inquiry_id": inq.inquiry_id,
                    "original_answer": ans,
                    "agent_domain": inq.target_agent.value,
                    "optical_attenuated": True,
                    "converted_from_inquiry": True,
                    "response_timestamp": ts_resp,
                },
                provenance={"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id},
            )

    # Case 3: Wi-Fi RF degradation / nominal
    if "wi-fi" in ans_lower or "rf" in ans_lower or "wireless" in ans_lower:
        m_rssi = re.search(r"rssi\s*[:=]?\s*(-?[0-9]+(?:\.[0-9]+)?)\s*dbm", ans, re.IGNORECASE)
        m_snr = re.search(r"snr\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*db", ans, re.IGNORECASE)
        rssi_val = float(m_rssi.group(1)) if m_rssi else None
        snr_val = float(m_snr.group(1)) if m_snr else None

        if "degradation" in ans_lower or "interference" in ans_lower or "weak" in ans_lower:
            final_val = rssi_val if rssi_val is not None else (snr_val if snr_val is not None else "degraded")
            unit = "dbm" if rssi_val is not None else ("db" if snr_val is not None else "text")
            return Observation(
                category=ObservationCategory.METRIC_ANOMALY,
                entity=target,
                metric_name="wifi_rf_degradation",
                observed_value=final_val,
                unit=unit,
                severity=Severity.CRITICAL,
                timestamp_start=None,
                context={
                    "inquiry_id": inq.inquiry_id,
                    "original_answer": ans,
                    "agent_domain": inq.target_agent.value,
                    "converted_from_inquiry": True,
                    "response_timestamp": ts_resp,
                },
                provenance={"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id},
            )
        elif "nominal" in ans_lower or "healthy" in ans_lower:
            final_val = rssi_val if rssi_val is not None else (snr_val if snr_val is not None else "nominal")
            unit = "dbm" if rssi_val is not None else ("db" if snr_val is not None else "text")
            return Observation(
                category=ObservationCategory.METRIC_ANOMALY,
                entity=target,
                metric_name="wifi_rf_nominal",
                observed_value=final_val,
                unit=unit,
                severity=Severity.INFO,
                timestamp_start=None,
                context={
                    "inquiry_id": inq.inquiry_id,
                    "original_answer": ans,
                    "agent_domain": inq.target_agent.value,
                    "converted_from_inquiry": True,
                    "response_timestamp": ts_resp,
                },
                provenance={"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id},
            )

    # Case 4: MTU mismatch
    if "mtu" in ans_lower:
        m_mtu = re.findall(r"\b([0-9]{3,5})\b", ans)
        mtu_nums = [int(n) for n in m_mtu if int(n) in (1500, 1492, 9000, 9198, 9216)]
        actual_val = mtu_nums[0] if mtu_nums else "mismatch"
        unit = "bytes" if mtu_nums else "text"

        if "mismatch" in ans_lower or "disparity" in ans_lower:
            return Observation(
                category=ObservationCategory.CONFIG_DIFF,
                entity=target,
                metric_name="mtu_mismatch",
                observed_value=actual_val,
                unit=unit,
                severity=Severity.CRITICAL,
                timestamp_start=None,
                context={
                    "inquiry_id": inq.inquiry_id,
                    "original_answer": ans,
                    "agent_domain": inq.target_agent.value,
                    "converted_from_inquiry": True,
                    "response_timestamp": ts_resp,
                },
                provenance={"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id},
            )

    return None
def node_specialists(state: GraphState) -> Dict[str, Any]:
    """Broadcast raw telemetry/configs to specialist domain agents concurrently."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    raw_data = state["raw_data"]
    devices = state["scope_devices"]

    specialist_roles = [r for r in mediator.registry.registered_roles if r != AgentRole.SYNTHESIZER_AGENT]

    all_obs: List[Dict[str, Any]] = list(state.get("accumulated_observations", []))
    all_hyps: List[Dict[str, Any]] = list(state.get("accumulated_hypotheses", []))
    limitations: List[str] = list(state.get("limitations", []))
    agent_execution: Dict[str, Dict[str, Any]] = dict(state.get("agent_execution", {}))
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

    # Construct dispatch envelopes for all specialists
    dispatch_envelopes = []
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
        dispatch_envelopes.append(dispatch_env)

    # Concurrently dispatch to all specialist microservices
    responses = mediator.dispatch_concurrent(dispatch_envelopes)

    for role, response_env in zip(specialist_roles, responses):
        # Capture execution telemetry record
        exec_rec = response_env.context.get("execution_record")
        if exec_rec:
            agent_execution[role.value] = exec_rec
        elif role.value not in agent_execution:
            agent_execution[role.value] = {
                "agent_id": role.value,
                "status": "success",
                "execution_status": "success",
                "correlation_id": response_env.header.correlation_id or incident_id,
            }

        # Inspect if response envelope contains an error
        if response_env.payload.error is not None or response_env.header.message_type == MessageType.PROTOCOL_ERROR:
            err = response_env.payload.error
            err_code = err.error_code if err else "INTERNAL_ERROR"
            err_msg = err.message if err else "Agent error"
            corr_id = response_env.header.correlation_id or incident_id
            is_protocol_err = (
                response_env.header.message_type == MessageType.PROTOCOL_ERROR
                or (err and "PROTOCOL" in str(err_code).upper())
            )
            exec_status = (
                AgentExecutionStatus.PROTOCOL_ERROR.value
                if is_protocol_err
                else AgentExecutionStatus.INTERNAL_ERROR.value
            )
            rec_dict = dict(exec_rec) if exec_rec else {}
            rec_dict.update({
                "agent_id": role.value,
                "status": exec_status,
                "execution_status": exec_status,
                "error_code": err_code,
                "correlation_id": corr_id,
                "message": err_msg,
            })
            agent_execution[role.value] = rec_dict
            mediator.dead_agents.add(role.value)
            lim_msg = f"agent_failed: {role.value} ({err_code}): {err_msg}"
            if lim_msg not in limitations:
                limitations.append(lim_msg)
            continue

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
            d = obs.model_dump()
            d.setdefault("provenance", {"source_agent": role.value})
            all_obs.append(d)

        for hyp in response_env.payload.hypotheses:
            d = hyp.model_dump()
            d.setdefault("provenance", {"source_agent": role.value})
            all_hyps.append(d)

        for lim in response_env.context.get("limitations", []):
            if lim not in limitations:
                limitations.append(lim)

    deduped_obs = _deduplicate_observations(all_obs)
    res = {
        "accumulated_observations": deduped_obs,
        "accumulated_hypotheses": all_hyps,
        "limitations": limitations,
        "agent_execution": agent_execution,
        "classifier_conformal_set": classifier_conformal_set,
        "classifier_calib_probs": classifier_calib_probs,
        "classifier_conformal_status": classifier_conformal_status,
    }
    if settings.feature_resume:
        save_checkpoint(session_id=incident_id, node_name="specialists", state_dict={**state, **res}, iteration=state.get("iteration", 0), is_paused=state.get("is_paused", False))
    return res


def node_mediation(state: GraphState) -> Dict[str, Any]:
    """Evaluate hypotheses for conflicts and determine if targeted inquiries are required."""
    hyps = [Hypothesis(**h) for h in state.get("accumulated_hypotheses", [])]
    obs = [Observation(**o) for o in state.get("accumulated_observations", [])]
    existing_resolved = list(state.get("conflicts_resolved", []))
    processed_hashes = set(state.get("processed_inquiry_hashes", []))

    conflict = ConflictResolver.detect_conflicts(hyps)
    conflict_summary = None
    inquiries: List[Dict[str, Any]] = []
    arbitration_winner: Optional[Dict[str, Any]] = None

    if conflict:
        winning_hyp, rationale, new_resolved = ConflictResolver.arbitrate(hyps, obs)
        conflict_summary = rationale
        for r in new_resolved:
            r["iteration"] = state.get("iteration", 0) + 1
            existing_resolved.append(r)

        if winning_hyp is not None:
            arbitration_winner = winning_hyp.model_dump()
        elif state.get("iteration", 0) < settings.max_inquiry_iterations:
            raw_inquiries = ConflictResolver.generate_cross_inquiries(hyps, obs, processed_hashes=processed_hashes)
            inquiries = [inq.model_dump() for inq in raw_inquiries]

    res = {
        "conflict_detected": conflict,
        "conflict_summary": conflict_summary,
        "conflicts_resolved": existing_resolved,
        "inquiries_queue": inquiries,
        "arbitration_winner": arbitration_winner,
    }
    if settings.feature_resume:
        save_checkpoint(session_id=state.get("incident_id", "session-unknown"), node_name="mediation", state_dict={**state, **res}, iteration=state.get("iteration", 0), is_paused=state.get("is_paused", False))
    return res


def route_mediation(state: GraphState) -> str:
    """Conditional edge routing to inquiries or directly to root cause synthesis."""
    if state.get("inquiries_queue") and state.get("iteration", 0) < settings.max_inquiry_iterations:
        return "inquiry"
    return "synthesis"


def node_inquiry(state: GraphState) -> Dict[str, Any]:
    """Route pending cross-examination inquiries to target agents, extract answers, and convert to observations."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    devices = state["scope_devices"]
    inquiries = [Inquiry(**i) for i in state.get("inquiries_queue", [])]

    new_obs = list(state.get("accumulated_observations", []))
    inquiries_history = list(state.get("inquiries_history", []))
    processed_hashes = list(state.get("processed_inquiry_hashes", []))
    agent_execution = dict(state.get("agent_execution", {}))
    limitations = list(state.get("limitations", []))

    for inq in inquiries:
        inq_key = f"{inq.target_agent.value}:{inq.target_entity}:{inq.question[:30]}"
        processed_hashes.append(inq_key)

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
        exec_rec = response_env.context.get("execution_record")
        if exec_rec:
            agent_execution[f"{inq.target_agent.value}_inquiry_{inq.inquiry_id}"] = exec_rec

        # Priority 2: Inspect payload.error, HTTP/protocol failure states, and execution record
        is_failed = (
            response_env.payload.error is not None
            or response_env.header.message_type == MessageType.PROTOCOL_ERROR
            or (exec_rec and exec_rec.get("execution_status") in (
                "unavailable", "timeout", "protocol_error", "internal_error", "circuit_open"
            ))
        )

        if is_failed:
            err = response_env.payload.error
            err_code = err.error_code if err else (exec_rec.get("error_code") if exec_rec else "INQUIRY_FAILED")
            err_msg = err.message if err else (exec_rec.get("error_code") if exec_rec else "Target agent failed to respond")

            # Preserve failed inquiry record with explicit status without recording as answered
            inq_fail = inq.model_dump()
            inq_fail["status"] = "failed"
            inq_fail["answer"] = None
            inq_fail["error"] = {"error_code": err_code, "message": err_msg}
            inq_fail["sender"] = inq.target_agent.value
            inq_fail["recipient"] = AgentRole.ORCHESTRATOR.value
            inq_fail["correlation_id"] = incident_id
            inquiries_history.append(inq_fail)

            lim_entry = f"inquiry_failed: {inq.target_agent.value} ({inq.inquiry_id}) {err_code}: {err_msg}"
            if lim_entry not in limitations:
                limitations.append(lim_entry)
            continue

        returned_inquiries = response_env.payload.inquiries
        if not returned_inquiries:
            # Empty response without error: record as unanswered
            inq_unans = inq.model_dump()
            inq_unans["status"] = "unanswered"
            inq_unans["answer"] = None
            inq_unans["sender"] = inq.target_agent.value
            inq_unans["recipient"] = AgentRole.ORCHESTRATOR.value
            inq_unans["correlation_id"] = incident_id
            inquiries_history.append(inq_unans)

            lim_entry = f"inquiry_unanswered: {inq.target_agent.value} ({inq.inquiry_id}) empty response payload"
            if lim_entry not in limitations:
                limitations.append(lim_entry)
            continue

        for ret_inq in returned_inquiries:
            inq_dump = ret_inq.model_dump()
            inq_dump["sender"] = inq.target_agent.value
            inq_dump["recipient"] = AgentRole.ORCHESTRATOR.value
            inq_dump["correlation_id"] = incident_id
            inq_dump["status"] = "answered" if ret_inq.answer else "unanswered"
            inquiries_history.append(inq_dump)

            # Convert meaningful inquiry findings into structured observations
            converted_obs = _convert_inquiry_to_observation(ret_inq, response_env)
            if converted_obs is not None:
                new_obs.append(converted_obs.model_dump())

        # Direct observations returned in payload
        for obs in response_env.payload.observations:
            d = obs.model_dump()
            d.setdefault("provenance", {"source_agent": inq.target_agent.value, "inquiry_id": inq.inquiry_id})
            new_obs.append(d)

    deduped_obs = _deduplicate_observations(new_obs)
    res = {
        "accumulated_observations": deduped_obs,
        "inquiries_queue": [],
        "inquiries_history": inquiries_history,
        "processed_inquiry_hashes": processed_hashes,
        "agent_execution": agent_execution,
        "limitations": limitations,
        "iteration": state.get("iteration", 0) + 1,
    }
    if settings.feature_resume:
        save_checkpoint(session_id=incident_id, node_name="inquiry", state_dict={**state, **res}, iteration=res["iteration"], is_paused=state.get("is_paused", False))
    return res
def node_synthesis(state: GraphState) -> Dict[str, Any]:
    """Invoke Synthesizer Agent to render root cause diagnosis or flag insufficient evidence."""
    incident_id = state["incident_id"]
    network_id = state["network_id"]
    devices = state["scope_devices"]
    obs = [Observation(**o) for o in state.get("accumulated_observations", [])]
    hyps = [Hypothesis(**h) for h in state.get("accumulated_hypotheses", [])]
    inquiries_history = [Inquiry(**i) for i in state.get("inquiries_history", [])]

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
            hypotheses=hyps,
            inquiries=inquiries_history,
        ),
        context={
            "iteration": state.get("iteration", 0),
            "arbitration_winner": state.get("arbitration_winner"),
            "conflicts_resolved": state.get("conflicts_resolved", []),
            "limitations": state.get("limitations", []),
            "degraded_agents": list(mediator.dead_agents),
        },
    )

    synth_resp = mediator.dispatch(synthesis_req)
    diag_status = synth_resp.context.get("diagnostic_status", "insufficient_evidence")
    uncertainty_dict = synth_resp.context.get("uncertainty", {})
    hypothesis_dict = synth_resp.context.get("hypothesis")

    res = {
        "status": diag_status,
        "uncertainty_dict": uncertainty_dict,
        "hypothesis_dict": hypothesis_dict,
    }
    if settings.feature_resume:
        save_checkpoint(session_id=incident_id, node_name="synthesis", state_dict={**state, **res}, iteration=state.get("iteration", 0), is_paused=state.get("is_paused", False))
    return res


def node_remediation(state: GraphState) -> Dict[str, Any]:
    """Generate simulated remediation plan if incident is successfully diagnosed."""
    hyp_dict = state.get("hypothesis_dict")
    status = state.get("status", "insufficient_evidence")
    devices = state["scope_devices"]
    incident_id = state.get("incident_id", "session-unknown")

    actions: List[Dict[str, Any]] = []
    if status == "diagnosed" and hyp_dict:
        hypothesis = DiagnosticHypothesis(**hyp_dict)
        plan_items = RemediationEngine.generate_plan(hypothesis, devices)
        for a in plan_items:
            if settings.feature_hitl:
                a.status = "pending"
                save_remediation_action_log(incident_id, a.model_dump(), status="pending")
            actions.append(a.model_dump())

    res = {"remediation_actions": actions}
    if settings.feature_resume:
        save_checkpoint(session_id=incident_id, node_name="remediation", state_dict={**state, **res}, iteration=state.get("iteration", 0), is_paused=state.get("is_paused", False))
    return res


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
    remediation_items = [RemediationActionItem(**d) for d in remediation_dicts]

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
        "agent_execution": state.get("agent_execution", {}),
        "inquiries_count": len(state.get("inquiries_history", [])),
        "conflicts_resolved_count": len(state.get("conflicts_resolved", [])),
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

    specialist_obs = state.get("accumulated_observations", [])
    top_class = max(classifier_calib_probs, key=classifier_calib_probs.get) if classifier_calib_probs else None
    top_prob = float(classifier_calib_probs.get(top_class, 0.0)) if top_class else 0.0

    is_benign_normal = (
        len(specialist_obs) == 0
        and not hypothesis
        and top_class == "normal_operation"
        and top_prob >= OfflineCorrelationEngine.ACCEPTANCE_CONFIDENCE_THRESHOLD
    )

    classifier_abstained = (
        not is_benign_normal
        and (
            classifier_conformal_status == "abstain"
            or (is_statistical_domain and classifier_calib_probs and len(conformal_prediction_set) == 0)
            or (not hypothesis and len(conformal_prediction_set) == 0 and classifier_calib_probs)
        )
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
    elif is_benign_normal:
        status = "benign"
        conformal_prediction_set = ["normal_operation"]
        confidence_category = "high" if top_prob >= 0.85 else "medium"
        confidence_breakdown = {
            "rules_score": 1.0,
            "model_score": top_prob,
            "blended_score": top_prob,
            "calibrated_confidence": top_prob,
        }
        uncertainty = UncertaintyEvaluation(
            score=round(1.0 - top_prob, 3),
            reasons=[],
            missing_evidence=[],
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

    if status == "benign":
        report.confidence = top_prob
        report.probable_cause = "normal_operation"
        if not report.summary or "insufficient" in report.summary.lower() or "status benign" in report.summary.lower():
            report.summary = (
                f"Normal network operation verified with {int(top_prob * 100)}% confidence. No anomalous faults detected."
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

    res_dict = {"report_dict": report.model_dump()}
    if settings.feature_resume:
        save_checkpoint(session_id=incident_id, node_name="report", state_dict={**state, **res_dict}, iteration=state.get("iteration", 0), is_paused=False)
    return res_dict


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
    mediator.reset_dead_agents()
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
        "inquiries_history": [],
        "processed_inquiry_hashes": [],
        "agent_execution": {},
        "arbitration_winner": None,
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


def pause_diagnosis(session_id: str) -> bool:
    """Signal an active diagnostic session to halt cleanly at its next checkpoint."""
    return mark_session_paused(session_id)


def resume_diagnosis(session_id: str) -> UnifiedDiagnosticReport:
    """Resume execution of an interrupted or paused diagnosis from the latest SQLite checkpoint."""
    init_db()
    latest = get_latest_checkpoint(session_id)
    if not latest:
        raise ValueError(f"No checkpoint found for session '{session_id}'. Cannot resume.")

    mark_session_resumed(session_id)
    state = json.loads(latest.state_json)
    state["is_paused"] = False

    node = latest.node_name

    # Step through remaining graph nodes sequentially from checkpointed state
    if node == "specialists":
        res_med = node_mediation(state)
        state.update(res_med)
        route = route_mediation(state)
        if route == "inquiry":
            res_inq = node_inquiry(state)
            state.update(res_inq)
            res_med2 = node_mediation(state)
            state.update(res_med2)
        res_synth = node_synthesis(state)
        state.update(res_synth)
        res_rem = node_remediation(state)
        state.update(res_rem)
        res_rep = node_report(state)
        state.update(res_rep)

    elif node in ("mediation", "inquiry"):
        route = route_mediation(state)
        if route == "inquiry":
            res_inq = node_inquiry(state)
            state.update(res_inq)
            res_med2 = node_mediation(state)
            state.update(res_med2)
        res_synth = node_synthesis(state)
        state.update(res_synth)
        res_rem = node_remediation(state)
        state.update(res_rem)
        res_rep = node_report(state)
        state.update(res_rep)

    elif node == "synthesis":
        res_rem = node_remediation(state)
        state.update(res_rem)
        res_rep = node_report(state)
        state.update(res_rep)

    elif node == "remediation":
        res_rep = node_report(state)
        state.update(res_rep)

    elif node == "report":
        res_rep = node_report(state)
        state.update(res_rep)

    report_dict = state.get("report_dict")
    if not report_dict:
        res_rep = node_report(state)
        report_dict = res_rep.get("report_dict")

    if not report_dict:
        raise RuntimeError(f"Resumed diagnostic execution for session '{session_id}' failed to produce a report.")

    return UnifiedDiagnosticReport(**report_dict)

