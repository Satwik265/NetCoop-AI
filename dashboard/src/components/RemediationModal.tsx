import { apiFetch } from '../auth/AuthContext';
import React, { useState } from "react";
import { RemediationAction } from "../types/protocol";

interface Props {
  incidentId: string;
  actions: RemediationAction[];
  onActionSimulated: () => void;
}

export const RemediationModal: React.FC<Props> = ({
  incidentId,
  actions,
  onActionSimulated,
}) => {
  const [selectedAction, setSelectedAction] = useState<RemediationAction | null>(
    actions[0] || null
  );
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  if (actions.length === 0) {
    return (
      <div className="bg-[#161618] border border-[#2A2A2D] p-5 text-xs font-mono text-[#888884] text-center">
        No simulated remediation actions currently recommended for this incident.
      </div>
    );
  }

  const handleSimulate = async () => {
    if (!selectedAction) return;
    setExecuting(true);
    setResult(null);

    try {
      const resp = await apiFetch(`/api/incidents/${incidentId}/remediate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_id: selectedAction.action_id,
          operator: "human_operator_dashboard",
        }),
      });
      const data = await resp.json();
      setResult(data);
      onActionSimulated();
    } catch (err) {
      setResult({ success: false, message: "Remediation request error." });
    } finally {
      setExecuting(false);
    }
  };

  const action = selectedAction || actions[0];

  return (
    <div className="bg-[#161618] border border-[#2A2A2D] p-5">
      <div className="flex flex-wrap items-center justify-between border-b border-[#2A2A2D] pb-3 mb-4 gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-wide uppercase font-mono text-[#EDEDEA]">
            Simulated Remediation & Human-in-the-Loop Gateway
          </h2>
          <div className="text-xs text-[#888884] font-mono mt-0.5">
            Safety Guarantee: Real infrastructure is never modified. All execution occurs in simulation.
          </div>
        </div>

        {actions.length > 1 && (
          <select
            value={action.action_id}
            onChange={(e) => {
              const act = actions.find((a) => a.action_id === e.target.value);
              if (act) setSelectedAction(act);
            }}
            className="bg-[#0F0F10] border border-[#2A2A2D] text-[#EDEDEA] px-2 py-1 text-xs font-mono outline-none"
          >
            {actions.map((a) => (
              <option key={a.action_id} value={a.action_id}>
                {a.action_id} ({a.device})
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="space-y-4">
        <div className="bg-[#0F0F10] border border-[#2A2A2D] p-4 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[#888884] uppercase">Action:</span>
            <span className="text-[#EDEDEA] font-semibold">{action.title}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[#888884] uppercase">Target Device:</span>
            <span className="text-[#EDEDEA]">{action.device}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[#888884] uppercase">Risk Assessment:</span>
            <span
              className={`uppercase font-semibold ${
                action.risk_level === "high"
                  ? "text-[#9A5B5B]"
                  : action.risk_level === "medium"
                  ? "text-[#A08A5B]"
                  : "text-[#5E7A6A]"
              }`}
            >
              {action.risk_level}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[#888884] uppercase">Blast Radius:</span>
            <span className="text-[#EDEDEA]">
              {action.blast_radius_devices.join(", ")}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[#0F0F10] border border-[#2A2A2D] p-3 text-xs font-mono">
            <div className="text-[#888884] uppercase text-[10px] mb-2 font-medium">
              Simulated Configuration Commands
            </div>
            <pre className="text-[#EDEDEA] leading-relaxed whitespace-pre-wrap">
              {action.commands.join("\n")}
            </pre>
          </div>

          <div className="bg-[#0F0F10] border border-[#2A2A2D] p-3 text-xs font-mono">
            <div className="text-[#888884] uppercase text-[10px] mb-2 font-medium">
              Automated Rollback Commands
            </div>
            <pre className="text-[#888884] leading-relaxed whitespace-pre-wrap">
              {action.rollback_commands.length > 0
                ? action.rollback_commands.join("\n")
                : "No rollback commands required."}
            </pre>
          </div>
        </div>

        {result && (
          <div
            className={`p-3 border text-xs font-mono ${
              result.success
                ? "bg-[#5E7A6A]/10 border-[#5E7A6A]/40 text-[#5E7A6A]"
                : "bg-[#9A5B5B]/10 border-[#9A5B5B]/40 text-[#9A5B5B]"
            }`}
          >
            <div className="font-semibold uppercase mb-1">
              {result.success ? "Simulated Execution Successful" : "Pre-flight Check Failed"}
            </div>
            <div>{result.message}</div>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={handleSimulate}
            disabled={executing}
            className="px-4 py-2 bg-[#475569] text-white text-xs font-mono uppercase tracking-wider font-medium hover:bg-[#334155] disabled:opacity-50 transition-colors"
          >
            {executing ? "Simulating..." : "Approve & Simulate Execution"}
          </button>
        </div>
      </div>
    </div>
  );
};

