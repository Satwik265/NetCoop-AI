"""Agent 2: Topology and Routing Analyzer Agent (ConnectivityAgent)."""

from typing import Any, Dict, List, Optional
from netcoop.agents.base import BaseAgent
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    Hypothesis,
    Inquiry,
    MessageType,
    Observation,
    ObservationCategory,
    Severity,
)
from netcoop.core.signatures import HypothesisKey, SIGNATURE_REGISTRY


class TopologyAgent(BaseAgent):
    """Analyzes network graph structure, BGP neighbor states, and Spanning Tree."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.TOPOLOGY_AGENT,
            name="Topology & Connectivity Analyzer",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process topology, routing state, or inquiries."""
        if envelope.header.message_type == MessageType.INQUIRY_REQUEST:
            return self._handle_inquiry(envelope)

        return self._handle_dispatch(envelope)

    def _handle_inquiry(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Answer targeted topology inquiries from peer agents."""
        response = self.create_response_envelope(envelope, MessageType.INQUIRY_RESPONSE)
        raw_data = envelope.payload.raw_data or {}
        topology = raw_data.get("topology") or {}
        nodes = topology.get("nodes", [])
        edges = topology.get("edges", [])

        inquiries = envelope.payload.inquiries
        for inq in inquiries:
            q = inq.question.lower()
            if not nodes and not edges:
                inq.answer = "Topology unavailable: no network graph nodes or adjacencies provided."
            elif "upstream" in q or "path" in q:
                target = inq.target_entity
                # Find connected edges
                adjacent = [e for e in edges if e.get("source") == target or e.get("target") == target]
                if adjacent:
                    inq.answer = f"Adjacent hops for {target}: {[e.get('target') if e.get('source') == target else e.get('source') for e in adjacent]}"
                else:
                    inq.answer = f"No direct upstream adjacencies identified for {target}."
            else:
                inq.answer = f"Topology contains {len(nodes)} devices and {len(edges)} transit links."

        response.payload.inquiries = inquiries
        return response

    def _handle_dispatch(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process topology, BGP neighbor states, and emit cross-inquiries when indicated."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_data = envelope.payload.raw_data or {}
        topology = raw_data.get("topology")
        raw_routing = raw_data.get("routing_state", {})
        raw_telemetry = raw_data.get("telemetry", [])

        bgp_sessions = raw_routing.get("bgp_sessions", [])
        stp_states = raw_routing.get("stp_state", [])

        observations: List[Observation] = []
        limitations: List[str] = []

        # 1. Topology availability verification
        if not topology or not topology.get("nodes"):
            limitations.append("topology unavailable: no nodes or link adjacencies provided")
            response.context["topology_status"] = "topology unavailable"
        else:
            response.context["topology_status"] = "available"
            if topology.get("is_assumed", False):
                response.payload.provenance = {"topology": "assumed"}

        # 2. Analyze BGP Sessions
        for session in bgp_sessions:
            dev = session.get("device", "unknown")
            peer = session.get("peer_ip", "")
            state = session.get("state", "Unknown")
            flaps = session.get("flaps_count", 0)

            if state != "Established" or flaps > 0:
                observations.append(
                    Observation(
                        category=ObservationCategory.STATE_TRANSITION,
                        entity=f"{dev}:bgp_peer_{peer}",
                        metric_name="bgp_state_flaps",
                        observed_value=flaps,
                        unit="count",
                        severity=Severity.CRITICAL if flaps >= 3 else Severity.WARNING,
                        context={"peer_ip": peer, "state": state, "agent_domain": "topology_agent"},
                    )
                )

        # 3. Analyze STP
        for stp in stp_states:
            dev = stp.get("device", "unknown")
            bpdu_filtered = stp.get("bpdu_filter_enabled", False)
            blocked_ports = stp.get("blocked_ports", [])

            if bpdu_filtered:
                observations.append(
                    Observation(
                        category=ObservationCategory.TOPOLOGY_CHANGE,
                        entity=dev,
                        metric_name="bpdu_filter",
                        observed_value=True,
                        unit="boolean",
                        severity=Severity.CRITICAL,
                        context={"blocked_ports": blocked_ports, "agent_domain": "topology_agent"},
                    )
                )

        # 4. Cross-agent inquiry generation:
        # If telemetry shows elevated latency on access devices without local congestion,
        # query TelemetryAgent for upstream core link utilization.
        has_latency_without_local_congestion = False
        edge_devices_with_delay = []
        for rec in raw_telemetry:
            dev = rec.get("device_id") or rec.get("device") or ""
            metrics = rec.get("metrics", rec)
            lat = float(metrics.get("latency_ms") or 0.0)
            drops = int(metrics.get("queue_drops") or 0)
            util = float(metrics.get("link_utilization_pct") or 0.0)

            if lat > 50.0 and drops == 0 and util < 70.0:
                has_latency_without_local_congestion = True
                edge_devices_with_delay.append(dev)

        inquiries: List[Inquiry] = []
        if has_latency_without_local_congestion:
            inquiries.append(
                Inquiry(
                    target_agent=AgentRole.TELEMETRY_AGENT,
                    question="Audit upstream core link utilization and queue drops for transit hops along path to delayed devices.",
                    target_entity="upstream_transit_path",
                    parameters={"devices": edge_devices_with_delay},
                )
            )

        response.payload.observations = observations
        response.payload.inquiries = inquiries
        response.context["limitations"] = limitations

        obs_ids = [o.observation_id for o in observations]
        has_bgp_flaps = any(o.metric_name == "bgp_state_flaps" for o in observations)
        has_bpdu_filter = any(o.metric_name == "bpdu_filter" for o in observations)

        if has_bgp_flaps:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="BGP route instability causing session flapping or route suppression",
                    confidence=0.75,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["log_agent:check_bfd_and_link_down_events"],
                )
            )
        elif has_bpdu_filter:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Spanning Tree loop due to BPDU filtering or missing port blocking",
                    confidence=0.80,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["telemetry_agent:check_broadcast_and_cpu_surge"],
                )
            )

        return response


# Export alias conforming to contract
ConnectivityAgent = TopologyAgent
