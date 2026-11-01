import React from "react";
import { ScenarioMeta } from "../types/protocol";
import { DataQualityBanner, TypedValidationErrorItem } from "./DataQualityBanner";

interface ScenarioPickerProps {
  scenarios: ScenarioMeta[];
  selectedScenario: string;
  onSelectScenario: (scenarioFilename: string) => void;
  onRunDiagnosis: () => void;
  loading: boolean;
  qualityScore: number;
  detectedFormat: string;
  validationErrors: TypedValidationErrorItem[];
  transformationsCount: number;
  isValidated?: boolean;
  recordsCount?: number;
  onRunValidation?: () => void;
  validating?: boolean;
  lastRunId?: string | null;
  lastRunTimestamp?: string | null;
  previousRunId?: string | null;
  onCompareRuns?: () => void;
  executionStatus?: "idle" | "running" | "completed" | "failed";
  errorMessage?: string | null;
}

export const ScenarioPicker: React.FC<ScenarioPickerProps> = ({
  scenarios,
  selectedScenario,
  onSelectScenario,
  onRunDiagnosis,
  loading,
  qualityScore,
  detectedFormat,
  validationErrors,
  transformationsCount,
  isValidated = true,
  recordsCount,
  onRunValidation,
  validating = false,
  lastRunId,
  lastRunTimestamp,
  previousRunId,
  onCompareRuns,
  executionStatus = "idle",
  errorMessage,
}) => {
  const standardScenarios = scenarios.filter((s) => !s.filename.includes("organizer"));
  const organizerScenarios = scenarios.filter((s) => s.filename.includes("organizer"));
  const currentScenario = scenarios.find((s) => s.filename === selectedScenario);

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-5 space-y-4 font-sans">
      {/* Top Selector & Primary Actions */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#94A3B8]">
              Target Network Diagnostic Scenario / Dataset
            </label>
            {/* Execution status indicator */}
            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 border text-xs font-semibold ${
                  executionStatus === "running"
                    ? "border-[#133E87] bg-[#EEF4FB] text-[#133E87] animate-pulse"
                    : executionStatus === "completed"
                    ? "border-[#15803D] bg-[#F0FDF4] text-[#15803D]"
                    : executionStatus === "failed"
                    ? "border-[#DC2626] bg-[#FEF2F2] text-[#DC2626]"
                    : "border-[#E2E8F0] bg-[#F8FAFC] text-[#475569]"
                }`}
              >
                {executionStatus === "running"
                  ? "Diagnosis Running..."
                  : executionStatus === "completed"
                  ? "Diagnosis Completed"
                  : executionStatus === "failed"
                  ? "Diagnosis Failed"
                  : "Ready to Diagnose"}
              </span>
            </div>
          </div>

          <div className="relative">
            <select
              value={selectedScenario}
              onChange={(e) => onSelectScenario(e.target.value)}
              className="w-full bg-[#F8FAFC] dark:bg-[#0F0F10] border border-[#E2E8F0] dark:border-[#2A2A2D] text-[#0F172A] dark:text-[#EDEDEA] px-3.5 py-2.5 text-sm font-sans outline-none focus:border-[#133E87] transition-colors"
            >
              <optgroup label="Multi-Domain Campus Scenarios (IIT Bhubaneswar)">
                {standardScenarios.map((s) => (
                  <option key={s.filename} value={s.filename}>
                    {s.filename.replace(".json", "")} {s.description ? `— ${s.description}` : ""}
                  </option>
                ))}
              </optgroup>

              <optgroup label="Organizer Challenge Samples (JSONL Telemetry)">
                {organizerScenarios.map((s) => (
                  <option key={s.filename} value={s.filename}>
                    {s.description || s.filename.replace(".jsonl", "")}
                  </option>
                ))}
              </optgroup>
            </select>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5 self-end lg:self-center pt-2 lg:pt-5">
          {previousRunId && onCompareRuns && (
            <button
              onClick={onCompareRuns}
              disabled={loading}
              className="px-4 py-2.5 text-xs font-semibold border border-[#133E87] text-[#133E87] dark:text-[#3A86FF] hover:bg-[#EEF4FB] transition-colors"
              title="Compare current findings with previous diagnostic execution"
            >
              Compare with Previous Run
            </button>
          )}

          <button
            onClick={onRunDiagnosis}
            disabled={loading || !selectedScenario}
            className="px-6 py-2.5 bg-[#0B2545] hover:bg-[#133E87] text-white text-sm font-bold tracking-wide transition-all shadow-sm disabled:opacity-50"
          >
            {loading ? "Executing Agents..." : "Run Network Diagnosis"}
          </button>
        </div>
      </div>

      {/* Active Run Provenance Information */}
      {lastRunId && (
        <div className="p-3 bg-[#EEF4FB] dark:bg-[#0B132B] border border-[#133E87]/20 flex flex-wrap items-center justify-between text-xs text-[#0B2545] dark:text-[#94A3B8]">
          <div className="flex items-center gap-2">
            <span className="font-semibold uppercase text-[11px]">Active Execution ID:</span>
            <span className="font-mono font-bold">{lastRunId}</span>
          </div>
          {lastRunTimestamp && (
            <div className="flex items-center gap-2">
              <span className="font-semibold uppercase text-[11px]">Timestamp (UTC):</span>
              <span className="font-mono">{new Date(lastRunTimestamp).toUTCString()}</span>
            </div>
          )}
        </div>
      )}

      {errorMessage && (
        <div className="p-3 bg-[#FEF2F2] border border-[#DC2626]/30 text-[#DC2626] text-xs">
          <strong>Execution Error:</strong> {errorMessage}
        </div>
      )}

      {/* Input Quality Audit & Validation */}
      <DataQualityBanner
        score={qualityScore}
        detectedFormat={detectedFormat}
        validationErrors={validationErrors}
        transformationsCount={transformationsCount}
        isValidated={isValidated}
        recordsCount={recordsCount}
        onRunValidation={onRunValidation}
        validating={validating}
      />

      <div className="text-xs text-[#475569] dark:text-[#888884]">
        {currentScenario?.description || "Select a network scenario to execute autonomous multi-agent diagnostic consensus."}
      </div>
    </div>
  );
};
