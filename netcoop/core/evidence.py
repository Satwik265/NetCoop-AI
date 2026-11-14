"""Evidence representations, chaining, and corroboration matrices."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator


class EvidenceConfidenceLevel(str, Enum):
    """Categorical confidence level."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CERTAIN = "certain"


class EvidenceItem(BaseModel):
    """Single verified evidence datum with complete observation provenance and lineage."""

    evidence_id: Optional[str] = None
    source_agent: str
    category: str
    finding: str
    interpretation: Optional[str] = None
    entity: str
    metric_name: Optional[str] = None
    metric: Optional[str] = None
    value: Union[float, int, str, bool, None] = None
    unit: Optional[str] = None
    severity: str = "warning"
    timestamp: Optional[str] = None
    timestamp_window: Optional[str] = None
    weight: float = 1.0
    observation_id: Optional[str] = None
    message_id: Optional[str] = None
    correlation_id: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def populate_defaults_and_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Alias metric_name <-> metric
            if "metric" in data and "metric_name" not in data:
                data["metric_name"] = data["metric"]
            elif "metric_name" in data and "metric" not in data:
                data["metric"] = data["metric_name"]

            # Alias finding <-> interpretation
            if "interpretation" in data and "finding" not in data:
                data["finding"] = data["interpretation"]
            elif "finding" in data and "interpretation" not in data:
                data["interpretation"] = data["finding"]

            # Stable evidence_id
            if not data.get("evidence_id"):
                obs_id = data.get("observation_id")
                if obs_id:
                    data["evidence_id"] = str(obs_id) if str(obs_id).startswith("evi-") else f"evi-{obs_id}"
                else:
                    data["evidence_id"] = f"evi-{uuid4().hex[:8]}"

        return data


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
