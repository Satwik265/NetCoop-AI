"""Unit and contract validation tests for the held-out telemetry generator."""

import json
import subprocess
import sys
from pathlib import Path
import jsonschema
import pytest

from netcoop.data.heldout_generator import HeldoutTelemetryGenerator

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
TELEMETRY_SCHEMA_PATH = SCHEMAS_DIR / "telemetry.json"


@pytest.fixture(scope="module")
def telemetry_schema():
    """Load canonical telemetry schema."""
    with open(TELEMETRY_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_heldout_generator_schema_validation(telemetry_schema):
    """Test that generated scenario datasets validate against canonical telemetry JSON schema."""
    generator = HeldoutTelemetryGenerator(seed=101)
    dataset = generator.generate_scenario("link_congestion", duration_seconds=120, step_seconds=15)

    # Validate against JSON schema
    jsonschema.validate(instance=dataset, schema=telemetry_schema)
    assert dataset["incident_id"] == "inc-link-congestion-101"
    assert dataset["network_id"] == "iit-bbs-campus-fabric"
    assert len(dataset["topology"]["nodes"]) > 0
    assert len(dataset["topology"]["links"]) > 0
    assert len(dataset["telemetry"]) > 0


def test_heldout_generator_determinism():
    """Test that the same seed produces identical output and different seeds produce variance."""
    gen1 = HeldoutTelemetryGenerator(seed=777)
    gen2 = HeldoutTelemetryGenerator(seed=777)
    gen3 = HeldoutTelemetryGenerator(seed=888)

    data1 = gen1.generate_scenario("weak_wifi_signal", duration_seconds=90, step_seconds=15)
    data2 = gen2.generate_scenario("weak_wifi_signal", duration_seconds=90, step_seconds=15)
    data3 = gen3.generate_scenario("weak_wifi_signal", duration_seconds=90, step_seconds=15)

    assert data1 == data2, "Identical seeds must produce deterministic identical output"
    assert data1 != data3, "Different seeds must produce different telemetry samples"


@pytest.mark.parametrize("scenario_name", HeldoutTelemetryGenerator.SUPPORTED_SCENARIOS)
def test_every_scenario_name_produces_data(scenario_name, telemetry_schema):
    """Verify that every supported scenario name produces valid data conforming to schema."""
    generator = HeldoutTelemetryGenerator(seed=42)
    dataset = generator.generate_scenario(scenario_name, duration_seconds=60, step_seconds=20)

    # Must validate schema
    jsonschema.validate(instance=dataset, schema=telemetry_schema)

    # Must produce non-empty components
    assert len(dataset["topology"]["nodes"]) >= 6
    assert len(dataset["topology"]["links"]) >= 6
    assert len(dataset["telemetry"]) > 0
    assert "bgp_sessions" in dataset["routing_state"]
    assert "stp_state" in dataset["routing_state"]


def test_heldout_cli_invocation(tmp_path, telemetry_schema):
    """Test CLI execution: python -m netcoop.data.heldout_generator --scenario link_congestion --seed 7 --out file.json."""
    out_file = tmp_path / "cli_output.json"
    cmd = [
        sys.executable,
        "-m",
        "netcoop.data.heldout_generator",
        "--scenario",
        "link_congestion",
        "--seed",
        "7",
        "--out",
        str(out_file),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"CLI command failed: {result.stderr}"
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    jsonschema.validate(instance=data, schema=telemetry_schema)
    assert data["incident_id"] == "inc-link-congestion-7"


def test_heldout_generator_statistical_properties():
    """Verify statistical heavy-tailed properties and metric variations."""
    generator = HeldoutTelemetryGenerator(seed=999)
    dataset = generator.generate_scenario("device_cpu_overload", duration_seconds=180, step_seconds=10)

    cpu_values = [
        record["value"]
        for record in dataset["telemetry"]
        if record["device"] == "spine-01" and record["metric"] == "cpu_pct"
    ]

    assert len(cpu_values) > 0
    # Over time, CPU should exhibit elevated values due to fault onset
    max_cpu = max(cpu_values)
    min_cpu = min(cpu_values)
    assert max_cpu > min_cpu, "Values must exhibit dynamic variance"
    assert max_cpu >= 80.0, "CPU overload scenario must reach high threshold on spine-01"

