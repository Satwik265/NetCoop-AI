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
  isValidated?: boolean;
  recordsCount?: number;
  onRunValidation?: () => void;
  validating?: boolean;
}

export const DataQualityBanner: React.FC<DataQualityBannerProps> = ({
  score,
  detectedFormat,
  validationErrors,
  transformationsCount,
  isValidated = true,
  recordsCount,
  onRunValidation,
  validating = false,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  const pct = Math.round(score * 100);
  const isHealthy = pct >= 85;

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E2E8F0] dark:border-[#2A2A2D] p-4 text-sm font-sans space-y-3">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-bold uppercase tracking-wider text-[#0B2545] dark:text-[#94A3B8]">
            Input Quality:
          </span>

          {isValidated ? (
            <span
              className={`px-2.5 py-0.5 border text-xs font-semibold ${
                isHealthy
                  ? "text-[#15803D] bg-[#F0FDF4] border-[#15803D]/30"
                  : "text-[#B45309] bg-[#FFFBEB] border-[#B45309]/30"
              }`}
            >
              {pct}% {isHealthy ? "Verified Compliance" : "Degraded with Tolerant Recovery"}
            </span>
          ) : (
            <span className="px-2.5 py-0.5 border border-[#E2E8F0] text-xs font-semibold text-[#475569] bg-[#F8FAFC]">
              Not Yet Validated
            </span>
          )}

          <span className="px-2.5 py-0.5 border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs font-medium text-[#475569] dark:text-[#94A3B8]">
            Format: <span className="font-mono text-xs font-semibold text-[#0F172A] dark:text-[#EDEDEA]">{detectedFormat}</span>
          </span>

          {isValidated && transformationsCount > 0 && (
            <span className="text-xs text-[#475569] dark:text-[#94A3B8]">
              {transformationsCount} field transformation{transformationsCount === 1 ? "" : "s"} applied
            </span>
          )}

          {recordsCount !== undefined && recordsCount > 0 && (
            <span className="text-xs text-[#475569] dark:text-[#94A3B8]">
              ({recordsCount} telemetry records inspected)
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {onRunValidation && (
            <button
              onClick={onRunValidation}
              disabled={validating}
              className="px-3 py-1 text-xs border border-[#133E87] text-[#133E87] hover:bg-[#EEF4FB] font-semibold transition-colors disabled:opacity-50"
            >
              {validating ? "Validating Input..." : "Verify Input"}
            </button>
          )}

          <button
            onClick={() => setIsExpanded((prev) => !prev)}
            className="text-xs text-[#133E87] dark:text-[#3A86FF] hover:underline font-semibold"
          >
            {isExpanded ? "Hide Details" : validationErrors.length > 0 ? `Review ${validationErrors.length} Issue${validationErrors.length === 1 ? "" : "s"}` : "View Validation Details"}
          </button>
        </div>
      </div>

      {/* Expandable Validation Details */}
      {isExpanded && (
        <div className="pt-3 border-t border-[#E2E8F0] dark:border-[#2A2A2D] space-y-3">
          {!isValidated ? (
            <p className="text-xs text-[#475569]">
              Dataset input has not been formally verified against RFC 8259 or the NetCoop telemetry schema. Run verification or execute diagnosis to audit input health.
            </p>
          ) : validationErrors.length === 0 ? (
            <div className="p-3 bg-[#F0FDF4] border border-[#15803D]/20 text-[#15803D] text-xs space-y-1">
              <div className="font-semibold">All Schema Constraints Verified</div>
              <p className="text-[13px] text-[#475569]">
                All telemetry records conform to required timestamp formatting, device identifiers, and metric units with zero syntax or format errors.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-xs font-bold uppercase tracking-wider text-[#B45309]">
                Detected Input Discrepancies ({validationErrors.length})
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {validationErrors.map((err, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-[#F8FAFC] dark:bg-[#0B132B] border border-[#E2E8F0] dark:border-[#2A2A2D] text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold text-[#DC2626]">{err.code}</span>
                      {err.field && (
                        <span className="font-mono text-xs text-[#475569] dark:text-[#94A3B8]">
                          Target Field: {err.field}
                        </span>
                      )}
                    </div>
                    <div className="text-[#0F172A] dark:text-[#F1F5F9] font-medium">{err.explanation}</div>
                    <div className="text-xs text-[#475569] dark:text-[#94A3B8]">
                      <strong>Recommended Fix:</strong> {err.suggested_fix}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
