export interface EvidenceItem {
  source_agent: string;
  category: string;
  finding: string;
  entity: string;
  metric_name?: string;
  value?: number | string | boolean | null;
  unit?: string;
  severity: "info" | "warning" | "critical";
  timestamp?: string;
}

export interface UncertaintyEvaluation {
  score: number;
  reasons: string[];
  missing_evidence: string[];
  alternative_hypotheses: Array<{ cause: string; confidence: number }>;
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
}

export interface UnifiedDiagnosticReport {
  incident_id: string;
  network_id: string;
  timestamp_utc: string;
  status: "diagnosed" | "insufficient_evidence" | "inconclusive" | "benign";
  probable_cause: string | null;
  confidence: number;
  affected_devices: string[];
  affected_interfaces: string[];
  evidence: EvidenceItem[];
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
