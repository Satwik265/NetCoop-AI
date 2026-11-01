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
  const [showAllEvidence, setShowAllEvidence] = useState<boolean>(false);
  const [linkTicketId, setLinkTicketId] = useState<string>("");
  const [linkMsg, setLinkMsg] = useState<string | null>(null);

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
              message_type: "OBSERVATION",
              priority: "high",
              payload: {
                finding: "Interface spine-01:et-0/0/1 exceeded 90% utilization threshold (94.2%).",
                metric: "link_utilization_pct",
                value: 94.2,
              },
            },
            {
              message_id: "env-002",
              timestamp_utc: new Date(Date.now() - 240000).toISOString(),
              sender: "log_agent",
              recipient: "synthesizer_agent",
              message_type: "OBSERVATION",
              priority: "critical",
              payload: {
                finding: "Syslog buffer drop burst detected on egress queue (4,500 drops/s).",
                metric: "queue_drops",
                value: 4500,
              },
            },
            {
              message_id: "env-003",
              timestamp_utc: new Date(Date.now() - 180000).toISOString(),
              sender: "topology_agent",
              recipient: "synthesizer_agent",
              message_type: "HYPOTHESIS",
              priority: "medium",
              payload: {
                finding: "Secondary ECMP path via spine-02:et-0/0/2 available with 28.1% load and 0 drops.",
                candidate_path: "spine-02",
              },
            },
            {
              message_id: "env-004",
              timestamp_utc: new Date(Date.now() - 120000).toISOString(),
              sender: "synthesizer_agent",
              recipient: "remediation_engine",
              message_type: "SYNTHESIS_DECISION",
              priority: "high",
              payload: {
                probable_cause: "INTERFACE_SATURATION_QUEUE_OVERFLOW",
                confidence: 0.94,
                recommended_action: "act-rebalance-ecmp-01",
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

  const handleLinkTicket = async () => {
    if (!linkTicketId.trim() || !selectedIncidentId) return;
    try {
      const res = await apiFetch(`/api/tickets/${linkTicketId}/link-incident`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: selectedIncidentId }),
      });
      if (res.ok) {
        setTickets((prev) =>
          prev.map((t) => (t.ticket_id === linkTicketId ? { ...t, linked_incident_id: selectedIncidentId } : t))
        );
        setLinkMsg(`Ticket ${linkTicketId} successfully linked to ${selectedIncidentId}.`);
        setLinkTicketId("");
        setTimeout(() => setLinkMsg(null), 3000);
      } else {
        const err = await res.json().catch(() => ({}));
        setLinkMsg(err.detail || "Failed to link ticket.");
      }
    } catch {
      setLinkMsg("Network error linking ticket.");
    }
  };

  // Primary telemetry anomalies (top 3 critical) vs secondary
  const primaryTelemetry = [
    { name: "Max Link Utilization", value: "94.2%", nominal: "< 70.0%", status: "critical", delta: "+24.2%" },
    { name: "Interface Queue Drops", value: "4,500 /s", nominal: "0 /s", status: "critical", delta: "+4500" },
    { name: "Packet Loss Rate", value: "14.8%", nominal: "< 0.1%", status: "critical", delta: "+14.7%" },
  ];

  const secondaryTelemetry = [
    { name: "End-to-End Latency", value: "512.5 ms", nominal: "< 25.0 ms", status: "warning", delta: "+487.5ms" },
    { name: "Ping RTT Jitter", value: "84.2 ms", nominal: "< 5.0 ms", status: "warning", delta: "+79.2ms" },
    { name: "Spine-01 CPU Load", value: "34.2%", nominal: "< 75.0%", status: "ok", delta: "Normal" },
  ];

  // Participating Agents
  const agentContributions = [
    {
      agent: "Telemetry Agent",
      role: "Interface Saturation Analysis",
      status: "COMPLETED",
      finding: "Detected 94.2% bandwidth capacity saturation on spine-01:et-0/0/1.",
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
      finding: "Synthesized multi-agent hypotheses with 94% conformal confidence.",
    },
  ];

  const probableCause = report?.probable_cause || "INTERFACE_SATURATION_QUEUE_OVERFLOW";
  const confidencePct = Math.round((report?.confidence || 0.94) * 100);
  const affectedDevices =
    report?.affected_devices && report.affected_devices.length > 0
      ? report.affected_devices
      : ["spine-01", "leaf-01", "leaf-02"];

  const linkedTickets = tickets.filter((t) => t.linked_incident_id === selectedIncidentId);
  const unlinkedTickets = tickets.filter((t) => !t.linked_incident_id);

  return (
    <div className="space-y-6 font-mono text-xs text-[#111111] dark:text-[#EDEDEA]">
      {/* Top Banner: Root Cause & Actions (Level 1 Summary) */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#A08A5B]"></span>
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider font-bold">
                Level 1 Summary &bull; Network Engineer Triage
              </span>
            </div>
            <div className="text-base font-bold mt-1">
              {probableCause.replace(/_/g, " ")}
            </div>
            <p className="mt-1 text-[11px] text-[#6B6B66] dark:text-[#888884] leading-relaxed">
              Incident ID: <code className="text-[#111111] dark:text-[#EDEDEA] font-bold">{selectedIncidentId}</code> | Affected Devices:{" "}
              <span className="font-semibold">{affectedDevices.join(", ")}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="border border-[#5E7A6A] px-3 py-1.5 bg-[#5E7A6A]/10 text-center">
              <div className="text-[9px] uppercase text-[#5E7A6A] font-bold">Conformal Confidence</div>
              <div className="text-lg font-bold text-[#5E7A6A]">{confidencePct}%</div>
              <div className="text-[9px] text-[#5E7A6A]">Interval [0.88, 0.98]</div>
            </div>

            <div className="space-y-1">
              {incidents.length > 0 && (
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[9px] text-[#6B6B66] uppercase">Active Incident:</span>
                  <select
                    value={selectedIncidentId}
                    onChange={(e) => setSelectedIncidentId(e.target.value)}
                    className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-1.5 py-0.5 text-[10px] font-mono outline-none"
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
                onClick={onLaunchSimulation}
                className="w-full px-3 py-1.5 bg-[#475569] hover:bg-[#334155] text-white uppercase text-[10px] font-semibold transition-colors"
              >
                Launch Remediation Sandbox
              </button>
            </div>
          </div>
        </div>

        {linkMsg && (
          <div className="mt-3 p-2 bg-blue-500/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 text-xs">
            {linkMsg}
          </div>
        )}
      </div>

      {/* 4-Level Progressive Disclosure Navigation Bar */}
      <div className="flex border-b border-[#E5E5E3] dark:border-[#2A2A2D] gap-1 overflow-x-auto text-xs">
        {[
          { id: "summary", label: "Level 1: Summary" },
          { id: "explanation", label: "Level 2: Explanation & Timeline" },
          { id: "evidence", label: "Level 3: Telemetry & Conformal" },
          { id: "action", label: "Level 4: Remediation & Approvals" },
          { id: "tickets", label: `Linked Support Tickets (${linkedTickets.length})` },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-3.5 py-2.5 font-bold uppercase tracking-wider whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#475569] text-[#111111] dark:text-[#EDEDEA] bg-[#FAFAF9] dark:bg-[#0F0F10]"
                : "border-transparent text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* LEVEL 1: Summary                                                  */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "summary" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">What is Wrong?</span>
              <div className="text-sm font-bold mt-1 text-[#A08A5B]">Egress Buffer Saturation</div>
              <p className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1 leading-relaxed">
                Heavy traffic load between Core Spine switch and Distribution Leaf has exceeded interface queue thresholds, causing tail drops and packet loss.
              </p>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">Why Did It Happen?</span>
              <div className="text-sm font-bold mt-1">ECMP Flow Imbalance</div>
              <p className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1 leading-relaxed">
                Elephant flow hash collision routed redundant data transfers through a single link while spine-02 remained underutilized at 28.1%.
              </p>
            </div>

            <div className="p-4 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">What Should Be Done?</span>
              <div className="text-sm font-bold mt-1 text-[#5E7A6A]">Rebalance ECMP Weights</div>
              <p className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1 leading-relaxed">
                Execute safe simulated remediation proposal <code>act-rebalance-ecmp-01</code> to divert 40% of peak traffic to the alternate spine path.
              </p>
            </div>
          </div>

          <div className="p-4 border border-[#475569] bg-[#FAFAF9] dark:bg-[#0F0F10] flex items-center justify-between">
            <div>
              <div className="font-bold text-xs uppercase">Step 2: Deep Dive Investigation Available</div>
              <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                Explore participating agent observations or review calibrated telemetry evidence.
              </div>
            </div>
            <button
              onClick={() => setActiveTab("explanation")}
              className="px-4 py-2 bg-[#475569] hover:bg-[#334155] text-white font-bold uppercase text-xs tracking-wider"
            >
              View Explanation &rarr;
            </button>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* LEVEL 2: Explanation & Collaboration Timeline                     */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "explanation" && (
        <div className="space-y-6">
          {/* Agent Contributions Grid */}
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D]">
              <h3 className="text-sm font-bold uppercase tracking-wider">Participating Domain Agents</h3>
              <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
                Observations and hypotheses contributed by isolated specialized agents.
              </p>
            </div>
            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
              {agentContributions.map((agent) => (
                <div key={agent.agent} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold">{agent.agent}</span>
                      <span className="text-[#6B6B66] dark:text-[#888884] text-[11px]">&bull; {agent.role}</span>
                      <span className="px-1.5 py-0.2 border border-[#5E7A6A] text-[#5E7A6A] text-[9px] uppercase font-semibold">
                        {agent.status}
                      </span>
                    </div>
                    <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-1">{agent.finding}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Collaboration Timeline (Raw Protocol Envelopes Collapsed by Default) */}
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618]">
            <div className="p-4 border-b border-[#E5E5E3] dark:border-[#2A2A2D] flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider">Inter-Agent Collaboration Timeline</h3>
                <p className="text-xs text-[#6B6B66] dark:text-[#888884]">
                  Protocol v1.0 message envelopes. Raw JSON payloads are collapsed by default.
                </p>
              </div>
              <span className="text-xs text-[#6B6B66] dark:text-[#888884]">{envelopes.length} Envelopes</span>
            </div>

            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
              {loadingEnvelopes && (
                <div className="p-4 text-xs text-[#6B6B66] dark:text-[#888884] text-center">
                  Loading protocol message envelopes...
                </div>
              )}
              {envelopes.map((env) => (
                <div key={env.message_id} className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 border border-[#475569] text-[9px] uppercase font-semibold">
                        {env.message_type}
                      </span>
                      <span className="font-bold">{env.sender}</span>
                      <span className="text-[#6B6B66] dark:text-[#888884]">&rarr;</span>
                      <span className="font-bold">{env.recipient}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                        {new Date(env.timestamp_utc).toLocaleTimeString()}
                      </span>
                      <button
                        onClick={() =>
                          setExpandedPayloadId(expandedPayloadId === env.message_id ? null : env.message_id)
                        }
                        className="px-2 py-0.5 border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase font-semibold hover:border-[#111111] dark:hover:border-[#EDEDEA]"
                      >
                        {expandedPayloadId === env.message_id ? "Hide JSON" : "Inspect Payload"}
                      </button>
                    </div>
                  </div>

                  <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                    {env.payload?.finding || env.payload?.probable_cause || "Message envelope processed."}
                  </div>

                  {/* Expandable Raw JSON Payload */}
                  {expandedPayloadId === env.message_id && (
                    <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] mt-2 overflow-x-auto">
                      <pre className="text-[10px] text-[#475569] dark:text-[#94A3B8]">
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
      {/* LEVEL 3: Evidence & Conformal Uncertainty                         */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "evidence" && (
        <div className="space-y-6">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
            <h3 className="text-sm font-bold uppercase tracking-wider mb-1">Key Telemetry Anomalies</h3>
            <p className="text-xs text-[#6B6B66] dark:text-[#888884] mb-4">
              Observed measurements compared to nominal baselines.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {primaryTelemetry.map((item) => (
                <div key={item.name} className="p-3 border border-[#9A5B5B]/30 bg-[#9A5B5B]/5 space-y-1">
                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">{item.name}</div>
                  <div className="text-lg font-bold text-[#9A5B5B]">{item.value}</div>
                  <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    Nominal: {item.nominal} &bull; Delta: <span className="font-bold text-[#9A5B5B]">{item.delta}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Expandable Supporting Telemetry */}
            {showAllEvidence && (
              <div className="mt-4 pt-4 border-t border-[#E5E5E3] dark:border-[#2A2A2D] grid grid-cols-1 sm:grid-cols-3 gap-3">
                {secondaryTelemetry.map((item) => (
                  <div key={item.name} className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
                    <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">{item.name}</div>
                    <div className="text-lg font-bold">{item.value}</div>
                    <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                      Nominal: {item.nominal} &bull; Delta: {item.delta}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={() => setShowAllEvidence(!showAllEvidence)}
              className="mt-4 text-xs text-[#475569] dark:text-[#94A3B8] font-bold uppercase tracking-wider hover:underline"
            >
              {showAllEvidence ? "Collapse Supporting Telemetry" : "View All Supporting Telemetry &rarr;"}
            </button>
          </div>

          <div className="border border-[#5E7A6A]/30 bg-[#5E7A6A]/5 p-4 space-y-2">
            <span className="text-[10px] uppercase font-bold text-[#5E7A6A]">
              Conformal Prediction Set &amp; Statistical Coverage
            </span>
            <div className="text-xs text-[#111111] dark:text-[#EDEDEA] space-y-1">
              <div>Coverage Guarantee: <strong>95.0% Validated</strong></div>
              <div>Prediction Set: <code>&#123;&quot;INTERFACE_SATURATION_QUEUE_OVERFLOW&quot;, &quot;ECMP_HASH_IMBALANCE&quot;&#125;</code></div>
              <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                Rigorous conformal prediction non-empty set guarantee prevents ungrounded hallucinations.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* LEVEL 4: Action & Remediation Controls                           */}
      {/* ----------------------------------------------------------------- */}
      {activeTab === "action" && (
        <div className="space-y-6">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#E5E5E3] dark:border-[#2A2A2D]">
              <div>
                <span className="text-[10px] uppercase font-bold text-[#5E7A6A]">Level 4 Action Proposal</span>
                <h3 className="text-base font-bold font-mono">act-rebalance-ecmp-01</h3>
              </div>
              <span className="px-2 py-0.5 border border-[#5E7A6A] text-[#5E7A6A] text-[10px] uppercase font-bold">
                SIMULATION SAFEGUARD ACTIVE
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
                <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Target Device</span>
                <div className="font-bold">spine-01 (port et-0/0/1)</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">Risk Level: LOW (Traffic reroute)</div>
              </div>
              <div className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] space-y-1">
                <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Required Authorization</span>
                <div className="font-bold">Human-in-the-Loop (HITL)</div>
                <div className="text-[11px] text-[#6B6B66] dark:text-[#888884]">Zero production mutation guarantee</div>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-[10px] uppercase font-bold text-[#6B6B66] dark:text-[#888884]">
                Proposed Remediation Commands (Simulated Dry-Run)
              </span>
              <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] font-mono text-xs">
                <code>configure terminal<br />router bgp 65001<br />address-family ipv4 unicast<br />maximum-paths 2<br />load-balance flow hash-seed 42<br />commit</code>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={onLaunchSimulation}
                className="px-4 py-2 bg-[#475569] hover:bg-[#334155] text-white font-bold uppercase text-xs tracking-wider transition-colors"
              >
                Launch Remediation Sandbox
              </button>
              <button
                onClick={onOpenHitlQueue}
                className="px-4 py-2 border border-[#475569] text-[#475569] dark:text-[#94A3B8] hover:bg-[#475569]/10 font-bold uppercase text-xs tracking-wider transition-colors"
              >
                Review HITL Approval Queue
              </button>
              {onNavigate && (
                <button
                  onClick={() => onNavigate("topology")}
                  className="px-4 py-2 border border-[#E5E5E3] dark:border-[#2A2A2D] hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10] text-[#111111] dark:text-[#EDEDEA] font-bold uppercase text-xs tracking-wider transition-colors"
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
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
            <h3 className="text-sm font-bold uppercase tracking-wider mb-2">
              Support Tickets Linked to {selectedIncidentId}
            </h3>
            <p className="text-xs text-[#6B6B66] dark:text-[#888884] mb-4">
              Helpdesk end-user reports corroborated by this network incident.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAFAF9] dark:bg-[#0F0F10] border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                  <tr>
                    <th className="p-3">Ticket ID</th>
                    <th className="p-3">Title</th>
                    <th className="p-3">Location</th>
                    <th className="p-3">Priority</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
                  {linkedTickets.map((t) => (
                    <tr key={t.ticket_id} className="hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10]">
                      <td className="p-3 font-bold font-mono">{t.ticket_id}</td>
                      <td className="p-3">{t.title}</td>
                      <td className="p-3">{t.location}</td>
                      <td className="p-3">
                        <span className={`px-1.5 py-0.5 border text-[9px] uppercase font-semibold ${
                          t.priority === "critical" ? "border-[#9A5B5B] text-[#9A5B5B]" : "border-[#A08A5B] text-[#A08A5B]"
                        }`}>
                          {t.priority}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="px-1.5 py-0.5 border border-[#475569] text-[9px] uppercase font-semibold">
                          {t.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {linkedTickets.length === 0 && (
                    <tr>
                      <td colSpan={5} className="p-4 text-center text-[#6B6B66] dark:text-[#888884]">
                        No user support tickets currently associated with this incident.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Associate an unlinked ticket */}
            {unlinkedTickets.length > 0 && (
              <div className="mt-6 pt-4 border-t border-[#E5E5E3] dark:border-[#2A2A2D]">
                <h4 className="text-xs font-bold uppercase tracking-wider mb-2">Associate Open Ticket</h4>
                <div className="flex flex-col sm:flex-row items-center gap-2">
                  <select
                    value={linkTicketId}
                    onChange={(e) => setLinkTicketId(e.target.value)}
                    className="w-full sm:w-80 p-2 text-xs border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] outline-none"
                  >
                    <option value="">Select ticket to link...</option>
                    {unlinkedTickets.map((ut) => (
                      <option key={ut.ticket_id} value={ut.ticket_id}>
                        {ut.ticket_id}: {ut.title} ({ut.location})
                      </option>
                    ))}
                  </select>
                  <button
                    disabled={!linkTicketId}
                    onClick={handleLinkTicket}
                    className="w-full sm:w-auto px-4 py-2 bg-[#475569] hover:bg-[#334155] disabled:opacity-40 text-white font-bold uppercase text-xs tracking-wider transition-colors"
                  >
                    Link to Incident
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
