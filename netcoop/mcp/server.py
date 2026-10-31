import os
"""Model Context Protocol (MCP) server exposing NetCoop AI diagnostic and remediation tools."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from netcoop.orchestrator.graph import pause_diagnosis, resume_diagnosis, run_diagnosis
from netcoop.remediation.actions import RemediationCatalog
from netcoop.remediation.engine import RemediationEngine
from netcoop.storage.db import get_envelope_logs, get_incident, init_db, list_incidents


class NetCoopMCPServer:
    """Standard Model Context Protocol tool interface for external agentic assistants."""

    TOOLS_MANIFEST = [
        {
            "name": "diagnose_network",
            "description": "Trigger multi-agent offline network fault diagnosis on provided network topology and telemetry.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "incident_data": {
                        "type": "object",
                        "description": "JSON object conforming to schemas/telemetry.json",
                    },
                    "auth_token": {"type": "string", "description": "Bearer JWT token"},
                },
                "required": ["incident_data"],
            },
        },
        {
            "name": "get_incident_status",
            "description": "Retrieve persisted diagnostic report, confidence, and root cause for an incident ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string", "description": "Unique incident identifier"},
                    "auth_token": {"type": "string", "description": "Bearer JWT token"},
                },
                "required": ["incident_id"],
            },
        },
        {
            "name": "get_envelope_trace",
            "description": "Retrieve complete auditable trace of versioned inter-agent envelope messages.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "correlation_id": {"type": "string", "description": "Correlation identifier of incident"},
                    "auth_token": {"type": "string", "description": "Bearer JWT token"},
                },
                "required": ["correlation_id"],
            },
        },
        {
            "name": "simulate_remediation",
            "description": "Execute simulated safe remediation for an approved action in a sandbox environment.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "incident_id": {"type": "string"},
                    "action_id": {"type": "string"},
                    "operator": {"type": "string", "default": "mcp_operator"},
                    "auth_token": {"type": "string", "description": "Bearer JWT token"},
                },
                "required": ["incident_id", "action_id"],
            },
        },
        {
            "name": "pause_session",
            "description": "Pause an ongoing diagnostic session at its next checkpoint.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "auth_token": {"type": "string", "description": "Bearer JWT token"},
                },
                "required": ["session_id"],
            },
        },
        {
            "name": "resume_session",
            "description": "Resume an interrupted or paused diagnostic session from its latest checkpoint.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "auth_token": {"type": "string", "description": "Bearer JWT token"},
                },
                "required": ["session_id"],
            },
        },
        {
            "name": "get_protocol_schema",
            "description": "Inspect formal JSON schemas governing inter-agent envelope communication.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "schema_name": {
                        "type": "string",
                        "enum": ["envelope", "telemetry", "diagnostic_report", "remediation_plan"],
                    }
                },
                "required": ["schema_name"],
            },
        },
    ]

    @classmethod
    def list_tools(cls) -> List[Dict[str, Any]]:
        """Return the manifest of available tools."""
        return cls.TOOLS_MANIFEST

    @classmethod
    def _verify_auth(cls, arguments: Dict[str, Any], required_perm: str) -> Optional[Dict[str, Any]]:
        """Verify token and permissions for sensitive tools."""
        token = arguments.get("auth_token") or arguments.get("token") or os.getenv("NETCOOP_MCP_TOKEN")
        if not token:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unauthorized: Missing authentication token for sensitive tool. '{required_perm}' permission required."}],
            }
        try:
            from netcoop.core.auth import ROLE_PERMISSIONS_MAP, decode_access_token
            from netcoop.storage.db import get_user_by_username, is_token_revoked

            payload = decode_access_token(token)
            jti = payload.get("jti")
            if jti and is_token_revoked(jti):
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": "Unauthorized: Token has been revoked."}],
                }
            username = payload.get("sub")
            if not username:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": "Unauthorized: Invalid token payload."}],
                }
            user = get_user_by_username(username)
            if not user or not user.is_active:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": "Unauthorized: User account is inactive or not found."}],
                }
            perms = ROLE_PERMISSIONS_MAP.get(user.role, set())
            if required_perm not in perms:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Forbidden: User '{username}' with role '{user.role}' lacks '{required_perm}' permission."}],
                }
            return None
        except Exception as e:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unauthorized: {str(e)}"}],
            }

    @classmethod
    def call_tool(cls, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the specified tool by name."""
        init_db()

        if name == "diagnose_network":
            data = arguments.get("incident_data", {})
            report = run_diagnosis(data)
            return {"content": [{"type": "text", "text": report.to_json()}]}

        elif name == "get_incident_status":
            inc_id = arguments.get("incident_id", "")
            rec = get_incident(inc_id)
            if not rec:
                return {"isError": True, "content": [{"type": "text", "text": f"Incident '{inc_id}' not found."}]}
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "incident_id": rec.incident_id,
                                "network_id": rec.network_id,
                                "status": rec.status,
                                "probable_cause": rec.probable_cause,
                                "confidence": rec.confidence,
                                "report": json.loads(rec.report_json) if rec.report_json else None,
                            },
                            indent=2,
                        ),
                    }
                ]
            }

        elif name == "get_envelope_trace":
            corr_id = arguments.get("correlation_id", "")
            logs = get_envelope_logs(corr_id)
            trace = [
                {
                    "message_id": l.message_id,
                    "timestamp_utc": l.timestamp_utc,
                    "sender": l.sender,
                    "recipient": l.recipient,
                    "message_type": l.message_type,
                    "payload": json.loads(l.payload_json),
                }
                for l in logs
            ]
            return {"content": [{"type": "text", "text": json.dumps(trace, indent=2)}]}

        elif name == "simulate_remediation":
            from netcoop.core.auth import PERM_SIMULATE_REMEDIATION
            auth_err = cls._verify_auth(arguments, PERM_SIMULATE_REMEDIATION)
            if auth_err:
                return auth_err

            inc_id = arguments.get("incident_id", "")
            act_id = arguments.get("action_id", "")
            operator = arguments.get("operator", "mcp_operator")

            rec = get_incident(inc_id)
            if not rec:
                return {"isError": True, "content": [{"type": "text", "text": f"Incident '{inc_id}' not found."}]}

            report_data = json.loads(rec.report_json) if rec.report_json else {}
            actions = report_data.get("remediation_actions", [])
            target_act = next((a for a in actions if a.get("action_id") == act_id), None)

            if not target_act:
                target_act = RemediationCatalog.create_mtu_harmonization_action("spine-01", "et-0/0/1").model_dump()

            from netcoop.core.report import RemediationActionItem
            action_item = RemediationActionItem(**target_act)
            result = RemediationEngine.execute_simulated_action(
                incident_id=inc_id,
                action=action_item,
                operator=operator,
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "pause_session":
            from netcoop.core.auth import PERM_EXECUTE_DIAGNOSIS
            auth_err = cls._verify_auth(arguments, PERM_EXECUTE_DIAGNOSIS)
            if auth_err:
                return auth_err

            session_id = arguments.get("session_id", "")
            ok = pause_diagnosis(session_id)
            return {"content": [{"type": "text", "text": json.dumps({"session_id": session_id, "paused": ok})}]}

        elif name == "resume_session":
            from netcoop.core.auth import PERM_EXECUTE_DIAGNOSIS
            auth_err = cls._verify_auth(arguments, PERM_EXECUTE_DIAGNOSIS)
            if auth_err:
                return auth_err

            session_id = arguments.get("session_id", "")
            report = resume_diagnosis(session_id)
            return {"content": [{"type": "text", "text": report.to_json()}]}

        elif name == "get_protocol_schema":
            schema_name = arguments.get("schema_name", "envelope")
            schema_file = Path(__file__).parent.parent.parent / "schemas" / f"{schema_name}.json"
            if not schema_file.exists():
                return {"isError": True, "content": [{"type": "text", "text": f"Schema '{schema_name}' not found."}]}
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_content = json.load(f)
            return {"content": [{"type": "text", "text": json.dumps(schema_content, indent=2)}]}

        return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: '{name}'"}]}

    @classmethod
    def run_stdio_server(cls) -> None:
        """Run standard JSON-RPC 2.0 loop over stdin and stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                req_id = request.get("id")
                method = request.get("method")
                params = request.get("params", {})

                if method == "tools/list":
                    response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": cls.list_tools()}}
                elif method == "tools/call":
                    tool_name = params.get("name")
                    args = params.get("arguments", {})
                    tool_result = cls.call_tool(tool_name, args)
                    response = {"jsonrpc": "2.0", "id": req_id, "result": tool_result}
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method '{method}' not found"},
                    }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(e)},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    NetCoopMCPServer.run_stdio_server()
