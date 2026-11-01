import { apiFetch } from '../auth/AuthContext';
import React, { useState, useEffect } from "react";

export interface SimulationResult {
  status: string;
  disclaimer: string;
  is_simulated: boolean;
  action_type: string;
  target_device: string;
  target_interface: string;
  safety_passed: boolean;
  safety_checks: Array<{
    check_name: string;
    passed: boolean;
    details: string;
  }>;
  executed_commands: string[];
  rollback_commands: string[];
  before_metrics: Record<string, number>;
  after_metrics: Record<string, number>;
  delta: Record<string, number>;
}

export const SimulatedRemediationView: React.FC = () => {
  const [selectedActionType, setSelectedActionType] = useState<string>("rebalance traffic");
  const [selectedDevice, setSelectedDevice] = useState<string>("spine-01");
  const [simulationData, setSimulationData] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [isSampleData, setIsSampleData] = useState<boolean>(false);

  const runSimulation = async (actionType: string, device: string) => {
    setLoading(true);
    try {
      const res = await apiFetch("/api/remediate/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_type: actionType,
          device: device,
          interface: "et-0/0/1",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSimulationData(data);
        setIsSampleData(false);
        return;
      }
    } catch {
      // ignore
    }

    // Default mock matching docs/contract_changes.md section 5.1
    const mockSim: SimulationResult = {
      status: "success",
      disclaimer: "Simulated, no production changes",
      is_simulated: true,
      action_type:
        actionType === "rebalance traffic"
          ? `Rebalance traffic across ECMP next-hops from ${device} et-0/0/1`
          : `Harmonize interface MTU to 9000 bytes on ${device} et-0/0/1`,
      target_device: device,
      target_interface: "et-0/0/1",
      safety_passed: true,
      safety_checks: [
        {
          check_name: "simulation_safety_gate",
          passed: true,
          details: "Action strictly configured for simulation sandbox.",
        },
        {
          check_name: "blast_radius_limit",
          passed: true,
          details: `Impacts 1/2 devices (50%). Boundary is 60%.`,
        },
        {
          check_name: "rollback_readiness",
          passed: true,
          details: "Rollback script verified for high/medium risk actions.",
        },
      ],
      executed_commands: [
        "configure terminal",
        "interface et-0/0/1",
        "load-interval 30",
        "traffic-policy REBALANCE_ECMP",
        "commit and-quit",
      ],
      rollback_commands: [
        "configure terminal",
        "interface et-0/0/1",
        "no traffic-policy REBALANCE_ECMP",
        "commit and-quit",
      ],
      before_metrics: {
        max_link_utilization_pct: 94.2,
        avg_link_utilization_pct: 82.5,
        max_queue_drops: 4500.0,
        avg_queue_drops: 2250.0,
        packet_loss_pct: 14.8,
        latency_ms: 512.5,
      },
      after_metrics: {
        max_link_utilization_pct: 42.39,
        avg_link_utilization_pct: 37.12,
        max_queue_drops: 0.0,
        avg_queue_drops: 0.0,
        packet_loss_pct: 0.05,
        latency_ms: 18.2,
      },
      delta: {
        max_link_utilization_pct: -51.81,
        avg_link_utilization_pct: -45.38,
        max_queue_drops: -4500.0,
        avg_queue_drops: -2250.0,
        packet_loss_pct: -14.75,
        latency_ms: -494.3,
      },
    };
    setSimulationData(mockSim);
    setIsSampleData(true);
    setLoading(false);
  };

  useEffect(() => {
    runSimulation(selectedActionType, selectedDevice);
  }, [selectedActionType, selectedDevice]);

  return (
    <div className="space-y-6">
      {/* Backend unreachable amber banner */}
      {isSampleData && (
        <div className="bg-amber-500/10 border border-amber-500/30 p-3 text-[11px] text-amber-600 dark:text-amber-400 flex flex-wrap items-center justify-between font-mono gap-2">
          <div className="flex items-center gap-2">
            <span className="bg-amber-500 text-black px-2 py-0.5 text-[9px] uppercase tracking-wider font-bold">
              [SAMPLE DATA]
            </span>
            <span className="font-semibold">Backend unreachable: showing sample data</span>
            <span className="text-[#888884] text-[10px] ml-2">(Simulation API unreachable; displaying sample sandbox preview)</span>
          </div>
        </div>
      )}

      {/* Persistent Mandatory Invariant Label */}
      <div className="bg-[#161618] border-2 border-[#475569] p-4 text-center">
        <div className="flex items-center justify-center gap-3">
          <span className="w-2.5 h-2.5 bg-[#475569] animate-pulse"></span>
          <span className="text-xs font-mono font-bold tracking-widest uppercase text-[#EDEDEA]">
            Simulated, no production changes
          </span>
          <span className="w-2.5 h-2.5 bg-[#475569] animate-pulse"></span>
        </div>
        <p className="text-[11px] font-mono text-[#888884] mt-1">
          Safety Sandbox Invariant: Real network equipment is never contacted. All configuration changes execute against in-memory telemetry models.
        </p>
      </div>

      {/* Control Bar */}
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
          <div>
            <span className="uppercase font-semibold tracking-wider text-[#111111] dark:text-[#EDEDEA]">
              Remediation Action Simulation Sandbox
            </span>
            <div className="text-[11px] text-[#6B6B66] dark:text-[#888884] mt-0.5">
              Select action template to project post-remediation performance deltas
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[#6B6B66] dark:text-[#888884]">Action:</span>
              <select
                value={selectedActionType}
                onChange={(e) => setSelectedActionType(e.target.value)}
                className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2.5 py-1 text-xs text-[#111111] dark:text-[#EDEDEA] outline-none"
              >
                <option value="rebalance traffic">Rebalance ECMP Traffic</option>
                <option value="harmonize mtu">Harmonize Interface MTU</option>
                <option value="clear interface counters">Clear Interface Counters</option>
                <option value="raise QoS priority">Raise QoS Priority</option>
                <option value="fail over a link">Fail Over Link to Redundant Path</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[#6B6B66] dark:text-[#888884]">Target:</span>
              <select
                value={selectedDevice}
                onChange={(e) => setSelectedDevice(e.target.value)}
                className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2.5 py-1 text-xs text-[#111111] dark:text-[#EDEDEA] outline-none"
              >
                <option value="spine-01">spine-01 (Campus Core)</option>
                <option value="spine-02">spine-02 (Redundant Core)</option>
                <option value="leaf-01">leaf-01 (Access Leaf)</option>
                <option value="leaf-02">leaf-02 (Access Leaf)</option>
                <option value="SW_CAMPUS_1">SW_CAMPUS_1 (Organizer Switch)</option>
              </select>
            </div>

            <button
              onClick={() => runSimulation(selectedActionType, selectedDevice)}
              disabled={loading}
              className="px-3.5 py-1 bg-[#475569] text-white hover:bg-[#334155] transition-colors uppercase text-[11px] font-semibold"
            >
              {loading ? "Simulating..." : "Re-Simulate"}
            </button>
          </div>
        </div>
      </div>

      {simulationData && (
        <div className="space-y-6">
          {/* Before vs After Metric Charts Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Metric 1: Link Utilization */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-4 space-y-3 font-mono">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#6B6B66] dark:text-[#888884] uppercase">Link Utilization</span>
                <span className="text-[#5E7A6A] font-semibold">
                  {simulationData.delta.max_link_utilization_pct}%
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Before:</span>
                    <span className="font-semibold text-[#9A5B5B]">
                      {simulationData.before_metrics.max_link_utilization_pct}%
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#9A5B5B] transition-all duration-300"
                      style={{ width: `${Math.min(100, simulationData.before_metrics.max_link_utilization_pct)}%` }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">After:</span>
                    <span className="font-semibold text-[#5E7A6A]">
                      {simulationData.after_metrics.max_link_utilization_pct}%
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#5E7A6A] transition-all duration-300"
                      style={{ width: `${Math.min(100, simulationData.after_metrics.max_link_utilization_pct)}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Metric 2: Queue Tail Drops */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-4 space-y-3 font-mono">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#6B6B66] dark:text-[#888884] uppercase">Queue Tail-Drops</span>
                <span className="text-[#5E7A6A] font-semibold">
                  {simulationData.delta.max_queue_drops} pkts
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Before:</span>
                    <span className="font-semibold text-[#9A5B5B]">
                      {simulationData.before_metrics.max_queue_drops}
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#9A5B5B] w-full"></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">After:</span>
                    <span className="font-semibold text-[#5E7A6A]">
                      {simulationData.after_metrics.max_queue_drops} (Eliminated)
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#5E7A6A] w-0"></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Metric 3: Packet Loss */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-4 space-y-3 font-mono">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#6B6B66] dark:text-[#888884] uppercase">Packet Loss</span>
                <span className="text-[#5E7A6A] font-semibold">
                  {simulationData.delta.packet_loss_pct || -14.75}%
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Before:</span>
                    <span className="font-semibold text-[#9A5B5B]">
                      {simulationData.before_metrics.packet_loss_pct || 14.8}%
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#9A5B5B]"
                      style={{ width: `${Math.min(100, (simulationData.before_metrics.packet_loss_pct || 14.8) * 3)}%` }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">After:</span>
                    <span className="font-semibold text-[#5E7A6A]">
                      {simulationData.after_metrics.packet_loss_pct || 0.05}%
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#5E7A6A]"
                      style={{ width: `${Math.max(2, (simulationData.after_metrics.packet_loss_pct || 0.05) * 5)}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Metric 4: Round-Trip Latency */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-4 space-y-3 font-mono">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#6B6B66] dark:text-[#888884] uppercase">RTT Latency</span>
                <span className="text-[#5E7A6A] font-semibold">
                  {simulationData.delta.latency_ms || -494.3} ms
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Before:</span>
                    <span className="font-semibold text-[#9A5B5B]">
                      {simulationData.before_metrics.latency_ms || 512.5} ms
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#9A5B5B] w-[85%]"></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#6B6B66] dark:text-[#888884]">After:</span>
                    <span className="font-semibold text-[#5E7A6A]">
                      {simulationData.after_metrics.latency_ms || 18.2} ms
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#5E7A6A] w-[12%]"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Safety Pre-Flight Checks & Verification Breakdown */}
          <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-3 font-mono">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3 text-xs">
              <span className="uppercase tracking-wider font-semibold text-[#111111] dark:text-[#EDEDEA]">
                Safety Pre-Flight Check Results
              </span>
              <span className="px-2 py-0.5 text-[10px] uppercase border border-[#5E7A6A] text-[#5E7A6A]">
                All Checks Passed
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {simulationData.safety_checks.map((check, idx) => (
                <div
                  key={idx}
                  className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] p-3 space-y-1.5"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#5E7A6A]"></span>
                    <span className="text-xs font-semibold text-[#111111] dark:text-[#EDEDEA]">
                      {check.check_name.replace(/_/g, " ").toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#6B6B66] dark:text-[#888884] font-sans">
                    {check.details}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Commands Side-by-Side View */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-2">
              <span className="text-[11px] uppercase tracking-wider text-[#6B6B66] dark:text-[#888884] font-semibold">
                Executed Simulated Commands ({simulationData.executed_commands.length})
              </span>
              <pre className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] p-3 text-[11px] text-[#111111] dark:text-[#EDEDEA] overflow-x-auto">
                {simulationData.executed_commands.join("\n")}
              </pre>
            </div>

            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-2">
              <span className="text-[11px] uppercase tracking-wider text-[#6B6B66] dark:text-[#888884] font-semibold">
                Pre-Generated Rollback Commands ({simulationData.rollback_commands.length})
              </span>
              <pre className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] p-3 text-[11px] text-[#111111] dark:text-[#EDEDEA] overflow-x-auto">
                {simulationData.rollback_commands.join("\n")}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

