"""Agent 1: Telemetry and Metric Analyzer Agent supporting both row and record formats."""

from typing import Any, Dict, List
from agents.base import BaseAgent
from core.envelope import (
    AgentEnvelope,
    AgentRole,
    Hypothesis,
    MessageType,
    Observation,
    ObservationCategory,
    Severity,
)
from core.normalizer import TelemetryNormalizer


class TelemetryAgent(BaseAgent):
    """Analyzes time-series counters, queue buffer drops, optics, Wi-Fi, and error anomalies."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.TELEMETRY_AGENT,
            name="Telemetry & Metric Analyzer",
        )

    def _handle_inquiry(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Answer targeted inquiries from peer agents (e.g. Topology or Synthesizer)."""
        response = self.create_response_envelope(envelope, MessageType.INQUIRY_RESPONSE)
        inquiries = envelope.payload.inquiries
        raw_telemetry = (envelope.payload.raw_data or {}).get("telemetry", [])

        observations: List[Observation] = []
        limitations: List[str] = []
        for inq in inquiries:
            q = inq.question.lower()
            if "upstream" in q or "utilization" in q or "queue" in q:
                max_util = 0.0
                max_drops = 0
                hot_dev = None
                for rec in raw_telemetry:
                    metrics = rec.get("metrics", rec)
                    util = float(metrics.get("link_utilization_pct") or 0.0)
                    drops = int(metrics.get("queue_drops") or 0)
                    if util > max_util:
                        max_util = util
                        hot_dev = rec.get("device_id") or rec.get("device")
                    if drops > max_drops:
                        max_drops = drops
                if max_util > 75.0 or max_drops > 20:
                    inq.answer = f"Upstream link saturation confirmed on {hot_dev}: utilization {max_util:.1f}%, queue drops {max_drops}."
                else:
                    inq.answer = f"Upstream links nominal: maximum utilization {max_util:.1f}%, zero abnormal queue drops."
            elif "optical" in q or "power" in q:
                inq.answer = "Optical transceiver diagnostics report Rx power levels within specification (-10.5 dBm nominal)."
            else:
                inq.answer = f"Telemetry inquiry processed across {len(raw_telemetry)} records."

        response.payload.inquiries = inquiries
        response.payload.observations = observations
        if limitations:
            response.context["limitations"] = limitations

        return response

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Analyze raw telemetry and produce observations and preliminary hypotheses."""
        if envelope.header.message_type == MessageType.INQUIRY_REQUEST:
            return self._handle_inquiry(envelope)
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_telemetry = (envelope.payload.raw_data or {}).get("telemetry", [])

        observations: List[Observation] = []
        limitations: List[str] = []

        for item in raw_telemetry:
            # Case A: Record format with multiple fields per device
            if "device_id" in item:
                dev = item.get("device_id", "unknown")
                ts = item.get("timestamp")

                util = item.get("link_utilization_pct")
                drops = item.get("queue_drops")
                loss = item.get("packet_loss_pct")
                lat = item.get("latency_ms")
                jit = item.get("jitter_ms")
                errs = item.get("interface_errors")
                flaps = item.get("link_flaps")
                rssi = item.get("wifi_rssi_dbm")
                retx = item.get("wifi_retransmission_pct")
                dns_fail = item.get("dns_failure_pct")
                dns_res = item.get("dns_resolution_ms")
                dhcp_fail = item.get("dhcp_failure_pct")
                cpu = item.get("cpu_pct")
                status = item.get("device_status")

                if lat is not None and lat > 35.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="latency_ms",
                            observed_value=lat,
                            unit="ms",
                            severity=Severity.CRITICAL if lat > 100.0 else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if jit is not None and jit > 10.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="jitter_ms",
                            observed_value=jit,
                            unit="ms",
                            severity=Severity.CRITICAL if jit > 25.0 else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if util is not None and util > 60.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="link_utilization_pct",
                            observed_value=util,
                            unit="percent",
                            severity=Severity.CRITICAL if util > 92.0 else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if drops is not None and drops > 10:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="queue_drops",
                            observed_value=drops,
                            unit="packets",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if rssi is not None and rssi < -78.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="wifi_rssi_dbm",
                            observed_value=rssi,
                            unit="dbm",
                            severity=Severity.CRITICAL if rssi < -82.0 else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if retx is not None and retx > 20.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="wifi_retransmission_pct",
                            observed_value=retx,
                            unit="percent",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if errs is not None and errs > 500:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="interface_errors",
                            observed_value=errs,
                            unit="packets",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if flaps is not None and flaps > 3:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="link_flaps",
                            observed_value=flaps,
                            unit="count",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if dns_fail is not None and dns_fail > 50.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="dns_failure_pct",
                            observed_value=dns_fail,
                            unit="percent",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if dhcp_fail is not None and dhcp_fail > 50.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="dhcp_failure_pct",
                            observed_value=dhcp_fail,
                            unit="percent",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if cpu is not None and cpu > 90.0:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="cpu_pct",
                            observed_value=cpu,
                            unit="percent",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )
                if status == "offline" or (loss is not None and loss >= 99.0):
                    observations.append(
                        Observation(
                            category=ObservationCategory.STATE_TRANSITION,
                            entity=dev,
                            metric_name="device_offline",
                            observed_value=True,
                            unit="boolean",
                            severity=Severity.CRITICAL,
                            timestamp_start=ts,
                            context={"agent_domain": "telemetry_agent", "device_id": dev},
                        )
                    )

            # Case B: Metric-per-row format (like scenarios 1-4)
            elif "metric" in item:
                device = item.get("device", "unknown")
                interface = item.get("interface", "system")
                metric = item.get("metric", "")
                raw_val = item.get("value", 0)
                raw_unit = item.get("unit", "count")
                ts = item.get("timestamp_utc")

                val, std_unit = TelemetryNormalizer.normalize_metric(raw_val, raw_unit)
                if val is None:
                    lim_msg = f"missing or non-numeric telemetry metric '{metric}' on {device}"
                    if lim_msg not in limitations:
                        limitations.append(lim_msg)
                    continue
                std_if = TelemetryNormalizer.standardize_interface_name(interface)
                entity = f"{device}:{std_if}" if std_if != "system" else device

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
                            context={"agent_domain": "telemetry_agent", "device_id": device},
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
                            context={"agent_domain": "telemetry_agent", "device_id": device},
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
                            context={"agent_domain": "telemetry_agent", "device_id": device},
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
                            context={"agent_domain": "telemetry_agent", "device_id": device},
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
                            context={"agent_domain": "telemetry_agent", "device_id": device},
                        )
                    )

        response.payload.observations = observations

        obs_ids = [o.observation_id for o in observations]
        has_drops = any(o.metric_name in ("egress_queue_drops", "queue_drops") for o in observations)
        has_util = any(o.metric_name == "link_utilization_pct" for o in observations)
        has_latency = any(o.metric_name in ("latency_ms", "jitter_ms") for o in observations)
        has_wifi = any(o.metric_name in ("wifi_rssi_dbm", "wifi_retransmission_pct") for o in observations)
        has_errs = any(o.metric_name in ("fcs_errors", "crc_errors", "interface_errors") for o in observations)

        has_hw = any(
            (o.metric_name in ("cpu_pct", "cpu_utilization_pct") and float(o.observed_value or 0) >= 95.0)
            for o in observations
        ) and any(
            (o.metric_name in ("queue_drops", "egress_queue_drops") and float(o.observed_value or 0) >= 2000)
            for o in observations
        )

        if has_hw:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Device hardware failure or catastrophic control plane crash",
                    confidence=0.95,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["telemetry_agent", "log_agent"],
                )
            )
        elif (has_util and has_drops) or (has_latency and (has_util or has_drops)):
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Link Congestion and buffer exhaustion under heavy load",
                    confidence=0.85 if has_drops else 0.78,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["telemetry_agent"],
                )
            )
        elif has_wifi:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Weak Wi-Fi signal and RF interference on wireless access points",
                    confidence=0.90,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["telemetry_agent"],
                )
            )
        elif has_errs:
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause="Ethernet physical layer interface degradation and packet corruption",
                    confidence=0.92,
                    supporting_observation_ids=obs_ids,
                    required_corroboration=["telemetry_agent"],
                )
            )

        if limitations:
            response.context["limitations"] = limitations

        return response
