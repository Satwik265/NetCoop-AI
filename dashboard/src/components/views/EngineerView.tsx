import React from "react";
import { UnifiedDiagnosticReport } from "../../types/protocol";

interface EngineerViewProps {
  report: UnifiedDiagnosticReport | null;
  onLaunchSimulation: () => void;
  onOpenHitlQueue: () => void;
}

export const EngineerView: React.FC<EngineerViewProps> = ({
  report,
  onLaunchSimulation,
  onOpenHitlQueue,
}) => {
  const telemetryMetrics = [
    { name: "Max Link Utilization", value: "94.2%", nominal: "< 70.0%", status: "critical", delta: "+24.2%" },
    { name: "Interface Queue Drops", value: "4,500 /s", nominal: "0 /s", status: "critical", delta: "+4500" },
    { name: "Packet Loss Rate", value: "14.8%", nominal: "< 0.1%", status: "critical", delta: "+14.7%" },
    { name: "End-to-End Latency", value: "512.5 ms", nominal: "< 25.0 ms", status: "warning", delta: "+487.5ms" },
    { name: "Ping RTT Jitter", value: "84.2 ms", nominal: "< 5.0 ms", status: "warning", delta: "+79.2ms" },
    { name: "Spine-01 CPU Load", value: "34.2%", nominal: "< 75.0%", status: "ok", delta: "Normal" },
  ];

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Top Banner: Root Cause Breakdown */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider">
              Diagnosed Root Cause Analysis
            </div>
            <div className="text-base font-bold text-[#111111] dark:text-[#EDEDEA] mt-1">
              {report?.probable_cause || "INTERFACE_SATURATION_QUEUE_OVERFLOW"}
            </div>
            <p className="mt-1 text-[11px] text-[#6B6B66] dark:text-[#888884]">
              Incident ID: <code className="text-[#111111] dark:text-[#EDEDEA]">{report?.incident_id || "inc-link-congestion-42"}</code> | Network: <code className="text-[#111111] dark:text-[#EDEDEA]">{report?.network_id || "iit-bbs-campus-fabric"}</code>
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="border border-[#5E7A6A] px-3 py-1.5 bg-[#5E7A6A]/10 text-center">
              <div className="text-[9px] uppercase text-[#5E7A6A]">Calibrated Confidence</div>
              <div className="text-lg font-bold text-[#5E7A6A]">
                {Math.round((report?.confidence || 0.94) * 100)}%
              </div>
            </div>

            <div className="space-y-1">
              <button
                onClick={onLaunchSimulation}
                className="w-full px-3 py-1.5 border border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10] uppercase font-semibold hover:opacity-90 transition-opacity"
              >
                Launch Remediation Sandbox
              </button>
              <button
                onClick={onOpenHitlQueue}
                className="w-full px-3 py-1 border border-[#475569] text-[#475569] dark:text-[#EDEDEA] uppercase text-[10px] hover:bg-[#475569] hover:text-white transition-colors"
              >
                Review HITL Proposals
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Telemetry Metrics Grid */}
      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
          Live Telemetry Anomaly Indicators
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {telemetryMetrics.map((m) => (
            <div
              key={m.name}
              className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-3"
            >
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase truncate">
                {m.name}
              </div>
              <div className="mt-1 text-base font-bold text-[#111111] dark:text-[#EDEDEA]">
                {m.value}
              </div>
              <div className="mt-1 flex items-center justify-between text-[9px]">
                <span className="text-[#6B6B66] dark:text-[#888884]">Nom: {m.nominal}</span>
                <span
                  className={
                    m.status === "critical"
                      ? "text-[#9A5B5B] font-bold"
                      : m.status === "warning"
                      ? "text-[#A08A5B] font-bold"
                      : "text-[#5E7A6A]"
                  }
                >
                  {m.delta}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Transparent AI Agent Findings & Evidentiary Chain */}
      <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-[#111111] dark:text-[#EDEDEA]">
              Transparent Evidentiary Chain &amp; Cross-Agent Corroboration
            </span>
            <p className="text-[10px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
              Multi-agent corroboration showing exact metric thresholds, observation sources, and corroborating hypotheses.
            </p>
          </div>
          <span className="text-[10px] border border-[#5E7A6A] text-[#5E7A6A] px-2 py-0.5">
            CORROBORATION: 100%
          </span>
        </div>

        <div className="space-y-3">
          {(report?.evidence || [
            {
              source_agent: "telemetry_agent",
              category: "link_saturation",
              finding: "Interface spine-01:et-0/0/1 exceeded 90% bandwidth capacity threshold.",
              entity: "spine-01:et-0/0/1",
              metric_name: "link_utilization_pct",
              value: 94.2,
              unit: "percent",
              severity: "critical" as const,
            },
            {
              source_agent: "log_agent",
              category: "syslog_pattern",
              finding: "Syslog buffer drop burst detected on egress queue (4,500 drops recorded in 30s window).",
              entity: "spine-01:et-0/0/1",
              metric_name: "queue_drops",
              value: 4500,
              unit: "count",
              severity: "critical" as const,
            },
            {
              source_agent: "topology_agent",
              category: "redundancy_path",
              finding: "Secondary ECMP path via spine-02:et-0/0/2 is operating at 28.1% capacity with zero queue drops.",
              entity: "spine-02:et-0/0/2",
              metric_name: "link_utilization_pct",
              value: 28.1,
              unit: "percent",
              severity: "info" as const,
            },
          ]).map((ev, idx) => (
            <div
              key={idx}
              className="p-3 border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FAFAF9] dark:bg-[#0F0F10] space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-1.5 py-0.2 border border-[#475569] text-[#475569] text-[9px] uppercase font-bold">
                    {ev.source_agent}
                  </span>
                  <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                    {ev.entity}
                  </span>
                </div>
                <span
                  className={`px-1.5 py-0.2 border text-[9px] uppercase ${
                    ev.severity === "critical"
                      ? "border-[#9A5B5B] text-[#9A5B5B]"
                      : ev.severity === "warning"
                      ? "border-[#A08A5B] text-[#A08A5B]"
                      : "border-[#475569] text-[#475569]"
                  }`}
                >
                  {ev.severity}
                </span>
              </div>

              <p className="text-[11px] text-[#6B6B66] dark:text-[#888884] leading-relaxed">
                {ev.finding}
              </p>

              {ev.metric_name && (
                <div className="text-[10px] text-[#111111] dark:text-[#EDEDEA]">
                  Metric: <code className="bg-[#FFFFFF] dark:bg-[#161618] px-1 py-0.2 border border-[#E5E5E3] dark:border-[#2A2A2D]">{ev.metric_name} = {String(ev.value)} {ev.unit || ""}</code>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

