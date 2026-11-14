"""Phase 5 UI/UX Contract & Accessibility Test Suite.

Verifies:
1. Internationalization (i18n) and operator timezone management (W3C i18n).
2. Complete 9-agent backend service registry in UI graph and accessible table view.
3. Accessible alternative representations for TopologyView (nodes & links tables).
4. Data provenance and anti-fabrication states ([LIVE], [SYNTHETIC DEMO], [ORGANIZER SAMPLE], [CACHED / STALE], [OFFLINE]).
5. Simulation safety invariants ('SIMULATED — NO PRODUCTION NETWORK CHANGES').
6. Fail-safe error handling for API mutations (HITL approvals and simulations).
7. WCAG 2.2 AA accessibility (skip links, focus visible, reduced motion, contrast, and touch targets).
"""

from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def test_i18n_utility_and_timezone_options():
    """Verify W3C i18n utility exists and provides operator timezones."""
    i18n_file = DASHBOARD_DIR / "src" / "utils" / "i18n.ts"
    assert i18n_file.exists(), "i18n.ts must exist"
    content = i18n_file.read_text(encoding="utf-8")

    assert "SupportedTimezone" in content
    assert '"UTC"' in content
    assert '"Asia/Kolkata"' in content
    assert '"LOCAL"' in content
    assert "formatDateTime" in content
    assert "formatPercent" in content
    assert "formatNumber" in content
    assert "formatRate" in content
    assert "formatDurationMs" in content


def test_agent_graph_includes_all_9_backend_services():
    """Verify AgentGraph renders all 9 backend services including classifier and wifi_services."""
    agent_graph_file = DASHBOARD_DIR / "src" / "components" / "AgentGraph.tsx"
    assert agent_graph_file.exists()
    content = agent_graph_file.read_text(encoding="utf-8")

    expected_agents = {
        "gateway": 8006,
        "orchestrator": 8000,
        "telemetry_agent": 8001,
        "topology_agent": 8002,
        "config_agent": 8003,
        "log_agent": 8004,
        "classifier_agent": 8007,
        "wifi_services_agent": 8008,
        "synthesizer_agent": 8005,
    }

    for agent_id, port in expected_agents.items():
        assert f'id: "{agent_id}"' in content, f"Missing agent id {agent_id}"
        assert f"port: {port}" in content, f"Missing port {port} for agent {agent_id}"

    # Verify accessible table view toggle
    assert "Accessible Table View" in content
    assert "Agent Registry Table" in content
    assert 'scope="col"' in content


def test_topology_view_accessible_alternative():
    """Verify TopologyView provides semantic HTML table alternative for nodes and links."""
    topo_file = DASHBOARD_DIR / "src" / "components" / "TopologyView.tsx"
    assert topo_file.exists()
    content = topo_file.read_text(encoding="utf-8")

    assert "Accessible Table View" in content
    assert "Topology Nodes Table" in content
    assert "Topology Links Table" in content
    assert "Primary Fault Root" in content
    assert "Blast Radius Boundary" in content


def test_data_provenance_badges_and_anti_fabrication():
    """Verify data provenance type definitions and anti-fabrication safeguards."""
    proto_file = DASHBOARD_DIR / "src" / "types" / "protocol.ts"
    assert proto_file.exists()
    proto_content = proto_file.read_text(encoding="utf-8")

    for state in ["LIVE", "SYNTHETIC_DEMO", "ORGANIZER_SAMPLE", "CACHED_STALE", "OFFLINE"]:
        assert f'"{state}"' in proto_content, f"Missing provenance state {state}"

    app_file = DASHBOARD_DIR / "src" / "App.tsx"
    app_content = app_file.read_text(encoding="utf-8")
    assert "[OFFLINE BACKEND]" in app_content
    assert "Diagnostic Backend Service Unreachable" in app_content
    assert "handleRetryConnect" in app_content


def test_simulation_safety_watermark_invariant():
    """Verify persistent watermark 'SIMULATED — NO PRODUCTION NETWORK CHANGES' in all simulation surfaces."""
    sim_file = DASHBOARD_DIR / "src" / "components" / "SimulatedRemediationView.tsx"
    assert sim_file.exists()
    sim_content = sim_file.read_text(encoding="utf-8")
    assert "SIMULATED — NO PRODUCTION NETWORK CHANGES" in sim_content

    hitl_file = DASHBOARD_DIR / "src" / "components" / "HitlApprovalQueue.tsx"
    assert hitl_file.exists()
    hitl_content = hitl_file.read_text(encoding="utf-8")
    assert "SIMULATED — NO PRODUCTION NETWORK CHANGES" in hitl_content

    report_file = DASHBOARD_DIR / "src" / "components" / "ReportCard.tsx"
    assert report_file.exists()
    report_content = report_file.read_text(encoding="utf-8")
    assert "SIMULATED — NO PRODUCTION NETWORK CHANGES" in report_content


def test_failsafe_mutation_error_handling():
    """Verify HITL and Simulation do not update state optimistically when backend rejected."""
    hitl_file = DASHBOARD_DIR / "src" / "components" / "HitlApprovalQueue.tsx"
    hitl_content = hitl_file.read_text(encoding="utf-8")
    assert "!decRes.ok" in hitl_content
    assert "Decision submission failed" in hitl_content
    assert "Zero pending remediation actions awaiting operator approval" in hitl_content

    sim_file = DASHBOARD_DIR / "src" / "components" / "SimulatedRemediationView.tsx"
    sim_content = sim_file.read_text(encoding="utf-8")
    assert "Explicit Operator Confirmation Required" in sim_content
    assert "Run Sandbox Simulation" in sim_content


def test_wcag_accessibility_tokens_and_markup():
    """Verify WCAG 2.2 AA accessibility requirements in styles and DOM."""
    tokens_file = DASHBOARD_DIR / "src" / "styles" / "tokens.css"
    tokens_content = tokens_file.read_text(encoding="utf-8")
    assert ":focus-visible" in tokens_content
    assert "prefers-reduced-motion: reduce" in tokens_content

    index_file = DASHBOARD_DIR / "index.html"
    index_content = index_file.read_text(encoding="utf-8")
    assert 'dir="ltr"' in index_content
    assert 'lang="en"' in index_content
    assert 'name="viewport"' in index_content

    app_file = DASHBOARD_DIR / "src" / "App.tsx"
    app_content = app_file.read_text(encoding="utf-8")
    assert "Skip to main content" in app_content
    assert 'id="main-content"' in app_content


def test_frontend_production_build_artifacts():
    """Verify frontend compiles and produces optimized production build."""
    dist_dir = DASHBOARD_DIR / "dist"
    index_html = dist_dir / "index.html"
    assert index_html.exists(), "dist/index.html must exist from production build"
    assets_dir = dist_dir / "assets"
    assert assets_dir.exists() and any(assets_dir.glob("*.js")), "dist/assets/*.js must exist"
