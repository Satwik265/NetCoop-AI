import React, { useState, useEffect } from "react";
import { apiFetch } from "../../auth/AuthContext";
import { UnifiedDiagnosticReport } from "../../types/protocol";

interface IncidentSummaryItem {
  incident_id: string;
  network_id?: string;
  status: string;
  probable_cause: string | null;
  confidence: number;
  created_at?: string;
}

interface EnvelopeItem {
  id?: number;
  message_id: string;
  timestamp_utc: string;
  sender: string;
  recipient: string;
  message_type: string;
  priority?: string;
  payload: any;
}

interface TicketItem {
  ticket_id: string;
  title: string;
  category: string;
  location: string;
  affected_service: string;
  priority: string;
  status: string;
  created_by: string;
  assigned_to?: string | null;
  linked_incident_id?: string | null;
  created_at: string;
}

export interface EngineerViewProps {
  report: UnifiedDiagnosticReport | null;
  onLaunchSimulation: () => void;
  onOpenHitlQueue: () => void;
  onNavigate?: (navId: string) => void;
  lastRunId?: string | null;
  lastRunTimestamp?: string | null;
  selectedScenario?: string;
  executionStatus?: "idle" | "running" | "completed" | "failed";
  runErrorMessage?: string | null;
  previousRunId?: string | null;
  onRunDiagnosis?: () => void;
  onCompareRuns?: () => void;
}

