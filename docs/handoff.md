# NetCoop AI: Developer Handoff and Integration Guide

This guide contains everything Member B (Specialist Agents & Gateway) and Member C (UI & Testing) need to know to develop, run, test, and integrate with the NetCoop AI platform.

---

## 1. Environment Setup (Windows 11 / PowerShell)

The project runs on Python 3.13 inside a local virtual environment (`.venv`). Bash-only syntax is prohibited; all scripts and commands must work natively in PowerShell.

### 1.1 First-Time Setup

In PowerShell from the repository root (`c:\Users\Admin\Desktop\Team_inSANE_MITRA_NetCoop-AI`):

```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Upgrade pip and install package in editable mode with development dependencies
python -m pip install --upgrade pip
pip install -e .
pip install pytest hypothesis rich typer uvicorn fastapi sqlmodel httpx websockets

# 3. Verify test suite
pytest tests/ -v
```

### 1.2 Plain Python Equivalents for Makefile Targets

All `make` targets defined in `Makefile` have exact plain `python` / PowerShell equivalents:

| Makefile Target | Action | Plain Python / PowerShell Equivalent |
| :--- | :--- | :--- |
| `make setup` | Setup dependencies and dashboard | `pip install -e .`<br/>`cd dashboard; npm install; cd ..` |
| `make up` | Start all agent microservices (daemon) | `python scripts/run_agents.py` |
| `make down` | Cleanly terminate all running agent processes | `python scripts/run_agents.py --stop` |
| `make demo` | Run 3-scenario end-to-end demo with trace and reports | `python scripts/demo.py` |
| `make demo-organizer` | Ingest organizer's Colab JSONL telemetry through gateway | `python scripts/demo_organizer.py` |
| `make test` | Run complete unit and property tests | `pytest tests/ -v` |
| `make eval` | Run 19-scenario accuracy evaluation benchmark | `python scripts/eval_benchmark.py` |
| `make assets` | Build frontend production bundle | `cd dashboard; npm run build; cd ..` |
| `make run` | Start FastAPI backend server on port 8000 | `uvicorn netcoop.main:app --host 127.0.0.1 --port 8000 --reload` |
| `make clean` | Terminate agents and remove temp caches | `python scripts/run_agents.py --stop`<br/>`Get-ChildItem -Recurse -Include __pycache__,.pytest_cache | Remove-Item -Recurse -Force` |

---

## 2. Process Architecture and Agent Registry

The system employs a strict shared-nothing architecture. Specialist agents run as decoupled OS processes communicating exclusively over HTTP loopback endpoints:

```
                          +------------------------+
                          |   Ingestion Gateway    | :8006
                          |  POST /ingest          |
                          +-----------+------------+
                                      | Normalized Incident
                                      v
+------------------+      +------------------------+
| React Dashboard  | <--- |   Orchestrator & API   | :8000
| (WS /ws/events)  |      |   (LangGraph Mediator) |
+------------------+      +-----------+------------+
                                      |
       +-----------------+------------+------------+-----------------+
       | :8001           | :8002                   | :8003           | :8004
       v                 v                         v                 v
+--------------+  +--------------+          +--------------+  +--------------+
|  Telemetry   |  |   Topology   |          |    Config    |  |     Log      |
|    Agent     |  |    Agent     |          |    Agent     |  |    Agent     |
+--------------+  +--------------+          +--------------+  +--------------+
                                      |
                                      | :8005
                                      v
                               +--------------+
                               | Synthesizer  |
                               |    Agent     |
                               +--------------+
```

### 2.1 Microservice Directory

| Subsystem | Port | Base URL | Endpoints | Health Check |
| :--- | :---: | :--- | :--- | :--- |
| **Orchestrator & API** | **8000** | `http://127.0.0.1:8000` | `POST /api/diagnose`<br/>`POST /api/ingest`<br/>`GET /api/incidents`<br/>`WS /ws/events`<br/>`WS /ws/envelopes` | `GET /api/health` |
| **Telemetry Agent** | **8001** | `http://127.0.0.1:8001` | `POST /process` | `GET /health` |
| **Topology Agent** | **8002** | `http://127.0.0.1:8002` | `POST /process` | `GET /health` |
| **Config Agent** | **8003** | `http://127.0.0.1:8003` | `POST /process` | `GET /health` |
| **Log Agent** | **8004** | `http://127.0.0.1:8004` | `POST /process` | `GET /health` |
| **Synthesizer Agent** | **8005** | `http://127.0.0.1:8005` | `POST /process` | `GET /health` |
| **Ingestion Gateway** | **8006** | `http://127.0.0.1:8006` | `POST /ingest` | `GET /health` |
| **Classifier Agent** | **8007** | `http://127.0.0.1:8007` | `POST /process` | `GET /health` |
| **Wi-Fi & Services Agent** | **8008** | `http://127.0.0.1:8008` | `POST /process` | `GET /health` |

