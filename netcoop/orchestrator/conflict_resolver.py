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

        Returns:
            ArbitrationResult unpackable as:
              - 2-tuple: (winning_hypothesis, resolution_rationale)
              - 3-tuple: (winning_hypothesis, resolution_rationale, conflicts_resolved)
        """
        conflicts_resolved: List[Dict[str, Any]] = []

        if not hypotheses:
            return ArbitrationResult(None, "No hypotheses to arbitrate.", [])

        if len(hypotheses) == 1:
            return ArbitrationResult(hypotheses[0], "Single hypothesis without conflict.", [])

        obs_names = {o.metric_name for o in observations}

        # Rule 1: Hardware crash / failure takes highest direct precedence
        hw_hyp = next((h for h in hypotheses if "hardware" in h.probable_cause.lower() or "crash" in h.probable_cause.lower()), None)
        has_severe_hw = any(
            (o.metric_name in ("cpu_pct", "cpu_utilization_pct") and float(o.observed_value or 0) >= 95.0)
            for o in observations
        ) and any(
            (o.metric_name in ("queue_drops", "egress_queue_drops") and float(o.observed_value or 0) >= 2000)
            for o in observations
        )
        if hw_hyp and has_severe_hw:
            rationale = (
                "Arbitration: Catastrophic hardware failure with severe forwarding plane crash "
                "takes direct precedence over secondary buffer congestion."
            )
            conflicts_resolved.append({
                "conflict": "Hardware Failure vs Congestion/CPU",
                "winner": hw_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(hw_hyp, rationale, conflicts_resolved)

        # Rule 2: Physical layer optical attenuation overrides soft queue congestion
        optics_hyp = next((h for h in hypotheses if "optical" in h.probable_cause.lower() or "fiber" in h.probable_cause.lower()), None)
        has_severe_optics = any(
            o.metric_name == "rx_power_dbm" and float(o.observed_value or 0) < -15.0
            for o in observations
        )
        if optics_hyp and has_severe_optics:
            rationale = (
                "Arbitration: Optical Rx power attenuation below physical receiver threshold "
                "takes direct precedence over soft counter anomalies."
            )
            conflicts_resolved.append({
                "conflict": "Optical Degradation vs Soft Congestion",
                "winner": optics_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(optics_hyp, rationale, conflicts_resolved)

        # Rule 2b: Optical inquiry nominal refutes optical hypothesis in favor of Ethernet CRC fault
        eth_hyp = next((h for h in hypotheses if "ethernet" in h.probable_cause.lower() or "crc" in h.probable_cause.lower()), None)
        has_nominal_optics = any(
            o.metric_name == "rx_power_dbm" and float(o.observed_value or 0) >= -15.0
            for o in observations
        )
        if optics_hyp and eth_hyp and has_nominal_optics:
            rationale = (
                "Arbitration: Inquiry confirmed optical power within nominal specification, "
                "refuting optical attenuation in favor of physical Ethernet interface corruption."
            )
            conflicts_resolved.append({
                "conflict": "Ethernet CRC vs Optical Attenuation",
                "winner": eth_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(eth_hyp, rationale, conflicts_resolved)

        # Rule 3: Confirmed MTU mismatch with large packet drops overrides generic congestion
        mtu_hyp = next((h for h in hypotheses if "mtu" in h.probable_cause.lower()), None)
        has_mtu_evidence = any(
            o.metric_name in ("mtu_mismatch", "large_packet_drops")
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
        stp_hyp = next((h for h in hypotheses if "spanning tree" in h.probable_cause.lower() or "bpdu" in h.probable_cause.lower()), None)
        has_stp_evidence = any(
            o.metric_name in ("bpdu_filter", "broadcast_storm")
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
        if dns_hyp and any(o.metric_name == "dns_failure_pct" and float(o.observed_value or 0) > 20.0 for o in observations):
            rationale = "Arbitration: DNS resolution failure rate takes direct precedence over transport anomalies."
            conflicts_resolved.append({
                "conflict": "DNS Outage vs Transport Delay",
                "winner": dns_hyp.probable_cause,
                "precedence": "DIRECT",
                "rationale": rationale,
            })
            return ArbitrationResult(dns_hyp, rationale, conflicts_resolved)

        # Rule 6: Upstream transit saturation confirmed via inquiry vs local link congestion
        upstream_hyp = next((h for h in hypotheses if "upstream" in h.probable_cause.lower() or "transit" in h.probable_cause.lower()), None)
        congestion_hyp = next((h for h in hypotheses if "congestion" in h.probable_cause.lower() or "queue" in h.probable_cause.lower()), None)
        has_upstream_confirmed = any(o.metric_name == "upstream_link_saturation" for o in observations)
        has_upstream_refuted = any(o.metric_name == "upstream_links_nominal" for o in observations)

        if upstream_hyp and congestion_hyp:
            if has_upstream_confirmed:
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
        wifi_hyp = next((h for h in hypotheses if "wifi" in h.probable_cause.lower() or "wireless" in h.probable_cause.lower()), None)
        has_wifi_confirmed = any(o.metric_name == "wifi_rf_degradation" for o in observations)
        if wifi_hyp and congestion_hyp and has_wifi_confirmed:
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
