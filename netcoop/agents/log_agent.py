"""Agent 4: Anomaly Correlation and Log Analyzer Agent."""

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


class LogAgent(BaseAgent):
    """Clusters and parses syslog streams, BFD state transitions, and transceiver alarms."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.LOG_AGENT,
            name="Anomaly Correlation & Log Analyzer",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Parse syslog messages for known fault signatures and state transitions."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_logs = (envelope.payload.raw_data or {}).get("logs", [])

        observations: List[Observation] = []

        for log in raw_logs:
            dev = log.get("device", "unknown")
            msg = log.get("message", "")
            severity_num = log.get("severity", 6)
            ts = log.get("timestamp_utc")

            msg_lower = msg.lower()

            if "bfd session down" in msg_lower or "bfd down" in msg_lower:
                observations.append(
                    Observation(
                        category=ObservationCategory.LOG_PATTERN,
                        entity=dev,
                        metric_name="bfd_session_down",
                        observed_value=msg,
                        unit="text",
                        severity=Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "log_agent"},
                    )
                )
            elif "dampening active" in msg_lower or "suppressed penalty" in msg_lower:
                observations.append(
                    Observation(
                        category=ObservationCategory.LOG_PATTERN,
                        entity=dev,
                        metric_name="flap_damping_active",
                        observed_value=msg,
                        unit="text",
                        severity=Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "log_agent"},
                    )
                )
            elif "optics dom alarm" in msg_lower or "rx power" in msg_lower:
                observations.append(
                    Observation(
                        category=ObservationCategory.LOG_PATTERN,
                        entity=dev,
                        metric_name="optical_power_alarm",
                        observed_value=msg,
                        unit="text",
                        severity=Severity.WARNING if severity_num >= 4 else Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "log_agent"},
                    )
                )
            elif "flapping between port" in msg_lower or "mac flapping" in msg_lower:
                observations.append(
                    Observation(
                        category=ObservationCategory.LOG_PATTERN,
                        entity=dev,
                        metric_name="mac_flapping_log",
                        observed_value=msg,
                        unit="text",
                        severity=Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "log_agent"},
                    )
                )

        response.payload.observations = observations

        obs_ids = [o.observation_id for o in observations]
        has_dampening = any(o.metric_name == "flap_damping_active" for o in observations)
        has_optics_alarm = any(o.metric_name == "optical_power_alarm" for o in observations)

        if has_dampening:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="BGP route flap damping triggered by physical carrier flapping",
                    confidence=0.82,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["topology_agent:verify_bgp_session_state"],
                )
            )
        elif has_optics_alarm:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Physical transceiver optical signal degradation",
                    confidence=0.80,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["telemetry_agent:verify_crc_and_fcs_errors"],
                )
            )

        return response
