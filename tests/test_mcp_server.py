"""Tests for Model Context Protocol (MCP) server tools."""

import json
from pathlib import Path
from netcoop.mcp.server import NetCoopMCPServer

SCENARIO_PATH = Path(__file__).parent.parent / "data" / "scenarios" / "01_mtu_mismatch_blackhole.json"


def test_mcp_list_tools() -> None:
    """Verify tool discovery manifests tool list."""
    tools = NetCoopMCPServer.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "diagnose_network" in tool_names
    assert "get_incident_status" in tool_names
    assert "get_envelope_trace" in tool_names
    assert "simulate_remediation" in tool_names
    assert "get_protocol_schema" in tool_names


def test_mcp_diagnose_tool() -> None:
    """Verify diagnose_network MCP tool execution."""
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    res = NetCoopMCPServer.call_tool("diagnose_network", {"incident_data": data})
    assert "content" in res
    text = res["content"][0]["text"]
    report = json.loads(text)
    assert report["status"] == "diagnosed"
    assert "MTU" in report["probable_cause"]


def test_mcp_schema_tool() -> None:
    """Verify get_protocol_schema tool returns valid JSON schema."""
    res = NetCoopMCPServer.call_tool("get_protocol_schema", {"schema_name": "envelope"})
    assert "content" in res
    schema = json.loads(res["content"][0]["text"])
    assert schema["title"] == "AgentEnvelope"
