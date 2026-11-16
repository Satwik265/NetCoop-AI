"""Feature extraction per device window including statistical, temporal, and topological signals."""

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class WindowFeatureExtractor:
    """Extracts statistical, temporal slope, baseline delta, and topology features from telemetry windows."""

    NUMERIC_METRICS = [
        "latency_ms",
        "jitter_ms",
        "packet_loss_pct",
        "link_utilization_pct",
        "cpu_pct",
        "memory_pct",
        "queue_drops",
        "interface_errors",
        "link_flaps",
        "wifi_rssi_dbm",
        "wifi_retransmission_pct",
        "dns_resolution_ms",
        "dns_failure_pct",
        "dhcp_failure_pct",
    ]

    BASELINES = {
        "latency_ms": 5.0,
        "jitter_ms": 1.0,
        "packet_loss_pct": 0.0,
        "link_utilization_pct": 25.0,
        "cpu_pct": 25.0,
        "memory_pct": 35.0,
        "queue_drops": 0.0,
        "interface_errors": 0.0,
        "link_flaps": 0.0,
        "wifi_rssi_dbm": -50.0,
        "wifi_retransmission_pct": 2.0,
        "dns_resolution_ms": 20.0,
        "dns_failure_pct": 0.0,
        "dhcp_failure_pct": 0.0,
    }

    BOUNDS = {
        "latency_ms": 20.0,
        "jitter_ms": 5.0,
        "packet_loss_pct": 1.0,
        "link_utilization_pct": 80.0,
        "cpu_pct": 75.0,
        "memory_pct": 80.0,
        "queue_drops": 10.0,
        "interface_errors": 10.0,
        "link_flaps": 1.0,
        "wifi_rssi_dbm": -75.0,
        "wifi_retransmission_pct": 15.0,
        "dns_resolution_ms": 100.0,
        "dns_failure_pct": 5.0,
        "dhcp_failure_pct": 5.0,
    }

    ROLES = ["router", "switch", "access_point", "host"]
    ROLE_GROUPS = ["network_wide", "router", "switch", "access_point", "host"]

    @classmethod
    def get_feature_names(cls) -> List[str]:
        """Return ordered canonical list of feature names."""
        names = []
        for m in cls.NUMERIC_METRICS:
            names.extend([
                f"{m}_mean",
                f"{m}_p95",
                f"{m}_slope",
                f"{m}_delta_baseline",
                f"{m}_missing_frac",
            ])
        # Topology features
        names.extend([
            "upstream_utilization",
            "neighbour_mean_loss",
            "neighbour_mean_util",
            "is_single_snapshot",
        ])
        return names

    @classmethod
    def compute_slope(cls, values: List[float], timestamps: List[float]) -> float:
        """Compute simple linear regression slope dy/dt."""
        if len(values) < 2 or len(timestamps) < 2:
            return float("nan")
        t_arr = np.array(timestamps)
        v_arr = np.array(values)
        t_diff = t_arr[-1] - t_arr[0]
        if t_diff <= 0.0:
            return 0.0
        # Linear regression slope: cov(t, y) / var(t)
        cov = np.cov(t_arr, v_arr)[0, 1] if len(t_arr) > 2 else (v_arr[-1] - v_arr[0]) / t_diff
        var_t = np.var(t_arr)
        if var_t == 0.0 or math.isnan(cov):
            return (v_arr[-1] - v_arr[0]) / max(1.0, t_diff)
        return float(cov / var_t)

    @classmethod
    def extract_device_features(
        cls,
        device_id: str,
        records: List[Dict[str, Any]],
        topology: Optional[Dict[str, Any]] = None,
        all_device_records: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Extract feature vector for a specific device window.

        Returns:
            (feature_vector, metadata_dict)
        """
        is_single = (len(records) <= 1)
        feat_map: Dict[str, float] = {}

        # 1. Metric features
        for metric in cls.NUMERIC_METRICS:
            vals: List[float] = []
            ts_vals: List[float] = []
            baseline = cls.BASELINES.get(metric, 0.0)

            total_points = len(records)
            missing_count = 0

            for idx, r in enumerate(records):
                v = r.get(metric)
                if v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                    vals.append(float(v))
                    # Extract timestamp in seconds relative to first record
                    ts_vals.append(float(idx * 5.0))  # standard 5s sampling interval
                else:
                    missing_count += 1

            missing_frac = float(missing_count) / max(1, total_points)
            feat_map[f"{metric}_missing_frac"] = missing_frac

            if vals:
                mean_val = float(np.mean(vals))
                p95_val = float(np.percentile(vals, 95))
                delta_val = mean_val - baseline
                slope_val = cls.compute_slope(vals, ts_vals) if not is_single else float("nan")
            else:
                mean_val = baseline
                p95_val = baseline
                delta_val = 0.0
                slope_val = float("nan")

            feat_map[f"{metric}_mean"] = mean_val
            feat_map[f"{metric}_p95"] = p95_val
            feat_map[f"{metric}_slope"] = slope_val
            feat_map[f"{metric}_delta_baseline"] = delta_val

        # 2. Topology features
        upstream_util = float("nan")
        neighbour_loss = float("nan")
        neighbour_util = float("nan")

        if topology and "links" in topology:
            neighbours: List[str] = []
            upstream_node: Optional[str] = None

            for link in topology["links"]:
                src = link.get("source")
                tgt = link.get("target")
                if src == device_id:
                    neighbours.append(tgt)
                elif tgt == device_id:
                    neighbours.append(src)
                    upstream_node = src

            if all_device_records:
                # Neighbour loss & util
                n_losses = []
                n_utils = []
                for n_id in neighbours:
                    n_recs = all_device_records.get(n_id, [])
                    for nr in n_recs:
                        nl = nr.get("packet_loss_pct")
                        nu = nr.get("link_utilization_pct")
                        if nl is not None and not math.isnan(nl):
                            n_losses.append(float(nl))
                        if nu is not None and not math.isnan(nu):
                            n_utils.append(float(nu))

                if n_losses:
                    neighbour_loss = float(np.mean(n_losses))
                if n_utils:
                    neighbour_util = float(np.mean(n_utils))

                if upstream_node and upstream_node in all_device_records:
                    u_recs = all_device_records[upstream_node]
                    u_utils = [float(ur["link_utilization_pct"]) for ur in u_recs if ur.get("link_utilization_pct") is not None]
                    if u_utils:
                        upstream_util = float(np.mean(u_utils))

        feat_map["upstream_utilization"] = upstream_util
        feat_map["neighbour_mean_loss"] = neighbour_loss
        feat_map["neighbour_mean_util"] = neighbour_util
        feat_map["is_single_snapshot"] = 1.0 if is_single else 0.0

        names = cls.get_feature_names()
        vector = np.array([feat_map.get(n, float("nan")) for n in names], dtype=np.float32)

        meta = {
            "device_id": device_id,
            "record_count": len(records),
            "is_single_snapshot": is_single,
        }
        return vector, meta

    @classmethod
    def extract_incident_features(cls, incident: Dict[str, Any]) -> Tuple[np.ndarray, List[str], List[Dict[str, Any]]]:
        """Extract multi-device aggregated feature matrix from a full incident."""
        telemetry = incident.get("telemetry", [])
        topology = incident.get("topology", {})

        # Group by device
        by_device: Dict[str, List[Dict[str, Any]]] = {}
        for r in telemetry:
            d_id = r.get("device_id", "unknown_device")
            if d_id not in by_device:
                by_device[d_id] = []
            by_device[d_id].append(r)

        vectors: List[np.ndarray] = []
        device_ids: List[str] = []
        metas: List[Dict[str, Any]] = []

        for d_id, recs in by_device.items():
            vec, meta = cls.extract_device_features(
                device_id=d_id,
                records=recs,
                topology=topology,
                all_device_records=by_device,
            )
            vectors.append(vec)
            device_ids.append(d_id)
            metas.append(meta)

        if not vectors:
            # Fallback for empty incident
            names = cls.get_feature_names()
            empty_vec = np.full(len(names), np.nan, dtype=np.float32)
            return np.array([empty_vec]), ["unknown_device"], [{"device_id": "unknown_device", "record_count": 0, "is_single_snapshot": True}]

        matrix = np.vstack(vectors)
        return matrix, device_ids, metas

    @classmethod
    def get_topology_invariant_feature_names(cls) -> List[str]:
        """Ordered list of topology-invariant feature names."""
        names = []
        for grp in cls.ROLE_GROUPS:
            for m in cls.NUMERIC_METRICS:
                names.append(f"{grp}_{m}_max")
                names.append(f"{grp}_{m}_mean")
                names.append(f"{grp}_{m}_p50")
                names.append(f"{grp}_{m}_p95")
                names.append(f"{grp}_{m}_count_over_bound")

        for r in cls.ROLES:
            names.append(f"count_{r}_devices")
        names.extend([
            "total_devices",
            "total_links",
            "device_status_offline_count",
            "device_status_degraded_count",
        ])
        return names

    @classmethod
    def extract_topology_invariant_features(cls, incident: Dict[str, Any]) -> Tuple[np.ndarray, List[str]]:
        """Extract permutation- and size-invariant aggregated feature vector from an incident.

        Computes per-role and network-wide maximums, means, percentiles (p50, p95),
        and threshold-exceedance device counts across equipment roles.
        """
        telemetry = incident.get("telemetry", [])
        topology = incident.get("topology", {})
        nodes = topology.get("nodes", []) if isinstance(topology, dict) else []
        links = topology.get("links", []) if isinstance(topology, dict) else []

        # 1. Map device roles
        device_roles: Dict[str, str] = {}
        for n in nodes:
            d_id = n.get("id")
            if not d_id:
                continue
            r = str(getattr(n.get("role", n.get("type", "")), "value", n.get("role", n.get("type", "")))).lower()
            if r in cls.ROLES:
                device_roles[d_id] = r
            elif "rtr" in d_id.lower() or "router" in d_id.lower() or "spine" in d_id.lower():
                device_roles[d_id] = "router"
            elif "sw" in d_id.lower() or "switch" in d_id.lower() or "leaf" in d_id.lower():
                device_roles[d_id] = "switch"
            elif "ap" in d_id.lower() or "wifi" in d_id.lower():
                device_roles[d_id] = "access_point"
            else:
                device_roles[d_id] = "host"

        # 2. Group telemetry records by device and determine role / status
        by_device: Dict[str, List[Dict[str, Any]]] = {}
        device_status_map: Dict[str, str] = {}

        for rec in telemetry:
            d_id = rec.get("device_id", "unknown")
            if d_id not in by_device:
                by_device[d_id] = []
            by_device[d_id].append(rec)

            if d_id not in device_roles:
                dev_type = str(getattr(rec.get("device_type"), "value", rec.get("device_type", ""))).lower()
                if dev_type in cls.ROLES:
                    device_roles[d_id] = dev_type
                elif "rtr" in d_id.lower() or "router" in d_id.lower() or "spine" in d_id.lower():
                    device_roles[d_id] = "router"
                elif "sw" in d_id.lower() or "switch" in d_id.lower() or "leaf" in d_id.lower():
                    device_roles[d_id] = "switch"
                elif "ap" in d_id.lower() or "wifi" in d_id.lower():
                    device_roles[d_id] = "access_point"
                else:
                    device_roles[d_id] = "host"

            st = str(getattr(rec.get("device_status"), "value", rec.get("device_status", ""))).lower()
            if st in ("offline", "degraded"):
                device_status_map[d_id] = st

        # 3. For each device, compute metric values (mean across observations)
        device_metrics: Dict[str, Dict[str, float]] = {}
        for d_id, recs in by_device.items():
            device_metrics[d_id] = {}
            for m in cls.NUMERIC_METRICS:
                vals = [
                    float(r[m]) for r in recs
                    if r.get(m) is not None and not (isinstance(r[m], float) and (math.isnan(r[m]) or math.isinf(r[m])))
                ]
                if vals:
                    device_metrics[d_id][m] = float(np.mean(vals))
                else:
                    device_metrics[d_id][m] = float("nan")

        # 4. Compute per-group aggregates
        feat_dict: Dict[str, float] = {}

        for grp in cls.ROLE_GROUPS:
            if grp == "network_wide":
                target_devs = list(by_device.keys())
            else:
                target_devs = [d for d in by_device if device_roles.get(d) == grp]

            for m in cls.NUMERIC_METRICS:
                bound = cls.BOUNDS.get(m, 0.0)
                m_vals = [
                    device_metrics[d][m] for d in target_devs
                    if d in device_metrics and not math.isnan(device_metrics[d].get(m, float("nan")))
                ]

                if m_vals:
                    val_max = float(np.max(m_vals))
                    val_mean = float(np.mean(m_vals))
                    val_p50 = float(np.percentile(m_vals, 50))
                    val_p95 = float(np.percentile(m_vals, 95))
                    if m == "wifi_rssi_dbm":
                        cnt_bound = sum(1 for v in m_vals if v < bound)
                    else:
                        cnt_bound = sum(1 for v in m_vals if v >= bound)
                else:
                    val_max = 0.0
                    val_mean = 0.0
                    val_p50 = 0.0
                    val_p95 = 0.0
                    cnt_bound = 0

                feat_dict[f"{grp}_{m}_max"] = val_max
                feat_dict[f"{grp}_{m}_mean"] = val_mean
                feat_dict[f"{grp}_{m}_p50"] = val_p50
                feat_dict[f"{grp}_{m}_p95"] = val_p95
                feat_dict[f"{grp}_{m}_count_over_bound"] = float(cnt_bound)

        # 5. Device and link count summary features
        for r in cls.ROLES:
            count_r = sum(1 for d in by_device if device_roles.get(d) == r)
            feat_dict[f"count_{r}_devices"] = float(count_r)

        feat_dict["total_devices"] = float(len(by_device))
        feat_dict["total_links"] = float(len(links))
        feat_dict["device_status_offline_count"] = float(sum(1 for s in device_status_map.values() if s == "offline"))
        feat_dict["device_status_degraded_count"] = float(sum(1 for s in device_status_map.values() if s == "degraded"))

        names = cls.get_topology_invariant_feature_names()
        vec = np.array([feat_dict.get(n, 0.0) for n in names], dtype=np.float32)
        return vec, names
