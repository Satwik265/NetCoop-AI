"""Agent 2: Topology and Routing Analyzer Agent."""

from typing import Any, Dict, List
from netcoop.agents.base import BaseAgent
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    Hypothesis,
    MessageType,
    Observation,
    ObservationCategory,
    Severity,
)


class TopologyAgent(BaseAgent):
    """Analyzes network graph structure, BGP neighbor states, and Spanning Tree."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.TOPOLOGY_AGENT,
            name="Topology & Routing Analyzer",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process topology and routing state to identify adjacencies and forwarding loops."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_routing = (envelope.payload.raw_data or {}).get("routing_state", {})
        bgp_sessions = raw_routing.get("bgp_sessions", [])
        stp_states = raw_routing.get("stp_state", [])

        observations: List[Observation] = []

        # Analyze BGP
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

        # Analyze STP
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

        response.payload.observations = observations

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

