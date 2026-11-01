import React, { useState } from "react";

export interface TypedValidationErrorItem {
  code: string;
  field?: string | null;
  explanation: string;
  suggested_fix: string;
}

interface DataQualityBannerProps {
  score: number;
  detectedFormat: string;
  validationErrors: TypedValidationErrorItem[];
  transformationsCount: number;
  isChaosActive: boolean;
  onToggleChaos: () => void;
}

export const DataQualityBanner: React.FC<DataQualityBannerProps> = ({
  score,
  detectedFormat,
  validationErrors,
  transformationsCount,
  isChaosActive,
  onToggleChaos,
}) => {
  const [showErrorList, setShowErrorList] = useState<boolean>(false);

  const pct = Math.round(score * 100);
  const isHealthy = pct >= 85;
  const healthColor = isHealthy
    ? "text-[#5E7A6A] border-[#5E7A6A]/30 bg-[#5E7A6A]/10"
    : "text-[#A08A5B] border-[#A08A5B]/30 bg-[#A08A5B]/10";

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-4 font-mono space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: Quality Audit & Format */}
        <div className="flex items-center gap-3 flex-wrap text-xs">
          <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase font-semibold">
            Data Quality Audit:
          </span>

          <span className={`px-2 py-0.5 border text-[10px] uppercase font-semibold ${healthColor}`}>
            Health: {pct}% {isHealthy ? "Verified" : "Degraded Recovery"}
          </span>

          <span className="px-2 py-0.5 border border-[#E5E5E3] dark:border-[#2A2A2D] text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
            Format: {detectedFormat}
          </span>

          <span className="text-[10px] text-[#6B6B66] dark:text-[#888884]">
            Recovered via {transformationsCount} transformations
          </span>
        </div>

        {/* Right: Chaos Mode Live Toggle */}
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <span className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">
              Chaos Injection:
            </span>
            <button
              onClick={onToggleChaos}
              className={`px-2.5 py-1 text-[10px] uppercase font-semibold border transition-all ${
                isChaosActive
                  ? "bg-[#9A5B5B] text-white border-[#9A5B5B]"
                  : "bg-[#FAFAF9] dark:bg-[#0F0F10] text-[#6B6B66] dark:text-[#888884] border-[#E5E5E3] dark:border-[#2A2A2D] hover:border-[#475569]"
              }`}
            >
              {isChaosActive ? "Chaos Active" : "Inject Chaos"}
            </button>
          </label>

          {validationErrors.length > 0 && (
            <button
              onClick={() => setShowErrorList((prev) => !prev)}
              className="text-[10px] underline text-[#475569] hover:text-[#111111] dark:hover:text-[#EDEDEA]"
            >
              {showErrorList ? "Hide Errors" : `View ${validationErrors.length} Typed Errors`}
            </button>
          )}
        </div>
      </div>

      {/* Expandable Typed Errors Breakdown */}
      {showErrorList && validationErrors.length > 0 && (
        <div className="pt-3 border-t border-[#E5E5E3] dark:border-[#2A2A2D] space-y-2">
          <div className="text-[10px] uppercase tracking-wider text-[#A08A5B] font-semibold">
            Gateway Typed Validation Errors ({validationErrors.length})
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {validationErrors.map((err, idx) => (
              <div
                key={idx}
                className="p-2.5 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] space-y-0.5"
              >
                <div className="flex items-center justify-between text-[10px]">
                  <span className="font-semibold text-[#9A5B5B]">{err.code}</span>
                  {err.field && <span className="text-[#6B6B66] dark:text-[#888884]">Field: {err.field}</span>}
                </div>
                <div className="text-[#111111] dark:text-[#EDEDEA]">{err.explanation}</div>
                <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] italic">
                  Suggested Fix: {err.suggested_fix}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

