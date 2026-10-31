"""State definition for LangGraph orchestrator."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from netcoop.core.envelope import AgentEnvelope, Hypothesis, Inquiry, Observation
from netcoop.core.report import UnifiedDiagnosticReport


class OrchestratorState(BaseModel):
    """Runtime state managed across LangGraph super-steps."""

    incident_id: str
    network_id: str
    raw_data: Dict[str, Any]
    envelopes: List[AgentEnvelope] = Field(default_factory=list)
    accumulated_observations: List[Observation] = Field(default_factory=list)
    accumulated_hypotheses: List[Hypothesis] = Field(default_factory=list)
    inquiries_queue: List[Inquiry] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 3
    is_paused: bool = False
    conflict_detected: bool = False
    conflict_summary: Optional[str] = None
    status: str = "initialized"
    report: Optional[UnifiedDiagnosticReport] = None

