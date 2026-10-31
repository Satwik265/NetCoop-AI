"""Specialist rule-based and statistical classifier agent module."""

from typing import Any, Dict, List, Optional
from netcoop.models import DiagnosticPrediction


class ScenarioClassifier:
    """Heuristic rule classifier correlating telemetry anomalies to fault categories."""

    @classmethod
    def classify_telemetry(cls, telemetry: List[Dict[str, Any]]) -> Optional[DiagnosticPrediction]:
        """Infer fault class from normalized telemetry."""
        for rec in telemetry:
            dev = rec.get("device_id", "unknown")
            loss = rec.get("packet_loss_pct") or 0.0
            util = rec.get("link_utilization_pct") or 0.0
            drops = rec.get("queue_drops") or 0
            errs = rec.get("interface_errors") or 0
            flaps = rec.get("link_flaps") or 0
            rssi = rec.get("wifi_rssi_dbm")
            retx = rec.get("wifi_retransmission_pct")
            cpu = rec.get("cpu_pct") or 0.0
            dns_fail = rec.get("dns_failure_pct") or 0.0
            dhcp_fail = rec.get("dhcp_failure_pct") or 0.0

            if dns_fail > 75.0:
                return DiagnosticPrediction(
                    probable_cause="DNS resolution service outage with high query timeout failure rate",
                    confidence=0.95,
                    category="service",
                    affected_devices=[dev],
                    supporting_signals=[f"dns_failure_pct: {dns_fail}%"],
                )
            if dhcp_fail > 70.0:
                return DiagnosticPrediction(
                    probable_cause="DHCP scope exhaustion or relay failure preventing lease assignment",
                    confidence=0.92,
                    category="service",
                    affected_devices=[dev],
                    supporting_signals=[f"dhcp_failure_pct: {dhcp_fail}%"],
                )
            if errs > 1500 and flaps > 3:
                return DiagnosticPrediction(
                    probable_cause="Physical layer Ethernet interface CRC errors and flapping transitions",
                    confidence=0.94,
                    category="hardware",
                    affected_devices=[dev],
                    supporting_signals=[f"interface_errors: {errs}", f"link_flaps: {flaps}"],
                )
            if rssi is not None and rssi < -80.0 and retx is not None and retx > 25.0:
                return DiagnosticPrediction(
                    probable_cause="Hostel access point RF attenuation causing high retransmissions and packet loss",
                    confidence=0.90,
                    category="wireless",
                    affected_devices=[dev],
                    supporting_signals=[f"wifi_rssi_dbm: {rssi}", f"wifi_retx: {retx}%"],
                )
            if cpu > 95.0:
                return DiagnosticPrediction(
                    probable_cause="Control-plane CPU exhaustion on core router driving queue drops",
                    confidence=0.94,
                    category="resource",
                    affected_devices=[dev],
                    supporting_signals=[f"cpu_pct: {cpu}%"],
                )
            if util > 90.0 and drops > 300:
                return DiagnosticPrediction(
                    probable_cause="Link utilization saturation causing buffer queue drops and latency spikes",
                    confidence=0.92,
                    category="capacity",
                    affected_devices=[dev],
                    supporting_signals=[f"link_utilization_pct: {util}%", f"queue_drops: {drops}"],
                )
        return None
