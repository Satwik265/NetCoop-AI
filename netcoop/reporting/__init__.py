"""NetCoop AI Reporting Package.

Exports models and builder for two-level Network Diagnostic Reports:
- Level 1: Executive Report
- Level 2: Technical Report
- NetworkDiagnosticReport: Root typed container model
- DiagnosticReportBuilder: Normalization and construction engine
"""

from netcoop.reporting.builder import DiagnosticReportBuilder, export_hackathon_report_json
from netcoop.reporting.models import (
    AgentInvestigationRecord,
    AgentState,
    AuditReference,
    CampusTopologyReference,
    ConfidenceCalibrationData,
    DiagnosticStatus,
    EvidenceRecord,
    ExecutiveReport,
    MetricObservation,
    NetworkDiagnosticReport,
    RecommendedAction,
    RecoveryStatus,
    RemediationState,
    ReportSeverity,
    RootCauseStatus,
    TechnicalReport,
    TechnicalSection,
)

__all__ = [
    "DiagnosticReportBuilder",
    "export_hackathon_report_json",
    "NetworkDiagnosticReport",
    "ExecutiveReport",
    "TechnicalReport",
    "TechnicalSection",
    "DiagnosticStatus",
    "ReportSeverity",
    "AgentState",
    "RootCauseStatus",
    "RemediationState",
    "RecoveryStatus",
    "MetricObservation",
    "EvidenceRecord",
    "AgentInvestigationRecord",
    "RecommendedAction",
    "CampusTopologyReference",
    "ConfidenceCalibrationData",
    "AuditReference",
]
