"""Agent 6: Wi-Fi and Infrastructure Services Specialist Agent."""

from typing import Any, Dict, List, Optional
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
from netcoop.core.signatures import HypothesisKey, SIGNATURE_REGISTRY
from netcoop.core.thresholds import DynamicThresholds, is_snapshot_mode


class WifiServicesAgent(BaseAgent):
    """Monitors Wi-Fi 802.11 RF physical parameters, client density, and DNS/DHCP services."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.WIFI_SERVICES_AGENT,
            name="Wi-Fi & Services Specialist",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process incoming dispatch or inquiry envelope."""
        msg_type = envelope.header.message_type

        if msg_type == MessageType.INQUIRY_REQUEST:
            return self._handle_inquiry(envelope)

        return self._handle_telemetry_dispatch(envelope)

    def _handle_inquiry(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Answer targeted inquiry from peer agents (e.g. Topology or Synthesizer)."""
        response = self.create_response_envelope(envelope, MessageType.INQUIRY_RESPONSE)
        inquiries = envelope.payload.inquiries
        raw_telemetry = (envelope.payload.raw_data or {}).get("telemetry", [])

        observations: List[Observation] = []
        for inq in inquiries:
            q = inq.question.lower()
            ans = "No anomalous Wi-Fi or infrastructure service metrics detected."
            
            # Check if inquiry is regarding Wi-Fi or services
            if "wifi" in q or "rf" in q or "signal" in q or "rssi" in q:
                weak_aps = []
                for rec in raw_telemetry:
                    dev = rec.get("device_id") or rec.get("device") or "unknown"
                    metrics = rec.get("metrics", rec)
                    rssi = metrics.get("wifi_rssi_dbm")
                    if rssi is not None and float(rssi) < DynamicThresholds.WIFI_RSSI_WARN_DBM:
                        weak_aps.append(f"{dev} (RSSI: {rssi} dBm)")
                if weak_aps:
                    ans = f"Wi-Fi RF degradation identified on: {', '.join(weak_aps)}."
                else:
                    ans = "Wi-Fi RF parameters within nominal coverage bounds."

            elif "dns" in q:
                dns_errs = []
                for rec in raw_telemetry:
                    dev = rec.get("device_id") or rec.get("device") or "unknown"
                    metrics = rec.get("metrics", rec)
                    fail = metrics.get("dns_failure_pct")
                    if fail is not None and float(fail) > DynamicThresholds.DNS_FAILURE_WARN_PCT:
                        dns_errs.append(f"{dev} ({fail}% failures)")
                if dns_errs:
                    ans = f"DNS query timeouts elevated on: {', '.join(dns_errs)}."
                else:
                    ans = "DNS resolution services operational."

            inq.answer = ans

        response.payload.inquiries = inquiries
        response.payload.observations = observations
        return response

    def _handle_telemetry_dispatch(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Analyze raw telemetry for Wi-Fi and core service degradation."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_telemetry = (envelope.payload.raw_data or {}).get("telemetry", [])

        observations: List[Observation] = []
        limitations: List[str] = []

        is_snapshot = is_snapshot_mode(raw_telemetry)
        if is_snapshot:
            limitations.append("single snapshot, no temporal context")

        # Track metric availability
        has_wifi_data = False
        has_service_data = False

        for rec in raw_telemetry:
            dev = rec.get("device_id") or rec.get("device") or "unknown"
            ts = rec.get("timestamp")
            metrics = rec.get("metrics", rec)

            rssi = metrics.get("wifi_rssi_dbm")
            snr = metrics.get("wifi_snr_db")
            retx = metrics.get("wifi_retransmission_pct")
            clients = metrics.get("client_density") or metrics.get("active_clients")
            dns_res = metrics.get("dns_resolution_ms")
            dns_fail = metrics.get("dns_failure_pct")
            dhcp_fail = metrics.get("dhcp_failure_pct")

            if rssi is not None or retx is not None or snr is not None:
                has_wifi_data = True
            if dns_res is not None or dns_fail is not None or dhcp_fail is not None:
                has_service_data = True

            # 1. Wi-Fi RSSI
            if rssi is not None:
                r_val = float(rssi)
                if r_val <= DynamicThresholds.WIFI_RSSI_WARN_DBM:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="wifi_rssi_dbm",
                            observed_value=r_val,
                            unit="dbm",
                            severity=Severity.CRITICAL if r_val <= DynamicThresholds.WIFI_RSSI_CRIT_DBM else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "wifi_services_agent", "device_id": dev},
                        )
                    )

            # 2. Wi-Fi Retransmission
            if retx is not None:
                rx_val = float(retx)
                if rx_val >= DynamicThresholds.WIFI_RETX_WARN_PCT:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="wifi_retransmission_pct",
                            observed_value=rx_val,
                            unit="percent",
                            severity=Severity.CRITICAL if rx_val >= DynamicThresholds.WIFI_RETX_CRIT_PCT else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "wifi_services_agent", "device_id": dev},
                        )
                    )

            # 3. Wi-Fi Client Density
            if clients is not None:
                c_val = int(clients)
                if c_val >= DynamicThresholds.WIFI_CLIENT_DENSITY_WARN:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="client_density",
                            observed_value=c_val,
                            unit="count",
                            severity=Severity.CRITICAL if c_val >= DynamicThresholds.WIFI_CLIENT_DENSITY_CRIT else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "wifi_services_agent", "device_id": dev},
                        )
                    )

            # 4. DNS Resolution Latency
            if dns_res is not None:
                d_lat = float(dns_res)
                if d_lat >= DynamicThresholds.DNS_RESOLUTION_WARN_MS:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="dns_resolution_ms",
                            observed_value=d_lat,
                            unit="ms",
                            severity=Severity.CRITICAL if d_lat >= DynamicThresholds.DNS_RESOLUTION_CRIT_MS else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "wifi_services_agent", "device_id": dev},
                        )
                    )

            # 5. DNS Failure Rate
            if dns_fail is not None:
                d_fail = float(dns_fail)
                if d_fail >= DynamicThresholds.DNS_FAILURE_WARN_PCT:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="dns_failure_pct",
                            observed_value=d_fail,
                            unit="percent",
                            severity=Severity.CRITICAL if d_fail >= DynamicThresholds.DNS_FAILURE_CRIT_PCT else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "wifi_services_agent", "device_id": dev},
                        )
                    )

            # 6. DHCP Failure Rate
            if dhcp_fail is not None:
                dh_fail = float(dhcp_fail)
                if dh_fail >= DynamicThresholds.DHCP_FAILURE_WARN_PCT:
                    observations.append(
                        Observation(
                            category=ObservationCategory.METRIC_ANOMALY,
                            entity=dev,
                            metric_name="dhcp_failure_pct",
                            observed_value=dh_fail,
                            unit="percent",
                            severity=Severity.CRITICAL if dh_fail >= DynamicThresholds.DHCP_FAILURE_CRIT_PCT else Severity.WARNING,
                            timestamp_start=ts,
                            context={"agent_domain": "wifi_services_agent", "device_id": dev},
                        )
                    )

        if not has_wifi_data:
            limitations.append("wifi metrics missing (rssi, snr, retransmissions)")
        if not has_service_data:
            limitations.append("service metrics missing (dns, dhcp)")

        response.payload.observations = observations
        response.context["limitations"] = limitations

        # Propose preliminary hypotheses
        obs_ids = [o.observation_id for o in observations]
        has_weak_wifi = any(o.metric_name in ("wifi_rssi_dbm", "wifi_retransmission_pct") for o in observations)
        has_dns = any(o.metric_name in ("dns_resolution_ms", "dns_failure_pct") for o in observations)
        has_dhcp = any(o.metric_name == "dhcp_failure_pct" for o in observations)

        conf_discount = 0.12 if is_snapshot else 0.0

        if has_dns:
            sig = SIGNATURE_REGISTRY[HypothesisKey.DNS_FAILURE]
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause=sig.title,
                    confidence=round(0.92 - conf_discount, 2),
                    supporting_observation_ids=obs_ids,
                    required_corroboration=sig.required_corroboration,
                )
            )
        elif has_dhcp:
            sig = SIGNATURE_REGISTRY[HypothesisKey.DHCP_FAILURE]
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause=sig.title,
                    confidence=round(0.90 - conf_discount, 2),
                    supporting_observation_ids=obs_ids,
                    required_corroboration=sig.required_corroboration,
                )
            )
        elif has_weak_wifi:
            sig = SIGNATURE_REGISTRY[HypothesisKey.WEAK_WIFI_SIGNAL]
            response.payload.hypotheses.append(
                Hypothesis(
                    probable_cause=sig.title,
                    confidence=round(0.88 - conf_discount, 2),
                    supporting_observation_ids=obs_ids,
                    required_corroboration=sig.required_corroboration,
                )
            )

        return response
