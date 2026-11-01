import React from "react";

export interface RunComparisonData {
  current_run_id: string;
  previous_run_id: string;
  scenario_filename: string;
  probable_cause: {
    current: string;
    previous: string;
    changed: boolean;
  };
  confidence: {
    current: number;
    previous: number;
    delta: number;
    status: "increased" | "decreased" | "unchanged";
  };
  uncertainty: {
    current: number;
    previous: number;
    delta: number;
    status: "increased" | "decreased" | "unchanged";
  };
  affected_devices: {
    current: string[];
    previous: string[];
    added: string[];
    removed: string[];
    unchanged: string[];
    changed: boolean;
  };
  conformal_prediction_set: {
    current: string[];
    previous: string[];
    changed: boolean;
  };
  classification_probabilities: Record<
    string,
    {
      current: number;
      previous: number;
      delta: number;
      status: "increased" | "decreased" | "unchanged";
    }
  >;
  remediation_actions: {
    current: string[];
    previous: string[];
    changed: boolean;
  };
}

interface CompareRunsModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: RunComparisonData | null;
  loading: boolean;
}

export const CompareRunsModal: React.FC<CompareRunsModalProps> = ({
  isOpen,
  onClose,
  data,
  loading,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 font-sans">
      <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#E2E8F0] dark:border-[#2A2A2D] flex items-center justify-between bg-[#F8FAFC] dark:bg-[#0F0F10]">
          <div>
            <h2 className="text-lg font-bold text-[#0B2545] dark:text-[#F1F5F9]">
              Diagnostic Run-to-Run Comparison
            </h2>
            <div className="text-xs text-[#475569] dark:text-[#94A3B8]">
              Scenario: <span className="font-mono font-semibold">{data?.scenario_filename}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-xs font-semibold px-3 py-1 border border-[#E2E8F0] hover:bg-[#E2E8F0] text-[#0F172A] dark:text-[#F1F5F9] transition-colors"
          >
            Close
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-sm flex-1">
          {loading ? (
            <div className="p-8 text-center text-[#475569]">
              Loading comparison data between runs...
            </div>
          ) : !data ? (
            <div className="p-8 text-center text-[#DC2626]">
              Unable to load comparison data. Ensure both runs exist.
            </div>
          ) : (
            <div className="space-y-6">
              {/* Execution IDs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
                <div className="p-3 bg-[#EEF4FB] border border-[#133E87]/20">
                  <span className="text-[11px] text-[#133E87] uppercase font-bold block mb-1">
                    Current Execution
                  </span>
                  <div className="font-bold text-[#0B2545]">{data.current_run_id}</div>
                </div>
                <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0]">
                  <span className="text-[11px] text-[#475569] uppercase font-bold block mb-1">
                    Previous Execution
                  </span>
                  <div className="font-bold text-[#475569]">{data.previous_run_id}</div>
                </div>
              </div>

              {/* Core Findings Comparison Table */}
              <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F8FAFC] dark:bg-[#0F0F10] border-b border-[#E2E8F0] dark:border-[#2A2A2D] text-[#475569] uppercase text-[11px] font-bold">
                    <tr>
                      <th className="p-3">Diagnostic Metric</th>
                      <th className="p-3">Current Run</th>
                      <th className="p-3">Previous Run</th>
                      <th className="p-3">Observed Shift</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
                    {/* Probable Cause */}
                    <tr>
                      <td className="p-3 font-semibold text-[#0F172A] dark:text-[#EDEDEA]">
                        Probable Root Cause
                      </td>
                      <td className="p-3 font-mono font-bold text-[#0B2545] dark:text-[#3A86FF]">
                        {data.probable_cause.current}
                      </td>
                      <td className="p-3 font-mono text-[#475569]">
                        {data.probable_cause.previous}
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 border text-xs font-semibold ${
                            data.probable_cause.changed
                              ? "text-[#DC2626] border-[#DC2626]/30 bg-[#FEF2F2]"
                              : "text-[#15803D] border-[#15803D]/30 bg-[#F0FDF4]"
                          }`}
                        >
                          {data.probable_cause.changed ? "Changed" : "Unchanged"}
                        </span>
                      </td>
                    </tr>

                    {/* Confidence */}
                    <tr>
                      <td className="p-3 font-semibold text-[#0F172A] dark:text-[#EDEDEA]">
                        Confidence Score
                      </td>
                      <td className="p-3 font-mono font-bold">
                        {(data.confidence.current * 100).toFixed(1)}%
                      </td>
                      <td className="p-3 font-mono text-[#475569]">
                        {(data.confidence.previous * 100).toFixed(1)}%
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 border text-xs font-semibold ${
                            data.confidence.status === "increased"
                              ? "text-[#15803D] border-[#15803D]/30 bg-[#F0FDF4]"
                              : data.confidence.status === "decreased"
                              ? "text-[#DC2626] border-[#DC2626]/30 bg-[#FEF2F2]"
                              : "text-[#475569] border-[#E2E8F0] bg-[#F8FAFC]"
                          }`}
                        >
                          {data.confidence.status.toUpperCase()} (
                          {data.confidence.delta >= 0 ? "+" : ""}
                          {(data.confidence.delta * 100).toFixed(1)}%)
                        </span>
                      </td>
                    </tr>

                    {/* Uncertainty Score */}
                    <tr>
                      <td className="p-3 font-semibold text-[#0F172A] dark:text-[#EDEDEA]">
                        Epistemic Uncertainty
                      </td>
                      <td className="p-3 font-mono font-bold">
                        {(data.uncertainty.current * 100).toFixed(1)}%
                      </td>
                      <td className="p-3 font-mono text-[#475569]">
                        {(data.uncertainty.previous * 100).toFixed(1)}%
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 border text-xs font-semibold ${
                            data.uncertainty.status === "decreased"
                              ? "text-[#15803D] border-[#15803D]/30 bg-[#F0FDF4]"
                              : data.uncertainty.status === "increased"
                              ? "text-[#DC2626] border-[#DC2626]/30 bg-[#FEF2F2]"
                              : "text-[#475569] border-[#E2E8F0] bg-[#F8FAFC]"
                          }`}
                        >
                          {data.uncertainty.status.toUpperCase()} (
                          {data.uncertainty.delta >= 0 ? "+" : ""}
                          {(data.uncertainty.delta * 100).toFixed(1)}%)
                        </span>
                      </td>
                    </tr>

                    {/* Affected Devices */}
                    <tr>
                      <td className="p-3 font-semibold text-[#0F172A] dark:text-[#EDEDEA]">
                        Affected Devices
                      </td>
                      <td className="p-3 font-mono text-xs">
                        {data.affected_devices.current.join(", ") || "None"}
                      </td>
                      <td className="p-3 font-mono text-xs text-[#475569]">
                        {data.affected_devices.previous.join(", ") || "None"}
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 border text-xs font-semibold ${
                            data.affected_devices.changed
                              ? "text-[#B45309] border-[#B45309]/30 bg-[#FFFBEB]"
                              : "text-[#15803D] border-[#15803D]/30 bg-[#F0FDF4]"
                          }`}
                        >
                          {data.affected_devices.changed ? "Changed" : "Unchanged"}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Classification Probabilities Breakdown */}
              {Object.keys(data.classification_probabilities).length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#94A3B8]">
                    Learned Classifier Probability Distribution Shift
                  </h3>
                  <div className="border border-[#E2E8F0] dark:border-[#2A2A2D] overflow-hidden">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-[#F8FAFC] dark:bg-[#0F0F10] border-b border-[#E2E8F0] dark:border-[#2A2A2D] text-[#475569] text-[11px] font-sans font-bold uppercase">
                        <tr>
                          <th className="p-2.5">Fault Hypothesis Class</th>
                          <th className="p-2.5">Current Probability</th>
                          <th className="p-2.5">Previous Probability</th>
                          <th className="p-2.5">Shift Delta</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#2A2A2D]">
                        {Object.entries(data.classification_probabilities).map(
                          ([clsName, pData]) => (
                            <tr key={clsName}>
                              <td className="p-2.5 font-bold">{clsName}</td>
                              <td className="p-2.5">{(pData.current * 100).toFixed(1)}%</td>
                              <td className="p-2.5 text-[#475569]">
                                {(pData.previous * 100).toFixed(1)}%
                              </td>
                              <td className="p-2.5 font-sans">
                                <span
                                  className={`px-1.5 py-0.5 border text-[11px] font-semibold ${
                                    pData.status === "increased"
                                      ? "text-[#15803D] border-[#15803D]/30 bg-[#F0FDF4]"
                                      : pData.status === "decreased"
                                      ? "text-[#DC2626] border-[#DC2626]/30 bg-[#FEF2F2]"
                                      : "text-[#475569] border-[#E2E8F0] bg-[#F8FAFC]"
                                  }`}
                                >
                                  {pData.status.toUpperCase()} ({pData.delta >= 0 ? "+" : ""}
                                  {(pData.delta * 100).toFixed(1)}%)
                                </span>
                              </td>
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

