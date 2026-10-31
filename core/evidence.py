"""Evidence facade mirroring netcoop.core.evidence."""

import sys
import netcoop.core.evidence

sys.modules[__name__] = netcoop.core.evidence
from netcoop.core.evidence import DiagnosticHypothesis, EvidenceConfidenceLevel, EvidenceItem, UncertaintyEvaluation
