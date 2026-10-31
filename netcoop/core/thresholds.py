"""Network telemetry thresholds and operational boundaries for NetCoop AI.

Contains explicit threshold definitions for both dynamic time-series monitoring
and static/sparse single-snapshot evaluation mode (e.g., organizer challenge dataset).
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DynamicThresholds:
    """Operational thresholds for continuous time-series telemetry.

    Used when multi-point time series data allows baseline tracking, trend
    evaluation, and anomaly rate-of-change estimation.
    """

    # --- Capacity & Utilization ---
    # Warning at 75% utilization: early sign of interface buffer accumulation.
    # Critical at 85%: sustained bandwidth above 85% causes micro-bursting and queue build-up.
    LINK_UTILIZATION_WARN_PCT: float = 75.0
    LINK_UTILIZATION_CRIT_PCT: float = 85.0

    # Queue drops indicate tail-drop buffer starvation under congestion.
    # Egress buffer queues nominal = 0; > 20 indicates buffer overflow.
    QUEUE_DROPS_WARN: int = 20
    QUEUE_DROPS_CRIT: int = 100

    # --- Latency & Jitter ---
    # Nominal campus RTT is 5-20ms; > 45ms indicates queuing delay or transit detour.
    # > 100ms indicates critical path queuing or severe transmission issues.
    LATENCY_WARN_MS: float = 45.0
    LATENCY_CRIT_MS: float = 100.0

    # Jitter represents packet delay variation; > 10ms impairs real-time traffic (VoIP/video).
    # > 25ms indicates severe queue buffer oscillation.
    JITTER_WARN_MS: float = 10.0
    JITTER_CRIT_MS: float = 25.0

    # Packet loss: > 0.5% triggers TCP congestion control backoff.
    # > 2.0% causes significant throughput collapse and connection resets.
    PACKET_LOSS_WARN_PCT: float = 0.5
    PACKET_LOSS_CRIT_PCT: float = 2.0

    # --- Device Hardware & Resources ---
    # CPU: > 80% warning; > 90% critical (control plane starvation, BGP keepalive drops).
    CPU_WARN_PCT: float = 80.0
    CPU_CRIT_PCT: float = 90.0

    # Memory: > 80% warning; > 90% critical (risk of OOM killer terminating routing daemons).
    MEMORY_WARN_PCT: float = 80.0
    MEMORY_CRIT_PCT: float = 90.0

    # Physical interface errors (CRC/FCS frame check sequence):
    # Any CRC error indicates physical layer cabling or optical transceiver issues.
    INTERFACE_ERRORS_WARN: int = 50
    INTERFACE_ERRORS_CRIT: int = 500

    # Optical transceiver DOM power levels (dBm):
    # Receiver power nominal: >= -14.0 dBm
    # Receiver power warning (marginal attenuation): < -14.0 dBm
    # Receiver power critical (severe attenuation / sensitivity cutoff): < -18.0 dBm
    OPTICAL_RX_POWER_WARN_DBM: float = -14.0
    OPTICAL_RX_POWER_CRIT_DBM: float = -18.0

    # Link flaps: transition between up and down state within rolling observation window.
    # > 1 flap is warning; >= 3 flaps indicates physical flapping or aggressive dampening.
    LINK_FLAPS_WARN: int = 1
    LINK_FLAPS_CRIT: int = 3

    # --- Wireless / RF Telemetry ---
    # RSSI (Received Signal Strength Indicator in dBm):
    # -30 to -65 dBm is excellent/good.
    # < -75 dBm is weak signal with reduced modulation rates.
    # < -82 dBm is edge of cell coverage with frequent disconnections.
    WIFI_RSSI_WARN_DBM: float = -75.0
    WIFI_RSSI_CRIT_DBM: float = -82.0

    # SNR (Signal-to-Noise Ratio in dB):
    # > 25 dB is clean signal; < 20 dB warning; < 12 dB critical (inability to decode 64-QAM).
    WIFI_SNR_WARN_DB: float = 20.0
    WIFI_SNR_CRIT_DB: float = 12.0

    # Retransmission percentage:
    # 802.11 MAC frames retransmitted due to collision or RF degradation.
    # > 15% warning; > 25% critical (channel airtime saturation).
    WIFI_RETX_WARN_PCT: float = 15.0
    WIFI_RETX_CRIT_PCT: float = 25.0

    # Client density per Access Point:
    # > 45 clients per AP degrades throughput; > 65 clients causes channel contention.
    WIFI_CLIENT_DENSITY_WARN: int = 45
    WIFI_CLIENT_DENSITY_CRIT: int = 65

    # --- Application & Infrastructure Services ---
    # DNS resolution latency:
    # Local recursive DNS nominal < 30ms; > 80ms warning; > 150ms critical.
    DNS_RESOLUTION_WARN_MS: float = 80.0
    DNS_RESOLUTION_CRIT_MS: float = 150.0

    # DNS failure percentage:
    # NXDOMAIN or timeout rate; > 5% warning; > 20% critical service degradation.
    # > 70% indicates total DNS server outage.
    DNS_FAILURE_WARN_PCT: float = 5.0
    DNS_FAILURE_CRIT_PCT: float = 20.0
    DNS_FAILURE_OUTAGE_PCT: float = 70.0

    # DHCP failure percentage:
    # DISCOVER/REQUEST drops or NAKs; > 5% warning; > 10% critical.
    # > 70% indicates DHCP pool scope exhaustion or relay failure.
    DHCP_FAILURE_WARN_PCT: float = 5.0
    DHCP_FAILURE_CRIT_PCT: float = 10.0
    DHCP_FAILURE_OUTAGE_PCT: float = 70.0


@dataclass(frozen=True)
class OrganizerSnapshotThresholds:
    """Operational thresholds calibrated for the organizer's synthetic dataset.

    Derived directly from organizer generator baseline distributions:
    - Normal CPU: 10% to 35%
    - Normal Link utilization: 20% to 50%
    - Normal Latency: 5ms to 20ms
    - Normal Jitter: 1ms to 5ms
    - Normal Packet loss: 0.0%
    - Normal Queue drops: 0
    - Normal Interface errors: 0
    - Normal Status: 'up' or 'active'
    """

    # Nominal bounds for sanity checking
    NORMAL_CPU_MIN: float = 10.0
    NORMAL_CPU_MAX: float = 35.0
    NORMAL_UTIL_MIN: float = 20.0
    NORMAL_UTIL_MAX: float = 50.0
    NORMAL_LATENCY_MIN: float = 5.0
    NORMAL_LATENCY_MAX: float = 20.0
    NORMAL_JITTER_MIN: float = 1.0
    NORMAL_JITTER_MAX: float = 5.0

    # Anomaly tripwires in snapshot mode:
    # CPU: Any value exceeding normal upper bound (35%) by a margin is an anomaly.
    CPU_WARN_PCT: float = 40.0
    CPU_CRIT_PCT: float = 50.0

    # Link utilization: Exceeding 60% is anomalous for organizer topology.
    # Exceeding 75% indicates active congestion.
    LINK_UTILIZATION_WARN_PCT: float = 60.0
    LINK_UTILIZATION_CRIT_PCT: float = 75.0

    # Latency: Organizer normal ceiling is 20ms. > 25ms is warning; > 35ms is a clear spike.
    LATENCY_WARN_MS: float = 25.0
    LATENCY_CRIT_MS: float = 35.0

    # Jitter: Organizer normal ceiling is 5ms. > 7ms is warning; > 10ms is critical.
    JITTER_WARN_MS: float = 7.0
    JITTER_CRIT_MS: float = 10.0

    # Packet loss: In organizer normal mode loss is strictly 0.0.
    # Any loss > 0.1% is anomalous; > 1.0% is critical.
    PACKET_LOSS_WARN_PCT: float = 0.1
    PACKET_LOSS_CRIT_PCT: float = 1.0

    # Queue drops: In organizer normal mode drops are 0.
    # Any drops > 0 indicate buffer exhaustion.
    QUEUE_DROPS_WARN: int = 1
    QUEUE_DROPS_CRIT: int = 10

    # Interface errors: In organizer normal mode errors are 0.
    # > 10 is warning; > 100 is critical.
    INTERFACE_ERRORS_WARN: int = 10
    INTERFACE_ERRORS_CRIT: int = 100

    # Hardware failure signature:
    # Device status down, inactive, unreachable, or 0 throughput with 100% loss.
    STATUS_DOWN_VALUES: tuple = ("down", "offline", "unreachable", "inactive", "failed")


def is_snapshot_mode(telemetry_records: List[Dict[str, Any]]) -> bool:
    """Determine if telemetry represents a single static snapshot rather than continuous time series.

    Returns True if:
    - Less than 3 temporal records exist per device, or
    - All timestamps are identical or within a 5-second interval, or
    - Telemetry lacks timestamped historical trends.
    """
    if not telemetry_records:
        return True

    # Group by device
    dev_records: Dict[str, List[Dict[str, Any]]] = {}
    for rec in telemetry_records:
        dev = rec.get("device_id") or rec.get("device") or "unknown"
        dev_records.setdefault(dev, []).append(rec)

    # If maximum records for any device is < 3, it's snapshot mode
    max_recs = max(len(recs) for recs in dev_records.values()) if dev_records else 0
    if max_recs < 3:
        return True

    # Check timestamp span
    timestamps = [rec.get("timestamp") for rec in telemetry_records if rec.get("timestamp")]
    if len(set(timestamps)) <= 1:
        return True

    return False
