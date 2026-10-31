import React, { useState } from "react";
import { UnifiedDiagnosticReport } from "../../types/protocol";

interface NocViewProps {
  report: UnifiedDiagnosticReport | null;
  onInvestigateIncident: () => void;
}

interface AlertItem {
  id: string;
  severity: "critical" | "warning" | "info";
  device: string;
  message: string;
  timestamp: string;
  acknowledged: boolean;
  assignedTo: string | null;
}

export const NocView: React.FC<NocViewProps> = ({ report, onInvestigateIncident }) => {
  const [alerts, setAlerts] = useState<AlertItem[]>([
    {
      id: "alt-101",
      severity: "critical",
      device: "spine-01:et-0/0/1",
      message: "Interface egress queue utilization > 90% (4,500 drops/s)",
      timestamp: "2 mins ago",
      acknowledged: false,
      assignedTo: "Tier-1 NOC",
    },
    {
      id: "alt-102",
      severity: "warning",
      device: "leaf-02:xe-0/0/4",
      message: "Physical layer CRC error burst detected on optical transceiver",
      timestamp: "8 mins ago",
      acknowledged: true,
      assignedTo: "Shift Lead",
    },
    {
      id: "alt-103",
      severity: "warning",
      device: "ap-hostel-04",
      message: "High channel utilization (84%) on 5GHz radio",
      timestamp: "14 mins ago",
      acknowledged: false,
      assignedTo: null,
    },
    {
      id: "alt-104",
      severity: "info",
      device: "wan-01",
      message: "BGP route policy re-convergence completed across ISP peer",
      timestamp: "22 mins ago",
      acknowledged: true,
      assignedTo: "System",
    },
  ]);

  const [escalated, setEscalated] = useState<string | null>(null);

  const handleAcknowledge = (id: string) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a))
    );
  };

  const handleEscalate = (id: string) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, assignedTo: "Tier-2 Engineering (Escalated)" } : a))
    );
    setEscalated(`Alert ${id} escalated to Tier-2 Network Engineering.`);
    setTimeout(() => setEscalated(null), 3000);
  };

  const criticalCount = alerts.filter((a) => a.severity === "critical" && !a.acknowledged).length;

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Top NOC KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider">
            Overall Fabric Health
          </div>
          <div className="mt-2 text-2xl font-bold text-[#111111] dark:text-[#EDEDEA]">
            98.4%
          </div>
          <div className="mt-1 text-[10px] text-[#5E7A6A]">
            Nominal Operational State
          </div>
        </div>

        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider">
            Active Incidents
          </div>
          <div className="mt-2 text-2xl font-bold text-[#A08A5B]">
            {report?.status === "diagnosed" ? "1 Active" : "0 Active"}
          </div>
          <div className="mt-1 text-[10px] text-[#6B6B66] dark:text-[#888884]">
            ID: {report?.incident_id || "inc-link-congestion-42"}
          </div>
        </div>

        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider">
            Unack'd Critical Alerts
          </div>
          <div className={`mt-2 text-2xl font-bold ${criticalCount > 0 ? "text-[#9A5B5B]" : "text-[#5E7A6A]"}`}>
            {criticalCount}
          </div>
          <div className="mt-1 text-[10px] text-[#6B6B66] dark:text-[#888884]">
            Requires Operator Triage
          </div>
        </div>

        <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4">
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider">
            Device Availability
          </div>
          <div className="mt-2 text-2xl font-bold text-[#111111] dark:text-[#EDEDEA]">
            7 / 7 Online
          </div>
          <div className="mt-1 text-[10px] text-[#5E7A6A]">
            0 Offline | 2 Degrading
          </div>
        </div>
      </div>

      {escalated && (
        <div className="p-3 border border-[#5E7A6A] bg-[#5E7A6A]/10 text-[#5E7A6A]">
          {escalated}
        </div>
      )}

      {/* Main Grid: Active Incident Triage & Alerts Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Active Incident Triage Card (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                Current Incident Under Investigation
              </span>
              <span className="px-2 py-0.5 text-[9px] border border-[#9A5B5B] text-[#9A5B5B]">
                PRIORITY: HIGH
              </span>
            </div>

            <div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Incident ID</div>
              <div className="text-xs font-bold text-[#111111] dark:text-[#EDEDEA]">
                {report?.incident_id || "inc-link-congestion-42"}
              </div>
            </div>

            <div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Probable Root Cause</div>
              <div className="text-xs text-[#A08A5B] font-semibold">
                {report?.probable_cause || "INTERFACE_SATURATION_QUEUE_OVERFLOW"}
              </div>
            </div>

            <div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Diagnostic Confidence</div>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] h-2">
                  <div
                    className="bg-[#475569] h-full"
                    style={{ width: `${Math.round((report?.confidence || 0.94) * 100)}%` }}
                  ></div>
                </div>
                <span className="text-[11px] font-bold">
                  {Math.round((report?.confidence || 0.94) * 100)}%
                </span>
              </div>
            </div>

            <div>
              <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">Impacted Devices</div>
              <div className="flex flex-wrap gap-1 mt-1">
                {(report?.affected_devices || ["spine-01", "leaf-02"]).map((dev) => (
                  <span
                    key={dev}
                    className="px-2 py-0.5 border border-[#475569] text-[#475569] dark:text-[#EDEDEA] text-[10px]"
                  >
                    {dev}
                  </span>
                ))}
              </div>
            </div>

            <div className="pt-2">
              <button
                onClick={onInvestigateIncident}
                className="w-full py-2 border border-[#111111] dark:border-[#EDEDEA] bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10] uppercase font-semibold tracking-wider hover:opacity-90 transition-opacity"
              >
                Open Full Technical Investigation
              </button>
            </div>
          </div>
        </div>

        {/* Right: Live Alerts & Triage Queue (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="border border-[#E5E5E3] dark:border-[#2A2A2D] bg-[#FFFFFF] dark:bg-[#161618] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-2">
              <span className="font-semibold text-[#111111] dark:text-[#EDEDEA] uppercase tracking-wider">
                Live Alert Triage Queue ({alerts.length})
              </span>
              <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                Auto-correlated by Multi-Agent Synthesizer
              </span>
            </div>

            <div className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
              {alerts.map((alt) => (
                <div key={alt.id} className="py-2.5 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-1.5 py-0.2 border text-[9px] uppercase font-bold ${
                          alt.severity === "critical"
                            ? "border-[#9A5B5B] text-[#9A5B5B] bg-[#9A5B5B]/10"
                            : alt.severity === "warning"
                            ? "border-[#A08A5B] text-[#A08A5B] bg-[#A08A5B]/10"
                            : "border-[#475569] text-[#475569]"
                        }`}
                      >
                        {alt.severity}
                      </span>
                      <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">
                        {alt.device}
                      </span>
                    </div>
                    <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
                      {alt.timestamp}
                    </span>
                  </div>

                  <p className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
                    {alt.message}
                  </p>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[10px] text-[#475569] dark:text-[#888884]">
                      Assigned: {alt.assignedTo || "Unassigned"}
                    </span>

                    <div className="space-x-2">
                      {!alt.acknowledged && (
                        <button
                          onClick={() => handleAcknowledge(alt.id)}
                          className="px-2 py-0.5 border border-[#475569] text-[10px] text-[#475569] dark:text-[#EDEDEA] hover:bg-[#475569] hover:text-white transition-colors"
                        >
                          ACKNOWLEDGE
                        </button>
                      )}
                      <button
                        onClick={() => handleEscalate(alt.id)}
                        className="px-2 py-0.5 border border-[#A08A5B] text-[10px] text-[#A08A5B] hover:bg-[#A08A5B]/10 transition-colors"
                      >
                        ESCALATE
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

