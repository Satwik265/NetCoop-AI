"""Generate monochrome SVG architecture diagram for NetCoop AI."""

from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent
OUTPUT_FILE = OUTPUT_DIR / "architecture.svg"


def generate_architecture_svg() -> None:
    """Generate clean, publication-grade monochrome architecture SVG."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 620" width="100%" height="100%" style="background-color: #0F0F10; font-family: 'JetBrains Mono', monospace;">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569" />
    </marker>
    <marker id="arrow-light" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#EDEDEA" />
    </marker>
  </defs>

  <!-- Title & Subtitle -->
  <text x="40" y="42" fill="#EDEDEA" font-size="16" font-weight="700" letter-spacing="1">NETCOOP AI: MULTI-AGENT ARCHITECTURE</text>
  <text x="40" y="62" fill="#6B6B66" font-size="11">Shared-Nothing Microservice Architecture with Versioned Wire Envelopes</text>

  <!-- Section 1: Ingestion Gateway -->
  <g transform="translate(40, 90)">
    <rect width="200" height="200" fill="#161618" stroke="#2A2A2D" stroke-width="1.5" />
    <text x="16" y="28" fill="#EDEDEA" font-size="12" font-weight="600">INGESTION GATEWAY</text>
    <text x="16" y="44" fill="#6B6B66" font-size="10">Port :8006 (HTTP loopback)</text>

    <!-- Sub-boxes -->
    <rect x="16" y="60" width="168" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="80" fill="#EDEDEA" font-size="10">Organizer Colab Adapter</text>

    <rect x="16" y="102" width="168" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="122" fill="#EDEDEA" font-size="10">Telemetry Normalizer</text>

    <rect x="16" y="144" width="168" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="164" fill="#EDEDEA" font-size="10">Data Quality Auditor</text>
  </g>

  <!-- Arrow Gateway -> Orchestrator -->
  <path d="M 240 190 L 300 190" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" />
  <text x="270" y="180" fill="#6B6B66" font-size="9" text-anchor="middle">Canonical</text>

  <!-- Section 2: Orchestrator & Mediator -->
  <g transform="translate(300, 90)">
    <rect width="250" height="200" fill="#161618" stroke="#475569" stroke-width="1.5" />
    <text x="16" y="28" fill="#EDEDEA" font-size="12" font-weight="600">ORCHESTRATOR &amp; MEDIATOR</text>
    <text x="16" y="44" fill="#6B6B66" font-size="10">Port :8000 (LangGraph State Machine)</text>

    <rect x="16" y="60" width="218" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="80" fill="#EDEDEA" font-size="10">Dispatch &amp; Fan-Out Bus</text>

    <rect x="16" y="102" width="218" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="122" fill="#EDEDEA" font-size="10">Mediator &amp; Cross-Inquiry Turn</text>

    <rect x="16" y="144" width="218" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="164" fill="#EDEDEA" font-size="10">Conflict Resolution Hierarchy</text>
  </g>

  <!-- Arrow Orchestrator -> Specialists -->
  <path d="M 425 290 L 425 340" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" />

  <!-- Section 3: Specialist Agent Microservices (Decoupled OS Processes) -->
  <g transform="translate(40, 340)">
    <rect width="880" height="130" fill="#161618" stroke="#2A2A2D" stroke-width="1.5" />
    <text x="20" y="26" fill="#EDEDEA" font-size="12" font-weight="600">SPECIALIST AGENT PROCESSES (Shared-Nothing, Dedicated Interpreters)</text>
    <text x="20" y="42" fill="#6B6B66" font-size="10">Decoupled HTTP REST loopbacks communicating exclusively via versioned wire envelopes (schemas/envelope.json)</text>

    <!-- Specialist 1 -->
    <rect x="20" y="55" width="158" height="60" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="30" y="78" fill="#EDEDEA" font-size="11" font-weight="600">Telemetry Agent</text>
    <text x="30" y="95" fill="#6B6B66" font-size="10">Port :8001</text>
    <text x="30" y="107" fill="#475569" font-size="9">Metric Anomalies</text>

    <!-- Specialist 2 -->
    <rect x="194" y="55" width="158" height="60" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="204" y="78" fill="#EDEDEA" font-size="11" font-weight="600">Topology Agent</text>
    <text x="204" y="95" fill="#6B6B66" font-size="10">Port :8002</text>
    <text x="204" y="107" fill="#475569" font-size="9">BGP Flaps &amp; Graph</text>

    <!-- Specialist 3 -->
    <rect x="368" y="55" width="158" height="60" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="378" y="78" fill="#EDEDEA" font-size="11" font-weight="600">Config Agent</text>
    <text x="378" y="95" fill="#6B6B66" font-size="10">Port :8003</text>
    <text x="378" y="107" fill="#475569" font-size="9">Diffs &amp; MTU Blackholes</text>

    <!-- Specialist 4 -->
    <rect x="542" y="55" width="158" height="60" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="552" y="78" fill="#EDEDEA" font-size="11" font-weight="600">Log Agent</text>
    <text x="552" y="95" fill="#6B6B66" font-size="10">Port :8004</text>
    <text x="552" y="107" fill="#475569" font-size="9">Syslog &amp; Pattern Buffer</text>

    <!-- Specialist 5 -->
    <rect x="716" y="55" width="144" height="60" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="726" y="78" fill="#EDEDEA" font-size="11" font-weight="600">Synthesizer</text>
    <text x="726" y="95" fill="#6B6B66" font-size="10">Port :8005</text>
    <text x="726" y="107" fill="#475569" font-size="9">Root Cause Evaluator</text>
  </g>

  <!-- Section 4: Storage & Outputs -->
  <g transform="translate(620, 90)">
    <rect width="300" height="200" fill="#161618" stroke="#2A2A2D" stroke-width="1.5" />
    <text x="16" y="28" fill="#EDEDEA" font-size="12" font-weight="600">STORAGE &amp; PLATFORM OUTPUTS</text>
    <text x="16" y="44" fill="#6B6B66" font-size="10">Auditable Event Store &amp; Interfaces</text>

    <rect x="16" y="60" width="268" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="80" fill="#EDEDEA" font-size="10">SQLite Event Store (netcoop replay)</text>

    <rect x="16" y="102" width="268" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="122" fill="#EDEDEA" font-size="10">Remediation Engine (Blast Radius &amp; Rollback)</text>

    <rect x="16" y="144" width="268" height="32" fill="#0F0F10" stroke="#2A2A2D" />
    <text x="24" y="164" fill="#EDEDEA" font-size="10">React Dashboard &amp; WebSocket (WS /ws/events)</text>
  </g>

  <!-- Connecting Arrows -->
  <path d="M 550 190 L 620 190" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" />

  <!-- Footer note -->
  <text x="40" y="590" fill="#6B6B66" font-size="10">Zero Shared Memory | 100% Deterministic Offline Core | Simulated Sandboxed Remediation</text>
</svg>"""

    OUTPUT_FILE.write_text(svg, encoding="utf-8")
    print(f"Generated architecture diagram: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_architecture_svg()

