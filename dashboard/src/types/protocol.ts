export type DataProvenance =
  | "LIVE"
  | "SYNTHETIC_DEMO"
  | "ORGANIZER_SAMPLE"
  | "CACHED_STALE"
  | "OFFLINE";

export interface EvidenceItem {
  evidence_id?: string;
  source_agent: string;
  category: string;
  finding: string;
  interpretation?: string;
  entity: string;
  metric_name?: string;
  metric?: string;
  value?: number | string | boolean | null;
  unit?: string;
  severity: "info" | "warning" | "critical";
  timestamp?: string;
  timestamp_window?: string;
  weight?: number;
  observation_id?: string;
  message_id?: string;
  correlation_id?: string;
  provenance?: Record<string, any>;
}

export interface UncertaintyEvaluation {
  score: number;
  reasons: string[];
  missing_evidence: string[];
  alternative_hypotheses: Array<{
    cause: string;
    confidence: number;
    discriminating_test?: string;
    supporting_evidence_ids?: string[];
    refuting_evidence_ids?: string[];
  }>;
}

export interface RemediationAction {
  action_id: string;
  title: string;
  description: string;
  device: string;
  commands: string[];
  rollback_commands: string[];
  risk_level: "low" | "medium" | "high";
  blast_radius_devices: string[];
  is_simulated: boolean;
  status: "recommended" | "pending_approval" | "simulated_success" | "simulated_executed" | "rejected" | string;
  action?: string;
}

export type CanonicalCauseKey =
  | "LINK_CONGESTION"
  | "WEAK_WIFI_SIGNAL"
  | "ETHERNET_INTERFACE_FAULT"
  | "DEVICE_CPU_OVERLOAD"
  | "DNS_FAILURE"
  | "DHCP_FAILURE"
  | "UPSTREAM_FAILURE_CASCADE"
  | "DEVICE_HARDWARE_FAILURE"
  | "MTU_MISMATCH_BLACKHOLE"
  | "BGP_ROUTE_FLAP_DAMPING"
  | "OPTICAL_TRANSCEIVER_DEGRADATION"
  | "STP_SPLIT_BRAIN_LOOP"
  | "NO_FAULT";

export interface UnifiedDiagnosticReport {
  incident_id: string;
  network_id: string;
  timestamp_utc: string;
  status: "diagnosed" | "insufficient_evidence" | "inconclusive" | "benign" | "failed" | "invalid" | string;
  probable_cause: string | null;
  suspected_root_cause?: string | null;
  hypothesis_key?: CanonicalCauseKey | string;
  confidence: number;
  is_confidence_calibrated?: boolean;
  confidence_type?: string;
  affected_devices: string[];
  affected_interfaces: string[];
  evidence: EvidenceItem[];
  evidence_sources?: string[];
  uncertainty: UncertaintyEvaluation;
  remediation_actions: RemediationAction[];
  summary: string;
  processing_time_ms: number;
  causal_chain?: string[];
  conflicts_resolved?: Array<Record<string, any>>;
  limitations?: string[];
  provenance?: Record<string, any>;
  confidence_breakdown?: Record<string, number>;
  conformal_prediction_set?: string[];
  confidence_category?: string;
}

export interface EnvelopeLogItem {
  id: number;
  message_id: string;
  correlation_id: string;
  timestamp_utc: string;
  sender: string;
  recipient: string;
  message_type: string;
  priority: string;
  payload: any;
  context: any;
}

export interface ScenarioMeta {
  filename: string;
  incident_id: string;
  network_id: string;
  description: string;
}
