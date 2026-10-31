"""Comprehensive test suite for MCP tools, remediation simulation, and network hard-blocking."""

import json
from pathlib import Path
import pytest
import socket
import subprocess

from netcoop.config import settings
from netcoop.mcp.server import NetCoopMCPServer
from netcoop.remediation.engine import (
    NetworkCallBlockedError,
    RemediationEngine,
    network_sandbox_guard,
)
from netcoop.remediation.actions import RemediationCatalog

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"


# ---------------------------------------------------------------------------
# 1. MCP Tools Verification
# ---------------------------------------------------------------------------

def test_mcp_tool_list_contains_all_required_tools() -> None:
    """Verify that all required MCP tools are registered in the manifest."""
    tools = NetCoopMCPServer.list_tools()
    tool_names = {t["name"] for t in tools}

    required_tools = {
        "get_telemetry",
        "list_devices",
        "get_topology",
        "run_diagnosis",
        "explain_finding",
        "diagnose_network",
        "get_incident_status",
        "get_envelope_trace",
        "simulate_remediation",
        "get_protocol_schema",
    }
    assert required_tools.issubset(tool_names)


def test_mcp_list_devices() -> None:
    """Verify list_devices returns non-empty list of unique network nodes."""
    res = NetCoopMCPServer.call_tool("list_devices", {})
    assert not res.get("isError")
    content = json.loads(res["content"][0]["text"])
    assert "devices" in content
    assert len(content["devices"]) > 0
    assert any("spine" in d or "SW_CAMPUS" in d or "leaf" in d or "core" in d for d in content["devices"])


def test_mcp_get_telemetry() -> None:
    """Verify get_telemetry retrieves requested window of metrics for a device."""
    res = NetCoopMCPServer.call_tool("get_telemetry", {"device_id": "core-rtr-01", "window": 3})
    assert not res.get("isError")
    content = json.loads(res["content"][0]["text"])
    assert content["device_id"] == "core-rtr-01"
    assert "telemetry" in content
    assert len(content["telemetry"]) <= 3


def test_mcp_get_topology_with_scenario() -> None:
    """Verify get_topology retrieves node/link topology for a named scenario."""
    res = NetCoopMCPServer.call_tool("get_topology", {"scenario": "link_congestion.json"})
    assert not res.get("isError")
    topo = json.loads(res["content"][0]["text"])
    assert "nodes" in topo
    assert "links" in topo


def test_mcp_get_topology_graceful_missing() -> None:
    """Verify get_topology returns 'topology unavailable' when no topology exists."""
    res = NetCoopMCPServer.call_tool("get_topology", {"scenario": "nonexistent_scenario.json"})
    assert not res.get("isError")
    content = json.loads(res["content"][0]["text"])
    assert content.get("status") == "topology unavailable" or "nodes" in content


def test_mcp_run_diagnosis_with_scenario_name() -> None:
    """Verify run_diagnosis resolves scenario name and returns diagnosed report."""
    res = NetCoopMCPServer.call_tool("run_diagnosis", {"target": "link_congestion.json"})
    assert not res.get("isError")
    report = json.loads(res["content"][0]["text"])
    assert report["status"] in ("diagnosed", "insufficient_evidence")
    assert "probable_cause" in report


def test_mcp_run_diagnosis_with_organizer_sample() -> None:
    """Verify run_diagnosis adapts organizer JSONL sample and executes diagnosis."""
    res = NetCoopMCPServer.call_tool("run_diagnosis", {"target": "hardware_failure.jsonl"})
    assert not res.get("isError")
    report = json.loads(res["content"][0]["text"])
    assert "probable_cause" in report


def test_mcp_explain_finding_semantic_lookup() -> None:
    """Verify explain_finding explains standard fault signature."""
    res = NetCoopMCPServer.call_tool(
        "explain_finding", {"finding_id": "INTERFACE_SATURATION_QUEUE_OVERFLOW"}
    )
    assert not res.get("isError")
    content = json.loads(res["content"][0]["text"])
    assert content["found"] is True
    assert "buffer" in content["explanation"].lower() or "queue" in content["explanation"].lower()


# ---------------------------------------------------------------------------
# 2. MCP Resources Verification
# ---------------------------------------------------------------------------

def test_mcp_resources_list() -> None:
    """Verify resource discovery includes scenarios, organizer samples, and latest report."""
    resources = NetCoopMCPServer.list_resources()
    uris = {r["uri"] for r in resources}
    assert any(u.startswith("scenario://") for u in uris)
    assert any(u.startswith("organizer://") for u in uris)
    assert "report://latest" in uris


def test_mcp_resources_read_scenario() -> None:
    """Verify reading a scenario resource returns valid JSON text."""
    res = NetCoopMCPServer.read_resource("scenario://link_congestion.json")
    assert not res.get("isError")
    text = res["contents"][0]["text"]
    data = json.loads(text)
    assert "telemetry" in data


def test_mcp_resources_read_organizer_sample() -> None:
    """Verify reading an organizer resource returns JSONL text."""
    res = NetCoopMCPServer.read_resource("organizer://normal.jsonl")
    assert not res.get("isError")
    text = res["contents"][0]["text"]
    first_line = text.strip().split("\n")[0]
    data = json.loads(first_line)
    assert "metrics" in data


# ---------------------------------------------------------------------------
# 3. Remediation Simulation & Before/After Metrics
# ---------------------------------------------------------------------------

