import React from "react";
import { EvidenceItem } from "../types/protocol";

interface Props {
  evidence: EvidenceItem[];
  missingEvidence?: string[];
}

export const EvidenceCard: React.FC<Props> = ({ evidence, missingEvidence = [] }) => {
  return (
    <div className="bg-[#161618] border border-[#2A2A2D] p-5">
      <div className="flex items-center justify-between border-b border-[#2A2A2D] pb-3 mb-4">
        <h2 className="text-sm font-semibold tracking-wide uppercase font-mono text-[#EDEDEA]">
          Corroborated Evidence Chains ({evidence.length})
        </h2>
      </div>

      {evidence.length === 0 ? (
        <div className="text-xs text-[#888884] font-mono py-4 text-center">
          No corroborated evidence items recorded.
        </div>
      ) : (
        <div className="space-y-3">
          {evidence.map((item, idx) => {
            const isCrit = item.severity === "critical";
            const isWarn = item.severity === "warning";
            const sevColor = isCrit
              ? "text-[#9A5B5B] border-[#9A5B5B]/30 bg-[#9A5B5B]/10"
              : isWarn
              ? "text-[#A08A5B] border-[#A08A5B]/30 bg-[#A08A5B]/10"
              : "text-[#888884] border-[#2A2A2D] bg-[#0F0F10]";

            return (
              <div
                key={idx}
                className="p-3 bg-[#0F0F10] border border-[#2A2A2D] flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[#475569] font-medium uppercase">
                      [{item.source_agent}]
                    </span>
                    <span className="font-mono text-[#888884]">{item.category}</span>
                    <span className={`px-2 py-0.5 border text-[10px] font-mono uppercase ${sevColor}`}>
                      {item.severity}
                    </span>
                  </div>
                  <div className="text-[#EDEDEA] font-mono">
                    <span className="text-[#888884]">Entity:</span> {item.entity}
                  </div>
                  <div className="text-[#EDEDEA]">{item.finding}</div>
                </div>

                {item.value !== undefined && item.unit && (
                  <div className="text-right font-mono bg-[#161618] px-3 py-2 border border-[#2A2A2D] shrink-0">
                    <div className="text-[10px] text-[#888884] uppercase">Telemetry</div>
                    <div className="text-xs font-semibold text-[#EDEDEA]">
                      {item.value} {item.unit}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {missingEvidence.length > 0 && (
        <div className="mt-5 pt-4 border-t border-[#2A2A2D]">
          <h3 className="text-xs font-mono uppercase text-[#A08A5B] font-medium mb-2">
            Prerequisite Corroboration Missing
          </h3>
          <ul className="space-y-1">
            {missingEvidence.map((m, i) => (
              <li key={i} className="text-xs font-mono text-[#888884] flex items-center gap-2">
                <span className="text-[#A08A5B]">-</span> {m}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

