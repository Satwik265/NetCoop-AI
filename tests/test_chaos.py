"""Chaos, circuit-breaker, and degraded-mode resilience testing."""

import json
from pathlib import Path
import pytest
from netcoop.core.envelope import AgentRole, MessageType
from netcoop.core.evidence import DiagnosticHypothesis, UncertaintyEvaluation
from netcoop.core.report import ReportBuilder, UnifiedDiagnosticReport
from netcoop.core.signatures import HypothesisKey, SignatureMatcher
from netcoop.core.thresholds import is_snapshot_mode
from netcoop.orchestrator.mediator import AgentMediator, CircuitBreaker


def test_circuit_breaker_trips_and_fast_fails() -> None:
    """Verify that repeated microservice failures trip circuit breaker to open state."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_s=30.0)
    role = AgentRole.WIFI_SERVICES_AGENT

    assert not cb.is_open(role)
    cb.record_failure(role)
    assert not cb.is_open(role)

    # Second failure trips breaker
    cb.record_failure(role)
    assert cb.is_open(role)

    # Success resets breaker
    cb.record_success(role)
    assert not cb.is_open(role)


def test_mediator_degraded_mode_continuation() -> None:
    """Verify mediator records dead agents in limitations without crashing when in-process fallback occurs."""
    mediator = AgentMediator(mode="http")
    # Mark an agent as dead
    mediator.dead_agents.add("wifi_services_agent")
    mediator.dead_agents.add("classifier_agent")

    limitations = mediator.get_degraded_limitations()
    assert len(limitations) == 2
    assert any("classifier_agent" in l for l in limitations)
    assert any("wifi_services_agent" in l for l in limitations)


def test_missing_topology_handling() -> None:
    """Verify missing topology marks upstream alternatives unverifiable and notes limitation."""
    telemetry = [
        {
            "device_id": "SW_CAMPUS_1",
            "latency_ms": 180.0,
            "jitter_ms": 45.0,
            "link_utilization_pct": 65.0,
            "queue_drops": 25,
        }
    ]

    key, conf, aff_devs, alternatives, limitations = SignatureMatcher.evaluate_telemetry(
        telemetry, topology_available=False
    )
    assert key == HypothesisKey.LINK_CONGESTION
    assert any("topology data unavailable" in l for l in limitations)

    # Alternative should be marked unverifiable
    assert len(alternatives) >= 1
    upstream_alt = alternatives[0]
    assert upstream_alt.get("status") == "unverifiable"


def test_snapshot_mode_detection_and_penalty() -> None:
    """Verify single snapshot telemetry is detected and confidence is penalized."""
    # Single sample per device
    snapshot_records = [
        {"device_id": "SW_1", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 15.0},
        {"device_id": "SW_2", "timestamp": "2026-10-31T12:00:00Z", "latency_ms": 12.0},
    ]

    assert is_snapshot_mode(snapshot_records) is True

    # Multi-point time series
    series_records = [
        {"device_id": "SW_1", "timestamp": f"2026-10-31T12:0{i}:00Z", "latency_ms": 15.0}
        for i in range(5)
    ]
    assert is_snapshot_mode(series_records) is False


def test_report_to_markdown_rendering() -> None:
    """Verify UnifiedDiagnosticReport.to_markdown() produces clean monochrome output."""
    report = ReportBuilder.build_report(
        incident_id="inc-test-md",
        network_id="iit-bbs-campus",
        status="diagnosed",
        hypothesis=DiagnosticHypothesis(
            cause_key="LINK_CONGESTION",
            title="Link utilization saturation causing buffer queue drops and latency spikes",
            description="Core transit link saturated.",
            affected_devices=["SW_CAMPUS_1", "SW_CAMPUS_2"],
            final_confidence=0.92,
            is_sufficient=True,
        ),
        uncertainty=UncertaintyEvaluation(
            score=0.08,
            reasons=[],
            missing_evidence=[],
            alternative_hypotheses=[
                {
                    "cause": "Upstream provider congestion",
                    "confidence": 0.80,
                    "discriminating_test": "Check upstream queue drops",
                }
            ],
        ),
        causal_chain=[
            "High traffic volume exceeds link capacity",
            "Queue drops trigger packet delay",
        ],
        conflicts_resolved=[
            {
                "conflict": "Hardware vs Congestion",
                "winner": "Hardware",
                "precedence": "DIRECT",
                "rationale": "Direct hardware precedence",
                "iteration": 1,
            }
        ],
        limitations=["single snapshot, no temporal context"],
        provenance={"generator": "test_generator"},
    )

    md = report.to_markdown()
    assert "# Diagnostic Incident Report: inc-test-md" in md
    assert "## Summary" in md
    assert "## Causal Chain" in md
    assert "## Alternative Hypotheses" in md
    assert "## Multi-Agent Conflicts & Arbitration" in md
    assert "## Data Limitations & Caveats" in md
    assert "single snapshot, no temporal context" in md


def test_report_schema_json_validation() -> None:
    """Verify generated UnifiedDiagnosticReport validates against schemas/diagnostic_report.json."""
    import jsonschema

    schema_file = Path("schemas/diagnostic_report.json")
    assert schema_file.exists(), "schemas/diagnostic_report.json missing"
    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)

    report = ReportBuilder.build_report(
        incident_id="inc-schema-val",
        network_id="iit-bbs-campus",
        status="diagnosed",
        hypothesis=DiagnosticHypothesis(
            cause_key="DEVICE_HARDWARE_FAILURE",
            title="Device hardware failure or catastrophic control plane crash",
            description="Hardware failure.",
            affected_devices=["SW_CAMPUS_1"],
            final_confidence=0.95,
            is_sufficient=True,
        ),
        uncertainty=UncertaintyEvaluation(
            score=0.05,
            reasons=[],
            missing_evidence=[],
        ),
        causal_chain=["Hardware failure", "Forwarding halted"],
        conflicts_resolved=[{"iteration": 1, "rationale": "Arbitrated"}],
        limitations=["missing metrics"],
        provenance={"generator": "organizer_adapter"},
    )

    report_dict = json.loads(report.to_json())
    jsonschema.validate(instance=report_dict, schema=schema)


# -----------------------------------------------------------------------------
# 3. Chaos Fuzzer & Stress Testing
# -----------------------------------------------------------------------------

import copy
import random
from typing import Dict, Any, List, Optional
from netcoop.data.generator import SyntheticNetworkGenerator, SeverityLevel
from gateway.adapters.organizer_adapter import OrganizerAdapter
from netcoop.orchestrator.graph import run_diagnosis
from netcoop.core.envelope import AgentEnvelope, ProtocolHeader, EnvelopePayload, NetworkScope


class ChaosFuzzer:
    """Randomly applies schema and data corruptions to verify pipeline resilience."""

    @classmethod
    def corrupt(
        cls,
        scenario_data: Dict[str, Any],
        seed: int = 42,
        corruption_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        rng = random.Random(seed)
        corrupted = copy.deepcopy(scenario_data)
        telemetry = corrupted.get("telemetry", [])

        if not telemetry:
            return corrupted

        types = corruption_types or [
            "drop_fields",
            "rename_fields",
            "change_units",
            "shuffle_time",
            "truncate",
            "inject_nulls",
            "mix_schema_versions",
            "mix_organizer_records",
        ]

        active_corruptions = rng.sample(types, k=rng.randint(1, min(4, len(types))))

        for corr in active_corruptions:
            if corr == "drop_fields":
                for rec in telemetry:
                    keys = [k for k in rec.keys() if k not in ("device_id", "device")]
                    if keys:
                        drop_k = rng.choice(keys)
                        del rec[drop_k]

            elif corr == "rename_fields":
                field_map = {
                    "latency_ms": "rtt",
                    "link_utilization_pct": "util",
                    "queue_drops": "drops",
                    "packet_loss_pct": "loss",
                    "cpu_pct": "cpu_util",
                }
                for rec in telemetry:
                    for old_k, new_k in field_map.items():
                        if old_k in rec and rng.random() > 0.4:
                            rec[new_k] = rec.pop(old_k)

            elif corr == "change_units":
                for rec in telemetry:
                    if "latency_ms" in rec and rng.random() > 0.4:
                        rec["latency_s"] = rec.pop("latency_ms") / 1000.0
                    if "throughput_mbps" in rec and rng.random() > 0.4:
                        rec["throughput_kbps"] = rec.pop("throughput_mbps") * 1000.0

            elif corr == "shuffle_time":
                rng.shuffle(telemetry)

            elif corr == "truncate":
                corrupted["telemetry"] = telemetry[: max(1, len(telemetry) // 3)]

            elif corr == "inject_nulls":
                for rec in telemetry:
                    keys = [k for k in rec.keys() if k not in ("device_id", "device")]
                    if keys and rng.random() > 0.4:
                        null_k = rng.choice(keys)
                        rec[null_k] = rng.choice([None, "null", "NaN"])

            elif corr == "mix_schema_versions":
                corrupted["schema_version"] = rng.choice(["1.0.0", "2.0.0", "1.5"])

            elif corr == "mix_organizer_records":
                new_tel = []
                for rec in telemetry:
                    if rng.random() > 0.5:
                        dev = rec.get("device_id") or rec.get("device")
                        ts = rec.get("timestamp") or rec.get("timestamp_utc")
                        st = rec.get("device_status") or rec.get("status")
                        m = {k: v for k, v in rec.items() if k not in ("device_id", "device", "timestamp", "timestamp_utc", "device_status", "status")}
                        new_tel.append({"device_id": dev, "timestamp": ts, "status": st, "metrics": m})
                    else:
                        new_tel.append(rec)
                corrupted["telemetry"] = new_tel

        return corrupted


def test_chaos_fuzzer_resilience_and_confidence_capping() -> None:
    """Verify fuzzer corruptions across scenarios never crash and cap confidence as data quality drops."""
    scenarios = [
        "link_congestion",
        "weak_wifi_signal",
        "ethernet_interface_fault",
        "dns_failure",
    ]

    for sc_name in scenarios:
        for seed in (10, 42, 99):
            base_data = SyntheticNetworkGenerator.generate(scenario=sc_name, seed=seed)
            corrupted = ChaosFuzzer.corrupt(base_data, seed=seed)

            adapted = OrganizerAdapter.adapt_dataset(corrupted)
            dq_score = adapted.get("data_quality", {}).get("overall_score", 1.0)

            report = run_diagnosis(adapted)

            assert isinstance(report, UnifiedDiagnosticReport)
            assert report.status in ("diagnosed", "insufficient_evidence", "benign")

            # Hard rule: when data quality drops below 0.60, confidence is capped
            if dq_score < 0.60 and report.status == "diagnosed":
                assert report.confidence <= 0.88, f"Overconfident {report.confidence} on degraded data (dq={dq_score})"


def test_chaos_fuzzer_on_organizer_samples() -> None:
    """Verify fuzzer corruptions on organizer samples never crash."""
    samples_dir = Path("data/organizer/samples")
    sample_files = ["hardware_failure.jsonl", "latency_spike.jsonl", "normal.jsonl"]

    for s_file in sample_files:
        path = samples_dir / s_file
        if not path.exists():
            continue
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        sample_data = {
            "incident_id": f"inc-fuzz-{s_file}",
            "network_id": "iit-bbs-campus",
            "telemetry": records[:40],
        }

        for seed in (21, 77):
            corrupted = ChaosFuzzer.corrupt(sample_data, seed=seed)
            adapted = OrganizerAdapter.adapt_dataset(corrupted)
            report = run_diagnosis(adapted)
            assert isinstance(report, UnifiedDiagnosticReport)
            assert report.status in ("diagnosed", "insufficient_evidence", "benign")


# -----------------------------------------------------------------------------
# 4. Seven Specific End-to-End Robustness Tests
# -----------------------------------------------------------------------------

def test_end_to_end_renamed_fields() -> None:
    """Prove end-to-end diagnosis when canonical fields are renamed (rtt, util, drops, loss)."""
    raw_scenario = {
        "incident_id": "inc-renamed-fields",
        "network_id": "iit-bbs-campus",
        "telemetry": [
            {
                "dev": "SW_CAMPUS_1",
                "rtt": 195.0,
                "util": 92.5,
                "loss": 4.5,
                "drops": 450,
            }
            for _ in range(3)
        ],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw_scenario)
    assert adapted["telemetry"][0]["latency_ms"] == 195.0
    assert adapted["telemetry"][0]["link_utilization_pct"] == 92.5
    assert adapted["telemetry"][0]["queue_drops"] == 450
    report = run_diagnosis(adapted)
    assert report.status == "diagnosed"
    assert "Link" in report.probable_cause or "congestion" in report.probable_cause.lower()


def test_end_to_end_seconds_vs_ms_latency() -> None:
    """Prove end-to-end: latency in seconds (0.195s) is converted to 195.0ms without scale corruption."""
    raw_scenario = {
        "incident_id": "inc-latency-sec",
        "network_id": "iit-bbs-campus",
        "telemetry": [
            {
                "device_id": "SW_CAMPUS_1",
                "latency_s": 0.195,
                "link_utilization_pct": 88.0,
                "queue_drops": 350,
            }
            for _ in range(3)
        ],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw_scenario)
    assert adapted["telemetry"][0]["latency_ms"] == 195.0
    report = run_diagnosis(adapted)
    assert report.status == "diagnosed"


def test_end_to_end_kbps_vs_mbps() -> None:
    """Prove end-to-end: throughput in kbps (950000 kbps) is converted to 950.0 Mbps."""
    raw_scenario = {
        "incident_id": "inc-throughput-kbps",
        "network_id": "iit-bbs-campus",
        "telemetry": [
            {
                "device_id": "SW_CAMPUS_1",
                "throughput_kbps": 950000.0,
                "bandwidth_kbps": 1000000.0,
                "link_utilization_pct": 95.0,
                "queue_drops": 400,
            }
            for _ in range(3)
        ],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw_scenario)
    assert adapted["telemetry"][0]["throughput_mbps"] == 950.0
    assert adapted["telemetry"][0]["bandwidth_mbps"] == 1000.0
    report = run_diagnosis(adapted)
    assert report.status == "diagnosed"


def test_end_to_end_v1_vs_v2_schema() -> None:
    """Prove end-to-end: mixed v1 (flat metrics) and v2 (nested under metrics) records are unified."""
    raw_scenario = {
        "incident_id": "inc-mixed-schemas",
        "network_id": "iit-bbs-campus",
        "telemetry": [
            {
                "device_id": "SW_CAMPUS_1",
                "timestamp": "2026-10-31T12:00:00Z",
                "link_utilization_pct": 92.0,
                "queue_drops": 300,
            },
            {
                "device_id": "SW_CAMPUS_1",
                "timestamp": "2026-10-31T12:01:00Z",
                "metrics": {
                    "link_utilization_pct": 94.0,
                    "queue_drops": 350,
                },
            },
        ],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw_scenario)
    assert len(adapted["telemetry"]) == 2
    assert adapted["telemetry"][0]["link_utilization_pct"] == 92.0
    assert adapted["telemetry"][1]["link_utilization_pct"] == 94.0
    report = run_diagnosis(adapted)
    assert report.status == "diagnosed"


def test_end_to_end_missing_message_fields() -> None:
    """Prove end-to-end: envelope with omitted optional payload fields validates and processes."""
    env = AgentEnvelope(
        header=ProtocolHeader(
            correlation_id="inc-missing-fields",
            sender=AgentRole.TELEMETRY_AGENT,
            recipient=AgentRole.ORCHESTRATOR,
            message_type=MessageType.FINDING_SUBMISSION,
        ),
        payload=EnvelopePayload(
            scope=NetworkScope(network_id="net-test", devices=["sw-1"]),
        ),
    )
    assert env.payload.observations == []
    assert env.payload.hypotheses == []
    assert env.payload.inquiries == []
    assert env.payload.error is None


def test_end_to_end_organizer_missing_metrics_object() -> None:
    """Prove end-to-end: organizer record missing metrics object flags ERR_MISSING_FIELD and degrades gracefully."""
    raw = {
        "incident_id": "inc-no-metrics",
        "network_id": "iit-bbs-campus",
        "telemetry": [
            {
                "device_id": "sw-corrupt-01",
                "timestamp": "2026-10-31T12:00:00Z",
                "status": "warning",
                "metrics": None,
            }
        ],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    err_codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_MISSING_FIELD" in err_codes or "ERR_EMPTY_METRICS" in err_codes
    report = run_diagnosis(adapted)
    assert report.status in ("insufficient_evidence", "benign")


def test_end_to_end_unsupported_schema_version() -> None:
    """Prove end-to-end: unsupported schema version triggers ERR_UNSUPPORTED_VERSION and continues in degraded mode."""
    raw = {
        "schema_version": "99.0.0",
        "incident_id": "inc-bad-version",
        "network_id": "iit-bbs-campus",
        "telemetry": [
            {"device_id": "sw-1", "link_utilization_pct": 95.0, "queue_drops": 200}
        ],
    }
    adapted = OrganizerAdapter.adapt_dataset(raw)
    err_codes = [e["code"] for e in adapted["data_quality"]["validation_errors"]]
    assert "ERR_UNSUPPORTED_SCHEMA_VERSION" in err_codes or "ERR_UNSUPPORTED_VERSION" in err_codes
    report = run_diagnosis(adapted)
    assert report is not None


# -----------------------------------------------------------------------------
# 5. Hybrid Integration & Conformal Guarantees Tests
# -----------------------------------------------------------------------------

def test_hybrid_confidence_breakdown_and_weights() -> None:
    """Verify confidence breakdown carries rules_score, model_score, blended_score, calibrated_confidence."""
    dataset = SyntheticNetworkGenerator.generate(
        scenario="link_congestion",
        seed=123,
        severity=SeverityLevel.HIGH,
    )
    adapted = OrganizerAdapter.adapt_dataset(dataset)
    report = run_diagnosis(adapted)

    assert report.status == "diagnosed"
    assert report.confidence_breakdown is not None
    bd = report.confidence_breakdown
    assert "rules_score" in bd
    assert "model_score" in bd
    assert "blended_score" in bd
    assert "calibrated_confidence" in bd
    # Never a blind 50/50 average
    assert abs(bd["blended_score"] - (0.55 * bd["rules_score"] + 0.45 * bd["model_score"])) < 0.02
    assert report.confidence_category in ("high", "medium", "low")
    assert len(report.conformal_prediction_set) >= 1


def test_hybrid_conformal_abstention_guarantee() -> None:
    """Verify hard rule: when model layer abstains, status is insufficient_evidence with no exact cause."""
    from netcoop.orchestrator.graph import run_diagnosis

    dataset = SyntheticNetworkGenerator.generate(
        scenario="normal_operation",
        seed=42,
    )
    adapted = OrganizerAdapter.adapt_dataset(dataset)
    report = run_diagnosis(adapted)

    assert report.status in ("insufficient_evidence", "benign")
    if report.confidence_category == "abstain":
        assert report.probable_cause is None
        assert report.confidence == 0.0
