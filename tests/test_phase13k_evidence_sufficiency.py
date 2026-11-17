"""Phase 13K tests for EvidenceItem independence_class, derived_from, source_type,
independent_domain_count computation, and the high-impact sufficiency policy.
"""

from netcoop.core.evidence import DiagnosticHypothesis, EvidenceItem
from netcoop.reporting.builder import export_hackathon_report_json
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.data.generator import SyntheticNetworkGenerator


def test_evidence_item_independence_fields():
    """Verify independence_class, derived_from, and source_type on EvidenceItem."""
    e1 = EvidenceItem(
        source_agent="telemetry_agent",
        category="metric_anomaly",
        finding="High link util",
        entity="rtr-01",
        metric="link_utilization_pct",
        value=92.5,
    )
    assert e1.independence_class == "direct"
    assert e1.derived_from == []
    assert e1.source_type is None

    e2 = EvidenceItem(
        source_agent="classifier_agent",
        category="model_prediction",
        finding="Classifier attribution",
        entity="rtr-01",
        independence_class="derived",
        derived_from=["evi-001", "evi-002"],
        source_type="classifier",
    )
    assert e2.independence_class == "derived"
    assert e2.derived_from == ["evi-001", "evi-002"]
    assert e2.source_type == "classifier"


def test_diagnostic_hypothesis_independent_domain_count():
    """Verify independent_domain_count computation and get_independent_domains."""
    e_tel = EvidenceItem(
        source_agent="telemetry_agent",
        category="metric_anomaly",
        finding="High util",
        entity="rtr-01",
        source_type="telemetry",
        independence_class="direct",
    )
    e_topo = EvidenceItem(
        source_agent="topology_agent",
        category="topology_bottleneck",
        finding="Transit bottleneck",
        entity="rtr-01",
        source_type="topology",
        independence_class="direct",
    )
    e_derived = EvidenceItem(
        source_agent="classifier_agent",
        category="attribution",
        finding="Model score",
        entity="rtr-01",
        source_type="classifier",
        independence_class="derived",
        derived_from=["evi-tel-1"],
    )

    hyp = DiagnosticHypothesis(
        cause_key="LINK_CONGESTION",
        title="Link Congestion",
        description="High utilization bottleneck",
        affected_devices=["rtr-01"],
        supporting_evidence=[e_tel, e_topo, e_derived],
    )

    # Direct domains are telemetry and topology (classifier is derived)
    assert hyp.independent_domain_count == 2
    assert set(hyp.get_independent_domains()) == {"telemetry", "topology"}


def test_10_key_export_shape_unchanged():
    """Verify that export_hackathon_report_json produces strictly the exact 10 keys."""
    gen = SyntheticNetworkGenerator()
    inc = gen.generate(scenario="link_congestion", seed=42)
    rep = run_diagnosis(inc)
    export = export_hackathon_report_json(rep)

    expected_keys = [
        "incident_id",
        "status",
        "suspected_root_cause",
        "confidence",
        "affected_devices",
        "supporting_evidence",
        "alternative_causes",
        "recommended_actions",
        "evidence_sources",
        "limitations",
    ]
    assert list(export.keys()) == expected_keys
    for item in export["supporting_evidence"]:
        assert set(item.keys()) == {"metric", "value", "interpretation"}


def test_sufficiency_policy_marks_limited_on_single_domain():
    """Verify that high-impact diagnoses with < 2 independent domains are marked limited."""
    # Create incident with single domain evidence manually
    e_tel = EvidenceItem(
        source_agent="telemetry_agent",
        category="metric_anomaly",
        finding="High util",
        entity="rtr-01",
        source_type="telemetry",
        independence_class="direct",
    )
    hyp = DiagnosticHypothesis(
        cause_key="LINK_CONGESTION",
        title="Link Congestion",
        description="High utilization bottleneck",
        affected_devices=["rtr-01"],
        supporting_evidence=[e_tel],
        final_confidence=0.88,
        is_sufficient=True,
    )
    assert hyp.independent_domain_count == 1
    assert len(hyp.get_independent_domains()) == 1