### 2.2 Microservice Process Isolation & Degraded Mode
- **Process Isolation**: Each specialist agent and gateway runs as a distinct OS process (FastAPI application launched with Uvicorn), bound to loopback `127.0.0.1:<port>`. Communication occurs strictly over HTTP with JSON-serialized `AgentEnvelope` models.
- **Fail-Closed Degraded Mode**: `in_process_fallback = False` is enforced. Unreachable agent microservices trip the circuit breaker and enter degraded mode, recording an explicit audit trail entry in report limitations (`agent_unavailable: <role> process unreachable; continued in degraded mode`), never silently executing in-process substitutes.
- **Gateway HTTP Microservice Dispatch**: Ingestion endpoints (`/api/ingest` and `/api/diagnose`) forward requests over HTTP to the Gateway microservice on port 8006 (`POST /ingest`). If the Gateway service is down, the API returns HTTP 503 Service Unavailable with an actionable error message rather than silently using an in-process adapter.
- **Process Supervision**: `scripts/run_agents.py` supervises processes, tracks PIDs in `.agents.pid`, polls health endpoints concurrently, and handles graceful teardown via `terminate_pid`.
- **Docker Compose Topology**: `docker-compose.yml` declares all 8 microservices plus orchestrator with healthchecks, non-root loopback overrides, and `service_healthy` dependency conditions.

---

## 3. Authoritative Code Structure and Logical Path Mapping

Code resides in both top-level modules and the `netcoop/` package. The authoritative locations are:

| Subsystem | Authoritative Path | Logical Path | Description |
| :--- | :--- | :--- | :--- |
| **Specialist Agents** | `netcoop/agents/` | `/agents` | Telemetry, Topology, Config, Log, Synthesizer |
| **Classifier Models** | `netcoop/agents/classifier/` | `/agents/classifier` | Classifier components |
| **Core Protocol** | `netcoop/core/` | `/core` | Envelopes, normalizer, scoring, report builder |
| **Models** | `netcoop/models/` | `/models` | Domain models |
| **Orchestrator** | `netcoop/orchestrator/` | `/orchestrator` | LangGraph state machine, mediator, conflict resolver |
| **Remediation** | `netcoop/remediation/` | `/sandbox` | Safety gates, action catalog, rollback plans |
| **Storage** | `netcoop/storage/` | `/storage` | SQLite event log and incident persistence |
| **LLM Bridge** | `netcoop/llm/` | `/llm` | Offline-safe Gemini integration |
| **MCP Server** | `netcoop/mcp/` & `mcp_server/` | `/mcp_server` | FastMCP stdio server |
| **Gateway** | `gateway/` | `/gateway` | Ingestion microservice and organizer format adapters |
| **Telemetry Generator** | `netcoop/data/` & `data/` | Generator code | `generator.py`, `heldout_generator.py` in `netcoop/data/`; scenarios in `data/scenarios/` |
| **Evaluation** | `eval/` & `scripts/` | `/eval` | Benchmark runner in `scripts/`, results in `eval/results/` |
| **Dashboard** | `dashboard/` | `/dashboard` | React + TypeScript + Tailwind monochrome UI |
| **CLI** | `netcoop/cli.py` & `cli/main.py` | `/cli` | Rich Typer CLI (`netcoop` command) |
| **Tests** | `tests/` | `/tests` | Comprehensive pytest test suite |
| **Schemas** | `schemas/` | `/schemas` | Formal JSON Schemas (envelope, telemetry, report) |
| **Docs** | `docs/` | `/docs` | Technical architecture, protocol, and guides |

> [!NOTE]
> Top-level folders (`agents/`, `core/`, `orchestrator/`, etc.) exist as facade bridges to support backward compatibility. Always implement new domain logic inside `netcoop/`.

---

## 4. Message Envelope Contract Mapping

The existing message envelope (`AgentEnvelope` in `netcoop/core/envelope.py`) is authoritative and binding:
- `payload.scope`: contains `network_id`, `devices`, `interfaces`.
- `payload.observations`: empirical findings from specialist agents.
- `payload.hypotheses`: proposed fault diagnoses with confidence scores.
- `payload.inquiries`: targeted questions for corroboration (`evidence_query = inquiries`).
- `context.iteration`: round counter for multi-turn debate/conflict resolution managed by the mediator.
- Extensions are strictly **additive** and backward-compatible (`schema_version`, units map, `provenance`, `data_quality`, `confidence`). Existing fields are never renamed or removed.

