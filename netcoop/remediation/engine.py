"""Simulated remediation execution engine and Human-in-the-Loop approval coordinator."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import Session

from netcoop.core.evidence import DiagnosticHypothesis
from netcoop.core.report import RemediationActionItem
from netcoop.remediation.actions import RemediationCatalog
from netcoop.remediation.safety import RemediationSafetyChecker
from netcoop.storage.db import engine
from netcoop.storage.models import RemediationLog


class RemediationEngine:
    """Manages simulated remediation plans and operator approval gates."""

    @classmethod
    def generate_plan(
        cls,
        hypothesis: DiagnosticHypothesis,
        network_devices: List[str],
    ) -> List[RemediationActionItem]:
        """Generate appropriate simulated actions based on diagnosed root cause."""
        actions: List[RemediationActionItem] = []
        cause = hypothesis.cause_key

        if cause == "MTU_MISMATCH_BLACKHOLE":
            # Harmonize MTU on first affected device
            dev = hypothesis.affected_devices[0] if hypothesis.affected_devices else "spine-01"
            actions.append(
                RemediationCatalog.create_mtu_harmonization_action(
                    device=dev, interface="et-0/0/1", target_mtu=9000
                )
            )
        elif cause == "BGP_ROUTE_FLAP_DAMPING":
            dev = hypothesis.affected_devices[0] if hypothesis.affected_devices else "wan-01"
            actions.append(
                RemediationCatalog.create_clear_flap_damping_action(
                    device=dev, peer_ip="198.51.100.1"
                )
            )
        elif cause == "OPTICAL_TRANSCEIVER_DEGRADATION":
            dev = hypothesis.affected_devices[0] if hypothesis.affected_devices else "core-b"
            peer = hypothesis.affected_devices[1] if len(hypothesis.affected_devices) > 1 else "core-a"
            actions.append(
                RemediationCatalog.create_drain_optical_link_action(
                    device=dev, interface="HundredGigE0/0/0/0", peer_device=peer
                )
            )
        elif cause == "STP_SPLIT_BRAIN_LOOP":
            dev = hypothesis.affected_devices[0] if hypothesis.affected_devices else "access-02"
            actions.append(
                RemediationCatalog.create_remove_bpdu_filter_action(
                    device=dev, interface="GigabitEthernet1/0/24"
                )
            )

        return actions

    @classmethod
    def execute_simulated_action(
        cls,
        incident_id: str,
        action: RemediationActionItem,
        operator: str = "human_operator",
        all_devices: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Validate safety gates and execute simulated configuration change."""
        all_devs = all_devices or action.blast_radius_devices
        passed, checks = RemediationSafetyChecker.evaluate_preflight(action, all_devs)

        if not passed:
            action.status = "rejected"
            return {
                "success": False,
                "message": "Pre-flight safety checks failed.",
                "checks": checks,
                "action": action.model_dump(),
            }

        # Simulated execution
        action.status = "simulated_success"
        executed_at = datetime.now(timezone.utc).isoformat()

        # Persist to remediation audit log
        with Session(engine) as session:
            log_entry = RemediationLog(
                incident_id=incident_id,
                action_id=action.action_id,
                device=action.device,
                commands_json=json.dumps(action.commands),
                rollback_commands_json=json.dumps(action.rollback_commands),
                risk_level=action.risk_level,
                status="simulated_executed",
                approved_by=operator,
                simulated_at=executed_at,
            )
            session.add(log_entry)
            session.commit()

        return {
            "success": True,
            "message": f"Successfully simulated remediation action {action.action_id} on {action.device}.",
            "executed_commands": action.commands,
            "checks": checks,
            "action": action.model_dump(),
        }

    @classmethod
    def approve_action(
        cls,
        action_id: str,
        operator: str = "human_operator",
        rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a pending remediation action and execute as a simulated action only."""
        from netcoop.storage.db import get_remediation_action_log, record_hitl_decision

        log_entry = get_remediation_action_log(action_id)
        if not log_entry:
            return {"success": False, "message": f"Remediation action '{action_id}' not found."}

        # Record approval decision
        record_hitl_decision(
            action_id=action_id,
            status="approved",
            operator=operator,
            rationale=rationale or "Approved by operator",
        )

        # Flow into simulated remediation engine
        action_item = RemediationActionItem(
            action_id=log_entry.action_id,
            title=f"Remediation on {log_entry.device}",
            description=f"Risk level {log_entry.risk_level}",
            device=log_entry.device,
            commands=json.loads(log_entry.commands_json),
            rollback_commands=json.loads(log_entry.rollback_commands_json),
            risk_level=log_entry.risk_level,
            blast_radius_devices=[log_entry.device],
            is_simulated=True,
            status="approved",
        )

        exec_res = cls.execute_simulated_action(
            incident_id=log_entry.incident_id,
            action=action_item,
            operator=operator,
            all_devices=[log_entry.device, "gw-01", "gw-02"],
        )

        return {
            "success": True,
            "action_id": action_id,
            "status": "approved",
            "operator": operator,
            "rationale": rationale,
            "simulation": exec_res,
        }

    @classmethod
    def reject_action(
        cls,
        action_id: str,
        operator: str = "human_operator",
        rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reject a pending remediation action and record the decision in event log."""
        from netcoop.storage.db import get_remediation_action_log, record_hitl_decision

        log_entry = get_remediation_action_log(action_id)
        if not log_entry:
            return {"success": False, "message": f"Remediation action '{action_id}' not found."}

        record_hitl_decision(
            action_id=action_id,
            status="rejected",
            operator=operator,
            rationale=rationale or "Rejected by operator",
        )
        return {
            "success": True,
            "action_id": action_id,
            "status": "rejected",
            "operator": operator,
            "rationale": rationale,
        }

    @classmethod
    def modify_action(
        cls,
        action_id: str,
        new_commands: List[str],
        operator: str = "human_operator",
        rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Modify parameters/commands of a pending remediation action and log the change."""
        from netcoop.storage.db import get_remediation_action_log, record_hitl_decision

        log_entry = get_remediation_action_log(action_id)
        if not log_entry:
            return {"success": False, "message": f"Remediation action '{action_id}' not found."}

        record_hitl_decision(
            action_id=action_id,
            status="modified",
            operator=operator,
            rationale=rationale or "Modified by operator",
            modified_commands=new_commands,
        )
        return {
            "success": True,
            "action_id": action_id,
            "status": "modified",
            "modified_commands": new_commands,
            "operator": operator,
            "rationale": rationale,
        }

