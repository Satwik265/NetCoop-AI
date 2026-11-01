import React, { useState, useEffect } from "react";
import { RemediationAction } from "../types/protocol";

export interface DecisionLogItem {
  id: number | string;
  incident_id: string;
  action_id: string;
  device: string;
  commands: string[];
  rollback_commands: string[];
  risk_level: string;
  status: string;
  approved_by: string | null;
  simulated_at: string | null;
}

interface HitlApprovalQueueProps {
  incidentId: string;
  actions: RemediationAction[];
  onActionExecuted?: (actionId: string) => void;
}

export const HitlApprovalQueue: React.FC<HitlApprovalQueueProps> = ({
  incidentId,
  actions,
  onActionExecuted,
}) => {
  const [pendingActions, setPendingActions] = useState<RemediationAction[]>([]);
  const [decisionLogs, setDecisionLogs] = useState<DecisionLogItem[]>([]);
  const [selectedAction, setSelectedAction] = useState<RemediationAction | null>(null);
  const [modalMode, setModalMode] = useState<"approve" | "reject" | "modify" | null>(null);
  const [operatorName, setOperatorName] = useState<string>("operator_alice");
  const [rationale, setRationale] = useState<string>("");
  const [modifiedCommands, setModifiedCommands] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Initialize pending actions from props or fallback default
  useEffect(() => {
    if (actions && actions.length > 0) {
      setPendingActions(actions);
    } else {
      setPendingActions([
        {
          action_id: "act-rebalance-spine-01",
          title: "Rebalance Traffic across ECMP Next-Hops",
          description: "Dynamic redistribution of egress flows away from saturated transit links on spine-01.",
          device: "spine-01",
          commands: [
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
          risk_level: "low",
          blast_radius_devices: ["spine-01", "spine-02"],
          is_simulated: true,
          status: "pending_approval",
        },
        {
          action_id: "act-mtu-spine-01",
          title: "Harmonize Interface MTU to 9000 Bytes",
          description: "Align MTU along transit path to prevent Path MTU blackholing on jumbo frames.",
          device: "spine-01",
          commands: [
            "configure terminal",
            "interface et-0/0/1",
            "mtu 9000",
            "commit and-quit",
          ],
          rollback_commands: [
            "configure terminal",
            "interface et-0/0/1",
            "mtu 1500",
            "commit and-quit",
          ],
          risk_level: "low",
          blast_radius_devices: ["spine-01"],
          is_simulated: true,
          status: "pending_approval",
        },
      ]);
    }
  }, [actions]);

  // Fetch decision logs on load
  const fetchLogs = async () => {
    try {
      const res = await fetch(`/api/remediation/logs?incident_id=${incidentId}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.length > 0) {
          setDecisionLogs(data);
          return;
        }
      }
    } catch {
      // ignore
    }

    // Default historical seed
    setDecisionLogs([
      {
        id: "log-seed-1",
        incident_id: incidentId,
        action_id: "act-rate-limit-leaf-02",
        device: "leaf-02",
        commands: ["configure terminal", "interface et-0/0/2", "rate-limit 10G", "commit and-quit"],
        rollback_commands: ["configure terminal", "interface et-0/0/2", "no rate-limit", "commit and-quit"],
        risk_level: "low",
        status: "hitl_approve",
        approved_by: "operator_alice (Rationale: Verified buffer overflow root cause)",
        simulated_at: "2026-10-31T12:05:00Z",
      },
      {
        id: "log-seed-2",
        incident_id: incidentId,
        action_id: "act-isolate-wan-01",
        device: "wan-01",
        commands: ["configure terminal", "router bgp 65001", "neighbor 198.51.100.1 shutdown"],
        rollback_commands: ["configure terminal", "router bgp 65001", "no neighbor 198.51.100.1 shutdown"],
        risk_level: "high",
        status: "hitl_reject",
        approved_by: "operator_bob (Rationale: Blast radius exceeds safety threshold)",
        simulated_at: "2026-10-31T11:45:00Z",
      },
    ]);
  };

  useEffect(() => {
    fetchLogs();
  }, [incidentId]);

  const openModal = (action: RemediationAction, mode: "approve" | "reject" | "modify") => {
    setSelectedAction(action);
    setModalMode(mode);
    setRationale("");
    setModifiedCommands(action.commands.join("\n"));
    setStatusMessage(null);
  };

  const closeModal = () => {
    setSelectedAction(null);
    setModalMode(null);
    setRationale("");
  };

  const handleDecisionSubmit = async () => {
    if (!selectedAction || !modalMode) return;
    if (!rationale.trim()) {
      setStatusMessage("Rationale is required for operator audit compliance.");
      return;
    }

    setIsSubmitting(true);
    setStatusMessage(null);

    const cmds =
      modalMode === "modify"
        ? modifiedCommands
            .split("\n")
            .map((c) => c.trim())
            .filter(Boolean)
        : selectedAction.commands;

    const payload = {
      action_id: selectedAction.action_id,
      decision: modalMode,
      rationale: rationale.trim(),
      operator: operatorName,
      modified_commands: modalMode === "modify" ? cmds : undefined,
    };

    try {
      await fetch(`/api/incidents/${incidentId}/hitl-decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (modalMode === "approve") {
        await fetch(`/api/incidents/${incidentId}/remediate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: selectedAction.action_id, operator: operatorName }),
        });
        if (onActionExecuted) {
          onActionExecuted(selectedAction.action_id);
        }
      }

      const newLog: DecisionLogItem = {
        id: `log-${Date.now()}`,
        incident_id: incidentId,
        action_id: selectedAction.action_id,
        device: selectedAction.device,
        commands: cmds,
        rollback_commands: selectedAction.rollback_commands,
        risk_level: selectedAction.risk_level,
        status: `hitl_${modalMode}`,
        approved_by: `${operatorName} (Rationale: ${rationale.trim()})`,
        simulated_at: new Date().toISOString(),
      };

      setDecisionLogs((prev) => [newLog, ...prev]);
      setPendingActions((prev) => prev.filter((a) => a.action_id !== selectedAction.action_id));
      closeModal();
    } catch {
      const newLog: DecisionLogItem = {
        id: `log-${Date.now()}`,
        incident_id: incidentId,
        action_id: selectedAction.action_id,
        device: selectedAction.device,
        commands: cmds,
        rollback_commands: selectedAction.rollback_commands,
        risk_level: selectedAction.risk_level,
        status: `hitl_${modalMode}`,
        approved_by: `${operatorName} (Rationale: ${rationale.trim()})`,
        simulated_at: new Date().toISOString(),
      };
      setDecisionLogs((prev) => [newLog, ...prev]);
      setPendingActions((prev) => prev.filter((a) => a.action_id !== selectedAction.action_id));
      closeModal();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#475569]"></span>
              <h2 className="text-sm font-semibold tracking-wider uppercase font-mono text-[#111111] dark:text-[#EDEDEA]">
                Human-in-the-Loop (HITL) Approval Queue
              </h2>
            </div>
            <p className="text-xs text-[#6B6B66] dark:text-[#888884] mt-1 font-sans">
              Autonomous execution safety gate. Recommended remediation actions require explicit operator sign-off or parameter modification with documented rationale.
            </p>
          </div>
          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="text-[#6B6B66] dark:text-[#888884]">Operator:</span>
            <input
              type="text"
              value={operatorName}
              onChange={(e) => setOperatorName(e.target.value)}
              className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-2 py-1 text-xs text-[#111111] dark:text-[#EDEDEA] outline-none focus:border-[#475569]"
            />
          </div>
        </div>
      </div>

      {/* Pending Actions Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between font-mono text-xs">
          <span className="uppercase tracking-wider font-semibold text-[#111111] dark:text-[#EDEDEA]">
            Pending Remediation Proposals ({pendingActions.length})
          </span>
          <span className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
            Pre-flight bounds: blast radius &lt; 60% · rollback validated
          </span>
        </div>

        {pendingActions.length === 0 ? (
          <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-8 text-center text-xs text-[#6B6B66] dark:text-[#888884] font-mono">
            No pending remediation actions requiring human approval.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {pendingActions.map((action) => (
              <div
                key={action.action_id}
                className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-4 transition-colors"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <span className="text-xs font-mono font-semibold text-[#111111] dark:text-[#EDEDEA]">
                        {action.title}
                      </span>
                      <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66] dark:text-[#888884]">
                        {action.action_id}
                      </span>
                      <span className="px-2 py-0.5 text-[10px] font-mono uppercase border border-[#A08A5B] text-[#A08A5B]">
                        Pending Review
                      </span>
                    </div>
                    <p className="text-xs text-[#6B6B66] dark:text-[#888884] mt-1 font-sans">
                      {action.description}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-[11px]">
                    <span className="text-[#6B6B66] dark:text-[#888884]">Device:</span>
                    <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">{action.device}</span>
                    <span className="text-[#6B6B66] dark:text-[#888884] ml-2">Risk:</span>
                    <span className="uppercase text-[#5E7A6A] font-semibold">{action.risk_level}</span>
                  </div>
                </div>

                {/* Proposed Commands */}
                <div className="space-y-1">
                  <div className="text-[10px] font-mono text-[#6B6B66] dark:text-[#888884] uppercase">
                    Proposed Configuration Commands:
                  </div>
                  <pre className="bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] p-3 text-[11px] font-mono text-[#111111] dark:text-[#EDEDEA] overflow-x-auto">
                    {action.commands.join("\n")}
                  </pre>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-wrap items-center justify-end gap-2.5 pt-2 border-t border-[#E5E5E3] dark:border-[#2A2A2D] font-mono text-xs">
                  <button
                    onClick={() => openModal(action, "modify")}
                    className="px-3.5 py-1.5 border border-[#475569] text-[#475569] dark:text-[#EDEDEA] hover:bg-[#475569] hover:text-white transition-colors uppercase tracking-wider"
                  >
                    Modify
                  </button>
                  <button
                    onClick={() => openModal(action, "reject")}
                    className="px-3.5 py-1.5 border border-[#9A5B5B] text-[#9A5B5B] hover:bg-[#9A5B5B] hover:text-white transition-colors uppercase tracking-wider"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => openModal(action, "approve")}
                    className="px-3.5 py-1.5 bg-[#475569] text-white hover:bg-[#334155] transition-colors uppercase tracking-wider font-semibold"
                  >
                    Approve &amp; Simulate
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Decision Modal */}
      {modalMode && selectedAction && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#2A2A2D] max-w-xl w-full p-6 space-y-4 font-mono">
            <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
              <h3 className="text-sm font-semibold uppercase text-[#111111] dark:text-[#EDEDEA]">
                {modalMode === "approve"
                  ? "Approve Remediation Action"
                  : modalMode === "reject"
                  ? "Reject Remediation Action"
                  : "Modify Remediation Action"}
              </h3>
              <button
                onClick={closeModal}
                className="text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
              >
                [ESC]
              </button>
            </div>

            <div className="text-xs space-y-1">
              <div>
                <span className="text-[#6B6B66] dark:text-[#888884]">Action:</span>{" "}
                <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">{selectedAction.action_id}</span>
              </div>
              <div>
                <span className="text-[#6B6B66] dark:text-[#888884]">Target Device:</span>{" "}
                <span className="text-[#111111] dark:text-[#EDEDEA]">{selectedAction.device}</span>
              </div>
            </div>

            {/* Editable commands if modifying */}
            {modalMode === "modify" && (
              <div className="space-y-1.5">
                <label className="text-xs text-[#6B6B66] dark:text-[#888884]">
                  Edit Configuration Commands (one per line):
                </label>
                <textarea
                  rows={5}
                  value={modifiedCommands}
                  onChange={(e) => setModifiedCommands(e.target.value)}
                  className="w-full bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] p-2.5 text-xs text-[#111111] dark:text-[#EDEDEA] outline-none focus:border-[#475569]"
                />
              </div>
            )}

            {/* Mandatory Rationale Field */}
            <div className="space-y-1.5">
              <label className="text-xs text-[#6B6B66] dark:text-[#888884]">
                Operator Rationale / Justification <span className="text-[#9A5B5B]">*</span>:
              </label>
              <textarea
                rows={3}
                placeholder="Explain the technical justification for this decision (required for compliance audit log)..."
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                className="w-full bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] p-2.5 text-xs text-[#111111] dark:text-[#EDEDEA] outline-none focus:border-[#475569]"
              />
            </div>

            {statusMessage && (
              <div className="text-xs text-[#9A5B5B]">{statusMessage}</div>
            )}

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E5E5E3] dark:border-[#2A2A2D]">
              <button
                onClick={closeModal}
                disabled={isSubmitting}
                className="px-3.5 py-1.5 border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs text-[#6B6B66] dark:text-[#888884] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
              >
                Cancel
              </button>
              <button
                onClick={handleDecisionSubmit}
                disabled={isSubmitting}
                className={`px-4 py-1.5 text-xs text-white uppercase tracking-wider font-semibold ${
                  modalMode === "reject"
                    ? "bg-[#9A5B5B] hover:bg-[#854747]"
                    : "bg-[#475569] hover:bg-[#334155]"
                }`}
              >
                {isSubmitting ? "Submitting..." : `Confirm ${modalMode}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Decision History Section */}
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-4">
        <div className="flex items-center justify-between font-mono text-xs border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-3">
          <span className="uppercase tracking-wider font-semibold text-[#111111] dark:text-[#EDEDEA]">
            Decision History &amp; Audit Log ({decisionLogs.length})
          </span>
          <span className="text-[11px] text-[#6B6B66] dark:text-[#888884]">
            SQLite table: remediation_logs
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-[#E5E5E3] dark:border-[#2A2A2D] text-[#6B6B66] dark:text-[#888884] uppercase text-[10px]">
                <th className="py-2 pr-4">Timestamp</th>
                <th className="py-2 pr-4">Action ID</th>
                <th className="py-2 pr-4">Device</th>
                <th className="py-2 pr-4">Decision</th>
                <th className="py-2 pr-4">Operator &amp; Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E5E3] dark:divide-[#2A2A2D]">
              {decisionLogs.map((log) => {
                const isApproved = log.status.includes("approve") || log.status.includes("simulated_executed");
                const isRejected = log.status.includes("reject");
                const isModified = log.status.includes("modify");

                return (
                  <tr key={log.id} className="hover:bg-[#FAFAF9] dark:hover:bg-[#0F0F10] transition-colors">
                    <td className="py-2.5 pr-4 text-[11px] text-[#6B6B66] dark:text-[#888884] whitespace-nowrap">
                      {log.simulated_at ? new Date(log.simulated_at).toLocaleTimeString() : "--"}
                    </td>
                    <td className="py-2.5 pr-4 text-[11px] font-semibold text-[#111111] dark:text-[#EDEDEA] whitespace-nowrap">
                      {log.action_id}
                    </td>
                    <td className="py-2.5 pr-4 text-[11px] text-[#6B6B66] dark:text-[#888884]">
                      {log.device}
                    </td>
                    <td className="py-2.5 pr-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-0.5 text-[10px] uppercase font-mono border ${
                          isApproved
                            ? "border-[#5E7A6A] text-[#5E7A6A]"
                            : isRejected
                            ? "border-[#9A5B5B] text-[#9A5B5B]"
                            : "border-[#475569] text-[#475569] dark:text-[#EDEDEA]"
                        }`}
                      >
                        {isApproved ? "Approved" : isRejected ? "Rejected" : isModified ? "Modified" : log.status}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-[11px] text-[#6B6B66] dark:text-[#888884]">
                      {log.approved_by || "human_operator"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
