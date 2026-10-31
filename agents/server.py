"""FastAPI microservice server wrapper for isolated specialist domain agents."""

import argparse
import sys
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.config import settings
from core.envelope import AgentEnvelope, AgentRole
from agents.base import BaseAgent
from agents.config_agent import ConfigAgent
from agents.log_agent import LogAgent
from agents.synthesizer_agent import SynthesizerAgent
from agents.telemetry_agent import TelemetryAgent
from agents.topology_agent import TopologyAgent


def get_agent_instance(role: AgentRole) -> BaseAgent:
    """Instantiate specialist agent by enum role."""
    mapping = {
        AgentRole.TELEMETRY_AGENT: TelemetryAgent,
        AgentRole.TOPOLOGY_AGENT: TopologyAgent,
        AgentRole.CONFIG_AGENT: ConfigAgent,
        AgentRole.LOG_AGENT: LogAgent,
        AgentRole.SYNTHESIZER_AGENT: SynthesizerAgent,
    }
    agent_cls = mapping.get(role)
    if not agent_cls:
        raise ValueError(f"Unknown agent role: {role}")
    return agent_cls()


def create_agent_app(role: AgentRole) -> FastAPI:
    """Create FastAPI application for a specific specialist agent."""
    agent = get_agent_instance(role)

    app = FastAPI(
        title=f"NetCoop Agent: {role.value}",
        version="1.0.0",
        description=f"Isolated microservice process for {agent.name}.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> Dict[str, str]:
        """Health check endpoint for process lifecycle monitoring."""
        return {
            "status": "ok",
            "agent": role.value,
            "name": agent.name,
            "version": "1.0.0",
        }

    @app.post("/process", response_model=AgentEnvelope)
    async def process_envelope(envelope_data: Dict[str, Any]) -> AgentEnvelope:
        """Process incoming protocol envelope and return agent response envelope."""
        try:
            envelope = AgentEnvelope.model_validate(envelope_data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Envelope schema validation failed: {str(e)}",
            )

        try:
            response = agent.handle_envelope(envelope)
            return response
        except Exception as e:
            return AgentEnvelope.create_error_response(
                original=envelope,
                error_code="PROCESSING_ERROR",
                message=f"Agent internal error: {str(e)}",
            )

    @app.post("/envelope", response_model=AgentEnvelope)
    async def process_envelope_alias(envelope_data: Dict[str, Any]) -> AgentEnvelope:
        """Alias endpoint conforming to alternate agent dispatch conventions."""
        return await process_envelope(envelope_data)

    return app


def main() -> None:
    """CLI runner to launch an individual agent server."""
    parser = argparse.ArgumentParser(description="Run NetCoop specialist agent microservice.")
    parser.add_argument(
        "--role",
        type=str,
        required=True,
        choices=[r.value for r in AgentRole if r not in (AgentRole.ORCHESTRATOR, AgentRole.BROADCAST, AgentRole.HUMAN_OPERATOR)],
        help="Specialist agent role enum value",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.host,
        help="Host interface to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to listen on (defaults to configured agent port)",
    )

    args = parser.parse_args()
    role = AgentRole(args.role)
    port = args.port or settings.get_agent_port(role)

    agent_app = create_agent_app(role)
    print(f"Starting {role.value} on {args.host}:{port}")
    uvicorn.run(agent_app, host=args.host, port=port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()

