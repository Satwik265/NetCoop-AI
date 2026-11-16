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
    independence_class: str = "direct"  # direct, derived, inferred
    derived_from: List[str] = Field(default_factory=list)
    source_type: Optional[str] = None

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
    independent_domain_count: int = 0

    @model_validator(mode="after")
    def compute_domains(self) -> "DiagnosticHypothesis":
        if self.supporting_evidence:
            direct_domains = set()
            for e in self.supporting_evidence:
                indep = getattr(e, "independence_class", "direct") or "direct"
                if indep == "direct":
                    dom = getattr(e, "source_type", None) or getattr(e, "source_agent", None)
                    if dom:
                        direct_domains.add(dom)
            if not direct_domains:
                for e in self.supporting_evidence:
                    dom = getattr(e, "source_type", None) or getattr(e, "source_agent", None)
                    if dom:
                        direct_domains.add(dom)
            self.independent_domain_count = len(direct_domains)
        elif self.provided_evidence_domains:
            self.independent_domain_count = len(set(self.provided_evidence_domains))
        return self

    def get_independent_domains(self) -> List[str]:
        """Return list of distinct independent direct evidence domains."""
        domains = set()
        for e in self.supporting_evidence:
            indep = getattr(e, "independence_class", "direct") or "direct"
            if indep == "direct":
                dom = getattr(e, "source_type", None) or getattr(e, "source_agent", None)
                if dom:
                    domains.add(dom)
        if not domains and self.supporting_evidence:
            for e in self.supporting_evidence:
                dom = getattr(e, "source_type", None) or getattr(e, "source_agent", None)
                if dom:
                    domains.add(dom)
        if not domains and self.provided_evidence_domains:
            domains = set(self.provided_evidence_domains)
        return sorted(list(domains))


class UncertaintyEvaluation(BaseModel):
    """Quantitative and qualitative measurement of diagnostic ambiguity."""

    score: float = Field(ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    alternative_hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
