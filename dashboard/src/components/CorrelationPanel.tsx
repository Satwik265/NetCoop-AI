import React from "react";
import { UnifiedDiagnosticReport, EnvelopeLogItem } from "../types/protocol";

interface CorrelationPanelProps {
  report: UnifiedDiagnosticReport | null;
  envelopes: EnvelopeLogItem[];
  currentIndex: number;
}

export const CorrelationPanel: React.FC<CorrelationPanelProps> = ({
  report,
  envelopes,
  currentIndex,
}) => {
  // Aggregate hypotheses from envelopes up to current scrub index
  const visibleEnvelopes = envelopes.slice(0, currentIndex + 1);

  // Collect hypotheses from all visible envelopes
  const allHypotheses: Array<{
    id: string;
    agent: string;
    cause: string;
    confidence: number;
    supporting: string[];
    refuting: string[];
    iteration: number;
  }> = [];

  // Collect inquiries from all visible envelopes
  const allInquiries: Array<{
    id: string;
    fromAgent: string;
    targetAgent: string;
    question: string;
    targetEntity: string;
    iteration: number;
  }> = [];

  for (const env of visibleEnvelopes) {
    if (env.payload?.hypotheses) {
      for (const h of env.payload.hypotheses) {
        allHypotheses.push({
          id: h.hypothesis_id || Math.random().toString(),
          agent: env.sender,
          cause: h.probable_cause,
          confidence: h.confidence ?? 0,
          supporting: h.supporting_observation_ids || [],
          refuting: h.refuting_observation_ids || [],
          iteration: env.context?.iteration ?? 0,
        });
      }
    }

    if (env.payload?.inquiries) {
      for (const inq of env.payload.inquiries) {
        allInquiries.push({
          id: inq.inquiry_id || Math.random().toString(),
          fromAgent: env.sender,
          targetAgent: inq.target_agent,
          question: inq.question,
          targetEntity: inq.target_entity,
          iteration: env.context?.iteration ?? 0,
        });
      }
    }
  }

  // Deduplicate latest hypothesis per cause
  const latestByCause: Record<string, typeof allHypotheses[0]> = {};
  for (const h of allHypotheses) {
    latestByCause[h.cause] = h;
  }
  const hypothesisList = Object.values(latestByCause).sort(
    (a, b) => b.confidence - a.confidence
  );

  // Confidence score from report or top hypothesis
  const finalConfidence = report ? report.confidence : hypothesisList[0]?.confidence || 0;
  const statusCategory = report ? report.status : hypothesisList.length > 0 ? "evaluating" : "idle";

  // Arc calculations for calibrated confidence
  const radius = 45;
  const strokeWidth = 5;
  const circumference = Math.PI * radius; // Semi-circle arc
  const strokeDashoffset = circumference * (1 - finalConfidence);

  const getStatusColor = (val: number, status: string) => {
    if (status === "insufficient_evidence" || status === "inconclusive") return "#A08A5B";
    if (val >= 0.8) return "#5E7A6A";
    if (val >= 0.5) return "#475569";
    return "#9A5B5B";
  };

  const arcColor = getStatusColor(finalConfidence, statusCategory);

  return (
    <div className="bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] p-5 space-y-6">
      {/* Header and Calibrated Confidence Arc */}
      <div className="flex flex-wrap items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-4 gap-4">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider font-mono text-[#111111] dark:text-[#EDEDEA]">
            Evidence Correlation & Hypothesis Arbitration
          </h2>
          <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] font-mono">
            Mediator Round: {visibleEnvelopes[visibleEnvelopes.length - 1]?.context?.iteration ?? 0} | Evaluated Hypotheses: {hypothesisList.length}
          </div>
        </div>

        {/* Thin Arc Confidence Gauge */}
        <div className="flex items-center gap-4 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-4 py-2">
          <div className="relative w-24 h-14 flex items-end justify-center">
            <svg className="w-24 h-14 overflow-visible" viewBox="0 0 100 55">
              {/* Background Arc */}
              <path
                d="M 5 50 A 45 45 0 0 1 95 50"
                fill="none"
                stroke="currentColor"
                className="text-[#E5E5E3] dark:text-[#2A2A2D]"
                strokeWidth={strokeWidth}
                strokeLinecap="round"
              />
              {/* Foreground Arc */}
              <path
                d="M 5 50 A 45 45 0 0 1 95 50"
                fill="none"
                stroke={arcColor}
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{ transition: "stroke-dashoffset 250ms ease-out" }}
              />
            </svg>
            <div className="absolute bottom-0 text-center font-mono">
              <span className="text-sm font-bold text-[#111111] dark:text-[#EDEDEA]">
                {Math.round(finalConfidence * 100)}%
              </span>
            </div>
          </div>

          <div className="font-mono text-left">
            <div className="text-[10px] text-[#6B6B66] dark:text-[#888884] uppercase">
              Calibrated Confidence
            </div>
            <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: arcColor }}>
              {statusCategory.replace("_", " ")}
            </div>
          </div>
        </div>
      </div>

      {/* Hypothesis Scores Bars */}
      <div>
        <h3 className="text-[11px] font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884] mb-3">
          Domain Hypothesis Scores & Weights
        </h3>

        {hypothesisList.length === 0 ? (
          <div className="text-xs text-[#6B6B66] dark:text-[#888884] font-mono py-4 text-center border border-dashed border-[#E5E5E3] dark:border-[#2A2A2D]">
            Awaiting domain agent findings...
          </div>
        ) : (
          <div className="space-y-3">
            {hypothesisList.map((h, i) => {
              const pct = Math.round(h.confidence * 100);
              const isLead = i === 0 && h.confidence >= 0.7;

              return (
                <div
                  key={h.id || i}
                  className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono"
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[#475569] font-medium">[{h.agent}]</span>
                      <span className="font-semibold text-[#111111] dark:text-[#EDEDEA]">
                        {h.cause}
                      </span>
                      {isLead && (
                        <span className="px-1.5 py-0.2 bg-[#5E7A6A]/10 border border-[#5E7A6A]/30 text-[#5E7A6A] text-[9px] uppercase">
                          Leading Cause
                        </span>
                      )}
                    </div>
                    <span className="font-bold text-[#111111] dark:text-[#EDEDEA]">
                      {pct}%
                    </span>
                  </div>

                  {/* Animated Bar */}
                  <div className="w-full bg-[#E5E5E3] dark:bg-[#2A2A2D] h-2 mb-2 overflow-hidden">
                    <div
                      className="bg-[#475569] h-full transition-all duration-200 ease-out"
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  {/* Supporting / Refuting Breakdown */}
                  <div className="flex items-center justify-between text-[10px] text-[#6B6B66] dark:text-[#888884]">
                    <span>
                      Supporting Observations: {h.supporting.length > 0 ? h.supporting.join(", ") : "none"}
                    </span>
                    <span>
                      Refuting: {h.refuting.length > 0 ? h.refuting.join(", ") : "0"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Conflict Detection & Arbitration Section */}
      <div className="border-t border-[#E5E5E3] dark:border-[#2A2A2D] pt-4">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884] mb-2">
          Conflict Resolution & Arbitration
        </h3>

        {hypothesisList.length > 1 ? (
          <div className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#A08A5B]/30 text-xs font-mono space-y-1">
            <div className="text-[#A08A5B] font-semibold flex items-center gap-2">
              <span>Arbitration Applied:</span>
              <span className="text-[10px] uppercase text-[#6B6B66] dark:text-[#888884]">
                Multi-agent hypothesis divergence detected
              </span>
            </div>
            <div className="text-[11px] text-[#111111] dark:text-[#EDEDEA]">
              Rule: Physical layer (CRC/optics) and saturation signatures take precedence over derivative route flaps and transient ping jitter.
            </div>
          </div>
        ) : (
          <div className="text-xs text-[#6B6B66] dark:text-[#888884] font-mono py-2">
            No active cross-domain conflicts. Agent consensus verified.
          </div>
        )}
      </div>

      {/* Inter-Agent Inquiries (evidence_query = inquiries) */}
      <div className="border-t border-[#E5E5E3] dark:border-[#2A2A2D] pt-4">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider font-mono text-[#6B6B66] dark:text-[#888884] mb-3">
          Inter-Agent Inquiries ({allInquiries.length})
        </h3>

        {allInquiries.length === 0 ? (
          <div className="text-xs text-[#6B6B66] dark:text-[#888884] font-mono py-2">
            No cross-inquiries initiated during this run.
          </div>
        ) : (
          <div className="space-y-2">
            {allInquiries.map((inq, idx) => (
              <div
                key={inq.id || idx}
                className="p-3 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-xs font-mono"
              >
                <div className="flex items-center justify-between text-[10px] text-[#6B6B66] dark:text-[#888884] mb-1">
                  <span>
                    Query from <strong className="text-[#475569]">{inq.fromAgent}</strong> to <strong className="text-[#475569]">{inq.targetAgent}</strong>
                  </span>
                  <span>Target: {inq.targetEntity}</span>
                </div>
                <div className="text-[#111111] dark:text-[#EDEDEA] italic">
                  "{inq.question}"
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

