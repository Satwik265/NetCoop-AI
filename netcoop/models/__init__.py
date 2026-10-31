"""Core domain models, diagnostic schemas, and classification structures for NetCoop AI."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DiagnosticPrediction(BaseModel):
    """Classifier prediction candidate."""

    probable_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    category: str
    affected_devices: List[str] = Field(default_factory=list)
    supporting_signals: List[str] = Field(default_factory=list)


class ScenarioEvaluationResult(BaseModel):
    """Result of evaluating a single scenario against ground truth."""

    scenario_name: str
    ground_truth: str
    predicted_status: str
    confidence: float
    is_correct: bool
    latency_ms: float
