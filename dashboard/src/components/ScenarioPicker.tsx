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
  isChaosActive: boolean;
  onToggleChaos: () => void;
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
  isChaosActive,
  onToggleChaos,
}) => {
  // Separate standard benchmark scenarios and organizer samples
  const standardScenarios = scenarios.filter((s) => !s.filename.includes("organizer"));
  const organizerScenarios = scenarios.filter((s) => s.filename.includes("organizer"));

  const currentScenario = scenarios.find((s) => s.filename === selectedScenario);

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-4 font-mono">
      {/* Top Selector & Run Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex-1 space-y-1">
          <label className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase tracking-wider font-semibold">
            Select Network Scenario or Ingestion Dataset
          </label>
          <div className="relative">
            <select
              value={selectedScenario}
              onChange={(e) => onSelectScenario(e.target.value)}
              className="w-full bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[#111111] dark:text-[#EDEDEA] px-3 py-2 text-xs font-mono outline-none focus:border-[#475569] transition-colors"
            >
              <optgroup label="Organizer Colab Samples (JSONL Telemetry)">
                {organizerScenarios.map((s) => (
                  <option key={s.filename} value={s.filename}>
                    {s.description || s.filename.replace(".jsonl", "")}
                  </option>
                ))}
              </optgroup>

              <optgroup label="Standard Multi-Domain Scenarios (JSON)">
                {standardScenarios.map((s) => (
                  <option key={s.filename} value={s.filename}>
                    {s.filename.replace(".json", "")} {s.description ? `- ${s.description}` : ""}
                  </option>
                ))}
              </optgroup>
            </select>
          </div>
        </div>

        <div className="shrink-0 flex items-end">
          <button
            onClick={onRunDiagnosis}
            disabled={loading || !selectedScenario}
            className={`w-full md:w-auto px-6 py-2.5 text-[#FFFFFF] dark:text-[#111111] text-xs uppercase tracking-wider font-semibold transition-all disabled:opacity-40 ${
              isChaosActive
                ? "bg-[#9A5B5B] hover:bg-[#854B4B]"
                : "bg-[#111111] dark:bg-[#EDEDEA] hover:opacity-90"
            }`}
          >
            {loading
              ? "Diagnosing Consensus..."
              : isChaosActive
              ? "Run Diagnosis (Chaos Active)"
              : "Run Diagnosis"}
          </button>
        </div>
      </div>

      {/* Embedded Data Quality Banner & Live Chaos Controls */}
      <DataQualityBanner
        score={qualityScore}
        detectedFormat={detectedFormat}
        validationErrors={validationErrors}
        transformationsCount={transformationsCount}
        isChaosActive={isChaosActive}
        onToggleChaos={onToggleChaos}
      />

      <div className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
        {currentScenario?.description || "Select a scenario to execute multi-agent diagnostic consensus."}
      </div>
    </div>
  );
};
