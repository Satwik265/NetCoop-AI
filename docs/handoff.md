# NetCoop AI Repository Handoff and Environment Guide

## 1. Environment and Execution Standards
- **Operating System**: Windows 11, PowerShell.
- **Python Runtime**: Python 3.13 within virtual environment `.venv`.
- **PowerShell Activation**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **Rule**: Never use bash-only syntax (e.g. `export`, `rm -rf`, `make` without Windows support).

## 2. Make Targets and Plain Python Equivalents

All `make` targets defined in `Makefile` have exact plain `python` / PowerShell equivalents:

| Make Target | Action | Plain Python / PowerShell Equivalent |
| :--- | :--- | :--- |
| `make setup` | Setup dependencies and dashboard | `uv pip install -r requirements.txt -e .`<br/>`cd dashboard; npm install; cd ..` |
| `make up` | Start all agent microservices (daemon) | `python scripts/run_agents.py --daemon` |
| `make down` | Stop all agent microservices | `python scripts/run_agents.py --stop` |
| `make demo` | Run end-to-end multi-agent demonstration | `python scripts/demo.py` |
| `make test` | Run complete unit and property tests | `python -m pytest tests/ -v` |
| `make eval` | Run ground-truth benchmark suite | `python scripts/eval_benchmark.py` |
| `make eval-quick` | Run fast evaluation benchmark on quick subset | `python scripts/eval_benchmark.py --quick` |
| `make train` | Train learned classifier and generate artifacts | `python scripts/train_models.py` |
| `make assets` | Build frontend production bundle | `cd dashboard; npm run build; cd ..` |
| `make run` | Start FastAPI backend server on port 8000 | `python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload` |
| `make clean` | Terminate agents and remove temp caches | `python scripts/run_agents.py --stop`<br/>`Get-ChildItem -Recurse -Include __pycache__,.pytest_cache | Remove-Item -Recurse -Force` |

## 3. Microservice Ports and Inter-Process Contracts

| Service / Agent | Process Type | Host Binding | HTTP Port | Primary Endpoints |
| :--- | :--- | :--- | :---: | :--- |
| **Orchestrator & API** | FastAPI / Uvicorn | `127.0.0.1` | **8000** | `GET /api/health`<br/>`POST /api/diagnose`<br/>`WS /ws/events` |
| **Telemetry Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8001** | `GET /health`<br/>`POST /process` |
| **Topology Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8002** | `GET /health`<br/>`POST /process` |
| **Config Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8003** | `GET /health`<br/>`POST /process` |
| **Log Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8004** | `GET /health`<br/>`POST /process` |
| **Synthesizer Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8005** | `GET /health`<br/>`POST /process` |
| **Gateway Ingestion** | FastAPI / Uvicorn | `127.0.0.1` | **8006** | `GET /health`<br/>`POST /ingest` |
| **Classifier Agent** | FastAPI / Uvicorn | `127.0.0.1` | **8007** | `GET /health`<br/>`POST /process` |

## 4. Repository Layout and Authoritative Subsystems

Code resides in both top-level modules and the `netcoop/` package. The authoritative locations are:

| Subsystem | Authoritative Path | Overlap / Delegation Strategy |
| :--- | :--- | :--- |
| **Agents** | `netcoop/agents/` | `agents/` delegates to or imports `netcoop/agents/` |
| **Classifier Agent** | `netcoop/agents/classifier/` | Separate process running on port 8007 emitting findings and conformal sets |
| **Core Protocol** | `netcoop/core/` | `core/` delegates directly to `netcoop.core.*` |
| **Orchestrator** | `netcoop/orchestrator/` | `orchestrator/` coordinates state graph and mediator |
| **Remediation** | `netcoop/remediation/` | `remediation/` provides safety and simulated actions |
| **Storage** | `netcoop/storage/` | `storage/` maintains SQLite schema and audit logs |
| **LLM Bridge** | `netcoop/llm/` | `llm/` provides offline-safe Google GenAI integration |
| **MCP Server** | `netcoop/mcp/` and `mcp_server/` | `mcp_server/server.py` implements standard stdio MCP |
| **Gateway** | `gateway/` | Ingestion microservice and organizer format adapters |
| **Scenario Generator** | `netcoop/data/` & `data/` | `generator.py`, `heldout_generator.py` in `netcoop/data/`; scenarios in `data/scenarios/` |
| **Models & Artifacts** | `netcoop/models/` | Models in `netcoop/models/`, weights and artifacts in `netcoop/models/artifacts/` |
| **Evaluation** | `eval/` & `scripts/` | Benchmark scripts in `scripts/`, results in `eval/results/` |
| **Dashboard** | `dashboard/` | React, Vite, Tailwind frontend monochrome UI |
| **CLI** | `netcoop/cli.py` & `cli/main.py` | Typer CLI (`netcoop` command) |

## 5. Logical Path Mappings
- `/core` -> `netcoop/core`
- `/agents` -> `netcoop/agents`
- `/agents/classifier` -> `netcoop/agents/classifier`
- `/orchestrator` -> `netcoop/orchestrator`
- `/gateway` -> `gateway`
- `/models` -> `netcoop/models`
- `/eval` -> `eval` (benchmark results in `eval/results`)
- `/sandbox` -> `netcoop/remediation`
- `/mcp_server` -> `mcp_server` and `netcoop/mcp`
- Generator code -> `netcoop/data` (`generator.py`, `heldout_generator.py`)
- Data files -> `data/`
- `/dashboard` -> `dashboard`
- `/tests` -> `tests`
- `/scripts` -> `scripts`
- `/docs` -> `docs`

## 6. Message Envelope Contract Mapping
The existing message envelope is authoritative:
- `payload.scope`: contains `network_id`, `devices`, `interfaces`.
- `payload.observations`: empirical findings from specialist agents.
- `payload.hypotheses`: proposed fault diagnoses with confidence scores.
- `payload.inquiries`: targeted questions for corroboration (`evidence_query = inquiries`).
- `context.iteration`: round counter for multi-turn debate/conflict resolution managed by the mediator.
- Extensions are strictly ADDITIVE and backward-compatible (`schema_version`, units map, `provenance`, `data_quality`, `confidence`). Existing fields are never renamed or removed.
