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

    # Server binding (host interface to bind listeners on: 127.0.0.1 locally, 0.0.0.0 in Docker)
    bind_host: str = "127.0.0.1"
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

    # Agent host overrides (e.g. for container DNS names in Docker)
    telemetry_agent_host: Optional[str] = None
    topology_agent_host: Optional[str] = None
    config_agent_host: Optional[str] = None
    log_agent_host: Optional[str] = None
    synthesizer_agent_host: Optional[str] = None
    gateway_host: Optional[str] = None
    classifier_agent_host: Optional[str] = None
    wifi_services_agent_host: Optional[str] = None

    # Explicit URL overrides
    telemetry_agent_url: Optional[str] = None
    topology_agent_url: Optional[str] = None
    config_agent_url: Optional[str] = None
    log_agent_url: Optional[str] = None
    synthesizer_agent_url: Optional[str] = None
    gateway_url: Optional[str] = None
    classifier_agent_url: Optional[str] = None
    wifi_services_agent_url: Optional[str] = None

    # Communication mode: "http" enforces microservice HTTP calls
    agents_mode: str = "http"

    # Strict isolation: in-process fallback is disabled by default in production and demo
    in_process_fallback: bool = False
    allow_dev_in_process_fallback: bool = False

    # Feature flags
    feature_mcp: bool = True
    feature_remediation_sim: bool = True

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

    @property
    def fallback_enabled(self) -> bool:
        """Returns True only when in-process execution is explicitly permitted for dev."""
        return self.in_process_fallback or self.allow_dev_in_process_fallback

    def _sanitize_outbound_host(self, target_host: Optional[str]) -> str:
        """Ensure outbound HTTP requests never target wildcard 0.0.0.0."""
        if not target_host or target_host in ("0.0.0.0", "::"):
            return "127.0.0.1"
        return target_host

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

    def get_agent_host(self, role: AgentRole) -> str:
        """Lookup destination hostname or IP for a given agent role."""
        host_mapping: Dict[AgentRole, Optional[str]] = {
            AgentRole.TELEMETRY_AGENT: self.telemetry_agent_host,
            AgentRole.TOPOLOGY_AGENT: self.topology_agent_host,
            AgentRole.CONNECTIVITY_AGENT: self.topology_agent_host,
            AgentRole.CONFIG_AGENT: self.config_agent_host,
            AgentRole.LOG_AGENT: self.log_agent_host,
            AgentRole.SYNTHESIZER_AGENT: self.synthesizer_agent_host,
            AgentRole.CLASSIFIER_AGENT: self.classifier_agent_host,
            AgentRole.WIFI_SERVICES_AGENT: self.wifi_services_agent_host,
        }
        specific = host_mapping.get(role)
        return self._sanitize_outbound_host(specific or self.host)

    def get_agent_url(self, role: AgentRole) -> str:
        """Get the HTTP process endpoint URL for an agent role."""
        url_mapping: Dict[AgentRole, Optional[str]] = {
            AgentRole.TELEMETRY_AGENT: self.telemetry_agent_url,
            AgentRole.TOPOLOGY_AGENT: self.topology_agent_url,
            AgentRole.CONNECTIVITY_AGENT: self.topology_agent_url,
            AgentRole.CONFIG_AGENT: self.config_agent_url,
            AgentRole.LOG_AGENT: self.log_agent_url,
            AgentRole.SYNTHESIZER_AGENT: self.synthesizer_agent_url,
            AgentRole.CLASSIFIER_AGENT: self.classifier_agent_url,
            AgentRole.WIFI_SERVICES_AGENT: self.wifi_services_agent_url,
        }
        if url_mapping.get(role):
            return url_mapping[role]  # type: ignore[return-value]
        host = self.get_agent_host(role)
        port = self.get_agent_port(role)
        return f"http://{host}:{port}/process"

    def get_agent_health_url(self, role: AgentRole) -> str:
        """Get the HTTP health check URL for an agent role."""
        host = self.get_agent_host(role)
        port = self.get_agent_port(role)
        return f"http://{host}:{port}/health"

    def get_gateway_url(self) -> str:
        """Get the HTTP ingest endpoint URL for the gateway microservice."""
        if self.gateway_url:
            return self.gateway_url
        host = self._sanitize_outbound_host(self.gateway_host or self.host)
        return f"http://{host}:{self.gateway_port}/ingest"

    def get_gateway_health_url(self) -> str:
        """Get the HTTP health check URL for the gateway microservice."""
        host = self._sanitize_outbound_host(self.gateway_host or self.host)
        return f"http://{host}:{self.gateway_port}/health"


settings = Settings()

# Module-level feature flag exports
FEATURE_RESUME: bool = settings.feature_resume
FEATURE_HITL: bool = settings.feature_hitl
FEATURE_MCP: bool = settings.feature_mcp
FEATURE_REMEDIATION_SIM: bool = settings.feature_remediation_sim
