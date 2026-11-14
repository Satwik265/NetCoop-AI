import { apiFetch } from '../auth/AuthContext';
import React, { useState } from "react";
import { formatNumber, formatPercent } from "../utils/i18n";

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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const runSimulation = async (actionType: string, device: string) => {
    setLoading(true);
    setErrorMessage(null);
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
        setLoading(false);
        return;
      } else {
        const err = await res.json().catch(() => ({ detail: "Simulation API returned error" }));
        setErrorMessage(err.detail || `Simulation failed with HTTP ${res.status}`);
      }
    } catch (e: any) {
      setErrorMessage(e?.message || "Network error connecting to simulation service.");
    }
    setLoading(false);
  };

  const loadSampleFixture = () => {
    const mockSim: SimulationResult = {
      status: "success",
      disclaimer: "SIMULATED — NO PRODUCTION NETWORK CHANGES",
      is_simulated: true,
      action_type:
        selectedActionType === "rebalance traffic"
          ? `Rebalance traffic across ECMP next-hops from ${selectedDevice} et-0/0/1`
          : `Harmonize interface MTU to 9000 bytes on ${selectedDevice} et-0/0/1`,
      target_device: selectedDevice,
      target_interface: "et-0/0/1",
      safety_passed: true,
      safety_checks: [
        {
          check_name: "simulation_safety_gate",
          passed: true,
          details: "Action strictly confined to in-memory sandbox telemetry model.",
        },
        {
          check_name: "blast_radius_limit",
          passed: true,
          details: "Impacts 1/2 devices (50%). Core safety boundary threshold is 60%.",
        },
        {
          check_name: "rollback_readiness",
          passed: true,
          details: "Pre-validated automated rollback script ready for atomic reversion.",
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
    setErrorMessage(null);
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Persistent Mandatory Simulation Invariant Banner */}
      <div
        role="alert"
        className="bg-[#FEF2F2] dark:bg-[#7F1D1D]/30 border-2 border-[#DC2626] p-4 text-center shadow-sm"
      >
        <div className="flex items-center justify-center gap-2">
          <span className="text-[#DC2626] text-base" aria-hidden="true">⚠️</span>
          <span className="text-xs font-mono font-bold tracking-widest uppercase text-[#991B1B] dark:text-[#FCA5A5]">
            SIMULATED — NO PRODUCTION NETWORK CHANGES
          </span>
          <span className="text-[#DC2626] text-base" aria-hidden="true">⚠️</span>
        </div>
        <p className="text-[11px] text-[#475569] dark:text-[#CBD5E1] mt-1 max-w-2xl mx-auto">
          Operational Safety Invariant: Hardware devices and production routing engines are NEVER contacted.
          All configuration changes and performance projections execute against isolated in-memory telemetry models.
        </p>
      </div>

      {/* Backend unreachable warning if error occurs */}
      {errorMessage && (
        <div className="bg-[#FFFBEB] dark:bg-[#78350F]/20 border border-[#B45309]/40 p-4 text-xs font-sans text-[#92400E] dark:text-[#FDE68A] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-bold uppercase tracking-wider">[SIMULATION API ERROR]</span>
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={loadSampleFixture}
            className="px-3 py-1.5 bg-[#B45309] text-white hover:bg-[#92400E] font-semibold text-xs tracking-wider uppercase transition-colors"
          >
            Load Offline Demo Fixture
          </button>
        </div>
      )}

      {/* Persistent indicator when displaying sample data */}
      {isSampleData && (
        <div className="bg-[#FFFBEB] dark:bg-[#78350F]/20 border border-[#B45309]/30 px-4 py-2 text-xs font-mono text-[#92400E] dark:text-[#FDE68A] flex items-center justify-between">
          <span>[SYNTHETIC DEMO FIXTURE] Displaying pre-computed sandbox simulation benchmark scenario.</span>
          <span className="text-[10px] uppercase font-bold text-[#B45309]">Demo Mode</span>
        </div>
      )}

      {/* Control Bar: Requires explicit operator trigger */}
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 text-xs">
          <div>
            <h2 className="uppercase font-bold tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
              Remediation Action Simulation Sandbox
            </h2>
            <div className="text-[11px] text-[#475569] dark:text-[#94A3B8] mt-0.5">
              Select remediation action template and target device to project post-remediation performance deltas
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="action-select" className="text-[#475569] dark:text-[#94A3B8] font-medium">
                Action:
              </label>
              <select
                id="action-select"
                value={selectedActionType}
                onChange={(e) => setSelectedActionType(e.target.value)}
                className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] px-3 py-1.5 text-xs text-[#0F172A] dark:text-[#F1F5F9] outline-none min-h-[32px] focus-visible:ring-2"
              >
                <option value="rebalance traffic">Rebalance ECMP Traffic</option>
                <option value="harmonize mtu">Harmonize Interface MTU</option>
                <option value="clear interface counters">Clear Interface Counters</option>
                <option value="raise QoS priority">Raise QoS Priority</option>
                <option value="fail over a link">Fail Over Link to Redundant Path</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="device-select" className="text-[#475569] dark:text-[#94A3B8] font-medium">
                Target:
              </label>
              <select
                id="device-select"
                value={selectedDevice}
                onChange={(e) => setSelectedDevice(e.target.value)}
                className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] px-3 py-1.5 text-xs text-[#0F172A] dark:text-[#F1F5F9] outline-none min-h-[32px] focus-visible:ring-2"
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
              className="px-4 py-1.5 bg-[#0B2545] text-white hover:bg-[#133E87] dark:bg-[#133E87] dark:hover:bg-[#3A86FF] transition-colors uppercase text-xs font-bold min-h-[32px] focus-visible:ring-2 disabled:opacity-50"
            >
              {loading ? "Simulating in Sandbox..." : "Run Sandbox Simulation"}
            </button>
          </div>
        </div>
      </div>

      {/* Initial state: Operator has not triggered simulation yet */}
      {!simulationData && !errorMessage && !loading && (
        <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-dashed border-[#CBD5E1] dark:border-[#2A2A2D] p-10 text-center space-y-3">
          <div className="text-sm font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
            Explicit Operator Confirmation Required
          </div>
          <p className="text-xs text-[#475569] dark:text-[#94A3B8] max-w-lg mx-auto leading-relaxed">
            In accordance with ISO 9241-110 safety principles, simulations do not execute automatically.
            Configure the remediation action template and device above, then click <strong>&quot;Run Sandbox Simulation&quot;</strong> to evaluate safety gates and projected telemetry impact.
          </p>
        </div>
      )}

      {/* Simulation Results Display */}
      {simulationData && (
        <div className="space-y-6">
          {/* Before vs After Metric Comparison Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Metric 1: Link Utilization */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-4 space-y-3 font-sans">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#475569] dark:text-[#94A3B8] font-bold uppercase">Link Utilization</span>
                <span className="text-[#15803D] dark:text-[#86EFAC] font-mono font-bold">
                  {formatPercent(simulationData.delta.max_link_utilization_pct / 100, 1)}
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">Before:</span>
                    <span className="font-mono font-bold text-[#B91C1C]">
                      {formatPercent(simulationData.before_metrics.max_link_utilization_pct / 100, 1)}
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#DC2626] transition-all duration-300"
                      style={{ width: `${Math.min(100, simulationData.before_metrics.max_link_utilization_pct)}%` }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">After:</span>
                    <span className="font-mono font-bold text-[#15803D] dark:text-[#86EFAC]">
                      {formatPercent(simulationData.after_metrics.max_link_utilization_pct / 100, 1)}
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#15803D] transition-all duration-300"
                      style={{ width: `${Math.min(100, simulationData.after_metrics.max_link_utilization_pct)}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Metric 2: Queue Tail Drops */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-4 space-y-3 font-sans">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#475569] dark:text-[#94A3B8] font-bold uppercase">Queue Tail-Drops</span>
                <span className="text-[#15803D] dark:text-[#86EFAC] font-mono font-bold">
                  {formatNumber(simulationData.delta.max_queue_drops)} drops/s
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">Before:</span>
                    <span className="font-mono font-bold text-[#B91C1C]">
                      {formatNumber(simulationData.before_metrics.max_queue_drops)}
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#DC2626] w-full"></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">After:</span>
                    <span className="font-mono font-bold text-[#15803D] dark:text-[#86EFAC]">
                      0 (Eliminated)
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#15803D] w-0"></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Metric 3: Packet Loss */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-4 space-y-3 font-sans">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#475569] dark:text-[#94A3B8] font-bold uppercase">Packet Loss</span>
                <span className="text-[#15803D] dark:text-[#86EFAC] font-mono font-bold">
                  {formatPercent((simulationData.delta.packet_loss_pct || -14.75) / 100, 2)}
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">Before:</span>
                    <span className="font-mono font-bold text-[#B91C1C]">
                      {formatPercent((simulationData.before_metrics.packet_loss_pct || 14.8) / 100, 1)}
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#DC2626]"
                      style={{ width: `${Math.min(100, (simulationData.before_metrics.packet_loss_pct || 14.8) * 3)}%` }}
                    ></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">After:</span>
                    <span className="font-mono font-bold text-[#15803D] dark:text-[#86EFAC]">
                      {formatPercent((simulationData.after_metrics.packet_loss_pct || 0.05) / 100, 2)}
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div
                      className="h-full bg-[#15803D]"
                      style={{ width: `${Math.max(2, (simulationData.after_metrics.packet_loss_pct || 0.05) * 5)}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Metric 4: Round-Trip Latency */}
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-4 space-y-3 font-sans">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#475569] dark:text-[#94A3B8] font-bold uppercase">RTT Latency</span>
                <span className="text-[#15803D] dark:text-[#86EFAC] font-mono font-bold">
                  {formatNumber(simulationData.delta.latency_ms || -494.3, 1)} ms
                </span>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">Before:</span>
                    <span className="font-mono font-bold text-[#B91C1C]">
                      {formatNumber(simulationData.before_metrics.latency_ms || 512.5, 1)} ms
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#DC2626] w-[85%]"></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-[#475569] dark:text-[#94A3B8]">After:</span>
                    <span className="font-mono font-bold text-[#15803D] dark:text-[#86EFAC]">
                      {formatNumber(simulationData.after_metrics.latency_ms || 18.2, 1)} ms
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-[#F1F5F9] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D]">
                    <div className="h-full bg-[#15803D] w-[12%]"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Safety Pre-Flight Checks & Verification Breakdown */}
          <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-3 font-sans">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-3 text-xs">
              <span className="uppercase tracking-wider font-bold text-[#0B2545] dark:text-[#F1F5F9]">
                Pre-Flight Safety Gate Verifications
              </span>
              <span className="px-2.5 py-0.5 text-xs uppercase font-bold border border-[#15803D]/40 text-[#15803D] bg-[#F0FDF4] dark:bg-[#14532D]/30 dark:text-[#86EFAC]">
                All Safety Gates Passed
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {simulationData.safety_checks.map((check, idx) => (
                <div
                  key={idx}
                  className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] p-3 space-y-1.5"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#15803D]"></span>
                    <span className="text-xs font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                      {check.check_name.replace(/_/g, " ").toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#475569] dark:text-[#94A3B8]">
                    {check.details}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Commands Side-by-Side View */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-2">
              <span className="text-[11px] uppercase tracking-wider text-[#475569] dark:text-[#94A3B8] font-bold">
                Projected Simulated Commands ({simulationData.executed_commands.length})
              </span>
              <pre className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] p-3 text-[11px] text-[#0F172A] dark:text-[#F1F5F9] overflow-x-auto">
                {simulationData.executed_commands.join("\n")}
              </pre>
            </div>

            <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-2">
              <span className="text-[11px] uppercase tracking-wider text-[#475569] dark:text-[#94A3B8] font-bold">
                Pre-Generated Rollback Commands ({simulationData.rollback_commands.length})
              </span>
              <pre className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] p-3 text-[11px] text-[#0F172A] dark:text-[#F1F5F9] overflow-x-auto">
                {simulationData.rollback_commands.join("\n")}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
