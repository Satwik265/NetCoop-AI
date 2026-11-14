import { apiFetch } from '../auth/AuthContext';
import React, { useState, useEffect } from "react";
import { RemediationAction } from "../types/protocol";
import { formatDateTime, SupportedTimezone } from "../utils/i18n";

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
  timezone?: SupportedTimezone;
}

export const HitlApprovalQueue: React.FC<HitlApprovalQueueProps> = ({
  incidentId,
  actions,
  onActionExecuted,
  timezone = "UTC",
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initialize pending actions strictly from props without inventing fake actions
  useEffect(() => {
    if (actions && actions.length > 0) {
      setPendingActions(actions);
    } else {
      setPendingActions([]);
    }
  }, [actions]);

  // Fetch decision logs on load
  const fetchLogs = async () => {
    try {
      const res = await apiFetch(`/api/remediation/logs?incident_id=${incidentId}`);
      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data)) {
          setDecisionLogs(data);
          return;
        }
      }
    } catch {
      // Backend offline or endpoint unmounted
    }
    setDecisionLogs([]);
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
    setErrorMessage(null);
  };

  const closeModal = () => {
    setSelectedAction(null);
    setModalMode(null);
    setRationale("");
    setErrorMessage(null);
    setStatusMessage(null);
  };

  const handleDecisionSubmit = async () => {
    if (!selectedAction || !modalMode) return;
    if (!rationale.trim()) {
      setErrorMessage("Operator rationale is mandatory for audit logging compliance.");
      return;
    }

    setIsSubmitting(true);
    setStatusMessage(null);
    setErrorMessage(null);

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
      const decRes = await apiFetch(`/api/incidents/${incidentId}/hitl-decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!decRes.ok) {
        const err = await decRes.json().catch(() => ({ detail: "Decision submission rejected by server." }));
        setErrorMessage(`Decision submission failed (HTTP ${decRes.status}): ${err.detail || "Server rejected approval request"}`);
        setIsSubmitting(false);
        return;
      }

      if (modalMode === "approve") {
        const remRes = await apiFetch(`/api/incidents/${incidentId}/remediate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: selectedAction.action_id, operator: operatorName }),
        });
        if (!remRes.ok) {
          const err = await remRes.json().catch(() => ({ detail: "Remediation execution failed." }));
          setErrorMessage(`Remediation simulation execution failed (HTTP ${remRes.status}): ${err.detail || "Sandbox error"}`);
          setIsSubmitting(false);
          return;
        }
        if (onActionExecuted) {
          onActionExecuted(selectedAction.action_id);
        }
      }

      // Success: Record into local audit trail
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
    } catch (e: any) {
      setErrorMessage(`Network error communicating with remediation service: ${e?.message || "Unknown error"}`);
    } finally {
      setIsSubmitting(false);
    }
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
          All approved actions execute exclusively in the sandbox simulation harness. Real network devices are never touched.
        </p>
      </div>

      {/* Header Banner */}
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#0B2545] dark:bg-[#3A86FF]"></span>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
                Human-in-the-Loop (HITL) Safety Gate &amp; Approval Queue
              </h2>
            </div>
            <p className="text-xs text-[#475569] dark:text-[#94A3B8] mt-1">
              Autonomous remediation recommendations require explicit operator authorization, command parameter review, or documented rejection.
            </p>
          </div>
          <div className="flex items-center gap-2 font-mono text-xs">
            <label htmlFor="operator-input" className="text-[#475569] dark:text-[#94A3B8] font-bold">
              Operator Sign-off ID:
            </label>
            <input
              id="operator-input"
              type="text"
              value={operatorName}
              onChange={(e) => setOperatorName(e.target.value)}
              className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] px-3 py-1.5 text-xs text-[#0F172A] dark:text-[#F1F5F9] outline-none min-h-[32px] focus-visible:ring-2 focus-visible:ring-[#133E87]"
            />
          </div>
        </div>
      </div>

      {/* Pending Actions Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs font-sans">
          <span className="uppercase tracking-wider font-bold text-[#0B2545] dark:text-[#F1F5F9]">
            Pending Remediation Proposals ({pendingActions.length})
          </span>
          <span className="text-[11px] text-[#475569] dark:text-[#94A3B8] font-mono">
            Safety Invariant: Blast Radius &lt; 60% &middot; Rollback Pre-Validated
          </span>
        </div>

        {pendingActions.length === 0 ? (
          <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-dashed border-[#CBD5E1] dark:border-[#2A2A2D] p-10 text-center text-xs text-[#475569] dark:text-[#94A3B8]">
            Zero pending remediation actions awaiting operator approval for incident <code>{incidentId}</code>.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {pendingActions.map((action) => (
              <div
                key={action.action_id}
                className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-4 transition-colors"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="text-xs font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                        {action.title}
                      </span>
                      <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-[#475569] dark:text-[#94A3B8]">
                        {action.action_id}
                      </span>
                      <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase border border-[#B45309]/40 bg-[#FFFBEB] text-[#B45309] dark:bg-[#78350F]/30 dark:text-[#FDE68A]">
                        Pending Operator Authorization
                      </span>
                    </div>
                    <p className="text-xs text-[#475569] dark:text-[#94A3B8] mt-1.5 leading-relaxed">
                      {action.description}
                    </p>
                  </div>

                  <div className="flex items-center gap-3 font-mono text-xs">
                    <span className="text-[#475569] dark:text-[#94A3B8]">Target Device:</span>
                    <span className="font-bold text-[#0F172A] dark:text-[#F1F5F9]">{action.device}</span>
                    <span className="text-[#475569] dark:text-[#94A3B8] ml-2">Risk Level:</span>
                    <span className={`uppercase font-bold ${action.risk_level === "high" ? "text-[#DC2626]" : action.risk_level === "medium" ? "text-[#B45309]" : "text-[#15803D]"}`}>
                      {action.risk_level}
                    </span>
                  </div>
                </div>

                {/* Proposed Commands */}
                <div className="space-y-1">
                  <div className="text-[10px] font-mono text-[#475569] dark:text-[#94A3B8] uppercase font-bold">
                    Proposed Configuration Commands (Sandbox):
                  </div>
                  <pre className="bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] p-3 text-xs font-mono text-[#0F172A] dark:text-[#F1F5F9] overflow-x-auto">
                    {action.commands.join("\n")}
                  </pre>
                </div>

                {/* Action Buttons: Accessible minimum target size >= 36px */}
                <div className="flex flex-wrap items-center justify-end gap-3 pt-3 border-t border-[#E2E8F0] dark:border-[#2A2A2D]">
                  <button
                    onClick={() => openModal(action, "modify")}
                    className="px-4 py-2 border border-[#0B2545] dark:border-[#3A86FF] text-[#0B2545] dark:text-[#F1F5F9] hover:bg-[#EEF4FB] dark:hover:bg-[#1E293B] transition-colors uppercase text-xs font-bold min-h-[36px] focus-visible:ring-2"
                  >
                    Modify Parameters
                  </button>
                  <button
                    onClick={() => openModal(action, "reject")}
                    className="px-4 py-2 border border-[#DC2626] text-[#DC2626] hover:bg-[#FEF2F2] dark:hover:bg-[#7F1D1D]/30 transition-colors uppercase text-xs font-bold min-h-[36px] focus-visible:ring-2"
                  >
                    Reject Proposal
                  </button>
                  <button
                    onClick={() => openModal(action, "approve")}
                    className="px-4 py-2 bg-[#0B2545] text-white hover:bg-[#133E87] dark:bg-[#133E87] dark:hover:bg-[#3A86FF] transition-colors uppercase text-xs font-bold min-h-[36px] focus-visible:ring-2"
                  >
                    Authorize &amp; Simulate
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Decision Modal */}
      {modalMode && selectedAction && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 font-sans"
        >
          <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#CBD5E1] dark:border-[#2A2A2D] max-w-xl w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-3">
              <h3 id="modal-title" className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#F1F5F9]">
                {modalMode === "approve"
                  ? "Authorize Remediation Proposal (Sandbox Execution)"
                  : modalMode === "reject"
                  ? "Reject Remediation Proposal"
                  : "Modify Configuration Parameters"}
              </h3>
              <button
                onClick={closeModal}
                className="text-[#475569] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-[#F1F5F9] font-mono text-xs p-1"
                aria-label="Close dialog"
              >
                [✕]
              </button>
            </div>

            <div className="text-xs space-y-1 font-mono">
              <div>
                <span className="text-[#475569] dark:text-[#94A3B8]">Action ID:</span>{" "}
                <strong className="text-[#0F172A] dark:text-[#F1F5F9]">{selectedAction.action_id}</strong>
              </div>
              <div>
                <span className="text-[#475569] dark:text-[#94A3B8]">Target Device:</span>{" "}
                <span className="text-[#0F172A] dark:text-[#F1F5F9] font-bold">{selectedAction.device}</span>
              </div>
            </div>

            {/* Editable commands if modifying */}
            {modalMode === "modify" && (
              <div className="space-y-1.5 font-mono">
                <label htmlFor="commands-edit" className="text-xs font-bold text-[#475569] dark:text-[#94A3B8]">
                  Edit Configuration Commands (one per line):
                </label>
                <textarea
                  id="commands-edit"
                  rows={5}
                  value={modifiedCommands}
                  onChange={(e) => setModifiedCommands(e.target.value)}
                  className="w-full bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] p-3 text-xs text-[#0F172A] dark:text-[#F1F5F9] outline-none focus-visible:ring-2"
                />
              </div>
            )}

            {/* Mandatory Rationale Field */}
            <div className="space-y-1.5">
              <label htmlFor="rationale-input" className="text-xs font-bold text-[#0F172A] dark:text-[#F1F5F9]">
                Operator Rationale / Justification <span className="text-[#DC2626]">*</span>:
              </label>
              <textarea
                id="rationale-input"
                rows={3}
                placeholder="Document technical reasoning (required for ISO 9241 and compliance audit logging)..."
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                className="w-full bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#CBD5E1] dark:border-[#2A2A2D] p-3 text-xs text-[#0F172A] dark:text-[#F1F5F9] outline-none focus-visible:ring-2"
              />
            </div>

            {errorMessage && (
              <div className="p-3 bg-[#FEF2F2] border border-[#DC2626]/40 text-[#DC2626] text-xs font-bold" role="alert">
                {errorMessage}
              </div>
            )}

            {statusMessage && (
              <div className="p-3 bg-[#F0FDF4] border border-[#15803D]/40 text-[#15803D] text-xs font-bold">
                {statusMessage}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E2E8F0] dark:border-[#2A2A2D]">
              <button
                onClick={closeModal}
                disabled={isSubmitting}
                className="px-4 py-2 border border-[#CBD5E1] dark:border-[#2A2A2D] text-xs font-semibold text-[#475569] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-[#F1F5F9] min-h-[36px]"
              >
                Cancel
              </button>
              <button
                onClick={handleDecisionSubmit}
                disabled={isSubmitting}
                className={`px-5 py-2 text-xs text-white uppercase tracking-wider font-bold min-h-[36px] transition-colors focus-visible:ring-2 ${
                  modalMode === "reject"
                    ? "bg-[#DC2626] hover:bg-[#B91C1C]"
                    : "bg-[#0B2545] hover:bg-[#133E87] dark:bg-[#133E87] dark:hover:bg-[#3A86FF]"
                }`}
              >
                {isSubmitting ? "Submitting to Backend..." : `Confirm ${modalMode}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Decision History Section */}
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-4">
        <div className="flex items-center justify-between font-sans text-xs border-b border-[#E2E8F0] dark:border-[#2A2A2D] pb-3">
          <span className="uppercase tracking-wider font-bold text-[#0B2545] dark:text-[#F1F5F9]">
            Operator Decision History &amp; Audit Trail ({decisionLogs.length})
          </span>
          <span className="text-[11px] text-[#475569] dark:text-[#94A3B8] font-mono">
            SQLite Audit Ledger: remediation_logs
          </span>
        </div>

        {decisionLogs.length === 0 ? (
          <div className="text-xs text-[#475569] dark:text-[#94A3B8] py-4 text-center font-mono">
            Zero recorded operator decisions for this incident.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-sans text-xs border-collapse" aria-label="Remediation Decision History Table">
              <thead>
                <tr className="border-b border-[#CBD5E1] dark:border-[#2A2A2D] bg-[#F1F5F9] dark:bg-[#0F0F10] text-[#475569] dark:text-[#94A3B8] uppercase text-[10px] tracking-wider">
                  <th scope="col" className="p-3 font-bold">Timestamp</th>
                  <th scope="col" className="p-3 font-bold">Action ID</th>
                  <th scope="col" className="p-3 font-bold">Target Device</th>
                  <th scope="col" className="p-3 font-bold">Decision Status</th>
                  <th scope="col" className="p-3 font-bold">Operator &amp; Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
                {decisionLogs.map((log) => {
                  const isApproved = log.status.includes("approve") || log.status.includes("simulated_executed");
                  const isRejected = log.status.includes("reject");
                  const isModified = log.status.includes("modify");

                  return (
                    <tr key={log.id} className="hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F10] transition-colors">
                      <td className="p-3 font-mono text-[11px] text-[#475569] dark:text-[#94A3B8] whitespace-nowrap">
                        {formatDateTime(log.simulated_at, timezone)}
                      </td>
                      <td className="p-3 font-mono font-bold text-[#0F172A] dark:text-[#F1F5F9] whitespace-nowrap">
                        {log.action_id}
                      </td>
                      <td className="p-3 font-mono text-[#0F172A] dark:text-[#F1F5F9]">
                        {log.device}
                      </td>
                      <td className="p-3 whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 text-[10px] uppercase font-mono font-bold border ${
                            isApproved
                              ? "border-[#15803D]/40 bg-[#F0FDF4] text-[#15803D] dark:bg-[#14532D]/30 dark:text-[#86EFAC]"
                              : isRejected
                              ? "border-[#DC2626]/40 bg-[#FEF2F2] text-[#DC2626] dark:bg-[#7F1D1D]/30 dark:text-[#FCA5A5]"
                              : "border-[#133E87]/40 bg-[#EEF4FB] text-[#133E87] dark:bg-[#1E3A8A]/30 dark:text-[#93C5FD]"
                          }`}
                        >
                          {isApproved ? "Approved" : isRejected ? "Rejected" : isModified ? "Modified" : log.status}
                        </span>
                      </td>
                      <td className="p-3 text-[11px] text-[#475569] dark:text-[#94A3B8]">
                        {log.approved_by || "human_operator"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
