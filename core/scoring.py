"""Diagnostic evidence scoring and certainty calculation algorithms."""

from typing import List, Optional, Set, Tuple
from core.evidence import DiagnosticHypothesis, EvidenceItem, UncertaintyEvaluation


class EvidenceScorer:
    """Computes quantitative diagnostic confidence and uncertainty scores."""

    MIN_ACCEPTABLE_CONFIDENCE: float = 0.70

    @classmethod
    def calculate_confidence(
        cls,
        base_weight: float,
        required_domains: List[str],
        provided_domains: List[str],
        refuting_evidence: Optional[List[EvidenceItem]] = None,
        temporal_spread_seconds: float = 0.0,
    ) -> Tuple[float, float, bool]:
        """Calculate composite diagnostic confidence.

        Formula:
          coverage_ratio = len(provided & required) / len(required)
          penalty = 0.25 * len(refuting_evidence)
          confidence = base_weight * coverage_ratio * (1.0 - penalty)
          uncertainty = max(0.0, 1.0 - confidence)

        Returns:
            Tuple of (confidence: float, uncertainty: float, is_sufficient: bool)
        """
        req_set = set(required_domains)
        prov_set = set(provided_domains)

        if not req_set:
            return 0.0, 1.0, False

        overlap = req_set.intersection(prov_set)
        coverage_ratio = len(overlap) / len(req_set)

        ref_count = len(refuting_evidence) if refuting_evidence else 0
        contradiction_penalty = min(0.60, ref_count * 0.25)

        # Decay confidence slightly if events are separated by > 300 seconds
        temporal_penalty = 0.10 if temporal_spread_seconds > 300.0 else 0.0

        raw = base_weight * coverage_ratio * (1.0 - contradiction_penalty - temporal_penalty)
        confidence = round(max(0.0, min(1.0, raw)), 2)

        is_sufficient = coverage_ratio >= 1.0 and confidence >= cls.MIN_ACCEPTABLE_CONFIDENCE
        uncertainty = round(max(0.0, 1.0 - confidence), 2)

        return confidence, uncertainty, is_sufficient

    @classmethod
    def evaluate_uncertainty(
        cls,
        hypotheses: List[DiagnosticHypothesis],
        missing_domains: List[str],
    ) -> UncertaintyEvaluation:
        """Construct detailed quantitative and qualitative uncertainty report."""
        if not hypotheses:
            return UncertaintyEvaluation(
                score=1.0,
                reasons=["No candidate hypothesis matched empirical observations."],
                missing_evidence=missing_domains or ["telemetry_counters", "config_diff", "syslog"],
                alternative_hypotheses=[],
            )

        top = hypotheses[0]
        alt = [
            {"cause": h.title, "confidence": h.final_confidence}
            for h in hypotheses[1:]
        ]

        reasons = []
        if not top.is_sufficient:
            reasons.append(
                f"Top candidate '{top.title}' lacked full cross-domain corroboration."
            )
        if len(hypotheses) > 1 and abs(top.final_confidence - hypotheses[1].final_confidence) < 0.10:
            reasons.append(
                "Multiple competing hypotheses exhibit close confidence scores within 0.10 margin."
            )

        missing = [f"corroboration:{d}" for d in missing_domains]

        return UncertaintyEvaluation(
            score=round(max(0.0, 1.0 - top.final_confidence), 2),
            reasons=reasons,
            missing_evidence=missing,
            alternative_hypotheses=alt,
        )