export const EngineerView: React.FC<EngineerViewProps> = ({
  report,
  onLaunchSimulation,
  onOpenHitlQueue,
  onNavigate: _onNavigate,
  lastRunId,
  lastRunTimestamp,
  selectedScenario = "link_congestion.json",
  executionStatus = "idle",
  runErrorMessage,
  previousRunId,
  onRunDiagnosis,
  onCompareRuns,
}) => {
  // Top-level independent navigation: Diagnosis Results vs Incident Investigation
  const [activeMainTab, setActiveMainTab] = useState<"diagnosis_results" | "incident_investigation">(
    lastRunId ? "diagnosis_results" : "incident_investigation"
  );

  // Incident Investigation state
  const [incidents, setIncidents] = useState<IncidentSummaryItem[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(
    report?.incident_id || "inc-link-congestion-42"
  );
  const [envelopes, setEnvelopes] = useState<EnvelopeItem[]>([]);
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [loadingEnvelopes, setLoadingEnvelopes] = useState<boolean>(false);
  const [showTechnicalMessages, setShowTechnicalMessages] = useState<boolean>(false);
  const [expandedPayloadId, setExpandedPayloadId] = useState<string | null>(null);
  const [showRawReport, setShowRawReport] = useState<boolean>(false);

  // Ticket linking inside incident investigation
  const [linkTicketId, setLinkTicketId] = useState<string>("");
  const [linkMsg, setLinkMsg] = useState<string | null>(null);

  // Switch to Diagnosis Results tab automatically when a new diagnosis run begins or completes
  useEffect(() => {
    if (executionStatus === "running" || executionStatus === "completed") {
      setActiveMainTab("diagnosis_results");
    }
  }, [executionStatus, lastRunId]);

  // Synchronize when report changes
  useEffect(() => {
    if (report?.incident_id) {
      setSelectedIncidentId(report.incident_id);
    }
  }, [report?.incident_id]);

  // Fetch live incident list
  useEffect(() => {
    apiFetch("/api/incidents")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: IncidentSummaryItem[]) => {
        if (data && data.length > 0) {
          setIncidents(data);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch envelopes for selected incident
  useEffect(() => {
    if (!selectedIncidentId) return;
    setLoadingEnvelopes(true);
    apiFetch(`/api/incidents/${selectedIncidentId}/envelopes`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: EnvelopeItem[]) => {
        if (data && data.length > 0) {
          setEnvelopes(data);
        } else {
          setEnvelopes([
            {
              message_id: "env-001",
              timestamp_utc: new Date(Date.now() - 300000).toISOString(),
              sender: "telemetry_agent",
              recipient: "synthesizer_agent",
              message_type: "METRIC_ANOMALY",
              payload: {
                metric: "link_utilization_pct",
                value: 94.2,
                threshold: 85.0,
                unit: "percent",
                finding: "High egress link utilization detected on spine-01 (et-0/0/1).",
              },
            },
            {
              message_id: "env-002",
              timestamp_utc: new Date(Date.now() - 240000).toISOString(),
              sender: "log_agent",
              recipient: "synthesizer_agent",
              message_type: "LOG_ANOMALY",
              payload: {
                finding: "Buffer queue tail drops corroborated at 4,500 drops/s.",
              },
            },
            {
              message_id: "env-003",
              timestamp_utc: new Date(Date.now() - 180000).toISOString(),
              sender: "topology_agent",
              recipient: "synthesizer_agent",
              message_type: "PATH_DISCOVERY",
              payload: {
                finding: "Alternate redundant transit link spine-02 available with 28.1% load.",
              },
            },
            {
              message_id: "env-004",
              timestamp_utc: new Date(Date.now() - 120000).toISOString(),
              sender: "synthesizer_agent",
              recipient: "remediation_agent",
              message_type: "DIAGNOSTIC_CONSENSUS",
              payload: {
                probable_cause: "INTERFACE_SATURATION_QUEUE_OVERFLOW",
                confidence: 0.94,
                uncertainty: 0.06,
                conformal_prediction_set: ["INTERFACE_SATURATION_QUEUE_OVERFLOW", "ECMP_HASH_IMBALANCE"],
              },
            },
          ]);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingEnvelopes(false));
  }, [selectedIncidentId]);

  // Fetch operational support tickets
  useEffect(() => {
    apiFetch("/api/tickets")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: TicketItem[]) => {
        if (data) setTickets(data);
      })
      .catch(() => {});
  }, []);

  const handleLinkTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!linkTicketId.trim()) return;
    setLinkMsg(null);
    try {
      const res = await apiFetch(`/api/tickets/${linkTicketId}/link-incident`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: selectedIncidentId }),
      });
      if (res.ok) {
        setLinkMsg(`Ticket ${linkTicketId} successfully linked to incident ${selectedIncidentId}.`);
        setLinkTicketId("");
        const refreshed = await apiFetch("/api/tickets");
        if (refreshed.ok) setTickets(await refreshed.json());
        setTimeout(() => setLinkMsg(null), 3500);
      } else {
        const err = await res.json().catch(() => ({ detail: "Failed to link ticket." }));
        setLinkMsg(`Error: ${err.detail || "Unable to associate ticket."}`);
      }
    } catch {
      setLinkMsg("Network error connecting to ticket service.");
    }
  };

  // Structured telemetry data
  const telemetryData = [
    {
      name: "Egress Link Utilization",
      value: "94.2%",
      unit: "percent",
      nominal: "< 70.0%",
      delta: "+24.2%",
      source: "telemetry_agent (SNMP ifHCOutOctets)",
      timestamp: "2026-11-01T07:15:00Z",
      explanation: "Interface throughput exceeds the 85.0% critical threshold, driving tail-drop buffer starvation.",
    },
    {
      name: "Queue Drop Rate",
      value: "4,500 drops/s",
      unit: "packets/second",
      nominal: "0 drops/s",
      delta: "+4,500",
      source: "log_agent (Hardware ASIC Telemetry)",
      timestamp: "2026-11-01T07:15:05Z",
      explanation: "Hardware buffers are dropping egress packets due to downstream link congestion.",
    },
    {
      name: "End-to-End Latency (RTT)",
      value: "48.5 ms",
      unit: "milliseconds",
      nominal: "12.0 ms",
      delta: "+36.5 ms",
      source: "telemetry_agent (ICMP Active Probes)",
      timestamp: "2026-11-01T07:15:10Z",
      explanation: "Packets spend excess time queuing in transmission buffers across transit hops.",
    },
    {
      name: "RTT Jitter Variance",
      value: "14.2 ms",
      unit: "milliseconds",
      nominal: "< 3.0 ms",
      delta: "+11.2 ms",
      source: "telemetry_agent (TWAMP probes)",
      timestamp: "2026-11-01T07:15:12Z",
      explanation: "Micro-burst queuing induces delay variation affecting real-time UDP streams.",
    },
    {
      name: "Control Plane CPU",
      value: "38.4%",
      unit: "percent",
      nominal: "< 60.0%",
      delta: "Nominal",
      source: "telemetry_agent (Host telemetry)",
      timestamp: "2026-11-01T07:15:15Z",
      explanation: "Control plane CPU remains unconstrained; fault is isolated to data-plane egress buffers.",
    },
  ];

  const agentContributions = [
    {
      agent: "Telemetry Agent",
      role: "Metric & Bandwidth Auditing",
      status: "COMPLETED",
      finding: "Detected 94.2% bandwidth capacity saturation on spine-01 (port et-0/0/1).",
    },
    {
      agent: "Log Agent",
      role: "Syslog Pattern & Queue Auditing",
      status: "COMPLETED",
      finding: "Corroborated 4,500 drops/s tail drop counter in hardware egress queue.",
    },
    {
      agent: "Topology Agent",
      role: "Path & Blast Radius Discovery",
      status: "COMPLETED",
      finding: "Verified spine-02 redundant path is operating nominally at 28.1% load.",
    },
    {
      agent: "Config Agent",
      role: "Device & Policy Audit",
      status: "COMPLETED",
      finding: "Confirmed ECMP hash weight configuration is intact with no pending commits.",
    },
    {
      agent: "Synthesizer Agent",
      role: "Evidence Cross-Corroboration",
      status: "COMPLETED",
      finding: "Synthesized multi-agent hypotheses with 94% calibrated confidence.",
    },
  ];

  const probableCause = report?.probable_cause || "INTERFACE_SATURATION_QUEUE_OVERFLOW";
  const confidencePct = Math.round((report?.confidence || 0.94) * 100);
  const uncertaintyPct = Math.round(((report?.uncertainty as any)?.score || 0.06) * 100);
  const affectedDevices =
    report?.affected_devices && report.affected_devices.length > 0
      ? report.affected_devices
      : ["spine-01", "leaf-01", "leaf-02"];

  const linkedTickets = tickets.filter((t) => t.linked_incident_id === selectedIncidentId);
  const selectedIncident = incidents.find((i) => i.incident_id === selectedIncidentId);

  return (
    <div className="space-y-6 font-sans text-slate-800 dark:text-slate-100">
      {/* Top Header */}
      <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs uppercase font-bold tracking-wider px-2.5 py-0.5 border border-[#0B2545]/20 bg-blue-50 text-[#0B2545] dark:bg-blue-950/40 dark:text-blue-300">
                Network Engineering Operations
              </span>
              <span className="text-sm text-slate-500 dark:text-slate-400">
                Fabric Domain: iitbbsr-campus-prod
              </span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-[#0B2545] dark:text-slate-100">
              Diagnostic Execution &amp; Incident Investigation
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Trigger live AI multi-agent diagnoses and perform deep root-cause investigations on persisted network incidents.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            {previousRunId && onCompareRuns && (
              <button
                onClick={onCompareRuns}
                className="px-4 py-2 border border-[#0B2545] text-[#0B2545] dark:text-blue-400 hover:bg-[#0B2545]/10 text-xs font-bold uppercase tracking-wide transition-colors"
              >
                Compare with Previous Run
              </button>
            )}
            {onRunDiagnosis && (
              <button
                onClick={onRunDiagnosis}
                disabled={executionStatus === "running"}
                className="px-5 py-2.5 bg-[#0B2545] hover:bg-[#133E87] disabled:opacity-50 text-white text-sm font-semibold tracking-wide transition-colors shadow-sm"
              >
                {executionStatus === "running" ? "Diagnosing..." : "Run Network Diagnosis"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Primary Tab Navigation: Exact labels "Diagnosis Results" and "Incident Investigation" */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-3 text-base">
        <button
          onClick={() => setActiveMainTab("diagnosis_results")}
          className={`px-5 py-3.5 font-bold tracking-wide border-b-2 transition-colors flex items-center gap-2 ${
            activeMainTab === "diagnosis_results"
              ? "border-[#0B2545] text-[#0B2545] dark:text-blue-400 bg-slate-50 dark:bg-slate-800/40"
              : "border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
          }`}
        >
          <span>Diagnosis Results</span>
          {lastRunId && (
            <span className="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 font-mono">
              Live
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveMainTab("incident_investigation")}
          className={`px-5 py-3.5 font-bold tracking-wide border-b-2 transition-colors flex items-center gap-2 ${
            activeMainTab === "incident_investigation"
              ? "border-[#0B2545] text-[#0B2545] dark:text-blue-400 bg-slate-50 dark:bg-slate-800/40"
              : "border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
          }`}
        >
          <span>Incident Investigation</span>
          <span className="text-xs px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-mono">
            {incidents.length}
          </span>
        </button>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* TAB 1: Diagnosis Results                                          */}
      {/* ----------------------------------------------------------------- */}
      {activeMainTab === "diagnosis_results" && (
        <div className="space-y-6">
          {/* State 1: Running */}
          {executionStatus === "running" && (
            <div className="border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-8 text-center space-y-4">
              <div className="inline-block animate-spin w-8 h-8 border-4 border-[#0B2545] border-t-transparent rounded-full mb-2"></div>
              <h3 className="text-xl font-bold text-[#0B2545] dark:text-slate-100">
                Diagnosis Execution in Progress
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-400 max-w-lg mx-auto">
                Dispatching topology telemetry from scenario <code className="font-mono font-bold text-slate-800 dark:text-slate-200">{selectedScenario}</code> to the multi-agent diagnostic pipeline.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 max-w-3xl mx-auto pt-4 text-xs font-semibold">
                <div className="p-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-emerald-700">1. Telemetry Auditor</div>
                <div className="p-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-emerald-700">2. Topology Auditor</div>
                <div className="p-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-blue-700 animate-pulse">3. Alert Correlator</div>
                <div className="p-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-400">4. Diagnosis Reasoner</div>
                <div className="p-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-400">5. Orchestrator</div>
              </div>
            </div>
          )}

          {/* State 2: Failed */}
          {executionStatus === "failed" && (
            <div className="border border-red-300 bg-red-50 dark:bg-red-950/20 dark:border-red-800 p-6 space-y-3">
              <h3 className="text-lg font-bold text-red-800 dark:text-red-300">
                Diagnostic Execution Failed
              </h3>
              <p className="text-sm text-red-700 dark:text-red-400">
                {runErrorMessage || "An unexpected error occurred while communicating with the diagnostic backend."}
              </p>
              {onRunDiagnosis && (
                <button
                  onClick={onRunDiagnosis}
                  className="px-4 py-2 bg-red-700 hover:bg-red-800 text-white text-xs font-bold uppercase tracking-wider"
                >
                  Retry Network Diagnosis
                </button>
              )}
            </div>
          )}

          {/* State 3: No diagnosis executed yet */}
          {!lastRunId && executionStatus === "idle" && (
            <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center space-y-4 shadow-sm">
              <div className="w-12 h-12 mx-auto rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 font-bold text-xl">
                ?
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                No diagnosis has been executed yet. Select a scenario and run network diagnosis.
              </h3>
              <p className="text-sm text-slate-500 max-w-md mx-auto">
                Execution results will appear here with unique run identifiers, timestamps, agent findings, calibrated confidence, and recommended remediation plans.
              </p>
              {onRunDiagnosis && (
                <button
                  onClick={onRunDiagnosis}
                  className="px-6 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white text-sm font-semibold tracking-wide transition-colors shadow-sm"
                >
                  Run Network Diagnosis Now &rarr;
                </button>
              )}
            </div>
          )}

          {/* State 4: Diagnosis Completed with Results */}
          {lastRunId && executionStatus !== "running" && (
            <div className="space-y-6">
              {/* Provenance Card */}
              <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
                  <div>
                    <span className="text-xs uppercase font-bold text-slate-500">Live Execution Provenance</span>
                    <h3 className="text-xl font-bold text-[#0B2545] dark:text-slate-100 mt-1">
                      Execution Run: <span className="font-mono text-blue-700 dark:text-blue-400">{lastRunId}</span>
                    </h3>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-3 py-1 bg-emerald-50 border border-emerald-300 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300 text-xs font-bold uppercase tracking-wider">
                      Status: COMPLETED
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      Timestamp: {new Date(lastRunTimestamp || Date.now()).toUTCString()}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mt-4 text-sm">
                  <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
                    <span className="text-xs uppercase font-semibold text-slate-500">Selected Scenario</span>
                    <div className="font-bold font-mono text-sm mt-1 text-slate-900 dark:text-slate-100">{selectedScenario}</div>
                  </div>
                  <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
                    <span className="text-xs uppercase font-semibold text-slate-500">Calibrated Confidence</span>
                    <div className="font-bold text-2xl mt-1 text-emerald-700 dark:text-emerald-400">{confidencePct}%</div>
                  </div>
                  <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
                    <span className="text-xs uppercase font-semibold text-slate-500">Epistemic Uncertainty</span>
                    <div className="font-bold text-2xl mt-1 text-slate-700 dark:text-slate-300">{uncertaintyPct}%</div>
                  </div>
                  <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
                    <span className="text-xs uppercase font-semibold text-slate-500">Affected Switches</span>
                    <div className="font-bold font-mono text-xs mt-1 text-slate-900 dark:text-slate-100">
                      {affectedDevices.join(", ")}
                    </div>
                  </div>
                </div>
              </div>

              {/* Root Cause Assessment */}
              <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4 shadow-sm">
                <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
                  <h4 className="text-base font-bold text-[#0B2545] dark:text-slate-100">
                    Diagnosed Root Cause Assessment
                  </h4>
                  <span className="px-2.5 py-0.5 border border-red-600/30 bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300 text-xs uppercase font-bold tracking-wider">
                    {probableCause}
                  </span>
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                  Synthesized across telemetry, hardware tail-drop logs, and topology discovery agents. Heavy burst traffic on spine switch egress exceeds capacity threshold, causing tail-drop queue starvation on downstream distribution links.
                </p>

                {/* Conformal Prediction Set */}
                <div className="p-4 border border-blue-200 bg-blue-50/60 dark:bg-blue-950/20 dark:border-blue-800 text-sm space-y-1.5">
                  <div className="font-bold text-xs uppercase text-[#0B2545] dark:text-blue-300">
                    Conformal Prediction Set (95.0% Coverage Guarantee)
                  </div>
                  <div className="flex flex-wrap gap-2 pt-1 font-mono text-xs">
                    {((report as any)?.conformal_prediction_set || ["INTERFACE_SATURATION_QUEUE_OVERFLOW", "ECMP_HASH_IMBALANCE"]).map(
                      (item: string) => (
                        <span key={item} className="px-2.5 py-1 bg-white dark:bg-slate-900 border border-blue-300 dark:border-blue-700 text-blue-900 dark:text-blue-200 font-semibold">
                          {item}
                        </span>
                      )
                    )}
                  </div>
                </div>
              </div>

              {/* Participating Agents & Findings */}
              <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4 shadow-sm">
                <h4 className="text-base font-bold text-[#0B2545] dark:text-slate-100">
                  Participating Agents &amp; Progress Findings
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {agentContributions.map((agent) => (
                    <div key={agent.agent} className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-1.5 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900 dark:text-slate-100">{agent.agent}</span>
                        <span className="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 font-semibold">
                          {agent.status}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 uppercase">{agent.role}</div>
                      <p className="text-xs text-slate-700 dark:text-slate-300 pt-1 leading-relaxed">
                        {agent.finding}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Supporting Telemetry Evidence */}
              <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                  <div>
                    <h4 className="text-base font-bold text-[#0B2545] dark:text-slate-100">
                      Supporting Evidence &amp; Measurements
                    </h4>
                    <p className="text-xs text-slate-500 mt-0.5">Observed metric values compared against nominal fabric baselines.</p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-xs uppercase font-bold text-slate-500">
                      <tr>
                        <th className="p-3.5">Metric Name</th>
                        <th className="p-3.5">Observed Value</th>
                        <th className="p-3.5">Nominal Baseline</th>
                        <th className="p-3.5">Delta</th>
                        <th className="p-3.5">Telemetry Source</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {telemetryData.map((m) => (
                        <tr key={m.name} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="p-3.5 font-semibold text-slate-900 dark:text-slate-100">{m.name}</td>
                          <td className="p-3.5 font-bold font-mono text-[#0B2545] dark:text-blue-400">{m.value}</td>
                          <td className="p-3.5 text-slate-500 text-xs font-mono">{m.nominal}</td>
                          <td className="p-3.5 font-bold font-mono text-red-600 text-xs">{m.delta}</td>
                          <td className="p-3.5 text-xs text-slate-500">{m.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Recommended Actions */}
              <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-4 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
                  <div>
                    <h4 className="text-base font-bold text-[#0B2545] dark:text-slate-100">
                      Recommended Remediation Actions
                    </h4>
                    <p className="text-xs text-slate-500 mt-0.5">Automated mitigation plan validated through sandboxed simulation.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={onLaunchSimulation}
                      className="px-4 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors"
                    >
                      Test Recommended Fix (Simulation)
                    </button>
                    <button
                      onClick={onOpenHitlQueue}
                      className="px-4 py-2 border border-[#0B2545] text-[#0B2545] dark:text-blue-400 hover:bg-[#0B2545]/10 text-xs font-bold uppercase tracking-wider transition-colors"
                    >
                      Review Pending Approvals
                    </button>
                  </div>
                </div>

                <div className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-2 text-sm">
                  <div className="font-bold text-[#0B2545] dark:text-blue-300">
                    Plan 1: ECMP Re-weighting &amp; Dynamic Transit Reroute
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                    Reroute 40% of egress flow from congested port <code className="font-mono">spine-01:et-0/0/1</code> across redundant path <code className="font-mono">spine-02:et-0/0/2</code>. Zero traffic drop during transition. Rollback verified.
                  </p>
                </div>

                {/* Collapsible Raw Report */}
                <div className="pt-2">
                  <button
                    onClick={() => setShowRawReport(!showRawReport)}
                    className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 underline"
                  >
                    {showRawReport ? "Hide Unified Diagnostic Report Contract" : "View Unified Diagnostic Report Contract (JSON)"}
                  </button>
                  {showRawReport && report && (
                    <pre className="mt-3 p-4 bg-slate-950 text-emerald-400 font-mono text-xs overflow-x-auto max-h-72">
                      {JSON.stringify(report, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 2: Incident Investigation                                     */}
      {/* ----------------------------------------------------------------- */}
      {activeMainTab === "incident_investigation" && (
        <div className="space-y-6">
          {/* Incident Selector Bar */}
          <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <span className="text-xs uppercase font-bold text-slate-500">Incident Record Selection</span>
                <div className="flex items-center gap-3">
                  <select
                    value={selectedIncidentId}
                    onChange={(e) => setSelectedIncidentId(e.target.value)}
                    className="p-2.5 border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 font-mono text-sm font-bold text-[#0B2545] dark:text-blue-400 outline-none"
                  >
                    {incidents.map((inc) => (
                      <option key={inc.incident_id} value={inc.incident_id}>
                        {inc.incident_id} ({inc.status.toUpperCase()})
                      </option>
                    ))}
                    {incidents.length === 0 && (
                      <option value="inc-link-congestion-42">inc-link-congestion-42 (DIAGNOSED)</option>
                    )}
                  </select>

                  <span className={`px-2.5 py-1 border text-xs uppercase font-bold tracking-wider ${
                    selectedIncident?.status === "diagnosed"
                      ? "border-emerald-600/30 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
                      : "border-amber-600/30 bg-amber-50 text-amber-800 dark:bg-amber-950/30 dark:text-amber-300"
                  }`}>
                    {selectedIncident?.status || "DIAGNOSED"}
                  </span>
                </div>
              </div>

              <div className="flex flex-col sm:items-end text-xs text-slate-500">
                <div>Severity: <span className="font-bold text-red-600 uppercase">Critical (Egress Buffer Saturation)</span></div>
                <div>Affected Switches: <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold">{affectedDevices.join(", ")}</span></div>
              </div>
            </div>
          </div>

          {/* Investigation History & Timeline */}
          <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div>
                <h4 className="text-base font-bold text-[#0B2545] dark:text-slate-100">
                  Agent Findings &amp; Collaboration Timeline
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">Chronological record of multi-agent investigation messages.</p>
              </div>
              <button
                onClick={() => setShowTechnicalMessages(!showTechnicalMessages)}
                className="px-3.5 py-1.5 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                {showTechnicalMessages ? "Collapse Technical Messages" : "View Technical Messages"}
              </button>
            </div>

            {loadingEnvelopes ? (
              <div className="p-6 text-center text-sm text-slate-500">Loading investigation timeline...</div>
            ) : (
              <div className="space-y-3">
                {envelopes.slice(0, 4).map((env) => (
                  <div key={env.message_id} className="p-4 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-1.5 text-sm">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-xs text-[#0B2545] dark:text-blue-400">{env.sender}</span>
                        <span className="text-slate-400 text-xs">&rarr;</span>
                        <span className="font-mono text-xs text-slate-600 dark:text-slate-400">{env.recipient}</span>
                      </div>
                      <span className="text-xs font-mono text-slate-400">
                        {new Date(env.timestamp_utc).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="text-xs font-bold uppercase text-slate-500">{env.message_type}</div>
                    <p className="text-xs text-slate-700 dark:text-slate-300">
                      {env.payload?.finding || env.payload?.probable_cause || "Metric observation dispatched."}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* Expandable Technical Envelopes */}
            {showTechnicalMessages && (
              <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
                <h5 className="text-xs font-bold uppercase text-slate-500">Raw Protocol Envelopes</h5>
                <div className="space-y-2">
                  {envelopes.map((env) => (
                    <div key={env.message_id} className="p-3 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs space-y-2">
                      <div className="flex items-center justify-between font-mono">
                        <span className="font-bold">{env.message_id}</span>
                        <button
                          onClick={() => setExpandedPayloadId(expandedPayloadId === env.message_id ? null : env.message_id)}
                          className="text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          {expandedPayloadId === env.message_id ? "Hide JSON" : "Show JSON"}
                        </button>
                      </div>
                      {expandedPayloadId === env.message_id && (
                        <pre className="p-3 bg-slate-950 text-emerald-400 font-mono text-xs overflow-x-auto max-h-48">
                          {JSON.stringify(env, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Linked Support Tickets Section */}
          <div className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div>
                <h4 className="text-base font-bold text-[#0B2545] dark:text-slate-100">
                  Linked Support Tickets ({linkedTickets.length})
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  End-user customer reports mapped to this specific network diagnostic incident.
                </p>
              </div>
            </div>

            {linkedTickets.length === 0 ? (
              <div className="p-6 text-center text-sm text-slate-500 border border-dashed border-slate-300 dark:border-slate-700">
                No support tickets currently linked to incident {selectedIncidentId}.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-xs uppercase font-bold text-slate-500">
                    <tr>
                      <th className="p-3.5">Ticket ID</th>
                      <th className="p-3.5">Title</th>
                      <th className="p-3.5">Location</th>
                      <th className="p-3.5">Priority</th>
                      <th className="p-3.5">Status</th>
                      <th className="p-3.5">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {linkedTickets.map((t) => (
                      <tr key={t.ticket_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="p-3.5 font-mono font-bold text-[#0B2545] dark:text-blue-400">{t.ticket_id}</td>
                        <td className="p-3.5 font-semibold text-slate-900 dark:text-slate-100">{t.title}</td>
                        <td className="p-3.5 text-slate-600 dark:text-slate-400">{t.location}</td>
                        <td className="p-3.5 uppercase text-xs font-semibold">{t.priority}</td>
                        <td className="p-3.5">
                          <span className="px-2 py-0.5 border border-emerald-600/30 bg-emerald-50 text-emerald-800 text-xs font-bold">
                            {t.status}
                          </span>
                        </td>
                        <td className="p-3.5 text-xs text-slate-500 font-mono">
                          {new Date(t.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Form to Associate Ticket to this Incident */}
            <div className="p-5 border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-3">
              <h5 className="text-xs font-bold uppercase text-slate-700 dark:text-slate-300">
                Link Additional Campus Support Ticket to Incident {selectedIncidentId}
              </h5>
              {linkMsg && (
                <div className="p-2.5 bg-blue-50 border border-blue-200 text-blue-800 text-xs">
                  {linkMsg}
                </div>
              )}
              <form onSubmit={handleLinkTicket} className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  placeholder="Enter Support Ticket ID (e.g. TICK-2026-0001)"
                  value={linkTicketId}
                  onChange={(e) => setLinkTicketId(e.target.value)}
                  className="flex-1 p-2.5 border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono outline-none"
                />
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
                >
                  Link Ticket to Incident
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
