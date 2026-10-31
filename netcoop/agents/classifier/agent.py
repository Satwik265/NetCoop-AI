"""Agent 7: Statistical & Rule-Based Classifier Agent."""

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
from netcoop.agents.classifier import ScenarioClassifier


class ClassifierAgent(BaseAgent):
    """Statistical and heuristic classifier agent evaluating telemetry signatures."""

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.CLASSIFIER_AGENT,
            name="Statistical & Heuristic Classifier",
        )

    def handle_envelope(self, envelope: AgentEnvelope) -> AgentEnvelope:
        """Process incoming dispatch or inquiry using heuristic classification rules."""
        response = self.create_response_envelope(envelope, MessageType.FINDING_SUBMISSION)
        raw_telemetry = (envelope.payload.raw_data or {}).get("telemetry", [])

        prediction = ScenarioClassifier.classify_telemetry(raw_telemetry)
        if prediction:
            obs = Observation(
                category=ObservationCategory.METRIC_ANOMALY,
                entity=prediction.affected_devices[0] if prediction.affected_devices else "network",
                metric_name="classification_inference",
                observed_value=prediction.category,
                unit="text",
                severity=Severity.CRITICAL if prediction.confidence > 0.9 else Severity.WARNING,
                context={
                    "agent_domain": "classifier_agent",
                    "signals": prediction.supporting_signals,
                },
            )
            response.payload.observations = [obs]
            response.payload.hypotheses = [
                Hypothesis(
                    probable_cause=prediction.probable_cause,
                    confidence=prediction.confidence,
                    supporting_observation_ids=[obs.observation_id],
                    required_corroboration=["telemetry_agent"],
                )
            ]

        return response
