# Model Context Protocol (MCP) Server Specification

The NetCoop AI platform implements a standard **Model Context Protocol (MCP)** server providing external AI coding assistants, IDE extensions (Claude Desktop, Cursor, VS Code, Antigravity), and autonomous agents direct access to network diagnostic, telemetry analysis, topology inspection, and simulated remediation capabilities.

---

## 1. Transport and Protocol Architecture

The NetCoop MCP server runs as a local stdio sub-process communicating via JSON-RPC 2.0. It exposes both dynamic tools (`tools/list`, `tools/call`) and static file resources (`resources/list`, `resources/read`).

- **Entrypoint**: `python -m netcoop.mcp.server` (or `python mcp_server/server.py`)
- **Protocol**: JSON-RPC 2.0 over standard input / output (`stdin` / `stdout`)
- **Zero-LLM Core**: All tools execute against local deterministic Python engines with zero external API dependencies.

---

## 2. MCP Tools Directory

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_telemetry` | `device_id` (str, required)<br/>`window` (int, default 5) | Retrieves the latest telemetry time-series metrics window for a specified network device. |
| `list_devices` | *(none)* | Enumerates all unique active and historical network devices across scenarios, organizer samples, and database logs. |
| `get_topology` | `incident_id` (str, optional)<br/>`scenario` (str, optional) | Returns the current network topology (nodes, links, and interface roles). Gracefully returns `"topology unavailable"` when missing. |
| `run_diagnosis` | `target` (str, optional)<br/>`incident_data` (obj, optional) | Executes complete multi-agent offline diagnosis on a named scenario (`link_congestion.json`), organizer sample (`normal.jsonl`), or inline telemetry. |
| `explain_finding` | `finding_id` (str, required) | Provides human-readable evidentiary explanations, metric attribution, and corroboration trails for an observation or hypothesis ID. |
| `diagnose_network` | `incident_data` (obj, required) | Direct programmatic entrypoint conforming to `schemas/telemetry.json`. |
| `get_incident_status` | `incident_id` (str, required) | Fetches persisted diagnostic report, confidence, and root cause from SQLite storage. |
| `get_envelope_trace` | `correlation_id` (str, required) | Retrieves complete auditable history of versioned inter-agent envelope messages. |
| `simulate_remediation` | `incident_id` (str, optional)<br/>`action_id` (str, optional)<br/>`action_type` (str, optional) | Simulates safe remediation in an isolated sandbox (`rebalance traffic`, `clear interface counters`, `raise QoS priority`, `fail over a link`). |
| `get_protocol_schema` | `schema_name` (str, required) | Inspects formal JSON schemas (`envelope`, `telemetry`, `diagnostic_report`, `remediation_plan`). |

---

## 3. MCP Resources Directory

The MCP server exposes static and live resources via standard `URI` patterns:

| Resource URI Scheme | MIME Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `scenario://{filename}` | `application/json` | Canonical ground-truth test scenario files | `scenario://link_congestion.json` |
| `organizer://{filename}` | `application/x-ndjson` | Hackathon organizer Colab JSONL telemetry samples | `organizer://normal.jsonl` |
| `report://latest` | `application/json` | Most recently computed network diagnostic report | `report://latest` |

---

## 4. Graceful Missing Topology Handling

When a scenario or external telemetry stream (such as the organizer's switch-only Colab format) does not contain explicit link or adjacency graphs, `get_topology` gracefully handles the absence without raising errors:

```json
{
  "status": "topology unavailable",
  "message": "Topology data unavailable for the requested context.",
  "nodes": [],
  "links": []
}
```

---

## 5. Client Configuration Snippet (Windows 11 / PowerShell)

Add the following configuration block to your MCP client configuration file (e.g., `claude_desktop_config.json`, Cursor MCP Settings, or Antigravity MCP Settings):

### Standard Virtual Environment Configuration

```json
{
  "mcpServers": {
    "netcoop": {
      "command": "D:\\NetCoop-AI\\Team_inSANE_MITRA_NetCoop-AI\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "netcoop.mcp.server"
      ],
      "cwd": "D:\\NetCoop-AI\\Team_inSANE_MITRA_NetCoop-AI",
      "env": {
        "PYTHONPATH": "D:\\NetCoop-AI\\Team_inSANE_MITRA_NetCoop-AI",
        "FEATURE_MCP": "true",
        "FEATURE_REMEDIATION_SIM": "true"
      }
    }
  }
}
```

### Relative Path Alternative (when running from repository root)

```json
{
  "mcpServers": {
    "netcoop": {
      "command": "python",
      "args": [
        "-m",
        "netcoop.mcp.server"
      ],
      "env": {
        "PYTHONPATH": ".",
        "FEATURE_MCP": "true",
        "FEATURE_REMEDIATION_SIM": "true"
      }
    }
  }
}
```

---

## 6. Testing MCP Server over stdio

You can test MCP JSON-RPC requests directly in PowerShell:

```powershell
# List available tools
'{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server

# Call list_devices tool
'{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_devices", "arguments": {}}}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server

# List resources
'{"jsonrpc": "2.0", "id": 3, "method": "resources/list"}' | .\.venv\Scripts\python.exe -m netcoop.mcp.server
```
