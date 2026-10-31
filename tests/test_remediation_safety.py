"""Unit and integration tests for simulated remediation safety gates."""

from netcoop.core.evidence import DiagnosticHypothesis
from netcoop.core.report import RemediationActionItem
from netcoop.remediation.engine import RemediationEngine
from netcoop.remediation.safety import RemediationSafetyChecker


def test_safety_check_accepts_simulated_action() -> None:
    """Verify that a compliant action with rollback commands passes pre-flight checks."""
    action = RemediationActionItem(
        action_id="act-test-01",
        title="Harmonize MTU",
        description="Set MTU to 9000",
        device="leaf-01",
        commands=["interface et-1", "mtu 9000"],
        rollback_commands=["interface et-1", "mtu 1500"],
        risk_level="low",
        blast_radius_devices=["leaf-01"],
        is_simulated=True,
    )
    all_devices = ["leaf-01", "spine-01", "leaf-02", "spine-02"]
    passed, checks = RemediationSafetyChecker.evaluate_preflight(action, all_devices)
    assert passed is True
    assert all(c["passed"] for c in checks)


def test_safety_check_rejects_excessive_blast_radius() -> None:
    """Verify that an action impacting too high a proportion of devices is flagged."""
    action = RemediationActionItem(
        action_id="act-test-blast",
        title="Global Switch Reload",
        description="Reload switches",
        device="core-1",
        commands=["reload"],
        rollback_commands=[],
        risk_level="high",
        blast_radius_devices=["core-1", "core-2", "spine-1", "spine-2"],
        is_simulated=True,
    )
    all_devices = ["core-1", "core-2", "spine-1", "spine-2"]  # 100% blast radius
    passed, checks = RemediationSafetyChecker.evaluate_preflight(action, all_devices)
    assert passed is False


def test_simulated_remediation_execution_updates_status() -> None:
    """Verify simulated execution produces success record and never touches real devices."""
    action = RemediationActionItem(
        action_id="act-safe-01",
        title="Harmonize MTU",
        description="Simulated MTU update",
        device="leaf-01",
        commands=["interface et-1", "mtu 9000"],
        rollback_commands=["interface et-1", "mtu 1500"],
        risk_level="low",
        blast_radius_devices=["leaf-01"],
        is_simulated=True,
    )
    res = RemediationEngine.execute_simulated_action(
        incident_id="inc-sim-test",
        action=action,
        operator="operator-alice",
        all_devices=["leaf-01", "leaf-02", "spine-01"],
    )
    assert res["success"] is True
    assert action.status == "simulated_success"

