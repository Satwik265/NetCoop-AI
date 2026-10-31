"""Agent 5: Root Cause Synthesizer and Evidence Judge."""

from typing import Any, Dict, List, Optional
from netcoop.agents.base import BaseAgent
from netcoop.core.correlation import OfflineCorrelationEngine
from netcoop.core.envelope import (
    AgentEnvelope,
    AgentRole,
    Hypothesis,
    MessageType,
    Observation,
)
from netcoop.core.evidence import DiagnosticHypothesis, UncertaintyEvaluation


class SynthesizerAgent(BaseAgent):
    """Correlates multi-agent evidence chains and enforces the insufficient evidence guarantee."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.SYNTHESIZER_AGENT,
            name="Root Cause Synthesizer",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Evaluate accumulated findings from specialist agents."""
        response = self.create_response_envelope(envelope, MessageType.SYNTHESIS_SUBMISSION)

        all_observations = envelope.payload.observations
        status, top_hyp, uncertainty = OfflineCorrelationEngine.evaluate(all_observations)

        response.context["diagnostic_status"] = status
        response.context["uncertainty"] = uncertainty.model_dump()

        if status == "diagnosed" and top_hyp:
            response.payload.hypotheses = [
                Hypothesis(
                    probable_cause=top_hyp.title,
                    confidence=top_hyp.final_confidence,
                    supporting_observation_ids=[
                        e.metric_name or "obs" for e in top_hyp.supporting_evidence
                    ],
                    required_corroboration=top_hyp.required_evidence_domains,
                )
            ]
            response.context["hypothesis"] = top_hyp.model_dump()
        else:
            # Insufficient evidence
            response.payload.hypotheses = []
            response.context["hypothesis"] = None

        return response
