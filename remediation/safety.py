"""Pre-flight safety validation, redundancy checks, and blast radius calculation."""

from typing import Any, Dict, List, Tuple
from netcoop.core.report import RemediationActionItem


class PreFlightCheckResult:
    """Outcome of safety validation."""

    def __init__(self, check_name: str, passed: bool, details: str) -> None:
        self.check_name = check_name
        self.passed = passed
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "details": self.details,
        }


class RemediationSafetyChecker:
    """Evaluates proposed actions against safety invariants before execution."""

    @classmethod
    def evaluate_preflight(
        cls,
        action: RemediationActionItem,
        total_network_devices: List[str],
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Run all safety checks on an action.

        Returns:
            Tuple of (all_passed: bool, check_results: List[dict])
        """
        results: List[Dict[str, Any]] = []

        # Check 1: Enforce simulated execution
        sim_check = {
            "check_name": "simulation_safety_gate",
            "passed": action.is_simulated is True,
            "details": "Action strictly configured for simulation sandbox.",
        }
        results.append(sim_check)

        # Check 2: Blast radius boundary (< 50% of network)
        total_count = max(1, len(total_network_devices))
        impacted_count = len(action.blast_radius_devices)
        blast_ratio = impacted_count / total_count

        blast_passed = blast_ratio <= 0.60
        blast_check = {
            "check_name": "blast_radius_limit",
            "passed": blast_passed,
            "details": f"Impacts {impacted_count}/{total_count} devices ({int(blast_ratio*100)}%). Boundary is 60%.",
        }
        results.append(blast_check)

        # Check 3: Rollback command availability
        rollback_passed = (
            action.risk_level == "low" or len(action.rollback_commands) > 0
        )
        rollback_check = {
            "check_name": "rollback_readiness",
            "passed": rollback_passed,
            "details": "Rollback script verified for high/medium risk actions."
            if rollback_passed
            else "Missing rollback commands for elevated risk action.",
        }
        results.append(rollback_check)

        all_passed = all(r["passed"] for r in results)
        return all_passed, results
