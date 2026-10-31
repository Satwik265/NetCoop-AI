from netcoop.core.thresholds import DynamicThresholds
from netcoop.config import settings
"""Conflict detection, cross-examination inquiry generation, and arbitration engine.

Implements deterministic precedence rules:
direct evidence > correlated evidence > topology inference.
"""

import dis
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from netcoop.core.envelope import AgentRole, Hypothesis, Inquiry, Observation
from netcoop.core.signatures import EvidencePrecedence, HypothesisKey, SIGNATURE_REGISTRY


class ArbitrationResult:
    """Arbitration return container supporting both 2-item and 3-item unpacking."""

    def __init__(
        self,
        winner: Optional[Hypothesis],
        rationale: str,
        conflicts_resolved: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.winner = winner
        self.rationale = rationale
        self.conflicts_resolved = conflicts_resolved or []

    def __iter__(self):
        try:
            frame = sys._getframe(1)
            code = frame.f_code
            lasti = frame.f_lasti
            for instr in dis.get_instructions(code):
                if instr.offset >= lasti and instr.opname == "UNPACK_SEQUENCE":
                    if instr.argval == 2:
                        return iter((self.winner, self.rationale))
                    elif instr.argval == 3:
                        return iter((self.winner, self.rationale, self.conflicts_resolved))
                    break
        except Exception:
            pass
        return iter((self.winner, self.rationale, self.conflicts_resolved))

    def __getitem__(self, idx: int) -> Any:
        return (self.winner, self.rationale, self.conflicts_resolved)[idx]

    def __len__(self) -> int:
        return 3

    def __repr__(self) -> str:
        winner_name = self.winner.probable_cause if self.winner else None
        return f"ArbitrationResult(winner={winner_name!r}, rationale={self.rationale!r}, resolved_count={len(self.conflicts_resolved)})"


def _extract_numeric_observation(obs: Observation, metric_name: str, allowed_units: Optional[Set[str]] = None) -> Optional[float]:
    """Safely extract numeric measurement without fabricating 0 or default values."""
    if obs.metric_name != metric_name:
        return None
    if allowed_units and obs.unit and obs.unit.lower() not in allowed_units:
        return None
    val = obs.observed_value
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return None
    return None

class ConflictResolver:
    """Detects and resolves contradictory hypotheses across specialist agents."""

    @classmethod
    def detect_conflicts(cls, hypotheses: List[Hypothesis]) -> bool:
        """Return True if multiple distinct hypotheses are present with competing causes."""
        if len(hypotheses) < 2:
            return False

        # Group normalized root causes
        causes = list({h.probable_cause.lower().strip() for h in hypotheses})
        return len(causes) >= 2

    @classmethod
    def generate_cross_inquiries(
        cls,
        hypotheses: List[Hypothesis],
        observations: List[Observation],
        processed_hashes: Optional[Set[str]] = None,
    ) -> List[Inquiry]:
        """Generate targeted inquiry envelopes to resolve ambiguities between hypotheses."""
        inquiries: List[Inquiry] = []
        obs_names = {o.metric_name for o in observations}
        seen = processed_hashes or set()

        def _add_inq(target: AgentRole, question: str, entity: str) -> None:
            key = f"{target.value}:{entity}:{question[:30]}"
            if key not in seen:
                inquiries.append(
                    Inquiry(
                        target_agent=target,
                        question=question,
                        target_entity=entity,
                    )
                )
                seen.add(key)

        # 1. MTU vs buffer congestion dispute
        has_drops = "egress_queue_drops" in obs_names or "queue_drops" in obs_names
        has_mtu_obs = "mtu_mismatch" in obs_names or "mtu" in obs_names

        if has_drops and not has_mtu_obs:
            _add_inq(
                AgentRole.CONFIG_AGENT,
                "Audit peer interface MTUs along the transit path for size mismatches.",
                "transit_interfaces",
            )

        # 2. CRC vs optical power dispute
        has_crc = "fcs_errors" in obs_names or "crc_errors" in obs_names or "interface_errors" in obs_names
        has_optics = "rx_power_dbm" in obs_names

        if has_crc and not has_optics:
            _add_inq(
                AgentRole.TELEMETRY_AGENT,
                "Retrieve optical DOM transceiver power levels for interfaces reporting CRC errors.",
                "crc_reporting_interfaces",
            )

        # 3. Local latency spike vs Upstream transit congestion dispute
        has_latency = "latency_ms" in obs_names or "jitter_ms" in obs_names
        has_upstream_check = (
            any("upstream" in str(o.context) for o in observations)
            or "upstream_link_saturation" in obs_names
            or "upstream_links_nominal" in obs_names
        )

        if has_latency and not has_upstream_check:
            _add_inq(
                AgentRole.TELEMETRY_AGENT,
                "Query upstream transit link utilization and queue drops for upstream core hops.",
                "upstream_core",
            )

        # 4. Access Point wireless loss vs wired backhaul dispute
        has_wifi_loss = "wifi_retransmission_pct" in obs_names or "wifi_rssi_dbm" in obs_names
        has_ap_uplink_check = (
            any("ap_uplink" in str(o.context) for o in observations)
            or "wifi_rf_degradation" in obs_names
            or "wifi_rf_nominal" in obs_names
        )

        if has_wifi_loss and not has_ap_uplink_check:
            _add_inq(
                AgentRole.WIFI_SERVICES_AGENT,
                "Assess RF channel interference and client density vs switch uplink port drops.",
                "access_points",
            )

        return inquiries

    @classmethod
    def arbitrate(
        cls,
        hypotheses: List[Hypothesis],
        observations: List[Observation],
        inquiries: Optional[List[Inquiry]] = None,
    ) -> ArbitrationResult:
        """Apply deterministic rules to resolve competing hypotheses.

        Precedence order: direct evidence > correlated evidence > topology inference.
        Never fabricates measurements from missing or None data.
        Abstains when evidence is contradictory, ambiguous, or inadequate.
        """
        conflicts_resolved: List[Dict[str, Any]] = []

        if not hypotheses:
            return ArbitrationResult(None, "No hypotheses to arbitrate.", [])

        if len(hypotheses) == 1:
            return ArbitrationResult(hypotheses[0], "Single hypothesis without conflict.", [])

        # Rule 1: Hardware crash takes direct precedence over secondary buffer congestion
        hw_hyp = next((h for h in hypotheses if any(k in h.probable_cause.lower() for k in ("hardware", "crash"))), None)
        if hw_hyp:
            cpu_vals = [_extract_numeric_observation(o, m, {"percent", "%"}) for o in observations for m in ("cpu_pct", "cpu_utilization_pct")]
            cpu_vals = [v for v in cpu_vals if v is not None]
            drop_vals = [_extract_numeric_observation(o, m) for o in observations for m in ("queue_drops", "egress_queue_drops")]
            drop_vals = [v for v in drop_vals if v is not None]

            if any(v >= DynamicThresholds.CPU_CRIT_PCT for v in cpu_vals) and any(v >= DynamicThresholds.QUEUE_DROPS_CRIT for v in drop_vals):
                rationale = (
                    f"Arbitration: Catastrophic hardware failure (CPU >= {DynamicThresholds.CPU_CRIT_PCT}%, "
                    f"queue drops >= {DynamicThresholds.QUEUE_DROPS_CRIT}) takes direct precedence over secondary buffer congestion."
                )
                conflicts_resolved.append({
                    "conflict": "Hardware Failure vs Congestion/CPU",
                    "winner": hw_hyp.probable_cause,
                    "precedence": "DIRECT",
                    "rationale": rationale,
                })
                return ArbitrationResult(hw_hyp, rationale, conflicts_resolved)

        # Rule 2: Physical layer optical attenuation vs Ethernet CRC/cabling degradation
        optics_hyp = next((h for h in hypotheses if any(k in h.probable_cause.lower() for k in ("optical", "fiber"))), None)
        eth_hyp = next((h for h in hypotheses if any(k in h.probable_cause.lower() for k in ("ethernet", "crc", "fcs", "cable"))), None)

        opt_pwr_crit = getattr(settings, "optical_rx_power_crit_dbm", DynamicThresholds.OPTICAL_RX_POWER_CRIT_DBM)
        opt_pwr_warn = getattr(settings, "optical_rx_power_warn_dbm", DynamicThresholds.OPTICAL_RX_POWER_WARN_DBM)

        optical_vals = [_extract_numeric_observation(o, "rx_power_dbm", {"dbm"}) for o in observations]
        optical_vals = [v for v in optical_vals if v is not None]

        has_optical_nominal_qual = any(
            (o.metric_name in ("rx_power_dbm", "optical_transceiver_status") and (
                o.observed_value == "nominal" or o.context.get("optical_nominal") is True
            )) for o in observations
        )
        has_optical_atten_qual = any(
            (o.metric_name in ("rx_power_dbm", "optical_transceiver_status") and (
                o.observed_value == "attenuated" or o.context.get("optical_attenuated") is True
            )) for o in observations
        )

        has_severe_optics = any(v < opt_pwr_crit for v in optical_vals) or has_optical_atten_qual
        has_nominal_optics = (any(v >= opt_pwr_warn for v in optical_vals) or has_optical_nominal_qual) and not has_optical_atten_qual

        if optics_hyp and has_severe_optics:
            rationale = (
                f"Arbitration: Optical Rx power attenuation below physical receiver threshold ({opt_pwr_crit} dBm) "
                "takes direct precedence over secondary soft counter anomalies."
            )
            conflicts_resolved.append({
                "conflict": "Optical Degradation vs Soft Congestion",
                "winner": optics_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(optics_hyp, rationale, conflicts_resolved)

        if optics_hyp and eth_hyp and has_nominal_optics:
            rationale = (
                f"Arbitration: Inquiry confirmed optical power within nominal specification (>= {opt_pwr_warn} dBm), "
                "refuting optical attenuation in favor of physical Ethernet interface corruption."
            )
            conflicts_resolved.append({
                "conflict": "Ethernet CRC vs Optical Attenuation",
                "winner": eth_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(eth_hyp, rationale, conflicts_resolved)

        # Rule 3: Confirmed MTU mismatch with packet drops overrides generic congestion
        mtu_hyp = next((h for h in hypotheses if "mtu" in h.probable_cause.lower()), None)
        has_mtu_evidence = any(
            (o.metric_name == "mtu_mismatch" and o.observed_value not in (None, False, "unknown"))
            or (o.metric_name == "large_packet_drops" and (_extract_numeric_observation(o, "large_packet_drops") or 0) > 0)
            for o in observations
        )
        if mtu_hyp and has_mtu_evidence:
            rationale = (
                "Arbitration: Confirmed MTU disparity with packet drop signature "
                "takes direct precedence over generic buffer starvation."
            )
            conflicts_resolved.append({
                "conflict": "MTU Mismatch vs Generic Congestion",
                "winner": mtu_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(mtu_hyp, rationale, conflicts_resolved)

        # Rule 4: Spanning tree loop with broadcast storm overrides generic CPU spike
        stp_hyp = next((h for h in hypotheses if any(k in h.probable_cause.lower() for k in ("spanning tree", "bpdu"))), None)
        has_stp_evidence = any(
            o.metric_name in ("bpdu_filter", "broadcast_storm") and o.observed_value not in (None, False)
            for o in observations
        )
        if stp_hyp and has_stp_evidence:
            rationale = (
                "Arbitration: BPDU filter misconfiguration causing catastrophic broadcast loop "
                "takes direct precedence over general CPU overload."
            )
            conflicts_resolved.append({
                "conflict": "STP Loop vs CPU Overload",
                "winner": stp_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(stp_hyp, rationale, conflicts_resolved)

        # Rule 5: DNS or DHCP service failure takes precedence when IP routing is healthy
        dns_hyp = next((h for h in hypotheses if "dns" in h.probable_cause.lower()), None)
        if dns_hyp:
            dns_vals = [_extract_numeric_observation(o, "dns_failure_pct", {"percent", "%"}) for o in observations]
            dns_vals = [v for v in dns_vals if v is not None]
            if any(v >= DynamicThresholds.DNS_FAILURE_CRIT_PCT for v in dns_vals):
                rationale = f"Arbitration: DNS resolution failure rate (>= {DynamicThresholds.DNS_FAILURE_CRIT_PCT}%) takes direct precedence over transport anomalies."
                conflicts_resolved.append({
                    "conflict": "DNS Outage vs Transport Delay",
                    "winner": dns_hyp.probable_cause,
                    "precedence": "DIRECT",
                    "rationale": rationale,
                })
                return ArbitrationResult(dns_hyp, rationale, conflicts_resolved)

        # Rule 6: Upstream transit saturation confirmed via inquiry vs local link congestion
        upstream_hyp = next((h for h in hypotheses if any(k in h.probable_cause.lower() for k in ("upstream", "transit"))), None)
        congestion_hyp = next((h for h in hypotheses if any(k in h.probable_cause.lower() for k in ("congestion", "queue"))), None)

        has_upstream_confirmed = any(
            (o.metric_name == "upstream_link_saturation" and o.observed_value not in (None, False))
            for o in observations
        )
        has_upstream_refuted = any(
            (o.metric_name == "upstream_links_nominal" and o.observed_value not in (None, False))
            for o in observations
        )

        if upstream_hyp and congestion_hyp:
            # Handle contradictory evidence: if both confirmed and refuted are present, abstain!
            if has_upstream_confirmed and has_upstream_refuted:
                rationale = "Arbitration abstained: Contradictory evidence detected for upstream transit link state."
                conflicts_resolved.append({
                    "conflict": "Upstream Transit Saturation vs Local Congestion",
                    "winner": "TIE",
                    "precedence": "CONTRADICTORY",
                    "rationale": rationale,
                })
                return ArbitrationResult(None, rationale, conflicts_resolved)
            elif has_upstream_confirmed:
                rationale = (
                    "Arbitration: Targeted inquiry corroborated upstream transit link saturation, "
                    "establishing upstream provider failure as root cause."
                )
                conflicts_resolved.append({
                    "conflict": "Upstream Transit Saturation vs Local Congestion",
                    "winner": upstream_hyp.probable_cause,
                    "precedence": "DIRECT",
                    "rationale": rationale,
                })
                return ArbitrationResult(upstream_hyp, rationale, conflicts_resolved)
            elif has_upstream_refuted:
                rationale = (
                    "Arbitration: Targeted inquiry verified upstream transit hops are nominal, "
                    "refuting upstream transit cascade in favor of local link congestion."
                )
                conflicts_resolved.append({
                    "conflict": "Upstream Transit Saturation vs Local Congestion",
                    "winner": congestion_hyp.probable_cause,
                    "precedence": "DIRECT",
                    "rationale": rationale,
                })
                return ArbitrationResult(congestion_hyp, rationale, conflicts_resolved)

        # Rule 7: Wi-Fi RF degradation corroborated via inquiry vs wired queue congestion
        wifi_hyp = next((h for h in hypotheses if any(k in h.probable_cause.lower() for k in ("wifi", "wireless"))), None)
        has_wifi_confirmed = any(
            (o.metric_name == "wifi_rf_degradation" and o.observed_value not in (None, False))
            for o in observations
        )
        has_wifi_refuted = any(
            (o.metric_name == "wifi_rf_nominal" and o.observed_value not in (None, False))
            for o in observations
        )

        if wifi_hyp and congestion_hyp:
            if has_wifi_confirmed and has_wifi_refuted:
                rationale = "Arbitration abstained: Contradictory wireless RF telemetry observed across access points."
                conflicts_resolved.append({
                    "conflict": "Wi-Fi RF Degradation vs Wired Congestion",
                    "winner": "TIE",
                    "precedence": "CONTRADICTORY",
                    "rationale": rationale,
                })
                return ArbitrationResult(None, rationale, conflicts_resolved)
            elif has_wifi_confirmed:
                rationale = (
                    "Arbitration: Targeted inquiry confirmed Wi-Fi RF coverage degradation, "
                    "establishing wireless channel degradation as root cause over wired backhaul."
                )
                conflicts_resolved.append({
                    "conflict": "Wi-Fi RF Degradation vs Wired Congestion",
                    "winner": wifi_hyp.probable_cause,
                    "precedence": "DIRECT",
                    "rationale": rationale,
                })
                return ArbitrationResult(wifi_hyp, rationale, conflicts_resolved)
            elif has_wifi_refuted:
                rationale = (
                    "Arbitration: Targeted inquiry verified Wi-Fi RF parameters within nominal bounds, "
                    "establishing wired backhaul congestion as root cause."
                )
                conflicts_resolved.append({
                    "conflict": "Wi-Fi RF Degradation vs Wired Congestion",
                    "winner": congestion_hyp.probable_cause,
                    "precedence": "DIRECT",
                    "rationale": rationale,
                })
                return ArbitrationResult(congestion_hyp, rationale, conflicts_resolved)

        # Rule 8: Precedence based on EvidencePrecedence ranking
        def get_precedence(h: Hypothesis) -> int:
            if not observations:
                return EvidencePrecedence.CORRELATED.value
            cause_lower = h.probable_cause.lower()
            if any(k in cause_lower for k in ("hardware", "optical", "crc", "cable", "ethernet", "dns", "dhcp", "wifi", "rf")):
                return EvidencePrecedence.DIRECT.value
            if any(k in cause_lower for k in ("congestion", "cpu", "queue", "drop", "buffer")):
                return EvidencePrecedence.CORRELATED.value
            return EvidencePrecedence.TOPOLOGY_INFERENCE.value

        sorted_by_precedence = sorted(
            hypotheses,
            key=lambda h: (get_precedence(h), h.confidence),
            reverse=True,
        )

        top = sorted_by_precedence[0]
        second = sorted_by_precedence[1]

        top_prec = get_precedence(top)
        sec_prec = get_precedence(second)

        if top_prec > sec_prec:
            rationale = (
                f"Arbitration: Selected '{top.probable_cause}' by evidence precedence "
                f"({EvidencePrecedence(top_prec).name} > {EvidencePrecedence(sec_prec).name})."
            )
            conflicts_resolved.append({
                "conflict": f"{top.probable_cause} vs {second.probable_cause}",
                "winner": top.probable_cause,
                "precedence": EvidencePrecedence(top_prec).name,
                "rationale": rationale,
            })
            return ArbitrationResult(top, rationale, conflicts_resolved)

        # Fallback: Compare confidence scores at same precedence level
        conf_diff = top.confidence - second.confidence
        if conf_diff < 0.10:
            rationale = (
                f"Arbitration tie: '{top.probable_cause}' ({top.confidence:.2f}) and "
                f"'{second.probable_cause}' ({second.confidence:.2f}) remain within 0.10 margin at equal precedence. "
                "Evidence insufficient to declare single winner."
            )
            conflicts_resolved.append({
                "conflict": f"{top.probable_cause} vs {second.probable_cause}",
                "winner": "TIE",
                "precedence": EvidencePrecedence(top_prec).name,
                "rationale": rationale,
            })
            return ArbitrationResult(None, rationale, conflicts_resolved)

        rationale = (
            f"Arbitration: Selected '{top.probable_cause}' with superior confidence "
            f"({top.confidence:.2f} vs {second.confidence:.2f})."
        )
        conflicts_resolved.append({
            "conflict": f"{top.probable_cause} vs {second.probable_cause}",
            "winner": top.probable_cause,
            "precedence": EvidencePrecedence(top_prec).name,
            "rationale": rationale,
        })
        return ArbitrationResult(top, rationale, conflicts_resolved)
