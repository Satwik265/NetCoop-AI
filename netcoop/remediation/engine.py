"""Simulated remediation execution engine and Human-in-the-Loop approval coordinator."""

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlmodel import Session

from netcoop.config import settings
from netcoop.core.evidence import DiagnosticHypothesis
from netcoop.core.report import RemediationActionItem
from netcoop.remediation.actions import RemediationCatalog
from netcoop.remediation.safety import RemediationSafetyChecker
from netcoop.storage.db import engine
from netcoop.storage.models import RemediationLog


class NetworkCallBlockedError(PermissionError):
    """Raised when any code attempts real network I/O during remediation simulation."""

    pass


@contextmanager
def network_sandbox_guard():
    """Hard-block any real network socket calls or subprocess calls to network tools.

    Guarantees that remediation actions are strictly simulated in-memory and can never
    contact real network infrastructure.
    """
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_bind = socket.socket.bind
    orig_create_conn = socket.create_connection
    orig_popen = subprocess.Popen

    blocked_cmds = {
        "ping", "traceroute", "tracert", "ssh", "telnet", "nc", "netcat",
        "curl", "wget", "netsh", "ip", "route", "ifconfig", "arp", "ethtool"
    }

    def _blocked_connect(*args, **kwargs):
        raise NetworkCallBlockedError(
            "Real network socket connection is hard-blocked during remediation simulation. "
            "Simulated, no production changes."
        )

    def _blocked_connect_ex(*args, **kwargs):
        raise NetworkCallBlockedError(
            "Real network socket connection is hard-blocked during remediation simulation. "
            "Simulated, no production changes."
        )

    def _blocked_bind(*args, **kwargs):
        raise NetworkCallBlockedError(
            "Real network socket bind is hard-blocked during remediation simulation. "
            "Simulated, no production changes."
        )

    def _blocked_create_connection(*args, **kwargs):
        raise NetworkCallBlockedError(
            "Real network socket connection is hard-blocked during remediation simulation. "
            "Simulated, no production changes."
        )

    def _safe_popen(cmd, *args, **kwargs):
        cmd_str = ""
        if isinstance(cmd, (list, tuple)) and cmd:
            cmd_str = str(cmd[0]).lower()
        elif isinstance(cmd, str):
            cmd_str = cmd.split()[0].lower() if cmd.split() else ""

        cmd_base = Path(cmd_str).name
        if cmd_base in blocked_cmds:
            raise NetworkCallBlockedError(
                f"Real network subprocess execution of '{cmd_base}' is hard-blocked during remediation simulation. "
                "Simulated, no production changes."
            )
        return orig_popen(cmd, *args, **kwargs)

    try:
        socket.socket.connect = _blocked_connect
        socket.socket.connect_ex = _blocked_connect_ex
        socket.socket.bind = _blocked_bind
        socket.create_connection = _blocked_create_connection
        subprocess.Popen = _safe_popen
        yield
    finally:
        socket.socket.connect = orig_connect
        socket.socket.connect_ex = orig_connect_ex
        socket.socket.bind = orig_bind
        socket.create_connection = orig_create_conn
        subprocess.Popen = orig_popen


