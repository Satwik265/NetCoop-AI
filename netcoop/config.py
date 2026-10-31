"""Application configuration and settings."""

from typing import Dict, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from netcoop.core.envelope import AgentRole


class Settings(BaseSettings):
    """Runtime application settings for NetCoop AI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NetCoop AI"
    version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Server binding
    host: str = "127.0.0.1"
    port: int = 8000

    # Dedicated microservice agent ports
    telemetry_agent_port: int = 8001
    topology_agent_port: int = 8002
    config_agent_port: int = 8003
    log_agent_port: int = 8004
    synthesizer_agent_port: int = 8005
    gateway_port: int = 8006
    classifier_agent_port: int = 8007
    wifi_services_agent_port: int = 8008

    # Communication mode: "http" enforces microservice HTTP calls
    agents_mode: str = "http"
    in_process_fallback: bool = True

    # Persistence
    database_url: str = "sqlite:///./netcoop.db"

    # Optional LLM integration (Gemini)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # Orchestrator parameters
    max_inquiry_iterations: int = 3
    agent_timeout_seconds: float = 3.0
    agent_max_retries: int = 2
    circuit_breaker_failure_threshold: int = 2

    # Remediation safety
    remediation_simulated_only: bool = True

    # Feature flags (default on for demo; when off, core pipeline remains untouched)
    feature_resume: bool = True
    feature_hitl: bool = True

    def get_agent_port(self, role: AgentRole) -> int:
        """Lookup HTTP port assigned to a given specialist agent role."""
        port_mapping: Dict[AgentRole, int] = {
            AgentRole.TELEMETRY_AGENT: self.telemetry_agent_port,
            AgentRole.TOPOLOGY_AGENT: self.topology_agent_port,
            AgentRole.CONNECTIVITY_AGENT: self.topology_agent_port,
            AgentRole.CONFIG_AGENT: self.config_agent_port,
            AgentRole.LOG_AGENT: self.log_agent_port,
            AgentRole.SYNTHESIZER_AGENT: self.synthesizer_agent_port,
            AgentRole.CLASSIFIER_AGENT: self.classifier_agent_port,
            AgentRole.WIFI_SERVICES_AGENT: self.wifi_services_agent_port,
        }
        return port_mapping.get(role, self.port)

    def get_agent_url(self, role: AgentRole) -> str:
        """Get the HTTP process endpoint URL for an agent role."""
        port = self.get_agent_port(role)
        return f"http://{self.host}:{port}/process"

    def get_agent_health_url(self, role: AgentRole) -> str:
        """Get the HTTP health check URL for an agent role."""
        port = self.get_agent_port(role)
        return f"http://{self.host}:{port}/health"


settings = Settings()

# Module-level feature flag exports
FEATURE_RESUME: bool = settings.feature_resume
FEATURE_HITL: bool = settings.feature_hitl
