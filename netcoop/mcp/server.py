import os
"""Model Context Protocol (MCP) server exposing NetCoop AI diagnostic and remediation tools."""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

from netcoop.config import settings
from gateway.adapters.organizer_adapter import OrganizerAdapter
from netcoop.orchestrator.graph import pause_diagnosis, resume_diagnosis, run_diagnosis
from netcoop.remediation.actions import RemediationCatalog
from netcoop.remediation.engine import RemediationEngine
from netcoop.storage.db import (
    get_envelope_logs,
    get_incident,
    init_db,
    list_incidents,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = BASE_DIR / "data" / "scenarios"
SAMPLES_DIR = BASE_DIR / "data" / "organizer" / "samples"
SCHEMAS_DIR = BASE_DIR / "schemas"


class NetCoopMCPServer:
    """Standard Model Context Protocol tool interface for external agentic assistants."""

    TOOLS_MANIFEST = [
        {
            "name": "get_telemetry",
            "description": "Fetch recent telemetry metrics window for a specified network device.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Target device identifier (e.g. 'spine-01' or 'SW_CAMPUS_1')",
                    },
                    "window": {
                        "type": "integer",
                        "description": "Number of recent telemetry points to retrieve (default 5)",
                        "default": 5,
                    },
                },
                "required": ["device_id"],
            },
        },
        {
            "name": "list_devices",
            "description": "List all active and known network devices across scenarios, organizer samples, and historical incidents.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_topology",
            "description": "Retrieve current network topology graph (nodes, links, and roles). Gracefully reports when unavailable.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "incident_id": {
                        "type": "string",
                        "description": "Optional incident ID to extract topology from",
                    },
                    "scenario": {
                        "type": "string",
                        "description": "Optional scenario filename to inspect",
                    },
                },
            },
        },
        {
            "name": "run_diagnosis",
            "description": "Execute end-to-end multi-agent diagnosis on a named scenario, organizer sample, or incident payload.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Scenario filename (e.g. 'link_congestion.json'), organizer sample ('normal.jsonl'), or inline JSON string",
                    },
                    "incident_data": {
                        "type": "object",
                        "description": "Optional inline JSON object conforming to telemetry schema",
                    },
                },
            },
        },
        {
            "name": "explain_finding",
            "description": "Provide a human-readable evidentiary explanation and metric attribution for a specific finding or hypothesis ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "finding_id": {
                        "type": "string",
                        "description": "Observation ID (e.g. 'obs-01'), hypothesis ID ('hyp-01'), or root cause key",
                    }
                },
                "required": ["finding_id"],
            },
        },
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
                    "action_type": {
                        "type": "string",
                        "description": "Optional action name: 'rebalance traffic', 'clear interface counters', 'raise QoS priority', 'fail over a link'",
                    },
                    "operator": {"type": "string", "default": "mcp_operator"},
                    "auth_token": {"type": "string", "description": "Bearer JWT token"},
                },
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
    def list_resources(cls) -> List[Dict[str, Any]]:
        """List available file resources for scenarios, organizer samples, and latest report."""
        resources: List[Dict[str, Any]] = []

        # Scenario files
        if SCENARIOS_DIR.exists():
            for f in sorted(SCENARIOS_DIR.glob("*.json")):
                resources.append({
                    "uri": f"scenario://{f.name}",
                    "name": f"Scenario: {f.stem}",
                    "mimeType": "application/json",
                    "description": f"Pre-configured benchmark scenario file {f.name}",
                })

        # Organizer samples
        if SAMPLES_DIR.exists():
            for f in sorted(SAMPLES_DIR.glob("*.jsonl")):
                resources.append({
                    "uri": f"organizer://{f.name}",
                    "name": f"Organizer Sample: {f.stem}",
                    "mimeType": "application/x-ndjson",
                    "description": f"Hackathon organizer Colab JSONL telemetry sample {f.name}",
                })

        # Latest report
        resources.append({
            "uri": "report://latest",
            "name": "Latest Diagnostic Report",
            "mimeType": "application/json",
            "description": "Most recently computed network diagnostic report from database",
        })

        return resources

    @classmethod
    def read_resource(cls, uri: str) -> Dict[str, Any]:
        """Read resource content by URI."""
        init_db()

        if uri.startswith("scenario://"):
            filename = uri[len("scenario://"):]
            path = SCENARIOS_DIR / filename
            if not path.exists():
                return {"isError": True, "message": f"Scenario '{filename}' not found."}
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "contents": [
                    {"uri": uri, "mimeType": "application/json", "text": content}
                ]
            }

        elif uri.startswith("organizer://"):
            filename = uri[len("organizer://"):]
            path = SAMPLES_DIR / filename
            if not path.exists():
                return {"isError": True, "message": f"Organizer sample '{filename}' not found."}
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "contents": [
                    {"uri": uri, "mimeType": "application/x-ndjson", "text": content}
                ]
            }

        elif uri == "report://latest" or uri.startswith("report://"):
            incidents = list_incidents()
            if not incidents or not incidents[0].report_json:
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps({"status": "no_reports_available"}),
                        }
                    ]
                }
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": incidents[0].report_json,
                    }
                ]
            }

        return {"isError": True, "message": f"Unknown resource URI scheme: '{uri}'"}

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
        if not getattr(settings, "feature_mcp", True):
            return {
                "isError": True,
                "content": [{"type": "text", "text": "FEATURE_MCP is disabled in configuration."}],
            }

        init_db()

        if name == "get_telemetry":
            dev_id = arguments.get("device_id", "")
            window = int(arguments.get("window", 5))
            records: List[Dict[str, Any]] = []

            # 1. Search recent incidents in database
            recent_incs = list_incidents()
            for inc in recent_incs[:5]:
                if inc.report_json:
                    rep = json.loads(inc.report_json)
                    for dev in rep.get("affected_devices", []):
                        if dev == dev_id:
                            records.append({
                                "source": "database_incident",
                                "incident_id": inc.incident_id,
                                "device": dev_id,
                                "status": inc.status,
                                "probable_cause": inc.probable_cause,
                                "confidence": inc.confidence,
                                "created_at": inc.created_at,
                            })

            # 2. Check scenario files if needed
            if len(records) < window and SCENARIOS_DIR.exists():
                for sc_path in sorted(SCENARIOS_DIR.glob("*.json")):
                    try:
                        with open(sc_path, "r", encoding="utf-8") as f:
                            sc_data = json.load(f)
                            for t in sc_data.get("telemetry", []):
                                if t.get("device") == dev_id:
                                    records.append(t)
                                    if len(records) >= window:
                                        break
                    except Exception:
                        continue
                    if len(records) >= window:
                        break

            # 3. Check organizer samples if needed
            if len(records) < window and SAMPLES_DIR.exists():
                for sm_path in sorted(SAMPLES_DIR.glob("*.jsonl")):
                    try:
                        with open(sm_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                r = json.loads(line)
                                if r.get("device_id") == dev_id:
                                    records.append(r)
                                    if len(records) >= window:
                                        break
                    except Exception:
                        continue
                    if len(records) >= window:
                        break

            if not records:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "device_id": dev_id,
                                    "records_found": 0,
                                    "message": f"No telemetry records found for device '{dev_id}'.",
                                    "telemetry": [],
                                },
                                indent=2,
                            ),
                        }
                    ]
                }

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "device_id": dev_id,
                                "window_requested": window,
                                "records_returned": len(records[:window]),
                                "telemetry": records[:window],
                            },
                            indent=2,
                        ),
                    }
                ]
            }

        elif name == "list_devices":
            devices = set()

            # Inspect scenarios
            if SCENARIOS_DIR.exists():
                for sc_path in SCENARIOS_DIR.glob("*.json"):
                    try:
                        with open(sc_path, "r", encoding="utf-8") as f:
                            sc_data = json.load(f)
                            for node in sc_data.get("topology", {}).get("nodes", []):
                                if isinstance(node, dict) and "id" in node:
                                    devices.add(node["id"])
                            for t in sc_data.get("telemetry", []):
                                if isinstance(t, dict) and "device" in t:
                                    devices.add(t["device"])
                    except Exception:
                        pass

            # Inspect organizer samples
            if SAMPLES_DIR.exists():
                for sm_path in SAMPLES_DIR.glob("*.jsonl"):
                    try:
                        with open(sm_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    r = json.loads(line)
                                    if "device_id" in r:
                                        devices.add(r["device_id"])
                    except Exception:
                        pass

            # Add default fallback devices if empty
            if not devices:
                devices = {"spine-01", "spine-02", "leaf-01", "leaf-02", "wan-01"}

            sorted_devices = sorted(list(devices))
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"total_devices": len(sorted_devices), "devices": sorted_devices},
                            indent=2,
                        ),
                    }
                ]
            }

        elif name == "get_topology":
            inc_id = arguments.get("incident_id")
            sc_name = arguments.get("scenario")

            topo: Optional[Dict[str, Any]] = None

            if sc_name:
                p = SCENARIOS_DIR / sc_name
                if not p.exists() and not sc_name.endswith(".json"):
                    p = SCENARIOS_DIR / f"{sc_name}.json"
                if p.exists():
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            sc_data = json.load(f)
                            topo = sc_data.get("topology")
                    except Exception:
                        pass

            if not topo and inc_id:
                rec = get_incident(inc_id)
                if rec and rec.report_json:
                    rep = json.loads(rec.report_json)
                    topo = rep.get("topology")

            if not topo:
                # Check default scenario
                def_p = SCENARIOS_DIR / "link_congestion.json"
                if def_p.exists():
                    try:
                        with open(def_p, "r", encoding="utf-8") as f:
                            sc_data = json.load(f)
                            topo = sc_data.get("topology")
                    except Exception:
                        pass

            if not topo or (not topo.get("nodes") and not topo.get("links")):
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "topology unavailable",
                                    "message": "Topology data unavailable for the requested context.",
                                    "nodes": [],
                                    "links": [],
                                },
                                indent=2,
                            ),
                        }
                    ]
                }

            return {"content": [{"type": "text", "text": json.dumps(topo, indent=2)}]}

        elif name in ("run_diagnosis", "diagnose_network"):
            target = arguments.get("target") or arguments.get("scenario") or arguments.get("incident_data")
            raw_data = None
            needs_adaptation = False

            if isinstance(target, dict):
                raw_data = target
                # If target has nested metrics or records, adapt it
                if "records" in raw_data or "metrics" in raw_data:
                    needs_adaptation = True
            elif isinstance(target, list):
                raw_data = target
                needs_adaptation = True
            elif isinstance(target, str):
                target_str = target.strip()
                # Check if it is a JSON string
                if target_str.startswith("{") or target_str.startswith("["):
                    try:
                        raw_data = json.loads(target_str)
                        if isinstance(raw_data, list) or "records" in raw_data or "metrics" in raw_data:
                            needs_adaptation = True
                    except Exception:
                        pass

                # Check if it is a scenario file
                if raw_data is None:
                    p = SCENARIOS_DIR / target_str
                    if not p.exists() and not target_str.endswith(".json"):
                        p = SCENARIOS_DIR / f"{target_str}.json"
                    if p.exists():
                        with open(p, "r", encoding="utf-8") as f:
                            raw_data = json.load(f)
                            needs_adaptation = False

                # Check if it is an organizer sample
                if raw_data is None:
                    sp = SAMPLES_DIR / target_str
                    if not sp.exists() and not target_str.endswith(".jsonl"):
                        sp = SAMPLES_DIR / f"{target_str}.jsonl"
                    if sp.exists():
                        records = []
                        with open(sp, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    records.append(json.loads(line))
                        raw_data = {"incident_id": f"inc-{sp.stem}", "records": records}
                        needs_adaptation = True

            if raw_data is None:
                def_p = SCENARIOS_DIR / "link_congestion.json"
                if def_p.exists():
                    with open(def_p, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                        needs_adaptation = False
                else:
                    return {
                        "isError": True,
                        "content": [{"type": "text", "text": f"Could not resolve target '{target}'."}],
                    }

            try:
                diag_input = OrganizerAdapter.adapt_dataset(raw_data) if needs_adaptation else raw_data
                report = run_diagnosis(diag_input)
                return {"content": [{"type": "text", "text": report.to_json()}]}
            except Exception as e:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Diagnosis failed: {str(e)}"}],
                }

        elif name == "explain_finding":
            finding_id = arguments.get("finding_id", "").strip()

            # 1. Search database envelope logs
            explanation: Dict[str, Any] = {
                "finding_id": finding_id,
                "found": False,
                "explanation": "",
                "severity": "unknown",
                "corroboration": [],
            }

            recent_incs = list_incidents()
            for inc in recent_incs:
                logs = get_envelope_logs(inc.incident_id)
                for l in logs:
                    try:
                        p_data = json.loads(l.payload_json)
                        for obs in p_data.get("observations", []):
                            if obs.get("observation_id") == finding_id:
                                explanation = {
                                    "finding_id": finding_id,
                                    "type": "observation",
                                    "found": True,
                                    "category": obs.get("category"),
                                    "entity": obs.get("entity"),
                                    "metric_name": obs.get("metric_name"),
                                    "observed_value": obs.get("observed_value"),
                                    "baseline_value": obs.get("baseline_value"),
                                    "severity": obs.get("severity"),
                                    "reported_by": l.sender,
                                    "incident_id": inc.incident_id,
                                    "explanation": f"Observed abnormal metric '{obs.get('metric_name')}' on {obs.get('entity')}: value {obs.get('observed_value')} (baseline: {obs.get('baseline_value')}). Severity: {obs.get('severity')}.",
                                }
                                return {"content": [{"type": "text", "text": json.dumps(explanation, indent=2)}]}

                        for hyp in p_data.get("hypotheses", []):
                            if hyp.get("hypothesis_id") == finding_id or hyp.get("probable_cause") == finding_id:
                                explanation = {
                                    "finding_id": finding_id,
                                    "type": "hypothesis",
                                    "found": True,
                                    "probable_cause": hyp.get("probable_cause"),
                                    "confidence": hyp.get("confidence"),
                                    "supporting_observation_ids": hyp.get("supporting_observation_ids"),
                                    "required_corroboration": hyp.get("required_corroboration"),
                                    "proposed_by": l.sender,
                                    "incident_id": inc.incident_id,
                                    "explanation": f"Hypothesis '{hyp.get('probable_cause')}' with confidence {hyp.get('confidence')}. Supported by {len(hyp.get('supporting_observation_ids', []))} observations.",
                                }
                                return {"content": [{"type": "text", "text": json.dumps(explanation, indent=2)}]}
                    except Exception:
                        continue

            # Standard semantic explanation fallback
            semantic_causes = {
                "INTERFACE_SATURATION_QUEUE_OVERFLOW": "Egress queue buffers overflowed due to high sustained traffic exceeding link bandwidth capacity, resulting in tail drops and rising latency.",
                "PHYSICAL_LAYER_CRC_DEGRADATION": "Frame check sequence errors and CRC cyclic redundancy failures indicating degraded physical cabling, loose connector, or faulty optical transceiver.",
                "MTU_MISMATCH_BLACKHOLE": "Large MTU frames (e.g. 9000 bytes) dropped silently on an intermediate link configured with smaller MTU (1500 bytes) when Don't Fragment (DF) bit is set.",
                "BGP_ROUTE_FLAP_DAMPING": "Frequent routing table updates and carrier flaps triggered exponential route flap dampening penalties, suppressing prefix reachability.",
                "OPTICAL_TRANSCEIVER_DEGRADATION": "Rx optical power dropped below minimum operational threshold causing bit errors and packet loss.",
                "STP_SPLIT_BRAIN_LOOP": "Misconfigured BPDU filter prevented spanning tree packet exchange, resulting in bridging loops and broadcast storm.",
                "link_congestion": "Bandwidth saturation on link resulting in queue drops and elevated latency.",
                "hardware_failure": "Control plane CPU exhaustion, 100% link utilization, and severe interface packet drops indicating physical switch hardware degradation.",
            }

            for k, exp in semantic_causes.items():
                if k.lower() in finding_id.lower() or finding_id.lower() in k.lower():
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "finding_id": finding_id,
                                        "found": True,
                                        "matched_cause_key": k,
                                        "explanation": exp,
                                        "status": "semantic_signature_lookup",
                                    },
                                    indent=2,
                                ),
                            }
                        ]
                    }

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "finding_id": finding_id,
                                "found": False,
                                "explanation": f"Finding identifier '{finding_id}' was not located in active envelope logs or standard fault dictionary.",
                            },
                            indent=2,
                        ),
                    }
                ]
            }

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
            act_type = arguments.get("action_type") or arguments.get("action")
            operator = arguments.get("operator", "mcp_operator")

            # Check if simulation on proposed action requested
            if act_type:
                target_data = None
                if inc_id:
                    rec = get_incident(inc_id)
                    if rec and rec.report_json:
                        target_data = json.loads(rec.report_json)
                if not target_data:
                    def_p = SCENARIOS_DIR / "link_congestion.json"
                    if def_p.exists():
                        with open(def_p, "r", encoding="utf-8") as f:
                            target_data = json.load(f)

                if target_data:
                    res = RemediationEngine.simulate_proposed_action(
                        scenario_data=target_data,
                        action_name=act_type,
                        operator=operator,
                    )
                    return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}

            if inc_id:
                rec = get_incident(inc_id)
                if not rec:
                    return {"isError": True, "content": [{"type": "text", "text": f"Incident '{inc_id}' not found."}]}
                report_data = json.loads(rec.report_json) if rec.report_json else {}
                actions = report_data.get("remediation_actions", [])
                target_act = next((a for a in actions if a.get("action_id") == act_id), None)
            else:
                target_act = None

            if not target_act:
                target_act = RemediationCatalog.create_rebalance_traffic_action("spine-01", "et-0/0/1").model_dump()

            from netcoop.core.report import RemediationActionItem
            action_item = RemediationActionItem(**target_act)
            result = RemediationEngine.execute_simulated_action(
                incident_id=inc_id or "inc-mcp-sim",
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
            schema_file = SCHEMAS_DIR / f"{schema_name}.json"
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
                elif method == "resources/list":
                    resources = cls.list_resources()
                    response = {"jsonrpc": "2.0", "id": req_id, "result": {"resources": resources}}
                elif method == "resources/read":
                    uri = params.get("uri", "")
                    res = cls.read_resource(uri)
                    response = {"jsonrpc": "2.0", "id": req_id, "result": res}
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