---

## 5. WebSocket Real-Time Event Streaming

The Orchestrator broadcasts diagnostic progress and envelope transmissions to connected frontend clients:

- **Progress Events**: `ws://127.0.0.1:8000/ws/events`
- **Envelope Stream**: `ws://127.0.0.1:8000/ws/envelopes`

### Example Progress Event Payload (`/ws/events`)

```json
{
  "event_type": "envelope_logged",
  "correlation_id": "inc-20261031-001",
  "timestamp_utc": "2026-10-31T12:00:01.120000+00:00",
  "sender": "telemetry_agent",
  "recipient": "orchestrator",
  "message_type": "finding_submission",
  "summary": "Reported 2 observations, 1 hypothesis (confidence: 0.88)",
  "envelope": {
    "header": {
      "message_id": "c1f72b22-86ee-4eb3-8182-3d712f5581ea",
      "correlation_id": "inc-20261031-001",
      "timestamp_utc": "2026-10-31T12:00:01.100000+00:00",
      "sender": "telemetry_agent",
      "recipient": "orchestrator",
      "schema_version": "1.0.0",
      "message_type": "finding_submission",
      "priority": "normal"
    },
    "payload": {
      "scope": {
        "network_id": "campus-core",
        "devices": ["spine-01", "leaf-02"],
        "interfaces": ["et-0/0/1"]
      },
      "observations": [
        {
          "observation_id": "obs-e4c19a02",
          "category": "metric_anomaly",
          "entity": "spine-01:et-0/0/1",
          "metric_name": "packet_loss_pct",
          "observed_value": 14.8,
          "baseline_value": 0.05,
          "unit": "percent",
          "severity": "critical"
        }
      ],
      "hypotheses": [
        {
          "hypothesis_id": "hyp-82b3a104",
          "probable_cause": "INTERFACE_SATURATION_QUEUE_OVERFLOW",
          "confidence": 0.88,
          "supporting_observation_ids": ["obs-e4c19a02"],
          "refuting_observation_ids": [],
          "required_corroboration": ["LOG_INTERFACE_DROP_MESSAGES"]
        }
      ],
      "inquiries": []
    },
    "context": {
      "iteration": 0,
      "environment": "simulation"
    }
  }
}
```

---

## 6. Ingestion Gateway API (`POST /ingest`)

Member B owns the ingestion gateway microservice (`gateway/api.py`, port 8006). It normalizes raw multi-vendor telemetry into canonical `NetworkIncidentData`.

### 6.1 Request Payload Shape
Raw input can be:
1. Standard canonical JSON matching `schemas/telemetry.json`.
2. Raw multi-device dictionary with metric aliases (e.g., `loss`, `util`, `ping_ms`).
3. Organizer's Colab notebook telemetry list with nested `metrics` dicts and uppercase status fields (`Healthy`, `Warning`, `Critical`).

```json
{
  "incident_id": "inc-organizer-01",
  "records": [
    {
      "timestamp": "2026-10-31T10:00:00.000Z",
      "device_id": "router-01",
      "device_type": "router",
      "status": "Warning",
      "metrics": {
        "latency": 85.4,
        "loss": 4.2,
        "bandwidth": "10000000000",
        "util": 92.1
      }
    }
  ]
}
```

### 6.2 Response Payload Shape

```json
{
  "status": "success",
  "incident_id": "inc-organizer-01",
  "record_count": 1,
  "data": {
    "incident_id": "inc-organizer-01",
    "network_id": "campus-net",
    "topology": {
      "nodes": [{ "id": "router-01", "role": "router" }],
      "links": []
    },
    "telemetry": [
      {
        "device": "router-01",
        "interface": "management",
        "metric": "latency_ms",
        "value": 85.4,
        "unit": "ms",
        "timestamp_utc": "2026-10-31T10:00:00.000Z"
      },
      {
        "device": "router-01",
        "interface": "management",
        "metric": "packet_loss_pct",
        "value": 4.2,
        "unit": "percent",
        "timestamp_utc": "2026-10-31T10:00:00.000Z"
      }
    ]
  }
}
```

---

## 7. Scenario Library and Sample Data

The repository contains 24 pre-built, reproducible scenarios in `data/scenarios/` and generated organizer JSONL samples in `data/organizer/samples/`:

