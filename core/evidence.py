"""Evidence representations, chaining, and corroboration matrices."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class EvidenceConfidenceLevel(str, Enum):
    """Categorical confidence level."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CERTAIN = "certain"


class EvidenceItem(BaseModel):
    """Single verified evidence datum with provenance."""

    source_agent: str
    category: str
    finding: str
    entity: str
    metric_name: Optional[str] = None
    value: Union[float, int, str, bool, None] = None
    unit: Optional[str] = None
    severity: str = "warning"
    timestamp: Optional[str] = None
    weight: float = 1.0


class DiagnosticHypothesis(BaseModel):
    """Correlated hypothesis composed of multiple agent observations."""

    cause_key: str
    title: str
    description: str
    affected_devices: List[str]
    affected_interfaces: List[str] = Field(default_factory=list)
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    refuting_evidence: List[EvidenceItem] = Field(default_factory=list)
    required_evidence_domains: List[str] = Field(default_factory=list)
    provided_evidence_domains: List[str] = Field(default_factory=list)
    raw_score: float = 0.0
    final_confidence: float = 0.0
    is_sufficient: bool = False
    suggested_remediation_type: Optional[str] = None


class UncertaintyEvaluation(BaseModel):
    """Quantitative and qualitative measurement of diagnostic ambiguity."""

    score: float = Field(ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    alternative_hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
