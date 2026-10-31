"""Conflict detection, cross-examination inquiry generation, and arbitration engine."""

from typing import Any, Dict, List, Optional, Tuple
from netcoop.core.envelope import AgentRole, Hypothesis, Inquiry, Observation


class ConflictResolver:
    """Detects and resolves contradictory hypotheses across specialist agents."""

    @classmethod
    def detect_conflicts(cls, hypotheses: List[Hypothesis]) -> bool:
        """Return True if multiple distinct hypotheses are present with conflicting causes."""
        if len(hypotheses) < 2:
            return False

        # Group by general fault category keywords
        causes = [h.probable_cause.lower() for h in hypotheses]
        has_mtu = any("mtu" in c for c in causes)
        has_optic = any("optical" in c or "fiber" in c for c in causes)
        has_stp = any("spanning tree" in c or "bpdu" in c for c in causes)
        has_bgp = any("bgp" in c or "flap" in c for c in causes)

        categories = [has_mtu, has_optic, has_stp, has_bgp]
        competing_categories = sum(1 for c in categories if c)
        return competing_categories >= 2

    @classmethod
    def generate_cross_inquiries(
        cls,
        hypotheses: List[Hypothesis],
        observations: List[Observation],
    ) -> List[Inquiry]:
        """Generate targeted inquiry envelopes to resolve ambiguities between hypotheses."""
        inquiries: List[Inquiry] = []
        obs_names = {o.metric_name for o in observations}

        # Check if MTU vs buffer congestion dispute
        has_drops = "egress_queue_drops" in obs_names or "packet_loss_pct" in obs_names
        has_mtu_obs = "mtu_mismatch" in obs_names or "mtu" in obs_names

        if has_drops and not has_mtu_obs:
            inquiries.append(
                Inquiry(
                    target_agent=AgentRole.CONFIG_AGENT,
                    question="Audit peer interface MTUs along the transit path for size mismatches.",
                    target_entity="transit_interfaces",
                )
            )

        # Check if CRC vs optical power dispute
        has_crc = "fcs_errors" in obs_names or "crc_errors" in obs_names
        has_optics = "rx_power_dbm" in obs_names

        if has_crc and not has_optics:
            inquiries.append(
                Inquiry(
                    target_agent=AgentRole.TELEMETRY_AGENT,
                    question="Retrieve optical DOM transceiver power levels for interfaces reporting CRC errors.",
                    target_entity="crc_reporting_interfaces",
                )
            )

        return inquiries

    @classmethod
    def arbitrate(
        cls,
        hypotheses: List[Hypothesis],
        observations: List[Observation],
    ) -> Tuple[Optional[Hypothesis], str]:
        """Apply deterministic rules to resolve competing hypotheses.

        Returns:
            Tuple of (winning_hypothesis or None, resolution_rationale)
        """
        if not hypotheses:
            return None, "No hypotheses to arbitrate."

        if len(hypotheses) == 1:
            return hypotheses[0], "Single hypothesis without conflict."

        # Rule 1: Physical layer optical attenuation overrides soft queue congestion
        optics_hyp = next((h for h in hypotheses if "optical" in h.probable_cause.lower() or "fiber" in h.probable_cause.lower()), None)
        has_severe_optics = any(
            o.metric_name == "rx_power_dbm" and float(o.observed_value or 0) < -15.0
            for o in observations
        )
        if optics_hyp and has_severe_optics:
            return (
                optics_hyp,
                "Arbitration: Optical Rx power attenuation below physical receiver threshold takes precedence over soft counter anomalies.",
            )

        # Rule 2: Explicit MTU mismatch with large packet drops overrides generic congestion
        mtu_hyp = next((h for h in hypotheses if "mtu" in h.probable_cause.lower()), None)
        has_mtu_evidence = any(
            o.metric_name in ("mtu_mismatch", "large_packet_drops")
            for o in observations
        )
        if mtu_hyp and has_mtu_evidence:
            return (
                mtu_hyp,
                "Arbitration: Confirmed MTU disparity with large packet drops takes precedence over generic buffer starvation.",
            )

        # Rule 3: Spanning tree loop with broadcast storm
        stp_hyp = next((h for h in hypotheses if "spanning tree" in h.probable_cause.lower() or "bpdu" in h.probable_cause.lower()), None)
        has_stp_evidence = any(
            o.metric_name in ("bpdu_filter", "cpu_utilization_pct")
            for o in observations
        )
        if stp_hyp and has_stp_evidence:
            return (
                stp_hyp,
                "Arbitration: BPDU filter misconfiguration causing catastrophic broadcast loop takes precedence.",
            )

        # Fallback: Sort by confidence
        sorted_hyps = sorted(hypotheses, key=lambda h: h.confidence, reverse=True)
        top = sorted_hyps[0]
        second = sorted_hyps[1]

        if (top.confidence - second.confidence) < 0.10:
            return (
                None,
                f"Arbitration tie: '{top.probable_cause}' ({top.confidence:.2f}) and '{second.probable_cause}' ({second.confidence:.2f}) remain within 0.10 margin. Evidence insufficient to declare single winner.",
            )

        return (
            top,
            f"Arbitration: Selected '{top.probable_cause}' with superior confidence ({top.confidence:.2f} vs {second.confidence:.2f}).",
        )