| Scenario File | Description / Fault Profile | Expected Root Cause |
| :--- | :--- | :--- |
| `normal_operation.json` | Baseline clean campus traffic | Benign (no fault) |
| `link_congestion.json` | High link utilization and queue drops | `INTERFACE_SATURATION_QUEUE_OVERFLOW` |
| `ethernet_interface_fault.json` | High CRC errors and link state flaps | `PHYSICAL_LAYER_CRC_DEGRADATION` |
| `weak_wifi_signal.json` | Low wireless RSSI and high retries | `WIFI_SIGNAL_COVERAGE_DEGRADATION` |
| `dns_failure.json` | High DNS latency and failed queries | `DNS_SERVER_RESOLUTION_TIMEOUT` |
| `dhcp_failure.json` | High DHCP request failure rate | `DHCP_POOL_EXHAUSTION_OR_TIMEOUT` |
| `device_cpu_overload.json` | Core switch CPU at 98% | `CONTROL_PLANE_CPU_EXHAUSTION` |
| `upstream_failure_cascade.json` | Upstream transit link drop | `UPSTREAM_ISP_TRANSIT_FAILURE` |
| `ambiguous_multi_fault.json` | Conflicting partial signals | `insufficient_evidence` |
| `insufficient_data.json` | Sparse telemetry, missing metrics | `insufficient_evidence` |
| `01_mtu_mismatch_blackhole.json`| MTU 1500 vs 9000 mismatch | `MTU_MISMATCH_BLACKHOLE` |
| `02_bgp_route_flap_damping.json`| Rapid BGP route flapping | `BGP_ROUTE_FLAP_DAMPING` |
| `03_optical_crc_degradation.json`| Low optical dBm with CRC errors | `OPTICAL_TRANSCEIVER_DEGRADATION` |
| `04_stp_split_brain_loop.json` | BPDU filter causing STP loop | `STP_SPLIT_BRAIN_LOOP` |
| `05_insufficient_evidence_sparse.json`| Incomplete multi-domain data | `insufficient_evidence` |
| `compound_cpu_and_link.json` | Compound CPU & link congestion | Compound fault analysis |
| `compound_wifi_and_dns.json` | Compound Wi-Fi & DNS degradation | Compound fault analysis |
| `interop_*.json` (9 files) | Clock skew, NaN/null, kbps/Mbps, etc. | Verified robust handling |

### Organizer Telemetry Samples (`data/organizer/samples/`)
- `normal.jsonl`: 10 devices, 30 snapshots each (300 records), healthy campus operation.
- `latency_spike.jsonl`: 10 devices, 30 snapshots each (300 records), severe latency on core distribution switches.
- `hardware_failure.jsonl`: 10 devices, 30 snapshots each (300 records), critical hardware degradation.

---

## 8. What Already Exists Beyond the Vertical Slice

Do not rebuild existing functionality! The following advanced subsystems are already implemented and tested:

1. **Remediation Safety Engine** (`netcoop/remediation/safety.py`):
   - Computes blast radius across downstream topology.
   - Blocks unsafe actions on core backbone routers.
   - Generates automated rollback commands.
2. **Model Context Protocol (MCP)** (`netcoop/mcp/server.py`):
   - Full JSON-RPC stdio server exposing 4 network diagnosis tools.
3. **Optional Gemini Bridge** (`netcoop/llm/gemini_bridge.py`):
   - Executive summary generation with automatic fallback when offline or without API key.
4. **SQLite Event Replay** (`netcoop/storage/db.py`):
   - Every envelope is written to SQLite.
   - CLI command `netcoop replay <incident_id>` replays the entire diagnostic trace.
5. **Chaos & Interop Testing** (`gateway/adapters/organizer_adapter.py`):
   - Automated handling for clock skews, corrupted timestamps, renamed fields, and missing metrics.

---

## 9. Team Ownership and Git Branching Rules

| Member | Branch | Subsystem Scope | Standing Commitments |
| :--- | :--- | :--- | :--- |
| **Member A** (Integrator) | `main` | Orchestration, storage, CI/CD, gatekeeper merges | No force pushes; merge gates only after verification |
| **Member B** (Specialist Agents) | `feat/gateway`, `feat/agents` | Specialist domain agents, Colab adapters, `/ingest` | Work exclusively on branch; maintain envelope contract |
| **Member C** (UI & Testing) | `feat/ui` | Dashboard UI, WebSocket client, CLI UX, testing | Minimalist monochrome design; zero emojis |
