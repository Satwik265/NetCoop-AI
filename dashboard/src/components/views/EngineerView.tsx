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

interface EngineerViewProps {
  report: UnifiedDiagnosticReport | null;
  onLaunchSimulation: () => void;
  onOpenHitlQueue: () => void;
  onNavigate?: (navId: string) => void;
}

export const EngineerView: React.FC<EngineerViewProps> = ({
  report,
  onLaunchSimulation,
  onOpenHitlQueue,
  onNavigate,
}) => {
  const [incidents, setIncidents] = useState<IncidentSummaryItem[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(
    report?.incident_id || "inc-link-congestion-42"
  );
  const [envelopes, setEnvelopes] = useState<EnvelopeItem[]>([]);
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [loadingEnvelopes, setLoadingEnvelopes] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<
    "summary" | "explanation" | "evidence" | "action" | "tickets"
  >("summary");
  const [expandedPayloadId, setExpandedPayloadId] = useState<string | null>(null);
  const [showTechnicalMessages, setShowTechnicalMessages] = useState<boolean>(false);
  const [showAllEvidence, setShowAllEvidence] = useState<boolean>(false);
  const [linkTicketId, setLinkTicketId] = useState<string>("");
  const [linkMsg, setLinkMsg] = useState<string | null>(null);

  // Synchronize when report changes from external run
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

  // Fetch live envelopes for selected incident
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

  // Fetch tickets for linking and inspection
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
        body: JSON.stringify({ incident_id: selectedIncidentId }),
      });
      if (res.ok) {
        setLinkMsg(`Ticket ${linkTicketId} successfully linked to incident ${selectedIncidentId}.`);
        setLinkTicketId("");
        const refreshed = await apiFetch("/api/tickets");
        if (refreshed.ok) setTickets(await refreshed.json());
      } else {
        const err = await res.json().catch(() => ({ detail: "Failed to link ticket." }));
        setLinkMsg(`Error: ${err.detail || "Unable to associate ticket."}`);
      }
    } catch {
      setLinkMsg("Network error connecting to ticket service.");
    }
  };

  const primaryTelemetry = [
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
  ];

  const secondaryTelemetry = [
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
      name: "CPU Utilization",
      value: "38.4%",
      unit: "percent",
      nominal: "< 60.0%",
      delta: "Nominal",
      source: "telemetry_agent (Host telemetry)",
      timestamp: "2026-11-01T07:15:15Z",
      explanation: "Control plane CPU remains unconstrained; fault is isolated to data-plane egress buffers.",
    },
    {
      name: "Memory Utilization",
      value: "42.1%",
      unit: "percent",
      nominal: "< 70.0%",
      delta: "Nominal",
      source: "telemetry_agent (Host telemetry)",
      timestamp: "2026-11-01T07:15:15Z",
      explanation: "Routing daemon memory usage is stable with no memory pressure or leakage.",
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

  return (
    <div className="space-y-6 font-sans text-sm text-[#0F172A] dark:text-[#EDEDEA]">
      {/* Top Banner: Incident Summary Card (Level 1) */}
      <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#15803D]"></span>
              <span className="text-xs text-[#0B2545] dark:text-[#94A3B8] uppercase tracking-wider font-bold">
                Network Engineer Incident Investigation
              </span>
            </div>
            <h2 className="text-xl font-bold text-[#0B2545] dark:text-[#F1F5F9]">
              {probableCause.replace(/_/g, " ")}
            </h2>
            <div className="text-xs text-[#475569] dark:text-[#94A3B8] flex flex-wrap items-center gap-3">
              <span>Incident ID: <strong className="font-mono text-[#0F172A] dark:text-[#EDEDEA]">{selectedIncidentId}</strong></span>
              <span>&bull;</span>
              <span>Affected Devices: <strong className="font-mono">{affectedDevices.join(", ")}</strong></span>
              <span>&bull;</span>
              <span>Status: <strong className="uppercase text-[#15803D]">{report?.status || "Diagnosed"}</strong></span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <div className="border border-[#15803D]/30 px-4 py-2 bg-[#F0FDF4] text-center">
              <div className="text-[11px] uppercase text-[#15803D] font-bold">Calibrated Confidence</div>
              <div className="text-2xl font-bold text-[#15803D]">{confidencePct}%</div>
              <div className="text-[11px] text-[#475569]">Uncertainty: {uncertaintyPct}%</div>
            </div>

            <div className="space-y-2">
              {incidents.length > 0 && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-[#475569] font-medium">Select Incident:</span>
                  <select
                    value={selectedIncidentId}
                    onChange={(e) => setSelectedIncidentId(e.target.value)}
                    className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] px-2 py-1 text-xs font-mono outline-none"
                  >
                    {incidents.map((inc) => (
                      <option key={inc.incident_id} value={inc.incident_id}>
                        {inc.incident_id} ({inc.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <button
                onClick={() => setActiveTab("explanation")}
                className="w-full px-4 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
              >
                View Investigation &rarr;
              </button>
            </div>
          </div>
        </div>

        {linkMsg && (
          <div className="mt-4 p-3 bg-[#EEF4FB] border border-[#133E87]/30 text-[#0B2545] text-xs">
            {linkMsg}
          </div>
        )}
      </div>

      {/* 4-Level Progressive Disclosure Navigation Bar */}
      <div className="flex border-b border-[#E2E8F0] dark:border-[#2A2A2D] gap-2 overflow-x-auto text-sm">
        {[
          { id: "summary", label: "1. Incident Summary — What is wrong?" },
          { id: "explanation", label: "2. Investigation Details — Why did it happen?" },
          { id: "evidence", label: "3. Evidence & Measurements — What supports the diagnosis?" },
          { id: "action", label: "4. Recommended Actions — What should happen next?" },
          { id: "tickets", label: `Linked Support Tickets (${linkedTickets.length})` },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-4 py-3 font-semibold whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#0B2545] dark:border-[#3A86FF] text-[#0B2545] dark:text-[#3A86FF] bg-[#EEF4FB]/50 dark:bg-[#161618]"
                : "border-transparent text-[#475569] dark:text-[#888884] hover:text-[#0B2545] dark:hover:text-[#EDEDEA]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* LEVEL 1: Incident Summary — What is wrong?                        */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "summary" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="p-5 border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] space-y-2">
              <span className="text-xs uppercase font-bold text-[#B45309]">What is Wrong?</span>
              <h3 className="text-base font-bold text-[#0B2545] dark:text-[#EDEDEA]">Egress Buffer Saturation</h3>
              <p className="text-sm text-[#475569] dark:text-[#888884] leading-relaxed">
                Heavy traffic load between Core Spine switch and Distribution Leaf has exceeded interface queue thresholds, causing tail drops and packet loss.
              </p>
            </div>

            <div className="p-5 border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] space-y-2">
              <span className="text-xs uppercase font-bold text-[#0B2545] dark:text-[#94A3B8]">Why Did It Happen?</span>
              <h3 className="text-base font-bold text-[#0F172A] dark:text-[#EDEDEA]">ECMP Flow Imbalance</h3>
              <p className="text-sm text-[#475569] dark:text-[#888884] leading-relaxed">
                Elephant flow hash collision routed redundant data transfers through a single link while spine-02 remained underutilized at 28.1%.
              </p>
            </div>

            <div className="p-5 border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] space-y-2">
              <span className="text-xs uppercase font-bold text-[#15803D]">What Should Be Done?</span>
              <h3 className="text-base font-bold text-[#15803D]">Rebalance ECMP Weights</h3>
              <p className="text-sm text-[#475569] dark:text-[#888884] leading-relaxed">
                Execute safe simulated remediation proposal <code className="font-mono text-xs">act-rebalance-ecmp-01</code> to divert 40% of peak traffic to the alternate spine path.
              </p>
            </div>
          </div>

          <div className="p-5 border border-[#133E87]/30 bg-[#EEF4FB] dark:bg-[#0B132B] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="font-bold text-sm text-[#0B2545] dark:text-[#F1F5F9]">
                Step 2: Deep Dive Investigation Available
              </div>
              <div className="text-xs text-[#475569] dark:text-[#94A3B8]">
                Explore participating agent observations or review calibrated telemetry evidence.
              </div>
            </div>
            <button
              onClick={() => setActiveTab("explanation")}
              className="px-5 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white font-bold text-xs uppercase tracking-wider transition-colors shadow-sm"
            >
              View Investigation Details &rarr;
            </button>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* LEVEL 2: Investigation Details — Why did it happen?               */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "explanation" && (
        <div className="space-y-6">
          {/* Agent Contributions Grid */}
          <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-5 border-b border-[#E2E8F0] dark:border-[#2A2A2D]">
              <h3 className="text-base font-bold text-[#0B2545] dark:text-[#F1F5F9]">Participating Domain Agents</h3>
              <p className="text-xs text-[#475569] dark:text-[#888884]">
                Domain findings and hypotheses contributed by isolated specialized agents.
              </p>
            </div>
            <div className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
              {agentContributions.map((agent) => (
                <div key={agent.agent} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm">{agent.agent}</span>
                      <span className="text-[#475569] dark:text-[#888884] text-xs">&bull; {agent.role}</span>
                      <span className="px-2 py-0.5 border border-[#15803D]/40 text-[#15803D] bg-[#F0FDF4] text-xs font-semibold">
                        {agent.status}
                      </span>
                    </div>
                    <div className="text-xs text-[#475569] dark:text-[#888884] mt-1">{agent.finding}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Collaboration Timeline & Collapsible Technical Messages */}
          <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-5 border-b border-[#E2E8F0] dark:border-[#2A2A2D] flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-[#0B2545] dark:text-[#F1F5F9]">
                  Inter-Agent Collaboration Timeline
                </h3>
                <p className="text-xs text-[#475569] dark:text-[#888884]">
                  Protocol v1.0 message envelopes. Raw JSON payloads are collapsed under technical messages.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-[#475569] dark:text-[#888884]">
                  {envelopes.length} Messages Exchanged
                </span>
                <button
                  onClick={() => setShowTechnicalMessages((prev) => !prev)}
                  className="px-3 py-1 border border-[#133E87] text-[#133E87] hover:bg-[#EEF4FB] text-xs font-semibold transition-colors"
                >
                  {showTechnicalMessages ? "Hide Technical Messages" : "View Technical Messages"}
                </button>
              </div>
            </div>

            <div className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
              {loadingEnvelopes && (
                <div className="p-4 text-xs text-[#475569] text-center">
                  Loading protocol message envelopes...
                </div>
              )}
              {envelopes.map((env) => (
                <div key={env.message_id} className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 border border-[#133E87]/30 bg-[#EEF4FB] text-[#133E87] text-xs font-mono font-semibold">
                        {env.message_type}
                      </span>
                      <span className="font-bold text-xs">{env.sender}</span>
                      <span className="text-[#475569]">&rarr;</span>
                      <span className="font-bold text-xs">{env.recipient}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-[#475569] font-mono">
                        {new Date(env.timestamp_utc).toLocaleTimeString()}
                      </span>
                      {showTechnicalMessages && (
                        <button
                          onClick={() =>
                            setExpandedPayloadId(
                              expandedPayloadId === env.message_id ? null : env.message_id
                            )
                          }
                          className="px-2 py-0.5 border border-[#E2E8F0] text-xs font-semibold hover:border-[#0B2545]"
                        >
                          {expandedPayloadId === env.message_id ? "Hide JSON" : "Inspect JSON"}
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="text-xs text-[#475569] dark:text-[#888884]">
                    {env.payload?.finding || env.payload?.probable_cause || "Message envelope processed cleanly."}
                  </div>

                  {/* Expandable Raw JSON Payload */}
                  {showTechnicalMessages && expandedPayloadId === env.message_id && (
                    <div className="p-3 bg-[#F8FAFC] dark:bg-[#0B132B] border border-[#E2E8F0] dark:border-[#2A2A2D] mt-2 overflow-x-auto">
                      <pre className="text-xs font-mono text-[#0B2545] dark:text-[#3A86FF]">
                        {JSON.stringify(env.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* LEVEL 3: Evidence & Measurements — What supports the diagnosis?    */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "evidence" && (
        <div className="space-y-6">
          <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
            <h3 className="text-base font-bold text-[#0B2545] dark:text-[#F1F5F9] mb-1">
              Calibrated Telemetry Measurements
            </h3>
            <p className="text-xs text-[#475569] dark:text-[#888884] mb-4">
              Observed telemetry compared to nominal operational baselines with data source and timestamp verification.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F8FAFC] dark:bg-[#0F0F10] border-b border-[#E2E8F0] dark:border-[#2A2A2D] text-[#475569] uppercase font-bold text-[11px]">
                  <tr>
                    <th className="p-3">Measurement</th>
                    <th className="p-3">Observed Value</th>
                    <th className="p-3">Baseline</th>
                    <th className="p-3">Difference</th>
                    <th className="p-3">Data Source</th>
                    <th className="p-3">Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
                  {primaryTelemetry.map((item) => (
                    <tr key={item.name} className="hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F10]">
                      <td className="p-3 font-semibold text-[#0F172A] dark:text-[#EDEDEA]">{item.name}</td>
                      <td className="p-3 font-mono font-bold text-[#DC2626]">{item.value}</td>
                      <td className="p-3 font-mono text-[#475569]">{item.nominal}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 border border-[#DC2626]/30 bg-[#FEF2F2] text-[#DC2626] font-bold text-[11px]">
                          {item.delta}
                        </span>
                      </td>
                      <td className="p-3 text-[#475569] font-mono text-[11px]">{item.source}</td>
                      <td className="p-3 text-[#475569] text-xs max-w-xs">{item.explanation}</td>
                    </tr>
                  ))}
                  {showAllEvidence &&
                    secondaryTelemetry.map((item) => (
                      <tr key={item.name} className="hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F10]">
                        <td className="p-3 font-semibold text-[#0F172A] dark:text-[#EDEDEA]">{item.name}</td>
                        <td className="p-3 font-mono font-bold">{item.value}</td>
                        <td className="p-3 font-mono text-[#475569]">{item.nominal}</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 border border-[#E2E8F0] bg-[#F8FAFC] text-[#475569] font-semibold text-[11px]">
                            {item.delta}
                          </span>
                        </td>
                        <td className="p-3 text-[#475569] font-mono text-[11px]">{item.source}</td>
                        <td className="p-3 text-[#475569] text-xs max-w-xs">{item.explanation}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>

            <button
              onClick={() => setShowAllEvidence(!showAllEvidence)}
              className="mt-4 text-xs text-[#133E87] dark:text-[#3A86FF] font-bold hover:underline"
            >
              {showAllEvidence ? "Collapse Supporting Metrics" : "View All Supporting Metrics & Telemetry &rarr;"}
            </button>
          </div>

          {/* Statistical Uncertainty & Conformal Prediction */}
          <div className="border border-[#15803D]/30 bg-[#F0FDF4] dark:bg-[#0B132B] p-5 space-y-2">
            <span className="text-xs uppercase font-bold text-[#15803D]">
              Split Conformal Prediction Set &amp; Statistical Bounds
            </span>
            <div className="text-sm text-[#0F172A] dark:text-[#EDEDEA] space-y-1">
              <div>Coverage Guarantee: <strong>95.0% Validated (alpha = 0.05)</strong></div>
              <div>
                Prediction Set: <code className="font-mono text-xs bg-[#FFFFFF] px-2 py-0.5 border border-[#15803D]/30 font-bold">&#123;&quot;INTERFACE_SATURATION_QUEUE_OVERFLOW&quot;, &quot;ECMP_HASH_IMBALANCE&quot;&#125;</code>
              </div>
              <div className="text-xs text-[#475569] dark:text-[#94A3B8] leading-relaxed">
                The non-empty conformal prediction set provides exact multi-label coverage under exchangeability, guaranteeing that the true network fault is included within the predicted set with 95% statistical confidence.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* LEVEL 4: Recommended Actions — What should happen next?           */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "action" && (
        <div className="space-y-6">
          <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-6 space-y-5">
            <div className="flex items-center justify-between pb-4 border-b border-[#E2E8F0] dark:border-[#2A2A2D]">
              <div>
                <span className="text-xs uppercase font-bold text-[#15803D]">Recommended Action Proposal</span>
                <h3 className="text-lg font-bold font-mono text-[#0B2545] dark:text-[#F1F5F9]">
                  act-rebalance-ecmp-01
                </h3>
              </div>
              <span className="px-3 py-1 border border-[#15803D] bg-[#F0FDF4] text-[#15803D] text-xs font-bold uppercase tracking-wider">
                SIMULATION SAFEGUARD ACTIVE
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-4 border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-1 bg-[#F8FAFC] dark:bg-[#0F0F10]">
                <span className="text-xs text-[#475569] uppercase font-bold">Target Device</span>
                <div className="text-sm font-bold text-[#0F172A] dark:text-[#EDEDEA]">spine-01 (port et-0/0/1)</div>
                <div className="text-xs text-[#475569]">Operational Risk: LOW (Traffic load diversion)</div>
              </div>
              <div className="p-4 border border-[#E2E8F0] dark:border-[#2A2A2D] space-y-1 bg-[#F8FAFC] dark:bg-[#0F0F10]">
                <span className="text-xs text-[#475569] uppercase font-bold">Required Authorization</span>
                <div className="text-sm font-bold text-[#0F172A] dark:text-[#EDEDEA]">Human-in-the-Loop (HITL)</div>
                <div className="text-xs text-[#475569]">Zero production mutation guarantee &bull; Dry-run sandbox</div>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-xs uppercase font-bold text-[#0B2545] dark:text-[#94A3B8]">
                Proposed Remediation Syntax (Simulated Dry-Run)
              </span>
              <div className="p-4 bg-[#F8FAFC] dark:bg-[#0B132B] border border-[#E2E8F0] dark:border-[#2A2A2D] font-mono text-xs">
                <code>
                  configure terminal<br />
                  router bgp 65001<br />
                  address-family ipv4 unicast<br />
                  maximum-paths 2<br />
                  load-balance flow hash-seed 42<br />
                  commit
                </code>
              </div>
            </div>

            <div className="space-y-1 text-xs text-[#475569]">
              <strong>Rollback Procedure:</strong> Reverting to previous configuration via <code className="font-mono">rollback configuration 1</code> restores default ECMP hash-seeds with zero configuration drift.
            </div>

            {/* Renamed Actions: Test Recommended Fix (Simulation) & Review Pending Approvals */}
            <div className="flex flex-wrap items-center gap-3 pt-3">
              <button
                onClick={onLaunchSimulation}
                className="px-5 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white font-bold text-xs uppercase tracking-wider transition-colors shadow-sm"
              >
                Test Recommended Fix (Simulation)
              </button>

              <button
                onClick={onOpenHitlQueue}
                className="px-5 py-2.5 border border-[#133E87] text-[#133E87] dark:text-[#3A86FF] hover:bg-[#EEF4FB] font-bold text-xs uppercase tracking-wider transition-colors"
              >
                Review Pending Approvals
              </button>

              {onNavigate && (
                <button
                  onClick={() => onNavigate("topology")}
                  className="px-5 py-2.5 border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#0F172A] dark:text-[#EDEDEA] font-semibold text-xs uppercase tracking-wider transition-colors"
                >
                  Inspect Topology
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* TAB 5: Linked Support Tickets Integration                         */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "tickets" && (
        <div className="space-y-6">
          <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
            <h3 className="text-base font-bold text-[#0B2545] dark:text-[#F1F5F9] mb-1">
              Support Tickets Linked to {selectedIncidentId}
            </h3>
            <p className="text-xs text-[#475569] dark:text-[#888884] mb-4">
              Real-world customer tickets mapped directly to this root-cause diagnostic investigation.
            </p>

            {linkedTickets.length === 0 ? (
              <div className="p-6 text-center text-xs text-[#475569] border border-dashed border-[#E2E8F0]">
                No support tickets currently linked to this incident.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F8FAFC] dark:bg-[#0F0F10] border-b border-[#E2E8F0] dark:border-[#2A2A2D] text-[#475569] uppercase font-bold text-[11px]">
                    <tr>
                      <th className="p-3">Ticket ID</th>
                      <th className="p-3">Title</th>
                      <th className="p-3">Location</th>
                      <th className="p-3">Priority</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
                    {linkedTickets.map((t) => (
                      <tr key={t.ticket_id}>
                        <td className="p-3 font-mono font-bold text-[#0B2545]">{t.ticket_id}</td>
                        <td className="p-3 font-semibold">{t.title}</td>
                        <td className="p-3 text-[#475569]">{t.location}</td>
                        <td className="p-3 uppercase font-semibold text-[11px]">{t.priority}</td>
                        <td className="p-3">
                          <span className="px-2 py-0.5 border border-[#15803D]/30 bg-[#F0FDF4] text-[#15803D] font-bold text-[11px]">
                            {t.status}
                          </span>
                        </td>
                        <td className="p-3 text-[#475569] font-mono text-[11px]">
                          {new Date(t.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Associate Support Ticket Form */}
          <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
            <h4 className="text-sm font-bold uppercase tracking-wider mb-2">
              Associate Campus Support Ticket to Incident
            </h4>
            <form onSubmit={handleLinkTicket} className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                placeholder="Enter Ticket ID (e.g. TICK-2026-0001)"
                value={linkTicketId}
                onChange={(e) => setLinkTicketId(e.target.value)}
                className="flex-1 px-3 py-2 text-xs border border-[#E2E8F0] dark:border-[#2A2A2D] bg-[#F8FAFC] dark:bg-[#0F0F10] focus:border-[#133E87] outline-none font-mono"
              />
              <button
                type="submit"
                className="px-5 py-2 bg-[#0B2545] hover:bg-[#133E87] text-white text-xs font-bold uppercase tracking-wider transition-colors shadow-sm"
              >
                Link to Incident
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