class RemediationEngine:
    """Manages simulated remediation plans and operator approval gates."""

    DISCLAIMER: str = "Simulated, no production changes"

    @classmethod
    def generate_plan(
        cls,
        hypothesis: DiagnosticHypothesis,
        network_devices: List[str],
    ) -> List[RemediationActionItem]:
        """Generate appropriate simulated actions based on diagnosed root cause."""
        actions: List[RemediationActionItem] = []
        cause = hypothesis.cause_key
        dev = hypothesis.affected_devices[0] if hypothesis.affected_devices else "spine-01"
        peer = hypothesis.affected_devices[1] if len(hypothesis.affected_devices) > 1 else "spine-02"

        if cause == "MTU_MISMATCH_BLACKHOLE":
            actions.append(
                RemediationCatalog.create_mtu_harmonization_action(
                    device=dev, interface="et-0/0/1", target_mtu=9000
                )
            )
        elif cause == "BGP_ROUTE_FLAP_DAMPING":
            actions.append(
                RemediationCatalog.create_clear_flap_damping_action(
                    device=dev, peer_ip="198.51.100.1"
                )
            )
        elif cause == "OPTICAL_TRANSCEIVER_DEGRADATION":
            actions.append(
                RemediationCatalog.create_drain_optical_link_action(
                    device=dev, interface="HundredGigE0/0/0/0", peer_device=peer
                )
            )
        elif cause == "STP_SPLIT_BRAIN_LOOP":
            actions.append(
                RemediationCatalog.create_remove_bpdu_filter_action(
                    device=dev, interface="GigabitEthernet1/0/24"
                )
            )
        elif cause in ("INTERFACE_SATURATION_QUEUE_OVERFLOW", "link_congestion"):
            actions.append(
                RemediationCatalog.create_rebalance_traffic_action(
                    device=dev, interface="et-0/0/1"
                )
            )
            actions.append(
                RemediationCatalog.create_raise_qos_action(
                    device=dev, interface="et-0/0/1"
                )
            )
        elif cause in ("PHYSICAL_LAYER_CRC_DEGRADATION", "hardware_failure", "ethernet_interface_fault"):
            actions.append(
                RemediationCatalog.create_clear_counters_action(
                    device=dev, interface="et-0/0/1"
                )
            )
            actions.append(
                RemediationCatalog.create_failover_link_action(
                    device=dev, interface="et-0/0/1", peer_device=peer
                )
            )
        elif cause in ("latency_spike", "upstream_congestion"):
            actions.append(
                RemediationCatalog.create_raise_qos_action(
                    device=dev, interface="et-0/0/1"
                )
            )
            actions.append(
                RemediationCatalog.create_rebalance_traffic_action(
                    device=dev, interface="et-0/0/1"
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
        """Validate safety gates and execute simulated configuration change under sandbox guard."""
        if not getattr(settings, "feature_remediation_sim", True):
            return {
                "success": False,
                "disclaimer": cls.DISCLAIMER,
                "message": "FEATURE_REMEDIATION_SIM is disabled in configuration.",
                "action": action.model_dump(),
            }

        with network_sandbox_guard():
            all_devs = all_devices or action.blast_radius_devices
            passed, checks = RemediationSafetyChecker.evaluate_preflight(action, all_devs)

            if not passed:
                action.status = "rejected"
                return {
                    "success": False,
                    "disclaimer": cls.DISCLAIMER,
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
                "disclaimer": cls.DISCLAIMER,
                "is_simulated": True,
                "message": f"Successfully simulated remediation action {action.action_id} on {action.device}.",
                "executed_commands": action.commands,
                "rollback_commands": action.rollback_commands,
                "checks": checks,
                "action": action.model_dump(),
            }

    @classmethod
    def approve_action(
        cls,
        action_id: str,
        operator: str = "human_operator",
        rationale: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a pending remediation action and execute as a simulated action only."""
        from netcoop.storage.db import get_remediation_action_log, record_hitl_decision

        log_entry = get_remediation_action_log(action_id)
        if not log_entry:
            return {"success": False, "message": f"Remediation action '{action_id}' not found."}

        record_hitl_decision(
            action_id=action_id,
            status="approved",
            operator=operator,
            rationale=rationale or "Approved by operator",
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
        )

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
        actor_user_id: Optional[str] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
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
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
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
        actor_user_id: Optional[str] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
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
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
        )
        return {
            "success": True,
            "action_id": action_id,
            "status": "modified",
            "modified_commands": new_commands,
            "operator": operator,
            "rationale": rationale,
        }

    @classmethod
    def simulate_proposed_action(
        cls,
        scenario_data: Dict[str, Any],
        action_name: str,
        device: Optional[str] = None,
        interface: Optional[str] = None,
        peer_device: Optional[str] = None,
        operator: str = "operator",
    ) -> Dict[str, Any]:
        """Apply a proposed action to in-memory scenario state and return before/after metrics.

        Supported actions:
        - 'rebalance traffic'
        - 'clear interface counters'
        - 'raise QoS priority'
        - 'fail over a link'
        - 'harmonize mtu'
        """
        if not getattr(settings, "feature_remediation_sim", True):
            raise RuntimeError("FEATURE_REMEDIATION_SIM is disabled in configuration.")

        norm_action = action_name.lower().replace("-", " ").replace("_", " ").strip()

        with network_sandbox_guard():
            state_copy = copy.deepcopy(scenario_data)

            # Determine candidate device if not provided
            target_dev = device or cls._find_candidate_device(state_copy) or "spine-01"
            target_iface = interface or "et-0/0/1"

            # Extract before metrics: both network-wide and target-device specific
            before_metrics = cls._extract_metrics_summary(state_copy)
            target_before_metrics = cls._extract_metrics_summary(state_copy, target_device=target_dev)

            action_item: RemediationActionItem

            if "rebalance" in norm_action:
                action_item = RemediationCatalog.create_rebalance_traffic_action(target_dev, target_iface)
                cls._apply_rebalance(state_copy, target_dev, target_iface)
            elif "clear" in norm_action and ("counter" in norm_action or "error" in norm_action):
                action_item = RemediationCatalog.create_clear_counters_action(target_dev, target_iface)
                cls._apply_clear_counters(state_copy, target_dev, target_iface)
            elif "qos" in norm_action or "priority" in norm_action:
                action_item = RemediationCatalog.create_raise_qos_action(target_dev, target_iface)
                cls._apply_raise_qos(state_copy, target_dev, target_iface)
            elif "fail" in norm_action or "failover" in norm_action:
                action_item = RemediationCatalog.create_failover_link_action(target_dev, target_iface, peer_device)
                cls._apply_failover(state_copy, target_dev, target_iface, peer_device)
            elif "mtu" in norm_action:
                action_item = RemediationCatalog.create_mtu_harmonization_action(target_dev, target_iface)
                cls._apply_mtu(state_copy, target_dev, target_iface)
            else:
                action_item = RemediationCatalog.create_rebalance_traffic_action(target_dev, target_iface)
                cls._apply_rebalance(state_copy, target_dev, target_iface)

            # Extract after metrics: both network-wide and target-device specific
            after_metrics = cls._extract_metrics_summary(state_copy)
            target_after_metrics = cls._extract_metrics_summary(state_copy, target_device=target_dev)

            # Calculate network-wide delta
            delta: Dict[str, float] = {}
            for k, before_val in before_metrics.items():
                if k in after_metrics and isinstance(before_val, (int, float)) and isinstance(after_metrics[k], (int, float)):
                    delta[k] = round(after_metrics[k] - before_val, 2)

            # Calculate target device delta
            target_delta: Dict[str, float] = {}
            for k, before_val in target_before_metrics.items():
                if k in target_after_metrics and isinstance(before_val, (int, float)) and isinstance(target_after_metrics[k], (int, float)):
                    target_delta[k] = round(target_after_metrics[k] - before_val, 2)

            all_devs = list(set([target_dev] + (action_item.blast_radius_devices or [])))
            safety_passed, checks = RemediationSafetyChecker.evaluate_preflight(action_item, all_devs)

            return {
                "status": "success",
                "disclaimer": cls.DISCLAIMER,
                "is_simulated": True,
                "action_type": action_item.title,
                "target_device": target_dev,
                "target_interface": target_iface,
                "safety_passed": safety_passed,
                "safety_checks": checks,
                "executed_commands": action_item.commands,
                "rollback_commands": action_item.rollback_commands,
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "delta": delta,
                "target_before_metrics": target_before_metrics,
                "target_after_metrics": target_after_metrics,
                "target_delta": target_delta,
                "simulated_scenario_state": state_copy,
            }

    @classmethod
    def _find_candidate_device(cls, state: Any) -> Optional[str]:
        """Find the device with the highest fault metrics in the scenario."""
        items = cls._get_items_list(state)
        # Find device with maximum interface errors, queue drops, or link utilization
        max_err = -1.0
        max_err_dev = None

        for item in items:
            if not isinstance(item, dict):
                continue
            dev = item.get("device") or item.get("device_id")
            val = 0.0
            if "metric" in item and "value" in item and isinstance(item["value"], (int, float)):
                if item["metric"] in ("interface_errors", "queue_drops", "link_utilization_pct"):
                    val = float(item["value"])
            else:
                m = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
                val = float(m.get("interface_errors", 0)) + float(m.get("queue_drops", 0)) + float(m.get("link_utilization_pct", 0))

            if val > max_err and dev:
                max_err = val
                max_err_dev = dev

        if max_err_dev:
            return max_err_dev

        if items and isinstance(items[0], dict):
            return items[0].get("device") or items[0].get("device_id")
        return None

    @classmethod
    def _extract_metrics_summary(cls, state: Any, target_device: Optional[str] = None) -> Dict[str, float]:
        """Extract summary metrics across scenario state supporting canonical, organizer, and list formats."""
        items = cls._get_items_list(state)
        metric_lists: Dict[str, List[float]] = {}
        non_metric_keys = {
            "timestamp", "timestamp_utc", "device_type", "status", "device_status",
            "device_id", "device", "interface", "metric", "source", "entity", "unit",
            "description", "id", "network_id", "incident_id"
        }

        for item in items:
            if not isinstance(item, dict):
                continue
            dev = item.get("device") or item.get("device_id")
            if target_device is not None and dev != target_device:
                continue

            # Case 1: Canonical item with "metric" and "value"
            if "metric" in item and "value" in item and isinstance(item["value"], (int, float)):
                m_name = item["metric"]
                metric_lists.setdefault(m_name, []).append(float(item["value"]))

            # Case 2: Nested "metrics" dict
            metrics_sub = item.get("metrics")
            if isinstance(metrics_sub, dict):
                for k, v in metrics_sub.items():
                    if isinstance(v, (int, float)):
                        metric_lists.setdefault(k, []).append(float(v))

            # Case 3: Flat dictionary of metrics
            for k, v in item.items():
                if k not in non_metric_keys and isinstance(v, (int, float)):
                    metric_lists.setdefault(k, []).append(float(v))

        summary: Dict[str, float] = {}
        for m, vals in metric_lists.items():
            if vals:
                summary[f"max_{m}"] = round(max(vals), 2)
                summary[f"avg_{m}"] = round(sum(vals) / len(vals), 2)
        return summary

    @classmethod
    def _apply_rebalance(cls, state: Any, device: str, interface: str) -> None:
        """Simulate traffic rebalance: reduce link utilization, clear queue drops and loss."""
        items = cls._get_items_list(state)
        for item in items:
            if not isinstance(item, dict):
                continue
            dev = item.get("device") or item.get("device_id")
            if dev == device or not device:
                if "metric" in item and "value" in item:
                    m = item["metric"]
                    if m == "link_utilization_pct":
                        item["value"] = round(float(item["value"]) * 0.45, 2)
                    elif m in ("queue_drops", "packet_loss_pct"):
                        item["value"] = 0.0
                    elif m == "latency_ms":
                        item["value"] = round(float(item["value"]) * 0.50, 2)

                target_dict = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
                if "link_utilization_pct" in target_dict:
                    target_dict["link_utilization_pct"] = round(float(target_dict["link_utilization_pct"]) * 0.45, 2)
                if "queue_drops" in target_dict:
                    target_dict["queue_drops"] = 0
                if "packet_loss_pct" in target_dict:
                    target_dict["packet_loss_pct"] = 0.0
                if "latency_ms" in target_dict:
                    target_dict["latency_ms"] = round(float(target_dict["latency_ms"]) * 0.50, 2)
                item["status"] = "Healthy"
                item["device_status"] = "online"

    @classmethod
    def _apply_clear_counters(cls, state: Any, device: str, interface: str) -> None:
        """Simulate clearing interface counters."""
        items = cls._get_items_list(state)
        for item in items:
            if not isinstance(item, dict):
                continue
            dev = item.get("device") or item.get("device_id")
            if dev == device or not device:
                if "metric" in item and "value" in item:
                    m = item["metric"]
                    if m in ("interface_errors", "crc_errors", "queue_drops", "link_flaps"):
                        item["value"] = 0.0

                target_dict = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
                if "interface_errors" in target_dict:
                    target_dict["interface_errors"] = 0
                if "queue_drops" in target_dict:
                    target_dict["queue_drops"] = 0
                if "link_flaps" in target_dict:
                    target_dict["link_flaps"] = 0
                item["status"] = "Healthy"
                item["device_status"] = "online"

    @classmethod
    def _apply_raise_qos(cls, state: Any, device: str, interface: str) -> None:
        """Simulate raising QoS priority: drop latency, jitter, and drops."""
        items = cls._get_items_list(state)
        for item in items:
            if not isinstance(item, dict):
                continue
            dev = item.get("device") or item.get("device_id")
            if dev == device or not device:
                if "metric" in item and "value" in item:
                    m = item["metric"]
                    if m == "latency_ms":
                        item["value"] = 12.0
                    elif m == "jitter_ms":
                        item["value"] = 1.5
                    elif m in ("queue_drops", "packet_loss_pct"):
                        item["value"] = 0.0

                target_dict = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
                if "latency_ms" in target_dict:
                    target_dict["latency_ms"] = 12.0
                if "jitter_ms" in target_dict:
                    target_dict["jitter_ms"] = 1.5
                if "queue_drops" in target_dict:
                    target_dict["queue_drops"] = 0
                if "packet_loss_pct" in target_dict:
                    target_dict["packet_loss_pct"] = 0.0
                item["status"] = "Healthy"
                item["device_status"] = "online"

    @classmethod
    def _apply_failover(
        cls, state: Any, device: str, interface: str, peer_device: Optional[str]
    ) -> None:
        """Simulate failing over link: active link drops to 0 utilization, peer link handles load."""
        items = cls._get_items_list(state)
        for item in items:
            if not isinstance(item, dict):
                continue
            dev = item.get("device") or item.get("device_id")
            if dev == device or not device:
                if "metric" in item and "value" in item:
                    m = item["metric"]
                    if m in ("link_utilization_pct", "queue_drops", "packet_loss_pct", "interface_errors"):
                        item["value"] = 0.0

                target_dict = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
                if "link_utilization_pct" in target_dict:
                    target_dict["link_utilization_pct"] = 0.0
                if "queue_drops" in target_dict:
                    target_dict["queue_drops"] = 0
                if "packet_loss_pct" in target_dict:
                    target_dict["packet_loss_pct"] = 0.0
                if "interface_errors" in target_dict:
                    target_dict["interface_errors"] = 0
                item["status"] = "Healthy"
                item["device_status"] = "online"

            elif peer_device and dev == peer_device:
                if "metric" in item and item.get("metric") == "link_utilization_pct":
                    item["value"] = round(min(80.0, float(item["value"]) + 25.0), 2)

                target_dict = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
                if "link_utilization_pct" in target_dict:
                    target_dict["link_utilization_pct"] = round(min(80.0, float(target_dict["link_utilization_pct"]) + 25.0), 2)

    @classmethod
    def _apply_mtu(cls, state: Any, device: str, interface: str) -> None:
        """Simulate MTU harmonization: packet loss drops to 0."""
        items = cls._get_items_list(state)
        for item in items:
            if not isinstance(item, dict):
                continue
            dev = item.get("device") or item.get("device_id")
            if dev == device or not device:
                if "metric" in item and item.get("metric") == "packet_loss_pct":
                    item["value"] = 0.0

                target_dict = item.get("metrics") if isinstance(item.get("metrics"), dict) else item
                if "packet_loss_pct" in target_dict:
                    target_dict["packet_loss_pct"] = 0.0
                item["status"] = "Healthy"
                item["device_status"] = "online"

    @classmethod
    def _get_items_list(cls, state: Any) -> List[Any]:
        if isinstance(state, dict):
            if "telemetry" in state and isinstance(state["telemetry"], list):
                return state["telemetry"]
            if "records" in state and isinstance(state["records"], list):
                return state["records"]
        elif isinstance(state, list):
            return state
        return []
