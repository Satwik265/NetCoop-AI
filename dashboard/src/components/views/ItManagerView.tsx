import React from "react";
import { UnifiedDiagnosticReport } from "../../types/protocol";

interface ItManagerViewProps {
  report?: UnifiedDiagnosticReport | null;
  onSelectIncident?: (id: string) => void;
}

export const ItManagerView: React.FC<ItManagerViewProps> = ({
  report,
  onSelectIncident,
}) => {
  const kpis = [
    { title: "Network Fabric Availability", value: "99.98%", target: "SLA >= 99.95%", status: "ok" },
    { title: "Mean Time to Detect (MTTD)", value: "1.4 min", target: "Target < 5.0 min", status: "ok" },
    { title: "Mean Time to Resolve (MTTR)", value: "4.8 min", target: "Target < 15.0 min", status: "ok" },
    { title: "Remediation Success Rate", value: "96.4%", target: "Target >= 95.0%", status: "ok" },
    { title: "Operator HITL Approvals", value: "18 / 19", target: "94.7% Consensus", status: "ok" },
    { title: "Rollback Invocations", value: "1", target: "Sandbox Protected", status: "warning" },
  ];

  const categoryBreakdown = [
    { category: "Link Congestion & Buffer Saturation", count: 12, pct: 40 },
    { category: "Physical Layer Optical CRC Flaps", count: 8, pct: 26 },
    { category: "Path MTU Blackholing", count: 6, pct: 20 },
    { category: "BGP / Routing Convergence Flaps", count: 4, pct: 14 },
  ];

  const recurringIncidents = [
    {
      id: "inc-link-congestion-42",
      cause: "INTERFACE_SATURATION_QUEUE_OVERFLOW",
      occurrences: 4,
      lastSeen: "2 hours ago",
      impact: "High (Egress Buffer Drops on spine-01)",
    },
    {
      id: "inc-organizer-hardware",
      cause: "PHYSICAL_LAYER_CRC_DEGRADATION",
      occurrences: 3,
      lastSeen: "Yesterday",
      impact: "Medium (Leaf-02 Port CRC Drops)",
    },
    {
      id: "inc-mtu-blackhole-01",
      cause: "PATH_MTU_MISMATCH_DISCARD",
      occurrences: 2,
      lastSeen: "3 days ago",
      impact: "Low (Jumbo Frame Dropping)",
    },
  ];

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Top Banner */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider">
              Executive Service Delivery &amp; SLA Management
            </div>
            <h2 className="text-base font-bold text-[#111111] dark:text-[#EDEDEA] mt-1">
              Campus Core Fabric Operational Performance
            </h2>
            <p className="mt-0.5 text-[11px] text-[#6B6B66] dark:text-[#888884]">
              High-level telemetry summaries, operational SLAs, and team workload analytics.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="border border-[#5E7A6A] text-[#5E7A6A] px-2.5 py-1 text-[11px] font-bold">
              SLA STATUS: COMPLIANT (99.98%)
            </span>
          </div>
        </div>
      </div>

      {/* Active Incident Alert Banner if present */}
      {report && (
        <div className="border border-[#475569] bg-[#FAFAF9] dark:bg-[#0F0F10] p-3 flex items-center justify-between text-xs">
          <div>
            <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">Active Diagnosed Incident: </span>
            <span className="text-[#475569]">{report.incident_id}</span>
            <span className="text-[#6B6B66] dark:text-[#888884] ml-2">({report.probable_cause || "Analyzing telemetry"})</span>
          </div>
          <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
            Confidence: {Math.round(report.confidence * 100)}%
          </span>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map((kpi) => (
          <div
            key={kpi.title}
            className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-3 space-y-1"
          >
            <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase truncate">
              {kpi.title}
            </div>
            <div className="text-lg font-bold text-[#111111] dark:text-[#EDEDEA]">
              {kpi.value}
            </div>
            <div
              className={`text-[9px] ${
                kpi.status === "ok" ? "text-[#5E7A6A]" : "text-[#A08A5B]"
              }`}
            >
              {kpi.target}
            </div>
          </div>
        ))}
      </div>

      {/* Breakdown: Categories & Recurring Incidents */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Category Distribution (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                Incident Volume by Root Cause (30 Days)
              </span>
              <span className="text-[10px] text-[#6B6B66]">30 Total</span>
            </div>

            <div className="space-y-3">
              {categoryBreakdown.map((item) => (
                <div key={item.category} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-[#111111] dark:text-[#EDEDEA] truncate">{item.category}</span>
                    <span className="font-bold">{item.count} ({item.pct}%)</span>
                  </div>
                  <div className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] h-2">
                    <div
                      className="bg-[#475569] h-full"
                      style={{ width: `${item.pct}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Recurring Incidents Drill-Down (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                Recurring Incident Patterns &amp; Impact
              </span>
              <span className="text-[10px] text-[#A08A5B]">Actionable Technical Debt</span>
            </div>

            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
              {recurringIncidents.map((inc) => (
                <div key={inc.id} className="py-2.5 flex items-center justify-between gap-4">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">{inc.id}</span>
                      <span className="px-1.5 py-0.2 border border-[#A08A5B] text-[#A08A5B] text-[9px] uppercase">
                        {inc.occurrences}x Recurrence
                      </span>
                    </div>
                    <div className="text-[11px] text-[#A08A5B] font-semibold">{inc.cause}</div>
                    <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">{inc.impact}</div>
                  </div>

                  <button
                    onClick={() => onSelectIncident?.(inc.id)}
                    className="px-2.5 py-1 border border-[#475569] text-[#475569] dark:text-[#EDEDEA] hover:bg-[#475569] hover:text-white transition-colors text-[10px] uppercase font-semibold whitespace-nowrap"
                  >
                    Drill Down
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
