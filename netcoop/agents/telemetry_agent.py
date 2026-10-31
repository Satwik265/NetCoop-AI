"""Agent 1: Telemetry and Metric Analyzer Agent."""

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
from netcoop.core.normalizer import TelemetryNormalizer


class TelemetryAgent(BaseAgent):
    """Analyzes time-series counters, queue buffer drops, optics, and CRC anomalies."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.TELEMETRY_AGENT,
            name="Telemetry & Metric Analyzer",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Analyze raw telemetry and produce observations and preliminary hypotheses."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_telemetry = (envelope.payload.raw_data or {}).get("telemetry", [])

        observations: List[Observation] = []
        for item in raw_telemetry:
            device = item.get("device", "unknown")
            interface = item.get("interface", "system")
            metric = item.get("metric", "")
            raw_val = item.get("value", 0)
            raw_unit = item.get("unit", "count")
            ts = item.get("timestamp_utc")

            val, std_unit = TelemetryNormalizer.normalize_metric(raw_val, raw_unit)
            std_if = TelemetryNormalizer.standardize_interface_name(interface)
            entity = f"{device}:{std_if}" if std_if != "system" else device

            # Anomaly rules
            if metric in ("egress_queue_drops", "large_packet_drops") and val > 0:
                observations.append(
                    Observation(
                        category=ObservationCategory.METRIC_ANOMALY,
                        entity=entity,
                        metric_name=metric,
                        observed_value=val,
                        unit=std_unit,
                        severity=Severity.CRITICAL if val > 1000 else Severity.WARNING,
                        timestamp_start=ts,
                        context={"agent_domain": "telemetry_agent"},
                    )
                )
            elif metric in ("ingress_packet_loss_pct", "packet_loss_pct") and val > 1.0:
                observations.append(
                    Observation(
                        category=ObservationCategory.METRIC_ANOMALY,
                        entity=entity,
                        metric_name=metric,
                        observed_value=val,
                        unit=std_unit,
                        severity=Severity.CRITICAL if val > 10.0 else Severity.WARNING,
                        timestamp_start=ts,
                        context={"agent_domain": "telemetry_agent"},
                    )
                )
            elif metric in ("fcs_errors", "crc_errors") and val > 0:
                observations.append(
                    Observation(
                        category=ObservationCategory.METRIC_ANOMALY,
                        entity=entity,
                        metric_name=metric,
                        observed_value=val,
                        unit=std_unit,
                        severity=Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "telemetry_agent"},
                    )
                )
            elif metric in ("rx_power_dbm", "optical_rx_power") and val < -15.0:
                observations.append(
                    Observation(
                        category=ObservationCategory.METRIC_ANOMALY,
                        entity=entity,
                        metric_name="rx_power_dbm",
                        observed_value=val,
                        baseline_value=-10.0,
                        unit=std_unit,
                        severity=Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "telemetry_agent"},
                    )
                )
            elif metric == "cpu_utilization_pct" and val > 80.0:
                observations.append(
                    Observation(
                        category=ObservationCategory.METRIC_ANOMALY,
                        entity=entity,
                        metric_name="cpu_utilization_pct",
                        observed_value=val,
                        unit=std_unit,
                        severity=Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "telemetry_agent"},
                    )
                )
            elif metric in ("broadcast_pps", "mac_flaps") and val > 50:
                observations.append(
                    Observation(
                        category=ObservationCategory.METRIC_ANOMALY,
                        entity=entity,
                        metric_name=metric,
                        observed_value=val,
                        unit=std_unit,
                        severity=Severity.CRITICAL,
                        timestamp_start=ts,
                        context={"agent_domain": "telemetry_agent"},
                    )
                )

        response.payload.observations = observations

        # Formulate initial telemetry hypothesis if clear pattern
        obs_ids = [o.observation_id for o in observations]
        has_drops = any(o.metric_name in ("egress_queue_drops", "large_packet_drops") for o in observations)
        has_crc = any(o.metric_name in ("fcs_errors", "crc_errors") for o in observations)
        has_optics = any(o.metric_name == "rx_power_dbm" for o in observations)

        if has_crc and has_optics:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Physical transceiver or optical cabling attenuation causing frame check sequence errors",
                    confidence=0.88,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["config_agent:verify_no_recent_mtu_or_speed_change"],
                )
            )
        elif has_drops:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Packet discard during egress serialization (potential MTU mismatch or buffer starvation)",
                    confidence=0.65,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["config_agent:check_interface_mtu"],
                )
            )

        return response