def test_remediation_simulation_rebalance_traffic() -> None:
    """Verify rebalance traffic reduces link utilization and clears queue drops."""
    scenario_path = SCENARIOS_DIR / "link_congestion.json"
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    res = RemediationEngine.simulate_proposed_action(
        scenario_data=data,
        action_name="rebalance traffic",
        device="dist-sw-core",
        interface="et-0/0/1",
    )
    assert res["status"] == "success"
    assert res["disclaimer"] == "Simulated, no production changes"
    assert res["is_simulated"] is True
    assert res["target_device"] == "dist-sw-core"

    target_before = res["target_before_metrics"]
    target_after = res["target_after_metrics"]
    target_delta = res["target_delta"]

    # Target device link utilization must drop
    assert target_after["max_link_utilization_pct"] < target_before["max_link_utilization_pct"]
    assert target_delta["max_link_utilization_pct"] < 0
    # Queue drops must clear to zero
    assert target_after.get("max_queue_drops", 0) == 0.0


def test_remediation_simulation_clear_counters() -> None:
    """Verify clear interface counters resets CRC and error counters to 0."""
    scenario_path = SCENARIOS_DIR / "ethernet_interface_fault.json"
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    res = RemediationEngine.simulate_proposed_action(
        scenario_data=data,
        action_name="clear interface counters",
        device="dept-sw-cs-01",
        interface="et-0/0/1",
    )
    assert res["status"] == "success"
    assert res["disclaimer"] == "Simulated, no production changes"
    target_after = res["target_after_metrics"]
    assert target_after.get("max_interface_errors", 0.0) == 0.0
    assert res["after_metrics"].get("max_interface_errors", 0.0) == 0.0


def test_remediation_simulation_raise_qos() -> None:
    """Verify raise QoS priority drops latency and jitter."""
    scenario_path = SCENARIOS_DIR / "link_congestion.json"
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    res = RemediationEngine.simulate_proposed_action(
        scenario_data=data,
        action_name="raise QoS priority",
        device="dist-sw-core",
        interface="et-0/0/1",
    )
    assert res["status"] == "success"
    assert res["disclaimer"] == "Simulated, no production changes"
    target_after = res["target_after_metrics"]
    assert target_after.get("max_latency_ms", 999.0) <= 20.0
    assert target_after.get("max_jitter_ms", 999.0) <= 5.0


def test_remediation_simulation_failover_link() -> None:
    """Verify fail over a link drops primary utilization to 0 and transfers to peer."""
    scenario_path = SCENARIOS_DIR / "link_congestion.json"
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    res = RemediationEngine.simulate_proposed_action(
        scenario_data=data,
        action_name="fail over a link",
        device="core-rtr-01",
        interface="et-0/0/1",
        peer_device="dist-sw-core",
    )
    assert res["status"] == "success"
    assert res["disclaimer"] == "Simulated, no production changes"
    target_after = res["target_after_metrics"]
    assert target_after.get("max_link_utilization_pct", 999.0) == 0.0


# ---------------------------------------------------------------------------
# 4. Hard-Block Safety Verification (No Sockets / No Subprocess to Network Tools)
# ---------------------------------------------------------------------------

def test_hard_block_socket_connect() -> None:
    """Verify network socket connection is hard-blocked inside the simulation sandbox."""
    with network_sandbox_guard():
        with pytest.raises((NetworkCallBlockedError, PermissionError)) as exc_info:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("8.8.8.8", 53))
        assert "hard-blocked" in str(exc_info.value)
        assert "Simulated, no production changes" in str(exc_info.value)


def test_hard_block_socket_bind() -> None:
    """Verify network socket binding is hard-blocked inside the simulation sandbox."""
    with network_sandbox_guard():
        with pytest.raises((NetworkCallBlockedError, PermissionError)) as exc_info:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 59999))
        assert "hard-blocked" in str(exc_info.value)


def test_hard_block_subprocess_ping() -> None:
    """Verify subprocess invocation of 'ping' is hard-blocked inside the simulation sandbox."""
    with network_sandbox_guard():
        with pytest.raises((NetworkCallBlockedError, PermissionError)) as exc_info:
            subprocess.Popen(["ping", "127.0.0.1"])
        assert "hard-blocked" in str(exc_info.value)


def test_hard_block_subprocess_curl() -> None:
    """Verify subprocess invocation of 'curl' is hard-blocked inside the simulation sandbox."""
    with network_sandbox_guard():
        with pytest.raises((NetworkCallBlockedError, PermissionError)) as exc_info:
            subprocess.Popen(["curl", "http://127.0.0.1:8000"])
        assert "hard-blocked" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. Feature Flags Verification
# ---------------------------------------------------------------------------

def test_feature_mcp_flag_disables_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify FEATURE_MCP=False refuses tool execution."""
    monkeypatch.setattr(settings, "feature_mcp", False)
    res = NetCoopMCPServer.call_tool("list_devices", {})
    assert res.get("isError") is True
    assert "FEATURE_MCP is disabled" in res["content"][0]["text"]


def test_feature_remediation_sim_flag_disables_sim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify FEATURE_REMEDIATION_SIM=False blocks simulation."""
    monkeypatch.setattr(settings, "feature_remediation_sim", False)
    scenario_path = SCENARIOS_DIR / "link_congestion.json"
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    with pytest.raises(RuntimeError) as exc_info:
        RemediationEngine.simulate_proposed_action(
            scenario_data=data,
            action_name="rebalance traffic",
        )
    assert "FEATURE_REMEDIATION_SIM is disabled" in str(exc_info.value)
