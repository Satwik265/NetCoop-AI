"""Agent 3: Configuration and Audit Analyzer Agent."""

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


class ConfigAgent(BaseAgent):
    """Audits running configurations, candidate diffs, MTU consistency, and security filters."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.CONFIG_AGENT,
            name="Configuration & Audit Analyzer",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process configurations to find parameter mismatches and recent diffs."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_configs = (envelope.payload.raw_data or {}).get("configurations", [])

        observations: List[Observation] = []
        mtu_by_device_if: Dict[str, int] = {}

        for cfg in raw_configs:
            dev = cfg.get("device", "unknown")
            diff = cfg.get("candidate_diff", "")
            running = cfg.get("running_config", {})
            ts = cfg.get("timestamp_utc")

            # Check for candidate diffs
            if diff:
                observations.append(
                    Observation(
                        category=ObservationCategory.CONFIG_DIFF,
                        entity=dev,
                        metric_name="config_commit_diff",
                        observed_value=diff,
                        unit="text",
                        severity=Severity.WARNING,
                        timestamp_start=ts,
                        context={"diff": diff, "agent_domain": "config_agent"},
                    )
                )

            # Check interface MTUs
            interfaces = running.get("interfaces", {})
            for if_name, if_data in interfaces.items():
                if isinstance(if_data, dict):
                    mtu = if_data.get("mtu")
                    if mtu is not None:
                        mtu_by_device_if[f"{dev}:{if_name}"] = int(mtu)

                    # Spanning tree bpdufilter check
                    st_data = if_data.get("spanning-tree", {})
                    if st_data.get("bpdufilter") == "enable":
                        observations.append(
                            Observation(
                                category=ObservationCategory.CONFIG_DIFF,
                                entity=f"{dev}:{if_name}",
                                metric_name="bpdu_filter",
                                observed_value=True,
                                unit="boolean",
                                severity=Severity.CRITICAL,
                                timestamp_start=ts,
                                context={"agent_domain": "config_agent"},
                            )
                        )

        # Detect MTU mismatches across devices
        if len(mtu_by_device_if) >= 2:
            unique_mtus = set(mtu_by_device_if.values())
            if len(unique_mtus) > 1:
                # Discrepancy detected
                for entity, mtu_val in mtu_by_device_if.items():
                    observations.append(
                        Observation(
                            category=ObservationCategory.CONFIG_DIFF,
                            entity=entity,
                            metric_name="mtu_mismatch",
                            observed_value=mtu_val,
                            unit="bytes",
                            severity=Severity.CRITICAL if mtu_val == min(unique_mtus) else Severity.WARNING,
                            context={"peer_mtus": mtu_by_device_if, "agent_domain": "config_agent"},
                        )
                    )

        response.payload.observations = observations

        obs_ids = [o.observation_id for o in observations]
        has_mtu_mismatch = any(o.metric_name == "mtu_mismatch" for o in observations)
        has_bpdu_filter = any(o.metric_name == "bpdu_filter" for o in observations)

        if has_mtu_mismatch:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Path MTU size disparity between interconnected network endpoints",
                    confidence=0.85,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["telemetry_agent:verify_large_packet_drops"],
                )
            )
        elif has_bpdu_filter:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="BPDU filter configuration enabled on trunk or cross-connect link",
                    confidence=0.90,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["topology_agent:verify_stp_loop_state"],
                )
            )

        return response
